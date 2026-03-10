"""
utils.py

Shared helper utilities: logging setup, timestamp generation, and output directory paths.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_output_directory() -> Path:
    """
    Return the configured output directory as a Path, creating it if it does not exist.

    Returns:
        A Path object pointing to the output directory.
    """
    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_screenshot_directory() -> Path:
    """
    Return the screenshots subdirectory inside the output directory.

    Returns:
        A Path object pointing to output/screenshots/.
    """
    screenshot_dir = get_output_directory() / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    return screenshot_dir


def get_downloads_directory() -> Path:
    """
    Return the xml subdirectory inside the output directory for downloaded files.

    Returns:
        A Path object pointing to output/xml/.
    """
    downloads_dir = get_output_directory() / "xml"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return downloads_dir


def build_timestamp_string() -> str:
    """
    Return the current UTC datetime as a compact string safe for use in file names.

    Returns:
        A string in the format YYYYMMDD_HHMMSS.
    """
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def configure_logging() -> None:
    """
    Configure the root logger with a consistent format and the level from the environment.

    Reads LOG_LEVEL from environment variables. Defaults to INFO if not set.
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

