from dataclasses import dataclass
from enum import Enum
import logging
import time
from tree_sitter import Language, Parser
from typing import cast


logger = logging.getLogger("piston")


class SupportedLanguage(Enum):
    Python = "Python"
    Diff = "Diff"


def is_language_supported(language: str) -> bool:
    """Check if a language is supported by the system."""
    result = language in SupportedLanguage.__members__.keys()
    logger.info(f"Checking if language '{language}' is supported: {result}")
    return result


def get_language_parser(language: str):
    """
    Get a tree-sitter parser for the specified language.
    
    Args:
        language: The language to get a parser for
        
    Returns:
        A configured Parser instance
        
    Raises:
        ValueError: If the language is not supported
    """
    if language.lower() == "diff":
        import tree_sitter_diff

        return Parser(Language(tree_sitter_diff.language()))
    elif language.lower() == "python":
        import tree_sitter_python

        return Parser(Language(tree_sitter_python.language()))
    else:
        raise ValueError(f"Unsupported language: {language}")


@dataclass
class Identifier:
    name: str
    character: int


def parse_line(parser: Parser, line: str) -> list[Identifier]:
    """
    Parse a line of code to extract identifiers.
    
    Args:
        parser: The tree-sitter parser to use
        line: The line of code to parse
        
    Returns:
        A list of Identifier objects found in the line
    """
    logger.info(f"Parsing line for identifiers: '{line[:50]}{'...' if len(line) > 50 else ''}'")
    start_time = time.time()
    
    try:
        # Parse the line into a syntax tree
        tree = parser.parse(bytes(line, "utf8"))
        
        # Create a query to find identifiers
        identifiers_query = tree.root_node.language.query("(identifier) @identifier")
        captures = identifiers_query.captures(tree.root_node)
        
        # Extract identifiers from the captures
        identifiers = []
        for node, tag in captures:
            if node.text:
                identifiers.append(
                    Identifier(
                        node.text.decode("utf8"),
                        node.start_point[1],  # column
                    )
                )
        
        # Sort identifiers by their character position
        identifiers.sort(key=lambda x: x.character)
        
        duration = time.time() - start_time
        logger.info(f"Found {len(identifiers)} identifiers in {duration:.3f}s")
        
        return identifiers
    except Exception as e:
        logger.warning(f"Error parsing line for identifiers: {str(e)}")
        return []


class ChangeType(Enum):
    Addition = "addition"
    Deletion = "deletion"


@dataclass
class Change:
    line: int
    text: str
    type: ChangeType
    identifiers: list[Identifier]


@dataclass
class Hunk:
    old_file: str | None
    new_file: str | None
    changes: list[Change]


