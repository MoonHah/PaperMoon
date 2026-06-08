import json
import logging
from contextvars import ContextVar
from typing import Any

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Standard LogRecord built-in attributes — excluded from extra JSON fields
_STDLIB_ATTRS = frozenset({
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "message", "module", "msecs", "msg",
    "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "taskName", "asctime",
})


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def _get_otel_ids() -> tuple[str, str]:
    """Returns (trace_id, span_id) from the active OpenTelemetry span.
    Returns ('-', '-') when OTEL SDK is not installed or no span is active.
    Import is deferred so opentelemetry remains an optional dependency."""
    try:
        from opentelemetry import trace  # type: ignore[import]
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:
        pass
    return "-", "-"


class JsonFormatter(logging.Formatter):
    """Emits one JSON object per log line.

    Base fields: time, level, service, request_id, trace_id, span_id, logger, message.
    Any key passed via extra={} in the log call is merged into the same object.
    """

    def __init__(self, service: str = "papermoon") -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = _get_otel_ids()
        entry: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "service": self._service,
            "request_id": _request_id_var.get(),
            "trace_id": trace_id,
            "span_id": span_id,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge caller-supplied extra fields (e.g. latency_ms, status_code)
        for key, val in record.__dict__.items():
            if key not in _STDLIB_ATTRS and key not in entry:
                entry[key] = val
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", service: str = "papermoon") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service=service))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
