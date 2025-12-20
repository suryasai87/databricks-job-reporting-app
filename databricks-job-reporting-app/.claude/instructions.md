# Instructions for Claude Code

## Deploying This Databricks Asset Bundle

This project includes FULLY AUTOMATED deployment scripts.

### Quick Deploy (One Command!)

Deploy to development:
```bash
python deploy.py dev
```

Deploy to staging:
```bash
python deploy.py staging
```

Deploy to production:
```bash
python deploy.py prod
```

### What the Scripts Do

The deployment is FULLY AUTOMATED:
1. Builds the React frontend
2. Creates app.yaml configuration
3. Validates bundle configuration
4. Deploys bundle to Databricks
5. Uploads built app to workspace
6. Deploys app to Databricks Apps
7. Shows the app URL and SSO status

### Prerequisites
- Databricks CLI installed: `pip install databricks-cli`
- Databricks CLI configured: `databricks configure --token`
- Node.js 18+ and npm installed
- Python 3.9+

### SSO Configuration
The app automatically detects and uses the appropriate authentication method.
Check authentication status at: `/api/auth/status`

### NO MANUAL STEPS REQUIRED!
Everything is automated in the deployment script.

## Project Structure

- `src/frontend/` - React application with TypeScript, MUI, and Recharts
- `src/backend/` - FastAPI application with SSO and Genie integration
- `databricks.yml` - Asset bundle configuration
- `build.py` - Build script
- `deploy.py` - Automated deployment script

## Local Development

1. Start backend: `cd src/backend && uvicorn app:app --reload --port 8000`
2. Start frontend: `cd src/frontend && npm run dev`
3. Access: http://localhost:5173

## Key Features

- **Dashboard**: Overview metrics and charts
- **Jobs List**: Searchable, filterable job runs
- **Gantt View**: Timeline with overlap detection
- **Cost Analytics**: Expense tracking and attribution
- **Health**: Failed jobs, anomalies, prolonged runs
- **AI Assistant**: Genie Spaces natural language queries
- **Reports**: Generate comprehensive reports

## Configuration

Set these in `databricks.yml` or environment:
- `WAREHOUSE_ID`: SQL Warehouse for system table queries
- `GENIE_SPACE_ID`: Genie Space for AI assistant
