# Deployment Guide - Databricks Jobs Monitor with Serverless Tags

This document provides step-by-step instructions for deploying the Databricks Jobs Monitor with Serverless Tags integration.

## Prerequisites

1. **Databricks CLI** installed and configured
2. **Node.js 18+** for frontend builds
3. **Python 3.9+** for backend
4. Access to a Databricks workspace with:
   - Unity Catalog enabled
   - SQL Warehouse access
   - Databricks Apps enabled

## App Information

| Property | Value |
|----------|-------|
| **App Name** | job-monitor-serverless-tags |
| **App URL** | https://job-monitor-serverless-tags-1602460480284688.aws.databricksapps.com |
| **Service Principal Client ID** | b9c515e9-e5f0-436b-9b41-c31914dfcf90 |
| **Service Principal Name** | app-46a7gs job-monitor-serverless-tags |

## Configuration Variables

The following environment variables are configured for the app:

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `WAREHOUSE_ID` | SQL Warehouse ID for system table queries | `4b28691c780d9875` |
| `GENIE_SPACE_ID` | Genie Space ID for AI Assistant | `01f0dde07de71fd3a4c0b4907fe15554` |
| `LAKEBASE_INSTANCE_ID` | Lakebase database instance ID | `6b59171b-cee8-4acc-9209-6c848ffbfbfe` |
| `SERVERLESS_TAG_CATALOG` | Unity Catalog for serverless tag tables | `main` |
| `SERVERLESS_TAG_SCHEMA` | Schema for serverless tag tables | `serverless_tagging` |

## Required Permissions

### For the App Service Principal

Grant the following permissions to the service principal (`b9c515e9-e5f0-436b-9b41-c31914dfcf90`):

1. **Lakebase Database Instance** (`6b59171b-cee8-4acc-9209-6c848ffbfbfe`):
   ```sql
   -- Grant access to Lakebase instance (via Databricks UI or API)
   ```

2. **Unity Catalog Tables**:
   ```sql
   -- System tables access (usually granted by default for workspace users)
   GRANT USAGE ON CATALOG system TO `app-46a7gs job-monitor-serverless-tags`;
   GRANT SELECT ON system.lakeflow.job_run_timeline TO `app-46a7gs job-monitor-serverless-tags`;
   GRANT SELECT ON system.lakeflow.jobs TO `app-46a7gs job-monitor-serverless-tags`;
   GRANT SELECT ON system.billing.usage TO `app-46a7gs job-monitor-serverless-tags`;
   GRANT SELECT ON system.billing.list_prices TO `app-46a7gs job-monitor-serverless-tags`;

   -- Serverless Tags tables
   GRANT USAGE ON CATALOG main TO `app-46a7gs job-monitor-serverless-tags`;
   GRANT USAGE ON SCHEMA main.serverless_tagging TO `app-46a7gs job-monitor-serverless-tags`;
   GRANT SELECT ON main.serverless_tagging.serverless_tag_correlation TO `app-46a7gs job-monitor-serverless-tags`;
   GRANT SELECT ON main.serverless_tagging.tag_policy_definitions TO `app-46a7gs job-monitor-serverless-tags`;
   ```

3. **SQL Warehouse Access**:
   ```sql
   -- Grant CAN_USE on the SQL Warehouse (done via app resource configuration)
   ```

## Setting Up Serverless Tags Infrastructure

If the serverless tags tables don't exist, create them:

```sql
-- Create schema
CREATE SCHEMA IF NOT EXISTS main.serverless_tagging;

-- Create tag correlation table
CREATE TABLE IF NOT EXISTS main.serverless_tagging.serverless_tag_correlation (
    job_id STRING,
    job_run_id STRING,
    notebook_path STRING,
    workspace_id STRING,
    cluster_id STRING,

    -- ADF Context
    adf_pipeline_name STRING,
    adf_pipeline_id STRING,
    adf_run_id STRING,
    adf_activity_name STRING,
    adf_trigger_name STRING,
    adf_trigger_time TIMESTAMP,

    -- Cost Tags
    project_code STRING,
    cost_center STRING,
    department STRING,
    business_unit STRING,
    environment STRING,
    application_name STRING,
    owner_email STRING,

    -- Custom Tags
    custom_tags MAP<STRING, STRING>,

    -- Execution Metadata
    run_start_time TIMESTAMP,
    run_end_time TIMESTAMP,
    run_status STRING,

    -- Audit
    created_by STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
USING DELTA
PARTITIONED BY (DATE(run_start_time))
CLUSTER BY (project_code, department, workspace_id);

-- Create tag policy table
CREATE TABLE IF NOT EXISTS main.serverless_tagging.tag_policy_definitions (
    tag_key STRING,
    tag_display_name STRING,
    tag_description STRING,
    tag_category STRING,
    is_required BOOLEAN,
    allowed_values ARRAY<STRING>,
    validation_regex STRING,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
USING DELTA;

-- Insert default tag policies
INSERT INTO main.serverless_tagging.tag_policy_definitions VALUES
    ('project_code', 'Project Code', 'Unique project identifier for cost allocation', 'cost', true, null, '^PROJ-[0-9]{3,6}$', true, current_timestamp(), current_timestamp()),
    ('department', 'Department', 'Business department owning the workload', 'organization', true, ARRAY('Data Engineering', 'ML Platform', 'Data Science', 'BI', 'Analytics'), null, true, current_timestamp(), current_timestamp()),
    ('business_unit', 'Business Unit', 'High-level business unit', 'organization', false, ARRAY('Analytics', 'AI', 'Operations', 'Finance'), null, true, current_timestamp(), current_timestamp()),
    ('environment', 'Environment', 'Deployment environment', 'infrastructure', true, ARRAY('dev', 'staging', 'prod'), null, true, current_timestamp(), current_timestamp()),
    ('cost_center', 'Cost Center', 'Financial cost center code', 'cost', false, null, '^CC-[0-9]{3}$', true, current_timestamp(), current_timestamp()),
    ('application_name', 'Application Name', 'Name of the application or pipeline', 'application', false, null, null, true, current_timestamp(), current_timestamp()),
    ('owner_email', 'Owner Email', 'Email of the workload owner', 'ownership', true, null, '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$', true, current_timestamp(), current_timestamp());
```

