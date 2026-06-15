use std::collections::HashSet;

use crate::graph::CodeGraph;
use crate::index::{get_chunk, vector_search, RawSearchHit};
use crate::types::{
    NeighborHit, NodeLookupHit, SearchFilters, SearchHit, SearchResponse, SymbolEntry,
    SymbolListResponse,
};

const SNIPPET_LEN: usize = 500;
const NEIGHBOR_CAP: usize = 20;

/// Format search hits with snippets, breadcrumbs, and neighbors.
pub fn format_search_response(
    graph: &CodeGraph,
    raw_hits: Vec<RawSearchHit>,
    stale: bool,
    index_version: &str,
) -> SearchResponse {
    let hits = raw_hits
        .into_iter()
        .map(|h| format_search_hit(graph, h))
        .collect();
    SearchResponse {
        hits,
        stale,
        index_version: index_version.to_string(),
    }
}

fn format_search_hit(graph: &CodeGraph, raw: RawSearchHit) -> SearchHit {
    let snippet = truncate_snippet(&raw.text, SNIPPET_LEN);
    let breadcrumb = build_breadcrumb(graph, &raw.node_id);
    let neighbors = compute_search_neighbors(graph, &raw.node_id);
    SearchHit {
        node_id: raw.node_id,
        kind: raw.kind,
        symbol: raw.symbol,
        rel_path: raw.rel_path,
        start_line: raw.start_line,
        end_line: raw.end_line,
        score: raw.score,
        snippet,
        compressed_text: raw.text.clone(),
        breadcrumb,
        neighbors,
    }
}

fn format_node_lookup(graph: &CodeGraph, raw: RawSearchHit) -> NodeLookupHit {
    let breadcrumb = build_breadcrumb(graph, &raw.node_id);
    let neighbors = compute_search_neighbors(graph, &raw.node_id);
    let location_ref = graph
        .get_node(&raw.node_id)
        .map(|n| n.location_ref.clone())
        .unwrap_or_default();
    NodeLookupHit {
        node_id: raw.node_id,
        kind: raw.kind,
        symbol: raw.symbol,
        rel_path: raw.rel_path,
        start_line: raw.start_line,
        end_line: raw.end_line,
        location_ref,
        score: 0.0,
        text: raw.text.clone(),
        compressed_text: raw.text,
        breadcrumb,
        neighbors,
    }
}

/// Node lookup from graph only (no sqlite chunk).
pub fn get_node_from_graph(
    graph: &CodeGraph,
    node_id: &str,
) -> crate::error::ScoutResult<NodeLookupHit> {
    let node = graph
        .get_node(node_id)
        .ok_or_else(|| crate::error::ScoutError::NotFound(node_id.to_string()))?;
    let breadcrumb = build_breadcrumb(graph, node_id);
    let neighbors = compute_search_neighbors(graph, node_id);
    Ok(NodeLookupHit {
        node_id: node_id.to_string(),
        kind: node.kind.as_str().to_string(),
        symbol: node.symbol.clone(),
        rel_path: node.rel_path.clone(),
        start_line: node.start_line,
        end_line: node.end_line,
        location_ref: node.location_ref.clone(),
        score: 0.0,
        text: String::new(),
        compressed_text: String::new(),
        breadcrumb,
        neighbors,
    })
}

fn truncate_snippet(text: &str, max: usize) -> String {
    if text.len() <= max {
        return text.to_string();
    }
    let mut end = max;
    while end > 0 && !text.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}…", &text[..end])
}

fn build_breadcrumb(graph: &CodeGraph, node_id: &str) -> String {
    let mut parts = Vec::new();
    let mut current = node_id.to_string();
    for _ in 0..16 {
        let node = match graph.get_node(&current) {
            Some(n) => n,
            None => break,
        };
        let label = node
            .symbol
            .clone()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| {
                if node.rel_path.is_empty() {
                    ".".to_string()
                } else {
                    node.rel_path.rsplit('/').next().unwrap_or(&node.rel_path).to_string()
                }
            });
        parts.push(label);
        match graph.contains_parent(&current) {
            Some(p) => current = p,
            None => break,
        }
    }
    parts.reverse();
    parts.join(" > ")
}

/// Anchor pivot neighbors for search hits: up 1 via contains parent, down 3 BFS.
fn compute_search_neighbors(graph: &CodeGraph, anchor_id: &str) -> Vec<NeighborHit> {
    let pivot = graph
        .contains_parent(anchor_id)
        .unwrap_or_else(|| anchor_id.to_string());
    let mut exclude = HashSet::new();
    exclude.insert(anchor_id.to_string());
    neighbors_from_pivot(graph, &pivot, 3, NEIGHBOR_CAP, &exclude)
}

fn neighbors_from_pivot(
    graph: &CodeGraph,
    pivot_id: &str,
    max_depth: u8,
    max_nodes: usize,
    exclude: &HashSet<String>,
) -> Vec<NeighborHit> {
    let raw = graph.bfs_neighbors(pivot_id, max_depth, max_nodes, exclude);
    raw.into_iter()
        .filter_map(|(id, edge, depth)| {
            let node = graph.get_node(&id)?;
            Some(NeighborHit {
                node_id: id,
                kind: node.kind.as_str().to_string(),
                symbol: node.symbol.clone(),
                rel_path: node.rel_path.clone(),
                location_ref: node.location_ref.clone(),
                edge: edge.as_str().to_string(),
                depth,
            })
        })
        .collect()
}

