from enum import Enum
from tree_sitter import Language, Parser
from typing import cast


class SupportedLanguage(Enum):
    Python = "Python"
    Diff = "Diff"


def is_language_supported(language: str) -> bool:
    return language in SupportedLanguage.__members__.keys()


def get_language_parser(language: str):
    if not is_language_supported(language):
        raise ValueError(f"Unsupported language: {language}")
    lang = SupportedLanguage[language]
    if lang == SupportedLanguage.Diff:
        import tree_sitter_diff

        lang = tree_sitter_diff.language()
        # cast is just to get rid of pyright error because it's not able to infer lang's type
        # since it comes from C bindings
        return Parser(Language(cast(object, lang)))
    elif lang == SupportedLanguage.Python:
        import tree_sitter_python

        lang = tree_sitter_python.language()
        return Parser(Language(cast(object, lang)))
    else:
        raise ValueError(f"Unsupported language: {language}")
