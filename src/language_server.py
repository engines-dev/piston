from multilspy import LanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger

PROJECT_ROOT = "/project"


async def get_language_server():
    config = MultilspyConfig.from_dict({"code_language": "typescript"})
    logger = MultilspyLogger()
    server = LanguageServer.create(config, logger, PROJECT_ROOT)
    async with server.start_server() as server:
        yield server
