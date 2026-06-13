use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use petgraph::graph::{DiGraph, NodeIndex};
use petgraph::visit::EdgeRef;
use petgraph::Direction;

use crate::chunk::{chunk_file, chunk_symbol};
use crate::error::{ScoutError, ScoutResult};
use crate::node_id::compute_node_id;
use crate::parse::extract_symbols;
use crate::scan::resolve_path;
use crate::types::ScannedFile;
use crate::types::{
    ChunkData, EdgeKind, GraphEdgeData, GraphNodeData, GraphSnapshot, NodeKind, SymbolInfo,
};

/// In-memory code graph with node lookup by id.
pub struct CodeGraph {
    graph: DiGraph<GraphNodeData, EdgeKind>,
    id_to_index: HashMap<String, NodeIndex>,
    index_to_id: HashMap<NodeIndex, String>,
}

impl Default for CodeGraph {
    fn default() -> Self {
        Self::new()
    }
}

impl CodeGraph {
    pub fn new() -> Self {
        Self {
            graph: DiGraph::new(),
            id_to_index: HashMap::new(),
            index_to_id: HashMap::new(),
        }
    }

    pub fn add_node(&mut self, data: GraphNodeData) -> NodeIndex {
        if let Some(&idx) = self.id_to_index.get(&data.node_id) {
            return idx;
        }
        let id = data.node_id.clone();
        let idx = self.graph.add_node(data);
        self.id_to_index.insert(id.clone(), idx);
        self.index_to_id.insert(idx, id);
        idx
    }

    pub fn add_edge(&mut self, from_id: &str, to_id: &str, kind: EdgeKind) -> ScoutResult<()> {
        let from = self
            .id_to_index
            .get(from_id)
            .copied()
            .ok_or_else(|| ScoutError::NotFound(from_id.to_string()))?;
        let to = self
            .id_to_index
            .get(to_id)
            .copied()
            .ok_or_else(|| ScoutError::NotFound(to_id.to_string()))?;
        self.graph.add_edge(from, to, kind);
        Ok(())
    }

    pub fn get_node(&self, node_id: &str) -> Option<&GraphNodeData> {
        self.id_to_index
            .get(node_id)
            .map(|&idx| &self.graph[idx])
    }

    pub fn node_index(&self, node_id: &str) -> Option<NodeIndex> {
        self.id_to_index.get(node_id).copied()
    }

    pub fn inner(&self) -> &DiGraph<GraphNodeData, EdgeKind> {
        &self.graph
    }

    pub fn snapshot(&self, index_version: &str) -> GraphSnapshot {
        let nodes: Vec<GraphNodeData> = self.graph.node_weights().cloned().collect();
        let edges: Vec<GraphEdgeData> = self
            .graph
            .edge_references()
            .map(|e| GraphEdgeData {
                from_id: self.index_to_id[&e.source()].clone(),
                to_id: self.index_to_id[&e.target()].clone(),
                kind: *e.weight(),
            })
            .collect();
        GraphSnapshot {
            nodes,
            edges,
            index_version: index_version.to_string(),
        }
    }

    pub fn load_from_snapshot(snapshot: &GraphSnapshot) -> Self {
        let mut g = Self::new();
        for node in &snapshot.nodes {
            g.add_node(node.clone());
        }
        for edge in &snapshot.edges {
            let _ = g.add_edge(&edge.from_id, &edge.to_id, edge.kind);
        }
        g
    }

    /// Parent via incoming `contains` edge.
    pub fn contains_parent(&self, node_id: &str) -> Option<String> {
        let idx = self.node_index(node_id)?;
        self.graph
            .neighbors_directed(idx, Direction::Incoming)
            .find_map(|n| {
                self.graph
                    .edges_directed(n, Direction::Outgoing)
                    .find(|e| e.target() == idx && *e.weight() == EdgeKind::Contains)
                    .map(|_| self.index_to_id[&n].clone())
            })
    }

