use tree_sitter::Language;

pub fn language() -> Language {
    tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into()
}
