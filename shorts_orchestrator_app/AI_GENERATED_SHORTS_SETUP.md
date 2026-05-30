# AI-Generated Shorts Automation Setup

This file covers the "something from nothing" workflow:

```text
AI#1 Trend Scout -> AI#2 Prompt Engineer -> AI#3 Video Generator -> AI#4 Reviewer -> AI#5 Channel Router -> private upload queue
```

## What can be fully automated

- Trend pattern scanning through the YouTube Data API.
- Prompt packet generation for an original AI Short.
- Local AI review for YouTube monetization/TOS risk.
- Routing to the best configured channel.
- Queueing AI video generation through ComfyUI.
- Uploading generated files as private.
- Pulling basic analytics.

## What should stay manually approved

- Public publishing.
- Scheduled public publishing.
- Real-person/celebrity likeness content.
- Anything with copyrighted characters, voices, music, or brand imagery.
- Channel strategy changes.

The app can reduce risk, but it cannot guarantee YouTube monetization.

## Lowest-cost AI stack

### LLM agents

Use Ollama locally:

```powershell
ollama pull qwen2.5:7b
ollama pull llama3.1:8b
```

Routing is in `config/models.yaml`.

### AI video generation

Use ComfyUI as the local AI video backend. Recommended path:

1. Install ComfyUI.
2. Install ComfyUI Manager.
3. Install one video workflow/model:
   - LTX-Video for fast tests.
   - Wan 2.1 1.3B for consumer-GPU text-to-video experiments.
   - HunyuanVideo / HunyuanVideo 1.5 for higher quality if your GPU/VRAM can handle it.
4. Start ComfyUI with API access.
5. Export your working workflow in API format.
6. Replace `config/comfyui_text_to_video_workflow.json` with your exported API workflow.
7. Put `__PROMPT__` in the positive prompt node.
8. Put `__NEGATIVE_PROMPT__` in the negative prompt node.

The app will replace those placeholders and POST the workflow to ComfyUI.

## Test the agent chain without YouTube API

```powershell
python -m shorts_orchestrator.cli ai-chain --account ai_oddly_satisfying --query "cozy impossible machines" --no-youtube
```

This creates a prompt packet and review without needing YouTube OAuth.

## Test the full chain with a placeholder video

```powershell
python -m shorts_orchestrator.cli ai-chain --account ai_oddly_satisfying --query "cozy impossible machines" --no-youtube --generate --provider mock
```

The mock provider creates a simple placeholder MP4. It is only for testing pipeline/upload logic.

## Queue a real ComfyUI generation

```powershell
python -m shorts_orchestrator.cli ai-chain --account ai_oddly_satisfying --query "cozy impossible machines" --generate --provider comfyui --workflow config/comfyui_text_to_video_workflow.json
```

To wait for the ComfyUI history response:

```powershell
python -m shorts_orchestrator.cli ai-chain --account ai_oddly_satisfying --query "cozy impossible machines" --generate --provider comfyui --workflow config/comfyui_text_to_video_workflow.json --wait
```

## Uploading

Uploads are private by default:

```powershell
python -m shorts_orchestrator.cli upload --file data/outputs/example.mp4 --title "Private Test" --description "AI-generated original short. Private review." --account ai_oddly_satisfying
```

Review the video in YouTube Studio before publishing.

## Suggested channels

- `ai_oddly_satisfying`: safest starting AI-generated channel because visuals can be abstract/fictional.
- `dog_channel`: use clearly fictional dog animations or your own footage; avoid fake animal danger.
- `eve_gaming_channel`: use original commentary or fictional sci-fi market lessons.
- `vtuber_channel`: use original virtual host content; avoid copying real VTubers or agencies.

## Avoid these prompt patterns

- "in the style of [living artist/creator]"
- "make [celebrity] say..."
- "Disney/Pokemon/Marvel/Naruto style character"
- "real news footage of disaster"
- "fake emergency caught on camera"
- "use MrBeast-style voice/face"
- any real person's face, voice, or identity without permission


## Daily candidate batch

Generate multiple private candidates for a day without public auto-posting:

```powershell
python -m shorts_orchestrator.cli daily-batch --account ai_oddly_satisfying --query "cozy impossible machine" --query "tiny satisfying factory" --no-youtube --generate --provider mock
```

The daily batch uses `config/posting_schedule.yaml`. Keep public posting manual until the channel has a clean history.

## Brand bibles

Each account has a channel-specific brand bible in `config/brand_bibles/`. Edit these before scaling so each channel develops a recognizable identity and avoids repetitive template content.

## Voiceover

Use `--voice-provider mock` while testing. On Windows, try `--voice-provider windows_sapi`. For better no-subscription narration, install Piper and set `PIPER_MODEL` in `.env`, then use `--voice-provider piper`.
