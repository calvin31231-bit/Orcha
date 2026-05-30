# Manager / Supervisor Agent

The Manager is the operations layer for the Shorts Orchestrator. It is designed to keep the system healthy without giving an AI unsafe control over your YouTube channels.

## What it does

- Checks required folders, configs, brand bibles, SQLite database, FFmpeg, Ollama, and configured local models.
- Validates recent prompt packets for missing handoff fields, rejected gates, and non-private upload settings.
- Summarizes recent runs, generated videos, blocked generations, and queue health.
- Can create safe missing folders and missing brand-bible skeletons when run with `--repair`.
- Creates daily debrief reports in `data/logs/manager_reports/`.
- Can pull YouTube Analytics into the learning loop when run with `--pull-analytics`.
- Scans configured vs installed Ollama models and gives upgrade recommendations.

## What it will not do by default

- It will not publicly publish generated videos.
- It will not bypass rejected compliance/originality gates.
- It will not silently switch AI models.
- It will not pull/install large models without your approval.
- It will not spend money or enable paid APIs without your approval.

## Commands

```powershell
# Health check only
python -m shorts_orchestrator.cli manager-check

# Health check and safe local repairs
python -m shorts_orchestrator.cli manager-check --repair

# Include an LLM smoke test for the Manager agent
python -m shorts_orchestrator.cli manager-check --smoke-test

# Daily debrief for all channels
python -m shorts_orchestrator.cli manager-debrief

# Daily debrief for one channel and pull YouTube Analytics
python -m shorts_orchestrator.cli manager-debrief --account ai_oddly_satisfying --pull-analytics

# Full supervise pass: health + debrief + model scan
python -m shorts_orchestrator.cli manager-supervise --account ai_oddly_satisfying --repair --pull-analytics

# Model upgrade scan
python -m shorts_orchestrator.cli manager-upgrade-scan
```

## Scheduling daily debriefs

Use Windows Task Scheduler to run something like this once per day:

```powershell
cd C:\path\to\shorts_orchestrator_app
.\.venv\Scripts\python.exe -m shorts_orchestrator.cli manager-supervise --pull-analytics
```

For early channels, keep public publishing manual. The Manager should generate reports and private candidates first, then you decide what goes public.

## Revenue/profit estimates

`config/revenue_tracking.yaml` lets you set rough RPM and cost assumptions per channel. If YouTube Analytics does not expose actual revenue yet, the Manager estimates revenue as:

```text
estimated revenue = views / 1000 * configured RPM
estimated profit = estimated revenue - configured video/daily costs
```

Leave RPM at `0.00` until you have real data or a conservative assumption. These estimates are planning numbers, not guaranteed earnings.
