# GitHub Repository Deployment Enhancement

## Overview

The `FabricDeploymentManager.py` has been updated to support deploying Fabric items directly from a GitHub repository instead of relying solely on the Fabric workspace API.

## Problem Solved

Previously, the deployment script would fail when trying to retrieve items from a Fabric workspace API endpoint with a 401 Unauthorized error. This enhancement allows you to deploy items stored in your GitHub repository, bypassing the need for direct API access to the Fabric workspace.

## New Features

### 1. GitHub Source Support

The script now includes methods to:

- **Read Fabric items from GitHub repository** (`get_items_from_github`)
- **Deploy items from local repository** (`deploy_items_from_github`)
- **Prepare items for deployment** (`deploy_item_from_path`)

### 2. Automatic Item Type Detection

The script automatically identifies item types based on folder naming conventions:

- `.Dataflow` → Dataflow
- `.Lakehouse` → Lakehouse
- `.Report` → Report
- `.SemanticModel` → Semantic Model
- `.Notebook` → Notebook
- `.Pipeline` → Pipeline

### 3. Configuration Options

Two new environment variables control GitHub deployment:

| Environment Variable | Default | Purpose                                                                 |
| -------------------- | ------- | ----------------------------------------------------------------------- |
| `USE_GITHUB_SOURCE`  | false   | Enable GitHub repository as deployment source                           |
| `GITHUB_REPO_PATH`   | (empty) | Path to your GitHub repository (e.g., `c:\Users\username\path\to\repo`) |

## Usage

### Setup

1. **Copy the example environment file:**

   ```bash
   copy .env.github-example .env
   ```

2. **Update your .env file with GitHub settings:**

   ```env
   USE_GITHUB_SOURCE=true
   GITHUB_REPO_PATH=c:\Users\NasifAzam\Documents\GitHub\Nasif-Dev
   PROD_WORKSPACE_ID=6404d31d-7060-4956-9f8a-c7e2b65de6ac
   ```

3. **Run the deployment:**
   ```bash
   python FabricDeploymentManager.py
   ```

### Configuration Examples

#### Option 1: Deploy from GitHub Repository

```env
USE_GITHUB_SOURCE=true
GITHUB_REPO_PATH=c:\Users\NasifAzam\Documents\GitHub\Nasif-Dev
PROD_WORKSPACE_ID=6404d31d-7060-4956-9f8a-c7e2b65de6ac
SKIP_ROLE_ASSIGNMENT=true
```

#### Option 2: Deploy from Fabric Workspace (Original Method)

```env
USE_GITHUB_SOURCE=false
DEV_WORKSPACE_ID=7616697c-da00-4dba-b6fb-4379d600cc7a
PROD_WORKSPACE_ID=6404d31d-7060-4956-9f8a-c7e2b65de6ac
```

## Expected Directory Structure

The script expects Fabric items in the following structure:

```
Development/
├── DF_SP_CSV.Dataflow/
│   ├── mashup.pq
│   └── queryMetadata.json
├── Lakehouse.Lakehouse/
│   ├── alm.settings.json
│   └── lakehouse.metadata.json
├── Music Sales Report.Report/
│   ├── definition.pbir
│   ├── report.json
│   └── StaticResources/
└── Music Sales Report.SemanticModel/
    ├── definition.pbism
    ├── definition/
    └── ...
```

## Output

When running with GitHub source, you'll see logs like:

```
2026-01-21 08:25:08,420 - INFO - STEP 3: Deploying Items from Dev to Prod
2026-01-21 08:25:08,420 - INFO - Using GitHub repository as source: c:\Users\NasifAzam\Documents\GitHub\Nasif-Dev
2026-01-21 08:25:08,420 - INFO - Retrieving items from GitHub repository: c:\Users\NasifAzam\Documents\GitHub\Nasif-Dev
2026-01-21 08:25:08,420 - INFO -   Found Dataflow: DF_SP_CSV
2026-01-21 08:25:08,420 - INFO -   Found Lakehouse: Lakehouse
2026-01-21 08:25:08,420 - INFO -   Found Report: Music Sales Report
2026-01-21 08:25:08,420 - INFO -   Found SemanticModel: Music Sales Report
2026-01-21 08:25:08,420 - INFO - ✓ Retrieved 4 items from GitHub repository
```

## Benefits

1. **Eliminates API Authentication Issues** - No need for workspace API access if using GitHub
2. **Better Version Control** - Items are tracked in Git with full history
3. **Faster Deployment** - No need to authenticate with Fabric workspace API
4. **Flexible Deployment** - Can deploy from any branch or version stored in Git
5. **Reduced Dependencies** - Uses local file system instead of API calls

## Migration Path

If you're currently getting 401 errors from the Fabric API:

1. Ensure your Fabric items are committed to GitHub in the `Development/` folder
2. Set `USE_GITHUB_SOURCE=true` in your `.env` file
3. Set `GITHUB_REPO_PATH` to your repository path
4. Run the deployment script

## Troubleshooting

### Issue: "Development folder not found"

- Ensure `GITHUB_REPO_PATH` points to the correct repository root
- Verify the `Development` folder exists in the repository

### Issue: "No items found to deploy"

- Check that item folders follow the naming convention (e.g., `Name.Report`, `Name.SemanticModel`)
- Ensure items are in the `Development/` folder

### Issue: Items found but deployment fails

- Check Prod workspace ID is correct (`PROD_WORKSPACE_ID`)
- Verify Service Principal has necessary permissions in Prod workspace
- Review logs for specific error messages

## Technical Details

### New Methods Added

#### `get_items_from_github(github_repo_path, branch='Dev-Branch')`

Scans the GitHub repository's Development folder and returns a list of detected Fabric items with their types and paths.

#### `deploy_items_from_github(github_repo_path, target_workspace_id, item_types=None)`

Orchestrates deployment of all items from GitHub repository to the target Fabric workspace.

#### `deploy_item_from_path(item_path, item_type, item_name, target_workspace_id)`

Deploys a single item from its local file system path to the Fabric workspace.

### Backward Compatibility

All original methods remain intact. The script maintains full backward compatibility:

- Original `deploy_items()` method still works with workspace IDs
- Existing configurations continue to function unchanged
- GitHub deployment is opt-in via configuration

## Future Enhancements

Potential improvements for future versions:

- Support for .pbix file generation and upload
- Integration with Fabric REST API for direct item creation
- Support for Power BI Desktop project files (.pbip)
- Automated testing of deployed items
- Rollback capabilities
