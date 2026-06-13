use std::collections::HashSet;
use std::path::Path;

use rusqlite::auto_extension::{register_auto_extension, RawAutoExtension};
use rusqlite::{params, Connection};
use sqlite_vec::sqlite3_vec_init;
use zerocopy::IntoBytes;

use crate::error::{ScoutError, ScoutResult};
use crate::types::{ChunkData, NodeKind};

const SCHEMA_VERSION: &str = "1";

/// vec0 TEXT metadata columns reject NULL — use empty string.
fn symbol_for_db(symbol: Option<&str>) -> &str {
    symbol.filter(|s| !s.is_empty()).unwrap_or("")
}

/// Register sqlite-vec extension with bundled SQLite.
fn register_vec_extension() -> ScoutResult<()> {
    unsafe {
        let raw_ext: RawAutoExtension =
            std::mem::transmute(sqlite3_vec_init as *const () as usize);
        register_auto_extension(raw_ext)
            .map_err(|e| ScoutError::Index(e.to_string()))?;
    }
    Ok(())
}

/// Open or create per-space sqlite-vec database.
pub fn open_index(path: &Path) -> ScoutResult<Connection> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    register_vec_extension()?;
    let conn = Connection::open(path)?;
    init_schema(&conn, 0)?;
    Ok(conn)
}

fn init_schema(conn: &Connection, dimensions: u32) -> ScoutResult<()> {
    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        "#,
    )?;
    if dimensions > 0 {
        let ddl = format!(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING vec0(
                node_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                rel_path TEXT NOT NULL,
                symbol TEXT,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding FLOAT[{dimensions}]
            );"
        );
        conn.execute(&ddl, [])?;
    }
    Ok(())
}

/// Write meta and (re)create chunks table for given dimensions.
pub fn prepare_index(conn: &Connection, model: &str, dimensions: u32) -> ScoutResult<()> {
    conn.execute_batch("DROP TABLE IF EXISTS chunks;")?;
    init_schema(conn, dimensions)?;
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?1)",
        params![SCHEMA_VERSION],
    )?;
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('model', ?1)",
        params![model],
    )?;
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('dimensions', ?1)",
        params![dimensions.to_string()],
    )?;
    Ok(())
}

/// Batch insert chunks with pre-computed embeddings from Python.
pub fn insert_chunks(
    conn: &Connection,
    chunks: &[ChunkData],
    embeddings: &[Vec<f32>],
) -> ScoutResult<()> {
    if chunks.len() != embeddings.len() {
        return Err(ScoutError::Index(
            "chunks and embeddings length mismatch".into(),
        ));
    }
    // vec0 rejects duplicate primary keys; query can emit duplicate symbols per file.
    let mut seen: HashSet<String> = HashSet::new();
    let mut deduped_chunks: Vec<&ChunkData> = Vec::new();
    let mut deduped_emb: Vec<&Vec<f32>> = Vec::new();
    for (chunk, emb) in chunks.iter().zip(embeddings.iter()) {
        if seen.insert(chunk.node_id.clone()) {
            deduped_chunks.push(chunk);
            deduped_emb.push(emb);
        }
    }
    let tx = conn.unchecked_transaction()?;
    for (chunk, emb) in deduped_chunks.iter().zip(deduped_emb.iter()) {
        tx.execute(
            "INSERT OR REPLACE INTO chunks
             (node_id, kind, rel_path, symbol, start_line, end_line, text, embedding)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                chunk.node_id,
                chunk.kind.as_str(),
                chunk.rel_path,
                symbol_for_db(chunk.symbol.as_deref()),
                chunk.start_line,
                chunk.end_line,
                chunk.text,
                emb.as_bytes(),
            ],
        )?;
    }
    tx.commit()?;
    Ok(())
}

#[derive(Debug, Clone)]
pub struct RawSearchHit {
    pub node_id: String,
    pub kind: String,
    pub rel_path: String,
    pub symbol: Option<String>,
    pub start_line: u32,
    pub end_line: u32,
    pub text: String,
    pub score: f32,
}

