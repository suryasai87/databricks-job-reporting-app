# Databricks Jobs Monitor (Lakebase-Powered)

A comprehensive monitoring application for Databricks jobs with AI-powered insights using Genie Spaces. Inspired by Azure Data Factory's monitoring capabilities, adapted for Databricks environments.

**Now powered by Databricks Lakebase for sub-100ms query performance!**

![Databricks Jobs Monitor](docs/screenshots/dashboard.png)

## Live Demo

**App URL:** https://databricks-jobs-monitor-1602460480284688.aws.databricksapps.com

## Features

### Dashboard Overview
- Real-time job run statistics (total, succeeded, failed, running)
- Success rate metrics with visual indicators
- Daily run trends with area charts
- Job distribution by run type (JOB_RUN, SUBMIT_RUN, WORKFLOW_RUN)
- Cost overview with DBU consumption

![Dashboard](docs/screenshots/dashboard.png)

### Jobs List
- Searchable and filterable job runs table
- Pagination and multi-column sorting
- Status indicators with color coding (SUCCESS, FAILED, RUNNING)
- Duration tracking and cost attribution
- Filter by status, run type, and time range

![Jobs List](docs/screenshots/jobs-list.png)

### Gantt View
- Visual timeline of job execution
- Overlap detection and highlighting
- Concurrent jobs analysis chart
- Time range selection (6h, 12h, 24h, 48h)
- Interactive zoom controls

![Gantt View](docs/screenshots/gantt-view.png)

### Matrix View (NEW)
- **Run History Grid**: Visual grid showing last N runs for each job
- **Color-coded status cells**: SUCCESS (green), FAILED (red), RUNNING (yellow), PENDING (grey)
- **Hover tooltips**: Show run details including duration, start/end times
- **Click navigation**: Navigate to run details on click
- **Search and filter**: Find specific jobs in the matrix
- **Configurable**: Adjust days and runs per job parameters

![Matrix View](docs/screenshots/matrix-view.png)

### Metrics Dashboard (NEW - 3-Tier Architecture)

The Metrics page provides a unified view of performance metrics from multiple sources:

#### Tier 1: Spark Executor Metrics (Always Available)
- **Memory usage**: Per-executor memory utilization with progress bars
- **GC time tracking**: Garbage collection time per executor
- **Shuffle I/O**: Read/write bytes for shuffle operations
- **Task counts**: Active, completed, and failed tasks per executor
- **Summary statistics**: Aggregated metrics across all executors

#### Tier 2: Cloud Metrics (If Configured)
- **Azure Monitor integration**: CPU, memory, disk, network metrics via Azure Monitor SDK
- **AWS CloudWatch integration**: Instance-level metrics via boto3
- **Auto-detection**: Automatically detects configured cloud provider
- **Instance-level details**: Metrics broken down by VM/instance

#### Tier 3: OpenTelemetry (OTEL) Metrics
- **OTEL integration**: Query metrics from Delta table (`jobs_monitor.metrics.otel_metrics`)
- **Init script generator**: Download init script for cluster configuration
- **Setup instructions**: Step-by-step guide for OTEL configuration
- **Databricks Runtime 15.4+ native support**: Automatic when using latest DBR

#### Summary Tab
- **Best available source**: Automatically uses the highest-fidelity metrics source
- **Tier availability status**: Shows which tiers are configured and active
- **Key metrics overview**: CPU, memory, I/O, tasks at a glance

![Metrics Dashboard](docs/screenshots/metrics.png)

### Task DAG Visualization (NEW)
- **SVG-based DAG rendering**: Visualize task dependencies without external libraries
- **Topological sorting**: Automatic layout using Kahn's algorithm
- **Status colors**: SUCCESS (green), FAILED (red), RUNNING (yellow), PENDING (grey)
- **Interactive selection**: Click nodes to see task details
- **Curved edges**: Smooth bezier curves connecting dependent tasks
- **Details panel**: Show task timing, duration, and error information

