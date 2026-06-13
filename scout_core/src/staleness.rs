use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use crate::error::{ScoutError, ScoutResult};
use crate::scan::{scan_workspace, ScanOptions};
use crate::types::{EmbedManifest, Manifest, ManifestFileEntry, ScannedFile};

/// Generate index version identifier from embed config + timestamp bucket.
pub fn generate_index_version(embed: &EmbedManifest) -> String {
    let raw = format!(
        "{}:{}:{}",
        embed.provider, embed.model, embed.dimensions
    );
    blake3::hash(raw.as_bytes()).to_hex()[..12].to_string()
}

/// Write manifest after successful index.
pub fn write_manifest(path: &Path, files: &[ScannedFile], embed: &EmbedManifest) -> ScoutResult<Manifest> {
    let mut map = BTreeMap::new();
    for f in files {
        map.insert(
            f.rel_path.clone(),
            ManifestFileEntry {
                mtime_secs: f.mtime_secs,
                size: f.size,
            },
        );
    }
    let manifest = Manifest {
        files: map,
        embed: embed.clone(),
        index_version: generate_index_version(embed),
    };
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let json = serde_json::to_string_pretty(&manifest)?;
    fs::write(path, json)?;
    Ok(manifest)
}

/// Load manifest from disk.
pub fn load_manifest(path: &Path) -> ScoutResult<Manifest> {
    let data = fs::read_to_string(path)?;
    Ok(serde_json::from_str(&data)?)
}

/// Check staleness: filesystem diff + embed config mismatch.
pub fn check_staleness(
    root: &Path,
    manifest_path: &Path,
    current_embed: &EmbedManifest,
    scan_options: &ScanOptions,
) -> ScoutResult<(bool, String)> {
    let manifest = match load_manifest(manifest_path) {
        Ok(m) => m,
        Err(_) => return Ok((true, String::new())),
    };

    if manifest.embed != *current_embed {
        return Ok((true, manifest.index_version));
    }

    let current_files = scan_workspace(root, scan_options)?;
    if current_files.len() != manifest.files.len() {
        return Ok((true, manifest.index_version));
    }

    for f in &current_files {
        match manifest.files.get(&f.rel_path) {
            Some(entry) if entry.mtime_secs == f.mtime_secs && entry.size == f.size => {}
            _ => return Ok((true, manifest.index_version)),
        }
    }

    Ok((false, manifest.index_version))
}

/// Atomic write: write to temp path then rename.
pub fn atomic_write(path: &Path, data: &[u8]) -> ScoutResult<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("tmp");
    fs::write(&tmp, data)?;
    fs::rename(&tmp, path)?;
    Ok(())
}

/// Atomic replace directory contents by renaming temp dir.
pub fn atomic_replace_dir(target: &Path, build: impl FnOnce(&Path) -> ScoutResult<()>) -> ScoutResult<()> {
    let parent = target
        .parent()
        .ok_or_else(|| ScoutError::Config("no parent dir".into()))?;
    let tmp = parent.join(format!(
        ".{}_tmp",
        target.file_name().unwrap_or_default().to_string_lossy()
    ));
    if tmp.exists() {
        fs::remove_dir_all(&tmp)?;
    }
    fs::create_dir_all(&tmp)?;
    build(&tmp)?;
    if target.exists() {
        if target.is_dir() {
            fs::remove_dir_all(target)?;
        } else {
            fs::remove_file(target)?;
        }
    }
    fs::rename(&tmp, target)?;
    Ok(())
}
