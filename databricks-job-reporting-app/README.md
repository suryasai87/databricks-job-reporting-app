# Databricks Jobs Monitor

A comprehensive monitoring application for Databricks jobs with AI-powered insights using Genie Spaces. Inspired by Azure Data Factory's monitoring capabilities, adapted for Databricks environments.

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
- **AI**: Databricks Genie Spaces

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
| `GENIE_SPACE_ID` | Genie Space ID for AI Assistant | `` (empty) |

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
│   │   │   ├── components/ # Shared UI components
│   │   │   ├── services/   # API services
│   │   │   ├── types/      # TypeScript types
│   │   │   └── theme/      # MUI theme
│   │   └── package.json
│   └── backend/            # FastAPI application
│       ├── app.py          # Main application
│       └── requirements.txt
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
- `cost-analytics.png`
- `health.png`
- `cluster-analysis.png`
- `ai-assistant.png`
- `reports.png`
- `settings.png`

## License

This project is licensed under the MIT License.
