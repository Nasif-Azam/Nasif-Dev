import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Access the environment variables
tenant_id = os.getenv('tenant_id_env')
client_id = os.getenv('client_id_env')
client_secret = os.getenv('client_secret_env')
fabric_api_url = os.getenv('fabric_api_base_url')

# Function to get the Fabric token (authentication)
def get_fabric_token(tenant_id, client_id, client_secret):
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://graph.microsoft.com/.default'
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        raise Exception(f"Error getting token: {response.text}")

# Function to check if the workspace exists
def check_workspace_exists(workspace_name, token):
    url = f"{fabric_api_url}/workspaces/{workspace_name}"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    return response.status_code == 200

# Function to create the workspace
def create_workspace(workspace_name, token):
    url = f"{fabric_api_url}/workspaces"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        "name": workspace_name,
        "description": f"{workspace_name} Workspace"
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        print(f"Workspace {workspace_name} created successfully.")
        return response.json()
    else:
        raise Exception(f"Error creating workspace: {response.text}")

# Function to assign roles to the workspace
def assign_role_to_workspace(workspace_name, token, role):
    url = f"{fabric_api_url}/workspaces/{workspace_name}/roles"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        "role": role,
        "workspace": workspace_name
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"Role {role} assigned to workspace {workspace_name}.")
    else:
        raise Exception(f"Error assigning role: {response.text}")

# Function to deploy items from the Dev repository to Prod workspace
def deploy_fabric_items(dev_repo_url, prod_workspace, token):
    deploy_url = f"{fabric_api_url}/workspaces/{prod_workspace}/deploy"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    deploy_data = {
        "repo_url": dev_repo_url,  # GitHub Dev repo URL
        "workspace": prod_workspace
    }
    response = requests.post(deploy_url, headers=headers, json=deploy_data)
    if response.status_code == 200:
        print(f"Deployment from {dev_repo_url} to {prod_workspace} workspace completed.")
    else:
        raise Exception(f"Error deploying items: {response.text}")

# Main function to control the process
def main():
    try:
        # Get Fabric token
        token = get_fabric_token(tenant_id, client_id, client_secret)

        # Check if Nasif-Prod workspace exists, create it if not
        workspace_name = "Nasif-Prod"
        if not check_workspace_exists(workspace_name, token):
            print(f"Workspace {workspace_name} does not exist. Creating...")
            create_workspace(workspace_name, token)

        # Assign Capacity Admin role to Nasif-Prod workspace
        role = "Capacity Admin"  # Assign the desired role (Capacity Admin)
        assign_role_to_workspace(workspace_name, token, role)

        # Deploy items from Nasif-Dev repository to Nasif-Prod workspace
        dev_repo_url = "https://github.com/Nasif-Azam/Nasif-Dev"  # GitHub repository URL
        deploy_fabric_items(dev_repo_url, workspace_name, token)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
