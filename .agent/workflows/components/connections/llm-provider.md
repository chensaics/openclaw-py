# Connection: LLM Provider

Credentials for LLM API providers, resolved from pyclaw config.

## Schema

```yaml
type: connection
name: llm-provider
source: config  # reads from ~/.openclaw/openclaw.json → models.providers

fields:
  provider:
    type: string
    required: true
    enum: [openai, anthropic, google, azure, ollama, custom]
  base_url:
    type: string
    required: false
  api_key:
    type: string
    secret: true
    required: true
  model:
    type: string
    required: false
```

## Resolution

The connection reads credentials from the active pyclaw config:

```python
from pyclaw.config.io import load_config

cfg = load_config()
provider = cfg.models.providers.get(provider_name)
# provider.baseUrl, provider.apiKey
```

No separate credential files are needed — pyclaw's config is the source of truth.
