# AWS Manager (Standalone) 🛡️

Universal AWS Assistant for secure, read-only infrastructure visibility and interactive profile discovery.

## 🚀 Installation

To use this as a standalone tool, ensure you have Python 3.x installed and the required dependencies:

```bash
pip install boto3 pandas
```

To integrate with Gemini CLI as a skill, add the path to `aws-manager.skill` in your Gemini configuration.

## 📖 User Guide: How to Use

### 1. The Main Menu
To get started, simply type **"aws"** or **"show me the aws menu"**. Gemini will present you with primary options:
- **Search Memory**: Quick lookups from your last scan.
- **Refresh Inventory**: Update your local cache with the latest AWS data.
- **Add Profile (Wizard)**: A step-by-step guide to adding new AWS accounts.
- **List/Delete Profiles**: Manage your local `~/.aws/config`.

---

### 2. Updating Your Inventory (Refresh)
Before searching, you need data!
1. Select **"Refresh Inventory"** from the main menu.
2. Choose **"All Profiles"** for a full scan or select a **specific profile**.
3. The engine will scan all regions in those accounts and save the data to `aws_inventory_memory.json`.
4. *Note:* If your SSO token is expired, you will be prompted to run `aws sso login`.

---

### 3. Searching and Navigating (Search Memory)
Once you have data, you can explore it instantly:
1. Select **"Search Memory"**.
2. **IP Lookup:** You can ask specifically: *"Find the server with IP 10.50.1.20"* or *"Which VPC is 172.16.5.4 in?"*
3. **Drill Down:** Explore by Account, Region, and Category (Network, Security, Tags, etc.).

---

### 4. Adding New Accounts (Setup Wizard)
1. Select **"Add Profile (Wizard)"**.
2. The tool discovers all AWS accounts accessible via your current SSO session.
3. Select an account and role from the interactive menus.
4. The tool automatically updates your `~/.aws/config`.

---

### 5. Exporting Data
1. After viewing a category, select **"Export this view to CSV"**.
2. Provide a filename (e.g., `inventory_report.csv`).
3. The CSV will be generated in the local directory.

---

## 🛡️ Security & Safety

- **Read-Only:** This tool uses only `Describe` and `List` APIs. It cannot modify AWS resources.
- **Local Privacy:** Your AWS data is stored locally in `aws_inventory_memory.json` and is never sent to external servers.

---
Developed for Gemini CLI.
