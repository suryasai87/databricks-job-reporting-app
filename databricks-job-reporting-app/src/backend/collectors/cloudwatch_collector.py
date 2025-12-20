"""
AWS CloudWatch Collector for Databricks Cluster Metrics.

This module provides functionality to collect cloud metrics from AWS CloudWatch
for Databricks clusters running on AWS.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging
import os

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


class CloudWatchCollector:
    """
    Collector for AWS CloudWatch metrics.

    This class interfaces with AWS CloudWatch to collect infrastructure metrics
    for Databricks clusters running on AWS.

    Attributes:
        region: AWS region name
        namespace: CloudWatch metric namespace (default: "Databricks/Spark")
    """

    def __init__(
        self,
        region: Optional[str] = None,
        namespace: str = "Databricks/Spark",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """
        Initialize the CloudWatch collector.

        Args:
            region: AWS region name (e.g., 'us-east-1')
            namespace: CloudWatch metric namespace
            aws_access_key_id: AWS access key ID (optional, uses env/instance profile if not provided)
            aws_secret_access_key: AWS secret access key (optional)
        """
        self.region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        self.namespace = namespace
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key

        self._client = None
        self._initialized = False

        if self.is_available():
            self._initialize_client()

    def is_available(self) -> bool:
        """
        Check if CloudWatch collector is properly configured.

        Returns:
            True if AWS credentials are available (via env, instance profile, or explicit),
            False otherwise.
        """
        # Check if region is available
        if not self.region:
            logger.debug("AWS region not configured")
            return False

        # Check for explicit credentials
        if self._aws_access_key_id and self._aws_secret_access_key:
            return True

        # Check for environment variables
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
            return True

        # Check if boto3 is available and can find credentials
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError

            # Try to create a session to check for instance profile or other credentials
            session = boto3.Session(region_name=self.region)
            credentials = session.get_credentials()

            if credentials is not None:
                return True

        except ImportError:
            logger.debug("boto3 not installed")
            return False
        except Exception as e:
            logger.debug("Error checking AWS credentials: %s", e)
            return False

        return False

    def _initialize_client(self) -> bool:
        """
        Initialize AWS CloudWatch client.

        Returns:
            True if client was initialized successfully, False otherwise.
        """
        if self._initialized:
            return True

        try:
            import boto3
            from botocore.config import Config

            config = Config(
                retries={
                    'max_attempts': 3,
                    'mode': 'adaptive'
                }
            )

            client_kwargs = {
                'service_name': 'cloudwatch',
                'region_name': self.region,
                'config': config,
            }

            if self._aws_access_key_id and self._aws_secret_access_key:
                client_kwargs['aws_access_key_id'] = self._aws_access_key_id
                client_kwargs['aws_secret_access_key'] = self._aws_secret_access_key

            self._client = boto3.client(**client_kwargs)
            self._initialized = True

            logger.info("CloudWatch client initialized successfully for region: %s", self.region)
            return True

        except ImportError as e:
            logger.warning(
                "boto3 not installed. Install with: pip install boto3. Error: %s",
                e
            )
            return False
        except Exception as e:
            logger.error("Failed to initialize CloudWatch client: %s", e)
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
            logger.debug("CloudWatch collector not configured")
            return None

        if not self._initialized and not self._initialize_client():
            logger.warning("Failed to initialize CloudWatch client")
            return None

        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=time_range_minutes)

            metrics = CloudMetrics(
                cluster_name=cluster_name,
                timestamp=datetime.utcnow(),
            )

            # Define the metrics to collect
            metric_definitions = [
                {
                    'name': 'CPUUtilization',
                    'stat': 'Average',
                    'attr': 'cpu_percent',
                },
                {
                    'name': 'MemoryUtilization',
                    'stat': 'Average',
                    'attr': 'memory_percent',
                },
                {
                    'name': 'DiskReadBytes',
                    'stat': 'Sum',
                    'attr': 'disk_read_bytes',
                },
                {
                    'name': 'DiskWriteBytes',
                    'stat': 'Sum',
                    'attr': 'disk_write_bytes',
                },
                {
                    'name': 'NetworkIn',
                    'stat': 'Sum',
                    'attr': 'network_in_bytes',
                },
                {
                    'name': 'NetworkOut',
                    'stat': 'Sum',
                    'attr': 'network_out_bytes',
                },
            ]

            # Build metric data queries for batch request
            metric_data_queries = []
            for i, metric_def in enumerate(metric_definitions):
                metric_data_queries.append({
                    'Id': f'm{i}',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': self.namespace,
                            'MetricName': metric_def['name'],
                            'Dimensions': [
                                {
                                    'Name': 'ClusterName',
                                    'Value': cluster_name,
                                },
                            ],
                        },
                        'Period': time_range_minutes * 60,
                        'Stat': metric_def['stat'],
                    },
                    'ReturnData': True,
                })

            # Execute batch query
            response = self._client.get_metric_data(
                MetricDataQueries=metric_data_queries,
                StartTime=start_time,
                EndTime=end_time,
            )

            # Process results
            for i, result in enumerate(response.get('MetricDataResults', [])):
                if result.get('Values'):
                    attr_name = metric_definitions[i]['attr']
                    # Take the most recent value
                    value = result['Values'][0]
                    setattr(metrics, attr_name, float(value))

            # Try alternative namespace if no metrics found (EC2 metrics)
            if all(v is None for v in [
                metrics.cpu_percent,
                metrics.memory_percent,
                metrics.disk_read_bytes,
                metrics.disk_write_bytes,
                metrics.network_in_bytes,
                metrics.network_out_bytes,
            ]):
                logger.debug("No metrics found in namespace %s, trying EC2 metrics", self.namespace)
                ec2_metrics = self._collect_ec2_metrics(cluster_name, start_time, end_time, time_range_minutes)
                if ec2_metrics:
                    metrics = ec2_metrics

            logger.info("Collected CloudWatch metrics for cluster: %s", cluster_name)
            return metrics

        except ImportError:
            logger.warning("boto3 not available")
            return None
        except Exception as e:
            logger.error("Error collecting CloudWatch metrics: %s", e)
            return None

    def _collect_ec2_metrics(
        self,
        cluster_name: str,
        start_time: datetime,
        end_time: datetime,
        period_minutes: int,
    ) -> Optional[CloudMetrics]:
        """
        Collect metrics from AWS/EC2 namespace for instances tagged with cluster name.

        Args:
            cluster_name: Name of the Databricks cluster
            start_time: Start time for metric query
            end_time: End time for metric query
            period_minutes: Aggregation period in minutes

        Returns:
            CloudMetrics object or None if collection failed.
        """
        try:
            metrics = CloudMetrics(
                cluster_name=cluster_name,
                timestamp=datetime.utcnow(),
            )

            # First, find EC2 instances with the cluster tag
            instance_ids = self._find_cluster_instances(cluster_name)

            if not instance_ids:
                logger.debug("No EC2 instances found for cluster: %s", cluster_name)
                return None

            # Collect aggregated metrics across all instances
            ec2_metric_definitions = [
                ('CPUUtilization', 'Average', 'cpu_percent'),
                ('DiskReadBytes', 'Sum', 'disk_read_bytes'),
                ('DiskWriteBytes', 'Sum', 'disk_write_bytes'),
                ('NetworkIn', 'Sum', 'network_in_bytes'),
                ('NetworkOut', 'Sum', 'network_out_bytes'),
            ]

            for metric_name, stat, attr in ec2_metric_definitions:
                try:
                    # Get metric for all instances and aggregate
                    total_value = 0.0
                    count = 0

                    for instance_id in instance_ids:
                        response = self._client.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName=metric_name,
                            Dimensions=[
                                {
                                    'Name': 'InstanceId',
                                    'Value': instance_id,
                                },
                            ],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=period_minutes * 60,
                            Statistics=[stat],
                        )

                        datapoints = response.get('Datapoints', [])
                        if datapoints:
                            # Get the most recent datapoint
                            sorted_points = sorted(datapoints, key=lambda x: x['Timestamp'], reverse=True)
                            value = sorted_points[0].get(stat, 0)

                            if stat == 'Average':
                                total_value += value
                                count += 1
                            else:
                                total_value += value

                    if stat == 'Average' and count > 0:
                        setattr(metrics, attr, total_value / count)
                    elif total_value > 0:
                        setattr(metrics, attr, total_value)

                except Exception as e:
                    logger.debug("Error collecting EC2 metric %s: %s", metric_name, e)

            return metrics

        except Exception as e:
            logger.error("Error collecting EC2 metrics: %s", e)
            return None

    def _find_cluster_instances(self, cluster_name: str) -> List[str]:
        """
        Find EC2 instance IDs for a Databricks cluster.

        Args:
            cluster_name: Name of the Databricks cluster

        Returns:
            List of EC2 instance IDs.
        """
        try:
            import boto3

            ec2 = boto3.client('ec2', region_name=self.region)

            # Look for instances with Databricks cluster tag
            response = ec2.describe_instances(
                Filters=[
                    {
                        'Name': 'tag:databricks-cluster-name',
                        'Values': [cluster_name],
                    },
                    {
                        'Name': 'instance-state-name',
                        'Values': ['running'],
                    },
                ],
            )

            instance_ids = []
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_ids.append(instance['InstanceId'])

            return instance_ids

        except Exception as e:
            logger.debug("Error finding cluster instances: %s", e)
            return []

    def list_available_metrics(self, cluster_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available CloudWatch metrics for Databricks clusters.

        Args:
            cluster_name: Optional cluster name to filter metrics

        Returns:
            List of available metric definitions.
        """
        if not self._initialized and not self._initialize_client():
            return []

        try:
            params = {
                'Namespace': self.namespace,
            }

            if cluster_name:
                params['Dimensions'] = [
                    {
                        'Name': 'ClusterName',
                        'Value': cluster_name,
                    },
                ]

            response = self._client.list_metrics(**params)

            metrics = []
            for metric in response.get('Metrics', []):
                metrics.append({
                    'name': metric['MetricName'],
                    'namespace': metric['Namespace'],
                    'dimensions': metric.get('Dimensions', []),
                })

            return metrics

        except Exception as e:
            logger.error("Error listing CloudWatch metrics: %s", e)
            return []

    def close(self) -> None:
        """Close any open connections and cleanup resources."""
        self._client = None
        self._initialized = False
        logger.debug("CloudWatch collector closed")
