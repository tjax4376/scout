//! On-demand workspace file read with path traversal guard.

use std::fs;
use std::path::{Component, Path, PathBuf};

use crate::error::{ScoutError, ScoutResult};
use crate::types::FileReadResponse;

const MAX_FILE_BYTES: usize = 512 * 1024;

/// Resolve `rel_path` under `root` and reject traversal escapes.
pub fn resolve_under_root(root: &Path, rel_path: &str) -> ScoutResult<PathBuf> {
    if rel_path.is_empty() {
        return Err(ScoutError::InvalidPath("rel_path is required".into()));
    }
    if rel_path.contains("..") {
        return Err(ScoutError::InvalidPath("path traversal not allowed".into()));
    }

    let root = root
        .canonicalize()
        .map_err(|e| ScoutError::InvalidPath(format!("invalid space root: {e}")))?;

    let mut joined = root.clone();
    for component in Path::new(rel_path).components() {
        match component {
            Component::Normal(part) => joined.push(part),
            Component::CurDir => {}
            Component::ParentDir | Component::Prefix(_) | Component::RootDir => {
                return Err(ScoutError::InvalidPath("path traversal not allowed".into()));
            }
        }
    }

    let canonical = joined
        .canonicalize()
        .map_err(|_| ScoutError::NotFound(rel_path.to_string()))?;

    if !canonical.starts_with(&root) {
        return Err(ScoutError::InvalidPath("path outside space root".into()));
    }
    Ok(canonical)
}

/// Read file or line range from workspace; cap response at 512 KiB.
pub fn read_workspace_file(
    root: &Path,
    rel_path: &str,
    start_line: Option<u32>,
    end_line: Option<u32>,
) -> ScoutResult<FileReadResponse> {
    let path = resolve_under_root(root, rel_path)?;
    if !path.is_file() {
        return Err(ScoutError::NotFound(rel_path.to_string()));
    }

    let raw = fs::read_to_string(&path)?;
    let lines: Vec<&str> = raw.split_inclusive('\n').collect();
    let total_lines = lines.len().max(1) as u32;

    let start = start_line.unwrap_or(1).max(1);
    let end = end_line.unwrap_or(total_lines).min(total_lines);
    if start > end {
        return Err(ScoutError::InvalidPath(format!(
            "start_line {start} > end_line {end}"
        )));
    }

    let slice: String = lines
        .iter()
        .skip((start - 1) as usize)
        .take((end - start + 1) as usize)
        .copied()
        .collect();

    if slice.len() > MAX_FILE_BYTES {
        return Err(ScoutError::PayloadTooLarge(format!(
            "response exceeds {MAX_FILE_BYTES} bytes; narrow line range"
        )));
    }

    Ok(FileReadResponse {
        rel_path: rel_path.to_string(),
        start_line: start,
        end_line: end,
        text: slice,
        total_lines,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn write_sample(root: &Path) -> std::io::Result<()> {
        let f = root.join("src").join("auth.py");
        std::fs::create_dir_all(f.parent().unwrap())?;
        let mut file = std::fs::File::create(&f)?;
        writeln!(file, "def authenticate(user):")?;
        writeln!(file, "    return user")?;
        writeln!(file, "")?;
        writeln!(file, "def logout():")?;
        writeln!(file, "    pass")?;
        Ok(())
    }

    #[test]
    fn read_full_file() {
        let dir = std::env::temp_dir().join(format!(
            "scout-file-read-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        write_sample(&dir).unwrap();

        let result = read_workspace_file(&dir, "src/auth.py", None, None).unwrap();
        assert!(result.text.contains("authenticate"));
        assert_eq!(result.total_lines, 5);
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn read_line_range() {
        let dir = std::env::temp_dir().join(format!(
            "scout-file-range-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        write_sample(&dir).unwrap();

        let result = read_workspace_file(&dir, "src/auth.py", Some(1), Some(2)).unwrap();
        assert!(result.text.contains("authenticate"));
        assert!(!result.text.contains("logout"));
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn rejects_parent_dir() {
        let dir = std::env::temp_dir().join(format!(
            "scout-file-traversal-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let err = read_workspace_file(&dir, "../etc/passwd", None, None).unwrap_err();
        assert!(matches!(err, ScoutError::InvalidPath(_)));
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn rejects_oversized_without_range() {
        let dir = std::env::temp_dir().join(format!(
            "scout-file-big-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let big = "x".repeat(MAX_FILE_BYTES + 1);
        std::fs::write(dir.join("big.txt"), big).unwrap();

        let err = read_workspace_file(&dir, "big.txt", None, None).unwrap_err();
        assert!(matches!(err, ScoutError::PayloadTooLarge(_)));
        let _ = std::fs::remove_dir_all(dir);
    }
}
