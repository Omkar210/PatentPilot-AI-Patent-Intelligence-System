# PatentMind AI — Automated 24/7 Startup & Background Execution Guide

This document explains how to eliminate manual command-line execution of `start_all_services.py` so your backend runs 100% automatically 24/7.

---

## ⚡ Quick Summary: Do You Have to Run It Manually?

- **If using Cloud Hosting (Render / Railway)** ➔ **NO!** 100% Automatic on cloud boot.
- **If running on CDAC GPU Server (`192.168.6.50`)** ➔ **NO!** Runs 24/7 in a background `systemd` service or `tmux` session.
- **If running on your Windows Laptop** ➔ **NO!** Automatically launches on Windows startup via Task Scheduler.

---

## 🛠️ How to Automate Backend Startup (Choose Your Method)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ METHOD 1: CLOUD HOSTING (RENDER / RAILWAY)                                             │
│ Zero manual steps. Render starts `python start_all_services.py` automatically on deploy. │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ METHOD 2: ALWAYS-ON HPC SERVER (CDAC PARAM SHAVAK)                                      │
│ Run via `nohup` or `tmux` on 192.168.6.50 so it stays alive even if your laptop closes.  │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ METHOD 3: WINDOWS AUTO-STARTUP (WINDOWS LAPTOP)                                         │
│ Add a 1-click shortcut to Windows `shell:startup` or Task Scheduler.                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ☁️ Method 1: Cloud Hosting on Render (100% Automatic)

When hosting on **Render.com** or **Railway.app**:

1. In Render Web Service settings, set **Start Command**:
   ```bash
   python start_all_services.py
   ```
2. Render automatically runs `start_all_services.py` 24/7 in the cloud whenever code is pushed.
3. You never need to open a terminal or run a manual script again!

---

## 🖥️ Method 2: Running 24/7 on CDAC GPU Server (`192.168.6.50`)

If you want your backend and GPU server running 24/7 without keeping your laptop open:

1. SSH into the CDAC server:
   ```bash
   ssh student15@192.168.6.50 -p 22
   ```
2. Start a persistent background session using `tmux` or `nohup`:
   ```bash
   # Option A: Using Tmux (Recommended)
   tmux new -s patentmind
   python start_all_services.py
   # Press Ctrl+B then D to detach (leaves it running 24/7)

   # Option B: Using nohup
   nohup python start_all_services.py > backend.log 2>&1 &
   ```

---

## 🪟 Method 3: Windows Startup Folder (Auto-Launch on Laptop Power On)

If running locally on Windows and you want it to launch automatically whenever your laptop turns on:

1. Press `Win + R`, type **`shell:startup`**, and press Enter.
2. Create a new text file named `start_patentmind.bat` inside that folder.
3. Paste the following script:
   ```bat
   @echo off
   cd /d "C:\Users\Omkar\Downloads\Patent Basic"
   start /min .venv\Scripts\python.exe start_all_services.py
   ```
4. Done! Every time Windows boots, `start_all_services.py` will launch silently in the background.
