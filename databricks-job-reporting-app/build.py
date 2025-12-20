#!/usr/bin/env python3
"""Build script for Databricks Jobs Monitor application."""

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
    print(" Building Databricks Jobs Monitor")
    print("=" * 70)

    project_root = Path(__file__).parent
    frontend_dir = project_root / "src" / "frontend"
    backend_dir = project_root / "src" / "backend"
    build_dir = project_root / "build"
    app_dir = build_dir / "app"

    # Clean and create build directory
    print("\n[1/5] Cleaning build directory...")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    app_dir.mkdir(parents=True)

    # Step 1: Install and build frontend
    print("\n[2/5] Building React frontend...")
    if not (frontend_dir / "node_modules").exists():
        run_command("npm install", cwd=frontend_dir)
    run_command("npm run build", cwd=frontend_dir)

    # Step 2: Copy backend files
    print("\n[3/5] Copying backend files...")
    shutil.copy2(backend_dir / "app.py", app_dir / "app.py")
    shutil.copy2(backend_dir / "requirements.txt", app_dir / "requirements.txt")

    # Copy additional backend modules
    for py_file in backend_dir.glob("*.py"):
        if py_file.name != "app.py":
            shutil.copy2(py_file, app_dir / py_file.name)

    # Step 3: Copy frontend build to static
    print("\n[4/5] Copying frontend build to static directory...")
    static_dir = app_dir / "static"
    shutil.copytree(frontend_dir / "dist", static_dir)

    # Step 4: Create app.yaml for Databricks Apps
    print("\n[5/5] Creating app.yaml...")
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
    description: "Genie Space ID for AI Assistant - configure in Databricks Apps settings"
    value: ""
"""

    with open(app_dir / "app.yaml", "w") as f:
        f.write(app_yaml_content)

    print("\n" + "=" * 70)
    print(" Build Complete!")
    print("=" * 70)
    print(f"  Bundle location: {build_dir}")
    print(f"  App directory: {app_dir}")
    print(f"  app.yaml created: {app_dir / 'app.yaml'}")
    print("\nNext step: python deploy.py dev")
    print("=" * 70)


if __name__ == "__main__":
    main()
