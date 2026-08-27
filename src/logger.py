import logging
import os
import sys

from paths import project_file


def setup_logger(log_file=None, log_level=logging.INFO, log_to_console=False):
    if log_file is None:
        log_file = project_file("credit-analysis.log")
    logger = logging.getLogger("credit_analysis_logger")
    logger.setLevel(log_level)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()
