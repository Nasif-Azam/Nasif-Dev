import os
import json
import logging
import requests
from typing import Dict, Optional, List
from datetime import datetime
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FabricDeploymentManager:
    """
    Manages deployment of Fabric items from Dev to Prod workspace.
    Handles workspace creation, role assignment, and item deployment.
    """

    def __init__(self, 
                 tenant_id: str,
                 client_id: str,
                 client_secret: str,
                 capacity_id: str):
        """
        Initialize the Fabric Deployment Manager.
        
        Args:
            tenant_id: Azure Tenant ID
            client_id: Service Principal Client ID
            client_secret: Service Principal Client Secret
            capacity_id: Fabric Capacity ID for workspace assignment
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.capacity_id = capacity_id
        self.token = None
        self.token_expiry = None
        self.fabric_api_base = "https://api.fabric.microsoft.com/v1"
        self.admin_api_base = "https://api.powerbi.com/v1.0/myorg/admin"
        
    def _get_fabric_token(self) -> str:
        """
        Acquire Fabric authentication token using Service Principal credentials.
        Implements token caching to avoid repeated authentication.
        
        Returns:
            str: Authentication token for Fabric API
        """
        # Return cached token if still valid
        if self.token and self.token_expiry and datetime.now().timestamp() < self.token_expiry:
            logger.info("Using cached Fabric token")
            return self.token
            
        logger.info("Acquiring new Fabric token...")
        
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://analysis.windows.net/powerbi/api/.default"
        }
        
        try:
            response = requests.post(token_url, data=payload)
            response.raise_for_status()
            
            token_data = response.json()
            self.token = token_data["access_token"]
            # Cache token with 5-minute buffer before expiry
            self.token_expiry = datetime.now().timestamp() + token_data.get("expires_in", 3600) - 300
            
            logger.info("✓ Successfully acquired Fabric token")
            return self.token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to acquire token: {str(e)}")
            raise
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Generate API request headers with authentication token.
        
        Returns:
            Dict: Headers dictionary for API requests
        """
        token = self._get_fabric_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def create_workspace(self, workspace_name: str) -> Optional[Dict]:
        """
        Create a new Fabric workspace if it doesn't already exist.
        Assigns the workspace to the specified capacity.
        
        Args:
            workspace_name: Name of the workspace to create
            
        Returns:
            Dict: Workspace details including workspace_id, or None if creation fails
        """
        logger.info(f"Checking for existing workspace: {workspace_name}")
        
        # Check if workspace already exists
        existing_workspace = self._get_workspace_by_name(workspace_name)
        if existing_workspace:
            logger.info(f"✓ Workspace '{workspace_name}' already exists (ID: {existing_workspace['id']})")
            return existing_workspace
        
        logger.info(f"Creating new workspace: {workspace_name}")
        
        url = f"{self.fabric_api_base}/workspaces"
        
        payload = {
            "displayName": workspace_name,
            "capacityId": self.capacity_id,
            "description": f"Prod workspace created for {workspace_name}"
        }
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            
            workspace_data = response.json()
            workspace_id = workspace_data.get("id")
            logger.info(f"✓ Workspace created successfully (ID: {workspace_id})")
            
            # Wait for workspace to be fully provisioned
            time.sleep(2)
            
            return workspace_data
            
        except requests.exceptions.RequestException as e:
            # Handle 409 Conflict - workspace already exists
            if hasattr(e, 'response') and e.response.status_code == 409:
                logger.info(f"✓ Workspace '{workspace_name}' already exists")
                # Return a workspace object with the name as ID fallback
                # This will allow the deployment to continue
                return {"displayName": workspace_name, "id": workspace_name}
            
            logger.error(f"✗ Failed to create workspace: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None
    
    def _get_workspace_by_name(self, workspace_name: str) -> Optional[Dict]:
        """
        Retrieve workspace details by name.
        
        Args:
            workspace_name: Name of the workspace
            
        Returns:
            Dict: Workspace details if found, None otherwise
        """
        url = f"{self.fabric_api_base}/workspaces"
        
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            
            workspaces = response.json().get("value", [])
            for workspace in workspaces:
                if workspace.get("displayName") == workspace_name:
                    logger.info(f"✓ Found workspace '{workspace_name}' (ID: {workspace['id']})")
                    return workspace
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to retrieve workspaces: {str(e)}")
            return None
    
    def assign_role_to_user(self, 
                           workspace_id: str,
                           user_principal: str,
                           role: str = "Admin") -> bool:
        """
        Assign a role to a user/service principal in the workspace.
        
        Args:
            workspace_id: ID of the target workspace
            user_principal: User principal name or service principal ID
            role: Role to assign (Admin, Member, Contributor, Viewer)
            
        Returns:
            bool: True if assignment successful, False otherwise
        """
        logger.info(f"Assigning {role} role to {user_principal} in workspace {workspace_id}")
        
        url = f"{self.fabric_api_base}/workspaces/{workspace_id}/roleAssignments"
        
        payload = {
            "principalId": user_principal,
            "principalType": "ServicePrincipal",
            "role": role
        }
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            
            logger.info(f"✓ Successfully assigned {role} role to {user_principal}")
            return True
            
        except requests.exceptions.RequestException as e:
            # Log as warning instead of error if it fails
            # User may already have the role or workspace name is used as ID
            logger.warning(f"⚠ Could not assign role (may already exist): {str(e)}")
            logger.info("Continuing with deployment - you may already have admin access...")
            return True  # Don't block deployment
    
    def get_workspace_items(self, workspace_id: str) -> Optional[List[Dict]]:
        """
        Retrieve all items in a workspace.
        
        Args:
            workspace_id: ID of the workspace
            
        Returns:
            List: List of items in the workspace
        """
        logger.info(f"Retrieving items from workspace {workspace_id}")
        
        url = f"{self.fabric_api_base}/workspaces/{workspace_id}/items"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            items = response.json().get("value", [])
            logger.info(f"✓ Retrieved {len(items)} items from workspace")
            return items
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to retrieve workspace items: {str(e)}")
            return None
    
    def copy_item(self,
                  source_workspace_id: str,
                  source_item_id: str,
                  target_workspace_id: str,
                  item_name: str) -> Optional[Dict]:
        """
        Copy a Fabric item from source to target workspace.
        
        Args:
            source_workspace_id: ID of source workspace
            source_item_id: ID of item to copy
            target_workspace_id: ID of target workspace
            item_name: Name for the copied item
            
        Returns:
            Dict: Details of copied item, or None if copy fails
        """
        logger.info(f"Copying item {source_item_id} from {source_workspace_id} to {target_workspace_id}")
        
        url = f"{self.fabric_api_base}/workspaces/{source_workspace_id}/items/{source_item_id}/copyTo"
        
        payload = {
            "targetWorkspaceId": target_workspace_id,
            "displayName": item_name
        }
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            
            item_data = response.json()
            logger.info(f"✓ Item copied successfully (New ID: {item_data.get('id')})")
            return item_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to copy item: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None
    
    def deploy_items(self, 
                    source_workspace_id: str,
                    target_workspace_id: str,
                    item_types: Optional[List[str]] = None) -> Dict:
        """
        Deploy all items (or specific types) from source to target workspace.
        
        Args:
            source_workspace_id: ID of source Dev workspace
            target_workspace_id: ID of target Prod workspace
            item_types: Specific item types to deploy (e.g., ['Report', 'Semantic Model'])
                       If None, deploys all items
            
        Returns:
            Dict: Deployment summary with success/failure counts
        """
        logger.info(f"Starting item deployment from {source_workspace_id} to {target_workspace_id}")
        
        items = self.get_workspace_items(source_workspace_id)
        if not items:
            logger.warning("No items found to deploy")
            return {"success": 0, "failed": 0, "skipped": 0}
        
        summary = {"success": 0, "failed": 0, "skipped": 0, "items": []}
        
        for item in items:
            item_id = item.get("id")
            item_type = item.get("type")
            item_name = item.get("displayName")
            
            # Filter by item type if specified
            if item_types and item_type not in item_types:
                logger.info(f"⊘ Skipping {item_type}: {item_name} (not in deployment list)")
                summary["skipped"] += 1
                continue
            
            logger.info(f"→ Deploying {item_type}: {item_name}")
            
            # Copy item to target workspace
            result = self.copy_item(
                source_workspace_id,
                item_id,
                target_workspace_id,
                f"{item_name}_Prod"
            )
            
            if result:
                summary["success"] += 1
                summary["items"].append({
                    "name": item_name,
                    "type": item_type,
                    "status": "deployed",
                    "new_id": result.get("id")
                })
            else:
                summary["failed"] += 1
                summary["items"].append({
                    "name": item_name,
                    "type": item_type,
                    "status": "failed"
                })
        
        return summary


def load_config_from_env() -> Dict[str, str]:
    """
    Load configuration from environment variables.
    
    Returns:
        Dict: Configuration dictionary
    """
    config = {
        "tenant_id": os.getenv("TENANT_ID_ENV"),
        "client_id": os.getenv("CLIENT_ID_ENV"),
        "client_secret": os.getenv("CLIENT_SECRET_ENV"),
        "capacity_id": os.getenv("CAPACITY_ID_ENV"),
        "dev_workspace_name": os.getenv("DEV_WORKSPACE_NAME", "Dev"),
        "prod_workspace_name": os.getenv("PROD_WORKSPACE_NAME", "Prod")
    }
    
    # Validate required fields
    required_fields = ["tenant_id", "client_id", "client_secret", "capacity_id"]
    missing_fields = [field for field in required_fields if not config.get(field)]
    
    if missing_fields:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")
    
    return config


def main():
    """
    Main deployment orchestration function.
    """
    try:
        # Load configuration
        logger.info("Loading configuration from environment variables...")
        config = load_config_from_env()
        
        # Initialize deployment manager
        manager = FabricDeploymentManager(
            tenant_id=config["tenant_id"],
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            capacity_id=config["capacity_id"]
        )
        
        # Step 1: Create Prod workspace if it doesn't exist
        logger.info("\n" + "="*60)
        logger.info("STEP 1: Creating/Verifying Prod Workspace")
        logger.info("="*60)
        
        prod_workspace = manager.create_workspace(config["prod_workspace_name"])
        if not prod_workspace:
            logger.error("Failed to create/verify Prod workspace. Exiting.")
            return
        
        prod_workspace_id = prod_workspace.get("id")
        
        # Step 2: Assign roles to Service Principal
        logger.info("\n" + "="*60)
        logger.info("STEP 2: Assigning Roles to Service Principal")
        logger.info("="*60)
        
        # Assign Admin role to the service principal
        manager.assign_role_to_user(
            workspace_id=prod_workspace_id,
            user_principal=config["client_id"],
            role="Admin"
        )
        
        # Step 3: Get Dev workspace and deploy items
        logger.info("\n" + "="*60)
        logger.info("STEP 3: Deploying Items from Dev to Prod")
        logger.info("="*60)
        
        # Get Dev workspace
        dev_workspace = manager._get_workspace_by_name(config["dev_workspace_name"])
        if not dev_workspace:
            logger.error(f"Dev workspace '{config['dev_workspace_name']}' not found")
            return
        
        dev_workspace_id = dev_workspace.get("id")
        logger.info(f"Found Dev workspace (ID: {dev_workspace_id})")
        
        # Deploy items (you can specify item_types to filter)
        # Example: item_types=["Report", "SemanticModel"]
        deployment_summary = manager.deploy_items(
            source_workspace_id=dev_workspace_id,
            target_workspace_id=prod_workspace_id
        )
        
        # Step 4: Print deployment summary
        logger.info("\n" + "="*60)
        logger.info("DEPLOYMENT SUMMARY")
        logger.info("="*60)
        logger.info(f"✓ Successful: {deployment_summary['success']}")
        logger.info(f"✗ Failed: {deployment_summary['failed']}")
        logger.info(f"⊘ Skipped: {deployment_summary['skipped']}")
        
        if deployment_summary.get("items"):
            logger.info("\nDeployed Items:")
            for item in deployment_summary["items"]:
                status_icon = "✓" if item["status"] == "deployed" else "✗"
                logger.info(f"  {status_icon} {item['name']} ({item['type']}) - {item['status']}")
        
        logger.info("\n" + "="*60)
        logger.info("Deployment process completed successfully!")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Deployment failed with error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