### SLA Tracking & Percentile Metrics (NEW)
- **SLA compliance monitoring**: Track jobs exceeding 2x their historical average duration
- **Compliance rate**: Overall percentage of runs meeting SLA
- **Violation details**: List of jobs with SLA violations and counts
- **Duration percentiles**: p50, p90, p95, p99 using PERCENTILE_CONT
- **Per-job percentiles**: Breakdown of percentile metrics by job
- **Historical analysis**: Configurable time range (7-90 days)

### Rerun/Repair Capabilities (NEW)
- **Run Now**: Trigger immediate job execution with optional parameters
- **Cancel Run**: Stop a running job execution
- **Repair Run**: Retry failed tasks or rerun all failed tasks
- **Run Output**: View notebook output and error traces for completed runs

### Cost Analytics
- Total cost and DBU consumption metrics
- Daily cost trends with bar charts
- Top 10 most expensive jobs ranking
- Cost breakdown by identity/user (pie chart)
- Customizable time range (7-90 days)

![Cost Analytics](docs/screenshots/cost-analytics.png)

### Health & Anomalies
- **Failed Jobs**: Jobs with failure history and success rates
- **Prolonged Jobs**: Currently running jobs exceeding thresholds
- **Anomaly Detection**: Z-score based detection of unusual patterns
- **Retry Statistics**: Jobs with high retry rates

![Health & Anomalies](docs/screenshots/health.png)

### Cluster Analysis
- Cluster configuration overview
- Node type distribution (driver/worker)
- DBR version tracking
- Autoscaling vs fixed cluster analysis

![Cluster Analysis](docs/screenshots/cluster-analysis.png)

### AI Assistant (Genie Spaces)
- Natural language queries about job data
- Suggested questions for common analysis
- Conversation history with markdown support
- SQL query responses with formatted tables

![AI Assistant](docs/screenshots/ai-assistant.png)

### Reports
- Performance reports generation
- Cost analysis reports
- Health & anomaly reports
- Executive summaries
- Configurable date ranges

![Reports](docs/screenshots/reports.png)

## Tech Stack

- **Frontend**: React 18, TypeScript, MUI (Material-UI), Recharts, Framer Motion
- **Backend**: FastAPI, Python 3.9+, Databricks SDK
- **Authentication**: Databricks SSO (OBO, U2M, M2M OAuth)
- **Data Source**: Databricks System Tables (system.lakeflow.*, system.billing.*)
- **Data Acceleration**: Databricks Lakebase (PostgreSQL-compatible layer)
- **AI**: Databricks Genie Spaces
- **Metrics Collection**:
  - Tier 1: Spark UI REST API (driver-proxy-api)
  - Tier 2: Azure Monitor SDK / AWS CloudWatch (boto3)
  - Tier 3: OpenTelemetry (OTEL) via Delta table

## Lakebase Integration (NEW)

Databricks Lakebase provides a **PostgreSQL-compatible layer** with synced tables for ultra-fast UI queries:

| Query Type | SQL Warehouse | Lakebase | Speedup |
|------------|---------------|----------|---------|
| Point lookups | 500-2000ms | 10-50ms | 10-40x |
| Dashboard aggregations | 2-5s | 100-300ms | 10-20x |
| Filtered lists | 1-3s | 50-150ms | 10-20x |
| Real-time refresh | Manual | ~15s continuous | N/A |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DELTA LAKE (Source of Truth)              │
│  system.lakeflow.jobs  system.lakeflow.job_run_timeline     │
└────────────────────────────┬────────────────────────────────┘
                             │ CONTINUOUS SYNC (~15s)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAKEBASE (PostgreSQL Layer)               │
│  jobs_monitor.synced.jobs  jobs_monitor.synced.job_run...   │
│  PostgreSQL Protocol  │  Low-Latency  │  Connection Pool    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              JOBS MONITOR APP (FastAPI + React)              │
│  • psycopg2 for direct PostgreSQL queries                   │
│  • Sub-100ms response times for UI interactions             │
│  • Graceful fallback to SQL Warehouse if unavailable        │
└─────────────────────────────────────────────────────────────┘
```

### Setting Up Lakebase

#### Option 1: Automated Setup (Recommended)

```bash
# Run the setup script
python -m src.backend.setup.lakebase_setup --instance-name jobs-monitor-lakebase --capacity CU_1

