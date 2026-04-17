import logging
import sys
from contextvars import ContextVar
from typing import Optional

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str):
    return _request_id_var.set(request_id or "-")


def reset_request_id(token) -> None:
    _request_id_var.reset(token)


def get_request_id() -> str:
    return _request_id_var.get()


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = getattr(record, "request_id", get_request_id())
        session_id = getattr(record, "session_id", None)
        model = getattr(record, "model", None)
        latency_ms = getattr(record, "latency_ms", None)
        if isinstance(latency_ms, float):
            latency_ms = int(latency_ms)

        parts = []
        if request_id and request_id != "-":
            parts.append(f"req={request_id}")
        if session_id and session_id != "-":
            parts.append(f"sid={session_id}")
        if model and model != "-":
            parts.append(f"model={model}")
        if latency_ms is not None and latency_ms != "-":
            parts.append(f"latency_ms={latency_ms}")

        context = f"[{' '.join(parts)}]" if parts else ""
        record.context_prefix = f"{context} " if context else ""
        return True


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    include_context: bool = True,
) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Avoid gbk encoding issues on Windows terminals.
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if include_context:
        log_format = "%(asctime)s.%(msecs)03d [%(levelname)s] %(context_prefix)s%(message)s"
    else:
        log_format = "%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    if include_context:
        context_filter = RequestContextFilter()
        for handler in handlers:
            handler.addFilter(context_filter)

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
