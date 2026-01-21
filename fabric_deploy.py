"""
Microsoft Fabric Deployment Manager
Copies Fabric items from Dev workspace (GitHub) to Prod workspace

Workflow:
1. Authenticate with Azure Service Principal
2. Verify access to both workspaces
3. Clone GitHub repository (Development folder)
4. Parse Fabric items from cloned repository
5. Deploy items to Production workspace
6. Generate deployment report

Usage:
    python fabric_deploy.py

Environment Variables (required in .env):
    TENANT_ID_ENV: Azure Tenant ID
    CLIENT_ID_ENV: Service Principal Client ID
    CLIENT_SECRET_ENV: Service Principal Client Secret
    CAPACITY_ID_ENV: Fabric Capacity ID
    DEV_WORKSPACE_NAME: Dev workspace name (e.g., Nasif-Dev)
    PROD_WORKSPACE_NAME: Prod workspace name (e.g., Nasif-Prod)
    DEV_WORKSPACE_ID: Dev workspace ID
    PROD_WORKSPACE_ID: Prod workspace ID
    SKIP_ROLE_ASSIGNMENT: Skip role assignment (true/false)
    GITHUB_REPO_PATH: GitHub repository URL
    GITHUB_BRANCH: GitHub branch (default: Dev-Branch)
"""

import os
import sys
import json
import base64
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Third-party imports
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
import requests

# Load environment variables from .env file
load_dotenv()


class Logger:
    """Centralized logging with colored output"""
    
    COLORS = {
        'SUCCESS': '\033[92m',      # Green
        'ERROR': '\033[91m',        # Red
        'WARNING': '\033[93m',      # Yellow
        'INFO': '\033[94m',         # Blue
        'HEADER': '\033[95m',       # Magenta
        'END': '\033[0m'            # Reset
    }
    
    @staticmethod
    def success(message: str) -> None:
        """Log success message"""
        print(f"{Logger.COLORS['SUCCESS']}[✓] {message}{Logger.COLORS['END']}")
    
    @staticmethod
    def error(message: str) -> None:
        """Log error message"""
        print(f"{Logger.COLORS['ERROR']}[✗] {message}{Logger.COLORS['END']}")
    
    @staticmethod
    def warning(message: str) -> None:
        """Log warning message"""
        print(f"{Logger.COLORS['WARNING']}[⚠] {message}{Logger.COLORS['END']}")
    
    @staticmethod
    def info(message: str) -> None:
        """Log info message"""
        print(f"{Logger.COLORS['INFO']}[→] {message}{Logger.COLORS['END']}")
    
    @staticmethod
    def section(title: str) -> None:
        """Log section header"""
        width = 70
        print(f"\n{Logger.COLORS['HEADER']}")
        print("=" * width)
        print(f"  {title}")
        print("=" * width)
        print(f"{Logger.COLORS['END']}\n")
    
    @staticmethod
    def step(step_num: int, total: int, title: str) -> None:
        """Log step number"""
        print(f"{Logger.COLORS['HEADER']}[STEP {step_num}/{total}] {title}{Logger.COLORS['END']}")


