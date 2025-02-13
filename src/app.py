from typing import Annotated

from fastapi import FastAPI, Depends
from urllib.parse import unquote
from multilspy import LanguageServer

from language_server import get_language_server

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World, from FastAPI!"}


@app.get("/definitions")
async def definitions(
    path: str,
    line: int,
    column: int,
    lsp: Annotated[LanguageServer, Depends(get_language_server)],
):
    path = unquote(path)  # in case it comes in URL encoded
    res = await lsp.request_definition(path, line, column)
    return {"definitions": res}


@app.get("/references")
async def references(
    path: str,
    line: int,
    column: int,
    lsp: Annotated[LanguageServer, Depends(get_language_server)],
):
    path = unquote(path)  # in case it comes in URL encoded
    res = await lsp.request_references(path, line, column)
    return {"references": res}
