"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: Centralized logging module for error tracking and debugging
"""
import logging
import sys
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE = LOG_DIR / "log_errors"
LOG_GRAPHIC_FILE = LOG_DIR / "log_grafic_errors"


def setup_logger():
    """@param: none
    @return: configured logger instance
    @desc: initializes logger with file and console handlers"""
    LOG_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger("OpenFileSync")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def log_exception(logger, exc, context=""):
    """@param logger: logger instance
    @param exc: exception object
    @param context: optional context description
    @return: none
    @desc: logs exception with full traceback and context"""
    if context:
        logger.error(f"[{context}] {type(exc).__name__}: {exc}", exc_info=True)
    else:
        logger.error(f"{type(exc).__name__}: {exc}", exc_info=True)


def log_expected_error(logger, exc, context=""):
    """@param logger: logger instance
    @param exc: exception object
    @param context: optional context description
    @return: none
    @desc: logs expected error as single line without traceback"""
    if context:
        logger.debug(f"[{context}] {type(exc).__name__}: {exc}")
    else:
        logger.debug(f"{type(exc).__name__}: {exc}")


def install_global_handler(logger):
    """@param logger: logger instance
    @return: none
    @desc: installs global exception hook for uncaught exceptions"""
    original_hook = sys.excepthook

    def global_handler(exc_type, exc_value, exc_tb):
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_tb)
        )
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = global_handler


def setup_textual_logger():
    """@param: none
    @return: configured textual logger instance
    @desc: initializes logger for Textual UI framework errors"""
    LOG_DIR.mkdir(exist_ok=True)

    textual_logger = logging.getLogger("textual")
    textual_logger.setLevel(logging.DEBUG)

    if any(
        isinstance(h, logging.FileHandler) and h.baseFilename == str(LOG_GRAPHIC_FILE)
        for h in textual_logger.handlers
    ):
        return textual_logger

    file_handler = logging.FileHandler(LOG_GRAPHIC_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    textual_logger.addHandler(file_handler)

    return textual_logger
