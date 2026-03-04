"""Chinese LLM provider configurations — Moonshot/Kimi, Volcengine/Doubao,
BytePlus, MiniMax, Xiaomi, Qianfan, Zhipu, DeepSeek.

Ported from ``src/agents/providers/`` in the TypeScript codebase.
Each provider is an OpenAI-compatible endpoint with specific model mappings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .openai_compat import ModelMapping, OpenAICompatConfig


@dataclass
class CNProviderSpec:
    """Specification for a Chinese LLM provider."""

    name: str
    display_name: str
    base_url: str
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer "
    default_model: str = ""
    models: list[ModelMapping] = field(default_factory=list)
    docs_url: str = ""
    supports_system_role: bool = True
    supports_tool_choice: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider specifications
# ---------------------------------------------------------------------------

MOONSHOT_SPEC = CNProviderSpec(
    name="moonshot",
    display_name="Moonshot / Kimi",
    base_url="https://api.moonshot.cn",
    default_model="moonshot-v1-128k",
    docs_url="https://platform.moonshot.cn/docs",
    models=[
        ModelMapping("moonshot-v1-8k", "moonshot-v1-8k", context_window=8192),
        ModelMapping("moonshot-v1-32k", "moonshot-v1-32k", context_window=32768),
        ModelMapping("moonshot-v1-128k", "moonshot-v1-128k", context_window=131072),
    ],
)

VOLCENGINE_SPEC = CNProviderSpec(
    name="volcengine",
    display_name="Volcengine / Doubao",
    base_url="https://ark.cn-beijing.volces.com/api",
    default_model="doubao-pro-256k",
    docs_url="https://www.volcengine.com/docs/82379",
    models=[
        ModelMapping("doubao-pro-4k", "doubao-pro-4k", context_window=4096),
        ModelMapping("doubao-pro-32k", "doubao-pro-32k", context_window=32768),
        ModelMapping("doubao-pro-128k", "doubao-pro-128k", context_window=131072),
        ModelMapping("doubao-pro-256k", "doubao-pro-256k", context_window=262144),
        ModelMapping("doubao-lite-4k", "doubao-lite-4k", context_window=4096),
        ModelMapping("doubao-lite-32k", "doubao-lite-32k", context_window=32768),
        ModelMapping("doubao-lite-128k", "doubao-lite-128k", context_window=131072),
    ],
)

BYTEPLUS_SPEC = CNProviderSpec(
    name="byteplus",
    display_name="BytePlus (International Volcengine)",
    base_url="https://ark.ap-southeast.bytepluses.com/api",
    default_model="doubao-pro-32k",
    docs_url="https://docs.byteplus.com/en/model-platform",
    models=VOLCENGINE_SPEC.models,
)

MINIMAX_SPEC = CNProviderSpec(
    name="minimax",
    display_name="MiniMax",
    base_url="https://api.minimax.chat",
    default_model="abab6.5s-chat",
    docs_url="https://platform.minimaxi.com/document",
    models=[
        ModelMapping("abab6.5s", "abab6.5s-chat", context_window=245760),
        ModelMapping("abab6.5t", "abab6.5t-chat", context_window=8192),
        ModelMapping("abab5.5", "abab5.5-chat", context_window=6144),
    ],
)

XIAOMI_SPEC = CNProviderSpec(
    name="xiaomi",
    display_name="Xiaomi MiLM",
    base_url="https://api.xiaomi.com/llm",
    default_model="milm-turbo",
    models=[
        ModelMapping("milm-turbo", "milm-turbo", context_window=32768),
        ModelMapping("milm-pro", "milm-pro", context_window=32768),
    ],
)

QIANFAN_SPEC = CNProviderSpec(
    name="qianfan",
    display_name="Baidu Qianfan / ERNIE",
    base_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
    default_model="ernie-4.0-8k",
    docs_url="https://cloud.baidu.com/doc/WENXINWORKSHOP",
    supports_tool_choice=False,
    models=[
        ModelMapping("ernie-4.0-8k", "completions_pro", context_window=8192),
        ModelMapping("ernie-4.0-turbo-8k", "ernie-4.0-turbo-8k", context_window=8192),
        ModelMapping("ernie-3.5-8k", "completions", context_window=8192),
        ModelMapping("ernie-speed-128k", "ernie-speed-128k", context_window=131072),
    ],
)

ZHIPU_SPEC = CNProviderSpec(
    name="zhipu",
    display_name="Zhipu AI / GLM",
    base_url="https://open.bigmodel.cn/api/paas",
    default_model="glm-4-plus",
    docs_url="https://open.bigmodel.cn/dev/api",
    models=[
        ModelMapping("glm-4-plus", "glm-4-plus", context_window=131072),
        ModelMapping("glm-4-long", "glm-4-long", context_window=1048576),
        ModelMapping("glm-4-flash", "glm-4-flash", context_window=131072),
        ModelMapping("glm-4", "glm-4", context_window=131072),
    ],
)

DEEPSEEK_SPEC = CNProviderSpec(
    name="deepseek",
    display_name="DeepSeek",
    base_url="https://api.deepseek.com",
    default_model="deepseek-chat",
    docs_url="https://platform.deepseek.com/api-docs",
    models=[
        ModelMapping("deepseek-chat", "deepseek-chat", context_window=65536),
        ModelMapping("deepseek-reasoner", "deepseek-reasoner", context_window=65536),
    ],
)

QWEN_SPEC = CNProviderSpec(
    name="qwen",
    display_name="Alibaba Qwen / Tongyi",
    base_url="https://dashscope.aliyuncs.com/compatible-mode",
    default_model="qwen-max",
    docs_url="https://help.aliyun.com/zh/model-studio",
    models=[
        ModelMapping("qwen-max", "qwen-max", context_window=32768),
        ModelMapping("qwen-plus", "qwen-plus", context_window=131072),
        ModelMapping("qwen-turbo", "qwen-turbo", context_window=131072),
        ModelMapping("qwen-long", "qwen-long", context_window=10000000),
        ModelMapping("qwen-vl-max", "qwen-vl-max", context_window=32768, supports_vision=True),
    ],
)

ALL_CN_PROVIDERS: dict[str, CNProviderSpec] = {
    "moonshot": MOONSHOT_SPEC,
    "volcengine": VOLCENGINE_SPEC,
    "byteplus": BYTEPLUS_SPEC,
    "minimax": MINIMAX_SPEC,
    "xiaomi": XIAOMI_SPEC,
    "qianfan": QIANFAN_SPEC,
    "zhipu": ZHIPU_SPEC,
    "deepseek": DEEPSEEK_SPEC,
    "qwen": QWEN_SPEC,
}


def build_cn_config(spec: CNProviderSpec, api_key: str) -> OpenAICompatConfig:
    """Build an OpenAICompatConfig from a Chinese provider spec."""
    headers = dict(spec.extra_headers)
    return OpenAICompatConfig(
        name=spec.name,
        base_url=spec.base_url,
        api_key=api_key,
        default_model=spec.default_model,
        models=list(spec.models),
        extra_headers=headers,
        supports_system_role=spec.supports_system_role,
        supports_tool_choice=spec.supports_tool_choice,
    )


def list_cn_providers() -> list[dict[str, str]]:
    """List all available Chinese providers with display info."""
    return [{"name": s.name, "display_name": s.display_name, "docs": s.docs_url} for s in ALL_CN_PROVIDERS.values()]


def get_cn_provider_models(name: str) -> list[str]:
    """Get model aliases for a Chinese provider."""
    spec = ALL_CN_PROVIDERS.get(name)
    if not spec:
        return []
    return [m.alias for m in spec.models]
