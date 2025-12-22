#!/usr/bin/env python3
"""Build script for Databricks Jobs Monitor with Serverless Tags application."""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def run_command(command, cwd=None):
    """Run a shell command and handle errors."""
    print(f"  Running: {command}")
    result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Error: {result.stderr}")
        sys.exit(1)
    if result.stdout:
        print(result.stdout)
    return result.stdout


def main():
    print("=" * 70)
    print(" Building Databricks Jobs Monitor with Serverless Tags")
    print("=" * 70)

    project_root = Path(__file__).parent
    frontend_dir = project_root / "src" / "frontend"
    backend_dir = project_root / "src" / "backend"
    build_dir = project_root / "build"
    app_dir = build_dir / "app"

    # Clean and create build directory
    print("\n[1/6] Cleaning build directory...")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    app_dir.mkdir(parents=True)

    # Step 1: Install and build frontend
    print("\n[2/6] Building React frontend...")
    if not (frontend_dir / "node_modules").exists():
        run_command("npm install", cwd=frontend_dir)
    run_command("npm run build", cwd=frontend_dir)

    # Step 2: Copy backend files
    print("\n[3/6] Copying backend files...")
    shutil.copy2(backend_dir / "app.py", app_dir / "app.py")
    shutil.copy2(backend_dir / "requirements.txt", app_dir / "requirements.txt")

    # Copy additional backend modules
    for py_file in backend_dir.glob("*.py"):
        if py_file.name != "app.py":
            shutil.copy2(py_file, app_dir / py_file.name)

    # Copy collectors directory
    collectors_src = backend_dir / "collectors"
    if collectors_src.exists():
        print("  Copying collectors directory...")
        collectors_dst = app_dir / "collectors"
        shutil.copytree(collectors_src, collectors_dst)

    # Copy data directory (Lakebase data layer)
    data_src = backend_dir / "data"
    if data_src.exists():
        print("  Copying data directory (Lakebase layer)...")
        data_dst = app_dir / "data"
        shutil.copytree(data_src, data_dst)

    # Copy setup directory (Lakebase setup scripts)
    setup_src = backend_dir / "setup"
    if setup_src.exists():
        print("  Copying setup directory...")
        setup_dst = app_dir / "setup"
        shutil.copytree(setup_src, setup_dst)

    # Copy integrations directory (Unity Catalog Lineage, MLflow, Multi-Workspace)
    integrations_src = backend_dir / "integrations"
    if integrations_src.exists():
        print("  Copying integrations directory...")
        integrations_dst = app_dir / "integrations"
        shutil.copytree(integrations_src, integrations_dst)

    # Copy features directory (Custom Dashboards)
    features_src = backend_dir / "features"
    if features_src.exists():
        print("  Copying features directory...")
        features_dst = app_dir / "features"
        shutil.copytree(features_src, features_dst)

    # Copy notifications directory (Push Notifications)
    notifications_src = backend_dir / "notifications"
    if notifications_src.exists():
        print("  Copying notifications directory...")
        notifications_dst = app_dir / "notifications"
        shutil.copytree(notifications_src, notifications_dst)

    # Copy reports directory (PDF Export, Scheduled Reports)
    reports_src = backend_dir / "reports"
    if reports_src.exists():
        print("  Copying reports directory...")
        reports_dst = app_dir / "reports"
        shutil.copytree(reports_src, reports_dst)

    # Copy ml directory (Anomaly Detection)
    ml_src = backend_dir / "ml"
    if ml_src.exists():
        print("  Copying ml directory...")
        ml_dst = app_dir / "ml"
        shutil.copytree(ml_src, ml_dst)

    # Step 3: Copy frontend build to static
    print("\n[4/6] Copying frontend build to static directory...")
    static_dir = app_dir / "static"
    shutil.copytree(frontend_dir / "dist", static_dir)

    # Step 4: Create app.yaml for Databricks Apps
    print("\n[5/6] Creating app.yaml...")
    app_yaml_content = """command: ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

env:
  - name: ENV
    value: "production"
  - name: PORT
    value: "8000"
  - name: DEBUG
    value: "False"
  - name: WAREHOUSE_ID
    value: "4b28691c780d9875"
  - name: GENIE_SPACE_ID
    description: "Genie Space ID for AI Assistant"
    value: "01f0dde07de71fd3a4c0b4907fe15554"
  # Lakebase Configuration
  - name: LAKEBASE_ENABLED
    description: "Enable Lakebase for faster queries"
    value: "true"
  - name: LAKEBASE_INSTANCE_ID
    description: "Lakebase database instance ID"
    value: "6b59171b-cee8-4acc-9209-6c848ffbfbfe"
  - name: LAKEBASE_HOST
    description: "Lakebase instance DNS (from setup script)"
    value: ""
  - name: LAKEBASE_PORT
    value: "5432"
  - name: LAKEBASE_DATABASE
    value: "jobs_monitor_db"
  # Serverless Tags Configuration
  - name: SERVERLESS_TAG_CATALOG
    description: "Unity Catalog containing serverless tag tables"
    value: "main"
  - name: SERVERLESS_TAG_SCHEMA
    description: "Schema containing serverless tag correlation tables"
    value: "serverless_tagging"
"""

    with open(app_dir / "app.yaml", "w") as f:
        f.write(app_yaml_content)

    # Step 5: Create a simple index file
    print("\n[6/6] Verifying build...")

    # Verify key files exist
    required_files = [
        app_dir / "app.py",
        app_dir / "requirements.txt",
        app_dir / "app.yaml",
        app_dir / "static" / "index.html",
    ]

    missing_files = [f for f in required_files if not f.exists()]
    if missing_files:
        print(f"  Warning: Missing files: {missing_files}")
    else:
        print("  All required files present")

    print("\n" + "=" * 70)
    print(" Build Complete!")
    print("=" * 70)
    print(f"  Bundle location: {build_dir}")
    print(f"  App directory: {app_dir}")
    print(f"  app.yaml created: {app_dir / 'app.yaml'}")
    print("\n  Included Modules:")
    print("  - Lakebase data layer")
    print("  - Setup scripts")
    print("  - Integrations (Lineage, MLflow, Multi-Workspace)")
    print("  - Features (Custom Dashboards)")
    print("  - Notifications (Push Notifications)")
    print("  - Reports (PDF Export, Scheduled Reports)")
    print("  - ML (Anomaly Detection)")
    print("  - Serverless Tags (Dynamic Cost Attribution)")
    print("\nNext step: python deploy.py dev --app-name job-monitor-serverless-tags")
    print("=" * 70)


if __name__ == "__main__":
    main()
