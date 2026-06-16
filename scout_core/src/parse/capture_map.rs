//! Tree-sitter capture name → Scout [`NodeKind`] lookup tables.
//!
//! Built-in mappings use compile-time [`phf`] perfect-hash maps (no runtime allocation
//! on the hot parse path). Unmapped `(language, node_kind)` pairs fall back to a
//! per-language default:
//!
//! | Language   | Default fallback   |
//! |------------|--------------------|
//! | TypeScript | [`NodeKind::Const`] |
//! | JavaScript | [`NodeKind::Const`] |
//! | Python     | [`NodeKind::Const`] |
//! | Rust       | [`NodeKind::Function`] |
//! | Go         | [`NodeKind::Function`] |
//!
//! External crates may register additional mappings via [`register_language_capture_map`];
//! extensions are consulted before the built-in tables.

use std::sync::{OnceLock, RwLock};

use phf::{phf_map, Map};

use super::SourceLanguage;
use crate::types::NodeKind;

/// Fallback when a language has no explicit default entry (should not occur for built-ins).
const GLOBAL_DEFAULT_KIND: NodeKind = NodeKind::Function;

static TYPESCRIPT_CAPTURES: Map<&'static str, NodeKind> = phf_map! {
    "function_declaration" => NodeKind::Function,
    "method_definition" => NodeKind::Method,
    "class_declaration" => NodeKind::Class,
    "interface_declaration" => NodeKind::Interface,
    "enum_declaration" => NodeKind::Enum,
};

static JAVASCRIPT_CAPTURES: Map<&'static str, NodeKind> = phf_map! {
    "function_declaration" => NodeKind::Function,
    "method_definition" => NodeKind::Method,
    "class_declaration" => NodeKind::Class,
};

static PYTHON_CAPTURES: Map<&'static str, NodeKind> = phf_map! {
    "function_definition" => NodeKind::Function,
    "class_definition" => NodeKind::Class,
};

static RUST_CAPTURES: Map<&'static str, NodeKind> = phf_map! {
    "function_item" => NodeKind::Function,
    "struct_item" => NodeKind::Struct,
    "enum_item" => NodeKind::Enum,
    "trait_item" => NodeKind::Interface,
    "impl_item" => NodeKind::Module,
    "const_item" => NodeKind::Const,
};

static GO_CAPTURES: Map<&'static str, NodeKind> = phf_map! {
    "function_declaration" => NodeKind::Function,
    "method_declaration" => NodeKind::Method,
    "type_declaration" => NodeKind::Struct,
};

/// Per-language default when `node_kind` is absent from the built-in and extension tables.
static LANGUAGE_DEFAULTS: Map<&'static str, NodeKind> = phf_map! {
    "typescript" => NodeKind::Const,
    "javascript" => NodeKind::Const,
    "python" => NodeKind::Const,
    "rust" => NodeKind::Function,
    "go" => NodeKind::Function,
};

/// Optional capture maps registered at runtime (checked only when non-empty).
#[derive(Debug, Clone)]
struct LanguageCaptureExtension {
    lang: SourceLanguage,
    mappings: Vec<(&'static str, NodeKind)>,
    default: NodeKind,
}

static EXTENSIONS: OnceLock<RwLock<Vec<LanguageCaptureExtension>>> = OnceLock::new();

fn extensions() -> &'static RwLock<Vec<LanguageCaptureExtension>> {
    EXTENSIONS.get_or_init(|| RwLock::new(Vec::new()))
}

fn builtin_captures(lang: SourceLanguage) -> &'static Map<&'static str, NodeKind> {
    match lang {
        SourceLanguage::TypeScript => &TYPESCRIPT_CAPTURES,
        SourceLanguage::JavaScript => &JAVASCRIPT_CAPTURES,
        SourceLanguage::Python => &PYTHON_CAPTURES,
        SourceLanguage::Rust => &RUST_CAPTURES,
        SourceLanguage::Go => &GO_CAPTURES,
    }
}

fn language_default(lang: SourceLanguage) -> NodeKind {
    LANGUAGE_DEFAULTS
        .get(lang.as_str())
        .copied()
        .unwrap_or(GLOBAL_DEFAULT_KIND)
}

fn extension_lookup(lang: SourceLanguage, node_kind: &str) -> Option<NodeKind> {
    let guard = extensions().read().ok()?;
    if guard.is_empty() {
        return None;
    }
    let ext = guard.iter().find(|entry| entry.lang == lang)?;
    ext.mappings
        .iter()
        .find(|(name, _)| *name == node_kind)
        .map(|(_, kind)| *kind)
        .or(Some(ext.default))
}

