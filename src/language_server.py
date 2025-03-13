import logging
import time

from multilspy import LanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


logger = logging.getLogger("piston")


def get_language_server(language: str, workspace: str):
    """
    Create and return a language server instance for the specified language and workspace.
    
    Args:
        language: The programming language to use
        workspace: The workspace directory path
    
    Returns:
        A configured LanguageServer instance
    """
    logger.info(f"Initializing language server for language '{language}' in workspace '{workspace}'")
    start_time = time.time()
    
    logger.info(f"Creating MultilspyConfig with code_language={language.lower()}")
    config = MultilspyConfig.from_dict({"code_language": language.lower()})
    
    logger.info("Creating MultilspyLogger")
    multilspy_logger = MultilspyLogger()
    
    logger.info("Creating LanguageServer instance")
    server = LanguageServer.create(config, multilspy_logger, workspace)
    
    duration = time.time() - start_time
    logger.info(f"Language server initialization completed in {duration:.3f}s")
    
    return server
