use blake3::Hasher;

use crate::types::NodeKind;

/// Deterministic node_id: blake3(space + rel_path + kind + symbol + lines) → 16 hex.
pub fn compute_node_id(
    space: &str,
    rel_path: &str,
    kind: NodeKind,
    symbol: Option<&str>,
    start_line: u32,
    end_line: u32,
) -> String {
    let mut hasher = Hasher::new();
    hasher.update(space.as_bytes());
    hasher.update(b"|");
    hasher.update(rel_path.as_bytes());
    hasher.update(b"|");
    hasher.update(kind.as_str().as_bytes());
    hasher.update(b"|");
    hasher.update(symbol.unwrap_or("").as_bytes());
    hasher.update(b"|");
    hasher.update(start_line.to_string().as_bytes());
    hasher.update(b"|");
    hasher.update(end_line.to_string().as_bytes());
    let hash = hasher.finalize();
    hash.to_hex()[..16].to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stable_node_id() {
        let a = compute_node_id("s", "src/a.rs", NodeKind::Function, Some("main"), 1, 10);
        let b = compute_node_id("s", "src/a.rs", NodeKind::Function, Some("main"), 1, 10);
        assert_eq!(a, b);
        assert_eq!(a.len(), 16);
    }
}
