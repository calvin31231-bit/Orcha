# Recommended AI Agents and Model Routing

## Requested automated chain

| Stage | Agent | Job | Default model |
|---|---|---|---|
| AI#1 | Trend Scout | Scans trend patterns and extracts safe/original angles | Ollama `qwen2.5:7b` |
| AI#2 | Prompt Engineer | Converts trends into original concepts and avoids copied/IP-risk ideas | Ollama `qwen2.5:7b` |
| AI#3 | Video Generator | Produces a text-to-video prompt packet and sends it to ComfyUI or another generator | Ollama `qwen2.5:7b` + ComfyUI |
| AI#4 | Video Reviewer | Reviews prompt/video metadata for monetization/TOS risk | Ollama first, Claude/OpenAI optional |
| AI#5 | Channel Router | Chooses the best configured channel or manual_review | Ollama `qwen2.5:7b` |
| Human | Final Publisher | Reviews private upload and publishes/schedules | Calvin |

## Cost-minimized model choices

| Agent | Primary choice | Why |
|---|---|---|
| Manager | Ollama `qwen2.5:7b` | Free local planning, structured enough for simple workflows |
| Trend Scout | Ollama `qwen2.5:7b` | Good low-cost pattern analysis |
| Prompt Engineer | Ollama `qwen2.5:7b` | Good instruction following for safe prompts |
| Scriptwriter | Ollama `llama3.1:8b` | Natural short-form writing, free local |
| Video Generator | Ollama `qwen2.5:7b` + ComfyUI | Text-to-video prompt generation and local render queue |
| Compliance Reviewer | Ollama locally, Claude/OpenAI when budget allows | Conservative policy reasoning is important |
| Critic/QA | Ollama locally, Claude/OpenAI when budget allows | Finds flaws and repeated/template risk |

## Suggested paid upgrades when budget allows

- Use OpenAI for Manager/final synthesis when you need stronger structured outputs.
- Use Claude for Compliance and Critic when reviewing copyright, monetization, or long prompt packets.
- Keep Ollama for cheap drafts, brainstorming, summaries, and local privacy.

## Hard rule

No agent can publish public videos, schedule public videos, spend money, clone real people, or reuse third-party clips without your manual approval.


## Added agents in this version

| Agent | Job | Default model |
|---|---|---|
| Idea Scorer | Scores hook, novelty, loop potential, brand fit, safety, and effort before generation | Ollama `qwen2.5:7b` |
| Preflight Compliance | Blocks risky ideas before video generation | Ollama `qwen2.5:7b` |
| Narration Director | Builds original voiceover script, timed beats, caption lines, and SFX cues | Ollama `llama3.1:8b` |
| Originality Checker | Compares each new idea against recent output to avoid repetitive/mass-produced content | Ollama `qwen2.5:7b` |
| Analytics Agent | Converts YouTube Analytics into future prompt lessons | Ollama `qwen2.5:7b` |
| Scheduler | Creates daily candidate batches within safe posting guardrails | Ollama `qwen2.5:7b` |

## Operations Manager Agent

**Agent key:** `ops_manager`

The Operations Manager is responsible for keeping the whole system coordinated:

- Verifies required tools, folders, configs, model routes, and brand bibles.
- Checks whether agents are producing complete prompt packets with required fields.
- Detects rejected gates, unsafe privacy settings, or blocked generations.
- Creates daily debriefs with run counts, channel notes, analytics, and next actions.
- Compares configured Ollama models against installed models.
- Recommends upgrades and A/B tests without silently switching production models.

The Manager may apply safe repairs with `--repair`, but only for local structure problems like missing folders or missing brand-bible skeletons. It does not publicly publish, spend money, install large models, switch model routes, or bypass compliance gates without manual approval.