def parse_diff_patch(patch: bytes, patch_language: str) -> list[Hunk]:
    """
    Parse a diff patch to extract hunks and changes.
    
    Args:
        patch: The diff patch content as bytes
        patch_language: The language of the code in the patch
        
    Returns:
        A list of Hunk objects representing the changes in the patch
    """
    logger.info(f"Parsing diff patch with language: {patch_language}")
    
    # Get parsers for the patch language and diff format
    patch_parser = get_language_parser(patch_language)
    diff_parser = get_language_parser("diff")
    
    # Parse the patch into a syntax tree
    logger.info(f"Parsing diff patch content of {len(patch)} bytes")
    tree = diff_parser.parse(patch)
    
    hunks: list[Hunk] = []
    
    # Get the language from the diff parser
    diff_language = tree.root_node.language
    
    # We first break it down to "blocks", which will tell us the old and new file names of the hunks
    logger.info("Analyzing diff structure: extracting file blocks and hunks")
    try:
        blocks_query = diff_language.query("(block) @block")
        block_captures = blocks_query.captures(tree.root_node)
        block_count = len([node for node, _ in block_captures])
        
        for block_node, _ in block_captures:
            try:
                file_name_query = diff_language.query(
                    """
                    (new_file (filename) @new_file)
                    (old_file (filename) @old_file)
                    """
                )
                file_captures = file_name_query.captures(block_node)
                
                old_file = None
                new_file = None
                
                for node, tag in file_captures:
                    if tag == "old_file" and node.text:
                        old_file = node.text.decode("utf8").strip()
                    elif tag == "new_file" and node.text:
                        new_file = node.text.decode("utf8").strip()
                
                logger.info(f"Processing changes between files: {old_file or '/dev/null'} → {new_file or '/dev/null'}")
                
                # We then break it down to "hunks"
                hunks_query = diff_language.query("(hunk) @hunk")
                hunk_captures = hunks_query.captures(block_node)
                
                # Sort hunk nodes by their start byte
                hunk_nodes = sorted(
                    [node for node, _ in hunk_captures], 
                    key=lambda x: x.start_byte
                )
                
                for hunk_idx, hunk_node in enumerate(hunk_nodes):

                    
                    line_query = diff_language.query(
                        """
                        (location (linerange) @old_line (linerange) @new_line)
                        """
                    )
                    line_captures = line_query.captures(hunk_node)
                    
                    old_line = None
                    new_line = None
                    
                    for node, tag in line_captures:
                        if tag == "old_line" and node.text:
                            old_line_text = node.text.decode("utf8").strip()
                            old_line = int(old_line_text[1:].split(",")[0])
                        elif tag == "new_line" and node.text:
                            new_line_text = node.text.decode("utf8").strip()
                            new_line = int(new_line_text[1:].split(",")[0])
                    
                    if old_line is None or new_line is None:
                        logger.error("Could not find old_line or new_line while parsing diff patch")
                        continue
                    

                    
                    # Now we go through the changes in the hunk line by line
                    logger.info(f"Extracting changes from hunk at lines {old_line}-{new_line}")
                    changes = []
                    changes_query = diff_language.query("(changes) @changes")
                    changes_captures = changes_query.captures(hunk_node)
                    
                    if not changes_captures:
                        logger.warning(f"No changes found in hunk {hunk_idx+1}")
                        continue
                    
                    # Get the first changes node
                    changes_node = changes_captures[0][0]
                    change_nodes = changes_node.children

                    
                    for change_idx, change_node in enumerate(change_nodes):
                        text = (
                            change_node.text.decode("utf8").strip() if change_node.text else ""
                        )
                        
                        if text.startswith("+"):
                            logger.debug(f"Processing addition: {text[:50]}{'...' if len(text) > 50 else ''}")
                            # Line numbers in diff are 1-based, we want to keep it zero-based for use in LSP later
                            identifiers = parse_line(patch_parser, text[1:])
                            changes.append(
                                Change(
                                    line=new_line - 1,
                                    text=text[1:],
                                    type=ChangeType.Addition,
                                    identifiers=identifiers,
                                )
                            )
                            new_line += 1
                        elif text.startswith("-"):
                            logger.debug(f"Processing deletion: {text[:50]}{'...' if len(text) > 50 else ''}")
                            # Line numbers in diff are 1-based, we want to keep it zero-based for use in LSP later
                            identifiers = parse_line(patch_parser, text[1:])
                            changes.append(
                                Change(
                                    line=old_line - 1,
                                    text=text[1:],
                                    type=ChangeType.Deletion,
                                    identifiers=identifiers,
                                )
                            )
                            old_line += 1
                        else:
                            # This is a context line that exists in both old and new files
                            old_line += 1
                            new_line += 1
                    

                    hunks.append(
                        Hunk(
                            old_file=old_file,
                            new_file=new_file,
                            changes=changes,
                        )
                    )
            except Exception as e:
                logger.error(f"Error processing block: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Error parsing diff patch: {str(e)}")
        return []
    
    total_changes = sum(len(hunk.changes) for hunk in hunks)
    logger.info(f"Completed diff analysis: found {len(hunks)} hunks with {total_changes} total changes ({sum(1 for h in hunks for c in h.changes if c.type == ChangeType.Addition)} additions, {sum(1 for h in hunks for c in h.changes if c.type == ChangeType.Deletion)} deletions)")
    return hunks
