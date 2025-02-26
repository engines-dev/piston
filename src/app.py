from typing import Annotated
from fastapi import FastAPI, Depends, File
from multilspy import LanguageServer
from pydantic_settings import BaseSettings
from multilspy import LanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger

from .parsing import parse_diff_patch


class Settings(BaseSettings):
    project_root: str = "/workspace"
    code_language: str | None = None


settings = Settings()
app = FastAPI()


async def language_server():
    config = MultilspyConfig.from_dict({"code_language": settings.code_language})
    logger = MultilspyLogger()
    server = LanguageServer.create(config, logger, settings.project_root)
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
    digest = parse_diff_patch(patch, settings.code_language)
    return {"digest": digest}
