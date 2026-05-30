from __future__ import annotations

import os

from shorts_orchestrator.agents.prompts import AGENT_SYSTEMS
from shorts_orchestrator.settings import models_config, settings

# Configure provider environment variables for LiteLLM.
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
if settings.anthropic_api_key:
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
os.environ["OLLAMA_API_BASE"] = settings.ollama_host


def model_for(agent_name: str) -> tuple[str, float]:
    cfg = (models_config.get("models") or {}).get(agent_name, {})
    return cfg.get("provider_model", "ollama/qwen2.5:7b"), float(cfg.get("temperature", 0.2))


def run_agent(agent_name: str, task: str, context: str | None = None, max_tokens: int = 1400) -> str:
    try:
        from litellm import completion
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("LiteLLM is not installed. Run: pip install -r requirements.txt") from exc

    model, temperature = model_for(agent_name)
    system = AGENT_SYSTEMS.get(agent_name, AGENT_SYSTEMS["manager"])
    content = task if not context else f"Context:\n{context}\n\nTask:\n{task}"

    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def run_panel(tasks: dict[str, str], shared_context: str | None = None) -> dict[str, str]:
    # Serial by default for simplicity/reliability. Parallelization can be added later.
    outputs: dict[str, str] = {}
    context = shared_context or ""
    for agent, task in tasks.items():
        outputs[agent] = run_agent(agent, task, context=context)
        context += f"\n\n[{agent} output]\n{outputs[agent]}"
    return outputs
