#!/usr/bin/env python3
"""
Prometheus Metrics Exporter for Local Data Stack Pipeline

Provides metrics collection for pipeline execution using prometheus_client.
Supports two deployment modes:
1. Local Development: TextFile collector exports to /tmp/ for node_exporter
2. Kubernetes: HTTP server exposes /metrics endpoint for Prometheus scraping

Integration with existing infrastructure:
- Complements oss_framework/monitoring/prometheus/ K8s stack
- Uses TextFile pattern for batch jobs (recommended by Prometheus)
- Follows naming conventions from oss_framework/monitoring/prometheus/alerts.yml

Usage:
    from scripts.metrics_exporter import MetricsCollector

    metrics = MetricsCollector(mode='textfile', export_path='/tmp/pipeline_metrics.prom')
    metrics.record_stage_start('stage1_ingestion')
    # ... run stage ...
    metrics.record_stage_complete('stage1_ingestion', rows=1700, status='success')

References:
- Prometheus Python Client: https://github.com/prometheus/client_python
- TextFile Collector: https://prometheus.io/docs/guides/node-exporter/
- Best Practices: https://www.cncf.io/blog/2025/07/22/prometheus-labels-understanding-and-best-practices/
"""

import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        CollectorRegistry,
        write_to_textfile,
        start_http_server,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning(
        "prometheus_client not installed. Metrics collection disabled. "
        "Install with: pip install prometheus-client"
    )

try:
    import structlog

    logger = structlog.get_logger()
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Prometheus metrics collector for data pipeline monitoring.

    Metrics Exported:
    - pipeline_runs_total: Counter of pipeline runs by stage and status
    - pipeline_stage_duration_seconds: Histogram of stage execution time
    - pipeline_rows_processed: Gauge of rows processed in last run
    - pipeline_last_success_timestamp: Gauge of last successful run timestamp

    Labels:
    - stage: Pipeline stage name (stage1_ingestion, stage2_refinement, etc.)
    - status: Execution status (success, failure, timeout)
    - table: Table/dataset name (for row counts)

    Cardinality: < 100 time series (safe for production)
    """

    def __init__(
        self,
        mode: str = "textfile",
        export_path: str = "/tmp/pipeline_metrics.prom",
        http_port: int = 8000,
        registry: Optional[CollectorRegistry] = None,
    ):
        """
        Initialize metrics collector.

        Args:
            mode: 'textfile' for local/batch or 'http' for K8s deployment
            export_path: Path for textfile collector output
            http_port: Port for HTTP metrics server (mode='http' only)
            registry: Custom CollectorRegistry (default: creates new)
        """
        if not PROMETHEUS_AVAILABLE:
            self.enabled = False
            logger.warning("Metrics collection disabled (prometheus_client not installed)")
            return

        self.enabled = True
        self.mode = mode
        self.export_path = Path(export_path)
        self.http_port = http_port
        self.registry = registry or CollectorRegistry()

        # Timing state
        self._stage_start_times: Dict[str, float] = {}

        # Define metrics
        self._init_metrics()

        # Start HTTP server if in http mode
        if mode == "http":
            try:
                start_http_server(http_port, registry=self.registry)
                logger.info(f"Metrics HTTP server started on port {http_port}")
            except Exception as e:
                logger.error(f"Failed to start HTTP server: {e}")
                self.enabled = False

        logger.info(
            f"Metrics collector initialized",
            mode=mode,
            export_path=str(export_path) if mode == "textfile" else None,
            http_port=http_port if mode == "http" else None,
        )

    def _init_metrics(self):
        """Initialize Prometheus metric objects."""
        # Counter: Total pipeline runs by stage and status
        self.pipeline_runs = Counter(
            "pipeline_runs_total",
            "Total number of pipeline runs",
            ["stage", "status"],
            registry=self.registry,
        )

        # Histogram: Stage execution duration
        # Buckets optimized for typical pipeline stages (seconds)
        self.pipeline_duration = Histogram(
            "pipeline_stage_duration_seconds",
            "Pipeline stage execution duration in seconds",
            ["stage"],
            buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1200, 1800),
            registry=self.registry,
        )

        # Gauge: Rows processed (last run)
        self.pipeline_rows = Gauge(
            "pipeline_rows_processed",
            "Number of rows processed in last pipeline run",
            ["table"],
            registry=self.registry,
        )

        # Gauge: Last success timestamp
        self.pipeline_last_success = Gauge(
            "pipeline_last_success_timestamp",
            "Timestamp of last successful pipeline run",
            ["stage"],
            registry=self.registry,
        )

        # Gauge: Active pipeline jobs
        self.pipeline_active = Gauge(
            "pipeline_jobs_active",
            "Number of currently active pipeline jobs",
            registry=self.registry,
        )

    def record_stage_start(self, stage: str):
        """
        Record the start of a pipeline stage.

        Args:
            stage: Stage name (e.g., 'stage1_ingestion', 'stage2_refinement')
        """
        if not self.enabled:
            return

        self._stage_start_times[stage] = time.time()
        self.pipeline_active.inc()

        if STRUCTLOG_AVAILABLE:
            logger.info("stage.started", stage=stage)
        else:
            logger.info(f"Stage started: {stage}")

    def record_stage_complete(
        self, stage: str, rows: int = 0, status: str = "success", table: Optional[str] = None
    ):
        """
        Record the completion of a pipeline stage.

        Args:
            stage: Stage name
            rows: Number of rows processed (optional)
            status: Execution status ('success', 'failure', 'timeout')
            table: Table/dataset name for row count metric
        """
        if not self.enabled:
            return

        # Calculate duration
        if stage in self._stage_start_times:
            duration = time.time() - self._stage_start_times[stage]
            self.pipeline_duration.labels(stage=stage).observe(duration)
            del self._stage_start_times[stage]
        else:
            duration = 0
            logger.warning(f"No start time recorded for stage: {stage}")

        # Update metrics
        self.pipeline_runs.labels(stage=stage, status=status).inc()
        self.pipeline_active.dec()

        if status == "success":
            self.pipeline_last_success.labels(stage=stage).set(time.time())

        if rows > 0:
            table_name = table or stage
            self.pipeline_rows.labels(table=table_name).set(rows)

        # Export metrics (textfile mode only)
        if self.mode == "textfile":
            self._export_textfile()

        # Log completion
        if STRUCTLOG_AVAILABLE:
            logger.info("stage.complete", stage=stage, duration=duration, rows=rows, status=status)
        else:
            logger.info(
                f"Stage complete: {stage} (duration={duration:.2f}s, rows={rows}, status={status})"
            )

    def record_stage_error(self, stage: str, error_type: str, error_message: Optional[str] = None):
        """
        Record a pipeline stage error.

        Args:
            stage: Stage name
            error_type: Error classification (e.g., 'timeout', 'validation', 'connection')
            error_message: Optional error message for logging
        """
        if not self.enabled:
            return

        # Update metrics with failure status
        self.record_stage_complete(stage=stage, status="failure")

        # Log error
        if STRUCTLOG_AVAILABLE:
            logger.error(
                "stage.failed", stage=stage, error_type=error_type, error_message=error_message
            )
        else:
            logger.error(
                f"Stage failed: {stage} (error_type={error_type}, message={error_message})"
            )

    def _export_textfile(self):
        """Export metrics to textfile for node_exporter."""
        try:
            # Ensure directory exists
            self.export_path.parent.mkdir(parents=True, exist_ok=True)

            # Write metrics
            write_to_textfile(str(self.export_path), self.registry)

            if STRUCTLOG_AVAILABLE:
                logger.debug("metrics.exported", path=str(self.export_path))
            else:
                logger.debug(f"Metrics exported to {self.export_path}")
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current metrics (for debugging).

        Returns:
            Dictionary with metric values
        """
        if not self.enabled:
            return {"enabled": False}

        return {
            "enabled": True,
            "mode": self.mode,
            "export_path": str(self.export_path),
            "active_stages": len(self._stage_start_times),
            "stages": list(self._stage_start_times.keys()),
        }


