"""Optional observability: OpenTelemetry spans when installed (no-op otherwise) and a Prometheus text exporter."""
from __future__ import annotations

import contextlib
import threading
from typing import Any, Dict, Iterator, Tuple

try:  # optional
    from opentelemetry import trace as _otel
    _TRACER = _otel.get_tracer("caterya")
except Exception:  # pragma: no cover
    _TRACER = None


@contextlib.contextmanager
def span(name: str, **attrs: Any) -> Iterator[None]:
    if _TRACER is None:
        yield
        return
    with _TRACER.start_as_current_span(name) as sp:  # pragma: no cover - needs opentelemetry
        for k, v in attrs.items():
            sp.set_attribute(k, v)
        yield


class Telemetry:
    """In-process counters/gauges rendered in the Prometheus text exposition format (no client library needed)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
        self.gauges: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}

    @staticmethod
    def _k(name: str, labels: Dict[str, str]):
        return name, tuple(sorted((k, str(v)) for k, v in labels.items()))

    def inc(self, name: str, **labels: str) -> None:
        with self._lock:
            k = self._k(name, labels)
            self.counters[k] = self.counters.get(k, 0) + 1

    def set(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self.gauges[self._k(name, labels)] = value

    def observe_report(self, report: Any) -> None:
        self.inc("caterya_evaluations_total", profile=report.profile, recommendation=report.recommendation)
        self.set("caterya_coverage_ratio", report.coverage, profile=report.profile)
        for o in report.outcomes:
            if o.result.tested:
                self.set("caterya_metric_value", o.result.value, metric=o.metric_id, profile=report.profile)

    def render(self) -> str:
        def fmt(items, typ):
            out, seen = [], set()
            for (name, labels), v in sorted(items.items()):
                if name not in seen:
                    out.append(f"# TYPE {name} {typ}")
                    seen.add(name)
                lab = ",".join(f'{k}="{val}"' for k, val in labels)
                out.append(f"{name}{{{lab}}} {v}" if lab else f"{name} {v}")
            return out
        with self._lock:
            return "\n".join(fmt(self.counters, "counter") + fmt(self.gauges, "gauge")) + "\n"
