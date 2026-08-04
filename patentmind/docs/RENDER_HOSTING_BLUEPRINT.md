# Codebase Changes & Configuration Blueprint for Render Hosting

This document details the exact changes made to the codebase to support hosting **PatentMind AI** on **Render.com** (Full Stack Deployment), alongside the necessary Render dashboard environment configuration.

---

## 🛠️ 1. Codebase Changes Performed

To make the application compatible with Render's hosting architecture, the following files have been modified:

### A. Dynamic PostgreSQL Scheme Fix
Render's managed PostgreSQL databases provision URLs starting with `postgres://`. SQLAlchemy requires `postgresql://`.
- **Modified File**: [`patentmind/db/session.py`](file:///c:/Users/Omkar/Downloads/Patent%20Basic/patentmind/db/session.py)
- **Modified File**: [`patentmind/db/alembic/env.py`](file:///c:/Users/Omkar/Downloads/Patent%20Basic/patentmind/db/alembic/env.py)
- **Change**: Added dynamic string replacement to convert the connection prefix automatically at runtime.

### B. Dynamic Port Binding
Render dynamically assigns a port to web services using the `PORT` environment variable (e.g. `PORT=10000`).
- **Modified File**: [`start_all_services.py`](file:///c:/Users/Omkar/Downloads/Patent%20Basic/start_all_services.py)
- **Change**: Updated the CLI port parser to read `PORT` from the environment:
  ```python
  port_default = int(os.getenv("PORT", "8000"))
  ```

### C. Primary Frontend Promotion to Root (`/`)
FastAPI now serves the production Terracotta theme frontend directly at the root URL if the production build folder is present.
- **Modified File**: [`patentmind/api/main.py`](file:///c:/Users/Omkar/Downloads/Patent%20Basic/patentmind/api/main.py)
- **Change**: Checked for the existence of `frontend/dist/index.html` at `/` before falling back to the developer dashboard page.

---

## 🚀 2. Step-by-Step Render Deployment Guide

Follow these steps to host your backend and frontend together on Render:

### Step 1: Push Code to GitHub
Ensure all changes are pushed to your repository:
```bash
git add .
git commit -m "Configure codebase for Render PostgreSQL and Port binding"
git push origin main
```

### Step 2: Create a PostgreSQL Database on Render
1. Go to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** ➔ **PostgreSQL**.
3. Name your database (e.g., `patentmind-db`).
4. Keep the defaults and click **Create Database**.
5. Once active, copy the **Internal Database URL** (e.g. `postgres://user:pass@host/db`).

### Step 3: Create a Web Service on Render
1. Click **New +** ➔ **Web Service**.
2. Select your repository: `Omkar210/PatentPilot-AI-Patent-Intelligence-System`.
3. Configure settings:
   - **Name**: `patentmind-service`
   - **Language**: `Python`
   - **Root Directory**: `patentmind` (or blank if deploying from the root folder)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python start_all_services.py`

### Step 4: Configure Environment Variables
In the **Environment** tab of your Render Web Service, add the following variables:

| Key | Value | Description |
|-----|-------|-------------|
| **`DATABASE_URL`** | `postgres://user:password@host/dbname` | Render database URL copied in Step 2 |
| **`OLLAMA_BASE_URL`**| `http://127.0.0.1:11434` | Point to your local server / GPU node |
| **`GROQ_API_KEY`** | `your_groq_api_key` | Enables auto-fallback if GPU goes offline |
| **`NEO4J_URI`** | `bolt://localhost:7687` | Link to your Neo4j Graph DB |
| **`NEO4J_PASSWORD`** | `patentpilot123` | Password matching your container/DBMS |

Click **Save Changes** and deploy!
