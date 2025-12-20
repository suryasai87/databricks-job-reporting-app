"""
OpenTelemetry Init Script Generator for Databricks Clusters

This module provides functionality to generate init scripts that install
and configure the OpenTelemetry Collector on Databricks cluster nodes.

The generated script:
- Auto-detects the cloud provider (AWS or Azure)
- Downloads and installs OTEL Collector Contrib
- Configures exporters for CloudWatch (AWS) or Azure Monitor
- Enables Spark Prometheus metrics
- Runs as a systemd service
"""

import os
from typing import Optional


def get_otel_init_script(
    otel_version: str = "0.96.0",
    enable_cloudwatch: bool = True,
    enable_azure_monitor: bool = True,
    enable_prometheus: bool = True,
    cloudwatch_namespace: str = "Databricks/Spark",
    cloudwatch_region: Optional[str] = None,
    azure_instrumentation_key: Optional[str] = None,
    prometheus_port: int = 9090,
    scrape_interval: str = "15s",
    custom_exporters: Optional[str] = None,
) -> str:
    """
    Generate a bash init script for installing and configuring OTEL Collector
    on Databricks cluster nodes.

    Args:
        otel_version: Version of OTEL Collector Contrib to install
        enable_cloudwatch: Enable CloudWatch exporter (AWS)
        enable_azure_monitor: Enable Azure Monitor exporter
        enable_prometheus: Enable Prometheus metrics scraping
        cloudwatch_namespace: CloudWatch namespace for metrics
        cloudwatch_region: AWS region for CloudWatch (auto-detected if not specified)
        azure_instrumentation_key: Azure Application Insights instrumentation key
        prometheus_port: Port for Prometheus metrics endpoint
        scrape_interval: How often to scrape metrics
        custom_exporters: Additional custom exporter configuration (YAML)

    Returns:
        Bash script as a string that can be used as a Databricks init script
    """

    script = f'''#!/bin/bash
################################################################################
# OpenTelemetry Collector Init Script for Databricks
#
# This script installs and configures the OpenTelemetry Collector on
# Databricks cluster nodes. It auto-detects the cloud provider and
# configures appropriate exporters.
#
# Generated for OTEL Collector Contrib v{otel_version}
################################################################################

set -e

# Configuration variables
OTEL_VERSION="{otel_version}"
PROMETHEUS_PORT="{prometheus_port}"
SCRAPE_INTERVAL="{scrape_interval}"
CLOUDWATCH_NAMESPACE="{cloudwatch_namespace}"

# Logging function
log() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] OTEL-INIT: $1"
}}

log "Starting OpenTelemetry Collector installation..."

################################################################################
# Cloud Provider Detection
################################################################################

detect_cloud_provider() {{
    log "Detecting cloud provider..."

    # Check for AWS
    if curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/instance-id &>/dev/null; then
        export CLOUD_PROVIDER="aws"
        export AWS_REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "us-east-1")
        log "Detected AWS cloud provider in region $AWS_REGION"
        return 0
    fi

    # Check for Azure
    if curl -s --connect-timeout 2 -H "Metadata:true" "http://169.254.169.254/metadata/instance?api-version=2021-02-01" &>/dev/null; then
        export CLOUD_PROVIDER="azure"
        export AZURE_REGION=$(curl -s -H "Metadata:true" "http://169.254.169.254/metadata/instance/compute/location?api-version=2021-02-01&format=text" 2>/dev/null || echo "eastus")
        log "Detected Azure cloud provider in region $AZURE_REGION"
        return 0
    fi

    # Check for GCP
    if curl -s --connect-timeout 2 -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone &>/dev/null; then
        export CLOUD_PROVIDER="gcp"
        log "Detected GCP cloud provider"
        return 0
    fi

    log "WARNING: Could not detect cloud provider, defaulting to aws"
    export CLOUD_PROVIDER="aws"
    export AWS_REGION="us-east-1"
}}

################################################################################
# Install OTEL Collector Contrib
################################################################################

install_otel_collector() {{
    log "Installing OTEL Collector Contrib v${{OTEL_VERSION}}..."

    # Determine architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            ARCH="amd64"
            ;;
        aarch64)
            ARCH="arm64"
            ;;
    esac

    DOWNLOAD_URL="https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${{OTEL_VERSION}}/otelcol-contrib_${{OTEL_VERSION}}_linux_${{ARCH}}.tar.gz"

    # Download and install
    cd /tmp
    log "Downloading from $DOWNLOAD_URL"
    curl -sL "$DOWNLOAD_URL" -o otelcol-contrib.tar.gz

    tar -xzf otelcol-contrib.tar.gz
    mv otelcol-contrib /usr/local/bin/
    chmod +x /usr/local/bin/otelcol-contrib

    # Verify installation
    /usr/local/bin/otelcol-contrib --version
    log "OTEL Collector installed successfully"

    # Clean up
    rm -f otelcol-contrib.tar.gz
}}

################################################################################
# Enable Spark Prometheus Metrics
################################################################################

enable_spark_prometheus() {{
    log "Enabling Spark Prometheus metrics..."

    # Create Spark metrics configuration
    mkdir -p /databricks/spark/conf

    cat > /databricks/spark/conf/metrics.properties << 'METRICS_EOF'
# Spark Prometheus Metrics Configuration
*.sink.prometheusServlet.class=org.apache.spark.metrics.sink.PrometheusServlet
*.sink.prometheusServlet.path=/metrics/prometheus

# Enable all metric sources
master.source.jvm.class=org.apache.spark.metrics.source.JvmSource
worker.source.jvm.class=org.apache.spark.metrics.source.JvmSource
driver.source.jvm.class=org.apache.spark.metrics.source.JvmSource
executor.source.jvm.class=org.apache.spark.metrics.source.JvmSource

# Application metrics
application.source.jvm.class=org.apache.spark.metrics.source.JvmSource
application.source.application.class=org.apache.spark.metrics.source.ApplicationSource

# Enable all sources
*.source.jvm.class=org.apache.spark.metrics.source.JvmSource
METRICS_EOF

    # Add Spark configuration for Prometheus
    SPARK_CONF_FILE="/databricks/spark/conf/spark-defaults.conf"
    if [ -f "$SPARK_CONF_FILE" ]; then
        if ! grep -q "spark.ui.prometheus.enabled" "$SPARK_CONF_FILE"; then
            echo "" >> "$SPARK_CONF_FILE"
            echo "# OpenTelemetry Prometheus Configuration" >> "$SPARK_CONF_FILE"
            echo "spark.ui.prometheus.enabled true" >> "$SPARK_CONF_FILE"
            echo "spark.metrics.conf /databricks/spark/conf/metrics.properties" >> "$SPARK_CONF_FILE"
        fi
    else
        mkdir -p /databricks/spark/conf
        cat > "$SPARK_CONF_FILE" << 'SPARK_EOF'
# OpenTelemetry Prometheus Configuration
spark.ui.prometheus.enabled true
spark.metrics.conf /databricks/spark/conf/metrics.properties
SPARK_EOF
    fi

    log "Spark Prometheus metrics enabled"
}}

################################################################################
# Generate OTEL Collector Configuration
################################################################################

generate_otel_config() {{
    log "Generating OTEL Collector configuration for $CLOUD_PROVIDER..."

    mkdir -p /etc/otelcol-contrib

    # Base receivers configuration
    cat > /etc/otelcol-contrib/config.yaml << 'CONFIG_START'
receivers:
  # Prometheus receiver for Spark metrics
  prometheus:
    config:
      scrape_configs:
        - job_name: 'spark-driver'
          scrape_interval: {scrape_interval}
          static_configs:
            - targets: ['localhost:4040']
          metrics_path: /metrics/prometheus

        - job_name: 'spark-executor'
          scrape_interval: {scrape_interval}
          static_configs:
            - targets: ['localhost:4041']
          metrics_path: /metrics/executors/prometheus

        - job_name: 'spark-streaming'
          scrape_interval: {scrape_interval}
          static_configs:
            - targets: ['localhost:4040']
          metrics_path: /api/v1/applications/*/streaming/statistics

  # Host metrics receiver
  hostmetrics:
    collection_interval: {scrape_interval}
    scrapers:
      cpu:
      memory:
      disk:
      network:
      filesystem:
      load:
      processes:

  # OTLP receiver for application instrumentation
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  # Add resource attributes
  resource:
    attributes:
      - key: cloud.provider
        value: "${{CLOUD_PROVIDER}}"
        action: upsert
      - key: service.name
        value: databricks-spark
        action: upsert
      - key: cluster.id
        value: "${{DB_CLUSTER_ID:-unknown}}"
        action: upsert
      - key: job.id
        value: "${{DB_JOB_ID:-unknown}}"
        action: upsert
      - key: run.id
        value: "${{DB_RUN_ID:-unknown}}"
        action: upsert

  # Batch processor for efficiency
  batch:
    timeout: 10s
    send_batch_size: 1000
    send_batch_max_size: 2000

  # Memory limiter to prevent OOM
  memory_limiter:
    check_interval: 5s
    limit_mib: 512
    spike_limit_mib: 128

CONFIG_START

    # Add cloud-specific exporters
    case $CLOUD_PROVIDER in
        aws)
            generate_aws_config
            ;;
        azure)
            generate_azure_config
            ;;
        gcp)
            generate_gcp_config
            ;;
    esac

    # Add service configuration
    cat >> /etc/otelcol-contrib/config.yaml << 'SERVICE_CONFIG'

service:
  telemetry:
    logs:
      level: info
    metrics:
      address: 0.0.0.0:8888

  pipelines:
    metrics:
      receivers: [prometheus, hostmetrics, otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [logging]
SERVICE_CONFIG

    # Update exporters list based on cloud provider
    case $CLOUD_PROVIDER in
        aws)
            sed -i 's/exporters: \[logging\]/exporters: [logging, awscloudwatch]/' /etc/otelcol-contrib/config.yaml
            ;;
        azure)
            sed -i 's/exporters: \[logging\]/exporters: [logging, azuremonitor]/' /etc/otelcol-contrib/config.yaml
            ;;
    esac

    log "OTEL Collector configuration generated"
}}

generate_aws_config() {{
    log "Adding AWS CloudWatch exporter configuration..."

    AWS_REGION="${cloudwatch_region or '${{AWS_REGION}}'}"

    cat >> /etc/otelcol-contrib/config.yaml << AWS_EOF

exporters:
  # Debug logging
  logging:
    loglevel: info

  # AWS CloudWatch exporter
  awscloudwatch:
    namespace: "{cloudwatch_namespace}"
    region: ${{AWS_REGION}}
    dimension_rollup_option: "NoDimensionRollup"
    resource_to_telemetry_conversion:
      enabled: true
    metric_declarations:
      - dimensions: [[cluster.id], [job.id], [cluster.id, job.id]]
        metric_name_selectors:
          - "^spark_.*"
          - "^system_.*"
          - "^process_.*"
AWS_EOF
}}

generate_azure_config() {{
    log "Adding Azure Monitor exporter configuration..."

    # Get instrumentation key from environment or Key Vault
    AZURE_INSTRUMENTATION_KEY="${azure_instrumentation_key or '${{APPLICATIONINSIGHTS_CONNECTION_STRING:-}}'}"

    cat >> /etc/otelcol-contrib/config.yaml << AZURE_EOF

exporters:
  # Debug logging
  logging:
    loglevel: info

  # Azure Monitor exporter
  azuremonitor:
    connection_string: "${{AZURE_INSTRUMENTATION_KEY}}"
    instrumentation_key: "${{AZURE_INSTRUMENTATION_KEY}}"
    maxbatchsize: 100
    maxbatchinterval: 10s
AZURE_EOF
}}

generate_gcp_config() {{
    log "Adding GCP Cloud Monitoring exporter configuration..."

    cat >> /etc/otelcol-contrib/config.yaml << GCP_EOF

exporters:
  # Debug logging
  logging:
    loglevel: info

  # GCP Cloud Monitoring exporter
  googlecloud:
    metric:
      prefix: "custom.googleapis.com/databricks"
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
      max_elapsed_time: 120s
GCP_EOF
}}

################################################################################
# Create Systemd Service
################################################################################

create_systemd_service() {{
    log "Creating OTEL Collector systemd service..."

    cat > /etc/systemd/system/otelcol-contrib.service << 'SYSTEMD_EOF'
[Unit]
Description=OpenTelemetry Collector Contrib
Documentation=https://opentelemetry.io/docs/collector/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/bin/otelcol-contrib --config=/etc/otelcol-contrib/config.yaml
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5s
LimitNOFILE=65536
TimeoutStopSec=30

# Environment variables for Databricks context
Environment="DB_CLUSTER_ID=%i"
EnvironmentFile=-/etc/databricks/otel.env

# Hardening
ProtectSystem=full
ProtectHome=true
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

    # Create environment file with Databricks context
    mkdir -p /etc/databricks
    cat > /etc/databricks/otel.env << ENV_EOF
# Databricks environment variables for OTEL
DB_CLUSTER_ID=${{DB_CLUSTER_ID:-unknown}}
DB_CLUSTER_NAME=${{DB_CLUSTER_NAME:-unknown}}
DB_DRIVER_IP=${{DB_DRIVER_IP:-127.0.0.1}}
DB_IS_DRIVER=${{DB_IS_DRIVER:-false}}
DB_JOB_ID=${{DATABRICKS_JOB_ID:-unknown}}
DB_RUN_ID=${{DATABRICKS_RUN_ID:-unknown}}
SPARK_LOCAL_IP=${{SPARK_LOCAL_IP:-127.0.0.1}}
ENV_EOF

    log "Systemd service created"
}}

################################################################################
# Start OTEL Collector Service
################################################################################

start_otel_service() {{
    log "Starting OTEL Collector service..."

    # Reload systemd
    systemctl daemon-reload

    # Enable and start the service
    systemctl enable otelcol-contrib
    systemctl start otelcol-contrib

    # Wait for service to start
    sleep 3

    # Check status
    if systemctl is-active --quiet otelcol-contrib; then
        log "OTEL Collector service started successfully"
        systemctl status otelcol-contrib --no-pager || true
    else
        log "WARNING: OTEL Collector service failed to start"
        journalctl -u otelcol-contrib --no-pager -n 50 || true
    fi
}}

################################################################################
# Health Check Function
################################################################################

health_check() {{
    log "Performing health check..."

    # Check if service is running
    if ! systemctl is-active --quiet otelcol-contrib; then
        log "ERROR: OTEL Collector service is not running"
        return 1
    fi

    # Check if OTEL Collector is responding
    if curl -s http://localhost:8888/metrics > /dev/null 2>&1; then
        log "OTEL Collector health check passed"
        return 0
    else
        log "WARNING: OTEL Collector metrics endpoint not responding"
        return 1
    fi
}}

################################################################################
# Main Execution
################################################################################

main() {{
    log "=============================================="
    log "OpenTelemetry Collector Installation Script"
    log "=============================================="

    # Only run on cluster nodes (not local development)
    if [ ! -d "/databricks" ]; then
        log "Not running on Databricks cluster, skipping installation"
        exit 0
    fi

    # Detect cloud provider
    detect_cloud_provider

    # Install OTEL Collector
    install_otel_collector

    # Enable Spark Prometheus metrics
    enable_spark_prometheus

    # Generate configuration
    generate_otel_config

    # Create and start systemd service
    create_systemd_service
    start_otel_service

    # Perform health check
    health_check || true

    log "=============================================="
    log "OpenTelemetry Collector installation complete"
    log "=============================================="
}}

# Run main function
main "$@"

# Exit successfully even if health check fails
# (cluster should continue to start)
exit 0
'''

    return script