# Set environment variables (output by the script)
export LAKEBASE_HOST='<instance-dns>'
export LAKEBASE_ENABLED='true'
```

#### Option 2: Manual Setup via CLI

```bash
# Create Lakebase instance
databricks database create-database-instance \
  --name "jobs-monitor-lakebase" \
  --capacity "CU_1"

# Create synced tables (repeat for each table)
databricks database create-synced-table \
  --name "jobs_monitor.synced.jobs" \
  --database-instance-name "jobs-monitor-lakebase" \
  --source-table "system.lakeflow.jobs" \
  --scheduling-policy "CONTINUOUS"
```

### Environment Variables for Lakebase

| Variable | Description | Default |
|----------|-------------|---------|
| `LAKEBASE_ENABLED` | Enable Lakebase acceleration | `false` |
| `LAKEBASE_HOST` | Lakebase instance DNS | (required) |
| `LAKEBASE_PORT` | PostgreSQL port | `5432` |
| `LAKEBASE_DATABASE` | Logical database name | `jobs_monitor_db` |
| `LAKEBASE_READ_REPLICA_HOST` | Read replica for HA (optional) | |

### Synced Tables

The following tables are synced from Delta Lake to Lakebase:

| Source Table | Sync Mode | Purpose |
|--------------|-----------|---------|
| `system.lakeflow.jobs` | CONTINUOUS | Job definitions |
| `system.lakeflow.job_tasks` | CONTINUOUS | Task definitions |
| `system.lakeflow.job_run_timeline` | CONTINUOUS | Run history |
| `system.lakeflow.job_task_run_timeline` | CONTINUOUS | Task run details |
| `system.billing.usage` | TRIGGERED | Billing data |
| `system.billing.list_prices` | TRIGGERED | Pricing info |
| `system.compute.clusters` | CONTINUOUS | Cluster metadata |

### Checking Lakebase Status

```bash
# Check sync status
python -m src.backend.setup.lakebase_setup --check-status

# API endpoint
curl https://your-app-url/api/data-source/health
```

### Performance Comparison API

Compare Lakebase vs SQL Warehouse performance:

```bash
curl https://your-app-url/api/data-source/performance
```

Response:
```json
{
  "lakebase_ms": 45.2,
  "sql_warehouse_ms": 1250.8,
  "speedup_factor": 27.7
}
```

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- Databricks CLI configured: `databricks configure --token`
- Access to Databricks workspace with System Tables

### One-Command Deployment

```bash
# Deploy to development environment
python deploy.py dev

# Deploy to staging
python deploy.py staging

# Deploy to production
python deploy.py prod
```

The deployment script automatically:
1. Builds the React frontend
2. Creates app.yaml configuration
3. Validates bundle configuration
4. Deploys bundle to Databricks
5. Uploads built app to workspace
6. Deploys app to Databricks Apps
7. Shows the app URL and SSO status

### Local Development

1. **Install frontend dependencies:**
   ```bash
   cd src/frontend
   npm install
   ```

2. **Install backend dependencies:**
   ```bash
   cd src/backend
   pip install -r requirements.txt
   ```

3. **Set environment variables:**
   ```bash
   export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
   export WAREHOUSE_ID="your-warehouse-id"
   export GENIE_SPACE_ID="your-genie-space-id"  # Optional
   ```

4. **Run backend (Terminal 1):**
   ```bash
   cd src/backend
   uvicorn app:app --reload --port 8000
   ```

5. **Run frontend (Terminal 2):**
   ```bash
   cd src/frontend
   npm run dev
   ```

6. **Access the app:**
   - Frontend: http://localhost:5173
   - API Docs: http://localhost:8000/docs

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABRICKS_HOST` | Databricks workspace URL | `https://fe-vm-hls-amer.cloud.databricks.com` |
| `WAREHOUSE_ID` | SQL Warehouse ID for queries | `4b28691c780d9875` |
| `GENIE_SPACE_ID` | Genie Space ID for AI Assistant | `01f0dde07de71fd3a4c0b4907fe15554` |

