# app/logging_config.py

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

"""
This module configures the application's logging system with:
- A custom log format showing timestamp, level, module, filename, line number, and function name
- Both console and file output handlers
- Configurable log level through environment variable
- Log file rotation to prevent excessive disk usage
"""

# Define a custom formatter to include filename and function name
# This format provides detailed context for each log message:
# - Timestamp for when the event occurred
# - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
# - Logger name
# - Source filename and line number
# - Function name where the log was generated
# - The actual log message
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d - %(funcName)s] - %(message)s")

# Retrieve logging level from environment variable, default to INFO
# This allows runtime configuration of logging verbosity without code changes
# Set LOG_LEVEL environment variable to one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

# Define the global logger that will be used throughout the application
# This ensures consistent logging configuration across all modules
logger = logging.getLogger("global_logger")
logger.setLevel(log_level)

# Create console handler for real-time log output
# This sends logs to stdout, typically the terminal or console
# Useful for development and debugging
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(log_level)
console_handler.setFormatter(formatter)

# Create file handler with rotation for persistent logs
# Features:
# - Writes to app.log in the current directory
# - Rotates logs when they reach 10MB
# - Keeps up to 5 backup copies
# - Logs at DEBUG level to capture more detailed information than console
file_handler = RotatingFileHandler("app.log", maxBytes=10 * 1024 * 1024, backupCount=5)
file_handler.setLevel(logging.DEBUG)  # File handler can log more detailed info
file_handler.setFormatter(formatter)

# Add both console and file handlers to the logger
# This enables simultaneous output to both destinations
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Prevent log messages from being propagated to the root logger
# This avoids duplicate log messages when multiple loggers are in use
logger.propagate = False
