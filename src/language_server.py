from enum import Enum

from multilspy import LanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


def get_language_server(language: str, workspace: str):
    config = MultilspyConfig.from_dict({"code_language": language.lower()})
    logger = MultilspyLogger()
    server = LanguageServer.create(config, logger, workspace)
    return server
