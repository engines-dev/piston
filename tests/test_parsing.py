from src.parsing import (
    Hunk,
    ChangeType,
    parse_diff_patch,
)

example_diff = b"""
diff --git src/app.py src/app.py
index 1fc9018..93e9679 100644
--- src/app.py
+++ src/app.py
@@ -1,17 +1,27 @@
 from typing import Annotated
-
-from fastapi import FastAPI, Depends
-from urllib.parse import unquote
+from fastapi import FastAPI, Depends, File
 from multilspy import LanguageServer
+from pydantic_settings import BaseSettings
+from multilspy import LanguageServer
+from multilspy.multilspy_config import MultilspyConfig
+from multilspy.multilspy_logger import MultilspyLogger
 
-from language_server import get_language_server
 
+class Settings(BaseSettings):
+    project_root: str = "/workspace"
+    code_language: str = "python"
+
+
+settings = Settings()
 app = FastAPI()
 
 
-@app.get("/")
-def read_root():
-    return {"Hello": "World, from FastAPI!"}
+async def language_server():
+    config = MultilspyConfig.from_dict({"code_language": settings.code_language})
+    logger = MultilspyLogger()
+    server = LanguageServer.create(config, logger, settings.project_root)
+    async with server.start_server() as server:
+        yield server
 
 
 @app.get("/definitions")
@@ -19,9 +29,8 @@ async def definitions(
     path: str,
     line: int,
     column: int,
-    lsp: Annotated[LanguageServer, Depends(get_language_server)],
+    lsp: Annotated[LanguageServer, Depends(language_server)],
 ):
-    path = unquote(path)  # in case it comes in URL encoded
     res = await lsp.request_definition(path, line, column)
     return {"definitions": res}
 
@@ -31,8 +40,27 @@ async def references(
     path: str,
     line: int,
     column: int,
-    lsp: Annotated[LanguageServer, Depends(get_language_server)],
+    lsp: Annotated[LanguageServer, Depends(language_server)],
 ):
-    path = unquote(path)  # in case it comes in URL encoded
     res = await lsp.request_references(path, line, column)
     return {"references": res}
+
+
+@app.get("/symbols")
+async def symbols(
+    path: str,
+    lsp: Annotated[LanguageServer, Depends(language_server)],
+):
+    res = await lsp.request_document_symbols(path)
+    return {"symbols": res}
+
+
+@app.post("/patch-digest")
+async def parse_diff_patch(
+    patch: Annotated[bytes, File()],
+) -> dict[str, str]:
+    # TODO
+    return {"digest": "patch digest"}
diff --git src/parsing.py src/parsing.py
new file mode 100644
index 0000000..06806ea
--- /dev/null
+++ src/parsing.py
@@ -0,0 +1,93 @@
+from dataclasses import dataclass
+from tree_sitter import Language, Parser, Node
+
+
+def get_language_parser(language: str):
+    if language == "diff":
+        import tree_sitter_diff
+
+        return Parser(Language(tree_sitter_diff.language()))
+    elif language == "python":
+        import tree_sitter_python
+
+        return Parser(Language(tree_sitter_python.language()))
+    # elif language == "typescript":
+    #     import tree_sitter_typescript
+    #     return Parser(Language(tree_sitter_typescript.language()))
+    else:
+        raise ValueError(f"Unsupported language: {language}")
+
+
"""


def test_parse_diff_patch():
    hunks = parse_diff_patch(example_diff, "Python")

    assert isinstance(hunks, list)
    assert len(hunks) == 4

    # hunk 0
    assert isinstance(hunks[0], Hunk)
    assert hunks[0].old_file == "src/app.py"
    assert hunks[0].new_file == "src/app.py"
    assert len(hunks[0].changes) == 24
    assert len([c for c in hunks[0].changes if c.type == ChangeType.Addition]) == 17
    assert len([c for c in hunks[0].changes if c.type == ChangeType.Deletion]) == 7
    # change is "-"
    assert hunks[0].changes[0].text == ""
    assert hunks[0].changes[0].line_index == 1
    assert hunks[0].changes[0].identifiers == []
    assert hunks[0].changes[0].type == ChangeType.Deletion
    # change is "-from fastapi import FastAPI, Depends"
    assert hunks[0].changes[1].text == "from fastapi import FastAPI, Depends"
    assert hunks[0].changes[1].line_index == 2
    assert hunks[0].changes[1].type == ChangeType.Deletion
    assert len(hunks[0].changes[1].identifiers) == 3
    assert hunks[0].changes[1].identifiers[0].name == "fastapi"
    assert hunks[0].changes[1].identifiers[0].char_index == 5
    assert hunks[0].changes[1].identifiers[1].name == "FastAPI"
    assert hunks[0].changes[1].identifiers[1].char_index == 20
    assert hunks[0].changes[1].identifiers[2].name == "Depends"
    assert hunks[0].changes[1].identifiers[2].char_index == 29
    # skip a couple lines and check on the first addition change
    # change is "+from fastapi import FastAPI, Depends, File"
    assert hunks[0].changes[3].text == "from fastapi import FastAPI, Depends, File"
    assert hunks[0].changes[3].line_index == 1
    assert hunks[0].changes[3].type == ChangeType.Addition
    assert len(hunks[0].changes[3].identifiers) == 4
    assert hunks[0].changes[3].identifiers[0].name == "fastapi"
    assert hunks[0].changes[3].identifiers[0].char_index == 5
    assert hunks[0].changes[3].identifiers[1].name == "FastAPI"
    assert hunks[0].changes[3].identifiers[1].char_index == 20
    assert hunks[0].changes[3].identifiers[2].name == "Depends"
    assert hunks[0].changes[3].identifiers[2].char_index == 29
    assert hunks[0].changes[3].identifiers[3].name == "File"
    assert hunks[0].changes[3].identifiers[3].char_index == 38

    # hunk 1
    assert isinstance(hunks[1], Hunk)
    assert hunks[1].old_file == "src/app.py"
    assert hunks[1].new_file == "src/app.py"
    assert len(hunks[1].changes) == 3
    assert len([c for c in hunks[1].changes if c.type == ChangeType.Addition]) == 1
    assert len([c for c in hunks[1].changes if c.type == ChangeType.Deletion]) == 2

    # hunk 2
    assert isinstance(hunks[2], Hunk)
    assert hunks[2].old_file == "src/app.py"
    assert hunks[2].new_file == "src/app.py"
    assert len(hunks[2].changes) == 20
    assert len([c for c in hunks[2].changes if c.type == ChangeType.Addition]) == 18
    assert len([c for c in hunks[2].changes if c.type == ChangeType.Deletion]) == 2

    # hunk 3
    assert isinstance(hunks[3], Hunk)
    assert hunks[3].old_file == "/dev/null"
    assert hunks[3].new_file == "src/parsing.py"
    assert len(hunks[3].changes) == 20
    assert len([c for c in hunks[3].changes if c.type == ChangeType.Addition]) == 20
    assert len([c for c in hunks[3].changes if c.type == ChangeType.Deletion]) == 0
