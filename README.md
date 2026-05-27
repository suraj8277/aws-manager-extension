# Gemini AWS Assistant Extension

A specialized Gemini CLI extension for secure, high-speed AWS infrastructure visibility. 

## 🚀 Features
- **Cache-First Architecture:** Instant search and browse using local inventory memory.
- **Multi-Account/Region Scanning:** Parallel scanning across dozens of profiles.
- **SSO Integration:** Native handling of AWS SSO login sessions.
- **Human-Readable Output:** Detailed "Notepad" views and structured Unicode tables.
- **Proactive Navigation:** Guided flows for discovery and troubleshooting.

## 🛠️ Structure
- `skills/aws-manager/SKILL.md`: The logic defining Gemini's behavior and UI.
- `skills/aws-manager/scripts/aws_engine.py`: The Python backend for AWS API interaction.

## 📦 Installation
1. Clone this repository.
2. Ensure you have the AWS CLI configured.
3. Install dependencies:
   ```bash
   pip install boto3 pandas openpyxl
   ```
4. Load into Gemini CLI.

## 🛡️ Security & Privacy
- **Strictly Read-Only:** No commands can modify or delete AWS resources.
- **Local Cache:** Inventory data is stored only on your local machine (`aws_inventory_memory.json`).
- **Confirmation Required:** Every AWS command and file access requires explicit user consent.

---
Developed by Suraj Kumar
