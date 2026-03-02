"""Pydantic models for pyclaw configuration.

Maps the existing ~/.pyclaw/pyclaw.json (JSON5) structure.
Uses aliases for camelCase compatibility with the TypeScript version.
All fields are optional to support partial configs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _CamelModel(BaseModel):
    """Base model with camelCase alias support and extra field passthrough."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


# --- Secrets ---


class SecretRef(_CamelModel):
    source: Literal["env", "file", "exec"]
    provider: str
    id: str


SecretInput = str | SecretRef


# --- Models ---


class ModelCompatConfig(_CamelModel):
    supports_store: bool | None = Field(None, alias="supportsStore")
    supports_developer_role: bool | None = Field(None, alias="supportsDeveloperRole")
    supports_reasoning_effort: bool | None = Field(None, alias="supportsReasoningEffort")
    max_tokens_field: str | None = Field(None, alias="maxTokensField")
    thinking_format: str | None = Field(None, alias="thinkingFormat")


class ModelCostConfig(_CamelModel):
    input: float | None = None
    output: float | None = None
    cache_read: float | None = Field(None, alias="cacheRead")
    cache_write: float | None = Field(None, alias="cacheWrite")


class ModelDefinitionConfig(_CamelModel):
    id: str
    name: str
    api: str | None = None
    reasoning: bool | None = None
    input: list[str] | None = None
    cost: ModelCostConfig | None = None
    context_window: int | None = Field(None, alias="contextWindow")
    max_tokens: int | None = Field(None, alias="maxTokens")
    headers: dict[str, str] | None = None
    compat: ModelCompatConfig | None = None
    deployment: str | None = None


class ModelProviderConfig(_CamelModel):
    base_url: str = Field(alias="baseUrl")
    api_key: SecretInput | None = Field(None, alias="apiKey")
    auth: str | None = None
    api: str | None = None
    models: list[ModelDefinitionConfig] = []
    headers: dict[str, str] | None = None
    api_version: str | None = Field(None, alias="apiVersion")
    use_aad: bool | None = Field(None, alias="useAad")
    aad_tenant_id: str | None = Field(None, alias="aadTenantId")
    aad_client_id: str | None = Field(None, alias="aadClientId")


class ModelsConfig(_CamelModel):
    mode: Literal["merge", "replace"] | None = None
    providers: dict[str, ModelProviderConfig] | None = None


# --- Session ---


class SessionResetConfig(_CamelModel):
    mode: Literal["daily", "idle"] | None = None
    at_hour: int | None = Field(None, alias="atHour")
    idle_minutes: int | None = Field(None, alias="idleMinutes")


class SessionMaintenanceConfig(_CamelModel):
    mode: Literal["enforce", "warn"] | None = None
    prune_after: str | int | None = Field(None, alias="pruneAfter")
    max_entries: int | None = Field(None, alias="maxEntries")
    rotate_bytes: int | str | None = Field(None, alias="rotateBytes")
    max_disk_bytes: int | str | None = Field(None, alias="maxDiskBytes")
    high_water_bytes: int | str | None = Field(None, alias="highWaterBytes")


class SessionSendPolicyMatch(_CamelModel):
    channel: str | None = None
    chat_type: str | None = Field(None, alias="chatType")
    key_prefix: str | None = Field(None, alias="keyPrefix")


class SessionSendPolicyRule(_CamelModel):
    action: Literal["allow", "deny"]
    match: SessionSendPolicyMatch | None = None


class SessionSendPolicyConfig(_CamelModel):
    default: Literal["allow", "deny"] | None = None
    rules: list[SessionSendPolicyRule] | None = None