### Cloud Metrics Configuration (Tier 2)

#### Azure Monitor
```bash
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_MONITOR_WORKSPACE_ID="your-log-analytics-workspace-id"
```

#### AWS CloudWatch
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

### OTEL Configuration (Tier 3)

For clusters running Databricks Runtime 15.4+, OTEL metrics are collected natively.

For older runtimes, download and configure the init script:
1. Navigate to Metrics > OTEL tab
2. Click "Download Init Script"
3. Upload to DBFS or Workspace
4. Configure cluster to use the init script

### Configuring the SQL Warehouse

The app uses Databricks SQL Warehouse to query system tables. The default configuration uses:
- **Warehouse ID**: `4b28691c780d9875` (Serverless Starter Warehouse)

To change the warehouse:

1. **In code** - Update `src/backend/app.py`:
   ```python
   WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "your-warehouse-id")
   ```

2. **In deployment** - Update `build.py` app.yaml section:
   ```yaml
   env:
     - name: WAREHOUSE_ID
       value: "your-warehouse-id"
   ```

3. **In Databricks Apps UI**:
   - Go to your app settings
   - Add/update the `WAREHOUSE_ID` environment variable

## Setting Up AI Assistant (Genie Spaces)

The AI Assistant feature uses Databricks Genie Spaces to enable natural language queries about your job data.

### Step 1: Create a Genie Space

1. Navigate to your Databricks workspace
2. Go to **AI/BI** > **Genie Spaces**
3. Click **Create Genie Space**
4. Configure the Genie Space:
   - **Name**: "Jobs Monitor Assistant" (or your preferred name)
   - **Description**: "AI assistant for Databricks jobs monitoring"
   - **SQL Warehouse**: Select your SQL warehouse
   - **Tables**: Add the following system tables:
     - `system.lakeflow.jobs`
     - `system.lakeflow.job_run_timeline`
     - `system.lakeflow.job_task_run_timeline`
     - `system.billing.usage`
     - `system.billing.list_prices`

5. Add sample instructions for the Genie:
   ```
   You are an AI assistant that helps users analyze Databricks job execution data.
   You can answer questions about:
   - Job run statistics and success rates
   - Cost analysis and DBU consumption
   - Failed jobs and error patterns
   - Long-running jobs and anomalies
   - Job scheduling and overlaps
   ```

6. Click **Save** and note the **Genie Space ID** from the URL

### Step 2: Configure the App with Genie Space ID

#### Option A: Update in Code (Recommended for Development)

1. Edit `src/backend/app.py`:
   ```python
   GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "your-genie-space-id")
   ```

2. Edit `build.py` to update app.yaml:
   ```python
   app_yaml_content = """...
   env:
     - name: GENIE_SPACE_ID
       value: "your-genie-space-id"
   """
   ```

3. Rebuild and redeploy:
   ```bash
   python deploy.py dev
   ```

#### Option B: Configure in Databricks Apps UI (Recommended for Production)

1. Navigate to your Databricks workspace
2. Go to **Compute** > **Apps**
3. Click on **databricks-jobs-monitor**
4. Go to **Settings** > **Environment Variables**
5. Add or update:
   - **Name**: `GENIE_SPACE_ID`
   - **Value**: `your-genie-space-id`
6. Click **Save** and redeploy the app

### Step 3: Verify Genie Space Integration

1. Open the app and navigate to **AI Assistant**
2. Select your Genie Space from the dropdown
3. Try asking a question like:
   - "What are the top 5 most expensive jobs?"
   - "Show me failed jobs from the last 7 days"
   - "What is the success rate by job type?"

### Genie Space Permissions

Ensure the Genie Space has access to:
- System tables (`system.lakeflow.*`, `system.billing.*`)
- The SQL Warehouse specified in your configuration
- Users who will be using the AI Assistant

## Project Structure