    /// BFS neighbors from pivot up to max_depth via allowed edges.
    pub fn bfs_neighbors(
        &self,
        pivot_id: &str,
        max_depth: u8,
        cap: usize,
        exclude: &HashSet<String>,
    ) -> Vec<(String, EdgeKind, u8)> {
        let start = match self.node_index(pivot_id) {
            Some(i) => i,
            None => return vec![],
        };
        let allowed = [EdgeKind::Contains, EdgeKind::Imports, EdgeKind::Calls];
        let mut queue = std::collections::VecDeque::new();
        let mut seen = HashSet::new();
        let mut out = Vec::new();

        queue.push_back((start, 0u8));
        seen.insert(start);

        while let Some((idx, depth)) = queue.pop_front() {
            if depth >= max_depth {
                continue;
            }
            for edge in self.graph.edges_directed(idx, Direction::Outgoing) {
                if !allowed.contains(edge.weight()) {
                    continue;
                }
                let target = edge.target();
                if seen.contains(&target) {
                    continue;
                }
                seen.insert(target);
                let tid = self.index_to_id[&target].clone();
                if exclude.contains(&tid) {
                    continue;
                }
                let nd = depth + 1;
                out.push((tid.clone(), *edge.weight(), nd));
                if out.len() >= cap {
                    return out;
                }
                queue.push_back((target, nd));
            }
        }
        out
    }
}

/// Build graph + chunks from scanned files.
pub struct BuildOutput {
    pub graph: CodeGraph,
    pub chunks: Vec<ChunkData>,
}

pub fn build_graph_and_chunks(
    space: &str,
    root: &Path,
    files: &[ScannedFile],
    index_version: &str,
) -> ScoutResult<BuildOutput> {
    let mut graph = CodeGraph::new();
    let mut chunks = Vec::new();
    let mut dir_nodes: HashMap<String, String> = HashMap::new();

    // Root directory node
    let root_id = compute_node_id(space, "", NodeKind::Directory, Some("."), 0, 0);
    graph.add_node(GraphNodeData {
        node_id: root_id.clone(),
        kind: NodeKind::Directory,
        symbol: Some(".".to_string()),
        rel_path: String::new(),
        start_line: 0,
        end_line: 0,
    });
    dir_nodes.insert(String::new(), root_id);

    for file in files {
        ensure_dir_chain(space, &mut graph, &mut dir_nodes, &file.rel_path)?;

        let abs = resolve_path(root, &file.rel_path);
        let source = fs::read_to_string(&abs).unwrap_or_default();
        let file_id = compute_node_id(space, &file.rel_path, NodeKind::File, None, 1, 1);
        graph.add_node(GraphNodeData {
            node_id: file_id.clone(),
            kind: NodeKind::File,
            symbol: None,
            rel_path: file.rel_path.clone(),
            start_line: 1,
            end_line: source.lines().count().max(1) as u32,
        });

        if let Some(parent_dir) = parent_dir_path(&file.rel_path) {
            if let Some(parent_id) = dir_nodes.get(&parent_dir) {
                let _ = graph.add_edge(parent_id, &file_id, EdgeKind::Contains);
            }
        } else {
            let _ = graph.add_edge(&dir_nodes[""], &file_id, EdgeKind::Contains);
        }

        let symbols = extract_symbols(Path::new(&file.rel_path), &source).unwrap_or_default();
        if symbols.is_empty() {
            let file_chunks = chunk_file(space, &file.rel_path, &source);
            for c in &file_chunks {
                graph.add_node(GraphNodeData {
                    node_id: c.node_id.clone(),
                    kind: c.kind,
                    symbol: c.symbol.clone(),
                    rel_path: c.rel_path.clone(),
                    start_line: c.start_line,
                    end_line: c.end_line,
                });
                let _ = graph.add_edge(&file_id, &c.node_id, EdgeKind::Contains);
            }
            chunks.extend(file_chunks);
        } else {
            for sym in &symbols {
                add_symbol_node(space, &mut graph, &file_id, &file.rel_path, sym);
                let sym_chunks = chunk_symbol(space, &file.rel_path, &source, sym);
                chunks.extend(sym_chunks);
            }
            resolve_static_edges(space, root, &mut graph, &file.rel_path, &source, &symbols)?;
        }
    }

    let _ = index_version; // version applied in snapshot on save
    Ok(BuildOutput { graph, chunks })
}

