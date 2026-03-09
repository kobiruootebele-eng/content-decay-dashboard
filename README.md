# Content Decay Dashboard

A CLI tool that connects to the **Google Search Console API** and surfaces pages whose organic performance is declining — flagging position drops, keyword falloff from page 1, CTR decline, and click/impression loss.

```
╭──────────────────────────────────────────────────────────────────╮
│               Content Decay Dashboard                            │
│  Recent period:  2025-01-01 → 2025-01-28                        │
│  Prior period:   2024-12-04 → 2024-12-31                        │
│  Decaying URLs found: 14                                         │
╰──────────────────────────────────────────────────────────────────╯
```

---

## Features

| Signal | How it's detected |
|--------|-------------------|
| **Position drop** | Average position worsened by ≥ 2 places |
| **Fell off page 1** | Position was ≤ 10, now > 10 |
| **Keyword loss** | Fewer page-1 keywords than prior period |
| **CTR decline** | Click-through rate fell by ≥ 10 % |
| **Click loss** | Clicks declined by ≥ 15 % |

Every decaying page gets a **severity score (0–100)** composed of weighted signals, and the table is sorted from most to least severe.

---

## Requirements

- Python 3.11+
- A Google account with access to a verified Search Console property
- A Google Cloud project with the **Search Console API** enabled

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/content-decay-dashboard.git
cd content-decay-dashboard
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows CMD
.venv\Scripts\activate.bat
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get credentials.json from Google Cloud Console

You need an **OAuth 2.0 Client ID** for a *Desktop application*.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create (or select) a project.
2. Navigate to **APIs & Services → Library** and search for **"Google Search Console API"**. Click **Enable**.
3. Navigate to **APIs & Services → Credentials**.
4. Click **+ Create Credentials → OAuth client ID**.
5. Set **Application type** to **Desktop app**, give it a name (e.g. `decay-dashboard`), and click **Create**.
6. Click **Download JSON** on the credential you just created.
7. Rename the downloaded file to `credentials.json` and place it in the project root.

> **Note:** If your Cloud project is in *Testing* mode you may need to add yourself as a test user under **OAuth consent screen → Test users**.

### 5. Configure the .env file

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# Path to OAuth2 credentials JSON (default: credentials.json)
CREDENTIALS_PATH=credentials.json

# Your GSC property — use the EXACT format shown in Search Console
# Domain property:
GSC_PROPERTY_URL=sc-domain:example.com
# URL-prefix property (note the trailing slash):
# GSC_PROPERTY_URL=https://www.example.com/
```

To find your exact property URL, open [Google Search Console](https://search.google.com/search-console) and copy the string shown in the property selector at the top-left.

### 6. Run the dashboard

```bash
python dashboard.py
```

The first time you run it, a browser window will open for Google OAuth consent. After authorising, a `token.json` file is saved locally so subsequent runs are silent.

---

## Command-line options

```
usage: dashboard.py [-h] [--property URL] [--days N] [--min-clicks N] [--top N]

options:
  -h, --help        show this help message and exit
  --property URL    GSC property URL (overrides .env)
  --days N          Days in each comparison window (default: 90 ≈ 3 months)
  --min-clicks N    Min clicks to include a URL (default: 5)
  --top N           Max decaying pages to display (default: 50)
```

### Examples

```bash
# Standard 90-day (3-month) comparison, top 50 results
python dashboard.py

# Use a different property on the fly
python dashboard.py --property "https://blog.example.com/"

# 6-month window for deeper trend analysis
python dashboard.py --days 180

# Tighter window with noise filter and fewer rows
python dashboard.py --days 90 --min-clicks 10 --top 25
```

---

## Project structure

```
content-decay-dashboard/
├── dashboard.py          # CLI entry point
├── requirements.txt      # Pinned dependencies
├── .env.example          # Environment variable template
├── .gitignore
├── README.md
└── src/
    ├── __init__.py
    ├── auth.py           # OAuth2 authentication + token caching
    ├── gsc_client.py     # Search Console API wrapper
    ├── analyzer.py       # Decay detection + severity scoring
    └── display.py        # Rich terminal table renderer
```

---

## Severity scoring

| Signal | Max points |
|--------|-----------|
| Position drop ≥ 10 places | 30 |
| Position drop 5–9 places | 20 |
| Position drop 2–4 places | 10 |
| Fell off page 1 (was ≤10, now >10) | 10 |
| Page-1 keyword loss ≥ 50 % | 30 |
| Page-1 keyword loss 25–49 % | 20 |
| Any page-1 keyword lost | 10 |
| CTR decline ≥ 50 % | 20 |
| CTR decline 25–49 % | 12 |
| CTR decline 10–24 % | 6 |
| Click loss ≥ 50 % | 20 |
| Click loss 30–49 % | 13 |
| Click loss 15–29 % | 7 |

Severity is capped at **100**. Colors: red ≥ 60, yellow ≥ 35, dim yellow < 35.

---

## Security notes

- `credentials.json` and `token.json` are listed in `.gitignore` — **never commit them**.
- The tool requests the read-only scope (`webmasters.readonly`) only.
- Tokens are stored locally in `token.json` and refreshed automatically.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `FileNotFoundError: credentials.json not found` | Follow step 4 above to download credentials |
| `Access Not Configured` API error | Enable the Search Console API in Cloud Console (step 4.2) |
| `403 Forbidden` | Ensure your Google account has access to the GSC property |
| No data returned | GSC has a ~3-day data lag; try a property with active traffic |
| `redirect_uri_mismatch` | Make sure the credential type is *Desktop app*, not *Web application* |
