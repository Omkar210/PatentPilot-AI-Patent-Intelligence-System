# Exposing Qdrant and Ollama (GPU / Local LLM) to Render Cloud Backend

This document explains how to expose Qdrant and Ollama when they run on your GPU server.

---

## 💡 The Tunnel Protocol Rule (TCP vs. HTTP)

- Databases that use custom binary protocols (**Postgres** on 5432, **Neo4j Bolt** on 7687) require **TCP Tunnels** (`tcp://...`).
- Services that run over standard web protocols (**Qdrant** on 6333, **Ollama** on 11434) are HTTP-based and use **HTTP Tunnels** (`http://...`).

---

## 🛠️ Step-by-Step CLI Commands to Expose Qdrant & Ollama

Open **two separate terminals** on your GPU server:

### 1️⃣ Terminal 1: Expose Ollama (Local LLM / Port 11434)
```bash
npx cloudflared tunnel --url http://localhost:11434
```
*Copy the generated HTTPS link (e.g. `https://your-ollama.trycloudflare.com`).*

### 2️⃣ Terminal 2: Expose Qdrant Vector DB (Port 6333)
```bash
npx cloudflared tunnel --url http://localhost:6333
```
*Copy the generated HTTPS link (e.g. `https://your-qdrant.trycloudflare.com`).*

---

## 🔑 Configure Render Environment Variables

Update the following keys in your **Render Web Service Dashboard** ➔ **Environment** tab:

| Environment Key | Value Format (Using your tunnel links) | Description |
|-----------------|----------------------------------------|-------------|
| **`OLLAMA_BASE_URL`** | `https://your-ollama.trycloudflare.com` | Complete HTTP link from Terminal 1. |
| **`QDRANT_HOST`** | `your-qdrant-tunnel.trycloudflare.com` | Host name from Terminal 2 (remove `https://`). |
| **`QDRANT_PORT`** | `443` | Set port to `443` (standard HTTP port for Cloudflare). |

Click **Save Changes** on Render. The cloud app will now successfully execute semantic vector searches and LLM generation using your local GPU resources!
