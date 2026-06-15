use serde::{Deserialize, Serialize};

/// Node kinds per Q35 spec.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum NodeKind {
    Directory,
    File,
    Module,
    Class,
    Struct,
    Interface,
    Enum,
    Function,
    Method,
    Const,
}

impl NodeKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Directory => "directory",
            Self::File => "file",
            Self::Module => "module",
            Self::Class => "class",
            Self::Struct => "struct",
            Self::Interface => "interface",
            Self::Enum => "enum",
            Self::Function => "function",
            Self::Method => "method",
            Self::Const => "const",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "directory" => Some(Self::Directory),
            "file" => Some(Self::File),
            "module" => Some(Self::Module),
            "class" => Some(Self::Class),
            "struct" => Some(Self::Struct),
            "interface" => Some(Self::Interface),
            "enum" => Some(Self::Enum),
            "function" => Some(Self::Function),
            "method" => Some(Self::Method),
            "const" => Some(Self::Const),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum EdgeKind {
    Contains,
    Imports,
    Calls,
}

impl EdgeKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Contains => "contains",
            Self::Imports => "imports",
            Self::Calls => "calls",
        }
    }
}

/// File discovered during workspace scan.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScannedFile {
    pub rel_path: String,
    pub size: u64,
    pub mtime_secs: i64,
    pub language: Option<String>,
    pub is_binary: bool,
}

/// Extracted symbol from AST or file fallback.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolInfo {
    pub kind: NodeKind,
    pub name: String,
    pub start_line: u32,
    pub end_line: u32,
    pub start_byte: usize,
    pub end_byte: usize,
}

/// Graph node metadata (no body text in graph layer).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphNodeData {
    pub node_id: String,
    pub kind: NodeKind,
    pub symbol: Option<String>,
    pub rel_path: String,
    pub start_line: u32,
    pub end_line: u32,
    /// Agent file pointer: `{folder_name}={/rel_path}`.
    #[serde(default)]
    pub location_ref: String,
}

/// Text chunk linked to graph node.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkData {
    pub node_id: String,
    pub text: String,
    pub kind: NodeKind,
    pub rel_path: String,
    pub symbol: Option<String>,
    pub start_line: u32,
    pub end_line: u32,
}

/// Serialized edge for graph.bin.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphEdgeData {
    pub from_id: String,
    pub to_id: String,
    pub kind: EdgeKind,
}

/// Persisted graph snapshot.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphSnapshot {
    pub nodes: Vec<GraphNodeData>,
    pub edges: Vec<GraphEdgeData>,
    pub index_version: String,
}

/// Search filters.
#[derive(Debug, Clone, Default)]
pub struct SearchFilters {
    pub top_k: usize,
    pub min_score: f32,
    pub kinds: Vec<NodeKind>,
    pub path_prefix: Option<String>,
}

/// Neighbor in search response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeighborHit {
    pub node_id: String,
    pub kind: String,
    pub symbol: Option<String>,
    pub rel_path: String,
    #[serde(default)]
    pub location_ref: String,
    pub edge: String,
    pub depth: u8,
}

/// Single search hit (vector search — snippet only).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchHit {
    pub node_id: String,
    pub kind: String,
    pub symbol: Option<String>,
    pub rel_path: String,
    pub start_line: u32,
    pub end_line: u32,
    pub score: f32,
    pub snippet: String,
    /// Full stored chunk text (compressed when compression enabled at embed time).
    pub compressed_text: String,
    pub breadcrumb: String,
    pub neighbors: Vec<NeighborHit>,
}

/// Node lookup response with full indexed chunk text.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeLookupHit {
    pub node_id: String,
    pub kind: String,
    pub symbol: Option<String>,
    pub rel_path: String,
    pub start_line: u32,
    pub end_line: u32,
    #[serde(default)]
    pub location_ref: String,
    pub score: f32,
    pub text: String,
    /// Indexed chunk body (same as `text` when stored compressed).
    pub compressed_text: String,
    pub breadcrumb: String,
    pub neighbors: Vec<NeighborHit>,
}

/// Graph symbol entry (no chunk text).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolEntry {
    pub node_id: String,
    pub kind: String,
    pub symbol: Option<String>,
    pub rel_path: String,
    #[serde(default)]
    pub location_ref: String,
    pub start_line: u32,
    pub end_line: u32,
}

/// Symbol list response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolListResponse {
    pub symbols: Vec<SymbolEntry>,
}

/// Neighbor expansion response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeighborsResponse {
    pub node_id: String,
    pub neighbors: Vec<NeighborHit>,
}

/// Workspace file read response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileReadResponse {
    pub rel_path: String,
    pub start_line: u32,
    pub end_line: u32,
    pub text: String,
    pub total_lines: u32,
}

/// Full search response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResponse {
    pub hits: Vec<SearchHit>,
    pub stale: bool,
    pub index_version: String,
}

/// Per-file manifest entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestFileEntry {
    pub mtime_secs: i64,
    pub size: u64,
}

/// Embed config stored in manifest for staleness.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct EmbedManifest {
    pub provider: String,
    pub model: String,
    pub dimensions: u32,
}

/// Space manifest for staleness checks.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Manifest {
    pub files: std::collections::BTreeMap<String, ManifestFileEntry>,
    pub embed: EmbedManifest,
    pub index_version: String,
}
