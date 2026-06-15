/// Format `{folder_name}={/rel_path}` for agent file resolution.
/// Root-level files use `.` as folder_name (e.g. `.=/README.md`).
pub fn compute_location_ref(rel_path: &str) -> String {
    if rel_path.is_empty() {
        return String::new();
    }
    let normalized = rel_path.replace('\\', "/");
    let folder_name = if normalized.contains('/') {
        normalized
            .split('/')
            .next()
            .unwrap_or(".")
            .to_string()
    } else {
        ".".to_string()
    };
    format!("{folder_name}=/{normalized}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nested_path_location_ref() {
        assert_eq!(
            compute_location_ref("scout_core/src/graph.rs"),
            "scout_core=/scout_core/src/graph.rs"
        );
    }

    #[test]
    fn root_level_file_location_ref() {
        assert_eq!(compute_location_ref("README.md"), ".=/README.md");
    }

    #[test]
    fn empty_path_returns_empty() {
        assert_eq!(compute_location_ref(""), "");
    }
}
