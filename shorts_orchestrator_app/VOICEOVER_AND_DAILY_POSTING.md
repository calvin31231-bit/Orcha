# Voiceover, Daily Posting, and Safety Gates

## Voiceover recommendation

Use a dedicated Narration Director agent and a TTS provider rather than embedding narration as an afterthought.

Recommended free/local order:

1. `mock` provider for pipeline testing. This creates a silent WAV and a script file.
2. `windows_sapi` provider for a quick no-cost Windows voice test.
3. `piper` provider for a stable local production voice after you install Piper and a voice model.
4. Optional later upgrade: Kokoro/F5-TTS/Chatterbox/ElevenLabs if a channel proves it can get traction.

Never clone celebrities, creators, VTubers, politicians, or private people without permission. Keep one consistent original synthetic voice per channel.

## Commands

Create a prompt packet with scoring, preflight gate, narration plan, originality check, and prompt/version log:

```powershell
python -m shorts_orchestrator.cli ai-packet --account ai_oddly_satisfying --query "cozy impossible machine loop" --no-youtube
```

Run the full safe chain with voiceover and a placeholder test video:

```powershell
python -m shorts_orchestrator.cli ai-chain --account ai_oddly_satisfying --query "cozy impossible machine loop" --no-youtube --generate --provider mock --voice-provider mock
```

Generate a voiceover from an existing packet:

```powershell
python -m shorts_orchestrator.cli voiceover --account ai_oddly_satisfying --packet data/outputs/YOUR_PACKET.json --provider windows_sapi
```

Run a daily batch of candidates:

```powershell
python -m shorts_orchestrator.cli daily-batch --account ai_oddly_satisfying --query "cozy impossible machine" --query "tiny satisfying factory" --query "soft kinetic sculpture" --no-youtube --generate --provider mock
```

Pull analytics and write channel lessons back into the learning file:

```powershell
python -m shorts_orchestrator.cli learn-analytics --account ai_oddly_satisfying
```

## Posting cadence

The app is configured to create multiple private candidates per day, but public posting should start with one Short per channel per day until the channel has clean history and positive retention. YouTube has daily upload limits that vary by channel history, country/region, and strikes, so do not spam rapid uploads.

Recommended ramp:

- Days 1-30: 1 public Short/day/channel, up to 2-3 private candidates/day.
- Days 31-90: consider 2 public Shorts/day only on channels with consistent retention and no warnings.
- After 100 videos: cautiously test more frequency, but keep variation high and avoid repeated templates.

All generated metadata uses `privacy_status: private` by default. Public publishing is intentionally manual.
