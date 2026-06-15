use thiserror::Error;

#[derive(Debug, Error)]
pub enum ScoutError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("SQLite error: {0}")]
    Sqlite(#[from] rusqlite::Error),
    #[error("Parse error: {0}")]
    Parse(String),
    #[error("Config error: {0}")]
    Config(String),
    #[error("Index error: {0}")]
    Index(String),
    #[error("Reindex in progress")]
    ReindexInProgress,
    #[error("Not found: {0}")]
    NotFound(String),
    #[error("Payload too large: {0}")]
    PayloadTooLarge(String),
    #[error("Invalid path: {0}")]
    InvalidPath(String),
    #[error("{0}")]
    Other(String),
}

pub type ScoutResult<T> = Result<T, ScoutError>;
