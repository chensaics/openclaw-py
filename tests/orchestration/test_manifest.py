"""Tests for orchestration manifest data structures."""

from pyclaw.agents.orchestration.manifest import (
    OrchestrationManifest,
    RoleConfig,
    RoleStatus,
    SpawnPolicy,
    ToolPolicy,
)


def test_manifest_creation():
    """Test creating a manifest with required fields."""
    manifest = OrchestrationManifest(
        version="1.0",
        task_id="task-001",
        goal="Analyze user request and delegate work",
        roles=[
            RoleConfig(
                role_id="researcher",
                name="Researcher",
                responsibility="Gather information from web",
                status=RoleStatus.PLANNED,
            )
        ],
        spawn_policy=SpawnPolicy(max_parallel=4),
    )

    assert manifest.version == "1.0"
    assert len(manifest.roles) == 1


def test_role_config():
    """Test RoleConfig dataclass creation."""
    role = RoleConfig(
        role_id="test-role",
        name="Test Role",
        responsibility="Test responsibility",
        status=RoleStatus.PLANNED,
    )

    assert role.role_id == "test-role"
    assert role.name == "Test Role"
    assert role.responsibility == "Test responsibility"
    assert role.status == RoleStatus.PLANNED


def test_spawn_policy():
    """Test SpawnPolicy dataclass creation."""
    policy = SpawnPolicy(max_parallel=4, max_depth=5)

    assert policy.max_parallel == 4
    assert policy.max_depth == 5


def test_tool_policy():
    """Test ToolPolicy dataclass creation."""
    policy = ToolPolicy(
        allow=["read", "write"],
        deny=["exec", "delete"],
    )

    assert "read" in policy.allow
    assert "exec" in policy.deny
    assert len(policy.allow) == 2
    assert len(policy.deny) == 2
