# PatentMind AI — Frontend Deployment & Hosting Guide

This guide details how to publish the **PatentMind AI** frontend to free, high-performance hosting platforms considering all architectural facts of the project.

---

## 🏛️ Project Architecture Facts & Hosting Options

Our frontend is a **Single-Page Application (SPA)** located at `patentmind/frontend/dist/index.html` built with Vanilla HTML5, CSS3, and JavaScript.

There are **two main hosting strategies**:

```
───────────────────────────────────────────────────────────────────────────────────
OPTION 1: DECOUPLED DEPLOYMENT (RECOMMENDED FOR SPEED & CDN)
┌───────────────────────────────────────┐        API Requests (`/api/*`)
│  Frontend (Vercel / Netlify / GitHub) │ ─────────────────────────────┐
│  Global CDN · HTTPS · Free Tier       │                              │
└───────────────────────────────────────┘                              ▼
                                                    ┌───────────────────────────────┐
                                                    │  FastAPI Backend              │
                                                    │  Render / Railway / GPU Server│
                                                    └───────────────────────────────┘

OPTION 2: ALL-IN-ONE SINGLE SERVER DEPLOYMENT
┌───────────────────────────────────────────────────────────────────────────────────┐
│  Render / Railway / AWS / Docker                                                  │
│  FastAPI Backend serves backend APIs AND mounts `index.html` on port 8000         │
└───────────────────────────────────────────────────────────────────────────────────┘
───────────────────────────────────────────────────────────────────────────────────
```

---

## 🏆 Top Hosting Platforms Comparison

| Platform | Best For | Price | Deployment Method | Key Advantage |
|----------|----------|-------|-------------------|---------------|
| **Vercel** 🥇 | **Static Frontend (Decoupled)** | **100% Free** | GitHub auto-deploy or Vercel CLI | Instant deployment, global CDN, free SSL |
| **Netlify** 🥈 | **Static Frontend (Drag & Drop)** | **100% Free** | Drag & drop folder or GitHub | Simple setup, custom domain support |
| **GitHub Pages** | **Zero-Cost Repository Hosting** | **100% Free** | GitHub Actions / `dist` branch | Built into your existing GitHub repository |
| **Render.com** 🥉 | **Full-Stack (Backend + Frontend)** | **Free Tier** | Docker / GitHub repo | Deploys Python FastAPI + Static Frontend together |
| **Railway.app** | **Production Full-Stack Container** | **$5 free credit**| Docker Compose / GitHub | Runs Qdrant + FastAPI + Postgres seamlessly |

---

## 🛠️ Step-by-Step Deployment Instructions

### 1️⃣ Updating API Endpoint Configuration (`index.html`)

Before deploying to Vercel/Netlify/GitHub Pages, update the API fetching logic in `patentmind/frontend/dist/index.html` so frontend requests automatically route to your backend URL when hosted live:

```javascript
// At the top of <script> tag in index.html:
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : 'https://your-backend-api.onrender.com'; // Replace with your live backend API URL

async function apiFetch(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`API Error ${response.status}`);
    return await response.json();
}
```

---

### 🚀 Deploy Option A: Vercel (Recommended — Free & Fast)

Vercel is the fastest, most reliable platform for static web applications.

#### Method 1: Using Vercel CLI (30 Seconds)
```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Navigate to frontend dist directory
cd "C:\Users\Omkar\Downloads\Patent Basic\patentmind\frontend\dist"

# 3. Deploy
vercel
```
*Follow the prompts (accept defaults). Vercel will output your live URL (e.g. `https://patentmind-ai.vercel.app`).*

#### Method 2: Via GitHub Repo
1. Go to [vercel.com](https://vercel.com) and log in with GitHub.
2. Click **Add New Project** ➔ Select your repository (`PatentPilot-AI-Patent-Intelligence-System`).
3. Set **Root Directory** to: `patentmind/frontend/dist`.
4. Click **Deploy**!

---

### 📦 Deploy Option B: Netlify (Drag & Drop — No CLI Required)

1. Go to [app.netlify.com/drop](https://app.netlify.com/drop).
2. Open File Explorer on Windows and navigate to:
   `C:\Users\Omkar\Downloads\Patent Basic\patentmind\frontend\dist`
3. **Drag and drop** the `dist` folder into the Netlify drop zone.
4. Netlify will generate a live HTTPS link in 5 seconds (e.g., `https://patentmind.netlify.app`).

---

### 🐙 Deploy Option C: GitHub Pages (Free with Repository)

1. Push your latest code to GitHub:
   ```bash
   git add .
   git commit -m "Deploy frontend to GitHub Pages"
   git push origin main
   ```
2. Go to your GitHub Repository settings:
   `https://github.com/Omkar210/PatentPilot-AI-Patent-Intelligence-System` ➔ **Settings** ➔ **Pages**.
3. Under **Build and deployment**:
   - Source: **Deploy from a branch**
   - Branch: `main`
   - Folder: `/patentmind/frontend/dist` (or root `/docs`)
4. Save — GitHub will publish your site at `https://omkar210.github.io/PatentPilot-AI-Patent-Intelligence-System/`.

---

### 🐳 Deploy Option D: Full-Stack on Render (Backend + Frontend Together)

If you want **one single platform** running both your FastAPI backend and static frontend:

1. Create a free account on [render.com](https://render.com).
2. Click **New +** ➔ **Web Service**.
3. Connect your GitHub repository: `Omkar210/PatentPilot-AI-Patent-Intelligence-System`.
4. Configure service settings:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn patentmind.api.main:app --host 0.0.0.0 --port 10000`
5. Render will host your full platform on a single HTTPS URL!

---

## ⚡ How to Expose Local/GPU Backend to Live Hosted Frontend (Testing)

If your frontend is live on Vercel (`https://patentmind.vercel.app`) but your FastAPI backend is running locally on your laptop or GPU server (`192.168.6.50`):

### Using Cloudflare Tunnel / Ngrok (Free Public URL for Backend)
```bash
# Option 1: Cloudflare Tunnel (Recommended - No signup required)
npx cloudflared tunnel --url http://localhost:8000

# Option 2: Ngrok
ngrok http 8000
```
*Copy the generated HTTPS URL (e.g. `https://random-subdomain.trycloudflare.com`) and set it as your `API_BASE_URL` in `index.html`.*

---

## 📋 Recommended Action Plan

1. **Host Frontend**: Use **Vercel** or **Netlify** for free static CDN hosting.
2. **Host Backend**: Use **Render** or **Railway** (or local GPU with Cloudflare Tunnel).
3. **CORS Handling**: Backend (`patentmind/api/main.py`) already has `CORSMiddleware` configured with `allow_origins=["*"]`, allowing requests from any frontend URL!