/// Map a tree-sitter node kind for `lang` to a Scout [`NodeKind`].
pub fn node_kind_from_capture(lang: SourceLanguage, node_kind: &str) -> NodeKind {
    if let Some(kind) = extension_lookup(lang, node_kind) {
        return kind;
    }
    builtin_captures(lang)
        .get(node_kind)
        .copied()
        .unwrap_or_else(|| language_default(lang))
}

/// Register or replace runtime capture mappings for `lang`.
///
/// Registered mappings take precedence over built-in tables. `default` is used when
/// `node_kind` is not listed in `mappings`.
pub fn register_language_capture_map(
    lang: SourceLanguage,
    mappings: &[(&'static str, NodeKind)],
    default: NodeKind,
) {
    let mut guard = extensions()
        .write()
        .expect("capture extension registry poisoned");
    if let Some(existing) = guard.iter_mut().find(|entry| entry.lang == lang) {
        existing.mappings = mappings.to_vec();
        existing.default = default;
        return;
    }
    guard.push(LanguageCaptureExtension {
        lang,
        mappings: mappings.to_vec(),
        default,
    });
}

#[cfg(test)]
pub(crate) fn clear_capture_extensions_for_test() {
    if let Ok(mut guard) = extensions().write() {
        guard.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every explicit built-in (language, tree-sitter node kind) → NodeKind row.
    const BUILTIN_MAPPINGS: &[(SourceLanguage, &'static str, NodeKind)] = &[
        (SourceLanguage::TypeScript, "function_declaration", NodeKind::Function),
        (SourceLanguage::TypeScript, "method_definition", NodeKind::Method),
        (SourceLanguage::TypeScript, "class_declaration", NodeKind::Class),
        (SourceLanguage::TypeScript, "interface_declaration", NodeKind::Interface),
        (SourceLanguage::TypeScript, "enum_declaration", NodeKind::Enum),
        (SourceLanguage::JavaScript, "function_declaration", NodeKind::Function),
        (SourceLanguage::JavaScript, "method_definition", NodeKind::Method),
        (SourceLanguage::JavaScript, "class_declaration", NodeKind::Class),
        (SourceLanguage::Python, "function_definition", NodeKind::Function),
        (SourceLanguage::Python, "class_definition", NodeKind::Class),
        (SourceLanguage::Rust, "function_item", NodeKind::Function),
        (SourceLanguage::Rust, "struct_item", NodeKind::Struct),
        (SourceLanguage::Rust, "enum_item", NodeKind::Enum),
        (SourceLanguage::Rust, "trait_item", NodeKind::Interface),
        (SourceLanguage::Rust, "impl_item", NodeKind::Module),
        (SourceLanguage::Rust, "const_item", NodeKind::Const),
        (SourceLanguage::Go, "function_declaration", NodeKind::Function),
        (SourceLanguage::Go, "method_declaration", NodeKind::Method),
        (SourceLanguage::Go, "type_declaration", NodeKind::Struct),
    ];

    /// Unmapped node kinds must resolve to the language-specific default.
    const LANGUAGE_FALLBACKS: &[(SourceLanguage, &'static str, NodeKind)] = &[
        (SourceLanguage::TypeScript, "lexical_declaration", NodeKind::Const),
        (SourceLanguage::JavaScript, "lexical_declaration", NodeKind::Const),
        (SourceLanguage::Python, "async_function_definition", NodeKind::Const),
        (SourceLanguage::Rust, "unknown_item", NodeKind::Function),
        (SourceLanguage::Go, "import_declaration", NodeKind::Function),
    ];

    #[test]
    fn builtin_capture_mappings() {
        for (lang, node_kind, want) in BUILTIN_MAPPINGS {
            assert_eq!(
                node_kind_from_capture(*lang, node_kind),
                *want,
                "mapping for {:?} + {}",
                lang,
                node_kind
            );
        }
    }

    #[test]
    fn language_specific_fallbacks() {
        for (lang, node_kind, want) in LANGUAGE_FALLBACKS {
            assert_eq!(
                node_kind_from_capture(*lang, node_kind),
                *want,
                "fallback for {:?} + {}",
                lang,
                node_kind
            );
        }
    }

    #[test]
    fn register_language_capture_map_overrides_builtin() {
        register_language_capture_map(
            SourceLanguage::Python,
            &[("custom_node", NodeKind::Interface)],
            NodeKind::Method,
        );
        assert_eq!(
            node_kind_from_capture(SourceLanguage::Python, "custom_node"),
            NodeKind::Interface
        );
        assert_eq!(
            node_kind_from_capture(SourceLanguage::Python, "unlisted_node"),
            NodeKind::Method
        );
        // Extension replaces the entire per-language table.
        assert_eq!(
            node_kind_from_capture(SourceLanguage::Python, "function_definition"),
            NodeKind::Method
        );
        clear_capture_extensions_for_test();
    }
}