## Deployment Steps

### 1. Clone the Repository

```bash
git clone https://github.com/suryasai87/databricks-job-reporting-app.git
cd databricks-job-reporting-app
git checkout including_serverless_tags
```

### 2. Build the Application

```bash
python3 build.py
```

This will:
- Build the React frontend
- Copy backend files
- Create the app.yaml configuration
- Package everything in the `build/app` directory

### 3. Deploy to Databricks

```bash
python3 deploy.py dev --app-name job-monitor-serverless-tags
```

Or use the manual deployment steps:

```bash
# Validate bundle
databricks bundle validate -t dev

# Deploy bundle
databricks bundle deploy -t dev --force

# Upload app files
databricks workspace import-dir build/app \
    /Workspace/Users/YOUR_EMAIL/.bundle/job-monitor-serverless-tags/dev/app \
    --overwrite

# Start the app compute
databricks apps start job-monitor-serverless-tags

# Deploy the app
databricks apps deploy job-monitor-serverless-tags \
    --source-code-path /Workspace/Users/YOUR_EMAIL/.bundle/job-monitor-serverless-tags/dev/app
```

### 4. Verify Deployment

```bash
# Check app status
databricks apps get job-monitor-serverless-tags

# View app URL
databricks apps get job-monitor-serverless-tags --output json | jq -r '.url'
```

## Serverless Tags Feature

The Serverless Tags feature provides:

### 1. Cost Attribution Dashboard
- **Cost by Department**: Pie chart showing cost distribution across departments
- **Cost by Project**: Bar chart of top projects by cost
- **Detailed Table**: Full breakdown with project, department, environment, and correlation quality

### 2. Cost Trends Analysis
- **Weekly Trends**: Area chart showing tagged vs untagged costs over time
- **Correlation Rate Tracking**: Line chart showing tag correlation improvement
- **Week-over-Week Variance**: Bar chart showing cost changes between weeks

### 3. Unmatched Runs Detection
- **Identify Gaps**: List runs that lack tag correlations
- **Cost Impact**: Show estimated cost of unattributed runs
- **Remediation Support**: Help teams improve tag coverage

### 4. Tag Policy Management
- **Policy Definitions**: View required and optional tags
- **Validation Rules**: Regex patterns and allowed values
- **Category Organization**: Tags grouped by cost, organization, infrastructure, etc.

## API Endpoints

The following API endpoints are available for serverless tags:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/serverless-tags/summary` | GET | Tag correlation summary and metrics |
| `/api/serverless-tags/cost-by-tags` | GET | Costs grouped by project/department |
| `/api/serverless-tags/cost-trends` | GET | Weekly cost trends with variance |
| `/api/serverless-tags/unmatched-runs` | GET | Runs without tag correlations |
| `/api/serverless-tags/policies` | GET | Tag policy definitions |

## Troubleshooting

### App shows "UNAVAILABLE" status
- Ensure the compute is started: `databricks apps start job-monitor-serverless-tags`
- Check deployment status: `databricks apps list-deployments job-monitor-serverless-tags`

### Tables not found
- Verify the service principal has access to Unity Catalog tables
- Check the `SERVERLESS_TAG_CATALOG` and `SERVERLESS_TAG_SCHEMA` environment variables

### Mock data displayed
- The app falls back to mock data when database tables are not accessible
- Grant the required permissions to the service principal

## Support

For issues or feature requests, please open an issue at:
https://github.com/suryasai87/databricks-job-reporting-app/issues
