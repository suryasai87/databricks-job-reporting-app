# Databricks Jobs Monitor

A comprehensive monitoring application for Databricks jobs with AI-powered insights using Genie Spaces. Inspired by Azure Data Factory's monitoring capabilities, adapted for Databricks environments.

## Features

### Dashboard Overview
- Real-time job run statistics (total, succeeded, failed, running)
- Success rate metrics
- Daily run trends and cost analysis
- Job distribution by run type (JOB_RUN, SUBMIT_RUN, WORKFLOW_RUN)

### Jobs List
- Searchable and filterable job runs table
- Pagination and sorting
- Status indicators with color coding
- Duration tracking and cost attribution

### Gantt View
- Visual timeline of job execution
- Overlap detection and highlighting
- Concurrent jobs analysis
- Time range selection (6h, 12h, 24h, 48h)

### Cost Analytics
- Total cost and DBU consumption
- Daily cost trends
- Top expensive jobs ranking
- Cost breakdown by identity/user

### Health & Anomalies
- **Failed Jobs**: Jobs with failure history and success rates
- **Prolonged Jobs**: Currently running jobs exceeding thresholds
- **Anomaly Detection**: Z-score based detection of unusual execution patterns
- **Retry Statistics**: Jobs with high retry rates

### Cluster Analysis
- Cluster configuration overview
- Node type distribution
- DBR version tracking
- Resource utilization insights

### AI Assistant (Genie Spaces)
- Natural language queries about job data
- Suggested questions for common analysis
- Conversation history
- Markdown-formatted responses with SQL queries

### Reports
- Performance reports
- Cost analysis reports
- Health & anomaly reports
- Executive summaries
- Scheduled report configuration

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

3. **Run backend (Terminal 1):**
   ```bash
   cd src/backend
   uvicorn app:app --reload --port 8000
   ```

4. **Run frontend (Terminal 2):**
   ```bash
   cd src/frontend
   npm run dev
   ```

5. **Access the app:**
   - Frontend: http://localhost:5173
   - API Docs: http://localhost:8000/docs

## Configuration

### Environment Variables

Set these in your environment or in `app.yaml`:

| Variable | Description |
|----------|-------------|
| `DATABRICKS_HOST` | Databricks workspace URL |
| `WAREHOUSE_ID` | SQL Warehouse ID for queries |
| `GENIE_SPACE_ID` | Genie Space ID for AI Assistant |

### databricks.yml

The main bundle configuration is in `databricks.yml`:

```yaml
bundle:
  name: databricks-jobs-monitor

workspace:
  host: https://your-workspace.cloud.databricks.com

variables:
  warehouse_id:
    description: SQL Warehouse ID for system table queries
  genie_space_id:
    description: Genie Space ID for AI Assistant
```

## Project Structure

```
databricks-job-reporting-app/
├── databricks.yml           # Asset bundle configuration
├── build.py                 # Build script
├── deploy.py                # Automated deployment script
├── requirements.txt         # Python dependencies
├── resources/
│   └── app.yml             # Databricks app resource
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
| `system.lakeflow.jobs` | Job definitions |
| `system.lakeflow.job_run_timeline` | Job run history |
| `system.lakeflow.job_task_run_timeline` | Task-level details |
| `system.billing.usage` | Cost and DBU data |
| `system.billing.list_prices` | Pricing information |

## Authentication

The app supports multiple authentication methods:

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
- `GET /api/analysis/concurrent` - Concurrent jobs

### AI Assistant
- `GET /api/genie/spaces` - List Genie Spaces
- `POST /api/genie/conversations` - Start conversation
- `POST /api/genie/conversations/{id}/messages` - Send message

## Troubleshooting

### Build Issues
- Ensure Node.js 18+ is installed: `node --version`
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`

### Deployment Issues
- Verify Databricks CLI is configured: `databricks auth env`
- Check bundle validation: `databricks bundle validate -t dev`

### Data Issues
- Ensure access to system tables
- Verify SQL Warehouse is running
- Check WAREHOUSE_ID configuration

## License

This project is licensed under the MIT License.
