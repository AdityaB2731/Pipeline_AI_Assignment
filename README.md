# Pipeline AI — Integrations Technical Assessment

A full-stack integration platform built with **React** (frontend) and **FastAPI** (backend). This project implements OAuth-based connections to third-party services and loads normalized integration items from each provider.

The primary deliverable for this assessment is the **HubSpot integration** — OAuth flow (Part 1) and CRM data loading (Part 2).

---

## Work Completed

### Part 1: HubSpot OAuth Integration

**Backend** (`backend/integrations/hubspot.py`)

| Function | Description |
|----------|-------------|
| `authorize_hubspot` | Builds the HubSpot OAuth URL, generates a CSRF-safe state token, and stores it in Redis |
| `oauth2callback_hubspot` | Handles the OAuth redirect, exchanges the authorization code for tokens, and stores credentials in Redis |
| `get_hubspot_credentials` | Retrieves and clears stored credentials after the frontend OAuth popup closes |

**Frontend**

- `frontend/src/integrations/hubspot.js` — Connect button, OAuth popup flow, and credential handoff
- `frontend/src/integration-form.js` — HubSpot added to the integration type dropdown
- `frontend/src/data-form.js` — Load Data wired to the HubSpot `/load` endpoint

**API routes** (`backend/main.py`)

- `POST /integrations/hubspot/authorize`
- `GET  /integrations/hubspot/oauth2callback`
- `POST /integrations/hubspot/credentials`
- `POST /integrations/hubspot/load`

### Part 2: Loading HubSpot Items

**Backend** (`get_items_hubspot`)

- Uses OAuth credentials to query the HubSpot CRM v3 API
- Fetches **Contacts**, **Companies**, and **Deals**
- Maps each record to the shared `IntegrationItem` model with meaningful display names:
  - Contacts → first name + last name (falls back to email)
  - Companies → company name
  - Deals → deal name
- Prints results to the backend console and returns them to the frontend

### Additional Improvements

- Environment variables loaded via `python-dotenv` from `backend/.env`
- Redis client configured with `decode_responses=True` for reliable string handling
- OAuth scopes and redirect URIs properly URL-encoded
- Clear error messages when required env vars are missing
- `backend/.env.example` provided as a safe template (no secrets committed)

---

## Architecture

```
┌─────────────┐     authorize      ┌─────────────┐     OAuth      ┌─────────┐
│   React UI  │ ─────────────────► │   FastAPI   │ ─────────────► │ HubSpot │
│  (port 3000)│                    │  (port 8000)│ ◄───────────── │         │
└─────────────┘     credentials    └──────┬──────┘    callback    └─────────┘
       │                                  │
       │         load (access token)      │  state + credentials
       └──────────────────────────────────┤
                                          ▼
                                    ┌──────────┐
                                    │  Redis   │
                                    └──────────┘
```

Each integration follows the same four-step pattern used by Airtable and Notion:

1. **Authorize** — frontend requests an OAuth URL
2. **Callback** — provider redirects back; backend stores tokens in Redis
3. **Credentials** — frontend fetches tokens after the popup closes
4. **Load** — frontend sends credentials; backend fetches and returns `IntegrationItem` objects

---

## Prerequisites

- **Node.js** 16+ and npm
- **Python** 3.10+
- **Redis** — must be running locally

---

## Environment Setup

Secrets and configuration live in `backend/.env`. This file is **gitignored** and must never be committed or included in submission ZIPs.

### Step 1: Copy the example file

From the project root:

```bash
cp backend/.env.example backend/.env
```

On Windows (PowerShell):

```powershell
Copy-Item backend\.env.example backend\.env
```

### Step 2: Fill in your values

Open `backend/.env` and replace the placeholder values:

```env
REDIS_HOST=localhost

# Required for the assessment
HUBSPOT_CLIENT_ID=your_actual_hubspot_client_id
HUBSPOT_CLIENT_SECRET=your_actual_hubspot_client_secret

# Optional — only needed if testing Notion or Airtable
AIRTABLE_CLIENT_ID=your_airtable_client_id
AIRTABLE_CLIENT_SECRET=your_airtable_client_secret
NOTION_CLIENT_ID=your_notion_client_id
NOTION_CLIENT_SECRET=your_notion_client_secret
```

