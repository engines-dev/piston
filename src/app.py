from contextlib import asynccontextmanager
import json
import logging
import os
import subprocess
import time
from typing import Annotated, Optional

from fastapi import FastAPI, File, Request
from fastapi.responses import JSONResponse
from multilspy.multilspy_types import SymbolKind
from pydantic_settings import BaseSettings
import uvicorn

from .language_server import get_language_server
from .parsing import is_language_supported, parse_diff_patch


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("piston")


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
            "The following languages are detected: " + ', '.join([
            f"{lang['language']}={lang['percentage']}" for lang in shell_output
        ])
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
            raise ValueError(f"Unsupported code language: {top_language['lanaguage']}")
        logger.info(
            f"Language '{top_language['language']}' is the top language in the workspace and will be used for language server"
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
    request: Request,
):
    request_id = f"req_{int(time.time() * 1000)}"
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"[{request_id}] Definition request from {client_host} for {path}:{line}:{character}")
    
    try:
        logger.info(f"[{request_id}] Requesting definition from language server")
        start_time = time.time()
        res = await app.state.lsp.request_definition(path, line, character)
        duration = time.time() - start_time
        
        logger.info(f"[{request_id}] Found {len(res)} definitions in {duration:.3f}s")
        return {"definitions": res}
    except Exception as e:
        if "Unexpected response from Language Server: None" in str(e):
            logger.info(f"[{request_id}] No definitions found for {path}:{line}:{character}")
            return JSONResponse(
                status_code=404,
                content={
                    "message": "No definitions found",
                    "input": {"path": path, "line": line, "character": character},
                },
            )
        else:
            logger.error(f"[{request_id}] Error finding definitions: {str(e)}", exc_info=True)
            raise e


@app.get("/references")
async def references(
    path: str,
    line: int,
    character: int,
    request: Request,
):
    request_id = f"req_{int(time.time() * 1000)}"
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"[{request_id}] References request from {client_host} for {path}:{line}:{character}")
    
    try:
        logger.info(f"[{request_id}] Requesting references from language server")
        start_time = time.time()
        res = await app.state.lsp.request_references(path, line, character)
        duration = time.time() - start_time
        
        logger.info(f"[{request_id}] Found {len(res)} references in {duration:.3f}s")
        return {"references": res}
    except Exception as e:
        if "Unexpected response from Language Server: None" in str(e):
            logger.info(f"[{request_id}] No references found for {path}:{line}:{character}")
            return JSONResponse(
                status_code=404,
                content={
                    "message": "No references found",
                    "input": {"path": path, "line": line, "character": character},
                },
            )
        else:
            logger.error(f"[{request_id}] Error finding references: {str(e)}", exc_info=True)
            raise e


@app.get("/symbols")
async def symbols(
    path: str,
    request: Request,
):
    request_id = f"req_{int(time.time() * 1000)}"
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"[{request_id}] Symbols request from {client_host} for {path}")
    
    try:
        logger.info(f"[{request_id}] Requesting document symbols from language server")
        start_time = time.time()
        res = await app.state.lsp.request_document_symbols(path)
        duration = time.time() - start_time
        
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
        symbols = [
            {
                **symbol,
                "kind": SymbolKind(symbol["kind"]).name,
            }
            for symbol in res[0]
        ]
        
        logger.info(f"[{request_id}] Found {len(symbols)} symbols in {duration:.3f}s")
        return {"symbols": symbols}
    except Exception as e:
        if "Unexpected response from Language Server: None" in str(e):
            logger.info(f"[{request_id}] No symbols found for {path}")
            return JSONResponse(
                status_code=404,
                content={
                    "message": "No symbols found",
                    "input": {"path": path},
                },
            )
        else:
            logger.error(f"[{request_id}] Error finding symbols: {str(e)}", exc_info=True)
            raise e


@app.post("/patch-digest")
async def patch_digest(
    patch: Annotated[bytes, File()],
    request: Request,
):
    request_id = f"req_{int(time.time() * 1000)}"
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"[{request_id}] Patch digest request from {client_host}")
    
    if settings.code_language is None:
        logger.error(f"[{request_id}] Code language is not set")
        raise ValueError("Code language is not set")
    
    logger.info(f"[{request_id}] Parsing diff patch with language: {settings.code_language}")
    start_time = time.time()
    digest = parse_diff_patch(patch, settings.code_language)
    duration = time.time() - start_time
    
    hunk_count = len(digest)
    change_count = sum(len(hunk.changes) for hunk in digest)
    logger.info(f"[{request_id}] Parsed diff patch with {hunk_count} hunks and {change_count} changes in {duration:.3f}s")
    
    return {"digest": digest}
