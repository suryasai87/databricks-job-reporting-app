# Instructions for Claude Code

## Deploying This Databricks Asset Bundle

This project includes FULLY AUTOMATED deployment scripts.

### Quick Deploy (One Command!)

```bash
# Deploy to development
python deploy.py dev

# Deploy to staging
python deploy.py staging

# Deploy to production
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

## Configuration

### SQL Warehouse
The app uses **Serverless Starter Warehouse** by default:
- **Warehouse ID**: `4b28691c780d9875`

To change, update in `src/backend/app.py`:
```python
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "your-warehouse-id")
```

### Genie Space ID (AI Assistant)

To enable the AI Assistant:

1. **Create a Genie Space** in your Databricks workspace:
   - Go to AI/BI > Genie Spaces
   - Create a new space with these tables:
     - `system.lakeflow.jobs`
     - `system.lakeflow.job_run_timeline`
     - `system.lakeflow.job_task_run_timeline`
     - `system.billing.usage`
     - `system.billing.list_prices`

2. **Get the Genie Space ID** from the URL

3. **Configure the app**:
   - Option A: Update `src/backend/app.py`:
     ```python
     GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "your-genie-space-id")
     ```
   - Option B: Update in Databricks Apps UI:
     - Go to Compute > Apps > databricks-jobs-monitor
     - Settings > Environment Variables
     - Add `GENIE_SPACE_ID` with your Genie Space ID

4. **Redeploy the app**:
   ```bash
   python deploy.py dev
   ```

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

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABRICKS_HOST` | Workspace URL | `https://fe-vm-hls-amer.cloud.databricks.com` |
| `WAREHOUSE_ID` | SQL Warehouse ID | `4b28691c780d9875` |
| `GENIE_SPACE_ID` | Genie Space ID | `` (empty) |
