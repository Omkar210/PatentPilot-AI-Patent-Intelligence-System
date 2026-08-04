# Playbook — Executing Approach B (Local Docker + Render Cloud Backend)

This document provides step-by-step CLI commands and dashboard configurations to connect your Render backend to local Docker containers.

---

## 🛠️ Step 1: Ensure Local Docker Containers Are Running

Before starting the tunnels, verify that your containers are active on your local machine:

1. Open PowerShell / Command Prompt.
2. Start the services:
   ```bash
   cd "C:\Users\Omkar\Downloads\Patent Basic"
   docker-compose up -d
   ```
3. Run `docker ps` to verify that `postgres`, `neo4j`, and `qdrant` are running.

---

## 🌐 Step 2: Open Tunnels for Each Port (3 Terminals)

Open three separate Command Prompt / PowerShell windows and run one command in each:

### 1️⃣ Terminal 1: Expose PostgreSQL (Port 5432)
```bash
npx cloudflared tunnel --url tcp://localhost:5432
```
*Look for output lines similar to:*
`+------------------------------------------------------------+`
`|  tcp://your-postgres-tunnel.trycloudflare.com:12345        |`
`+------------------------------------------------------------+`
*Copy this public URL.*

### 2️⃣ Terminal 2: Expose Neo4j (Port 7687)
```bash
npx cloudflared tunnel --url tcp://localhost:7687
```
*Look for output lines similar to:*
`+------------------------------------------------------------+`
`|  tcp://your-neo4j-tunnel.trycloudflare.com:56789           |`
`+------------------------------------------------------------+`
*Copy this public URL.*

### 3️⃣ Terminal 3: Expose Qdrant (Port 6333)
```bash
npx cloudflared tunnel --url http://localhost:6333
```
*Look for output lines similar to:*
`+------------------------------------------------------------+`
`|  https://your-qdrant-tunnel.trycloudflare.com              |`
`+------------------------------------------------------------+`
*Copy this public URL.*

---

## 🔑 Step 3: Configure Environment Variables on Render

Go to your **Render Web Service Dashboard** ➔ **Environment** tab, and set/update the variables as follows:

| Environment Key | Value Format (Using your generated tunnel links) | Description |
|-----------------|--------------------------------------------------|-------------|
| **`DATABASE_URL`** | `postgresql://patentuser:patentpass@your-postgres-tunnel.trycloudflare.com:12345/patentmind_db` | Replace with your Terminal 1 host and port. |
| **`NEO4J_URI`** | `bolt://your-neo4j-tunnel.trycloudflare.com:56789` | Replace with your Terminal 2 host and port (change `tcp://` to `bolt://`). |
| **`QDRANT_HOST`** | `your-qdrant-tunnel.trycloudflare.com` | Replace with host name from Terminal 3 (no `https://`). |
| **`QDRANT_PORT`** | `443` | Set port to `443` (standard HTTPS port for Cloudflare). |

Click **Save Changes** on Render. The web service will redeploy and automatically connect to your local machine databases!
