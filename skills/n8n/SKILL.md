---
name: n8n
description: Manage n8n workflow automation via its REST API. Use to list, activate/deactivate, trigger, and inspect workflows on a self-hosted n8n instance. Also use to design and output n8n workflow JSON that can be imported directly.
homepage: https://n8n.io
metadata: { "openclaw": { "emoji": "⚙️", "requires": { "env": ["N8N_BASE_URL", "N8N_API_KEY"] } } }
---

# n8n Workflow Automation

n8n is a self-hosted workflow automation platform. This skill covers the REST API (v1) and JSON authoring.

## Base setup

```bash
# n8n API v1 base URL and auth header
BASE="${N8N_BASE_URL:-http://localhost:5678}/api/v1"
AUTH="X-N8N-API-KEY: $N8N_API_KEY"
```

## List workflows

```bash
curl -s -H "$AUTH" "$BASE/workflows" | jq '.data[] | {id, name, active}'
```

## Get a workflow

```bash
curl -s -H "$AUTH" "$BASE/workflows/<id>"
```

## Activate / deactivate a workflow

```bash
# Activate
curl -s -X PATCH -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"active":true}' "$BASE/workflows/<id>"

# Deactivate
curl -s -X PATCH -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"active":false}' "$BASE/workflows/<id>"
```

## Trigger a workflow manually (webhook node)

If the workflow starts with a Webhook node, POST to its path:

```bash
curl -s -X POST "$N8N_BASE_URL/webhook/<webhook-path>" \
  -H "Content-Type: application/json" \
  -d '{"key":"value"}'
```

## Execute a workflow via API

```bash
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  "$BASE/workflows/<id>/run" -d '{}'
```

## List executions

```bash
curl -s -H "$AUTH" "$BASE/executions?workflowId=<id>&limit=10" \
  | jq '.data[] | {id, status, startedAt, stoppedAt}'
```

## Import a workflow (create)

```bash
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  "$BASE/workflows" -d @workflow.json
```

## Designing workflow JSON

Use the agent to output `workflow.json` directly:

- Top-level keys: `name`, `nodes`, `connections`, `settings`, `staticData`
- Each node: `id`, `name`, `type`, `typeVersion`, `position`, `parameters`
- Common node types: `n8n-nodes-base.httpRequest`, `n8n-nodes-base.code`, `n8n-nodes-base.cron`, `n8n-nodes-base.telegramSendMessage`, `n8n-nodes-base.emailSend`

Minimal workflow skeleton:

```json
{
  "name": "My Workflow",
  "nodes": [
    {
      "id": "1",
      "name": "Start",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [250, 300],
      "parameters": {}
    }
  ],
  "connections": {},
  "settings": { "executionOrder": "v1" }
}
```

## Self-hosted install (Docker)

```bash
docker run -d --name n8n \
  -p 5678:5678 \
  -e N8N_BASIC_AUTH_ACTIVE=true \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=changeme \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

Enable API key in Settings → n8n API → Generate API key.

## Environment variables

| Variable       | Purpose                                        |
| -------------- | ---------------------------------------------- |
| `N8N_BASE_URL` | n8n instance URL, e.g. `http://localhost:5678` |
| `N8N_API_KEY`  | API key from n8n settings                      |
