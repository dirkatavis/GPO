# Software Configuration Wizard

Welcome! Let's get your environment ready from a fresh clone.

This guide follows the config layering used in this repository:
- Base shared defaults live in config/config.json.
- config/project.json is the committed project template layered on top of those defaults.
- Your personal machine-only overrides live in config/project.local.json.
- A legacy local override file, config/config.local.json, may also be present in older setups.

JSON is just a settings file written as key/value pairs.

## Step 1: The Git Handshake

Open a terminal in the repository root folder.

Create your personal local config file from the project template:

```bash
cp config/project.json config/project.local.json
```

If you are in Windows PowerShell, this is the equivalent command:

```powershell
Copy-Item config/project.json config/project.local.json
```

Important safety note:
- config/project.local.json is protected by .gitignore.
- That means your local credentials and passwords are not uploaded when you push code.

## Step 2: Identifying Yourself (The JSON Edit)

Open config/project.local.json in your editor.

Fill in the personal fields below.

| JSON key | Plain-English meaning | Example |
|---|---|---|
| login_id | Your internal employee WWID used during SSO selection. | E96693 |
| spreadsheet_id | The long ID string from your Google Sheet URL. | 1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890 |
| email_password | Your Google App Password for Gmail integration. This is not your normal Google sign-in password. | abcd efgh ijkl mnop |

How to find spreadsheet_id:
1. Open your target Google Sheet in a browser.
2. Copy the URL.
3. Take only the string between /d/ and /edit.

Example:
- URL: https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890/edit#gid=0
- spreadsheet_id: 1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890

## Step 3: Verification (The Smoke Test)

Run this command from the repository root to verify two things:
- The app can read your new local config file.
- The login URL is reachable.

```bash
py -3 -c "from config.config_loader import get_config; import urllib.request; url=get_config('login_url','https://avisbudget.palantirfoundry.com/multipass/login'); print('Loaded login_url:', url); response=urllib.request.urlopen(url, timeout=10); print('Connected. HTTP status:', response.status)"
```

Expected result:
- You should see your resolved login URL printed.
- You should see an HTTP status code, which confirms connectivity to your Foundry login endpoint.

You are now configured with a safe local setup pattern for development.
