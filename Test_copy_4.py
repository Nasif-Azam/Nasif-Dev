import os
import json
import requests
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
import time
import shutil
import subprocess
import base64  # Added for Base64 encoding

# Load environment variables
load_dotenv()

class FabricDeploymentManager:
    def __init__(self):
        self.tenant_id = os.getenv('TENANT_ID_ENV')
        self.client_id = os.getenv('CLIENT_ID_ENV')
        self.client_secret = os.getenv('CLIENT_SECRET_ENV')
        self.capacity_id = os.getenv('CAPACITY_ID_ENV')
        self.dev_workspace_id = os.getenv('DEV_WORKSPACE_ID')
        self.prod_workspace_id = os.getenv('PROD_WORKSPACE_ID')
        self.prod_workspace_name = os.getenv('PROD_WORKSPACE_NAME')
        self.skip_role_assignment = os.getenv('SKIP_ROLE_ASSIGNMENT', 'false').lower() == 'true'
        
        self.fabric_api_url = "https://api.fabric.microsoft.com/v1"
        self.access_token = None
        
    def get_access_token(self):
        """Generate access token using Service Principal credentials"""
        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            # Use the default scope
            token = credential.get_token("https://api.fabric.microsoft.com/.default")
            self.access_token = token.token
            print("[OK] Access token generated successfully")
            return self.access_token
        except Exception as e:
            print(f"[ERROR] Error generating access token: {e}")
            raise
    
    def get_headers(self):
        """Return authorization headers"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    # --- NEW: Your Role Assignment Logic Adapted for Class Use ---
    def get_role_assignments(self, workspace_id):
        """Get existing roles to avoid duplicates"""
        try:
            url = f"{self.fabric_api_url}/workspaces/{workspace_id}/roleAssignments"
            response = requests.get(url, headers=self.get_headers())
            
            # If 403, we might not be admin yet, or we are admin but token scope issues.
            # We return empty list to try assignment, or let it fail downstream.
            if response.status_code == 403:
                print(f"[WARNING] Cannot list roles (403). Assuming no access or limited permissions.")
                return []
                
            response.raise_for_status()
            return response.json().get("value", [])
        except Exception as e:
            print(f"[WARNING] Failed to get role assignments: {e}")
            return []

    def assign_role_to_workspace(self, workspace_id, principal_id, principal_type="ServicePrincipal", role="Admin"):
        """
        Assign role checking for existence first to avoid 403/409 errors.
        Adapted from user provided snippet.
        """
        if self.skip_role_assignment:
            print(f"[SKIP] Skipping role assignment")
            return True

        print(f"[INFO] Checking existing roles for {workspace_id}...")
        existing_roles = self.get_role_assignments(workspace_id)
        
        # Check if our principal already has ANY role (simplified check)
        # Ideally we check for the specific role, but if we are already Admin, we are good.
        is_assigned = False
        for ra in existing_roles:
            # Check ID match
            if ra.get("principal", {}).get("id") == principal_id:
                current_role = ra.get("role")
                print(f"[INFO] Principal {principal_id} already has role: {current_role}")
                if current_role == "Admin" or current_role == role:
                    is_assigned = True
                    break

        if is_assigned:
            print(f"[SKIP] Role '{role}' already assigned to {principal_id}")
            return True

        # If not assigned, try to assign
        try:
            url = f"{self.fabric_api_url}/workspaces/{workspace_id}/roleAssignments"
            payload = {
                "principal": {
                    "id": principal_id,
                    "type": principal_type 
                },
                "role": role
            }
            
            response = requests.post(
                url, 
                headers=self.get_headers(), 
                json=payload
            )
            
            if response.status_code in [200, 201]:
                print(f"[OK] Assigned {role} to {principal_id}")
                return True
            else:
                print(f"[ERROR] Role assignment failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"[ERROR] Error assigning role: {e}")
            return False
    # -------------------------------------------------------------

    def create_workspace(self, workspace_name, workspace_id=None):
        """Create workspace if it doesn't exist"""
        try:
            # Check if workspace exists by ID
            if workspace_id:
                url = f"{self.fabric_api_url}/workspaces/{workspace_id}"
                response = requests.get(url, headers=self.get_headers())
                
                if response.status_code == 200:
                    print(f"[OK] Workspace '{workspace_name}' already exists")
                    return response.json()
            
            # Create new workspace
            payload = {
                "displayName": workspace_name,
                "capacityId": self.capacity_id
            }
            response = requests.post(
                f"{self.fabric_api_url}/workspaces",
                headers=self.get_headers(),
                json=payload
            )
            
            if response.status_code in [200, 201]:
                workspace = response.json()
                print(f"[OK] Workspace '{workspace_name}' created successfully")
                return workspace
            elif response.status_code == 409:
                print(f"[OK] Workspace '{workspace_name}' already exists (409)")
                # We can't easily get the ID if we just have the name and 409, 
                # so we rely on the passed workspace_id if available.
                if workspace_id:
                    return {"id": workspace_id}
                return None
            else:
                print(f"[ERROR] Error creating workspace: {response.status_code}")
                return None
        except Exception as e:
            print(f"[ERROR] Error in create_workspace: {e}")
            raise

    def get_items_from_github(self, repo_url="https://github.com/Nasif-Azam/Nasif-Dev", branch="Dev-Branch"):
        """Clone and retrieve items"""
        # (Keeping your original logic but ensuring we catch errors)
        try:
            if os.path.exists("temp_fabric_repo"):
                shutil.rmtree("temp_fabric_repo", ignore_errors=True)
            
            print(f"[INFO] Cloning {repo_url}...")
            subprocess.run(["git", "clone", "--branch", branch, repo_url, "temp_fabric_repo"], check=True, capture_output=True)
            
            dev_path = os.path.join("temp_fabric_repo", "Development")
            items = []
            
            if not os.path.exists(dev_path):
                print("[ERROR] Development folder not found")
                return []

            for item_name in os.listdir(dev_path):
                item_path = os.path.join(dev_path, item_name)
                if os.path.isdir(item_path):
                    # Simple type detection
                    itype = "Unknown"
                    if ".Report" in item_name: itype = "Report"
                    elif ".SemanticModel" in item_name: itype = "SemanticModel"
                    elif ".Lakehouse" in item_name: itype = "Lakehouse"
                    elif ".Notebook" in item_name: itype = "Notebook"
                    elif ".Dataflow" in item_name: itype = "Dataflow"
                    
                    if itype != "Unknown":
                        items.append({
                            "displayName": item_name.split('.')[0],
                            "type": itype,
                            "path": item_path
                        })
            return items
        except Exception as e:
            print(f"[ERROR] Git clone failed: {e}")
            return []

    # --- UPDATED: Fixes 415 Error (Base64 Encoding) ---
    def copy_item_to_workspace(self, item, target_workspace_id):
        try:
            item_type = item.get('type')
            item_name = item.get('displayName')
            item_path = item.get('path')
            
            # Map types to specific definition files
            def_map = {
                'Report': 'definition.pbir',
                'SemanticModel': 'definition.pbism',
                'Lakehouse': 'lakehouse.metadata.json',
                'Dataflow': 'mashup.pq',
                'Notebook': 'notebook-content.py'
            }
            
            logical_file = def_map.get(item_type)
            if not logical_file:
                print(f"[SKIP] Unknown definition for {item_type}")
                return False

            file_path = os.path.join(item_path, logical_file)
            
            # Special handling for notebooks which might be .ipynb
            if item_type == 'Notebook' and not os.path.exists(file_path):
                 file_path = os.path.join(item_path, f"{item_name}.ipynb")
                 logical_file = f"{item_name}.ipynb"

            if not os.path.exists(file_path):
                print(f"[WARNING] File not found: {file_path}")
                return False

            # READ AND BASE64 ENCODE
            with open(file_path, 'rb') as f:
                raw_content = f.read()
                base64_content = base64.b64encode(raw_content).decode('utf-8')

            # Create Payload
            payload = {
                "displayName": item_name,
                "type": item_type,
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

            url = f"{self.fabric_api_url}/workspaces/{target_workspace_id}/items"
            res = requests.post(url, headers=self.get_headers(), json=payload)
            
            if res.status_code in [200, 201, 202]:
                print(f"[OK] Created {item_name}")
                return True
            else:
                print(f"[ERROR] Failed to create {item_name}: {res.status_code} - {res.text}")
                return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False

    def deploy_all_items(self):
        self.get_access_token()
        
        # 1. Workspace
        print("\n--- Workspace Setup ---")
        ws = self.create_workspace(self.prod_workspace_name, self.prod_workspace_id)
        if not ws: return
        ws_id = ws.get('id', self.prod_workspace_id)

        # 2. Role Assignment (Using your new logic)
        print("\n--- Role Assignment ---")
        # Note: Change principal_type to "ServicePrincipal" for App authentication
        self.assign_role_to_workspace(ws_id, self.client_id, principal_type="ServicePrincipal")

        # 3. Get Items
        print("\n--- Fetching Items ---")
        items = self.get_items_from_github()

        # 4. Deploy
        print("\n--- Deploying Items ---")
        for item in items:
            self.copy_item_to_workspace(item, ws_id)
            time.sleep(2) # Rate limiting buffer

        # Cleanup
        if os.path.exists("temp_fabric_repo"):
            shutil.rmtree("temp_fabric_repo", ignore_errors=True)

if __name__ == "__main__":
    manager = FabricDeploymentManager()
    manager.deploy_all_items()