```
databricks-job-reporting-app/
├── databricks.yml           # Asset bundle configuration
├── build.py                 # Build script
├── deploy.py                # Automated deployment script
├── requirements.txt         # Python dependencies
├── resources/
│   └── app.yml             # Databricks app resource
├── docs/
│   └── screenshots/        # App screenshots
├── src/
│   ├── frontend/           # React application
│   │   ├── src/
│   │   │   ├── pages/      # Page components
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── JobsList.tsx
│   │   │   │   ├── GanttView.tsx
│   │   │   │   ├── MatrixView.tsx    # NEW: Run history grid
│   │   │   │   ├── Metrics.tsx       # NEW: 3-tier metrics
│   │   │   │   ├── CostAnalytics.tsx
│   │   │   │   ├── Health.tsx
│   │   │   │   ├── ClusterAnalysis.tsx
│   │   │   │   ├── AIAssistant.tsx
│   │   │   │   ├── Reports.tsx
│   │   │   │   └── Settings.tsx
│   │   │   ├── components/ # Shared UI components
│   │   │   │   ├── TaskDAG.tsx       # NEW: DAG visualization
│   │   │   │   └── TaskDetails.tsx   # NEW: Task detail panel
│   │   │   ├── services/   # API services
│   │   │   ├── types/      # TypeScript types
│   │   │   └── theme/      # MUI theme
│   │   └── package.json
│   └── backend/            # FastAPI application
│       ├── app.py          # Main application
│       ├── requirements.txt
│       └── collectors/     # NEW: Metrics collectors
│           ├── __init__.py
│           ├── spark_ui_collector.py      # Tier 1: Spark UI
│           ├── azure_monitor_collector.py # Tier 2: Azure
│           ├── cloudwatch_collector.py    # Tier 2: AWS
│           ├── otel_collector.py          # Tier 3: OTEL
│           └── otel_init_script.py        # OTEL init script
└── build/                  # Build output (generated)
    └── app/                # Deployment package
```

## System Tables Used

| Table | Purpose |
|-------|---------|
| `system.lakeflow.jobs` | Job definitions and metadata |
| `system.lakeflow.job_run_timeline` | Job run history and execution details |
| `system.lakeflow.job_task_run_timeline` | Task-level execution details |
| `system.billing.usage` | Cost and DBU consumption data |
| `system.billing.list_prices` | Pricing information for cost calculations |

## Authentication

The app supports multiple Databricks SSO authentication methods:

1. **OBO (On-Behalf-Of)**: Via `x-forwarded-email` header
2. **U2M OAuth**: Via `x-forwarded-access-token` header
3. **Cookie-based**: Via `_databricks_auth` cookie
4. **M2M OAuth**: Using Databricks SDK (fallback)

Check authentication status at `/api/auth/status`.

## API Endpoints

### Jobs
- `GET /api/jobs/runs` - List job runs
- `GET /api/jobs/summary` - Run summary statistics
- `GET /api/jobs/by-type` - Runs grouped by type
- `GET /api/jobs/daily` - Daily run counts
- `GET /api/jobs/matrix` - Matrix view data (NEW)
- `GET /api/jobs/sla-status` - SLA compliance status (NEW)
- `GET /api/jobs/duration-percentiles` - Duration percentiles (NEW)

### Job Actions (NEW)
- `POST /api/jobs/{job_id}/run-now` - Trigger job run immediately
- `POST /api/jobs/runs/{run_id}/cancel` - Cancel a running job
- `POST /api/jobs/runs/{run_id}/repair` - Repair/retry failed run
- `GET /api/jobs/runs/{run_id}/output` - Get run output/logs

### Costs
- `GET /api/costs/summary` - Cost summary
- `GET /api/costs/daily` - Daily costs
- `GET /api/costs/top-jobs` - Top expensive jobs
- `GET /api/costs/by-identity` - Cost by user

### Health
- `GET /api/health/failed-jobs` - Failed job statistics
- `GET /api/health/prolonged-jobs` - Long-running jobs
- `GET /api/health/anomalies` - Detected anomalies
- `GET /api/health/retry-stats` - Retry statistics

