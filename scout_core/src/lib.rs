//! Scout core engine — scan, parse, graph, index, search.
//!
//! Metadata: v0.1.0 | Scout Contributors | 2026-06-12
//! Rationale: Rust owns CPU-bound indexing/search; Python shell calls via pyo3.

pub mod chunk;
pub mod error;
pub mod graph;
pub mod index;
pub mod node_id;
pub mod parse;
pub mod pyapi;
pub mod scan;
pub mod search;
pub mod staleness;
pub mod types;

pub use error::{ScoutError, ScoutResult};

use pyo3::prelude::*;

/// Python module entrypoint for maturin.
#[pymodule]
fn scout_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    pyapi::register(m)
}
