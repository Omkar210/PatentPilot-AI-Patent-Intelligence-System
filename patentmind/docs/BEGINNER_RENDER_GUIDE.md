# Beginner's Guide: Deploying PatentMind AI on Render

This guide provides a detailed, click-by-click walkthrough for beginners to deploy the **PatentMind AI** full-stack application on **Render.com**.

---

## 🛠️ Step 2: Creating Your Web Service on Render

A **Web Service** on Render is a virtual computer running in the cloud that will host your Python FastAPI backend and serve your frontend website 24/7.

### 1. Log In to Render
1. Go to [dashboard.render.com](https://dashboard.render.com).
2. If you don't have an account, click **Sign Up** and choose **GitHub** (this links your code repository directly).

### 2. Start a New Web Service
1. On your Render dashboard dashboard, click the blue **`New +`** button in the top right corner.
2. Select **`Web Service`** from the dropdown menu.

---

## 🐙 Step 3: Connecting Your GitHub Repository

Render builds your application by pulling the code directly from your GitHub account.

1. You will see a list of your GitHub repositories under **Connect a repository**.
2. Find the repository named: `PatentPilot-AI-Patent-Intelligence-System` (or your project repository name).
3. Click the blue **`Connect`** button next to it.

---

## ⚙️ Step 4: Configuring the Web Service Settings

Now, fill in the configuration details. Here is what each setting means and what you need to type:

1. **Name**: Type `patentmind-app` (this will form your website URL, e.g., `https://patentmind-app.onrender.com`).
2. **Region**: Select the region closest to you (e.g., **Singapore** or **Oregon**) for faster page load times.
3. **Branch**: Select `main` (this is the primary branch containing your latest code).
4. **Root Directory**: Leave this **blank** (or type `patentmind` if your repository only contains the patentmind subfolder).
5. **Runtime**: Select **`Python`** (since our FastAPI server is built with Python).
6. **Build Command**: 
   This tells Render to install all the Python libraries (like FastAPI, SQLAlchemy, PyMuPDF) required by our project. Type:
   ```bash
   pip install -r requirements.txt
   ```
7. **Start Command**:
   This tells Render how to launch our server program. Type:
   ```bash
   python start_all_services.py
   ```
8. **Instance Type**: Select the **Free** tier (this is perfect for testing and prototyping!).

---

## 🔑 Step 5: Setting Up Environment Variables

Environment variables are secure configurations (like database credentials and API keys) that your code reads at runtime without hardcoding them into the files.

1. Scroll down and click the **`Advanced`** button.
2. Click **`Add Environment Variable`** for each of the following settings:

| Key (Name) | Value (What to paste) | Why it is needed |
|------------|-----------------------|------------------|
| **`DATABASE_URL`** | *Paste your Render Postgres database URL* (e.g. `postgres://user:pass@host/db`) | Directs the app to store metadata in your cloud Postgres database instead of local SQLite. |
| **`GROQ_API_KEY`** | *Paste your Groq API key* | Enables fallback LLM support so the app works even when your local GPU server is off. |
| **`OLLAMA_BASE_URL`** | `http://127.0.0.1:11434` | The endpoint where Ollama runs (local/tunnel). |
| **`NEO4J_URI`** | `bolt://localhost:7687` | Connects the app to the Neo4j Knowledge Graph container. |
| **`NEO4J_PASSWORD`** | `patentpilot123` | Password matching your Neo4j database authentication. |

---

## 🚀 Step 6: Deploy & Verify Your App

1. Scroll to the bottom of the page and click the blue **`Create Web Service`** button.
2. Render will start building your application. You will see a live terminal console under **Logs** showing the progress.
3. Once you see **`Uvicorn running on http://0.0.0.0:10000`** and status changes to **`Live`** (with a green checkmark):
   - Click the live link generated at the top left of the page (e.g., `https://patentmind-app.onrender.com`).
4. **Success!** Your website is now live and accessible to anyone on the internet.
