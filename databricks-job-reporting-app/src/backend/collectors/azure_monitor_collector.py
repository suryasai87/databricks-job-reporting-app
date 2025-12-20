"""
Azure Monitor Collector for Databricks Cluster Metrics.

This module provides functionality to collect cloud metrics from Azure Monitor
for Databricks clusters running on Azure.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class CloudMetrics:
    """Data class representing cloud infrastructure metrics."""

    cluster_name: str
    timestamp: datetime
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_read_bytes: Optional[float] = None
    disk_write_bytes: Optional[float] = None
    network_in_bytes: Optional[float] = None
    network_out_bytes: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert metrics to dictionary format."""
        return {
            "cluster_name": self.cluster_name,
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_read_bytes": self.disk_read_bytes,
            "disk_write_bytes": self.disk_write_bytes,
            "network_in_bytes": self.network_in_bytes,
            "network_out_bytes": self.network_out_bytes,
        }


class AzureMonitorCollector:
    """
    Collector for Azure Monitor metrics.

    This class interfaces with Azure Monitor to collect infrastructure metrics
    for Databricks clusters running on Azure.

    Attributes:
        tenant_id: Azure AD tenant ID
        client_id: Azure AD application (client) ID
        client_secret: Azure AD application secret
        workspace_id: Log Analytics workspace ID
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        """
        Initialize the Azure Monitor collector.

        Args:
            tenant_id: Azure AD tenant ID
            client_id: Azure AD application (client) ID
            client_secret: Azure AD application secret
            workspace_id: Log Analytics workspace ID
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.workspace_id = workspace_id

        self._credential = None
        self._metrics_client = None
        self._logs_client = None
        self._initialized = False

        if self.is_available():
            self._initialize_clients()

    def is_available(self) -> bool:
        """
        Check if Azure Monitor collector is properly configured.

        Returns:
            True if all required credentials are provided, False otherwise.
        """
        required_fields = [
            self.tenant_id,
            self.client_id,
            self.client_secret,
            self.workspace_id,
        ]
        return all(field is not None and field.strip() for field in required_fields)

    def _initialize_clients(self) -> bool:
        """
        Initialize Azure SDK clients.

        Returns:
            True if clients were initialized successfully, False otherwise.
        """
        if self._initialized:
            return True

        try:
            from azure.identity import ClientSecretCredential
            from azure.monitor.query import MetricsQueryClient, LogsQueryClient

            self._credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            self._metrics_client = MetricsQueryClient(self._credential)
            self._logs_client = LogsQueryClient(self._credential)
            self._initialized = True

            logger.info("Azure Monitor clients initialized successfully")
            return True

        except ImportError as e:
            logger.warning(
                "Azure SDK packages not installed. Install with: "
                "pip install azure-identity azure-monitor-query. Error: %s",
                e
            )
            return False
        except Exception as e:
            logger.error("Failed to initialize Azure Monitor clients: %s", e)
            return False

    def collect_metrics(
        self,
        cluster_name: str,
        time_range_minutes: int = 5,
    ) -> Optional[CloudMetrics]:
        """
        Collect infrastructure metrics for a Databricks cluster.

        Args:
            cluster_name: Name of the Databricks cluster
            time_range_minutes: Time range for metric aggregation (default: 5 minutes)

        Returns:
            CloudMetrics object containing the collected metrics, or None if
            collection failed or collector is not configured.
        """
        if not self.is_available():
            logger.debug("Azure Monitor collector not configured")
            return None

        if not self._initialized and not self._initialize_clients():
            logger.warning("Failed to initialize Azure Monitor clients")
            return None

        try:
            from azure.monitor.query import MetricsQueryClient, LogsQueryClient
            from azure.core.exceptions import AzureError

            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=time_range_minutes)
            timespan = (start_time, end_time)

            # Query Log Analytics for cluster metrics
            # Databricks metrics are typically available in custom logs
            query = f"""
            Perf
            | where Computer contains "{cluster_name}"
            | where TimeGenerated >= ago({time_range_minutes}m)
            | summarize
                avg_cpu = avg(CounterValue) by ObjectName, CounterName
            | where ObjectName == "Processor" or ObjectName == "Memory"
                or ObjectName == "LogicalDisk" or ObjectName == "Network Adapter"
            """

            metrics = CloudMetrics(
                cluster_name=cluster_name,
                timestamp=datetime.utcnow(),
            )

            try:
                from azure.monitor.query import LogsQueryStatus

                response = self._logs_client.query_workspace(
                    workspace_id=self.workspace_id,
                    query=query,
                    timespan=timespan,
                )

                if response.status == LogsQueryStatus.SUCCESS:
                    for table in response.tables:
                        for row in table.rows:
                            object_name = row[0]
                            counter_name = row[1]
                            value = row[2]

                            if object_name == "Processor" and "% Processor Time" in counter_name:
                                metrics.cpu_percent = float(value)
                            elif object_name == "Memory" and "% Used Memory" in counter_name:
                                metrics.memory_percent = float(value)
                            elif object_name == "LogicalDisk":
                                if "Disk Read Bytes/sec" in counter_name:
                                    metrics.disk_read_bytes = float(value)
                                elif "Disk Write Bytes/sec" in counter_name:
                                    metrics.disk_write_bytes = float(value)
                            elif object_name == "Network Adapter":
                                if "Bytes Received/sec" in counter_name:
                                    metrics.network_in_bytes = float(value)
                                elif "Bytes Sent/sec" in counter_name:
                                    metrics.network_out_bytes = float(value)

            except AzureError as e:
                logger.warning("Failed to query Log Analytics: %s", e)
                # Try alternative approach using Azure Monitor Metrics API
                metrics = self._collect_metrics_via_monitor_api(cluster_name, timespan)
                if metrics is None:
                    metrics = CloudMetrics(
                        cluster_name=cluster_name,
                        timestamp=datetime.utcnow(),
                    )

            logger.info("Collected Azure Monitor metrics for cluster: %s", cluster_name)
            return metrics

        except ImportError:
            logger.warning("Azure SDK packages not available")
            return None
        except Exception as e:
            logger.error("Error collecting Azure Monitor metrics: %s", e)
            return None

    def _collect_metrics_via_monitor_api(
        self,
        cluster_name: str,
        timespan: tuple,
    ) -> Optional[CloudMetrics]:
        """
        Alternative method to collect metrics via Azure Monitor Metrics API.

        Args:
            cluster_name: Name of the Databricks cluster
            timespan: Tuple of (start_time, end_time)

        Returns:
            CloudMetrics object or None if collection failed.
        """
        try:
            # This would require the resource ID of the Databricks workspace
            # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Databricks/workspaces/{ws}
            logger.debug(
                "Metrics API collection not implemented - requires resource ID"
            )
            return None
        except Exception as e:
            logger.error("Error in alternative metrics collection: %s", e)
            return None

    def close(self) -> None:
        """Close any open connections and cleanup resources."""
        self._credential = None
        self._metrics_client = None
        self._logs_client = None
        self._initialized = False
        logger.debug("Azure Monitor collector closed")
