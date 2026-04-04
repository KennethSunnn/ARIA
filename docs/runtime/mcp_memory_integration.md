# ARIA MCP Memory Integration

This project now includes a local MCP memory server implementation at `memory/mcp_memory_server.py`.

## Server Contract

The server exposes four tools:

- `remember(project, agent, topic, content, tags?)`
- `recall(query, tags?, limit?)`
- `search(query, limit?)`
- `rollback(method_id, to_version)`

Data is persisted through ARIA long-term memory (`data/methodology/methodologies.json`).

## Project MCP Config

Project-scoped MCP config is stored in `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "memory.mcp_memory_server"]
    }
  }
}
```

## Validation

Run:

```bash
python -m pytest tests/test_mcp_memory_chain.py -q
```

Expected result: 2 passing tests covering `remember -> recall/search` and `rollback`.

## Tagging Convention

- `project:aria`
- `agent:<agent-slug>`
- `run:<date-or-ticket>`
- `domain:ops`

Use these tags in `remember` writes so cross-session recall stays reliable.

