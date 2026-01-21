# Quick Start Guide - GitHub Deployment

## Problem

Getting 401 Unauthorized errors when trying to deploy items from Fabric workspace API.

## Solution

Deploy directly from your GitHub repository instead!

---

## 3 Quick Steps

### Step 1: Update .env File

```env
USE_GITHUB_SOURCE=true
GITHUB_REPO_PATH=c:\Users\NasifAzam\Documents\GitHub\Nasif-Dev
PROD_WORKSPACE_ID=6404d31d-7060-4956-9f8a-c7e2b65de6ac
SKIP_ROLE_ASSIGNMENT=true
```

### Step 2: Ensure Items Are in GitHub

Your repository should have this structure:

```
Nasif-Dev/
└── Development/
    ├── DF_SP_CSV.Dataflow/
    ├── Lakehouse.Lakehouse/
    ├── Music Sales Report.Report/
    └── Music Sales Report.SemanticModel/
```

### Step 3: Run Deployment

```bash
python FabricDeploymentManager.py
```

---

## Expected Output

```
2026-01-21 08:25:08,420 - INFO - STEP 3: Deploying Items from Dev to Prod
2026-01-21 08:25:08,420 - INFO - Using GitHub repository as source: c:\Users\NasifAzam\Documents\GitHub\Nasif-Dev
2026-01-21 08:25:08,420 - INFO - ✓ Retrieved 4 items from GitHub repository
2026-01-21 08:25:08,420 - INFO - → Deploying Dataflow: DF_SP_CSV from GitHub
2026-01-21 08:25:08,420 - INFO - ✓ Dataflow 'DF_SP_CSV' prepared for deployment
...
2026-01-21 08:25:08,420 - INFO - DEPLOYMENT SUMMARY
2026-01-21 08:25:08,420 - INFO - ✓ Successful: 4
```

---

## Configuration Reference

| Setting                | Value             | Purpose                          |
| ---------------------- | ----------------- | -------------------------------- |
| `USE_GITHUB_SOURCE`    | `true`            | Enable GitHub deployment         |
| `GITHUB_REPO_PATH`     | Your repo path    | Where to find Development folder |
| `PROD_WORKSPACE_ID`    | Your workspace ID | Target Fabric workspace          |
| `SKIP_ROLE_ASSIGNMENT` | `true`            | Skip role assignment (optional)  |

---

## Supported Item Types

- `.Dataflow` → Dataflow
- `.Lakehouse` → Lakehouse
- `.Report` → Report
- `.SemanticModel` → Semantic Model
- `.Notebook` → Notebook
- `.Pipeline` → Pipeline

---

## Troubleshooting

| Error                          | Fix                                                           |
| ------------------------------ | ------------------------------------------------------------- |
| `Development folder not found` | Check `GITHUB_REPO_PATH` is correct                           |
| `No items found to deploy`     | Verify items are in `Development/` folder with correct naming |
| Still getting 401 errors       | Make sure `USE_GITHUB_SOURCE=true` in .env                    |

---

## More Information

- See **GITHUB_DEPLOYMENT.md** for detailed documentation
- See **CHANGES.md** for technical details of modifications
- See **.env.github-example** for configuration template

---

## Benefits

✅ No 401 errors  
✅ Items tracked in Git  
✅ Faster deployment  
✅ Full version history  
✅ Better for CI/CD pipelines

**Ready to deploy!**
