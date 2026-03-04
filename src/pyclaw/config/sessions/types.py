"""Session entry types — compatible with TypeScript sessions.json format."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SessionOrigin(_CamelModel):
    label: str | None = None
    provider: str | None = None
    surface: str | None = None
    chat_type: str | None = Field(None, alias="chatType")
    from_: str | None = Field(None, alias="from")
    to: str | None = None
    account_id: str | None = Field(None, alias="accountId")
    thread_id: str | int | None = Field(None, alias="threadId")


class SessionAcpIdentity(_CamelModel):
    state: Literal["pending", "resolved"]
    acpx_record_id: str | None = Field(None, alias="acpxRecordId")
    acpx_session_id: str | None = Field(None, alias="acpxSessionId")
    agent_session_id: str | None = Field(None, alias="agentSessionId")
    source: Literal["ensure", "status", "event"]
    last_updated_at: int = Field(alias="lastUpdatedAt")


class SessionAcpMeta(_CamelModel):
    backend: str
    agent: str
    runtime_session_name: str = Field(alias="runtimeSessionName")
    identity: SessionAcpIdentity | None = None
    mode: Literal["persistent", "oneshot"]
    state: Literal["idle", "running", "error"]
    last_activity_at: int = Field(alias="lastActivityAt")
    last_error: str | None = Field(None, alias="lastError")


class SessionEntry(_CamelModel):
    """A single session entry in sessions.json.

    Compatible with the TypeScript SessionEntry type.
    """

    session_id: str = Field(alias="sessionId")
    updated_at: int = Field(alias="updatedAt")
    session_file: str | None = Field(None, alias="sessionFile")
    spawned_by: str | None = Field(None, alias="spawnedBy")
    forked_from_parent: bool | None = Field(None, alias="forkedFromParent")
    spawn_depth: int | None = Field(None, alias="spawnDepth")
    system_sent: bool | None = Field(None, alias="systemSent")
    aborted_last_run: bool | None = Field(None, alias="abortedLastRun")
    chat_type: str | None = Field(None, alias="chatType")

    # Model/provider
    model: str | None = None
    model_provider: str | None = Field(None, alias="modelProvider")
    provider_override: str | None = Field(None, alias="providerOverride")
    model_override: str | None = Field(None, alias="modelOverride")

    # Levels
    thinking_level: str | None = Field(None, alias="thinkingLevel")
    verbose_level: str | None = Field(None, alias="verboseLevel")
    reasoning_level: str | None = Field(None, alias="reasoningLevel")
    elevated_level: str | None = Field(None, alias="elevatedLevel")

    # Queue
    queue_mode: str | None = Field(None, alias="queueMode")
    queue_debounce_ms: int | None = Field(None, alias="queueDebounceMs")
    queue_cap: int | None = Field(None, alias="queueCap")

    # Token usage
    input_tokens: int | None = Field(None, alias="inputTokens")
    output_tokens: int | None = Field(None, alias="outputTokens")
    total_tokens: int | None = Field(None, alias="totalTokens")
    context_tokens: int | None = Field(None, alias="contextTokens")
    compaction_count: int | None = Field(None, alias="compactionCount")

    # Display
    label: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    channel: str | None = None
    group_id: str | None = Field(None, alias="groupId")
    subject: str | None = None

    # Origin & routing
    origin: SessionOrigin | None = None
    last_channel: str | None = Field(None, alias="lastChannel")
    last_to: str | None = Field(None, alias="lastTo")
    last_account_id: str | None = Field(None, alias="lastAccountId")
    last_thread_id: str | int | None = Field(None, alias="lastThreadId")

    # ACP
    acp: SessionAcpMeta | None = None


class SessionStore(_CamelModel):
    """The full sessions.json file: a mapping of session key to SessionEntry."""

    entries: dict[str, SessionEntry] = {}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionStore:
        entries = {k: SessionEntry.model_validate(v) for k, v in data.items()}
        return cls(entries=entries)

    def to_dict(self) -> dict[str, Any]:
        return {k: v.model_dump(by_alias=True, exclude_none=True) for k, v in self.entries.items()}