class SessionConfig(_CamelModel):
    scope: Literal["per-sender", "global"] | None = None
    dm_scope: str | None = Field(None, alias="dmScope")
    identity_links: dict[str, list[str]] | None = Field(None, alias="identityLinks")
    reset_triggers: list[str] | None = Field(None, alias="resetTriggers")
    idle_minutes: int | None = Field(None, alias="idleMinutes")
    reset: SessionResetConfig | None = None
    reset_by_type: dict[str, SessionResetConfig] | None = Field(None, alias="resetByType")
    reset_by_channel: dict[str, SessionResetConfig] | None = Field(None, alias="resetByChannel")
    store: str | None = None
    typing_mode: Literal["never", "instant", "thinking", "message"] | None = Field(
        None, alias="typingMode"
    )
    main_key: str | None = Field(None, alias="mainKey")
    send_policy: SessionSendPolicyConfig | None = Field(None, alias="sendPolicy")
    maintenance: SessionMaintenanceConfig | None = None


# --- Auth ---


class AuthConfig(_CamelModel):
    password: str | None = None
    token: str | None = None


# --- Gateway ---


class GatewayTailscaleConfig(_CamelModel):
    enabled: bool | None = None
    serve: bool | None = None
    funnel: bool | None = None
    hostname: str | None = None


class GatewayAuthConfig(_CamelModel):
    mode: str | None = None
    password: str | None = None
    token: str | None = None


class GatewayConfig(_CamelModel):
    mode: Literal["local", "remote"] | None = None
    host: str | None = None
    port: int | None = None
    bind: str | None = None
    tailscale: GatewayTailscaleConfig | None = None
    auth: GatewayAuthConfig | None = None
    auto_start: bool | None = Field(None, alias="autoStart")
    control_ui: dict[str, Any] | None = Field(None, alias="controlUi")


# --- Channels ---


class ChannelDefaultsConfig(_CamelModel):
    dm_policy: str | None = Field(None, alias="dmPolicy")
    group_policy: str | None = Field(None, alias="groupPolicy")
    group_activation: str | None = Field(None, alias="groupActivation")
    elevated_allow_from: dict[str, list[str | int]] | None = Field(None, alias="elevatedAllowFrom")


class ChannelsConfig(_CamelModel):
    defaults: ChannelDefaultsConfig | None = None
    telegram: dict[str, Any] | None = None
    discord: dict[str, Any] | None = None
    slack: dict[str, Any] | None = None
    whatsapp: dict[str, Any] | None = None
    signal: dict[str, Any] | None = None
    imessage: dict[str, Any] | None = None
    webchat: dict[str, Any] | None = None
    googlechat: dict[str, Any] | None = Field(None, alias="googlechat")
    dingtalk: dict[str, Any] | None = None
    qq: dict[str, Any] | None = None


# --- Agent ---


class IdentityConfig(_CamelModel):
    name: str | None = None
    theme: str | None = None
    emoji: str | None = None
    avatar: str | None = None


class AgentSandboxConfig(_CamelModel):
    mode: str | None = None
    image: str | None = None
    container: str | None = None


class AgentDefaultsConfig(_CamelModel):
    model: str | None = None
    provider: str | None = None
    thinking: str | None = None
    reasoning: str | None = None
    verbose: str | None = None
    identity: IdentityConfig | None = None
    sandbox: AgentSandboxConfig | None = None
    workspace_dir: str | None = Field(None, alias="workspaceDir")


class AgentConfig(_CamelModel):
    defaults: AgentDefaultsConfig | None = None
    model: str | None = None
    provider: str | None = None


class AgentsConfig(_CamelModel):
    defaults: AgentDefaultsConfig | None = None


class AgentBindingMatch(_CamelModel):
    channel: str | None = None
    account_id: str | None = Field(None, alias="accountId")
    peer: str | None = None
    guild: str | None = None
    team: str | None = None
    roles: list[str] | None = None


class AgentBinding(_CamelModel):
    agent: str
    match: AgentBindingMatch | None = None


# --- Tools ---


class ExecToolConfig(_CamelModel):
    enabled: bool | None = None
    timeout_ms: int | None = Field(None, alias="timeoutMs")
    shell: str | None = None
    allowlist: list[str] | None = None
    denylist: list[str] | None = None


