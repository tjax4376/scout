use std::path::PathBuf;
use std::sync::Mutex;

use pyo3::exceptions::{PyFileNotFoundError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::bulk_read::bulk_read_workspace_files;
use crate::file_read::read_workspace_file;
use crate::graph::{build_graph, load_graph, save_graph};
use crate::index::{
    index_exists, insert_chunks, open_index, prepare_index, session_index_stats, vector_search,
};
use crate::scan::{scan_workspace, ScanOptions};
use crate::search::{expand_neighbors, format_search_response, get_node, get_node_from_graph, list_symbols};
use crate::staleness::{check_staleness, write_graph_manifest, write_manifest};
use crate::types::{
    ChunkData, EmbedManifest, GraphSnapshot, NodeKind, ScannedFile, SearchFilters,
};

static REINDEX_LOCK: Mutex<Option<String>> = Mutex::new(None);

fn to_py_err(err: crate::error::ScoutError) -> PyErr {
    match err {
        crate::error::ScoutError::NotFound(msg) => PyFileNotFoundError::new_err(msg),
        crate::error::ScoutError::PayloadTooLarge(msg) => PyValueError::new_err(msg),
        crate::error::ScoutError::InvalidPath(msg) => PyValueError::new_err(msg),
        crate::error::ScoutError::ReindexInProgress => {
            PyRuntimeError::new_err("reindex in progress")
        }
        other => PyRuntimeError::new_err(other.to_string()),
    }
}

#[pyclass]
#[derive(Clone)]
struct PyScannedFile {
    #[pyo3(get)]
    rel_path: String,
    #[pyo3(get)]
    size: u64,
    #[pyo3(get)]
    mtime_secs: i64,
    #[pyo3(get)]
    language: Option<String>,
}

impl From<ScannedFile> for PyScannedFile {
    fn from(f: ScannedFile) -> Self {
        Self {
            rel_path: f.rel_path,
            size: f.size,
            mtime_secs: f.mtime_secs,
            language: f.language,
        }
    }
}

#[pyfunction]
#[pyo3(signature = (root, skip_globs=None, skip_paths=None, respect_gitignore=None))]
fn py_scan_workspace(
    root: String,
    skip_globs: Option<Vec<String>>,
    skip_paths: Option<Vec<String>>,
    respect_gitignore: Option<bool>,
) -> PyResult<Vec<PyScannedFile>> {
    let opts = ScanOptions {
        skip_globs: skip_globs.unwrap_or_default(),
        skip_paths: skip_paths.unwrap_or_default(),
        respect_gitignore: respect_gitignore.unwrap_or(true),
    };
    let files = scan_workspace(PathBuf::from(root).as_path(), &opts).map_err(to_py_err)?;
    Ok(files.into_iter().map(PyScannedFile::from).collect())
}

#[pyfunction]
#[pyo3(signature = (space, root, files_json, index_version))]
fn py_build_graph(
    space: String,
    root: String,
    files_json: String,
    index_version: String,
) -> PyResult<String> {
    let files: Vec<ScannedFile> =
        serde_json::from_str(&files_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let graph = build_graph(
        &space,
        PathBuf::from(root).as_path(),
        &files,
        &index_version,
    )
    .map_err(to_py_err)?;
    let snapshot = graph.snapshot(&index_version);
    Ok(serde_json::to_string(&snapshot).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
#[pyo3(signature = (space, root, files_json, index_version))]
fn py_build_index(
    space: String,
    root: String,
    files_json: String,
    index_version: String,
) -> PyResult<String> {
    py_build_graph(space, root, files_json, index_version)
}

#[pyfunction]
fn py_save_graph(path: String, snapshot_json: String) -> PyResult<()> {
    let snapshot: GraphSnapshot =
        serde_json::from_str(&snapshot_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    save_graph(PathBuf::from(path).as_path(), &snapshot).map_err(to_py_err)
}

#[pyfunction]
fn py_load_graph(path: String) -> PyResult<String> {
    let graph = load_graph(PathBuf::from(path).as_path()).map_err(to_py_err)?;
    let snapshot = graph.snapshot("");
    Ok(serde_json::to_string(&snapshot).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
#[pyo3(signature = (db_path, model, dimensions, chunks_json, embeddings_json))]
fn py_write_index(
    db_path: String,
    model: String,
    dimensions: u32,
    chunks_json: String,
    embeddings_json: String,
) -> PyResult<()> {
    let chunks: Vec<ChunkData> =
        serde_json::from_str(&chunks_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let embeddings: Vec<Vec<f32>> =
        serde_json::from_str(&embeddings_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let conn = open_index(PathBuf::from(db_path).as_path()).map_err(to_py_err)?;
    prepare_index(&conn, &model, dimensions).map_err(to_py_err)?;
    insert_chunks(&conn, &chunks, &embeddings).map_err(to_py_err)?;
    Ok(())
}

#[pyfunction]
fn py_index_exists(db_path: String) -> PyResult<bool> {
    Ok(index_exists(PathBuf::from(db_path).as_path()))
}

#[pyfunction]
#[pyo3(signature = (db_path, model, dimensions))]
fn py_session_prepare_index(db_path: String, model: String, dimensions: u32) -> PyResult<()> {
    let conn = open_index(PathBuf::from(db_path).as_path()).map_err(to_py_err)?;
    prepare_index(&conn, &model, dimensions).map_err(to_py_err)?;
    Ok(())
}

#[pyfunction]
#[pyo3(signature = (db_path, chunks_json, embeddings_json))]
fn py_session_append_chunks(
    db_path: String,
    chunks_json: String,
    embeddings_json: String,
) -> PyResult<()> {
    let chunks: Vec<ChunkData> =
        serde_json::from_str(&chunks_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let embeddings: Vec<Vec<f32>> =
        serde_json::from_str(&embeddings_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let conn = open_index(PathBuf::from(db_path).as_path()).map_err(to_py_err)?;
    insert_chunks(&conn, &chunks, &embeddings).map_err(to_py_err)?;
    Ok(())
}

#[pyfunction]
fn py_session_index_stats(db_path: String) -> PyResult<(usize, usize)> {
    let conn = open_index(PathBuf::from(db_path).as_path()).map_err(to_py_err)?;
    session_index_stats(&conn).map_err(to_py_err)
}

#[pyfunction]
#[pyo3(signature = (root, manifest_path, provider=None, model=None, dimensions=None, skip_globs=None, skip_paths=None, respect_gitignore=None))]
fn py_check_staleness(
    root: String,
    manifest_path: String,
    provider: Option<String>,
    model: Option<String>,
    dimensions: Option<u32>,
    skip_globs: Option<Vec<String>>,
    skip_paths: Option<Vec<String>>,
    respect_gitignore: Option<bool>,
) -> PyResult<(bool, String)> {
    let embed = EmbedManifest {
        provider: provider.unwrap_or_default(),
        model: model.unwrap_or_default(),
        dimensions: dimensions.unwrap_or(0),
    };
    let opts = ScanOptions {
        skip_globs: skip_globs.unwrap_or_default(),
        skip_paths: skip_paths.unwrap_or_default(),
        respect_gitignore: respect_gitignore.unwrap_or(true),
    };
    check_staleness(
        PathBuf::from(root).as_path(),
        PathBuf::from(manifest_path).as_path(),
        &embed,
        &opts,
    )
    .map_err(to_py_err)
}

#[pyfunction]
#[pyo3(signature = (graph_path, db_path, query_embedding, top_k=10, min_score=0.0, kinds=None, path_prefix=None, stale=false, index_version=None))]
fn py_search(
    graph_path: String,
    db_path: String,
    query_embedding: Vec<f32>,
    top_k: usize,
    min_score: f32,
    kinds: Option<Vec<String>>,
    path_prefix: Option<String>,
    stale: bool,
    index_version: Option<String>,
) -> PyResult<String> {
    let graph = load_graph(PathBuf::from(graph_path).as_path()).map_err(to_py_err)?;
    let conn = open_index(PathBuf::from(db_path).as_path()).map_err(to_py_err)?;
    let kind_filters: Vec<NodeKind> = kinds
        .unwrap_or_default()
        .iter()
        .filter_map(|k| NodeKind::parse(k))
        .collect();
    let filters = SearchFilters {
        top_k,
        min_score,
        kinds: kind_filters,
        path_prefix,
    };
    let raw = vector_search(
        &conn,
        &query_embedding,
        filters.top_k,
        filters.min_score,
        &filters.kinds,
        filters.path_prefix.as_deref(),
    )
    .map_err(to_py_err)?;
    let version = index_version.unwrap_or_default();
    let response = format_search_response(&graph, raw, stale, &version);
    Ok(serde_json::to_string(&response).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
#[pyo3(signature = (graph_path, db_path, node_id))]
fn py_get_node(graph_path: String, db_path: String, node_id: String) -> PyResult<String> {
    let graph = load_graph(PathBuf::from(graph_path).as_path()).map_err(to_py_err)?;
    let db = PathBuf::from(db_path);
    let hit = if index_exists(db.as_path()) {
        let conn = open_index(db.as_path()).map_err(to_py_err)?;
        get_node(&graph, &conn, &node_id).map_err(to_py_err)?
    } else {
        get_node_from_graph(&graph, &node_id).map_err(to_py_err)?
    };
    Ok(serde_json::to_string(&hit).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
#[pyo3(signature = (graph_path, path_prefix, kinds=None))]
fn py_list_symbols(
    graph_path: String,
    path_prefix: String,
    kinds: Option<Vec<String>>,
) -> PyResult<String> {
    let graph = load_graph(PathBuf::from(graph_path).as_path()).map_err(to_py_err)?;
    let kind_filters: Vec<NodeKind> = kinds
        .unwrap_or_default()
        .iter()
        .filter_map(|k| NodeKind::parse(k))
        .collect();
    let response = list_symbols(&graph, &path_prefix, &kind_filters);
    Ok(serde_json::to_string(&response).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
#[pyo3(signature = (graph_path, node_id, depth=3, max_nodes=50))]
fn py_expand_neighbors(
    graph_path: String,
    node_id: String,
    depth: u8,
    max_nodes: usize,
) -> PyResult<String> {
    let graph = load_graph(PathBuf::from(graph_path).as_path()).map_err(to_py_err)?;
    let neighbors = expand_neighbors(&graph, &node_id, depth, max_nodes).map_err(to_py_err)?;
    let payload = serde_json::json!({
        "node_id": node_id,
        "neighbors": neighbors,
    });
    Ok(serde_json::to_string(&payload).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
#[pyo3(signature = (root, rel_path, start_line=None, end_line=None))]
fn py_read_workspace_file(
    root: String,
    rel_path: String,
    start_line: Option<u32>,
    end_line: Option<u32>,
) -> PyResult<String> {
    let result =
        read_workspace_file(PathBuf::from(root).as_path(), &rel_path, start_line, end_line)
            .map_err(to_py_err)?;
    Ok(serde_json::to_string(&result).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
#[pyo3(signature = (root, files_json))]
fn py_bulk_read_workspace_files(root: String, files_json: String) -> PyResult<String> {
    let files: Vec<ScannedFile> =
        serde_json::from_str(&files_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let entries =
        bulk_read_workspace_files(PathBuf::from(root).as_path(), &files).map_err(to_py_err)?;
    serde_json::to_string(&entries).map_err(|e| PyValueError::new_err(e.to_string()))
}

#[pyfunction]
fn py_write_graph_manifest(manifest_path: String, files_json: String) -> PyResult<String> {
    let files: Vec<ScannedFile> =
        serde_json::from_str(&files_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let manifest =
        write_graph_manifest(PathBuf::from(manifest_path).as_path(), &files).map_err(to_py_err)?;
    Ok(manifest.index_version)
}

#[pyfunction]
#[pyo3(signature = (manifest_path, files_json, provider=None, model=None, dimensions=None))]
fn py_write_manifest(
    manifest_path: String,
    files_json: String,
    provider: Option<String>,
    model: Option<String>,
    dimensions: Option<u32>,
) -> PyResult<String> {
    let files: Vec<ScannedFile> =
        serde_json::from_str(&files_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let provider = provider.unwrap_or_default();
    if provider.is_empty() {
        let manifest = write_graph_manifest(PathBuf::from(manifest_path).as_path(), &files)
            .map_err(to_py_err)?;
        return Ok(manifest.index_version);
    }
    let embed = EmbedManifest {
        provider,
        model: model.unwrap_or_default(),
        dimensions: dimensions.unwrap_or(0),
    };
    let manifest =
        write_manifest(PathBuf::from(manifest_path).as_path(), &files, &embed).map_err(to_py_err)?;
    Ok(manifest.index_version)
}

#[pyfunction]
fn py_acquire_reindex_lock(space: String) -> PyResult<bool> {
    let mut guard = REINDEX_LOCK.lock().unwrap();
    if guard.is_some() {
        return Ok(false);
    }
    *guard = Some(space);
    Ok(true)
}

#[pyfunction]
fn py_release_reindex_lock() -> PyResult<()> {
    let mut guard = REINDEX_LOCK.lock().unwrap();
    *guard = None;
    Ok(())
}

#[pyfunction]
fn py_core_version() -> PyResult<&'static str> {
    Ok(env!("CARGO_PKG_VERSION"))
}

/// Register Python bindings on the module.
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_scan_workspace, m)?)?;
    m.add_function(wrap_pyfunction!(py_build_graph, m)?)?;
    m.add_function(wrap_pyfunction!(py_build_index, m)?)?;
    m.add_function(wrap_pyfunction!(py_save_graph, m)?)?;
    m.add_function(wrap_pyfunction!(py_load_graph, m)?)?;
    m.add_function(wrap_pyfunction!(py_write_index, m)?)?;
    m.add_function(wrap_pyfunction!(py_index_exists, m)?)?;
    m.add_function(wrap_pyfunction!(py_session_prepare_index, m)?)?;
    m.add_function(wrap_pyfunction!(py_session_append_chunks, m)?)?;
    m.add_function(wrap_pyfunction!(py_session_index_stats, m)?)?;
    m.add_function(wrap_pyfunction!(py_check_staleness, m)?)?;
    m.add_function(wrap_pyfunction!(py_search, m)?)?;
    m.add_function(wrap_pyfunction!(py_get_node, m)?)?;
    m.add_function(wrap_pyfunction!(py_list_symbols, m)?)?;
    m.add_function(wrap_pyfunction!(py_expand_neighbors, m)?)?;
    m.add_function(wrap_pyfunction!(py_read_workspace_file, m)?)?;
    m.add_function(wrap_pyfunction!(py_bulk_read_workspace_files, m)?)?;
    m.add_function(wrap_pyfunction!(py_write_graph_manifest, m)?)?;
    m.add_function(wrap_pyfunction!(py_write_manifest, m)?)?;
    m.add_function(wrap_pyfunction!(py_acquire_reindex_lock, m)?)?;
    m.add_function(wrap_pyfunction!(py_release_reindex_lock, m)?)?;
    m.add_function(wrap_pyfunction!(py_core_version, m)?)?;
    m.add_class::<PyScannedFile>()?;
    Ok(())
}