### Metrics (NEW - 3-Tier Architecture)
- `GET /api/metrics/executors` - Tier 1: Spark executor metrics
- `GET /api/metrics/cloud` - Tier 2: Cloud metrics (Azure/AWS)
- `GET /api/metrics/otel/status` - Tier 3: OTEL status
- `GET /api/metrics/summary` - Best available metrics summary

### OTEL (NEW)
- `GET /api/otel/status` - OTEL integration status
- `GET /api/otel/metrics` - Query OTEL metrics from Delta table
- `GET /api/otel/spark-metrics` - Spark-specific OTEL metrics
- `GET /api/otel/cluster-summary/{cluster_id}` - Cluster metrics summary
- `GET /api/otel/init-script` - Get OTEL init script info
- `GET /api/otel/init-script/download` - Download init script
- `GET /api/otel/init-script/minimal` - Minimal init script version

### Analysis
- `GET /api/clusters/configs` - Cluster configurations
- `GET /api/analysis/overlaps` - Job overlaps
- `GET /api/analysis/concurrent` - Concurrent jobs over time

### AI Assistant (Genie)
- `GET /api/genie/spaces` - List available Genie Spaces
- `POST /api/genie/conversations` - Start a new conversation
- `POST /api/genie/conversations/{id}/messages` - Send message and get response

## Troubleshooting

### Build Issues
- Ensure Node.js 18+ is installed: `node --version`
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`

### Deployment Issues
- Verify Databricks CLI is configured: `databricks auth env`
- Check bundle validation: `databricks bundle validate -t dev`

### Data Issues
- Ensure access to system tables (requires Unity Catalog)
- Verify SQL Warehouse is running
- Check WAREHOUSE_ID configuration

### AI Assistant Issues
- Verify Genie Space ID is correctly configured
- Ensure Genie Space has access to required tables
- Check that the SQL Warehouse is running

### Metrics Collection Issues
- **Tier 1 (Spark UI)**: Requires active Spark cluster with driver-proxy-api
- **Tier 2 (Cloud)**: Check Azure/AWS credentials and permissions
- **Tier 3 (OTEL)**: Verify Delta table exists and init script is configured

## Screenshots

To take screenshots of the app:

1. Open the app URL in your browser
2. Navigate to each tab
3. Use your OS screenshot tool or browser dev tools
4. Save screenshots to `docs/screenshots/`

Screenshot naming convention:
- `dashboard.png`
- `jobs-list.png`
- `gantt-view.png`
- `matrix-view.png` (NEW)
- `metrics.png` (NEW)
- `cost-analytics.png`
- `health.png`
- `cluster-analysis.png`
- `ai-assistant.png`
- `reports.png`
- `settings.png`

## Changelog

### v2.0.0 (Latest) - Lakebase-Powered
- **Lakebase Integration**: 10-40x faster queries with PostgreSQL-compatible layer
- **Dual-Mode Data Access**: Automatic fallback from Lakebase to SQL Warehouse
- **Circuit Breaker**: Resilient error handling with automatic recovery
- **Connection Pooling**: Efficient connection management for concurrent users
- **HA Support**: Read replica support for high availability
- **Setup Automation**: One-command Lakebase setup script
- **Health Monitoring**: Data source health and performance comparison APIs

### v1.1.0
- **Matrix View**: Added run history grid with color-coded status cells
- **Metrics Dashboard**: 3-tier architecture (Spark UI, Cloud, OTEL)
- **Task DAG**: SVG-based visualization of task dependencies
- **SLA Tracking**: Compliance monitoring with percentile metrics
- **Rerun/Repair**: Job execution control via REST API
- **OTEL Integration**: OpenTelemetry metrics collection and init scripts
- **Cloud Metrics**: Azure Monitor and AWS CloudWatch support

### v1.0.0
- Initial release with Dashboard, Jobs List, Gantt View
- Cost Analytics and Health monitoring
- AI Assistant with Genie Spaces integration
- Databricks SSO authentication

## License

This project is licensed under the MIT License.