class FabricDeploymentManager:
    """Orchestrates deployment of Fabric items from GitHub to production workspace"""
    
    # ======================== INITIALIZATION ========================
    
    def __init__(self):
        """Initialize deployment manager with configuration"""
        Logger.section("FABRIC DEPLOYMENT MANAGER - INITIALIZATION")
        
        # Load configuration from environment variables
        self._load_config()
        
        # Initialize state
        self.access_token = None
        self.temp_repo_path = "temp_fabric_repo"
        self.dev_items: List[Dict] = []
        self.deployment_results = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "failed_items": []
        }
        
        Logger.success("Deployment manager initialized")
    
    def _load_config(self) -> None:
        """Load and validate configuration from environment variables"""
        Logger.info("Loading configuration from environment variables...")
        
        self.tenant_id = os.getenv('TENANT_ID_ENV')
        self.client_id = os.getenv('CLIENT_ID_ENV')
        self.client_secret = os.getenv('CLIENT_SECRET_ENV')
        self.capacity_id = os.getenv('CAPACITY_ID_ENV')
        
        self.dev_workspace_name = os.getenv('DEV_WORKSPACE_NAME', 'Nasif-Dev')
        self.prod_workspace_name = os.getenv('PROD_WORKSPACE_NAME', 'Nasif-Prod')
        self.dev_workspace_id = os.getenv('DEV_WORKSPACE_ID')
        self.prod_workspace_id = os.getenv('PROD_WORKSPACE_ID')
        
        self.skip_role_assignment = os.getenv('SKIP_ROLE_ASSIGNMENT', 'false').lower() == 'true'
        self.github_repo_path = os.getenv('GITHUB_REPO_PATH', 'https://github.com/Nasif-Azam/Nasif-Dev')
        self.github_branch = os.getenv('GITHUB_BRANCH', 'Dev-Branch')
        
        # API endpoint
        self.fabric_api_url = "https://api.fabric.microsoft.com/v1"
        
        # Validate required variables
        required_vars = {
            'TENANT_ID_ENV': self.tenant_id,
            'CLIENT_ID_ENV': self.client_id,
            'CLIENT_SECRET_ENV': self.client_secret,
            'CAPACITY_ID_ENV': self.capacity_id,
            'DEV_WORKSPACE_ID': self.dev_workspace_id,
            'PROD_WORKSPACE_ID': self.prod_workspace_id,
        }
        
        missing = [k for k, v in required_vars.items() if not v]
        if missing:
            Logger.error(f"Missing required environment variables: {missing}")
            raise ValueError(f"Missing configuration: {missing}")
        
        Logger.success("Configuration loaded and validated")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with Bearer token"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    # ======================== STEP 1: AUTHENTICATION ========================
    
    def step_1_authenticate(self) -> bool:
        """
        STEP 1: Authenticate with Azure using Service Principal credentials
        
        Returns:
            bool: True if authentication successful
        """
        Logger.step(1, 6, "AUTHENTICATE WITH AZURE")
        
        try:
            Logger.info("Generating access token using Service Principal...")
            
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            token_response = credential.get_token("https://api.fabric.microsoft.com/.default")
            self.access_token = token_response.token
            
            Logger.success(f"Access token generated successfully")
            Logger.success(f"Token expires at: {token_response.expires_on}")
            
            return True
        
        except Exception as e:
            Logger.error(f"Authentication failed: {e}")
            return False
    
    # ======================== STEP 2: VERIFY WORKSPACE ACCESS ========================
    
    def step_2_verify_workspace_access(self) -> bool:
        """
        STEP 2: Verify access to both Dev and Prod workspaces
        
        Returns:
            bool: True if access verified to both workspaces
        """
        Logger.step(2, 6, "VERIFY WORKSPACE ACCESS")
        
        # Verify Dev workspace access
        Logger.info(f"Verifying access to Dev workspace: {self.dev_workspace_name}...")
        if not self._verify_workspace(self.dev_workspace_id, self.dev_workspace_name):
            Logger.error("Cannot access Dev workspace")
            return False
        
        Logger.success(f"Dev workspace accessible: {self.dev_workspace_name}")
        
        # Verify Prod workspace access
        Logger.info(f"Verifying access to Prod workspace: {self.prod_workspace_name}...")
        if not self._verify_workspace(self.prod_workspace_id, self.prod_workspace_name):
            Logger.error("Cannot access Prod workspace")
            return False
        
        Logger.success(f"Prod workspace accessible: {self.prod_workspace_name}")
        
        # Assign role to Prod workspace if needed
        Logger.info(f"Assigning Admin role to Prod workspace...")
        if not self._assign_workspace_role(self.prod_workspace_id):
            Logger.warning("Could not auto-assign role (may need manual assignment)")
        
        return True
    
    def _verify_workspace(self, workspace_id: str, workspace_name: str) -> bool:
        """Verify access to a specific workspace"""
        try:
            url = f"{self.fabric_api_url}/workspaces/{workspace_id}"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                ws = response.json()
                Logger.info(f"  → {ws.get('displayName', workspace_name)} (accessible)")
                return True
            elif response.status_code == 401:
                Logger.error("Unauthorized - check Azure credentials")
                return False
            elif response.status_code == 403:
                Logger.warning("Forbidden - Service Principal may not be assigned to workspace")
                return False
            else:
                Logger.error(f"Workspace check failed: {response.status_code}")
                return False
        
        except Exception as e:
            Logger.error(f"Workspace verification error: {e}")
            return False
    
    def _assign_workspace_role(self, workspace_id: str) -> bool:
        """Assign Admin role to Service Principal in workspace"""
        if self.skip_role_assignment:
            Logger.info("Role assignment skipped (SKIP_ROLE_ASSIGNMENT=true)")
            return True
        
        try:
            # Check if role already assigned
            url = f"{self.fabric_api_url}/workspaces/{workspace_id}/roleAssignments"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                roles = response.json().get("value", [])
                for role in roles:
                    if role.get("principal", {}).get("id") == self.client_id:
                        existing_role = role.get("role")
                        if existing_role in ["Admin", "Contributor"]:
                            Logger.info(f"  → Already has {existing_role} role")
                            return True
            
            # Try to assign Admin role
            payload = {
                "principal": {
                    "id": self.client_id,
                    "type": "ServicePrincipal"
                },
                "role": "Admin"
            }
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            
            if response.status_code in [200, 201]:
                Logger.info("  → Admin role assigned successfully")
                return True
            elif response.status_code == 403:
                Logger.warning("  → Cannot assign role (403 Forbidden)")
                return False
            else:
                Logger.warning(f"  → Role assignment failed: {response.status_code}")
                return False
        
        except Exception as e:
            Logger.warning(f"Role assignment error: {e}")
            return False
    
    # ======================== STEP 3: CLONE GITHUB REPOSITORY ========================
    
    def step_3_clone_github_repository(self) -> bool:
        """
        STEP 3: Clone GitHub repository containing Fabric items
        
        Returns:
            bool: True if repository cloned successfully
        """
        Logger.step(3, 6, "CLONE GITHUB REPOSITORY")
        
        try:
            # Clean up any existing temp directory
            if os.path.exists(self.temp_repo_path):
                Logger.info(f"Cleaning up existing temp directory...")
                shutil.rmtree(self.temp_repo_path, ignore_errors=True)
            
            Logger.info(f"Cloning repository: {self.github_repo_path}")
            Logger.info(f"Branch: {self.github_branch}")
            
            # Clone the repository
            result = subprocess.run(
                ["git", "clone", "--branch", self.github_branch, self.github_repo_path, self.temp_repo_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                Logger.error(f"Git clone failed: {result.stderr}")
                return False
            
            Logger.success(f"Repository cloned successfully to {self.temp_repo_path}")
            
            # Verify Development folder exists
            dev_folder_path = os.path.join(self.temp_repo_path, "Development")
            if not os.path.exists(dev_folder_path):
                Logger.error(f"Development folder not found at {dev_folder_path}")
                return False
            
            Logger.success(f"Development folder found")
            
            return True
        
        except subprocess.TimeoutExpired:
            Logger.error("Git clone timed out")
            return False
        except Exception as e:
            Logger.error(f"Clone error: {e}")
            return False
    
    # ======================== STEP 4: PARSE FABRIC ITEMS ========================
    
    def step_4_parse_fabric_items(self) -> bool:
        """
        STEP 4: Parse Fabric items from Development folder
        
        Returns:
            bool: True if items parsed successfully
        """
        Logger.step(4, 6, "PARSE FABRIC ITEMS")
        
        try:
            dev_folder_path = os.path.join(self.temp_repo_path, "Development")
            
            Logger.info(f"Scanning Development folder: {dev_folder_path}")
            
            # Item type mapping
            type_map = {
                '.Report': 'Report',
                '.SemanticModel': 'SemanticModel',
                '.Lakehouse': 'Lakehouse',
                '.Notebook': 'Notebook',
                '.Dataflow': 'Dataflow'
            }
            
            # Scan Development folder
            self.dev_items = []
            for item_folder in os.listdir(dev_folder_path):
                item_path = os.path.join(dev_folder_path, item_folder)
                
                if not os.path.isdir(item_path):
                    continue
                
                # Detect item type
                item_type = None
                for suffix, itype in type_map.items():
                    if suffix in item_folder:
                        item_type = itype
                        break
                
                if item_type is None:
                    Logger.warning(f"  → Unknown type: {item_folder}")
                    continue
                
                # Extract display name (remove type suffix)
                display_name = item_folder
                for suffix in type_map.keys():
                    if suffix in display_name:
                        display_name = display_name.replace(suffix, '')
                        break
                
                item = {
                    'display_name': display_name,
                    'type': item_type,
                    'path': item_path,
                    'folder_name': item_folder
                }
                
                self.dev_items.append(item)
                Logger.info(f"  → Found: {display_name} ({item_type})")
            
            if not self.dev_items:
                Logger.error("No Fabric items found in Development folder")
                return False
            
            Logger.success(f"Found {len(self.dev_items)} Fabric items")
            
            return True
        
        except Exception as e:
            Logger.error(f"Error parsing items: {e}")
            return False
    
    # ======================== STEP 5: DEPLOY ITEMS TO PROD ========================
    
    def step_5_deploy_items_to_prod(self) -> bool:
        """
        STEP 5: Deploy parsed items to Production workspace
        
        Returns:
            bool: True if all items deployed (or mostly deployed)
        """
        Logger.step(5, 6, "DEPLOY ITEMS TO PRODUCTION WORKSPACE")
        
        self.deployment_results['total'] = len(self.dev_items)
        
        for idx, item in enumerate(self.dev_items, 1):
            Logger.info(f"\n[{idx}/{len(self.dev_items)}] Deploying: {item['display_name']} ({item['type']})")
            
            if self._deploy_single_item(item):
                self.deployment_results['success'] += 1
                Logger.success(f"Deployed: {item['display_name']}")
            else:
                self.deployment_results['failed'] += 1
                self.deployment_results['failed_items'].append(item['display_name'])
                Logger.error(f"Failed to deploy: {item['display_name']}")
            
            # Rate limiting - delay between requests
            time.sleep(2)
        
        return self.deployment_results['success'] > 0
    
    def _deploy_single_item(self, item: Dict) -> bool:
        """Deploy a single Fabric item to production workspace"""
        try:
            # Get definition file based on type
            definition_file = self._get_definition_file(item['type'], item['path'], item['display_name'])
            
            if not definition_file:
                Logger.warning(f"  → Definition file not found")
                return False
            
            # Read and encode definition file
            with open(definition_file, 'rb') as f:
                file_content = f.read()
                base64_content = base64.b64encode(file_content).decode('utf-8')
            
            # Get logical file name
            logical_file = os.path.basename(definition_file)
            
            # Create deployment payload
            payload = {
                "displayName": item['display_name'],
                "type": item['type'],
                "definition": {
                    "parts": [
                        {
                            "path": logical_file,
                            "payload": base64_content,
                            "payloadType": "InlineBase64"
                        }
                    ]
                }
            }
            
            # Deploy to Fabric API
            url = f"{self.fabric_api_url}/workspaces/{self.prod_workspace_id}/items"
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)
            
            if response.status_code in [200, 201, 202]:
                return True
            elif response.status_code == 401:
                Logger.warning(f"  → Unauthorized (401) - check workspace permissions")
                return False
            elif response.status_code == 403:
                Logger.warning(f"  → Forbidden (403) - insufficient permissions")
                return False
            else:
                Logger.warning(f"  → API Error {response.status_code}: {response.text[:100]}")
                return False
        
        except Exception as e:
            Logger.warning(f"  → Deployment error: {e}")
            return False
    
    def _get_definition_file(self, item_type: str, item_path: str, display_name: str) -> Optional[str]:
        """Get the definition file path for an item"""
        
        definition_map = {
            'Report': 'definition.pbir',
            'SemanticModel': 'definition.pbism',
            'Lakehouse': 'lakehouse.metadata.json',
            'Dataflow': 'mashup.pq',
            'Notebook': 'notebook-content.py'
        }
        
        def_file = definition_map.get(item_type)
        if not def_file:
            return None
        
        file_path = os.path.join(item_path, def_file)
        
        # Special handling for notebooks - check for .ipynb
        if item_type == 'Notebook' and not os.path.exists(file_path):
            file_path = os.path.join(item_path, f"{display_name}.ipynb")
        
        if os.path.exists(file_path):
            return file_path
        
        return None
    
    # ======================== STEP 6: GENERATE REPORT ========================
    
    def step_6_generate_report(self) -> None:
        """
        STEP 6: Generate deployment report
        """
        Logger.step(6, 6, "GENERATE DEPLOYMENT REPORT")
        
        total = self.deployment_results['total']
        success = self.deployment_results['success']
        failed = self.deployment_results['failed']
        
        # Summary statistics
        Logger.section("DEPLOYMENT SUMMARY")
        
        print(f"Total Items:        {total}")
        print(f"Successfully Deployed: {success}")
        print(f"Failed:             {failed}")
        
        if success == total:
            Logger.success(f"All {total} items deployed successfully!")
        elif success > 0:
            Logger.warning(f"{success}/{total} items deployed successfully")
        else:
            Logger.error(f"No items deployed successfully")
        
        # Failed items details
        if self.deployment_results['failed_items']:
            Logger.section("FAILED ITEMS")
            for item_name in self.deployment_results['failed_items']:
                print(f"  - {item_name}")
        
        # Workspace info
        Logger.section("WORKSPACE INFORMATION")
        print(f"Source Workspace:   {self.dev_workspace_name} (Dev)")
        print(f"Target Workspace:   {self.prod_workspace_name} (Prod)")
        print(f"Deployment Date:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save report to file
        self._save_report_to_file()
    
    def _save_report_to_file(self) -> None:
        """Save deployment report to JSON file"""
        try:
            report = {
                "timestamp": datetime.now().isoformat(),
                "source_workspace": self.dev_workspace_name,
                "target_workspace": self.prod_workspace_name,
                "summary": {
                    "total_items": self.deployment_results['total'],
                    "successful": self.deployment_results['success'],
                    "failed": self.deployment_results['failed']
                },
                "failed_items": self.deployment_results['failed_items'],
                "items_deployed": [
                    {
                        "name": item['display_name'],
                        "type": item['type']
                    }
                    for item in self.dev_items[:self.deployment_results['success']]
                ]
            }
            
            report_path = "deployment_report.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            Logger.success(f"Report saved to {report_path}")
        
        except Exception as e:
            Logger.warning(f"Could not save report: {e}")
    
    # ======================== CLEANUP ========================
    
    def cleanup(self) -> None:
        """Clean up temporary files"""
        Logger.info("Cleaning up temporary files...")
        
        try:
            if os.path.exists(self.temp_repo_path):
                shutil.rmtree(self.temp_repo_path, ignore_errors=True)
                Logger.success(f"Cleaned up {self.temp_repo_path}")
        except Exception as e:
            Logger.warning(f"Cleanup error: {e}")
    
    # ======================== MAIN ORCHESTRATION ========================
    
    def run(self) -> bool:
        """
        Execute the complete deployment workflow
        
        Returns:
            bool: True if deployment completed successfully
        """
        try:
            # Step 1: Authenticate
            if not self.step_1_authenticate():
                Logger.error("Authentication failed. Aborting.")
                return False
            
            # Step 2: Verify workspace access
            if not self.step_2_verify_workspace_access():
                Logger.error("Workspace access verification failed. Aborting.")
                return False
            
            # Step 3: Clone GitHub repository
            if not self.step_3_clone_github_repository():
                Logger.error("GitHub clone failed. Aborting.")
                return False
            
            # Step 4: Parse Fabric items
            if not self.step_4_parse_fabric_items():
                Logger.error("Item parsing failed. Aborting.")
                return False
            
            # Step 5: Deploy items to prod
            if not self.step_5_deploy_items_to_prod():
                Logger.error("Deployment failed.")
                return False
            
            # Step 6: Generate report
            self.step_6_generate_report()
            
            return True
        
        except Exception as e:
            Logger.error(f"Unexpected error: {e}")
            return False
        
        finally:
            self.cleanup()


def main():
    """Entry point"""
    try:
        manager = FabricDeploymentManager()
        success = manager.run()
        
        if success:
            Logger.section("DEPLOYMENT COMPLETED SUCCESSFULLY")
            sys.exit(0)
        else:
            Logger.section("DEPLOYMENT FAILED")
            sys.exit(1)
    
    except Exception as e:
        Logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()