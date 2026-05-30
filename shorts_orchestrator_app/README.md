# Local YouTube Shorts Orchestrator


## Animated Command Center HUD

The Streamlit front end now includes an animated **Shorts Orchestrator Command Center** view based on the approved 8-bit space-station concept art.

Launch it with:

```powershell
launch_dashboard.bat
```

or:

```powershell
streamlit run dashboard.py
```

The HUD uses the bundled asset at `assets/command_center_hud.png`, adds animated scanlines/glow overlays, and surfaces live queue, manager, video, analytics, and channel-routing data from the local SQLite database.


A local-first multi-agent workflow for planning, generating, reviewing, uploading, and tracking YouTube Shorts. It is built to keep costs low by using Ollama locally, with optional OpenAI/Anthropic API keys for stronger review and planning.

## New AI-generated workflow

The app now supports your requested chain:

```text
AI#1 Trend Scout
  -> AI#2 Prompt Engineer
  -> AI#3 Video Generator Prompt Packet
  -> AI#4 Policy/Monetization Reviewer
  -> AI#5 Channel Router
  -> Private upload queue
```

For real AI video generation, the app can queue a local ComfyUI workflow. For testing, the `mock` provider creates a placeholder MP4 so you can verify the pipeline without running a video model.

## What this app is designed to do

- Scan public YouTube signals through official APIs, not scraping.
- Turn trend patterns into original AI video ideas.
- Generate prompt packets for text-to-video systems.
- Queue local ComfyUI generation for Wan/LTX/Hunyuan-style workflows.
- Run a monetization/TOS risk review before upload.
- Route content to the best configured channel.
- Upload to YouTube as **private by default**.
- Pull basic analytics after posting.

## What it is not designed to do

- It does not scrape TikTok/YouTube/Instagram and repost other people's content.
- It does not bypass copyright, Content ID, or YouTube monetization policies.
- It does not guarantee virality or monetization.
- It does not auto-publish public videos without your approval.

## Fast setup on Windows

### 1. Install Python
Install Python 3.11 or 3.12 from https://www.python.org/downloads/ and check "Add Python to PATH" during install.

### 2. Install FFmpeg
Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/ and add the `bin` folder to PATH.

Test:

```powershell
ffmpeg -version
```

### 3. Install Ollama
Download Ollama from https://ollama.com/download.

Then in PowerShell:

```powershell
ollama pull qwen2.5:7b
ollama pull llama3.1:8b
```

### 4. Create virtual environment

```powershell
cd shorts_orchestrator_app
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 5. Test the AI-generated chain without YouTube API

```powershell
python -m shorts_orchestrator.cli ai-chain --account ai_oddly_satisfying --query "cozy impossible machines" --no-youtube
```

### 6. Test with a placeholder generated video

```powershell
python -m shorts_orchestrator.cli ai-chain --account ai_oddly_satisfying --query "cozy impossible machines" --no-youtube --generate --provider mock
```

### 7. Use real AI video generation through ComfyUI

Read `AI_GENERATED_SHORTS_SETUP.md`, then replace `config/comfyui_text_to_video_workflow.json` with your exported API workflow.

Queue generation:

```powershell
python -m shorts_orchestrator.cli ai-chain --account ai_oddly_satisfying --query "cozy impossible machines" --generate --provider comfyui --workflow config/comfyui_text_to_video_workflow.json
```

### 8. YouTube API setup

1. Go to Google Cloud Console.
2. Create a project.
3. Enable **YouTube Data API v3** and **YouTube Analytics API**.
4. Configure OAuth consent screen.
5. Create OAuth Client ID for Desktop App.
6. Download the JSON file and save it as:

```text
config/client_secret.json
```

Then authenticate:

```powershell
python -m shorts_orchestrator.cli auth-youtube
```

### 9. Upload privately

```powershell
python -m shorts_orchestrator.cli upload --file data/outputs/example.mp4 --title "Test Upload" --description "Private test upload" --account ai_oddly_satisfying
```

Uploads are private by default. Review in YouTube Studio before changing visibility.

## Folder structure

```text
config/                 Model, channel, generator, and policy config
shorts_orchestrator/    App source code
data/inputs/            Authorized raw footage you own or can use
data/outputs/           Prompt packets, generated clips, output files
data/logs/              Run logs
data/db/                SQLite database
```


## Added success/safety upgrades

This build now includes:

- `config/brand_bibles/*.brand_bible.yaml` per channel.
- Idea scoring before video generation.
- Pre-generation compliance gate before GPU time is spent.
- Prompt/version logs in `data/logs/prompt_versions/`.
- Hard private-upload metadata default for generated packets.
- Analytics learning loop through `learn-analytics`.
- Repetition/originality checker against prior runs.
- Narration Director agent and local voiceover providers: `mock`, `windows_sapi`, and `piper`.
- `daily-batch` command for safe daily candidate creation.

Read `VOICEOVER_AND_DAILY_POSTING.md` for the recommended posting cadence and voiceover setup.

## Manager / Supervisor Agent

This build includes a Manager agent that supervises the production system. It checks configuration, model availability, agent handoff packets, queue health, daily run counts, analytics learning, and model-upgrade recommendations.

Common commands:

```powershell
python -m shorts_orchestrator.cli manager-check
python -m shorts_orchestrator.cli manager-check --repair
python -m shorts_orchestrator.cli manager-debrief --pull-analytics
python -m shorts_orchestrator.cli manager-supervise --repair --pull-analytics
python -m shorts_orchestrator.cli manager-upgrade-scan
```

Reports are saved to `data/logs/manager_reports/`. The Manager is intentionally conservative: public posting, model switching, paid API use, and compliance bypasses still require your approval.


## If setup_windows.ps1 closes instantly

Use `run_setup_debug.bat` instead. It runs the setup script with PowerShell execution bypass, keeps the window open, and writes the full output to `setup_log.txt`.

You can also run setup manually from PowerShell:

```powershell
cd "C:\path	o\shorts_orchestrator_app"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1
```
