use crate::types::{ChunkData, NodeKind, SymbolInfo};

/// Approximate token count (~4 chars per token heuristic for MVP1).
pub fn estimate_tokens(text: &str) -> usize {
    if text.is_empty() {
        return 0;
    }
    (text.len() + 3) / 4
}

const MAX_CHUNK_TOKENS: usize = 768;
const OVERLAP_TOKENS: usize = 64;

/// Symbol-first chunking; oversized symbols split with overlap.
pub fn chunk_symbol(
    space: &str,
    rel_path: &str,
    source: &str,
    symbol: &SymbolInfo,
) -> Vec<ChunkData> {
    let text = extract_text(source, symbol.start_byte, symbol.end_byte);
    let tokens = estimate_tokens(&text);
    if tokens <= MAX_CHUNK_TOKENS {
        let node_id = crate::node_id::compute_node_id(
            space,
            rel_path,
            symbol.kind,
            Some(&symbol.name),
            symbol.start_line,
            symbol.end_line,
        );
        return vec![ChunkData {
            node_id,
            text,
            kind: symbol.kind,
            rel_path: rel_path.to_string(),
            symbol: Some(symbol.name.clone()),
            start_line: symbol.start_line,
            end_line: symbol.end_line,
        }];
    }
    split_oversized(space, rel_path, &text, symbol)
}

/// File-level chunk when AST parse fails or unsupported language.
pub fn chunk_file(space: &str, rel_path: &str, source: &str) -> Vec<ChunkData> {
    let symbol = crate::parse::file_fallback_symbol(source);
    let node_id = crate::node_id::compute_node_id(
        space,
        rel_path,
        NodeKind::File,
        None,
        symbol.start_line,
        symbol.end_line,
    );
    vec![ChunkData {
        node_id,
        text: source.to_string(),
        kind: NodeKind::File,
        rel_path: rel_path.to_string(),
        symbol: None,
        start_line: symbol.start_line,
        end_line: symbol.end_line,
    }]
}

fn extract_text(source: &str, start: usize, end: usize) -> String {
    let end = end.min(source.len());
    let start = start.min(end);
    source[start..end].to_string()
}

fn split_oversized(
    space: &str,
    rel_path: &str,
    text: &str,
    symbol: &SymbolInfo,
) -> Vec<ChunkData> {
    let chars_per_token = 4;
    let chunk_chars = MAX_CHUNK_TOKENS * chars_per_token;
    let overlap_chars = OVERLAP_TOKENS * chars_per_token;
    let mut chunks = Vec::new();
    let mut start = 0;
    let mut part = 0;
    while start < text.len() {
        let end = (start + chunk_chars).min(text.len());
        let slice = &text[start..end];
        let name = format!("{}#part{}", symbol.name, part);
        let node_id = crate::node_id::compute_node_id(
            space,
            rel_path,
            symbol.kind,
            Some(&name),
            symbol.start_line,
            symbol.end_line,
        );
        chunks.push(ChunkData {
            node_id,
            text: slice.to_string(),
            kind: symbol.kind,
            rel_path: rel_path.to_string(),
            symbol: Some(name),
            start_line: symbol.start_line,
            end_line: symbol.end_line,
        });
        if end >= text.len() {
            break;
        }
        start = end.saturating_sub(overlap_chars);
        part += 1;
    }
    chunks
}
