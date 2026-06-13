use tree_sitter::Language;

pub fn language() -> Language {
    tree_sitter_rust::LANGUAGE.into()
}
