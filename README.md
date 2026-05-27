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

To install this extension directly into your Gemini CLI, use one of the following commands:

**Recommended (SSH)**
```bash
gemini extensions install git@github.com:suraj8277/AWS_Assistant.git
```

**Alternative (HTTPS)**
```bash
gemini extensions install https://github.com/suraj8277/AWS_Assistant.git
```

### Manual Setup (Development)
1. Clone this repository to your local machine.
2. Ensure you have the AWS CLI configured.
3. Install dependencies:
   ```bash
   pip install boto3 pandas openpyxl rich
   ```

## 🛡️ Security & Privacy
- **Strictly Read-Only:** No commands can modify or delete AWS resources.
- **Local Cache:** Inventory data is stored only on your local machine (`aws_inventory_memory.json`).
- **Confirmation Required:** Every AWS command and file access requires explicit user consent.

---
Developed by Suraj Kumar