# Convenience function for simple usage
def create_metrics_collector(
    mode: str = "textfile", export_path: str = "/tmp/pipeline_metrics.prom"
) -> MetricsCollector:
    """
    Create a metrics collector with default settings.

    Args:
        mode: 'textfile' for local/batch or 'http' for K8s deployment
        export_path: Path for textfile collector output

    Returns:
        Configured MetricsCollector instance
    """
    return MetricsCollector(mode=mode, export_path=export_path)


if __name__ == "__main__":
    """Example usage and testing."""
    import sys

    print("Prometheus Metrics Exporter - Example Usage\n")

    if not PROMETHEUS_AVAILABLE:
        print("ERROR: prometheus_client not installed")
        print("Install with: pip install prometheus-client")
        sys.exit(1)

    # Create collector
    metrics = create_metrics_collector(mode="textfile", export_path="/tmp/test_metrics.prom")

    # Simulate pipeline execution
    print("Simulating pipeline execution...")

    metrics.record_stage_start("stage1_ingestion")
    time.sleep(0.5)
    metrics.record_stage_complete("stage1_ingestion", rows=1700, status="success")

    metrics.record_stage_start("stage2_refinement")
    time.sleep(0.3)
    metrics.record_stage_complete("stage2_refinement", rows=1695, status="success")

    metrics.record_stage_start("stage3_analytics")
    time.sleep(0.2)
    metrics.record_stage_complete("stage3_analytics", rows=5, status="success")

    # Simulate error
    metrics.record_stage_start("stage4_export")
    time.sleep(0.1)
    metrics.record_stage_error(
        "stage4_export", error_type="connection", error_message="DuckDB connection lost"
    )

    print(f"\nMetrics exported to: /tmp/test_metrics.prom")
    print("\nView metrics with:")
    print("  cat /tmp/test_metrics.prom")
    print("\nTo scrape with Prometheus node_exporter:")
    print("  node_exporter --collector.textfile.directory=/tmp")
    print("  curl http://localhost:9100/metrics | grep pipeline_")