fn parent_dir_path(rel_path: &str) -> Option<String> {
    Path::new(rel_path)
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .map(|p| p.to_string_lossy().replace('\\', "/"))
}

fn ensure_dir_chain(
    space: &str,
    graph: &mut CodeGraph,
    dir_nodes: &mut HashMap<String, String>,
    rel_path: &str,
) -> ScoutResult<()> {
    let path = Path::new(rel_path);
    let mut parts: Vec<String> = path
        .parent()
        .unwrap_or_else(|| Path::new(""))
        .components()
        .map(|c| c.as_os_str().to_string_lossy().to_string())
        .collect();

    let mut accum = String::new();
    let mut parent_id = dir_nodes.get("").cloned().unwrap_or_default();

    for part in parts.drain(..) {
        if !accum.is_empty() {
            accum.push('/');
        }
        accum.push_str(&part);
        if let Some(id) = dir_nodes.get(&accum).cloned() {
            parent_id = id;
            continue;
        }
        let dir_id = compute_node_id(space, &accum, NodeKind::Directory, Some(&part), 0, 0);
        graph.add_node(GraphNodeData {
            node_id: dir_id.clone(),
            kind: NodeKind::Directory,
            symbol: Some(part.clone()),
            rel_path: accum.clone(),
            start_line: 0,
            end_line: 0,
        });
        let _ = graph.add_edge(&parent_id, &dir_id, EdgeKind::Contains);
        dir_nodes.insert(accum.clone(), dir_id.clone());
        parent_id = dir_id;
    }
    Ok(())
}

fn add_symbol_node(
    space: &str,
    graph: &mut CodeGraph,
    file_id: &str,
    rel_path: &str,
    sym: &SymbolInfo,
) {
    let node_id = compute_node_id(
        space,
        rel_path,
        sym.kind,
        Some(&sym.name),
        sym.start_line,
        sym.end_line,
    );
    graph.add_node(GraphNodeData {
        node_id: node_id.clone(),
        kind: sym.kind,
        symbol: Some(sym.name.clone()),
        rel_path: rel_path.to_string(),
        start_line: sym.start_line,
        end_line: sym.end_line,
    });
    let _ = graph.add_edge(file_id, &node_id, EdgeKind::Contains);
}

/// Best-effort static import/call resolution for MVP1.
fn resolve_static_edges(
    space: &str,
    root: &Path,
    graph: &mut CodeGraph,
    rel_path: &str,
    source: &str,
    symbols: &[SymbolInfo],
) -> ScoutResult<()> {
    let import_targets = resolve_imports(root, rel_path, source);
    let file_id = compute_node_id(space, rel_path, NodeKind::File, None, 1, 1);

    for target in import_targets {
        let target_file_id = compute_node_id(space, &target, NodeKind::File, None, 1, 1);
        if graph.get_node(&target_file_id).is_some() {
            let _ = graph.add_edge(&file_id, &target_file_id, EdgeKind::Imports);
        }
    }

    // Same-file call edges: naive identifier reference between known symbols.
    for caller in symbols {
        let caller_id = compute_node_id(
            space,
            rel_path,
            caller.kind,
            Some(&caller.name),
            caller.start_line,
            caller.end_line,
        );
        let caller_text = extract_line_range(source, caller.start_line, caller.end_line);
        for callee in symbols {
            if caller.name == callee.name {
                continue;
            }
            if caller_text.contains(&callee.name) {
                let callee_id = compute_node_id(
                    space,
                    rel_path,
                    callee.kind,
                    Some(&callee.name),
                    callee.start_line,
                    callee.end_line,
                );
                let _ = graph.add_edge(&caller_id, &callee_id, EdgeKind::Calls);
            }
        }
    }
    Ok(())
}

fn extract_line_range(source: &str, start_line: u32, end_line: u32) -> String {
    source
        .lines()
        .skip((start_line.saturating_sub(1)) as usize)
        .take((end_line.saturating_sub(start_line) + 1) as usize)
        .collect::<Vec<_>>()
        .join("\n")
}