/// Vector similarity search with optional filters.
pub fn vector_search(
    conn: &Connection,
    query_embedding: &[f32],
    top_k: usize,
    min_score: f32,
    kinds: &[NodeKind],
    path_prefix: Option<&str>,
) -> ScoutResult<Vec<RawSearchHit>> {
    let dims: u32 = conn
        .query_row(
            "SELECT value FROM meta WHERE key = 'dimensions'",
            [],
            |r| r.get::<_, String>(0),
        )
        .map_err(|_| ScoutError::Index("missing dimensions meta".into()))?
        .parse()
        .map_err(|_| ScoutError::Index("invalid dimensions meta".into()))?;

    let sql = format!(
        "SELECT node_id, kind, rel_path, symbol, start_line, end_line, text,
                vec_distance_cosine(embedding, ?1) AS dist
         FROM chunks
         ORDER BY dist ASC
         LIMIT ?2"
    );

    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map(params![query_embedding.as_bytes(), top_k.max(1)], |row| {
        let dist: f64 = row.get(7)?;
        Ok(RawSearchHit {
            node_id: row.get(0)?,
            kind: row.get(1)?,
            rel_path: row.get(2)?,
            symbol: row.get(3)?,
            start_line: row.get(4)?,
            end_line: row.get(5)?,
            text: row.get(6)?,
            score: (1.0 - dist as f32).max(0.0),
        })
    })?;

    let mut hits = Vec::new();
    for row in rows {
        let hit = row?;
        if hit.score < min_score {
            continue;
        }
        if !kinds.is_empty() {
            let kind = NodeKind::parse(&hit.kind);
            if kind.map(|k| !kinds.contains(&k)).unwrap_or(true) {
                continue;
            }
        }
        if let Some(prefix) = path_prefix {
            if !hit.rel_path.starts_with(prefix) {
                continue;
            }
        }
        hits.push(hit);
        if hits.len() >= top_k {
            break;
        }
    }
    let _ = dims;
    Ok(hits)
}

/// Full chunk retrieval by node_id.
pub fn get_chunk(conn: &Connection, node_id: &str) -> ScoutResult<RawSearchHit> {
    conn.query_row(
        "SELECT node_id, kind, rel_path, symbol, start_line, end_line, text
         FROM chunks WHERE node_id = ?1",
        params![node_id],
        |row| {
            Ok(RawSearchHit {
                node_id: row.get(0)?,
                kind: row.get(1)?,
                rel_path: row.get(2)?,
                symbol: row.get(3)?,
                start_line: row.get(4)?,
                end_line: row.get(5)?,
                text: row.get(6)?,
                score: 0.0,
            })
        },
    )
    .map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => {
            ScoutError::NotFound(format!("node {node_id}"))
        }
        other => ScoutError::Sqlite(other),
    })
}

pub fn read_meta(conn: &Connection, key: &str) -> ScoutResult<Option<String>> {
    let result = conn.query_row(
        "SELECT value FROM meta WHERE key = ?1",
        params![key],
        |r| r.get(0),
    );
    match result {
        Ok(v) => Ok(Some(v)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(ScoutError::Sqlite(e)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{ChunkData, NodeKind};

    #[test]
    fn insert_chunk_with_null_symbol() {
        let dir = std::env::temp_dir().join(format!(
            "scout-index-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let db = dir.join("test.db");
        let conn = open_index(&db).unwrap();
        prepare_index(&conn, "test-model", 4).unwrap();
        let chunk = ChunkData {
            node_id: "abc123".into(),
            text: "file content".into(),
            kind: NodeKind::File,
            rel_path: "readme.md".into(),
            symbol: None,
            start_line: 1,
            end_line: 10,
        };
        let chunk_dup = ChunkData {
            text: "duplicate".into(),
            ..chunk.clone()
        };
        insert_chunks(
            &conn,
            &[chunk, chunk_dup],
            &[vec![0.1, 0.2, 0.3, 0.4], vec![0.9, 0.8, 0.7, 0.6]],
        )
        .unwrap();
        let _ = std::fs::remove_dir_all(dir);
    }
}
