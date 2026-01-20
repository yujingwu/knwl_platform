import threading
import time
from typing import Dict, Optional


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._requests_total = 0
        self._requests_by_tenant: Dict[str, int] = {}
        self._requests_by_endpoint: Dict[str, int] = {}
        self._latency_sum_total = 0.0
        self._latency_count_total = 0
        self._latency_sum_by_endpoint: Dict[str, float] = {}
        self._latency_count_by_endpoint: Dict[str, int] = {}
        self._errors_total = 0
        self._errors_by_status: Dict[str, int] = {}
        self._errors_by_tenant: Dict[str, int] = {}

    def record_request(
        self,
        endpoint: str,
        tenant_id: Optional[str],
        status_code: int,
        latency_ms: float,
    ) -> None:
        with self._lock:
            self._requests_total += 1
            self._requests_by_endpoint[endpoint] = (
                self._requests_by_endpoint.get(endpoint, 0) + 1
            )
            if tenant_id:
                self._requests_by_tenant[tenant_id] = (
                    self._requests_by_tenant.get(tenant_id, 0) + 1
                )
            self._latency_sum_total += latency_ms
            self._latency_count_total += 1
            self._latency_sum_by_endpoint[endpoint] = (
                self._latency_sum_by_endpoint.get(endpoint, 0.0) + latency_ms
            )
            self._latency_count_by_endpoint[endpoint] = (
                self._latency_count_by_endpoint.get(endpoint, 0) + 1
            )
            if status_code >= 400:
                self._errors_total += 1
                status_key = str(status_code)
                self._errors_by_status[status_key] = (
                    self._errors_by_status.get(status_key, 0) + 1
                )
                if tenant_id:
                    self._errors_by_tenant[tenant_id] = (
                        self._errors_by_tenant.get(tenant_id, 0) + 1
                    )

    def snapshot(self) -> dict:
        with self._lock:
            avg_overall = (
                self._latency_sum_total / self._latency_count_total
                if self._latency_count_total
                else 0.0
            )
            by_endpoint_avg = {
                endpoint: self._latency_sum_by_endpoint[endpoint]
                / self._latency_count_by_endpoint[endpoint]
                for endpoint in self._latency_sum_by_endpoint
            }
            uptime = int(time.time() - self._start_time)
            return {
                "uptimeSeconds": uptime,
                "requests": {
                    "total": self._requests_total,
                    "byTenant": dict(self._requests_by_tenant),
                    "byEndpoint": dict(self._requests_by_endpoint),
                },
                "latencyMs": {
                    "avgOverall": avg_overall,
                    "byEndpointAvg": by_endpoint_avg,
                },
                "errors": {
                    "total": self._errors_total,
                    "byStatus": dict(self._errors_by_status),
                    "byTenant": dict(self._errors_by_tenant),
                },
            }

