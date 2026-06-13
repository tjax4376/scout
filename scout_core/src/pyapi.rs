use std::path::PathBuf;
use std::sync::Mutex;

use pyo3::exceptions::{PyFileNotFoundError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::graph::{build_graph_and_chunks, load_graph, save_graph};
use crate::index::{insert_chunks, open_index, prepare_index, vector_search};
use crate::scan::{scan_workspace, ScanOptions};
use crate::search::{format_search_response, get_node};
use crate::staleness::{check_staleness, write_manifest};
use crate::types::{
    ChunkData, EmbedManifest, GraphSnapshot, NodeKind, ScannedFile, SearchFilters,
};

static REINDEX_LOCK: Mutex<Option<String>> = Mutex::new(None);

fn to_py_err(err: crate::error::ScoutError) -> PyErr {
    match err {
        crate::error::ScoutError::NotFound(msg) => PyFileNotFoundError::new_err(msg),
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
#[pyo3(signature = (root, skip_globs=None, skip_paths=None))]
fn py_scan_workspace(
    root: String,
    skip_globs: Option<Vec<String>>,
    skip_paths: Option<Vec<String>>,
) -> PyResult<Vec<PyScannedFile>> {
    let opts = ScanOptions {
        skip_globs: skip_globs.unwrap_or_default(),
        skip_paths: skip_paths.unwrap_or_default(),
    };
    let files = scan_workspace(PathBuf::from(root).as_path(), &opts).map_err(to_py_err)?;
    Ok(files.into_iter().map(PyScannedFile::from).collect())
}

#[pyfunction]
#[pyo3(signature = (space, root, files_json, index_version))]
fn py_build_index(
    space: String,
    root: String,
    files_json: String,
    index_version: String,
) -> PyResult<String> {
    let files: Vec<ScannedFile> =
        serde_json::from_str(&files_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let output = build_graph_and_chunks(
        &space,
        PathBuf::from(root).as_path(),
        &files,
        &index_version,
    )
    .map_err(to_py_err)?;
    let snapshot = output.graph.snapshot(&index_version);
    Ok(serde_json::to_string(&(snapshot, output.chunks)).map_err(|e| PyValueError::new_err(e.to_string()))?)
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
#[pyo3(signature = (root, manifest_path, provider, model, dimensions, skip_globs=None, skip_paths=None))]
fn py_check_staleness(
    root: String,
    manifest_path: String,
    provider: String,
    model: String,
    dimensions: u32,
    skip_globs: Option<Vec<String>>,
    skip_paths: Option<Vec<String>>,
) -> PyResult<(bool, String)> {
    let embed = EmbedManifest {
        provider,
        model,
        dimensions,
    };
    let opts = ScanOptions {
        skip_globs: skip_globs.unwrap_or_default(),
        skip_paths: skip_paths.unwrap_or_default(),
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
#[pyo3(signature = (graph_path, db_path, query_embedding, top_k=10, min_score=0.0, kinds=None, path_prefix=None, stale=false, index_version=""))]
fn py_search(
    graph_path: String,
    db_path: String,
    query_embedding: Vec<f32>,
    top_k: usize,
    min_score: f32,
    kinds: Option<Vec<String>>,
    path_prefix: Option<String>,
    stale: bool,
    index_version: String,
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
    let response = format_search_response(&graph, raw, stale, &index_version);
    Ok(serde_json::to_string(&response).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
fn py_get_node(graph_path: String, db_path: String, node_id: String) -> PyResult<String> {
    let graph = load_graph(PathBuf::from(graph_path).as_path()).map_err(to_py_err)?;
    let conn = open_index(PathBuf::from(db_path).as_path()).map_err(to_py_err)?;
    let hit = get_node(&graph, &conn, &node_id).map_err(to_py_err)?;
    Ok(serde_json::to_string(&hit).map_err(|e| PyValueError::new_err(e.to_string()))?)
}

#[pyfunction]
#[pyo3(signature = (manifest_path, files_json, provider, model, dimensions))]
fn py_write_manifest(
    manifest_path: String,
    files_json: String,
    provider: String,
    model: String,
    dimensions: u32,
) -> PyResult<String> {
    let files: Vec<ScannedFile> =
        serde_json::from_str(&files_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let embed = EmbedManifest {
        provider,
        model,
        dimensions,
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
    m.add_function(wrap_pyfunction!(py_build_index, m)?)?;
    m.add_function(wrap_pyfunction!(py_save_graph, m)?)?;
    m.add_function(wrap_pyfunction!(py_load_graph, m)?)?;
    m.add_function(wrap_pyfunction!(py_write_index, m)?)?;
    m.add_function(wrap_pyfunction!(py_check_staleness, m)?)?;
    m.add_function(wrap_pyfunction!(py_search, m)?)?;
    m.add_function(wrap_pyfunction!(py_get_node, m)?)?;
    m.add_function(wrap_pyfunction!(py_write_manifest, m)?)?;
    m.add_function(wrap_pyfunction!(py_acquire_reindex_lock, m)?)?;
    m.add_function(wrap_pyfunction!(py_release_reindex_lock, m)?)?;
    m.add_function(wrap_pyfunction!(py_core_version, m)?)?;
    m.add_class::<PyScannedFile>()?;
    Ok(())
}
