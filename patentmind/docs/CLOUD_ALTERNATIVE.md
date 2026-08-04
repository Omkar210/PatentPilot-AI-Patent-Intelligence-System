# Playbook — Pure Cloud Deployment (No GPU Server Required)

This guide details how to host **PatentMind AI** completely in the cloud using **Groq API** and **Qdrant Cloud**, allowing your website to run 24/7 without needing local GPU or Docker tunnels.

---

## 🏛️ 1. Architecture Overview

```
┌───────────────────────────────────────┐
│     FRONTEND WEBSITE (Vercel)         │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│     BACKEND SERVICE (Render)          │
└─────────┬───────────────────┬─────────┘
          │                   │
          ▼                   ▼
┌───────────────────┐ ┌───────────────────┐
│  DATABASE (Render)│ │ VECTOR DB (Qdrant)│
│  PostgreSQL       │ │ Qdrant Cloud (Free│
│  (Managed Cloud)  │ │ Cluster / 1GB)    │
└───────────────────┘ └───────────────────┘
          │
          ▼
┌───────────────────────────────────────┐
│  INFERENCE ENGINE (Groq Cloud API)    │
│  Ultra-fast Llama-3.3-70b (Free Tier) │
└───────────────────────────────────────┘
```

---

## 🛠️ 2. Step-by-Step Setup

### Step 1: Create a Free Qdrant Cloud Cluster
1. Go to [cloud.qdrant.io](https://cloud.qdrant.io) and register for a free account.
2. Click **Create Cluster** ➔ Choose **Free Tier** (1GB storage, 0.5 CPU, 100% Free).
3. Once created, copy the following details from your cluster dashboard:
   - **Cluster Endpoint** (e.g. `https://xxxxxx.gcp.qdrant.io`)
   - **API Key** (e.g. `xyz123abc...`)

### Step 2: Push Your Patents to the Qdrant Cloud Cluster (One-Time)
Run a quick migration script on your local computer to upload your existing 30,000 vectors from local Qdrant to your new Qdrant Cloud cluster:
```bash
# Set environment variables in your local terminal
$env:QDRANT_HOST="xxxxxx.gcp.qdrant.io"
$env:QDRANT_PORT="443"
$env:QDRANT_API_KEY="your_qdrant_cloud_api_key"

# Run the ingestion script to populate the cloud cluster
python -m patentmind.embeddings.pipeline
```

### Step 3: Configure Render Environment Variables
In your **Render Web Service Dashboard** ➔ **Environment** tab, set the variables to connect directly to the cloud engines:

| Key | Value | Description |
|-----|-------|-------------|
| **`DATABASE_URL`** | *Your Render Postgres URL* | Stores metadata in Render's managed database. |
| **`QDRANT_HOST`** | `xxxxxx.gcp.qdrant.io` | Your Qdrant Cloud endpoint (remove `https://`). |
| **`QDRANT_PORT`** | `443` | Standard secure HTTPS port. |
| **`QDRANT_API_KEY`** | `your_qdrant_cloud_api_key` | Authorizes Render to access Qdrant Cloud. |
| **`GROQ_API_KEY`** | `your_groq_api_key` | Powers the chatbot using Groq Llama-3.3-70b. |

---

## 💎 Why This is the Best Option

1. **Zero Maintenance**: You don't need to keep your laptop on, run Docker commands, or manage SSH tunnels.
2. **Ultra-Fast Performance**: Groq API returns LLM answers in **< 1.5 seconds** (much faster than a local 3B model).
3. **100% Free**: All used cloud services (Vercel, Render, Qdrant Cloud, Groq) offer generous free tiers that cover our dataset size.
