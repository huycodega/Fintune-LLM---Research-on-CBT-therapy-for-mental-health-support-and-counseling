"""
Prometheus observability stack — counters, histograms, gauges that match
the metrics named in cbt_database_map.html (latency_stage, triage_level_count,
hallucination_flag_rate, model_drift_score).

We use the stdlib-only approach: a single endpoint /metrics that emits
the Prometheus text exposition format. No prometheus_client dependency
needed — keeps the image small and avoids extra binary deps.

To swap in `prometheus-client` later, simply replace this file's
`render()` with that library — call sites do not change.
"""
import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List


_lock = Lock()

# Counter:  triage_level_count{level="L0|L1|L2|L3"}
_counters: Dict[str, Dict[tuple, int]] = defaultdict(lambda: defaultdict(int))
# Histogram: latency_stage_seconds{stage="<name>"} — record observations
_histograms: Dict[str, Dict[tuple, List[float]]] = defaultdict(
    lambda: defaultdict(list))
# Gauge: arbitrary numeric (hallucination_flag_rate, model_drift_score)
_gauges: Dict[str, Dict[tuple, float]] = defaultdict(dict)


_HIST_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)


def inc(name: str, value: float = 1.0, **labels) -> None:
    with _lock:
        key = tuple(sorted(labels.items()))
        _counters[name][key] += value


def observe(name: str, value: float, **labels) -> None:
    with _lock:
        key = tuple(sorted(labels.items()))
        _histograms[name][key].append(value)


def gauge(name: str, value: float, **labels) -> None:
    with _lock:
        key = tuple(sorted(labels.items()))
        _gauges[name][key] = value


class Timer:
    """Context manager: with Timer('stage_name', x='foo'): ..."""

    def __init__(self, name: str, **labels):
        self.name = name
        self.labels = labels

    def __enter__(self):
        self.t0 = time.monotonic()
        return self

    def __exit__(self, *_):
        observe(self.name, time.monotonic() - self.t0, **self.labels)


# ============================================================
# Render Prometheus text format
# ============================================================
def _fmt_labels(items: tuple) -> str:
    if not items:
        return ""
    return "{" + ",".join(f'{k}="{v}"' for k, v in items) + "}"


def render() -> str:
    lines: List[str] = []
    with _lock:
        # counters
        for name, by_labels in _counters.items():
            lines.append(f"# TYPE {name} counter")
            for labels, v in by_labels.items():
                lines.append(f"{name}{_fmt_labels(labels)} {v}")
        # gauges
        for name, by_labels in _gauges.items():
            lines.append(f"# TYPE {name} gauge")
            for labels, v in by_labels.items():
                lines.append(f"{name}{_fmt_labels(labels)} {v}")
        # histograms (bucket + sum + count)
        for name, by_labels in _histograms.items():
            lines.append(f"# TYPE {name} histogram")
            for labels, values in by_labels.items():
                if not values:
                    continue
                cumulative = 0
                total = 0.0
                for b in _HIST_BUCKETS:
                    cumulative += sum(1 for v in values if v <= b)
                    bucket_labels = labels + (("le", str(b)),)
                    lines.append(f"{name}_bucket{_fmt_labels(bucket_labels)} "
                                 f"{cumulative}")
                inf_labels = labels + (("le", "+Inf"),)
                lines.append(f"{name}_bucket{_fmt_labels(inf_labels)} "
                             f"{len(values)}")
                lines.append(f"{name}_sum{_fmt_labels(labels)} {sum(values)}")
                lines.append(f"{name}_count{_fmt_labels(labels)} "
                             f"{len(values)}")
    return "\n".join(lines) + "\n"
