# Node: LLM Chat

Sends a prompt to an LLM provider and captures the response. Used for summarization, analysis, and generation tasks within workflows.

## Schema

```yaml
type: node
name: llm-chat
connection: llm-provider
inputs:
  prompt:
    type: string
    required: true
  system_prompt:
    type: string
    required: false
  model:
    type: string
    required: false
    description: Override default model
  max_tokens:
    type: number
    default: 1024
  temperature:
    type: number
    default: 0.3

outputs:
  response: string
  usage:
    prompt_tokens: number
    completion_tokens: number
  model_used: string
  latency_ms: number

on_error: fail
on_empty: fail
```

## Implementation

```python
import time
from pyclaw.agents.stream import chat_completion

async def run(inputs: dict, connection: dict) -> dict:
    start = time.monotonic()
    result = await chat_completion(
        provider=connection["provider"],
        model=inputs.get("model", connection.get("model")),
        messages=[
            {"role": "system", "content": inputs.get("system_prompt", "")},
            {"role": "user", "content": inputs["prompt"]},
        ],
        max_tokens=inputs.get("max_tokens", 1024),
        temperature=inputs.get("temperature", 0.3),
    )
    elapsed = int((time.monotonic() - start) * 1000)
    return {
        "response": result.content,
        "usage": result.usage,
        "model_used": result.model,
        "latency_ms": elapsed,
    }
```
