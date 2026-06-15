//! Parallel bulk read of workspace text files for RAM cache warm.

use std::fs;
use std::path::Path;

use rayon::prelude::*;
use serde::Serialize;

use crate::error::{ScoutError, ScoutResult};
use crate::file_read::resolve_under_root;
use crate::scan::{is_binary_file, resolve_path};
use crate::types::ScannedFile;

#[derive(Debug, Clone, Serialize)]
pub struct BulkReadEntry {
    pub rel_path: String,
    pub text: String,
    pub mtime_secs: i64,
}

/// Read many workspace files in parallel; skips binary and unreadable paths.
pub fn bulk_read_workspace_files(
    root: &Path,
    files: &[ScannedFile],
) -> ScoutResult<Vec<BulkReadEntry>> {
    let root = root
        .canonicalize()
        .map_err(|e| ScoutError::Config(format!("invalid root path: {e}")))?;

    for file in files {
        resolve_under_root(&root, &file.rel_path)?;
    }

    let entries: Vec<BulkReadEntry> = files
        .par_iter()
        .map(|file| read_one(&root, file))
        .collect::<ScoutResult<Vec<_>>>()?;

    let mut sorted = entries;
    sorted.sort_by(|a, b| a.rel_path.cmp(&b.rel_path));
    Ok(sorted)
}

fn read_one(root: &Path, file: &ScannedFile) -> ScoutResult<BulkReadEntry> {
    resolve_under_root(root, &file.rel_path)?;
    let path = resolve_path(root, &file.rel_path);
    if !path.is_file() {
        return Err(ScoutError::NotFound(file.rel_path.clone()));
    }
    if is_binary_file(&path)? {
        return Err(ScoutError::Index(format!(
            "binary file skipped: {}",
            file.rel_path
        )));
    }
    let text = fs::read_to_string(&path)?;
    Ok(BulkReadEntry {
        rel_path: file.rel_path.clone(),
        text,
        mtime_secs: file.mtime_secs,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scan::scan_workspace;
    use crate::types::ScannedFile;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!("scout-bulk-{name}-{nanos}"));
        fs::create_dir_all(&path).unwrap();
        path
    }

    #[test]
    fn bulk_read_utf8_files() {
        let dir = temp_dir("bulk");
        fs::write(dir.join("a.py"), "print('α')").unwrap();
        fs::write(dir.join("b.py"), "pass").unwrap();
        let files = scan_workspace(&dir, &crate::scan::ScanOptions::default()).unwrap();
        let entries = bulk_read_workspace_files(&dir, &files).unwrap();
        assert_eq!(entries.len(), 2);
        assert!(entries.iter().any(|e| e.rel_path == "a.py" && e.text.contains('α')));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn bulk_read_rejects_traversal() {
        let dir = temp_dir("bulk-bad");
        let files = vec![ScannedFile {
            rel_path: "../etc/passwd".into(),
            size: 0,
            mtime_secs: 0,
            language: None,
            is_binary: false,
        }];
        let err = bulk_read_workspace_files(&dir, &files).unwrap_err();
        assert!(matches!(err, ScoutError::InvalidPath(_)));
        let _ = fs::remove_dir_all(dir);
    }
}
