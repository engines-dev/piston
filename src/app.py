import os
import subprocess
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, File
from multilspy import LanguageServer
from multilspy import LanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
from pydantic_settings import BaseSettings
from typing import Annotated, Optional

from .language import is_language_supported
from .parsing import parse_diff_patch


class Settings(BaseSettings):
    workspace_root: str = os.environ.get("WORKSPACE_ROOT", "/workspace")
    code_language: Optional[str] = None


settings = Settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global settings
    if os.environ.get("CODE_LANGUAGE") is not None:
        settings.code_language = os.environ.get("CODE_LANGUAGE")
    else:
        linguist_output = json.loads(
            subprocess.check_output(
                ["github-linguist", "--json"],
                cwd=settings.workspace_root,
            )
        )
        # output looks like
        # {
        #   "Shell": { "size": 5430, "percentage": "1.38" },
        #   "JavaScript": { "size": 2211, "percentage": "0.56" },
        #   "TypeScript": { "size": 385771, "percentage": "97.91" },
        #   "HTML": { "size": 590, "percentage": "0.15" }
        # }
        top_language = max(
            linguist_output.items(),
            key=lambda lang: float(lang[1]["percentage"]),
        )
        if not top_language:
            raise ValueError("Unable to determine code language in workspace")
        if not is_language_supported(top_language[0]):
            raise ValueError(f"Unsupported code language: {top_language[0]}")
        settings.code_language = top_language[0]
    yield


app = FastAPI(lifespan=lifespan)


async def language_server():
    config = MultilspyConfig.from_dict({"code_language": settings.code_language})
    logger = MultilspyLogger()
    server = LanguageServer.create(config, logger, settings.workspace_root)
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
    return {"symbols": res}


@app.post("/patch-digest")
async def patch_digest(
    patch: Annotated[bytes, File()],
):
    if settings.code_language is None:
        raise ValueError("Code language is not set")
    digest = parse_diff_patch(patch, settings.code_language)
    return {"digest": digest}
