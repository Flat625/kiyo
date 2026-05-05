import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

class JSONFormatter(logging.Formatter):
    """JSON 格式化器，用于结构化日志"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


def setup_logger(
    name: str = "kiyo",
    level: int = logging.INFO,
    json_output: bool = False
) -> logging.Logger:
    """配置并返回日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    file_handler = logging.FileHandler(
        LOG_DIR / "kiyo.log",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    if json_output:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(console_format)
    logger.addHandler(file_handler)
    
    return logger


logger = setup_logger()


def get_logger(name: str = "kiyo") -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)
