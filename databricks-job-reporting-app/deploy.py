#!/usr/bin/env python3
"""
Automated Databricks Asset Bundle Deployment Script
Handles complete deployment pipeline from build to app deployment.
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Tuple, Optional


class DatabricksDeployer:
    def __init__(self, app_name: str, target: str = "dev", profile: str = None):
        self.app_name = app_name
        self.target = target
        self.profile = profile or os.getenv("DATABRICKS_CONFIG_PROFILE", "DEFAULT")
        self.workspace_path = None
        self.app_path = None
        self.user_email = None

    def run_command(self, command: list, check: bool = True) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout, e.stderr

    def print_section(self, title: str):
        """Print a formatted section header."""
        print()
        print("=" * 70)
        print(f" {title}")
        print("=" * 70)

    def step1_build_application(self):
        """Step 1: Build the application."""
        self.print_section("Step 1: Building application")
        exit_code, stdout, stderr = self.run_command(["python3", "build.py"])
        if exit_code != 0:
            print(f"Build failed: {stderr}")
            sys.exit(1)
        print("Application built successfully")

    def step2_validate_bundle(self):
        """Step 2: Validate bundle configuration."""
        self.print_section("Step 2: Validating bundle configuration")
        cmd = ["databricks", "bundle", "validate", "-t", self.target]
        if self.profile:
            cmd.extend(["--profile", self.profile])

        exit_code, stdout, stderr = self.run_command(cmd)
        if exit_code != 0:
            print(f"Validation failed: {stderr}")
            sys.exit(1)
        print(stdout)
        print("Bundle validation successful")

    def step3_deploy_bundle(self):
        """Step 3: Deploy the bundle."""
        self.print_section("Step 3: Deploying bundle to Databricks")
        cmd = ["databricks", "bundle", "deploy", "-t", self.target, "--force"]
        if self.profile:
            cmd.extend(["--profile", self.profile])

        exit_code, stdout, stderr = self.run_command(cmd)
        if exit_code != 0:
            print(f"Bundle deployment failed: {stderr}")
            sys.exit(1)
        print("Bundle deployed successfully")

    def step4_get_workspace_paths(self):
        """Step 4: Get workspace paths."""
        self.print_section("Step 4: Determining workspace paths")

        cmd = ["databricks", "current-user", "me", "--output", "json"]
        if self.profile:
            cmd.extend(["--profile", self.profile])

        exit_code, stdout, stderr = self.run_command(cmd)
        if exit_code != 0:
            print(f"Failed to get user info: {stderr}")
            sys.exit(1)

        user_info = json.loads(stdout)
        self.user_email = user_info.get("userName", user_info.get("user_name"))

        self.workspace_path = f"/Workspace/Users/{self.user_email}/.bundle/{self.app_name}/{self.target}"
        self.app_path = f"{self.workspace_path}/app"

        print(f"User: {self.user_email}")
        print(f"Workspace path: {self.workspace_path}")
        print(f"App path: {self.app_path}")
        print("Workspace paths determined")

    def step5_upload_app(self):
        """Step 5: Upload built app to workspace."""
        self.print_section("Step 5: Uploading built app to workspace")

        cmd = [
            "databricks", "workspace", "import-dir",
            "build/app", self.app_path,
            "--overwrite"
        ]
        if self.profile:
            cmd.extend(["--profile", self.profile])

        exit_code, stdout, stderr = self.run_command(cmd)
        if exit_code != 0:
            print(f"Upload failed: {stderr}")
            sys.exit(1)
        print(stdout)
        print("App uploaded to workspace")

    def step6_deploy_app(self):
        """Step 6: Deploy the app."""
        self.print_section("Step 6: Deploying app to Databricks Apps")

        cmd = [
            "databricks", "apps", "deploy", self.app_name,
            "--source-code-path", self.app_path
        ]
        if self.profile:
            cmd.extend(["--profile", self.profile])

        exit_code, stdout, stderr = self.run_command(cmd)
        if exit_code != 0:
            print(f"App deployment failed: {stderr}")
            sys.exit(1)

        try:
            deployment_info = json.loads(stdout)
            print(f"Deployment ID: {deployment_info.get('deployment_id')}")
            print(f"Status: {deployment_info.get('status', {}).get('state')}")
        except:
            print(stdout)
        print("App deployed successfully")

    def step7_get_app_info(self):
        """Step 7: Get and display app information."""
        self.print_section("Step 7: Getting app information")

        cmd = ["databricks", "apps", "get", self.app_name, "--output", "json"]
        if self.profile:
            cmd.extend(["--profile", self.profile])

        exit_code, stdout, stderr = self.run_command(cmd)
        if exit_code != 0:
            print(f"Failed to get app info: {stderr}")
            sys.exit(1)

        app_info = json.loads(stdout)
        app_url = app_info.get("url")
        sso_scopes = app_info.get("effective_user_api_scopes", [])

        self.print_section("Deployment Complete!")
        print(f"App Name: {self.app_name}")
        print(f"Environment: {self.target}")
        print(f"URL: {app_url}")
        print()
        print("SSO Status:")
        if sso_scopes:
            for scope in sso_scopes:
                print(f"  - {scope}")
        else:
            print("  No SSO scopes configured")
        print("=" * 70)

        return app_url

    def deploy(self):
        """Run the complete deployment pipeline."""
        print(f"Deploying {self.app_name} to Databricks ({self.target} environment)")

        try:
            self.step1_build_application()
            self.step2_validate_bundle()
            self.step3_deploy_bundle()
            self.step4_get_workspace_paths()
            self.step5_upload_app()
            self.step6_deploy_app()
            app_url = self.step7_get_app_info()

            print(f"\nApp is live at: {app_url}")

        except KeyboardInterrupt:
            print("\n\nDeployment interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\nDeployment failed: {e}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Deploy Databricks Asset Bundle")
    parser.add_argument(
        "target",
        nargs="?",
        default="dev",
        choices=["dev", "staging", "prod"],
        help="Deployment target (default: dev)"
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Databricks CLI profile to use"
    )
    parser.add_argument(
        "--app-name",
        default="job-monitor-lakebase",
        help="Application name"
    )

    args = parser.parse_args()

    deployer = DatabricksDeployer(
        app_name=args.app_name,
        target=args.target,
        profile=args.profile
    )

    deployer.deploy()


if __name__ == "__main__":
    main()