/// Expand neighbors from a node without anchor pivot (graph-only API).
pub fn expand_neighbors(
    graph: &CodeGraph,
    node_id: &str,
    depth: u8,
    max_nodes: usize,
) -> crate::error::ScoutResult<Vec<NeighborHit>> {
    if graph.get_node(node_id).is_none() {
        return Err(crate::error::ScoutError::NotFound(node_id.to_string()));
    }
    let depth = depth.clamp(1, 5);
    let max_nodes = max_nodes.clamp(1, 100);
    let exclude = HashSet::new();
    Ok(neighbors_from_pivot(graph, node_id, depth, max_nodes, &exclude))
}

/// List graph symbols under a path prefix without vector search.
pub fn list_symbols(
    graph: &CodeGraph,
    path_prefix: &str,
    kinds: &[crate::types::NodeKind],
) -> SymbolListResponse {
    let symbols = graph
        .list_symbols(path_prefix, kinds)
        .into_iter()
        .map(|n| SymbolEntry {
            node_id: n.node_id,
            kind: n.kind.as_str().to_string(),
            symbol: n.symbol,
            rel_path: n.rel_path,
            location_ref: n.location_ref,
            start_line: n.start_line,
            end_line: n.end_line,
        })
        .collect();
    SymbolListResponse { symbols }
}

/// Run vector search and format response.
pub fn search(
    graph: &CodeGraph,
    conn: &rusqlite::Connection,
    query_embedding: &[f32],
    filters: &SearchFilters,
    stale: bool,
    index_version: &str,
) -> crate::error::ScoutResult<SearchResponse> {
    let raw = vector_search(
        conn,
        query_embedding,
        filters.top_k,
        filters.min_score,
        &filters.kinds,
        filters.path_prefix.as_deref(),
    )?;
    Ok(format_search_response(graph, raw, stale, index_version))
}

/// Node lookup — full chunk text, no snippet truncation.
pub fn get_node(
    graph: &CodeGraph,
    conn: &rusqlite::Connection,
    node_id: &str,
) -> crate::error::ScoutResult<NodeLookupHit> {
    let raw = get_chunk(conn, node_id)?;
    Ok(format_node_lookup(graph, raw))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::graph::CodeGraph;
    use crate::index::{insert_chunks, open_index, prepare_index};
    use crate::types::{ChunkData, GraphNodeData, NodeKind};

    fn graph_with_long_chunk() -> (CodeGraph, std::path::PathBuf) {
        let mut graph = CodeGraph::new();
        let long_text = "x".repeat(600);
        graph.add_node(GraphNodeData {
            node_id: "node1".into(),
            kind: NodeKind::Function,
            symbol: Some("big_fn".into()),
            rel_path: "src/a.py".into(),
            start_line: 1,
            end_line: 50,
            location_ref: "src=/src/a.py".into(),
        });

        let dir = std::env::temp_dir().join(format!(
            "scout-node-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let db = dir.join("test.db");
        let conn = open_index(&db).unwrap();
        prepare_index(&conn, "m", 4).unwrap();
        let chunk = ChunkData {
            node_id: "node1".into(),
            text: long_text.clone(),
            kind: NodeKind::Function,
            rel_path: "src/a.py".into(),
            symbol: Some("big_fn".into()),
            start_line: 1,
            end_line: 50,
        };
        insert_chunks(&conn, &[chunk], &[vec![0.1, 0.2, 0.3, 0.4]]).unwrap();
        (graph, dir)
    }

    #[test]
    fn node_lookup_returns_full_text() {
        let (graph, dir) = graph_with_long_chunk();
        let conn = open_index(&dir.join("test.db")).unwrap();
        let hit = get_node(&graph, &conn, "node1").unwrap();
        assert_eq!(hit.text.len(), 600);
        assert_eq!(hit.compressed_text.len(), 600);
        assert_eq!(hit.text, hit.compressed_text);
        assert!(!hit.text.contains('…'));
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn list_symbols_filters_prefix() {
        let mut graph = CodeGraph::new();
        graph.add_node(GraphNodeData {
            node_id: "a".into(),
            kind: NodeKind::Function,
            symbol: Some("f".into()),
            rel_path: "scout/embed/x.py".into(),
            start_line: 1,
            end_line: 2,
            location_ref: "scout=/scout/embed/x.py".into(),
        });
        graph.add_node(GraphNodeData {
            node_id: "b".into(),
            kind: NodeKind::File,
            symbol: None,
            rel_path: "other/y.py".into(),
            start_line: 1,
            end_line: 2,
            location_ref: "other=/other/y.py".into(),
        });
        let resp = list_symbols(&graph, "scout/embed/", &[]);
        assert_eq!(resp.symbols.len(), 1);
        assert_eq!(resp.symbols[0].node_id, "a");
    }

    #[test]
    fn expand_neighbors_unknown_node_errors() {
        let graph = CodeGraph::new();
        let err = expand_neighbors(&graph, "missing", 3, 10).unwrap_err();
        assert!(matches!(err, crate::error::ScoutError::NotFound(_)));
    }
}
