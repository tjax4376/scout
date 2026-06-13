use tree_sitter::Language;

pub fn language() -> Language {
    tree_sitter_go::LANGUAGE.into()
}