def get_otel_init_script_minimal() -> str:
    """
    Get a minimal version of the OTEL init script for quick testing.

    Returns:
        A simplified bash script for basic OTEL installation
    """
    return '''#!/bin/bash
# Minimal OTEL Collector Init Script for Databricks
set -e

# Only run on Databricks clusters
[ ! -d "/databricks" ] && exit 0

echo "Installing minimal OTEL Collector..."

# Install OTEL Collector
OTEL_VERSION="0.96.0"
ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
curl -sL "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${OTEL_VERSION}/otelcol-contrib_${OTEL_VERSION}_linux_${ARCH}.tar.gz" | tar -xzf - -C /tmp
mv /tmp/otelcol-contrib /usr/local/bin/
chmod +x /usr/local/bin/otelcol-contrib

# Create minimal config
mkdir -p /etc/otelcol-contrib
cat > /etc/otelcol-contrib/config.yaml << 'EOF'
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: spark
          static_configs:
            - targets: ['localhost:4040']
          metrics_path: /metrics/prometheus

exporters:
  logging:
    loglevel: info

service:
  pipelines:
    metrics:
      receivers: [prometheus]
      exporters: [logging]
EOF

# Start collector in background
nohup /usr/local/bin/otelcol-contrib --config=/etc/otelcol-contrib/config.yaml > /var/log/otelcol.log 2>&1 &

echo "OTEL Collector started"
'''


