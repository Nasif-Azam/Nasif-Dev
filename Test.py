import os
import json
import requests
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
import time

# filepath: c:\Users\NasifAzam\Documents\GitHub\Nasif-Dev\FabricDeploymentManager.py


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
        self.dev_workspace_name = os.getenv('DEV_WORKSPACE_NAME')
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
                # Workspace already exists, use the provided workspace_id
                print(f"[OK] Workspace '{workspace_name}' already exists")
                if workspace_id:
                    return {"id": workspace_id, "displayName": workspace_name}
                else:
                    print(f"[ERROR] Workspace exists but no workspace_id provided")
                    return None
            else:
                print(f"[ERROR] Error creating workspace: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"[ERROR] Error in create_workspace: {e}")
            raise
    
    def assign_role_to_workspace(self, workspace_id, principal_id, principal_type="App", role="Admin"):
        """Assign role to Service Principal in workspace"""
        if self.skip_role_assignment:
            print(f"[SKIP] Skipping role assignment (SKIP_ROLE_ASSIGNMENT=true)")
            return True
        
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
                print(f"[OK] Role '{role}' assigned to workspace '{workspace_id}'")
                return True
            else:
                print(f"[WARNING] Role assignment failed: {response.status_code} - {response.text}")
                print(f"[INFO] Continuing deployment without role assignment...")
                return True  # Don't block deployment
        except Exception as e:
            print(f"[WARNING] Error in assign_role_to_workspace: {e}")
            print(f"[INFO] Continuing deployment without role assignment...")
            return True  # Don't block deployment
    
    def get_workspace_items(self, workspace_id):
        """Get all items from a workspace"""
        try:
            url = f"{self.fabric_api_url}/workspaces/{workspace_id}/items"
            response = requests.get(url, headers=self.get_headers())
            
            if response.status_code == 200:
                items = response.json().get('value', [])
                print(f"[OK] Retrieved {len(items)} items from workspace '{workspace_id}'")
                return items
            else:
                print(f"[ERROR] Error retrieving items: {response.status_code}")
                return []
        except Exception as e:
            print(f"[ERROR] Error in get_workspace_items: {e}")
            return []
    
    def copy_item_to_workspace(self, item, source_workspace_id, target_workspace_id):
        """Copy item from source to target workspace"""
        try:
            item_id = item.get('id')
            item_type = item.get('type')
            item_name = item.get('displayName')
            
            url = f"{self.fabric_api_url}/workspaces/{source_workspace_id}/items/{item_id}/copyto"
            payload = {
                "targetWorkspaceId": target_workspace_id,
                "copyOption": "Copy"
            }
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload
            )
            
            if response.status_code in [200, 202]:
                print(f"[OK] Item '{item_name}' ({item_type}) copied successfully")
                return True
            else:
                print(f"[ERROR] Error copying item '{item_name}': {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] Error in copy_item_to_workspace: {e}")
            return False
    
    def deploy_all_items(self):
        """Main deployment function"""
        try:
            print("\n" + "="*60)
            print("FABRIC DEPLOYMENT MANAGER")
            print("="*60 + "\n")
            
            # Step 1: Get access token
            print("[1/5] Generating Fabric Access Token...")
            self.get_access_token()
            
            # Step 2: Create/Verify Prod Workspace
            print("\n[2/5] Creating/Verifying Prod Workspace...")
            prod_ws = self.create_workspace(self.prod_workspace_name, self.prod_workspace_id)
            if not prod_ws:
                print("[ERROR] Failed to create/verify Prod workspace")
                return False
            
            prod_ws_id = prod_ws.get('id', self.prod_workspace_id)
            
            # Step 3: Assign Role to Prod Workspace
            print("\n[3/5] Assigning Role to Prod Workspace...")
            self.assign_role_to_workspace(prod_ws_id, self.client_id)
            
            # Step 4: Get items from Dev Workspace
            print("\n[4/5] Retrieving items from Dev Workspace...")
            dev_items = self.get_workspace_items(self.dev_workspace_id)
            
            if not dev_items:
                print("[ERROR] No items found in Dev workspace")
                return False
            
            # Step 5: Deploy items to Prod Workspace
            print("\n[5/5] Deploying items to Prod Workspace...")
            successful_deployments = 0
            
            for item in dev_items:
                if self.copy_item_to_workspace(item, self.dev_workspace_id, prod_ws_id):
                    successful_deployments += 1
                time.sleep(1)  # Rate limiting
            
            print("\n" + "="*60)
            print(f"DEPLOYMENT COMPLETE: {successful_deployments}/{len(dev_items)} items deployed")
            print("="*60 + "\n")
            
            return True
        except Exception as e:
            print(f"\n[ERROR] Deployment failed: {e}")
            return False

if __name__ == "__main__":
    manager = FabricDeploymentManager()
    manager.deploy_all_items()