| Variable | Required | Description |
|----------|----------|-------------|
| `REDIS_HOST` | Yes | Redis server hostname (use `localhost` for local dev) |
| `HUBSPOT_CLIENT_ID` | **Yes** | OAuth Client ID from your HubSpot developer app |
| `HUBSPOT_CLIENT_SECRET` | **Yes** | OAuth Client Secret from your HubSpot developer app |
| `AIRTABLE_CLIENT_ID` | No | Only if testing Airtable (create your own OAuth app) |
| `AIRTABLE_CLIENT_SECRET` | No | Only if testing Airtable |
| `NOTION_CLIENT_ID` | No | Only if testing Notion |
| `NOTION_CLIENT_SECRET` | No | Only if testing Notion |

### Step 3: Configure HubSpot OAuth app

In the [HubSpot Developer Portal](https://developers.hubspot.com/):

1. Create an OAuth app (or use an existing one).
2. Set the **Redirect URL** to exactly:
   ```
   http://localhost:8000/integrations/hubspot/oauth2callback
   ```
3. Enable these scopes:
   - `oauth`
   - `crm.objects.contacts.read`
   - `crm.objects.companies.read`
   - `crm.objects.deals.read`
4. Copy the Client ID and Client Secret into `backend/.env`.

> **Important:** Do not rename variables in `.env`. The backend reads exact key names such as `HUBSPOT_CLIENT_ID`. Quotes around values are optional; do not commit the real `.env` file.

---

## Running the Application

Use **three separate terminals**.

### Terminal 1 — Redis

```bash
redis-server
```

Verify Redis is running:

```bash
redis-cli ping
# Expected: PONG
```

### Terminal 2 — Backend

```bash
cd backend

# Create and activate a virtual environment (recommended)
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```

Backend runs at `http://localhost:8000`.

### Terminal 3 — Frontend

```bash
cd frontend
npm install
npm run start
```

Frontend runs at `http://localhost:3000`.

---

## Testing the HubSpot Integration

1. Open `http://localhost:3000`.
2. Leave **User** and **Organization** as defaults (or set your own).
3. Select **HubSpot** from **Integration Type**.
4. Click **Connect to HubSpot**.
5. Authorize in the popup; it closes automatically.
6. Confirm the button shows **HubSpot Connected**.
7. Click **Load Data** — contacts, companies, and deals appear as JSON in the UI.
8. Check the backend terminal for the printed `list_of_integration_item_metadata` log.

---

## Project Structure

```
Pipeline AI Assignment/
├── backend/
│   ├── integrations/
│   │   ├── hubspot.py          # HubSpot OAuth + data loading (assessment focus)
│   │   ├── airtable.py         # Reference integration
│   │   ├── notion.py           # Reference integration
│   │   └── integration_item.py # Shared data model
│   ├── main.py                 # FastAPI routes
│   ├── redis_client.py         # Redis helpers
│   ├── requirements.txt
│   ├── .env.example            # Template — copy to .env and fill in
│   └── .env                    # Local secrets (gitignored, do not submit)
├── frontend/
│   └── src/
│       ├── integrations/
│       │   ├── hubspot.js      # HubSpot connect UI
│       │   ├── airtable.js
│       │   └── notion.js
│       ├── integration-form.js # Integration selector
│       └── data-form.js        # Load Data UI
└── README.md
```

---

## Design Decisions

- **Pattern consistency** — HubSpot mirrors the existing Airtable/Notion four-function structure so new integrations stay predictable.
- **Temporary credential storage** — OAuth state and tokens live in Redis with TTL expiry; credentials are deleted after one-time retrieval by the frontend.
- **CSRF protection** — Random state token stored in Redis and validated on callback.
- **Normalized output** — All providers return the same `IntegrationItem` shape regardless of source API differences.
- **Secrets management** — All keys and IDs come from `backend/.env`; `.env.example` documents required variables without exposing real values.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `CLIENT_ID is missing` | Copy `.env.example` → `.env` and set HubSpot credentials |
| OAuth redirect error | Redirect URI in HubSpot app must match exactly: `http://localhost:8000/integrations/hubspot/oauth2callback` |
| `No HubSpot credentials found` | Complete OAuth in the popup before it closes; ensure Redis is running |
| Redis connection error | Start `redis-server` and confirm `REDIS_HOST=localhost` in `.env` |
| Empty Load Data | HubSpot account may have no CRM records; sample contacts appear in new developer accounts |
| Airtable invalid credentials | Original repo credentials were redacted — create your own Airtable OAuth app |
| Notion returns nothing | Share pages with your Notion integration under **Connections**, then reconnect |

---
Reviewers should copy `.env.example` to `.env`, add their own HubSpot OAuth credentials, and follow the run instructions above.
