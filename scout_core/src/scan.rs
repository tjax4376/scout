use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

use glob::Pattern;
use walkdir::WalkDir;

use crate::error::{ScoutError, ScoutResult};
use crate::types::ScannedFile;

/// Hardcoded skip directory names per Q34.
const SKIP_DIRS: &[&str] = &[
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "vendor",
    ".scout",
    ".cursor",
    ".cache",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "coverage",
    "htmlcov",
];

/// Scan options from per-space config.
#[derive(Debug, Clone, Default)]
pub struct ScanOptions {
    pub skip_globs: Vec<String>,
    pub skip_paths: Vec<String>,
}

/// Detect language from extension for metrics.
pub fn detect_language(path: &Path) -> Option<String> {
    let ext = path.extension()?.to_str()?;
    Some(
        match ext {
            "ts" | "tsx" => "typescript",
            "js" | "jsx" | "mjs" | "cjs" => "javascript",
            "py" | "pyi" => "python",
            "rs" => "rust",
            "go" => "go",
            "md" | "yaml" | "yml" | "json" | "toml" | "ini" | "cfg" => "config",
            _ => return None,
        }
        .to_string(),
    )
}

/// Config/doc files indexed as file-only (no AST).
pub fn is_config_or_doc(path: &Path) -> bool {
    matches!(
        path.extension().and_then(|e| e.to_str()),
        Some("md" | "yaml" | "yml" | "json" | "toml" | "ini" | "cfg" | "txt" | "rst")
    )
}

fn is_binary_file(path: &Path) -> ScoutResult<bool> {
    let mut file = fs::File::open(path)?;
    let mut buf = [0u8; 8192];
    let n = std::io::Read::read(&mut file, &mut buf)?;
    if n == 0 {
        return Ok(false);
    }
    // NUL byte or high ratio of non-text bytes → binary.
    if buf[..n].contains(&0) {
        return Ok(true);
    }
    let non_text = buf[..n]
        .iter()
        .filter(|&&b| b < 9 || (b > 13 && b < 32))
        .count();
    Ok(non_text * 10 > n)
}

fn path_has_skipped_component(rel: &str, skip_paths: &HashSet<String>) -> bool {
    if skip_paths.contains(rel) {
        return true;
    }
    for part in rel.split('/') {
        if SKIP_DIRS.contains(&part) || skip_paths.contains(part) {
            return true;
        }
    }
    false
}

fn matches_skip_glob(rel_path: &str, patterns: &[Pattern]) -> bool {
    patterns.iter().any(|p| p.matches(rel_path))
}

/// Recursive filesystem walk with skip rules.
pub fn scan_workspace(root: &Path, options: &ScanOptions) -> ScoutResult<Vec<ScannedFile>> {
    let root = root
        .canonicalize()
        .map_err(|e| ScoutError::Config(format!("invalid root path: {e}")))?;
    if !root.is_dir() {
        return Err(ScoutError::Config(format!(
            "root is not a directory: {}",
            root.display()
        )));
    }

    let glob_patterns: Vec<Pattern> = options
        .skip_globs
        .iter()
        .filter_map(|g| Pattern::new(g).ok())
        .collect();
    let skip_paths: HashSet<String> = options.skip_paths.iter().cloned().collect();

    let mut results = Vec::new();

    for entry in WalkDir::new(&root).follow_links(false).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if path == root {
            continue;
        }

        let rel = path
            .strip_prefix(&root)
            .unwrap_or(path)
            .to_string_lossy()
            .replace('\\', "/");

        if path_has_skipped_component(&rel, &skip_paths) {
            continue;
        }

        if matches_skip_glob(&rel, &glob_patterns) {
            continue;
        }

        if entry.file_type().is_dir() {
            continue;
        }

        let meta = fs::metadata(path)?;
        let mtime = meta
            .modified()
            .ok()
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);

        let binary = is_binary_file(path)?;
        if binary {
            continue;
        }

        results.push(ScannedFile {
            rel_path: rel,
            size: meta.len(),
            mtime_secs: mtime,
            language: detect_language(path),
            is_binary: false,
        });
    }

    results.sort_by(|a, b| a.rel_path.cmp(&b.rel_path));
    Ok(results)
}

/// Resolve absolute path from workspace root + relative path.
pub fn resolve_path(root: &Path, rel_path: &str) -> PathBuf {
    root.join(rel_path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!("scout-test-{name}-{nanos}"));
        fs::create_dir_all(&path).unwrap();
        path
    }

    #[test]
    fn skips_node_modules() {
        let dir = temp_dir("scan");
        fs::create_dir_all(dir.join("node_modules/pkg")).unwrap();
        fs::write(dir.join("node_modules/pkg/a.js"), "x").unwrap();
        fs::write(dir.join("main.py"), "print(1)").unwrap();

        let files = scan_workspace(&dir, &ScanOptions::default()).unwrap();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0].rel_path, "main.py");
        let _ = fs::remove_dir_all(dir);
    }
}
