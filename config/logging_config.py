"""
Centralized logging configuration for the D&D game system.
Provides timestamped log files and console output with proper formatting.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class GameLogger:
    """Centralized logger for the D&D game system"""

    _instance: Optional[logging.Logger] = None
    _initialized: bool = False

    @classmethod
    def get_logger(cls, name: str = "dnd_game") -> logging.Logger:
        """
        Get or create the game logger instance.

        Args:
            name: Logger name (default: "dnd_game")

        Returns:
            Configured logger instance
        """
        if not cls._initialized:
            cls._setup_logging()
            cls._initialized = True

        return logging.getLogger(name)

    @classmethod
    def _setup_logging(cls):
        """Set up logging configuration with file and console handlers"""

        # Create logs directory if it doesn't exist
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Create timestamped log filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"dnd_game_{timestamp}.log"

        # Create root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Remove existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # Create formatters
        detailed_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_formatter = logging.Formatter(
            fmt='%(levelname)s - %(message)s'
        )

        # File handler (DEBUG and above)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)

        # Console handler (INFO and above)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # Set Haystack loggers to WARNING level to reduce noise
        logging.getLogger('haystack').setLevel(logging.WARNING)
        logging.getLogger('haystack.components').setLevel(logging.WARNING)
        logging.getLogger('haystack.components.agents').setLevel(logging.WARNING)

        # Create game-specific logger
        game_logger = logging.getLogger("dnd_game")
        game_logger.info(f"Logging initialized. Log file: {log_file}")

        return game_logger


def get_logger(name: str = "dnd_game") -> logging.Logger:
    """
    Convenience function to get a logger instance.

    Args:
        name: Logger name (default: "dnd_game")

    Returns:
        Configured logger instance

    Example:
        >>> from config.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Game started")
    """
    return GameLogger.get_logger(name)


# Pre-configure loggers for different modules
def get_module_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        module_name: Name of the module (usually __name__)

    Returns:
        Configured logger instance
    """
    return GameLogger.get_logger(f"dnd_game.{module_name}")
