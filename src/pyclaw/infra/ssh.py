"""SSH/SCP — config parsing, tunnel management, file transfer.

Ported from ``src/infra/ssh-config.ts``, ``ssh-tunnel.ts``, ``scp-host.ts``.

Provides:
- SSH config file parsing (~/.ssh/config)
- SSH tunnel management (local/remote port forwarding)
- SCP file transfer interface
- Host alias resolution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SSHHostConfig:
    """Parsed SSH host configuration."""

    host: str
    hostname: str = ""
    user: str = ""
    port: int = 22
    identity_file: str = ""
    proxy_jump: str = ""
    forward_agent: bool = False
    extra: dict[str, str] = field(default_factory=dict)


def parse_ssh_config(config_path: str | Path | None = None) -> list[SSHHostConfig]:
    """Parse an SSH config file into host entries."""
    path = Path(config_path) if config_path else Path.home() / ".ssh" / "config"
    if not path.exists():
        return []

    hosts: list[SSHHostConfig] = []
    current: SSHHostConfig | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        parts = stripped.split(maxsplit=1)
        if len(parts) < 2:
            continue

        key, value = parts[0].lower(), parts[1]

        if key == "host":
            if current:
                hosts.append(current)
            current = SSHHostConfig(host=value)
        elif current:
            if key == "hostname":
                current.hostname = value
            elif key == "user":
                current.user = value
            elif key == "port":
                current.port = int(value)
            elif key == "identityfile":
                current.identity_file = value
            elif key == "proxyjump":
                current.proxy_jump = value
            elif key == "forwardagent":
                current.forward_agent = value.lower() in ("yes", "true")
            else:
                current.extra[key] = value

    if current:
        hosts.append(current)

    return hosts


def resolve_host(hosts: list[SSHHostConfig], alias: str) -> SSHHostConfig | None:
    """Resolve an SSH host alias to its config."""
    for h in hosts:
        if h.host == alias:
            return h
    return None


# ---------------------------------------------------------------------------
# SSH Tunnel
# ---------------------------------------------------------------------------


@dataclass
class TunnelConfig:
    """SSH tunnel configuration."""

    ssh_host: str
    local_port: int
    remote_host: str = "127.0.0.1"
    remote_port: int = 0
    reverse: bool = False
    ssh_user: str = ""
    ssh_port: int = 22
    identity_file: str = ""

    def build_command(self) -> list[str]:
        """Build the SSH tunnel command."""
        cmd = ["ssh", "-N"]

        if self.ssh_user:
            cmd.extend(["-l", self.ssh_user])
        if self.ssh_port != 22:
            cmd.extend(["-p", str(self.ssh_port)])
        if self.identity_file:
            cmd.extend(["-i", self.identity_file])

        remote_port = self.remote_port or self.local_port
        if self.reverse:
            cmd.extend(["-R", f"{remote_port}:{self.remote_host}:{self.local_port}"])
        else:
            cmd.extend(["-L", f"{self.local_port}:{self.remote_host}:{remote_port}"])

        cmd.append(self.ssh_host)
        return cmd


@dataclass
class TunnelState:
    """Runtime state of an SSH tunnel."""

    config: TunnelConfig
    active: bool = False
    pid: int = 0
    started_at: float = 0.0


# ---------------------------------------------------------------------------
# SCP Transfer
# ---------------------------------------------------------------------------


@dataclass
class SCPTransfer:
    """SCP file transfer specification."""

    source: str
    destination: str
    ssh_host: str
    ssh_user: str = ""
    ssh_port: int = 22
    identity_file: str = ""
    recursive: bool = False
    upload: bool = True  # True = local→remote, False = remote→local

    def build_command(self) -> list[str]:
        """Build the SCP command."""
        cmd = ["scp"]
        if self.recursive:
            cmd.append("-r")
        if self.ssh_port != 22:
            cmd.extend(["-P", str(self.ssh_port)])
        if self.identity_file:
            cmd.extend(["-i", self.identity_file])

        user_prefix = f"{self.ssh_user}@" if self.ssh_user else ""

        if self.upload:
            cmd.extend([self.source, f"{user_prefix}{self.ssh_host}:{self.destination}"])
        else:
            cmd.extend([f"{user_prefix}{self.ssh_host}:{self.source}", self.destination])

        return cmd
