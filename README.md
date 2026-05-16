# OpenClaw — Self-Hosted AI Gateway · Telegram · Venice AI · Tor · Ubuntu VPS

> **Deployment target:** Ubuntu 20.04 LTS VPS · headless SSH · Docker Compose · Tor anonymity layer · Venice AI (abliterated models) · Telegram Bot control interface
>
> **Repository:** This guide covers the `bitbybit91/openclawtor` fork on branch `copilot/add-telegram-marketing-bot-again`. The upstream project is [openclaw/openclaw](https://github.com/openclaw/openclaw). All installation steps in this document target the fork's feature branch.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Prerequisites](#2-prerequisites)
3. [VPS Environment Setup](#3-vps-environment-setup-headless-no-gui-required)
4. [Telegram Bot Setup](#4-telegram-bot-setup-marketing-bot--command-interface)
5. [Venice AI Configuration](#5-venice-ai-configuration)
6. [Configuration](#6-configuration)
7. [Installation](#7-installation)
8. [Build](#8-build)
9. [Running Tests](#9-running-tests)
10. [Common Issues & Troubleshooting](#10-common-issues--troubleshooting)
11. [Project Structure](#11-project-structure)
12. [Scripts Reference](#12-scripts-reference)
13. [Contributing](#13-contributing)
14. [License](#14-license)

---

## 1. Project Overview

**OpenClaw** is a self-hosted, privacy-first AI agent gateway written in TypeScript that connects abliterated LLMs to real-world messaging channels and computer-use tools. It runs on your VPS, routes all outbound traffic through Tor for anonymity, and is controlled entirely via Telegram. The gateway exposes a typed WebSocket + HTTP API on port `18789`, managed by Docker Compose, and can be extended with plugins, skills, and memory backends.

### Key Features

- **Telegram Bot** as the primary control + marketing dispatch interface (powered by [grammy](https://grammy.dev/))
- **Venice AI abliterated model integration** — no content filtering, full prompt freedom — via the OpenAI-compatible endpoint at `https://api.venice.ai/api/v1`
- **Tor-routed AI API calls and outbound traffic** via `torsocks` / `SOCKS5 127.0.0.1:9050`
- **Multi-channel AI agent gateway** — Telegram, Discord, Slack, Mattermost, Signal, iMessage, WhatsApp, Matrix, and more
- **Plugin SDK** for extending tools, memory, and skills
- **Docker Compose deployment** — one-command VPS launch
- **Automated Telegram marketing bot** — scheduled message dispatch to channels/groups, audience targeting, and campaign management via bot commands
- **MCP support** via `mcporter` bridge (port `18790`)
- **Sandbox isolation** via nested Docker containers
- **Supported environment:** Ubuntu 20.04 LTS VPS, headless SSH only

### Tech Stack

| Layer | Technology |
|-------|------------|
| Language | TypeScript (ESM, strict) |
| Runtime | Node.js 22.12+ |
| Package manager | pnpm 9+ |
| Build | tsdown |
| Tests | Vitest + V8 coverage |
| Lint / Format | Oxlint + Oxfmt |
| Telegram library | [grammy](https://grammy.dev/) + `@grammyjs/runner` |
| AI API | Venice AI (OpenAI-compatible, abliterated models) |
| Anonymity | Tor + torsocks (`SOCKS5 127.0.0.1:9050`) |
| Deployment | Docker 24+ · Docker Compose v2 |
| Platform | Ubuntu 20.04 LTS VPS, SSH-only |

---

## 2. Prerequisites

Install every tool listed below on a clean Ubuntu 20.04 LTS VPS before proceeding to [Section 7 — Installation](#7-installation).

| Tool | Min Version | Install (Ubuntu 20.04) | Verify |
|------|-------------|------------------------|--------|
| git | 2.25+ | `sudo apt install -y git` | `git --version` |
| curl | any | `sudo apt install -y curl` | `curl --version` |
| Node.js | 22.12+ | See command block below | `node --version` |
| pnpm | 9+ | `npm install -g pnpm@9` | `pnpm --version` |
| Docker Engine | 24+ | See command block below | `docker --version` |
| Docker Compose v2 | 2.20+ | `sudo apt install -y docker-compose-plugin` | `docker compose version` |
| Tor | 0.4.7+ | `sudo apt install -y tor` | `tor --version` |
| torsocks | 2.3+ | `sudo apt install -y torsocks` | `torsocks --version` |
| tmux | 3+ | `sudo apt install -y tmux` | `tmux -V` |
| openssl | 1.1.1+ | `sudo apt install -y openssl` | `openssl version` |
| Venice AI API Key | — | https://venice.ai → Settings → API Keys | `curl https://api.venice.ai/api/v1/models -H "Authorization: Bearer $VENICE_API_KEY"` |
| Telegram Bot Token | — | Create via @BotFather — see Section 4 | `curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"` |

**Install Node.js 22 LTS via NodeSource:**

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # must show v22.x.x
```

**Install Docker Engine on Ubuntu 20.04 focal:**

```bash
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
sudo apt install -y ca-certificates curl gnupg lsb-release

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
                    docker-buildx-plugin docker-compose-plugin

docker --version          # must show 24.x or higher
docker compose version    # must show v2.x
```

---

## 3. VPS Environment Setup (Headless, No GUI Required)

### 3.1 Initial VPS Hardening

Connect as root via SSH, then run:

```bash
# Update all packages
apt update && apt upgrade -y

# Create a non-root operator user
adduser operator
usermod -aG sudo operator

# Copy your SSH public key to the new user (run on your local machine)
# ssh-copy-id operator@<VPS_IP>

# Disable root SSH login and password authentication
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
sudo ufw status verbose
```

Add the operator user to the `docker` group:

```bash
sudo usermod -aG docker operator
# Log out and back in for the group change to take effect
```

### 3.2 Tor Setup

```bash
sudo apt install -y tor torsocks
```

Append the required configuration to `/etc/tor/torrc`:

```bash
printf '\n# OpenClaw Tor\nSocksPort 127.0.0.1:9050\nSocksPolicy accept 127.0.0.1\nLog notice file /var/log/tor/notices.log\n' | sudo tee -a /etc/tor/torrc
```

Enable and start Tor:

```bash
sudo systemctl enable tor
sudo systemctl start tor
sudo systemctl status tor   # must show "active (running)"
```

Verify Tor is routing correctly:

```bash
curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip
# Expected: {"IsTor":true,"IP":"..."}
```

**Tor Troubleshooting:**

| Problem | Cause | Fix |
|---------|-------|-----|
| `Could not bind to 127.0.0.1:9050` | Port already in use | sudo lsof -i :9050 to find the PID, then terminate it with `sudo kill -9 <PID>`, then `sudo systemctl restart tor` |
| Bootstrap stuck at 0% | Network or DNS block | Run `sudo journalctl -u tor -n 50`; add a bridge entry to `/etc/tor/torrc` |
| `{"IsTor":false}` | Tor not routing | Confirm `grep SocksPort /etc/tor/torrc` returns `SocksPort 127.0.0.1:9050`, then `sudo systemctl restart tor` |
| DNS leaking | Using `socks5://` without `h` | Always use `socks5h://` — the `h` forces DNS resolution over Tor |

### 3.3 Docker Setup (Verification)

After installing Docker from Section 2:

```bash
docker run --rm hello-world
docker compose version
docker ps   # must work without sudo
```

### 3.4 Routing Docker Container Traffic Through Tor

Add to your `.env` file:

```bash
HTTPS_PROXY=socks5h://127.0.0.1:9050
HTTP_PROXY=socks5h://127.0.0.1:9050
```

Find the Docker bridge IP and pass it into the container environment:

```bash
ip route | grep docker
# Example: 172.17.0.0/16 dev docker0
# Use 172.17.0.1 as the TOR_SOCKS_HOST for the container
```

Add to the `openclaw-gateway` service in `docker-compose.yml` under `environment`:

```yaml
HTTPS_PROXY: "socks5h://172.17.0.1:9050"
HTTP_PROXY:  "socks5h://172.17.0.1:9050"
TOR_SOCKS_HOST: "172.17.0.1"
TOR_SOCKS_PORT: "9050"
```

Verify Tor routing from inside a running container:

```bash
docker compose exec openclaw-gateway \
  node --input-type=module --eval \
  "const r = await fetch('https://check.torproject.org/api/ip'); console.log(await r.json());"
# Expected: { IsTor: true, IP: '...' }
```

---

## 4. Telegram Bot Setup (Marketing Bot + Command Interface)

### 4.1 Create the Bot

1. Open Telegram and search for `@BotFather`.
2. Send `/start`.
3. Send `/newbot`.
4. Enter a display name (example: `OpenClaw Agent`).
5. Enter a username ending in `bot` (example: `openclawagent_bot`).
6. Copy the API token — format: `123456789:ABCDEFghijklmNOPQRSTuvwxyz`
7. Set a description: `/setdescription` → select your bot → enter text.
8. Disable Group Privacy for full message access: `/setprivacy` → select your bot → `Disable`
9. Enable inline mode if needed: `/setinline` → select your bot → enter placeholder text.

Store the token as `TELEGRAM_BOT_TOKEN` in your `.env` file.

### 4.2 Find Your Chat ID

Send any message to your bot first, then run:

```bash
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" | python3 -m json.tool
# Look for: result[0].message.chat.id
```

The numeric value is your `chat_id`. Add it to `TELEGRAM_ALLOWED_CHAT_IDS` in `.env`.

To get a channel chat ID: add the bot as admin, post a message to the channel, run `getUpdates`, and look for `result[N].channel_post.chat.id`.

### 4.3 Bot Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Initialize session, display menu | `/start` |
| `/ask <prompt>` | Send prompt to the active Venice AI model | `/ask explain quantum entanglement` |
| `/model <name>` | Switch the active Venice AI model | `/model nous-hermes-2-mixtral-8x7b` |
| `/status` | Show gateway health, Tor status, active model | `/status` |
| `/broadcast <message>` | Send marketing message to all configured channels | `/broadcast New feature just dropped!` |
| `/schedule <cron> <message>` | Schedule a recurring marketing message (cron syntax) | `/schedule "0 9 * * 1" Weekly update` |
| `/campaigns` | List all active scheduled marketing campaigns | `/campaigns` |
| `/stop_campaign <id>` | Cancel a scheduled campaign by ID | `/stop_campaign 3` |
| `/tor_check` | Verify current Tor exit node and circuit status | `/tor_check` |
| `/newcircuit` | Request a new Tor identity (new exit IP) | `/newcircuit` |
| `/help` | Show all available commands | `/help` |

### 4.4 Security: Restrict to Operator Only

Set `TELEGRAM_ALLOWED_CHAT_IDS` in `.env` to a comma-separated list of authorized numeric chat IDs:

```bash
TELEGRAM_ALLOWED_CHAT_IDS=123456789,987654321
```

The bot silently drops all messages from unauthorized chat IDs with no response, preventing information leakage.

Authorization guard pattern (grammy middleware):

```typescript
bot.use(async (ctx, next) => {
  const allowed = (process.env.TELEGRAM_ALLOWED_CHAT_IDS ?? "")
    .split(",")
    .map(Number)
    .filter(Boolean);
  if (allowed.length > 0 && !allowed.includes(ctx.chat?.id ?? 0)) {
    return; // silent drop
  }
  return next();
});
```

---

## 5. Venice AI Configuration

### What Abliterated Models Are

Abliterated models are LLMs with safety-filter and refusal layers removed via representation engineering. They respond to any prompt without content policy rejections. Venice AI hosts these models via an OpenAI-compatible API endpoint.

> **Operator responsibility:** Deploying abliterated models gives you full control over model output. You are solely responsible for all content generated by your deployment. Ensure your use complies with the laws of your jurisdiction, Venice AI's terms of service, and any applicable platform policies. Do not deploy this stack to generate illegal content or content that could harm others.

### Obtain a Venice AI API Key

1. Go to [https://venice.ai](https://venice.ai) and create an account.
2. Navigate to **Settings → API Keys → Create Key**.
3. Copy the key and store it as `VENICE_API_KEY` in your `.env` file.

Verify the key:

```bash
curl -s https://api.venice.ai/api/v1/models \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  | python3 -m json.tool | grep '"id"'
```

### Venice AI API Details

- **Base URL:** `https://api.venice.ai/api/v1`
- **Compatibility:** Drop-in OpenAI replacement — set `OPENAI_BASE_URL=https://api.venice.ai/api/v1` and `OPENAI_API_KEY` to your Venice key.

### Recommended Abliterated Models

| Model ID | Best Use Case | Context Window |
|----------|---------------|----------------|
| `nous-hermes-2-mixtral-8x7b` | General reasoning, agent planning, long tasks | 32k |
| `dolphin-2.9-llama3-8b` | Fast single-turn completions, tool calls | 8k |
| `dolphin-mixtral-8x22b` | Large-context analysis, document summarization | 64k |
| `llama-3.1-405b` | Maximum capability tasks | 128k |

### Configure OpenClaw to Use Venice AI

In `~/.openclaw/openclaw.json`:

```json
{
  "model": {
    "default": "nous-hermes-2-mixtral-8x7b",
    "providers": {
      "openai": {
        "baseUrl": "https://api.venice.ai/api/v1",
        "apiKey": "${VENICE_API_KEY}"
      }
    }
  }
}
```

### Route Venice AI Calls Through Tor

In `.env`:

```bash
HTTPS_PROXY=socks5h://127.0.0.1:9050
HTTP_PROXY=socks5h://127.0.0.1:9050
```

Verify Venice AI is reachable via Tor:

```bash
torsocks curl -s https://api.venice.ai/api/v1/models \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  | python3 -m json.tool | grep '"id"'
```

---

## 6. Configuration

### Complete `.env` File

```bash
# --- Gateway Auth -----------------------------------------------------------
# Generate with: openssl rand -hex 32
# The gateway refuses to start if this is a known placeholder value.
OPENCLAW_GATEWAY_TOKEN=

# --- Gateway Binding --------------------------------------------------------
# loopback = localhost-only (recommended behind Tor or nginx)
# lan      = binds to all interfaces
OPENCLAW_GATEWAY_BIND=loopback
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_BRIDGE_PORT=18790

# --- Venice AI (abliterated models) ----------------------------------------
VENICE_API_KEY=              # From https://venice.ai -> Settings -> API Keys
VENICE_BASE_URL=https://api.venice.ai/api/v1
VENICE_MODEL=nous-hermes-2-mixtral-8x7b

# --- OpenAI-compatible routing to Venice -----------------------------------
OPENAI_API_KEY=              # Set to the same value as VENICE_API_KEY
OPENAI_BASE_URL=https://api.venice.ai/api/v1

# --- Tor Proxy --------------------------------------------------------------
HTTPS_PROXY=socks5h://127.0.0.1:9050
HTTP_PROXY=socks5h://127.0.0.1:9050
TOR_SOCKS_HOST=127.0.0.1
TOR_SOCKS_PORT=9050

# --- Telegram Bot -----------------------------------------------------------
TELEGRAM_BOT_TOKEN=          # From @BotFather -- format: 123456:ABCDEF...
TELEGRAM_ALLOWED_CHAT_IDS=   # Comma-separated numeric chat IDs of authorized operators
TELEGRAM_MARKETING_CHANNELS= # Comma-separated channel IDs or @usernames for broadcast

# --- Paths ------------------------------------------------------------------
OPENCLAW_STATE_DIR=~/.openclaw
OPENCLAW_CONFIG_PATH=~/.openclaw/openclaw.json

# --- Docker Volumes ---------------------------------------------------------
OPENCLAW_IMAGE=openclaw:local
OPENCLAW_CONFIG_DIR=/home/operator/.openclaw
OPENCLAW_WORKSPACE_DIR=/home/operator/.openclaw/workspace
OPENCLAW_TZ=UTC
```

### `openclaw.json` Key Reference

Location: `~/.openclaw/openclaw.json`

| Key | Type | Description | Valid Values |
|-----|------|-------------|--------------|
| `model.default` | string | Default model ID for inference | Any model ID listed by the provider |
| `model.providers.openai.baseUrl` | string | Override base URL for OpenAI-compatible provider | `https://api.venice.ai/api/v1` |
| `model.providers.openai.apiKey` | string | API key; supports `${ENV_VAR}` interpolation | Your Venice AI key |
| `channels.telegram.token` | string | Telegram Bot token; overrides env var | `123456:ABCDEF...` |
| `gateway.auth.token` | string | Gateway WebSocket + HTTP auth token | 64-char hex string |
| `gateway.bind` | string | Network interface binding | `loopback`, `lan` |
| `gateway.port` | number | Gateway port | Default `18789` |

Full example:

```json
{
  "model": {
    "default": "nous-hermes-2-mixtral-8x7b",
    "providers": {
      "openai": {
        "baseUrl": "https://api.venice.ai/api/v1",
        "apiKey": "${VENICE_API_KEY}"
      }
    }
  },
  "channels": {
    "telegram": {
      "token": "${TELEGRAM_BOT_TOKEN}"
    }
  },
  "gateway": {
    "auth": {
      "token": "${OPENCLAW_GATEWAY_TOKEN}"
    },
    "bind": "loopback",
    "port": 18789
  }
}
```

---

## 7. Installation

Follow these steps in order on a clean Ubuntu 20.04 LTS VPS over SSH.

**Step 1 — Install system packages**

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl openssl tmux tor torsocks ca-certificates gnupg lsb-release python3
```

**Step 2 — Install Node.js 22 LTS**

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # must show v22.x.x
```

**Step 3 — Install pnpm 9**

```bash
npm install -g pnpm@9
pnpm --version   # must show 9.x.x
```

**Step 4 — Install Docker Engine**

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
                    docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
newgrp docker
```

**Step 5 — Clone the repository**

```bash
git clone https://github.com/bitbybit91/openclawtor.git
cd openclawtor
git checkout copilot/add-telegram-marketing-bot-again
```

**Step 6 — Install project dependencies**

```bash
pnpm install
```

If this fails with `EACCES`:

```bash
sudo chown -R $(whoami) ~/.npm ~/.local/share/pnpm
pnpm install
```

**Step 7 — Configure the environment**

```bash
cp .env.example .env

# Generate a secure gateway token
openssl rand -hex 32
# Paste the printed value as OPENCLAW_GATEWAY_TOKEN in .env

nano .env
# Fill in: OPENCLAW_GATEWAY_TOKEN, VENICE_API_KEY, OPENAI_API_KEY,
#          TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_IDS,
#          OPENCLAW_CONFIG_DIR, OPENCLAW_WORKSPACE_DIR
```

**Step 8 — Create the openclaw.json config**

```bash
mkdir -p ~/.openclaw ~/.openclaw/workspace

python3 -c "
import json
cfg = {
  'model': {
    'default': 'nous-hermes-2-mixtral-8x7b',
    'providers': {
      'openai': {
        'baseUrl': 'https://api.venice.ai/api/v1',
        'apiKey': '\${VENICE_API_KEY}'
      }
    }
  },
  'channels': {'telegram': {'token': '\${TELEGRAM_BOT_TOKEN}'}},
  'gateway': {'auth': {'token': '\${OPENCLAW_GATEWAY_TOKEN}'}}
}
import os
with open(os.path.expanduser('~/.openclaw/openclaw.json'), 'w') as f:
    json.dump(cfg, f, indent=2)
print('Written.')
"
```

**Step 9 — Build the project**

```bash
pnpm build
# Expected: compiles to dist/ with zero TypeScript errors
```

**Step 10 — Build the Docker image**

```bash
docker build -t openclaw:local .
```

**Step 11 — Start the gateway**

```bash
docker compose up -d
sleep 10
docker compose ps
curl -sf http://127.0.0.1:18789/healthz && echo "Gateway OK"
```

**Step 12 — Verify Telegram bot connection**

```bash
docker compose logs openclaw-gateway | grep -i telegram
# Expected: log line showing the Telegram bot has started polling
```

Send `/start` to your bot in Telegram. It should respond with a menu.

---

## 8. Build

### Development Build

```bash
pnpm dev
```

Gateway starts at `http://127.0.0.1:18789`. The Telegram bot connects automatically.

### Production Build (Docker)

```bash
pnpm build
docker build -t openclaw:local .
docker compose up -d
docker compose ps
docker compose logs -f openclaw-gateway
```

### CI/CD Build — GitHub Actions

Create `.github/workflows/build.yml`:

```yaml
name: Build and Test

on:
  push:
    branches: [main, "copilot/**"]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-22.04
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Node.js 22
        uses: actions/setup-node@v4
        with:
          node-version: "22"

      - name: Install pnpm
        run: npm install -g pnpm@9

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Build
        run: pnpm build
        env:
          VENICE_API_KEY: ${{ secrets.VENICE_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          OPENCLAW_GATEWAY_TOKEN: ${{ secrets.OPENCLAW_GATEWAY_TOKEN }}

      - name: Run tests
        run: pnpm test
        env:
          VENICE_API_KEY: ${{ secrets.VENICE_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          OPENCLAW_GATEWAY_TOKEN: ${{ secrets.OPENCLAW_GATEWAY_TOKEN }}

      - name: Build Docker image
        run: docker build -t openclaw:local .
```

Add `VENICE_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `OPENCLAW_GATEWAY_TOKEN` to **Settings → Secrets and variables → Actions** in your GitHub repository.

### Running Persistently via systemd

Create `/etc/systemd/system/openclaw-gateway.service`:

```ini
[Unit]
Description=OpenClaw Gateway
After=network.target tor.service docker.service
Requires=docker.service

[Service]
Type=simple
User=operator
WorkingDirectory=/home/operator/openclawtor
EnvironmentFile=/home/operator/openclawtor/.env
ExecStartPre=docker compose pull
ExecStart=docker compose up
ExecStop=docker compose down
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activate:

```bash
sudo cp openclaw-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable openclaw-gateway
sudo systemctl start openclaw-gateway
sudo systemctl status openclaw-gateway
```

---

## 9. Running Tests

```bash
# Run the full test suite
pnpm test

# Run a single test file
pnpm test src/path/to/target.test.ts

# Run with V8 coverage report
pnpm test -- --coverage

# Interactive watch mode (development)
pnpm vitest

# Coverage summary in terminal
pnpm test -- --coverage --reporter=text
```

Expected output for a passing run:

```
 PASS  src/channels/...  (N tests)
 PASS  src/gateway/...   (N tests)

Test Files  N passed
Tests       N passed
Duration    Xs
```

---

## 10. Common Issues & Troubleshooting

| Error / Symptom | Cause | Fix |
|-----------------|-------|-----|
| `Gateway refuses to start: insecure token` | `OPENCLAW_GATEWAY_TOKEN` is empty or a known placeholder | Run `openssl rand -hex 32` and paste the output into `.env` as `OPENCLAW_GATEWAY_TOKEN` |
| Venice AI returns `401 Unauthorized` | `VENICE_API_KEY` missing or incorrect | Verify at https://venice.ai → Settings → API Keys |
| Venice AI returns `400` or content refused | Using a non-abliterated model | Switch to `nous-hermes-2-mixtral-8x7b` or `dolphin-2.9-llama3-8b` in `openclaw.json` |
| `Connection refused` on port 9050 | Tor daemon not running | `sudo systemctl start tor && sudo systemctl status tor` |
| `curl: (7) Failed to connect to 127.0.0.1 port 9050` | Tor not listening | `grep SocksPort /etc/tor/torrc` must return `SocksPort 127.0.0.1:9050`; then `sudo systemctl restart tor` |
| Telegram bot not responding | Wrong token or unauthorized chat ID | `curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"` to validate; run `getUpdates` to find correct chat ID |
| `pnpm install` fails with `EACCES` | Wrong cache ownership | `sudo chown -R $(whoami) ~/.npm ~/.local/share/pnpm` |
| `docker compose up` fails: `port 18789 already in use` | Previous container on that port | `sudo lsof -i :18789` to find the PID, then terminate it with `sudo kill -9 <PID>` |
| `pnpm build` fails: TypeScript errors | Stale deps or missing generated types | `pnpm install --frozen-lockfile` then `pnpm build` |
| DNS leaking through Tor | Using `socks5://` without `h` | Use `socks5h://` everywhere |
| Marketing broadcast not sending | `TELEGRAM_MARKETING_CHANNELS` not set or bot not admin | Add bot as admin to each target channel; verify IDs with `@userinfobot` |
| Container shows `unhealthy` | Gateway slow to start | Increase `start_period` to `60s` in `docker-compose.yml` healthcheck |
| `openclaw: Node.js v22.12+ is required` | Node below 22.12 | Install Node 22 LTS via NodeSource (see Section 2) |

---

## 11. Project Structure

```
openclawtor/                          # Root of the pnpm monorepo
|-- src/                              # Core TypeScript source
|   |-- channels/                     # Channel adapter implementations
|   |-- gateway/                      # WebSocket + HTTP gateway (port 18789)
|   |-- agents/                       # Agent runtime, tools, session management
|   |-- config/                       # Configuration loading and validation
|   |-- cli/                          # CLI command wiring
|   |-- commands/                     # CLI subcommands
|   |-- plugins/                      # Plugin discovery, loader, registry
|   |-- plugin-sdk/                   # Public plugin SDK (internal copy)
|   |-- mcp/                          # MCP bridge (port 18790)
|   |-- routing/                      # Message routing and dispatch
|   |-- security/                     # Auth, token, and audit logic
|   `-- ...
|-- packages/
|   |-- plugin-sdk/                   # Public plugin SDK (npm-publishable)
|   |-- memory-host-sdk/              # Memory plugin host interface
|   `-- plugin-package-contract/      # Plugin manifest type contracts
|-- extensions/                       # Built-in bundled plugins
|   |-- telegram/                     # Telegram plugin (grammy + @grammyjs/runner)
|   |-- discord/                      # Discord plugin
|   |-- slack/                        # Slack plugin
|   |-- anthropic/                    # Anthropic Claude provider
|   |-- amazon-bedrock/               # Amazon Bedrock provider
|   |-- browser/                      # Browser / computer-use tool
|   `-- ...                           # 100+ additional extensions
|-- skills/                           # Bundled agent skills
|   |-- webmanager/                   # Web browsing and scraping
|   |-- github/                       # GitHub operations
|   |-- coding-agent/                 # Code generation and execution
|   `-- ...
|-- apps/
|   |-- ios/                          # iOS app (Swift)
|   |-- android/                      # Android app
|   |-- macos/                        # macOS app (SwiftUI)
|   `-- shared/                       # Shared cross-platform code
|-- ui/                               # Web frontend (React/Vite)
|-- test/                             # Integration and E2E tests
|-- test-fixtures/                    # Static test data
|-- qa/                               # QA automation
|-- scripts/                          # CI, release, utility automation
|-- git-hooks/                        # Pre-commit and pre-push hooks
|-- docs/                             # Project documentation
|-- assets/                           # Images, icons, static assets
|-- vendor/                           # Vendored/pinned third-party code
|-- patches/                          # pnpm dependency patches
|-- .github/                          # GitHub Actions and issue templates
|-- .agents/                          # AI agent configuration
|-- .pi/                              # Platform integration configs
|-- Dockerfile                        # Production image (node:24-bookworm)
|-- Dockerfile.sandbox                # Sandboxed agent execution
|-- Dockerfile.sandbox-browser        # Browser-enabled sandbox
|-- Dockerfile.sandbox-common         # Shared sandbox base layer
|-- docker-compose.yml                # Compose: gateway + CLI services
|-- docker-setup.sh                   # Automated Docker setup
|-- openclaw.mjs                      # CLI entry point (Node.js 22.12+)
|-- package.json                      # Root pnpm scripts and workspace config
|-- pnpm-workspace.yaml               # Monorepo workspace definitions
|-- tsconfig.json                     # Root TypeScript config
|-- tsdown.config.ts                  # Build bundler config
|-- vitest.config.ts                  # Test runner config
|-- knip.config.ts                    # Dead code analysis
|-- Makefile                          # make build -> pnpm build
|-- .env.example                      # Environment variable template
|-- .env                              # Local secrets -- NEVER commit
|-- fly.toml                          # Fly.io deployment config
|-- render.yaml                       # Render.com deployment config
|-- VISION.md                         # Project goals and architecture
|-- CONTRIBUTING.md                   # Contribution guidelines
|-- SECURITY.md                       # Security policy
|-- AGENTS.md                         # AI agent developer docs
`-- CHANGELOG.md                      # Version history
```

---

## 12. Scripts Reference

| Script | Command | Description |
|--------|---------|-------------|
| `build` | `pnpm build` | Compile TypeScript for all packages via tsdown |
| `dev` | `pnpm dev` | Start gateway in watch/development mode |
| `test` | `pnpm test` | Run all Vitest tests |
| `lint` | `pnpm lint` | Run Oxlint across the monorepo |
| `format` | `pnpm format` | Run Oxfmt formatter (check mode) |
| `format:fix` | `pnpm format:fix` | Run Oxfmt and write fixes in place |
| `check` | `pnpm check` | Full local gate: cycles, types, lint, format |
| `tsgo` | `pnpm tsgo` | TypeScript type-check (no emit) |
| `make build` | `make build` | Alias for `pnpm build` via Makefile |
| Docker build | `docker build -t openclaw:local .` | Build the production Docker image |
| Docker up | `docker compose up -d` | Start all containers in the background |
| Docker logs | `docker compose logs -f` | Tail all container logs |
| Docker down | `docker compose down` | Stop and remove all containers |
| Setup script | `bash docker-setup.sh` | Automated Docker environment provisioning |
| Podman setup | `bash setup-podman.sh` | Podman alternative to Docker setup |

---

## 13. Contributing

Fork and clone your fork of `bitbybit91/openclawtor` (the upstream canonical project is [openclaw/openclaw](https://github.com/openclaw/openclaw)):

```bash
git clone https://github.com/YOUR_USERNAME/openclawtor.git
cd openclawtor
```

**Branch naming:**

- `feat/short-description` — new features
- `fix/short-description` — bug fixes
- `chore/short-description` — maintenance, tooling, docs

**Rules:**

- One PR = one issue or topic. Do not bundle unrelated changes.
- PRs over ~5,000 changed lines are reviewed only in exceptional circumstances.

Run before every PR:

```bash
pnpm lint
pnpm format
pnpm tsgo
pnpm test
pnpm build
```

**PR Checklist:**

- [ ] No secrets or API keys committed to any file
- [ ] `.env.example` updated if new environment variables were added
- [ ] Tests added or updated for all changed code paths
- [ ] Tor routing preserved — no hardcoded clearnet-only API calls
- [ ] Venice AI model references use environment variables, not hardcoded strings
- [ ] `pnpm build` completes with zero TypeScript errors
- [ ] `CHANGELOG.md` entry added for user-facing changes

---

## 14. License

MIT License — 2024 OpenClaw Contributors

See [LICENSE](LICENSE) for the full license text.
