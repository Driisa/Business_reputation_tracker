import logging
import os
import sys
from datetime import datetime

def setup_logging(log_level=logging.INFO):
    """Configure logging for the entire application."""
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"pipeline_{timestamp}.log")

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)  # Use stdout with proper encoding
        ]
    )

    # Create loggers for different components
    loggers = {
        "pipeline": logging.getLogger("pipeline"),
        "search": logging.getLogger("search"),
        "scraping": logging.getLogger("scraping"),
        "cleaning": logging.getLogger("cleaning"),
        "analysis": logging.getLogger("analysis"),
        "database": logging.getLogger("database"),
        "api": logging.getLogger("api")
    }

    # Set log levels for specific components
    loggers["pipeline"].setLevel(log_level)
    loggers["search"].setLevel(log_level)
    loggers["scraping"].setLevel(log_level)
    loggers["cleaning"].setLevel(log_level)
    loggers["analysis"].setLevel(log_level)
    loggers["database"].setLevel(log_level)
    loggers["api"].setLevel(log_level)

    return loggers 