def generate_dbfs_upload_script(
    dbfs_path: str = "dbfs:/databricks/init-scripts/otel-collector.sh",
) -> str:
    """
    Generate a Python script to upload the init script to DBFS.

    Args:
        dbfs_path: The DBFS path where the init script should be uploaded

    Returns:
        Python script as a string
    """
    return f'''"""
Upload OTEL Init Script to DBFS

Run this script to upload the OpenTelemetry Collector init script
to DBFS for use with Databricks clusters.
"""

from databricks.sdk import WorkspaceClient
from otel_init_script import get_otel_init_script

def upload_init_script():
    """Upload the OTEL init script to DBFS."""
    w = WorkspaceClient()

    # Generate the init script
    script_content = get_otel_init_script()

    # Upload to DBFS
    dbfs_path = "{dbfs_path}"
    w.dbfs.put(
        path=dbfs_path.replace("dbfs:", ""),
        contents=script_content.encode("utf-8"),
        overwrite=True,
    )

    print(f"Init script uploaded to {{dbfs_path}}")
    print("\\nTo use this init script, add it to your cluster configuration:")
    print(f'  "init_scripts": [' + '{{"dbfs": {{"destination": "{dbfs_path}"}}}}'.format(dbfs_path=dbfs_path) + ']')

if __name__ == "__main__":
    upload_init_script()
'''


# Convenience function for API endpoints
def get_init_script_response() -> dict:
    """
    Get the init script in a format suitable for API response.

    Returns:
        Dictionary with script content and metadata
    """
    script = get_otel_init_script()

    return {
        "script": script,
        "filename": "otel-collector-init.sh",
        "content_type": "text/x-shellscript",
        "size_bytes": len(script.encode("utf-8")),
        "version": "0.96.0",
        "description": "OpenTelemetry Collector init script for Databricks clusters",
    }
