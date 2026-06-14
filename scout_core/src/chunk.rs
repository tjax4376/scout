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

fn floor_char_boundary(s: &str, mut index: usize) -> usize {
    index = index.min(s.len());
    while index > 0 && !s.is_char_boundary(index) {
        index -= 1;
    }
    index
}

fn extract_text(source: &str, start: usize, end: usize) -> String {
    let end = floor_char_boundary(source, end.min(source.len()));
    let start = floor_char_boundary(source, start.min(end));
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
        let target_end = start.saturating_add(chunk_chars).min(text.len());
        let mut end = floor_char_boundary(text, target_end);
        // target_end may land inside a multi-byte char; include at least one full char
        if end <= start {
            end = text[start..]
                .char_indices()
                .nth(1)
                .map(|(off, _)| start + off)
                .unwrap_or(text.len());
        }
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
        start = floor_char_boundary(text, end.saturating_sub(overlap_chars));
        if start >= end {
            start = end;
        }
        part += 1;
    }
    chunks
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{NodeKind, SymbolInfo};

    fn greek_symbol(source: &str) -> SymbolInfo {
        SymbolInfo {
            name: "_seg_20".into(),
            kind: NodeKind::Function,
            start_byte: 0,
            end_byte: source.len(),
            start_line: 1,
            end_line: source.lines().count() as u32,
        }
    }

    #[test]
    fn split_oversized_respects_utf8_boundaries() {
        // Greek chars are 2–3 bytes each; byte-aligned split at 3072 hits mid-char
        let line = format!(
            "def _seg_20():\n    return [(0x1F5F, \"M\", \"{}\"),]\n",
            "ὗ".repeat(1200)
        );
        let source = line.repeat(3);
        let symbol = greek_symbol(&source);
        let chunks = split_oversized("space", "sym.py", &source, &symbol);
        assert!(!chunks.is_empty());
        for chunk in &chunks {
            assert!(chunk.text.is_char_boundary(chunk.text.len()));
        }
    }

    #[test]
    fn extract_text_floors_to_char_boundary() {
        let source = "abcὗdef";
        let greek_start = "abc".len();
        let mid_greek = greek_start + 1;
        let text = extract_text(source, 0, mid_greek);
        assert_eq!(text, "abc");
    }
}
