//! Segment-safe workspace path prefix matching.

/// Normalize a path prefix (posix-style, no leading slash).
pub fn normalize_prefix(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    let mut parts: Vec<&str> = Vec::new();
    for component in trimmed.split('/').filter(|s| !s.is_empty() && *s != ".") {
        if component == ".." {
            parts.pop();
        } else {
            parts.push(component);
        }
    }
    parts.join("/")
}

/// True when `rel_path` is under `path_prefix` (segment-safe).
///
/// Trailing slash on prefix means children only (exclude exact directory node).
pub fn rel_path_matches_prefix(rel_path: &str, path_prefix: &str) -> bool {
    if path_prefix.is_empty() {
        return !rel_path.is_empty();
    }
    let raw = path_prefix.trim();
    if raw.is_empty() {
        return true;
    }
    let children_only = raw.ends_with('/');
    let prefix = normalize_prefix(raw);
    if prefix.is_empty() {
        return true;
    }
    if rel_path == prefix {
        return !children_only;
    }
    rel_path.starts_with(&format!("{prefix}/"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trailing_slash_excludes_directory_node() {
        assert!(!rel_path_matches_prefix("src", "src/"));
        assert!(rel_path_matches_prefix("src/auth.py", "src/"));
    }

    #[test]
    fn no_trailing_slash_includes_directory_node() {
        assert!(rel_path_matches_prefix("src", "src"));
        assert!(rel_path_matches_prefix("src/auth.py", "src"));
    }

    #[test]
    fn prefix_does_not_match_similar_names() {
        assert!(!rel_path_matches_prefix("src_extra/foo.py", "src/"));
        assert!(!rel_path_matches_prefix("src_extra/foo.py", "src"));
    }
}
