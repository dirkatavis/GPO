"""
Logger utility module.

Provides a centralized logger instance for the application.
"""





import logging
import os
import sys
import configparser

# Read logging config from ini file, disable interpolation to allow %(...)s in format
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'logging.ini')
config = configparser.ConfigParser(interpolation=None)
config.read(CONFIG_PATH)

log_level = config.get('logging', 'level', fallback='INFO').upper()
log_format = config.get('logging', 'format', fallback='%(asctime)s [%(levelname)s] %(message)s')

# Determine log file name based on main script name
def _get_script_logfile():
    script_path = None
    # Try to get the main script path
    if hasattr(sys, 'argv') and sys.argv and sys.argv[0]:
        script_path = sys.argv[0]
    else:
        try:
            import __main__
            script_path = getattr(__main__, '__file__', None)
        except Exception:
            pass
    if script_path:
        script_base = os.path.splitext(os.path.basename(script_path))[0]
        log_dir = 'log'
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, f"{script_base}.log")
    # fallback to config
    return config.get('logging', 'file', fallback='log/results.log')

log_file = _get_script_logfile()

# Ensure log directory exists
LOG_DIR = os.path.dirname(os.path.abspath(log_file))
os.makedirs(LOG_DIR, exist_ok=True)

class ColorFormatter(logging.Formatter):
    RED = '\033[31m'
    RESET = '\033[0m'
    def format(self, record):
        msg = super().format(record)
        if record.levelno == logging.ERROR:
            return f"{self.RED}{msg}{self.RESET}"
        return msg

# File handler (plain)
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(log_format))

# Console handler (color for ERROR)
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter(log_format))

logging.basicConfig(level=getattr(logging, log_level, logging.INFO), handlers=[file_handler, console_handler])

# Create a logger instance
log = logging.getLogger(__name__)
