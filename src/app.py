from contextlib import asynccontextmanager
import json
import os
import subprocess
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, File
from multilspy import LanguageServer
from multilspy.multilspy_types import SymbolKind
from pydantic_settings import BaseSettings

from .language_server import get_language_server
from .parsing import is_language_supported, parse_diff_patch


class Settings(BaseSettings):
    workspace_root: str = os.environ.get("WORKSPACE_ROOT", "/workspace")
    code_language: Optional[str] = None


settings = Settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global settings

    if len(os.environ.get("CODE_LANGUAGE", "")) > 0:
        settings.code_language = os.environ.get("CODE_LANGUAGE")
    else:
        shell_output = json.loads(
            subprocess.check_output(
                ["enry", "-json"],
                cwd=settings.workspace_root,
            )
        )
        # output looks like
        # [{"color":"#3572A5","language":"Python","percentage":"100.00%","type":"unknown"}]
        top_language = max(
            shell_output,
            key=lambda lang: float(lang["percentage"].rstrip("%")),
        )
        if not top_language:
            raise ValueError("Unable to determine code language in workspace")
        if not is_language_supported(top_language["language"]):
            raise ValueError(f"Unsupported code language: {top_language["lanaguage"]}")
        settings.code_language = top_language["language"]
    yield


app = FastAPI(lifespan=lifespan)


async def language_server():
    assert settings.code_language is not None
    server = get_language_server(settings.code_language, settings.workspace_root)
    async with server.start_server() as server:
        yield server


@app.get("/definitions")
async def definitions(
    path: str,
    line: int,
    column: int,
    lsp: Annotated[LanguageServer, Depends(language_server)],
):
    res = await lsp.request_definition(path, line, column)
    return {"definitions": res}


@app.get("/references")
async def references(
    path: str,
    line: int,
    column: int,
    lsp: Annotated[LanguageServer, Depends(language_server)],
):
    res = await lsp.request_references(path, line, column)
    return {"references": res}


@app.get("/symbols")
async def symbols(
    path: str,
    lsp: Annotated[LanguageServer, Depends(language_server)],
):
    res = await lsp.request_document_symbols(path)
    # each symbol is of the shape
    # {
    #   "name": "is_even",
    #   "kind": 12,
    #   "range": {
    #     "start": { "line": 0, "character": 0 },
    #     "end": { "line": 2, "character": 26 }
    #   },
    #   "selectionRange": {
    #     "start": { "line": 0, "character": 4 },
    #     "end": { "line": 0, "character": 11 }
    #   },
    #   "detail": "def is_even"
    # }
    # we just need to convert the `kind` to its string name
    return {
        "symbols": list(
            map(
                lambda symbol: {
                    **symbol,
                    "kind": SymbolKind(symbol["kind"]).name,
                },
                res[0],
            )
        )
    }


@app.post("/patch-digest")
async def patch_digest(
    patch: Annotated[bytes, File()],
):
    if settings.code_language is None:
        raise ValueError("Code language is not set")
    digest = parse_diff_patch(patch, settings.code_language)
    return {"digest": digest}
