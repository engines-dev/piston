from enum import Enum
from tree_sitter import Language, Parser
import tree_sitter_diff


class SupportedLanguage(Enum):
    Python = "Python"
    TypeScript = "TypeScript"
    Diff = "Diff"


def is_language_supported(language: str) -> bool:
    return language in SupportedLanguage.__members__.keys()


def get_language_parser(language: str):
    if not is_language_supported(language):
        raise ValueError(f"Unsupported language: {language}")
    lang = SupportedLanguage[language]
    if lang == SupportedLanguage.Diff:
        return Parser(Language(tree_sitter_diff.language()))
    elif lang == SupportedLanguage.Python:
        import tree_sitter_python

        return Parser(Language(tree_sitter_python.language()))
    # elif language == "typescript":
    #     import tree_sitter_typescript
    #     return Parser(Language(tree_sitter_typescript.language()))
    else:
        raise ValueError(f"Unsupported language: {language}")
