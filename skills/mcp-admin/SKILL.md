---
skill_key: mcp-admin
description: MCP server inventory, health checks, and integration diagnostics.
version: 1.0.0
runtime: mcp-bridge
launcher: mcp-bridge
security-level: standard
deps: mcp:filesystem
capability: mcp-inventory, connectivity-diagnostics, tool-discovery-audit
healthcheck: Validate tools.mcpServers entries are present and reachable.
rollback: Temporarily disable MCP-dependent skills and use local tool fallbacks.
---

# MCP Admin

Use this skill to diagnose MCP connectivity and tool registration issues.

## Checks

1. MCP server config validity (`tools.mcpServers`).
2. Transport reachability (stdio/http).
3. Tool discovery parity (expected vs actual).
4. Timeout/error signatures and retry behavior.

## Output

- MCP status summary
- Missing/failed servers
- Recommended remediation order
