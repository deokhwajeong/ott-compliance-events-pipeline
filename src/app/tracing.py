"""
Distributed Tracing Module
Implements OpenTelemetry integration for distributed tracing
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import json
from functools import wraps
import time

logger = logging.getLogger(__name__)


class Span:
    """OpenTelemetry-like span representation"""

    def __init__(self, name: str, trace_id: str, span_id: str, parent_span_id: Optional[str] = None):
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.start_time = datetime.utcnow()
        self.end_time = None
        self.attributes: Dict[str, Any] = {}
        self.events: list = []
        self.status = "UNSET"  # UNSET, OK, ERROR

    def set_attribute(self, key: str, value: Any):
        """Set span attribute"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add event to span"""
        self.events.append({
            "name": name,
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": attributes or {},
        })

    def set_status(self, status: str, description: Optional[str] = None):
        """Set span status"""
        self.status = status
        if description:
            self.set_attribute("error.description", description)

    def end(self):
        """Mark span as ended"""
        self.end_time = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary"""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": (self.end_time - self.start_time).total_seconds() * 1000
            if self.end_time
            else None,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
        }


class Trace:
    """OpenTelemetry-like trace representation"""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.spans: Dict[str, Span] = {}
        self.root_span: Optional[Span] = None
        self.start_time = datetime.utcnow()

    def create_span(
        self, name: str, parent_span_id: Optional[str] = None
    ) -> Span:
        """Create a new span in this trace"""
        import uuid

        span_id = str(uuid.uuid4())
        span = Span(
            name=name,
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )
        self.spans[span_id] = span

        if parent_span_id is None:
            self.root_span = span

        return span

    def end_span(self, span_id: str):
        """End a span"""
        if span_id in self.spans:
            self.spans[span_id].end()

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary"""
        return {
            "trace_id": self.trace_id,
            "start_time": self.start_time.isoformat(),
            "span_count": len(self.spans),
            "spans": [span.to_dict() for span in self.spans.values()],
        }


class Tracer:
    """Tracer for creating and managing traces"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.traces: Dict[str, Trace] = {}
        self.current_trace: Optional[Trace] = None
        self.current_span: Optional[Span] = None

    def start_trace(self, name: str) -> Trace:
        """Start a new trace"""
        import uuid

        trace_id = str(uuid.uuid4())
        trace = Trace(trace_id)
        root_span = trace.create_span(name)
        root_span.set_attribute("service_name", self.service_name)
        self.traces[trace_id] = trace
        self.current_trace = trace
        self.current_span = root_span
        return trace

    def start_span(self, name: str) -> Span:
        """Start a child span in current trace"""
        if not self.current_trace:
            self.start_trace(name)
            return self.current_span

        parent_span_id = self.current_span.span_id if self.current_span else None
        span = self.current_trace.create_span(name, parent_span_id)
        prev_span = self.current_span
        self.current_span = span
        return span

    def end_span(self):
        """End current span"""
        if self.current_span:
            self.current_span.end()

    def get_current_trace(self) -> Optional[Trace]:
        """Get current trace"""
        return self.current_trace


class JaegerExporter:
    """Exporter for sending traces to Jaeger"""

    def __init__(
        self,
        jaeger_host: str = "localhost",
        jaeger_port: int = 6831,
        service_name: str = "ott-compliance",
    ):
        self.jaeger_host = jaeger_host
        self.jaeger_port = jaeger_port
        self.service_name = service_name
        self.exported_traces = []

    def export_trace(self, trace: Trace) -> bool:
        """Export trace to Jaeger"""
        try:
            # In real implementation, this would send to Jaeger UDP endpoint
            trace_dict = trace.to_dict()
            trace_dict["service_name"] = self.service_name
            self.exported_traces.append(trace_dict)
            logger.info(f"Exported trace {trace.trace_id} to Jaeger")
            return True
        except Exception as e:
            logger.error(f"Failed to export trace: {e}")
            return False

    def get_exported_traces(self) -> list:
        """Get list of exported traces"""
        return self.exported_traces


class OpenTelemetryIntegration:
    """Main OpenTelemetry integration class"""

    def __init__(self, service_name: str = "ott-compliance"):
        self.service_name = service_name
        self.tracer = Tracer(service_name)
        self.exporter = JaegerExporter(service_name=service_name)
        self.trace_context = {}

    def start_request_trace(self, request_id: str, path: str) -> Trace:
        """Start trace for incoming request"""
        trace = self.tracer.start_trace(f"HTTP {path}")
        trace.root_span.set_attribute("http.method", "GET")
        trace.root_span.set_attribute("http.url", path)
        trace.root_span.set_attribute("request_id", request_id)
        self.trace_context[request_id] = trace
        return trace

    def end_request_trace(self, request_id: str, status_code: int):
        """End trace for request"""
        trace = self.trace_context.get(request_id)
        if trace and trace.root_span:
            trace.root_span.set_attribute("http.status_code", status_code)
            trace.root_span.end()
            self.exporter.export_trace(trace)

    def create_span(self, name: str) -> Span:
        """Create a child span"""
        return self.tracer.start_span(name)

    def trace_function(self, func: Callable) -> Callable:
        """Decorator to trace function execution"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            span = self.create_span(func.__name__)
            span.set_attribute("function_name", func.__name__)

            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                span.set_attribute("duration_ms", duration)
                span.set_status("OK")
                return result
            except Exception as e:
                span.set_status("ERROR", str(e))
                span.add_event("exception", {"exception_type": type(e).__name__})
                raise
            finally:
                span.end()

        return wrapper


class MetricsCollector:
    """Collect metrics from traces"""

    def __init__(self):
        self.metrics = {}

    def collect_from_trace(self, trace: Trace) -> Dict[str, Any]:
        """Collect metrics from trace"""
        metrics = {
            "trace_id": trace.trace_id,
            "span_count": len(trace.spans),
            "total_duration_ms": 0,
            "spans_by_status": {"OK": 0, "ERROR": 0, "UNSET": 0},
            "slowest_spans": [],
            "error_spans": [],
        }

        # Calculate total duration and span statistics
        spans_with_duration = []
        for span in trace.spans.values():
            if span.end_time:
                duration = (span.end_time - span.start_time).total_seconds() * 1000
                spans_with_duration.append((span.name, duration, span))
                metrics["total_duration_ms"] += duration

            metrics["spans_by_status"][span.status] += 1

            if span.status == "ERROR":
                metrics["error_spans"].append({
                    "name": span.name,
                    "error": span.attributes.get("error.description"),
                })

        # Find slowest spans
        spans_with_duration.sort(key=lambda x: x[1], reverse=True)
        metrics["slowest_spans"] = [
            {"name": name, "duration_ms": duration}
            for name, duration, _ in spans_with_duration[:5]
        ]

        return metrics


def create_telemetry_config() -> Dict[str, Any]:
    """Create OpenTelemetry configuration"""
    return {
        "otel": {
            "enabled": True,
            "service_name": "ott-compliance",
            "version": "1.0.0",
            "environment": "production",
        },
        "jaeger": {
            "enabled": True,
            "endpoint": "http://jaeger:14268/api/traces",
            "service_name": "ott-compliance",
            "sampler": {
                "type": "probabilistic",
                "param": 1.0,  # 100% sampling
            },
        },
        "traces": {
            "exporters": ["jaeger"],
            "processors": ["batch"],
        },
        "metrics": {
            "enabled": True,
            "exporters": ["prometheus"],
            "interval_ms": 60000,
        },
        "logs": {
            "enabled": True,
            "exporters": ["jaeger"],
            "level": "INFO",
        },
    }
