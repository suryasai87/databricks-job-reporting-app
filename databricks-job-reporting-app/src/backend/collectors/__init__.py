"""
Databricks Job Reporting App - Collectors Module

This module contains collectors for gathering metrics from various Databricks sources.

Supported Collectors:
- AzureMonitorCollector: Collects metrics from Azure Monitor for Azure-based clusters
- CloudWatchCollector: Collects metrics from AWS CloudWatch for AWS-based clusters
- OTelCollector: Collects metrics via OpenTelemetry

Usage:
    from collectors import AzureMonitorCollector, CloudWatchCollector, CloudMetrics

    # Azure Monitor
    azure_collector = AzureMonitorCollector(
        tenant_id="your-tenant-id",
        client_id="your-client-id",
        client_secret="your-client-secret",
        workspace_id="your-workspace-id",
    )
    if azure_collector.is_available():
        metrics = azure_collector.collect_metrics("my-cluster")

    # AWS CloudWatch
    cw_collector = CloudWatchCollector(region="us-east-1")
    if cw_collector.is_available():
        metrics = cw_collector.collect_metrics("my-cluster")
"""

from collectors.azure_monitor_collector import (
    AzureMonitorCollector,
    CloudMetrics as AzureCloudMetrics,
)
from collectors.cloudwatch_collector import (
    CloudWatchCollector,
    CloudMetrics as AWSCloudMetrics,
)
from collectors.spark_ui_collector import (
    SparkUICollector,
    ExecutorMetrics,
    StageInfo,
    JobInfo,
    SparkUICollectorError,
    ClusterNotRunningError,
)
from collectors.otel_collector import (
    OTELCollector,
    OTELStatus,
    create_otel_collector,
)
from collectors.otel_init_script import (
    get_otel_init_script,
    get_otel_init_script_minimal,
    get_init_script_response,
)

# Use a unified CloudMetrics class (they have the same structure)
CloudMetrics = AWSCloudMetrics

__all__ = [
    # Cloud Provider Collectors
    "AzureMonitorCollector",
    "CloudWatchCollector",
    "CloudMetrics",
    "AzureCloudMetrics",
    "AWSCloudMetrics",
    # Spark UI Collector (Tier 1)
    "SparkUICollector",
    "ExecutorMetrics",
    "StageInfo",
    "JobInfo",
    "SparkUICollectorError",
    "ClusterNotRunningError",
    # OpenTelemetry Collector
    "OTELCollector",
    "OTELStatus",
    "create_otel_collector",
    "get_otel_init_script",
    "get_otel_init_script_minimal",
    "get_init_script_response",
]

__version__ = "1.0.0"
