from contextlib import asynccontextmanager
import json
import logging
import os
import subprocess
from typing import Annotated, Optional

from fastapi import FastAPI, File
from fastapi.responses import JSONResponse
from multilspy.multilspy_types import SymbolKind
from pydantic_settings import BaseSettings

from .language_server import get_language_server
from .parsing import is_language_supported, parse_diff_patch


logger = logging.getLogger("uvicorn")


class Settings(BaseSettings):
    workspace_root: str = os.environ.get("WORKSPACE_ROOT", "/workspace")
    code_language: Optional[str] = None


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global settings

    if len(os.environ.get("CODE_LANGUAGE", "")) > 0:
        settings.code_language = os.environ.get("CODE_LANGUAGE")
    else:
        logger.info(f"Detecting code languages in workspace: {settings.workspace_root}")
        shell_output = json.loads(
            subprocess.check_output(
                ["enry", "-json"],
                cwd=settings.workspace_root,
            )
        )
        logger.info(
            f"The following languages are detected: {', '.join( [
            f"{lang['language']}={lang['percentage']}" for lang in shell_output
        ])}"
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
        logger.info(
            f"{top_language['language']} is the top language in the workspace and will be used for language server"
        )
        settings.code_language = top_language["language"]

    assert settings.code_language is not None
    app.state.lsp = get_language_server(settings.code_language, settings.workspace_root)
    async with app.state.lsp.start_server():
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/definitions")
async def definitions(
    path: str,
    line: int,
    character: int,
):
    try:
        res = await app.state.lsp.request_definition(path, line, character)
        return {"definitions": res}
    except Exception as e:
        if "Unexpected response from Language Server: None" in str(e):
            return JSONResponse(
                status_code=404,
                content={
                    "message": "No definitions found",
                    "input": {"path": path, "line": line, "character": character},
                },
            )
        else:
            raise e


@app.get("/references")
async def references(
    path: str,
    line: int,
    character: int,
):
    try:
        res = await app.state.lsp.request_references(path, line, character)
        return {"references": res}
    except Exception as e:
        if "Unexpected response from Language Server: None" in str(e):
            return JSONResponse(
                status_code=404,
                content={
                    "message": "No references found",
                    "input": {"path": path, "line": line, "character": character},
                },
            )
        else:
            raise e


@app.get("/symbols")
async def symbols(
    path: str,
):
    try:
        res = await app.state.lsp.request_document_symbols(path)
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
            "symbols": [
                {
                    **symbol,
                    "kind": SymbolKind(symbol["kind"]).name,
                }
                for symbol in res[0]
            ]
        }
    except Exception as e:
        if "Unexpected response from Language Server: None" in str(e):
            return JSONResponse(
                status_code=404,
                content={
                    "message": "No symbols found",
                    "input": {"path": path},
                },
            )
        else:
            raise e


@app.post("/patch-digest")
async def patch_digest(
    patch: Annotated[bytes, File()],
):
    if settings.code_language is None:
        raise ValueError("Code language is not set")
    digest = parse_diff_patch(patch, settings.code_language)
    return {"digest": digest}
