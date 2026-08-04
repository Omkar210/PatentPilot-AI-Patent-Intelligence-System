# Exposing Local Docker Containers (Postgres, Neo4j, Qdrant) to the Cloud

This guide answers how to connect cloud services to local Docker containers and how Neo4j/Postgres can be accessed remotely.

---

## 💡 The Core Networking Concept

When your backend runs on **Render.com** (in the cloud), it cannot access `localhost` or `127.0.0.1` to connect to your databases. To Render, `localhost` refers to Render's own cloud server, not your laptop.

There are **two ways** to handle this:

```
───────────────────────────────────────────────────────────────────────────────────
APPROACH A: LOCAL HYBRID (EASIEST & RECOMMENDED)
Only the frontend is on the cloud (Vercel). The backend + Docker run locally on your laptop.
- Expose ONLY port 8000 using Cloudflare Tunnel.
- Backend accesses Postgres, Qdrant, and Neo4j on `localhost` naturally.

APPROACH B: FULL CLOUD BACKEND (RENDER) CONNECTING TO LOCAL DOCKER
The backend is on Render. Docker containers run locally on your laptop.
- Expose port 5432 (Postgres), 6333 (Qdrant), and 7687 (Neo4j) to the public internet using tunnels.
- Update Render environment variables with these public tunnel URLs.
───────────────────────────────────────────────────────────────────────────────────
```

---

## 🚀 Approach A: Local Hybrid Setup (Easiest & Free)

Instead of hosting the backend on Render, you run the backend locally on your laptop (which has direct access to local Docker containers) and expose only port 8000 to your Vercel frontend.

1. **Start Docker Containers locally**:
   ```bash
   docker-compose up -d
   ```
   *Postgres (5432), Neo4j (7687), and Qdrant (6333) are now active on your laptop.*

2. **Start FastAPI Backend locally**:
   ```bash
   python start_all_services.py
   ```
   *FastAPI connects to local Docker containers directly over `localhost` without any cloud setup.*

3. **Expose FastAPI to the web**:
   ```bash
   npx cloudflared tunnel --url http://localhost:8000
   ```
4. **Link Vercel Frontend**:
   Set `API_BASE_URL` in `index.html` on Vercel to the generated Cloudflare URL (e.g. `https://xxxx.trycloudflare.com`).

---

## 🌐 Approach B: Exposing Local Docker Ports to Render Backend

If you want the FastAPI backend hosted on Render, you must expose your local Docker ports so Render can reach them.

### 1. How to Expose Local Docker Ports (Postgres, Qdrant, Neo4j)

Run separate Cloudflare tunnels on your local machine for each container port:

```bash
# Terminal 1: Expose local Postgres (5432)
npx cloudflared tunnel --url tcp://localhost:5432

# Terminal 2: Expose local Neo4j Bolt (7687)
npx cloudflared tunnel --url tcp://localhost:7687

# Terminal 3: Expose local Qdrant (6333)
npx cloudflared tunnel --url http://localhost:6333
```
*Each command will generate a public address (e.g., `tcp://xxx.trycloudflare.com:12345` or `https://yyy.trycloudflare.com`).*

---

### 2. Update Render Environment Variables

Update the variables in the Render Dashboard with the generated public tunnel URLs:

| Key | Value (Example Public Tunnel URL) | Description |
|-----|-----------------------------------|-------------|
| **`DATABASE_URL`** | `postgresql://patentuser:patentpass@xxx.trycloudflare.com:12345/patentmind_db` | Points Render to your local Docker Postgres |
| **`NEO4J_URI`** | `bolt://xxx.trycloudflare.com:23456` | Points Render to your local Docker Neo4j |
| **`QDRANT_HOST`** | `yyy.trycloudflare.com` | Points Render to your local Docker Qdrant |
