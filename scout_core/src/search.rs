use std::collections::HashSet;

use crate::graph::CodeGraph;
use crate::index::{get_chunk, vector_search, RawSearchHit};
use crate::types::{NeighborHit, SearchFilters, SearchHit, SearchResponse};

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
        .map(|h| format_hit(graph, h))
        .collect();
    SearchResponse {
        hits,
        stale,
        index_version: index_version.to_string(),
    }
}

fn format_hit(graph: &CodeGraph, raw: RawSearchHit) -> SearchHit {
    let snippet = truncate_snippet(&raw.text, SNIPPET_LEN);
    let breadcrumb = build_breadcrumb(graph, &raw.node_id);
    let neighbors = compute_neighbors(graph, &raw.node_id);
    SearchHit {
        node_id: raw.node_id,
        kind: raw.kind,
        symbol: raw.symbol,
        rel_path: raw.rel_path,
        start_line: raw.start_line,
        end_line: raw.end_line,
        score: raw.score,
        snippet,
        breadcrumb,
        neighbors,
    }
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

/// Anchor pivot: up 1 via contains parent, down 3 BFS from pivot.
fn compute_neighbors(graph: &CodeGraph, anchor_id: &str) -> Vec<NeighborHit> {
    let pivot = graph
        .contains_parent(anchor_id)
        .unwrap_or_else(|| anchor_id.to_string());
    let mut exclude = HashSet::new();
    exclude.insert(anchor_id.to_string());
    let raw = graph.bfs_neighbors(&pivot, 3, NEIGHBOR_CAP, &exclude);
    raw.into_iter()
        .filter_map(|(id, edge, depth)| {
            let node = graph.get_node(&id)?;
            Some(NeighborHit {
                node_id: id,
                kind: node.kind.as_str().to_string(),
                symbol: node.symbol.clone(),
                rel_path: node.rel_path.clone(),
                edge: edge.as_str().to_string(),
                depth,
            })
        })
        .collect()
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

/// Node lookup wrapper.
pub fn get_node(
    graph: &CodeGraph,
    conn: &rusqlite::Connection,
    node_id: &str,
) -> crate::error::ScoutResult<SearchHit> {
    let raw = get_chunk(conn, node_id)?;
    Ok(format_hit(graph, raw))
}