/// Resolve imports to single unambiguous workspace-relative paths.
fn resolve_imports(root: &Path, rel_path: &str, source: &str) -> Vec<String> {
    let mut targets = Vec::new();
    let base_dir = Path::new(rel_path).parent().unwrap_or_else(|| Path::new(""));

    for line in source.lines() {
        let trimmed = line.trim();
        let import_path = if trimmed.starts_with("import ") || trimmed.starts_with("from ") {
            parse_py_import(trimmed)
        } else if trimmed.starts_with("use ") {
            parse_rust_use(trimmed)
        } else if trimmed.starts_with("import ") && rel_path.ends_with(".go") {
            parse_go_import(trimmed)
        } else if trimmed.contains("from '") || trimmed.contains("from \"") {
            parse_ts_import(trimmed)
        } else {
            None
        };

        if let Some(raw) = import_path {
            if let Some(resolved) = resolve_import_path(root, base_dir, rel_path, &raw) {
                targets.push(resolved);
            }
        }
    }
    targets
}

fn parse_py_import(line: &str) -> Option<String> {
    if line.starts_with("from ") {
        let rest = line.strip_prefix("from ")?.split(" import").next()?.trim();
        if rest.starts_with('.') {
            return None;
        }
        return Some(rest.replace('.', "/") + ".py");
    }
    if line.starts_with("import ") {
        let rest = line.strip_prefix("import ")?.split(',').next()?.trim();
        return Some(rest.replace('.', "/") + ".py");
    }
    None
}

fn parse_rust_use(line: &str) -> Option<String> {
    let rest = line.strip_prefix("use ")?;
    let path = rest.split(';').next()?.trim();
    if path.starts_with("crate::") {
        return Some(path.replace("crate::", "src/").replace("::", "/") + ".rs");
    }
    None
}

fn parse_go_import(line: &str) -> Option<String> {
    let start = line.find('"')? + 1;
    let end = line[start..].find('"')? + start;
    let path = &line[start..end];
    if path.contains('.') {
        return Some(format!("{path}.go"));
    }
    None
}

fn parse_ts_import(line: &str) -> Option<String> {
    for quote in ['\'', '"'] {
        if let Some(i) = line.find(quote) {
            let rest = &line[i + 1..];
            if let Some(j) = rest.find(quote) {
                let p = &rest[..j];
                if p.starts_with('.') {
                    return Some(normalize_ts_relative(p));
                }
            }
        }
    }
    None
}

fn normalize_ts_relative(path: &str) -> String {
    let mut out = path.trim_start_matches("./").to_string();
    if !out.ends_with(".ts") && !out.ends_with(".tsx") && !out.ends_with(".js") {
        out.push_str(".ts");
    }
    out
}

fn resolve_import_path(
    root: &Path,
    base_dir: &Path,
    rel_path: &str,
    raw: &str,
) -> Option<String> {
    let candidate = if raw.starts_with("src/") {
        root.join(raw)
    } else {
        root.join(base_dir).join(raw)
    };
    if candidate.is_file() {
        return candidate
            .strip_prefix(root)
            .ok()
            .map(|p| p.to_string_lossy().replace('\\', "/"));
    }
    // Try extension variants
    for ext in ["", ".ts", ".tsx", ".js", ".py", ".rs", ".go"] {
        let try_path = if ext.is_empty() {
            candidate.clone()
        } else {
            PathBuf::from(candidate.to_string_lossy().to_string() + ext)
        };
        if try_path.is_file() {
            return try_path
                .strip_prefix(root)
                .ok()
                .map(|p| p.to_string_lossy().replace('\\', "/"));
        }
    }
    let _ = rel_path;
    None
}

/// Serialize graph to disk.
pub fn save_graph(path: &Path, snapshot: &GraphSnapshot) -> ScoutResult<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let bytes = bincode::serialize(snapshot)
        .map_err(|e| ScoutError::Other(format!("serialize graph: {e}")))?;
    fs::write(path, bytes)?;
    Ok(())
}

/// Load graph from disk.
pub fn load_graph(path: &Path) -> ScoutResult<CodeGraph> {
    let bytes = fs::read(path)?;
    let snapshot: GraphSnapshot = bincode::deserialize(&bytes)
        .map_err(|e| ScoutError::Other(format!("deserialize graph: {e}")))?;
    Ok(CodeGraph::load_from_snapshot(&snapshot))
}
