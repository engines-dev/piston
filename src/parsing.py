from dataclasses import dataclass
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


@dataclass
class Identifier:
    name: str
    char_index: int


def parse_line(parser: Parser, line: str) -> list[Identifier]:
    tree = parser.parse(bytes(line, "utf8"))
    identifiers_query = tree.language.query("(identifier) @identifier")
    captures = identifiers_query.captures(tree.root_node)
    identifiers = [
        Identifier(
            identifier.text.decode("utf8"),
            identifier.start_point.column,
        )
        for identifier in captures.get("identifier") or []
        if identifier.text is not None
    ]
    identifiers.sort(key=lambda x: x.char_index)
    return identifiers


class ChangeType(Enum):
    Addition = "addition"
    Deletion = "deletion"


@dataclass
class Change:
    line_index: int
    text: str
    type: ChangeType
    identifiers: list[Identifier]


@dataclass
class Hunk:
    old_file: str | None
    new_file: str | None
    changes: list[Change]


def parse_diff_patch(patch: bytes, patch_language: str) -> list[Hunk]:
    patch_parser = get_language_parser(patch_language)
    diff_parser = get_language_parser("Diff")

    # diff_lang = Language(tree_sitter_diff.language())
    # diff_parser = Parser(diff_lang)
    tree = diff_parser.parse(patch)

    hunks: list[Hunk] = []

    # we first break it down to "blocks", which will tell us the old and new file names of the hunks
    blocks_query = tree.language.query("(block) @block")
    for block_node in blocks_query.captures(tree.root_node)["block"]:
        file_name_query = tree.language.query(
            """
            (new_file (filename) @new_file)
            (old_file (filename) @old_file)
        """
        )
        captures = file_name_query.captures(block_node)
        old_file = (
            captures["old_file"][0].text.decode("utf8").strip()
            if captures["old_file"][0].text
            else None
        )
        new_file = (
            captures["new_file"][0].text.decode("utf8").strip()
            if captures["new_file"][0].text
            else None
        )

        # we then break it down to "hunks"
        hunks_query = tree.language.query("(hunk) @hunk")
        # `captures` in theory should return nodes in consistent order, but because we are querying
        # it multiple times, the sort order is messed up, so we manually sort it here
        hunk_nodes = sorted(
            hunks_query.captures(block_node)["hunk"], key=lambda x: x.start_byte
        )
        for hunk_node in hunk_nodes:
            line_index_query = tree.language.query(
                """
                (location (linerange) @old_line_index (linerange) @new_line_index)
            """
            )
            captures = line_index_query.captures(hunk_node)
            # text should look like: -1,17
            old_line_index = (
                int(
                    captures["old_line_index"][0]
                    .text.decode("utf8")
                    .strip()[1:]
                    .split(",")[0]
                )
                if captures["old_line_index"][0].text
                else None
            )
            # text should look like: +1,17
            new_line_index = (
                int(
                    captures["new_line_index"][0]
                    .text.decode("utf8")
                    .strip()[1:]
                    .split(",")[0]
                )
                if captures["new_line_index"][0].text
                else None
            )
            if old_line_index is None or new_line_index is None:
                raise ValueError(
                    "Could not find old_line_index or new_line_index while parsing diff patch"
                )
            # now we go through the changes in the hunk line by line
            changes = []
            changes_query = tree.language.query("(changes) @changes")
            # there should only be one changes node
            for change_node in changes_query.captures(hunk_node)["changes"][0].children:
                text = (
                    change_node.text.decode("utf8").strip() if change_node.text else ""
                )
                if text.startswith("+"):
                    changes.append(
                        Change(
                            # line numbers in diff are 1-based, we want to keep it zero-based for
                            # use in LSP later
                            line_index=new_line_index - 1,
                            text=text[1:],
                            type=ChangeType.Addition,
                            identifiers=parse_line(patch_parser, text[1:]),
                        )
                    )
                    new_line_index += 1
                elif text.startswith("-"):
                    changes.append(
                        Change(
                            # line numbers in diff are 1-based, we want to keep it zero-based for
                            # use in LSP later
                            line_index=old_line_index - 1,
                            text=text[1:],
                            type=ChangeType.Deletion,
                            identifiers=parse_line(patch_parser, text[1:]),
                        )
                    )
                    old_line_index += 1
                else:
                    # this is a context line that exists in both old and new files
                    old_line_index += 1
                    new_line_index += 1
            hunks.append(
                Hunk(
                    old_file=old_file,
                    new_file=new_file,
                    changes=changes,
                )
            )
    return hunks
