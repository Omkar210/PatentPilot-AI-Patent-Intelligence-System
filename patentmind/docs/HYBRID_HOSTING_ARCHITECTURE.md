# PatentMind AI — Hybrid Backend & GPU Offloading Architecture

This document answers how to connect a cloud-hosted frontend (e.g., Vercel or Netlify) to your local or remote **Docker Engine** (Neo4j, Qdrant, Postgres) and **GPU Server** (Ollama Qwen3-4B / CDAC PARAM Shavak).

---

## 🧠 1. The Core Architecture Truth

When you deploy **only the frontend files** to Vercel/Netlify, the HTML/JS code is downloaded and executed inside the **user's web browser**.

The browser needs a **Public HTTPS URL** to talk to your FastAPI backend.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  CLOUD CDN LAYER                                                                        │
│  Vercel / Netlify / GitHub Pages (Hosts Static index.html)                             │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            │ HTTPS API Requests (`/api/query`, `/api/stats`)
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  PUBLIC TUNNEL GATEWAY                                                                  │
│  Cloudflare Tunnel / Ngrok (Public HTTPS Endpoint: `https://api.patentmind.com`)       │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  YOUR BACKEND & DOCKER ENGINE HOST (Local PC or Server)                                 │
│                                                                                         │
│  ┌───────────────────────────┐      ┌───────────────────────────┐                       │
│  │ FastAPI App (Port 8000)   │ ────▶│ Qdrant Vector DB (6333)   │                       │
│  └─────────────┬─────────────┘      └───────────────────────────┘                       │
│                │                                                                        │
│                ├───────────────────┐                                                    │
│                ▼                   ▼                                                    │
│  ┌───────────────────────────┐  ┌───────────────────────────┐                           │
│  │ Neo4j Knowledge Graph     │  │ SQLite / Postgres DB      │                           │
│  └───────────────────────────┘  └───────────────────────────┘                           │
└────────────────┬────────────────────────────────────────────────────────────────────────┘
                 │
                 │ SSH Tunnel / Local Network (`http://192.168.6.50:11434`)
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  GPU ENGINE HOST (CDAC PARAM Shavak / Local RTX GPU)                                    │
│  Ollama Serving Qwen3-4B / PaddleOCR CUDA Engine                                        │
│  (Auto-Fallback to Groq Cloud API if GPU is offline)                                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 2. Step-by-Step Workflow: How to Run the Entire System

To host the frontend on Vercel while keeping your Docker + GPU engines running:

### Step 1: Start Docker Engine & Services
On your local machine or backend server, start your databases:
```bash
# Start Docker Desktop, then launch containers
docker-compose up -d
```
*This starts Postgres, Neo4j, and Qdrant.*

### Step 2: Start GPU Engine (Ollama / Remote SSH)
If using your local GPU or remote CDAC PARAM Shavak GPU server:
```bash
# Start Ollama service on GPU host
ollama serve

# If GPU is on remote server (192.168.6.50), ensure SSH tunnel is open:
ssh -N -L 11434:localhost:11434 student15@192.168.6.50 -p 22
```

### Step 3: Start Master Python Services Orchestrator
```bash
python start_all_services.py
```
*This starts FastAPI on `http://localhost:8000`.*

### Step 4: Expose Backend to the Web via Cloudflare Tunnel (Free)
Run this single command to generate a public HTTPS URL for FastAPI:
```bash
npx cloudflared tunnel --url http://localhost:8000
```
*Output:*
```text
+-----------------------------------------------------------------------------------+
|  Your quick Tunnel has been created!                                             |
|  https://patentmind-api-demo.trycloudflare.com                                    |
+-----------------------------------------------------------------------------------+
```

### Step 5: Link Hosted Frontend to Public Tunnel URL
In `patentmind/frontend/dist/index.html`, set `API_BASE_URL` to your Cloudflare tunnel URL:
```javascript
const API_BASE_URL = 'https://patentmind-api-demo.trycloudflare.com';
```
Now, anyone visiting your Vercel site (`https://patentmind.vercel.app`) can use your live AI Query & Knowledge Graph powered by your Docker & GPU engines!

---

## 🚀 3. What Happens If Your Local GPU Server Is Powered Off?

PatentMind AI features a **Dual LLM Fallback Architecture** designed specifically for this:

1. If your GPU server (`192.168.6.50` / Ollama) is turned off or unavailable, the backend automatically catches the connection timeout in `< 0.1s`.
2. The `LLMRouter` diverts generative queries to **Groq Cloud API (`llama-3.3-70b`)**.
3. If Neo4j is offline, the backend switches to **Simulated SQL Graph Mode**.

> **Result**: Your Vercel website **NEVER CRASHES** even if your GPU server or Docker containers are offline!

---

## ☁️ 4. Fully Automated Cloud Option (Zero Local Running Hardware)

If you do NOT want your laptop running at all, you can host all backend services in the cloud:

| Service | Hosting Solution | Free Tier / Cost |
|---------|------------------|------------------|
| **Frontend** | Vercel / Netlify | 100% Free |
| **FastAPI Backend** | Render.com / Railway | Free Tier |
| **Databases (Qdrant & Postgres)** | Railway.app / Qdrant Cloud | Free Tier |
| **GPU Inference Engine** | CDAC Server (always-on) OR Groq Cloud API | Free Tier API |