class ToolsConfig(_CamelModel):
    exec: ExecToolConfig | None = None
    browser: dict[str, Any] | None = None
    media: dict[str, Any] | None = None
    memory_search: dict[str, Any] | None = Field(None, alias="memorySearch")
    mcp_servers: dict[str, dict[str, Any]] | None = Field(None, alias="mcpServers")
    restrict_to_workspace: bool | None = Field(None, alias="restrictToWorkspace")


# --- Logging ---


class LoggingConfig(_CamelModel):
    level: str | None = None
    file: str | None = None
    console_level: str | None = Field(None, alias="consoleLevel")
    console_style: str | None = Field(None, alias="consoleStyle")


# --- Update ---


class UpdateAutoConfig(_CamelModel):
    enabled: bool | None = None


class UpdateConfig(_CamelModel):
    channel: Literal["stable", "beta", "dev"] | None = None
    check_on_start: bool | None = Field(None, alias="checkOnStart")
    auto: UpdateAutoConfig | None = None


# --- Memory ---


class MemoryConfig(_CamelModel):
    enabled: bool | None = None
    provider: str | None = None


# --- Hooks ---


class HookConfig(_CamelModel):
    url: str | None = None
    events: list[str] | None = None
    secret: str | None = None


class HooksConfig(_CamelModel):
    mappings: dict[str, HookConfig] | None = None


# --- Cron ---


class CronConfig(_CamelModel):
    enabled: bool | None = None
    jobs: list[dict[str, Any]] | None = None


# --- UI ---


class UiAssistantConfig(_CamelModel):
    name: str | None = None
    avatar: str | None = None


class UiConfig(_CamelModel):
    seam_color: str | None = Field(None, alias="seamColor")
    assistant: UiAssistantConfig | None = None


# --- Messages ---


class MessagesConfig(_CamelModel):
    markdown: dict[str, Any] | None = None
    block_streaming: dict[str, Any] | None = Field(None, alias="blockStreaming")


# --- Skills ---


class SkillsConfig(_CamelModel):
    enabled: bool | None = None
    filter: list[str] | None = None
    load: dict[str, Any] | None = None


# --- Plugins ---


class PluginsConfig(_CamelModel):
    load: dict[str, Any] | None = None


# --- Meta ---


class MetaConfig(_CamelModel):
    last_touched_version: str | None = Field(None, alias="lastTouchedVersion")
    last_touched_at: str | None = Field(None, alias="lastTouchedAt")


# --- Top-level config ---


class PyClawConfig(_CamelModel):
    """Root configuration model.

    Compatible with the TypeScript PyClawConfig.
    All fields optional; unknown fields are preserved via extra="allow".
    """

    meta: MetaConfig | None = None
    auth: AuthConfig | None = None
    env: dict[str, Any] | None = None
    wizard: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None
    skills: SkillsConfig | None = None
    plugins: PluginsConfig | None = None
    models: ModelsConfig | None = None
    agents: AgentsConfig | None = None
    tools: ToolsConfig | None = None
    bindings: list[AgentBinding] | None = None
    session: SessionConfig | None = None
    ui: UiConfig | None = None
    web: dict[str, Any] | None = None
    channels: ChannelsConfig | None = None
    cron: CronConfig | None = None
    hooks: HooksConfig | None = None
    gateway: GatewayConfig | None = None
    memory: MemoryConfig | None = None
    logging: LoggingConfig | None = None
    update: UpdateConfig | None = None
    messages: MessagesConfig | None = None
    broadcast: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    commands: dict[str, Any] | None = None
    approvals: dict[str, Any] | None = None
    discovery: dict[str, Any] | None = None
    canvas_host: dict[str, Any] | None = Field(None, alias="canvasHost")
    talk: dict[str, Any] | None = None
    node_host: dict[str, Any] | None = Field(None, alias="nodeHost")
    acp: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    browser: dict[str, Any] | None = None
