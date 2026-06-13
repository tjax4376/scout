mod go;
mod javascript;
mod python;
mod rust_lang;
mod typescript;

use std::path::Path;

use tree_sitter::{Language, Parser, Query, QueryCursor, Tree};

use crate::error::{ScoutError, ScoutResult};
use crate::scan::is_config_or_doc;
use crate::types::{NodeKind, SymbolInfo};

pub use go::language as go_language;
pub use javascript::language as javascript_language;
pub use python::language as python_language;
pub use rust_lang::language as rust_language;
pub use typescript::language as typescript_language;

/// Supported AST languages for MVP1.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SourceLanguage {
    TypeScript,
    JavaScript,
    Python,
    Rust,
    Go,
}

impl SourceLanguage {
    pub fn from_path(path: &Path) -> Option<Self> {
        let ext = path.extension()?.to_str()?;
        match ext {
            "ts" | "tsx" => Some(Self::TypeScript),
            "js" | "jsx" | "mjs" | "cjs" => Some(Self::JavaScript),
            "py" | "pyi" => Some(Self::Python),
            "rs" => Some(Self::Rust),
            "go" => Some(Self::Go),
            _ => None,
        }
    }

    fn tree_sitter_language(self) -> Language {
        match self {
            Self::TypeScript => typescript_language(),
            Self::JavaScript => javascript_language(),
            Self::Python => python_language(),
            Self::Rust => rust_language(),
            Self::Go => go_language(),
        }
    }

    fn symbol_query(self) -> &'static str {
        match self {
            Self::TypeScript | Self::JavaScript => {
                r#"
                (function_declaration name: (identifier) @name) @def
                (method_definition name: (property_identifier) @name) @def
                (class_declaration name: (type_identifier) @name) @def
                (interface_declaration name: (type_identifier) @name) @def
                (enum_declaration name: (identifier) @name) @def
                (lexical_declaration (variable_declarator name: (identifier) @name) @name) @def
                "#
            }
            Self::Python => {
                r#"
                (function_definition name: (identifier) @name) @def
                (class_definition name: (identifier) @name) @def
                "#
            }
            Self::Rust => {
                r#"
                (function_item name: (identifier) @name) @def
                (struct_item name: (type_identifier) @name) @def
                (enum_item name: (type_identifier) @name) @def
                (trait_item name: (type_identifier) @name) @def
                (impl_item type: (type_identifier) @name) @def
                (const_item name: (identifier) @name) @def
                "#
            }
            Self::Go => {
                r#"
                (function_declaration name: (identifier) @name) @def
                (method_declaration name: (field_identifier) @name) @def
                (type_declaration (type_spec name: (type_identifier) @name)) @def
                "#
            }
        }
    }
}

fn kind_for_capture(lang: SourceLanguage, node_kind: &str) -> NodeKind {
    match lang {
        SourceLanguage::TypeScript | SourceLanguage::JavaScript => match node_kind {
            "function_declaration" => NodeKind::Function,
            "method_definition" => NodeKind::Method,
            "class_declaration" => NodeKind::Class,
            "interface_declaration" => NodeKind::Interface,
            "enum_declaration" => NodeKind::Enum,
            _ => NodeKind::Const,
        },
        SourceLanguage::Python => match node_kind {
            "function_definition" => NodeKind::Function,
            "class_definition" => NodeKind::Class,
            _ => NodeKind::Const,
        },
        SourceLanguage::Rust => match node_kind {
            "function_item" => NodeKind::Function,
            "struct_item" => NodeKind::Struct,
            "enum_item" => NodeKind::Enum,
            "trait_item" => NodeKind::Interface,
            "impl_item" => NodeKind::Module,
            "const_item" => NodeKind::Const,
            _ => NodeKind::Function,
        },
        SourceLanguage::Go => match node_kind {
            "function_declaration" => NodeKind::Function,
            "method_declaration" => NodeKind::Method,
            "type_declaration" => NodeKind::Struct,
            _ => NodeKind::Function,
        },
    }
}

/// Parse file and extract symbols; file fallback on failure or non-AST file.
pub fn extract_symbols(path: &Path, source: &str) -> ScoutResult<Vec<SymbolInfo>> {
    if is_config_or_doc(path) {
        return Ok(vec![]);
    }

    let lang = match SourceLanguage::from_path(path) {
        Some(l) => l,
        None => return Ok(vec![]),
    };

    let mut parser = Parser::new();
    parser
        .set_language(&lang.tree_sitter_language())
        .map_err(|e| ScoutError::Parse(e.to_string()))?;

    let tree = match parser.parse(source, None) {
        Some(t) => t,
        None => return Ok(vec![]),
    };

    extract_from_tree(lang, source, &tree)
}

fn extract_from_tree(lang: SourceLanguage, source: &str, tree: &Tree) -> ScoutResult<Vec<SymbolInfo>> {
    let query_src = lang.symbol_query();
    let query = Query::new(&lang.tree_sitter_language(), query_src)
        .map_err(|e| ScoutError::Parse(e.to_string()))?;

    let mut cursor = QueryCursor::new();
    let mut symbols = Vec::new();
    let root = tree.root_node();

    let matches = cursor.matches(&query, root, source.as_bytes());
    for m in matches {
        let mut name = String::new();
        let mut def_node = None;
        for capture in m.captures {
            let cap_name = query.capture_names()[capture.index as usize];
            let node = capture.node;
            if cap_name == "name" {
                name = node.utf8_text(source.as_bytes()).unwrap_or("").to_string();
            } else if cap_name == "def" {
                def_node = Some(node);
            }
        }
        if let Some(node) = def_node {
            if name.is_empty() {
                continue;
            }
            let start = node.start_position();
            let end = node.end_position();
            let kind = kind_for_capture(lang, node.kind());
            symbols.push(SymbolInfo {
                kind,
                name,
                start_line: start.row as u32 + 1,
                end_line: end.row as u32 + 1,
                start_byte: node.start_byte(),
                end_byte: node.end_byte(),
            });
        }
    }

    Ok(symbols)
}

/// File-level fallback symbol spanning entire file.
pub fn file_fallback_symbol(source: &str) -> SymbolInfo {
    let line_count = source.lines().count().max(1) as u32;
    SymbolInfo {
        kind: NodeKind::File,
        name: String::new(),
        start_line: 1,
        end_line: line_count,
        start_byte: 0,
        end_byte: source.len(),
    }
}
