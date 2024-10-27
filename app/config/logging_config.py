# app/logging_config.py

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Define a custom formatter to include filename and function name
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d - %(funcName)s] - %(message)s")

# Retrieve logging level from environment variable, default to INFO
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

# Define the global logger
logger = logging.getLogger("global_logger")
logger.setLevel(log_level)

# Create console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(log_level)
console_handler.setFormatter(formatter)

# Create file handler with rotation
file_handler = RotatingFileHandler("app.log", maxBytes=10 * 1024 * 1024, backupCount=5)
file_handler.setLevel(logging.DEBUG)  # File handler can log more detailed info
file_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Prevent log messages from being propagated to the root logger
logger.propagate = False
