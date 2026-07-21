"""Minimal Locust load profile for the biomarker backend.

Exercises the unauthenticated health/status endpoints so the performance-tests
CI job has a real locustfile to run. Kept intentionally small: it validates
that the service stays responsive under light concurrent load rather than
benchmarking any heavy analysis path (those need auth and uploaded data).
"""
from locust import HttpUser, between, task


class HealthUser(HttpUser):
    # Small think time so a short --headless run issues a steady request stream
    # without hammering the process.
    wait_time = between(0.1, 0.5)

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(1)
    def health_live(self):
        self.client.get("/health/live")

    @task(1)
    def api_status(self):
        self.client.get("/api/status")
