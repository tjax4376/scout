> **See also:** [vector-search](../vector-search/spec.md), [space-config](../space-config/spec.md), [prescan](../prescan/spec.md)

## ADDED Requirements

### Requirement: File scan with skip rules
The system SHALL walk the workspace root recursively and index eligible files. The system SHALL hardcode skip directories: `.git`, `node_modules`, `target`, `dist`, `build`, `__pycache__`, `.venv`, `vendor`, `.scout`, `.cursor`, and common cache directories. The system SHALL skip binary files. The system SHALL support optional per-space `skip.globs` and `skip.paths` in space config. The system SHALL NOT read `.gitignore` in MVP1.

#### Scenario: Standard skip directories excluded
- **WHEN** scan encounters `node_modules/` or `.git/` under workspace root
- **THEN** those directories and their contents are not indexed

#### Scenario: Binary file skipped
- **WHEN** scan encounters a file detected as binary
- **THEN** the file is skipped and not added to the graph or vector store

#### Scenario: Custom skip glob applied
- **WHEN** space config contains `skip.globs: ["*.generated.ts"]`
- **THEN** matching files are excluded from indexing

### Requirement: AST parsing for supported languages
The system SHALL parse TypeScript, JavaScript, Python, Rust, and Go source files using tree-sitter AST parsers. The system SHALL treat config and documentation files as file-only chunks without AST parsing. The system SHALL fall back to a single `file` chunk when AST parsing fails.

#### Scenario: TypeScript symbol extraction
- **WHEN** a `.ts` file is indexed and parses successfully
- **THEN** the system extracts symbols (functions, classes, interfaces, etc.) as separate nodes linked to the file node

#### Scenario: Parse failure fallback
- **WHEN** a supported-language file fails AST parsing
- **THEN** the system creates a single `file` kind node with the full file content as one chunk

#### Scenario: Config file file-only indexing
- **WHEN** a `.yaml` or `.md` file is encountered
- **THEN** the system indexes it as a `file` kind node without AST symbol extraction

### Requirement: Symbol-first chunking
The system SHALL create one chunk per extracted symbol by default. The system SHALL split oversized symbols at approximately 512–1024 tokens with 64-token overlap. The system SHALL store chunk text in sqlite-vec linked to the symbol's `node_id`.

#### Scenario: Function symbol single chunk
- **WHEN** a function symbol fits within the token limit
- **THEN** one chunk is created containing the function source text

#### Scenario: Oversized symbol split
- **WHEN** a symbol exceeds the token limit
- **THEN** the system splits it into multiple chunks with 64-token overlap between adjacent chunks

### Requirement: Petgraph structure graph
The system SHALL build an in-memory directed graph using petgraph. The system SHALL create `contains` edges from directory to file to symbol. The system SHALL create `imports` edges for statically resolvable single unambiguous workspace imports. The system SHALL create `calls` edges for same-file calls and cross-file calls resolvable via import graph and exported names. The system SHALL skip unresolved import and call edges. The system SHALL NOT store body text in the graph — structure only (paths, symbols, edges, line ranges).

#### Scenario: Directory contains file contains symbol
- **WHEN** a file with functions is indexed
- **THEN** the graph has edges: directory →(contains)→ file →(contains)→ function symbols

#### Scenario: Unresolved import skipped
- **WHEN** an import cannot be resolved to a single unambiguous workspace file
- **THEN** no `imports` edge is created for that import

#### Scenario: Same-file call edge
- **WHEN** function A calls function B in the same file
- **THEN** an edge A →(calls)→ B is created in the graph

### Requirement: Deterministic node_id
The system SHALL assign each node a deterministic `node_id` computed as blake3 hash of `space + rel_path + kind + symbol + start_line + end_line`, truncated to 16 hexadecimal characters. The same inputs SHALL always produce the same `node_id`.

#### Scenario: Stable node_id across reindex
- **WHEN** a file is reindexed without changes to path, kind, symbol name, or line range
- **THEN** the resulting `node_id` is identical to the previous index

### Requirement: sqlite-vec storage per space
The system SHALL store chunks in a sqlite-vec database at `.scout/spaces/<space>/index.db`. The `chunks` table SHALL contain text, embedding vector, and `node_id` linking to the petgraph. A `meta` table SHALL store schema version, embed model, and embed dimensions.

#### Scenario: Chunk linked to graph node
- **WHEN** a symbol chunk is stored in sqlite-vec
- **THEN** its `node_id` matches the corresponding petgraph node

### Requirement: Graph cache on disk
The system SHALL serialize the petgraph to `.scout/cache/<space>/graph.bin` after indexing. The system SHALL load graph.bin on subsequent operations to avoid rebuild when only vectors need refresh.

#### Scenario: Graph written after successful index
- **WHEN** indexing completes successfully
- **THEN** `graph.bin` exists at `.scout/cache/<space>/graph.bin`

### Requirement: Manifest staleness tracking
The system SHALL write `manifest.json` per space recording per-file `mtime` and `size` plus embed provider, model, and dimensions. The system SHALL compare manifest against filesystem on search to detect new, deleted, or changed files and embed config mismatches.

#### Scenario: Changed file detected as stale
- **WHEN** a file's mtime or size differs from manifest entry during search
- **THEN** staleness is flagged as true

#### Scenario: Embed config mismatch detected
- **WHEN** current embed provider, model, or dimensions differ from manifest
- **THEN** staleness is flagged as true

### Requirement: Sync full reindex with atomic swap
The system SHALL perform full rebuild on setup and reindex — no incremental updates. The system SHALL write index artifacts to temporary paths and atomically rename on success. The system SHALL abort without partial index on failure. The system SHALL return 409 if reindex is already in progress. The system SHALL NOT use background jobs.

#### Scenario: Successful atomic reindex
- **WHEN** reindex completes without error
- **THEN** temp index files are atomically renamed to production paths and old index is replaced

#### Scenario: Failed reindex leaves no partial index
- **WHEN** reindex fails mid-process
- **THEN** the previous index remains intact and no partial artifacts are exposed

#### Scenario: Concurrent reindex rejected
- **WHEN** a reindex is already in progress and another reindex is requested
- **THEN** the system returns 409 Conflict

### Requirement: Supported node kinds
The system SHALL use node kinds: `directory`, `file`, `module`, `class`, `struct`, `interface`, `enum`, `function`, `method`, `const`. Parse failures SHALL use kind `file`.

#### Scenario: Rust struct kind
- **WHEN** a Rust `struct` is extracted via AST
- **THEN** the node kind is `struct`
