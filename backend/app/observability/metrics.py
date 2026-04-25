"""
Prometheus metrics for pipeline, LLM, and federated flows.
"""

import time
from contextlib import contextmanager

from prometheus_client import REGISTRY, Counter, Histogram, generate_latest


def _histogram(name: str, documentation: str, labelnames):
    try:
        return Histogram(name, documentation, labelnames)
    except ValueError:
        for coll in list(REGISTRY._collector_to_names.keys()):
            if getattr(coll, "_name", None) == name:
                return coll
        raise


def _counter(name: str, documentation: str, labelnames):
    try:
        return Counter(name, documentation, labelnames)
    except ValueError:
        for coll in list(REGISTRY._collector_to_names.keys()):
            if getattr(coll, "_name", None) == name:
                return coll
        raise


REQUEST_LATENCY = _histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path_group"],
)

PIPELINE_RUNS = _counter(
    "pipeline_runs_total",
    "Pipeline runs by terminal status",
    ["status"],
)

LLM_REQUESTS = _counter(
    "llm_requests_total",
    "LLM calls",
    ["endpoint", "status"],
)

LLM_LATENCY = _histogram(
    "llm_request_duration_seconds",
    "LLM request latency",
    ["endpoint"],
)

FEDERATED_ROUNDS = _counter(
    "federated_rounds_total",
    "Federated rounds completed",
    ["phase"],
)


def metrics_response():
    from starlette.responses import Response

    return Response(generate_latest(), media_type="text/plain; version=0.0.4")


@contextmanager
def timed_llm(endpoint: str):
    t0 = time.perf_counter()
    try:
        yield
        LLM_REQUESTS.labels(endpoint=endpoint, status="ok").inc()
    except Exception:
        LLM_REQUESTS.labels(endpoint=endpoint, status="error").inc()
        raise
    finally:
        LLM_LATENCY.labels(endpoint=endpoint).observe(time.perf_counter() - t0)
