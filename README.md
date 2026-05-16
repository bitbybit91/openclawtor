# OpenClaw + Telegram Marketing Bot

<p align="center">
    <picture>
        <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/openclaw-logo-text-dark.svg">
        <img src="https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/openclaw-logo-text.svg" alt="OpenClaw" width="500">
    </picture>
</p>

<p align="center">
  <a href="https://github.com/openclaw/openclaw/actions/workflows/ci.yml?branch=main"><img src="https://img.shields.io/github/actions/workflow/status/openclaw/openclaw/ci.yml?branch=main&style=for-the-badge" alt="CI status"></a>
  <a href="https://github.com/openclaw/openclaw/releases"><img src="https://img.shields.io/github/v/release/openclaw/openclaw?include_prereleases&style=for-the-badge" alt="GitHub release"></a>
  <a href="https://discord.gg/clawd"><img src="https://img.shields.io/discord/1456350064065904867?label=Discord&logo=discord&logoColor=white&color=5865F2&style=for-the-badge" alt="Discord"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
</p>

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Prerequisites](#2-prerequisites)
3. [Environment Setup](#3-environment-setup-no-physical-device-required)
4. [Configuration](#4-configuration)
5. [Installation](#5-installation)
6. [Build](#6-build)
7. [Running Tests](#7-running-tests)
8. [Common Issues and Troubleshooting](#8-common-issues-and-troubleshooting)
9. [Project Structure](#9-project-structure)
10. [Scripts Reference](#10-scripts-reference)
11. [Contributing](#11-contributing)
12. [License](#12-license)

---

## 1. Project Overview

This repository is a fork of [OpenClaw](https://openclaw.ai) — a self-hosted, personal AI assistant gateway — extended with `marketingbot.py`, a **Telegram-controlled marketing automation bot** added on this branch.

### OpenClaw AI Gateway

OpenClaw is a multi-channel AI assistant gateway you run on your own hardware. It connects to the AI providers and messaging channels you choose, and serves as the control plane for your personal assistant.

**Core features:**

- AI gateway with multi-provider support: OpenAI, Anthropic (Claude), Google Gemini, OpenRouter, and more
- Messaging channel integrations: Telegram, Discord, Slack, WhatsApp, Signal, iMessage, Matrix, and many others
- Plugin and extension system for adding providers, channels, and tools
- Docker-first deployment with multi-stage builds (Node 24 + Bun)
- REST and WebSocket gateway APIs (port 18789 / 18790)
- Control UI served at `http://localhost:18789`
- Voice input/output (ElevenLabs, Deepgram)
- Browser automation, web search, and media understanding skills
- Health and readiness probe endpoints (`/healthz`, `/readyz`)

### Marketing Bot (`marketingbot.py`)

`marketingbot.py` is a Python 3.10+ bot controlled entirely via Telegram commands. It stores platform credentials encrypted at rest, composes content from per-platform instruction templates, and publishes posts to multiple social networks and webhooks.

**Marketing bot features:**

- Telegram command interface with chat-level authorization (`TELEGRAM_CHAT_ID`)
- Encrypted credential storage using the Fernet symmetric cipher (`cryptography` library)
- Per-platform instruction wizard — tone, hashtags, length, emoji, audience, format
- Direct publishing to:
  - **Twitter/X** via `tweepy` (`Client.create_tweet`)
  - **Reddit** via `praw` (text or link posts to configured subreddits)
  - **Facebook** via Graph API (`/{page_id}/feed`)
  - **Instagram** via Graph API (media create + publish)
  - **LinkedIn** via `/v2/shares`
  - **Telegram channels** via the bot's own `send_message`
  - **Custom/generic webhooks** (HTTP POST with JSON `{"text": "..."}`)
- APScheduler persistent scheduling: schedules survive restarts, past-due jobs are pruned on startup
- Campaign management: define a campaign once, run it across all configured platforms
- Draft → approve/edit → publish workflow (`/generatecontent`, `/approve`, `/edit`)
- Local analytics per platform (posts sent, success count, last post date)
- Log management (`/clearlog <platform>`)

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Node.js 24 (LTS), Bun (build/dev) |
| Language | TypeScript (ESM, strict mode) |
| Package manager | pnpm 9.x (monorepo via `pnpm-workspace.yaml`) |
| Build | tsdown, bundled via `pnpm build` |
| Tests (JS) | Vitest with V8 coverage |
| Python runtime | Python 3.10+ |
| Bot framework | `python-telegram-bot >= 20, < 22` |
| Scheduling | `apscheduler >= 3.10, < 4` |
| Encryption | `cryptography >= 42, < 44` (Fernet) |
| Twitter/X | `tweepy >= 4.14, < 5` |
| Reddit | `praw >= 7.7, < 8` |
| HTTP | `requests >= 2.31, < 3` |
| Container | Docker 24+, Docker Compose v2 |

**Supported platforms:** Linux, macOS, Windows (via Docker). The Python marketing bot runs on any platform with Python 3.10+.

---

## 2. Prerequisites

Install every tool listed below before proceeding. All version requirements are minimums.

### Git 2.40+

**macOS:**

```bash
brew install git
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt update && sudo apt install -y git
```

**Windows:**

```powershell
winget install Git.Git
```

**Verify:**

```bash
git --version
# Expected: git version 2.40.x or later
```

### Node.js 24.x

**macOS:**

```bash
brew install node@24
```

**Linux:**

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
```

**Windows:**

```powershell
winget install OpenJS.NodeJS.LTS
```

**Verify:**

```bash
node --version
# Expected: v24.x.x
```

### pnpm 9.x (via corepack)

**All platforms (requires Node 24 installed first):**

```bash
corepack enable
corepack prepare pnpm@latest --activate
```

**Verify:**

```bash
pnpm --version
# Expected: 9.x.x
```

### Bun (latest)

**macOS / Linux:**

```bash
curl -fsSL https://bun.sh/install | bash
```

**Windows:**

```powershell
powershell -c "irm bun.sh/install.ps1|iex"
```

**Verify:**

```bash
bun --version
# Expected: 1.x.x
```

### Python 3.10+

**macOS:**

```bash
brew install python@3.12
```

**Linux:**

```bash
sudo apt install -y python3 python3-pip python3-venv
```

**Windows:**

```powershell
winget install Python.Python.3.12
```

**Verify:**

```bash
python3 --version
# Expected: Python 3.10.x or later
```

### pip 23+

**All platforms (upgrades pip inside the active Python):**

```bash
python3 -m pip install --upgrade pip
```

**Verify:**

```bash
pip --version
# Expected: pip 23.x.x or later
```

### Docker 24+

**macOS:** Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/).

**Linux:**

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

**Windows:** Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).

**Verify:**

```bash
docker --version
# Expected: Docker version 24.x.x or later
```

### Docker Compose v2 plugin

Included with Docker Desktop. On Linux without Docker Desktop:

```bash
sudo apt install -y docker-compose-plugin
```

**Verify:**

```bash
docker compose version
# Expected: Docker Compose version v2.x.x
```

---

## 3. Environment Setup (No Physical Device Required)

There are two independent setup paths. Choose one or both.

### Path A — OpenClaw Gateway (Docker, no local Node install needed)

This path runs the full OpenClaw gateway inside Docker. No local Node.js or pnpm installation is required.

**Step 1: Clone the repository.**

```bash
git clone https://github.com/bitbybit91/openclawtor.git
cd openclawtor
git checkout copilot/add-telegram-marketing-bot
```

**Step 2: Create your environment file.**

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```bash
OPENCLAW_GATEWAY_TOKEN=        # leave blank to auto-generate, OR set with: openssl rand -hex 32
OPENAI_API_KEY=sk-...          # or any other provider key listed in .env.example
```

**Step 3: Build the Docker image.**

The `Dockerfile` is a multi-stage build (Node 24 + Bun build stage, slim Debian bookworm runtime). Available build arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `OPENCLAW_EXTENSIONS` | `""` | Space-separated list of bundled plugin directories to include |
| `OPENCLAW_VARIANT` | `default` | `default` (bookworm) or `slim` (bookworm-slim, ~100MB smaller) |
| `OPENCLAW_INSTALL_BROWSER` | `""` | Set to `1` to bake in Chromium + Xvfb for browser automation (~300MB) |
| `OPENCLAW_INSTALL_DOCKER_CLI` | `""` | Set to `1` to install Docker CLI for sandbox isolation (~50MB) |
| `OPENCLAW_DOCKER_APT_PACKAGES` | `""` | Extra Debian packages to install at runtime |

```bash
# Default build
docker build -t openclaw:local .

# With specific extensions
docker build --build-arg OPENCLAW_EXTENSIONS="matrix diagnostics-otel" -t openclaw:local .

# Slim variant
docker build --build-arg OPENCLAW_VARIANT=slim -t openclaw:local .

# With browser support
docker build --build-arg OPENCLAW_INSTALL_BROWSER=1 -t openclaw:local .
```

Build time is approximately 5–15 minutes on first run (depends on network and CPU). Subsequent builds are fast due to layer caching.

**Step 4: Start the services.**

```bash
docker compose up -d
```

This starts two containers:

- `openclaw-gateway` — the gateway server bound to `0.0.0.0:18789` and `0.0.0.0:18790`
- `openclaw-cli` — an interactive CLI container sharing the gateway's network

**Step 5: Verify the gateway is healthy.**

```bash
curl -s http://localhost:18789/healthz
# Expected output: {"status":"ok"} with HTTP 200
```

You can also poll readiness:

```bash
curl -s http://localhost:18789/readyz
```

**Troubleshooting — Gateway path A:**

| Symptom | Cause | Fix |
|---------|-------|-----|
| `docker: Error response from daemon: driver failed programming external connectivity` | Port 18789 or 18790 is already in use | `lsof -i :18789` to find the conflicting process, then `kill <PID>` |
| `Killed` during `docker build` | OOM on host with less than 4GB free RAM | Add `--memory=4g` to the `docker build` command, or set `NODE_OPTIONS=--max-old-space-size=2048` in the build stage environment |
| `ERROR: matrix-sdk-crypto native addon missing` | pnpm install silently failed for the current CPU architecture | Build on a supported architecture (amd64 or arm64) |
| `A2UI bundle: creating stub` in build output | QEMU cross-compilation limitation for A2UI canvas bundler | Non-fatal; stub is created automatically. Build natively per-arch to avoid this |

---

### Path B — Marketing Bot (Python virtualenv, no Telegram device needed)

This path runs only `marketingbot.py`. No Node.js is required.

**Step 1: Create and activate a virtual environment.**

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (Command Prompt):**

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Step 2: Install Python dependencies.**

```bash
pip install \
  "python-telegram-bot>=20,<22" \
  "apscheduler>=3.10,<4" \
  "cryptography>=42,<44" \
  "tweepy>=4.14,<5" \
  "praw>=7.7,<8" \
  "requests>=2.31,<3"
```

**Step 3: Create required directories and log files.**

**macOS / Linux:**

```bash
sudo mkdir -p /etc/marketingbot
sudo chown "$USER" /etc/marketingbot
sudo touch /var/log/marketingbot.log /var/log/marketingbot_posts.log
sudo chown "$USER" /var/log/marketingbot.log /var/log/marketingbot_posts.log
```

**Windows:** The bot uses `/etc/marketingbot/` and `/var/log/` paths by default, which are not native Windows paths. Override them using environment variables or by editing the `BASE_DIR`, `BOT_LOG_PATH`, and `POST_LOG_PATH` constants at the top of `marketingbot.py` to Windows paths such as `C:\marketingbot\` and `C:\logs\`.

**Step 4: Obtain a Telegram bot token without a physical device.**

You need a Telegram bot token and a chat ID. You do not need a phone number — you can use the [Telegram Web client](https://web.telegram.org) from any browser, or create a test account using a virtual number service.

1. Open Telegram Web or the Telegram app.
2. Search for `@BotFather`.
3. Send `/newbot` and follow the prompts to name your bot.
4. BotFather responds with a token in the format `123456789:ABCDEF...`. Copy it.
5. To find your chat ID, start a conversation with your new bot and then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   Send any message to the bot first, then reload the URL. The `chat.id` field in the response is your `TELEGRAM_CHAT_ID`.
   Alternatively, forward a message to `@userinfobot` to get your own user ID.

**Step 5: Set environment variables.**

**macOS / Linux:**

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCDEF..."
export TELEGRAM_CHAT_ID="123456789"
```

**Windows (PowerShell):**

```powershell
$env:TELEGRAM_BOT_TOKEN = "123456789:ABCDEF..."
$env:TELEGRAM_CHAT_ID = "123456789"
```

**Step 6: Run the bot.**

```bash
python marketingbot.py
```

**Expected console output on successful startup:**

```
2026-05-16 08:40:39,123 INFO marketingbot: Marketing bot started. Restored 0 scheduled jobs.
```

The bot immediately begins polling the Telegram API. Send `/start` from the authorized chat to verify it responds.

**First-run file creation:**

On the first run, the bot creates:

- `/etc/marketingbot/secret.key` — Fernet encryption key (mode 0600)
- `/etc/marketingbot/credentials.json` — encrypted credentials blob
- `/etc/marketingbot/instructions.json` — per-platform instruction config
- `/etc/marketingbot/scheduled.json` — persistent scheduled post registry
- `/etc/marketingbot/campaigns.json` — campaign definitions

**Overriding paths for local development:**

Edit the constants at the top of `marketingbot.py`:

```python
BASE_DIR = Path("/etc/marketingbot")          # change to e.g. Path("./data/marketingbot")
POST_LOG_PATH = Path("/var/log/marketingbot_posts.log")   # change to Path("./logs/posts.log")
BOT_LOG_PATH = Path("/var/log/marketingbot.log")          # change to Path("./logs/bot.log")
```

**Troubleshooting — Marketing bot path B:**

| Symptom | Cause | Fix |
|---------|-------|-----|
| `PermissionError: [Errno 13] Permission denied: '/etc/marketingbot/secret.key'` | Current user cannot write to `/etc/marketingbot/` | `sudo mkdir -p /etc/marketingbot && sudo chown "$USER" /etc/marketingbot` |
| `Not authorized.` in Telegram | The chat ID does not match `TELEGRAM_CHAT_ID` | Verify your chat ID with `@userinfobot` and update `TELEGRAM_CHAT_ID` |
| `RuntimeError: Missing TELEGRAM_BOT_TOKEN` | Environment variable not set in current shell | `export TELEGRAM_BOT_TOKEN="..."` and rerun |
| `telegram.error.InvalidToken` | Token format is wrong | Token must match `\d+:[A-Za-z0-9_-]{35,}` — regenerate with BotFather |
| `ModuleNotFoundError: No module named 'telegram'` | Virtual environment not activated | `source .venv/bin/activate` then rerun |

---

## 4. Configuration

### OpenClaw Gateway Environment Variables

Copy `.env.example` to `.env` and fill in the values you need. All variables are optional unless noted.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OPENCLAW_GATEWAY_TOKEN` | string | auto-generated | Auth token for the gateway. Leave blank to auto-generate on first start. Never copy a placeholder value from docs — the gateway refuses to start if it detects an example token. Generate with `openssl rand -hex 32`. |
| `OPENCLAW_GATEWAY_PASSWORD` | string | — | Alternative auth mode. Use token OR password, not both. |
| `OPENCLAW_STATE_DIR` | path | `~/.openclaw` | Directory where the gateway stores config, sessions, and state. |
| `OPENCLAW_CONFIG_PATH` | path | `~/.openclaw/openclaw.json` | Path to the main config file. |
| `OPENCLAW_HOME` | path | `~` | Home directory used for path resolution. |
| `OPENCLAW_LOAD_SHELL_ENV` | `0` or `1` | `0` | When `1`, imports missing keys from the login shell profile on startup. |
| `OPENCLAW_SHELL_ENV_TIMEOUT_MS` | integer | `15000` | Timeout in milliseconds for shell env import. |
| `OPENAI_API_KEY` | string | — | OpenAI API key (`sk-...`). At least one provider key is required. |
| `ANTHROPIC_API_KEY` | string | — | Anthropic Claude API key (`sk-ant-...`). |
| `GEMINI_API_KEY` | string | — | Google Gemini API key. |
| `OPENROUTER_API_KEY` | string | — | OpenRouter API key (`sk-or-...`). |
| `TELEGRAM_BOT_TOKEN` | string | — | Telegram bot token from BotFather. Required if using the Telegram channel. |
| `DISCORD_BOT_TOKEN` | string | — | Discord bot token. Required if using the Discord channel. |
| `SLACK_BOT_TOKEN` | string | — | Slack bot token (`xoxb-...`). Required if using the Slack channel. |
| `SLACK_APP_TOKEN` | string | — | Slack app token (`xapp-...`). Required for Slack Socket Mode. |
| `BRAVE_API_KEY` | string | — | Brave Search API key for web search. |
| `PERPLEXITY_API_KEY` | string | — | Perplexity API key (`pplx-...`). |
| `ELEVENLABS_API_KEY` | string | — | ElevenLabs API key for voice synthesis. |
| `DEEPGRAM_API_KEY` | string | — | Deepgram API key for voice transcription. |
| `MATTERMOST_BOT_TOKEN` | string | — | Mattermost bot token. |
| `MATTERMOST_URL` | string | — | Mattermost server URL (e.g. `https://chat.example.com`). |

#### Example `.env` file for the OpenClaw gateway

```bash
# Gateway auth — leave blank to auto-generate, or:
# OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)
OPENCLAW_GATEWAY_TOKEN=

# Model providers — set at least one
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GEMINI_API_KEY=...

# Messaging channels — set what you enable
# TELEGRAM_BOT_TOKEN=123456:ABCDEF...
# DISCORD_BOT_TOKEN=...
# SLACK_BOT_TOKEN=xoxb-...
# SLACK_APP_TOKEN=xapp-...

# Optional tools
# BRAVE_API_KEY=...
# ELEVENLABS_API_KEY=...
```

---

### Marketing Bot Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | **Yes** | Token from [@BotFather](https://t.me/BotFather). Format: `123456789:ABCDEF...`. Keep this value private — anyone with the token can interact with the bot. |
| `TELEGRAM_CHAT_ID` | **Yes** | Integer chat ID of the single authorized operator. Only this chat ID can issue commands. This value acts as the bot's authorization boundary — keep it private and do not share it. Any chat whose ID does not match this value receives `Not authorized.` |

> **Security note:** `TELEGRAM_CHAT_ID` is the sole access control boundary for the marketing bot. Do not commit it to version control or log it. If you need to change the authorized operator, update this value and restart the bot.

#### Example `.env` file for the marketing bot

```bash
# Required — obtain from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCDEF_your_token_here

# Required — your personal Telegram chat ID (integer)
# Find it by messaging @userinfobot or reading the Telegram getUpdates API response
TELEGRAM_CHAT_ID=123456789
```

---

### Docker Compose Environment Variables

These variables are read by `docker-compose.yml` at `docker compose up` time.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLAW_IMAGE` | `openclaw:local` | Docker image tag to use for both services. |
| `OPENCLAW_CONFIG_DIR` | *(required)* | Host directory mounted to `/home/node/.openclaw` inside the container. |
| `OPENCLAW_WORKSPACE_DIR` | *(required)* | Host directory mounted to `/home/node/.openclaw/workspace`. |
| `OPENCLAW_GATEWAY_PORT` | `18789` | Host port mapped to the gateway's internal port 18789. |
| `OPENCLAW_BRIDGE_PORT` | `18790` | Host port mapped to the gateway's internal bridge port 18790. |
| `OPENCLAW_GATEWAY_BIND` | `lan` | Bind address for the gateway. `lan` binds to `0.0.0.0`; `loopback` binds to `127.0.0.1` (unreachable from host when using Docker bridge networking). |
| `OPENCLAW_GATEWAY_TOKEN` | *(empty)* | Passed through to the container as the auth token. |
| `OPENCLAW_TZ` | `UTC` | Timezone string passed to the container (`TZ` env var). |

#### Example `.env` file for Docker Compose

```bash
# Docker image to run
OPENCLAW_IMAGE=openclaw:local

# Host directories (create these before running docker compose up)
OPENCLAW_CONFIG_DIR=/home/youruser/.openclaw
OPENCLAW_WORKSPACE_DIR=/home/youruser/.openclaw/workspace

# Port mapping
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_BRIDGE_PORT=18790

# Bind address: "lan" for 0.0.0.0 (accessible from host), "loopback" for 127.0.0.1
OPENCLAW_GATEWAY_BIND=lan

# Auth token — leave blank to auto-generate
OPENCLAW_GATEWAY_TOKEN=

# Model provider (passed through to the container)
OPENAI_API_KEY=sk-...

# Timezone
OPENCLAW_TZ=UTC
```

---

## 5. Installation

### Full Monorepo Setup (OpenClaw + Marketing Bot)

Follow these steps on a fresh machine with all prerequisites installed.

**1. Clone the repository.**

```bash
git clone https://github.com/bitbybit91/openclawtor.git
cd openclawtor
```

Expected output: git clone progress followed by `Resolving deltas: 100%`.

**2. Check out the marketing bot branch.**

```bash
git checkout copilot/add-telegram-marketing-bot
```

Expected output: `Switched to branch 'copilot/add-telegram-marketing-bot'`.

**3. Enable corepack.**

```bash
corepack enable
```

This activates pnpm via the Node.js corepack mechanism. No output on success.

**4. Install Node.js dependencies.**

```bash
pnpm install --frozen-lockfile
```

Expected output: pnpm resolves workspace packages and installs all dependencies. The `matrix-sdk-crypto` native addon is compiled or downloaded for your architecture. This step takes 2–10 minutes on first run.

If you see `ERR_PNPM_FROZEN_LOCKFILE` errors, it means the lockfile is out of sync with `package.json`. Run `pnpm install` (without `--frozen-lockfile`) to regenerate it.

**5. Verify the critical native addon.**

```bash
find node_modules -name "matrix-sdk-crypto*.node" | head -1
```

Expected output: a path such as `node_modules/.pnpm/.../matrix-sdk-crypto.linux-x64-gnu.node`.

If the command returns no output, the native addon failed to install. Re-run `pnpm install --frozen-lockfile` on a supported architecture (amd64 or arm64).

**6. Copy and configure the environment file.**

```bash
cp .env.example .env
```

Open `.env` in a text editor and set at minimum:

```bash
OPENAI_API_KEY=sk-...          # or another provider key
OPENCLAW_CONFIG_DIR=/home/$USER/.openclaw
OPENCLAW_WORKSPACE_DIR=/home/$USER/.openclaw/workspace
```

Create the config directories:

```bash
mkdir -p ~/.openclaw ~/.openclaw/workspace
```

**7. Build the TypeScript source.**

```bash
pnpm build
# or equivalently:
make build
```

Expected output: build scripts run, `dist/index.js` and related files are produced. Build takes 1–3 minutes.

Verify:

```bash
ls dist/index.js dist/control-ui/index.html
```

**8. Build the Docker image.**

```bash
docker build -t openclaw:local .
```

Expected output: multi-stage build completes with `Successfully built <image-id>` and `Successfully tagged openclaw:local`.

**9. Start the services.**

```bash
docker compose up -d
```

Expected output:

```
[+] Running 2/2
 ✔ Container openclawtor-openclaw-gateway-1  Started
 ✔ Container openclawtor-openclaw-cli-1      Started
```

**10. Verify the gateway health.**

```bash
curl -s http://localhost:18789/healthz
```

Expected output: `{"status":"ok"}` with HTTP 200.

---

### Marketing Bot Standalone Setup

Use this path if you only need `marketingbot.py` and do not want to run the full OpenClaw gateway.

**1. Clone the repository (or copy only `marketingbot.py`).**

```bash
git clone https://github.com/bitbybit91/openclawtor.git
cd openclawtor
git checkout copilot/add-telegram-marketing-bot
```

If you only need the bot file:

```bash
curl -fsSL https://raw.githubusercontent.com/bitbybit91/openclawtor/copilot/add-telegram-marketing-bot/marketingbot.py -o marketingbot.py
```

**2. Create and activate a virtual environment.**

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# or: .venv\Scripts\activate.bat  (Windows Command Prompt)
# or: .venv\Scripts\Activate.ps1  (Windows PowerShell)
```

Expected output: your shell prompt changes to show `(.venv)`.

**3. Install Python dependencies.**

```bash
pip install \
  "python-telegram-bot>=20,<22" \
  "apscheduler>=3.10,<4" \
  "cryptography>=42,<44" \
  "tweepy>=4.14,<5" \
  "praw>=7.7,<8" \
  "requests>=2.31,<3"
```

Expected output: pip downloads and installs all packages. If you see `ERROR: Could not find a version that satisfies the requirement`, verify your Python version is 3.10 or later.

**4. Create required directories and log files.**

```bash
sudo mkdir -p /etc/marketingbot
sudo chown "$USER" /etc/marketingbot
sudo touch /var/log/marketingbot.log /var/log/marketingbot_posts.log
sudo chown "$USER" /var/log/marketingbot.log /var/log/marketingbot_posts.log
```

If you do not have `sudo` access (e.g., a shared server or CI environment), override the paths in `marketingbot.py`:

```python
BASE_DIR = Path("./data/marketingbot")
POST_LOG_PATH = Path("./logs/marketingbot_posts.log")
BOT_LOG_PATH = Path("./logs/marketingbot.log")
```

Then create the local directories:

```bash
mkdir -p ./data/marketingbot ./logs
```

**5. Set environment variables.**

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCDEF..."
export TELEGRAM_CHAT_ID="123456789"
```

Replace the values with your actual token and chat ID.

**6. Run the bot.**

```bash
python marketingbot.py
```

Expected output:

```
2026-05-16 08:40:39,000 INFO marketingbot: Marketing bot started. Restored 0 scheduled jobs.
```

The process runs in the foreground polling the Telegram API. Press `Ctrl+C` to stop.

**7. Verify in Telegram.**

Open Telegram and send `/start` to your bot. The expected welcome response lists all available commands.

---

## 6. Build

### Development Build (OpenClaw)

Start the gateway in watch mode:

```bash
pnpm dev
```

The CLI and gateway rebuild automatically when source files change. The control UI is accessible at `http://localhost:18789`.

### Production Build (OpenClaw)

Build the full TypeScript monorepo:

```bash
pnpm build
```

Build only the control UI:

```bash
pnpm ui:build
```

Verify outputs:

```bash
ls dist/index.js dist/control-ui/index.html
# Both files must exist
```

Build the Docker image:

```bash
docker build -t openclaw:local .
```

### Production Run (Marketing Bot)

**Run in the background with nohup:**

```bash
nohup python marketingbot.py &> /var/log/marketingbot.log &
echo $! > /tmp/marketingbot.pid
```

To stop:

```bash
kill "$(cat /tmp/marketingbot.pid)"
```

> **Note:** `/var/run/` typically requires root permissions. `/tmp/marketingbot.pid` is writable by any user. For a persistent PID file location owned by your user, use `~/.local/run/marketingbot.pid` (create the directory first with `mkdir -p ~/.local/run`).

**Run as a systemd service:**

Create `/etc/systemd/system/marketingbot.service`:

```ini
[Unit]
Description=Telegram Marketing Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/opt/openclawtor
Environment=TELEGRAM_BOT_TOKEN=123456789:ABCDEF...
Environment=TELEGRAM_CHAT_ID=123456789
ExecStart=/opt/openclawtor/.venv/bin/python /opt/openclawtor/marketingbot.py
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/marketingbot.log
StandardError=append:/var/log/marketingbot.log

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable marketingbot
sudo systemctl start marketingbot
sudo systemctl status marketingbot
```

### CI/CD Build (Headless)

The following GitHub Actions workflow performs a complete headless build, test, and Docker image build:

```yaml
name: CI

on:
  push:
    branches: [main, "copilot/**"]
  pull_request:

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Node.js 24
        uses: actions/setup-node@v4
        with:
          node-version: "24"

      - name: Enable corepack
        run: corepack enable

      - name: Install Node dependencies
        run: pnpm install --frozen-lockfile
        env:
          CI: "true"

      - name: Build TypeScript
        run: pnpm build
        env:
          CI: "true"

      - name: Run Vitest tests
        run: pnpm test
        env:
          CI: "true"
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install \
            "python-telegram-bot>=20,<22" \
            "apscheduler>=3.10,<4" \
            "cryptography>=42,<44" \
            "tweepy>=4.14,<5" \
            "praw>=7.7,<8" \
            "requests>=2.31,<3" \
            pytest pytest-asyncio pytest-cov

      - name: Run pytest
        run: pytest skills/ -v
        env:
          CI: "true"

      - name: Build Docker image
        run: docker build -t openclaw:local .
        env:
          DOCKER_BUILDKIT: "1"
```

---

## 7. Running Tests

### JavaScript / TypeScript (Vitest)

**Run the full test suite:**

```bash
pnpm test
```

Expected output: Vitest runs all test files, reports passed/failed counts, and exits 0.

**Run a single test file:**

```bash
pnpm vitest run path/to/test.ts
# Example:
pnpm vitest run src/commands/onboard-search.test.ts
```

**Run with V8 coverage:**

```bash
pnpm test:coverage
```

Coverage output is written to `coverage/`. The configured thresholds are 70% for lines, branches, functions, and statements.

**Run tests changed relative to `origin/main`:**

```bash
pnpm test:changed
```

**Vitest configuration file:** `vitest.config.ts` (re-exports from `test/vitest/vitest.config.ts`).

**Run inside Docker (headless):**

```bash
docker run --rm openclaw:local pnpm test
```

Expected output: same as local run, exits 0 on all passing.

### Python (pytest)

Test paths are configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["skills"]
python_files = ["test_*.py"]
```

**Run the full Python test suite:**

```bash
source .venv/bin/activate
pytest skills/ -v
```

Expected output: pytest collects and runs all `test_*.py` files under `skills/`, reports `N passed` at the end.

**Run a single test file:**

```bash
pytest skills/test_marketingbot.py -v
```

**Run with HTML coverage report:**

```bash
pytest --cov=. --cov-report=html skills/
# Report is written to htmlcov/index.html
```

**Lint Python with ruff:**

```bash
ruff check .
```

`ruff` is configured in `pyproject.toml` with `target-version = "py310"` and selects `E9`, `F63`, `F7`, `F82`, and `I` rule sets.

---

## 8. Common Issues and Troubleshooting

| Error Message / Symptom | Cause | Fix |
|-------------------------|-------|-----|
| `PermissionError: [Errno 13] Permission denied: '/etc/marketingbot/secret.key'` | Bot process cannot write to `/etc/marketingbot/` | `sudo mkdir -p /etc/marketingbot && sudo chown "$USER" /etc/marketingbot` |
| `Not authorized.` in Telegram | The sending chat's ID does not match `TELEGRAM_CHAT_ID` | Find your real chat ID with `@userinfobot` and update `TELEGRAM_CHAT_ID` |
| `RuntimeError: Missing TELEGRAM_BOT_TOKEN environment variable` | Env var not exported in the current shell | `export TELEGRAM_BOT_TOKEN="..."` and rerun |
| `telegram.error.InvalidToken` | `TELEGRAM_BOT_TOKEN` is malformed or revoked | Token must be format `123456789:ABCDEF...` from BotFather — regenerate if necessary |
| `ModuleNotFoundError: No module named 'telegram'` | Virtual environment is not active | `source .venv/bin/activate` then rerun |
| `tweepy.errors.Unauthorized: 401` | Twitter/X API keys are invalid or expired | Regenerate keys at [developer.twitter.com](https://developer.twitter.com) and update with `/addcredentials twitter api_key <value>` |
| `praw.exceptions.OAuthException` | Reddit client credentials are wrong or account has 2FA enabled | Use app credentials from [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps). For accounts with 2FA enabled, use an OAuth2 refresh token flow instead of password auth — create a Reddit app of type "script", obtain a refresh token via the OAuth2 authorization flow, and supply it as `refresh_token` in your credentials. Password auth (`username`/`password`) requires 2FA to be disabled on the Reddit account. |
| `ERROR: matrix-sdk-crypto native addon missing` | pnpm install silently failed for this CPU architecture | Run `pnpm install --frozen-lockfile` on a supported architecture (amd64 or arm64) |
| `docker: Error response from daemon: driver failed programming external connectivity` | Port 18789 or 18790 is already bound by another process | `lsof -i :18789` or `ss -ltnp \| grep 18789` to identify the process, then `kill <PID>` |
| `Killed` during `pnpm install` inside Docker build | Out of memory on the build host | Add `--memory=4g` to `docker build`, or set `NODE_OPTIONS=--max-old-space-size=2048` in the build environment |
| `OPENCLAW_GATEWAY_TOKEN cannot be the example value` | A placeholder token was copied from documentation | Generate a real token: `openssl rand -hex 32` and set it in `.env` |
| `pnpm: command not found` | corepack not enabled | `corepack enable && corepack prepare pnpm@latest --activate` |
| A2UI bundle fails during Docker cross-arch build | QEMU cross-compilation limitation for the A2UI canvas bundler | Non-fatal; a stub is created automatically. Build natively per-arch for full functionality |
| `cryptography.fernet.InvalidToken` on bot startup | Fernet key at `/etc/marketingbot/secret.key` was replaced after credentials were encrypted | Delete `/etc/marketingbot/credentials.json` and re-add credentials with `/addcredentials` |

---

## 9. Project Structure

```text
openclawtor/                          # Fork of openclaw/openclaw
├── marketingbot.py                   # NEW: Telegram marketing automation bot (Python)
├── MARKETINGBOT_README.md            # NEW: Marketing bot feature/command reference
├── openclaw.mjs                      # OpenClaw CLI entrypoint
├── Dockerfile                        # Multi-stage production Docker build (Node 24 + Bun)
├── Dockerfile.sandbox                # Sandbox isolation variant
├── Dockerfile.sandbox-browser        # Browser sandbox isolation variant
├── Dockerfile.sandbox-common         # Shared sandbox base
├── docker-compose.yml                # Gateway + CLI services
├── docker-setup.sh                   # Automated Docker setup script
├── setup-podman.sh                   # Podman alternative setup
├── Makefile                          # build → pnpm build
├── package.json                      # Root pnpm workspace manifest
├── pnpm-workspace.yaml               # Monorepo workspace config
├── pyproject.toml                    # Python tooling (ruff, pytest)
├── tsconfig.json                     # TypeScript root config
├── vitest.config.ts                  # Vitest test runner config (re-exports from test/)
├── tsdown.config.ts                  # tsdown bundler config
├── .env.example                      # All environment variable documentation
├── src/                              # Core TypeScript source (gateway, CLI, channels)
├── ui/                               # Control UI frontend (Vite/React)
├── apps/                             # Platform apps (iOS, Android, macOS)
├── extensions/                       # Bundled provider and tool plugins
├── packages/                         # Internal shared packages
├── skills/                           # Skills + Python tests (pytest testpath)
├── test/                             # TypeScript/Vitest test configs and helpers
├── test-fixtures/                    # Test fixture data
├── scripts/                          # Build, Docker, CI, and utility automation
├── docs/                             # Documentation source
├── qa/                               # QA tooling and lab
├── assets/                           # Static assets
├── vendor/                           # Vendored dependencies
├── .github/                          # CI/CD workflows and issue templates
│   └── workflows/
│       ├── ci.yml                    # Main CI workflow
│       ├── docker-release.yml        # Docker image release
│       ├── openclaw-npm-release.yml  # npm publish workflow
│       └── ...                       # Additional workflows
├── git-hooks/                        # Pre-commit and other git hooks
└── .agents/ / .pi/ / .vscode/        # Agent, PI, and editor configuration
```

---

## 10. Scripts Reference

### pnpm scripts (root `package.json`)

| Script | Command | Description |
|--------|---------|-------------|
| `build` | `node scripts/build-all.mjs` | Build the full TypeScript monorepo |
| `build:docker` | tsdown + postbuild + stamp + copy scripts | Docker-optimized build (used inside Dockerfile) |
| `dev` | `node scripts/run-node.mjs` | Run the CLI in dev mode |
| `test` | `node scripts/test-projects.mjs` | Run all Vitest test projects |
| `test:coverage` | vitest run with `--coverage` | Run tests with V8 coverage |
| `test:changed` | `node scripts/test-projects.mjs --changed origin/main` | Run tests for files changed vs `origin/main` |
| `test:bundled` | vitest run `vitest.bundled.config.ts` | Run bundled plugin tests |
| `test:channels` | vitest run `vitest.channels.config.ts` | Run channel-specific tests |
| `test:contracts` | channels + plugins contract tests | Run all contract tests |
| `check` | conflict markers + import cycles + tsgo + lint | Full local gate |
| `tsgo` | `node scripts/run-tsgo.mjs` | TypeScript type-check |
| `lint` | `node scripts/run-oxlint.mjs` | Run Oxlint linter |
| `lint:fix` | oxlint --fix + format | Fix lint issues and reformat |
| `format` | `oxfmt --write` | Format all source files |
| `format:check` | `oxfmt --check --threads=1` | Check formatting without writing |
| `format:fix` | `oxfmt --write` | Alias for `format` |
| `ui:build` | vite build | Build the control UI to `dist/control-ui/` |
| `canvas:a2ui:bundle` | `node scripts/bundle-a2ui.mjs` | Bundle the A2UI canvas component |
| `config:docs:gen` | generate-config-doc-baseline.ts | Regenerate config schema baseline |
| `config:docs:check` | generate-config-doc-baseline.ts --check | Check config schema drift |
| `plugin-sdk:api:gen` | generate-plugin-sdk-api-baseline.ts | Regenerate plugin SDK API baseline |
| `plugin-sdk:api:check` | generate-plugin-sdk-api-baseline.ts --check | Check plugin SDK drift |
| `qa:lab:build` | vite build QA lab UI | Build the QA lab web UI |
| `qa:lab:up` | qa-lab-up.ts | Start a local QA lab environment |
| `docs:check-links` | docs-link-audit.mjs | Audit docs for broken links |
| `docs:spellcheck` | docs-spellcheck.sh | Run docs spell check |

### Makefile Targets

| Target | Command | Description |
|--------|---------|-------------|
| `build` | `pnpm build` | Builds the full TypeScript monorepo |

### Marketing Bot Scripts

| Action | Command | Description |
|--------|---------|-------------|
| Start bot | `python marketingbot.py` | Run the Telegram marketing bot |
| Install deps | `pip install "python-telegram-bot>=20,<22" ...` | Install all Python dependencies |
| Run Python tests | `pytest skills/` | Run the Python test suite |
| Lint Python | `ruff check .` | Run the ruff linter on all Python files |
| Format Python | `ruff format .` | Auto-format all Python files |
| Run bot in background | `nohup python marketingbot.py &> /var/log/marketingbot.log &` | Start bot as a background process |

### Marketing Bot Telegram Command Reference

| Command | Syntax | Description |
|---------|--------|-------------|
| `/start` | `/start` | Welcome message and command list |
| `/help` | `/help` | Full command help |
| `/addcredentials` | `/addcredentials <platform> <key> <value>` | Add or update a credential key for a platform |
| `/listcredentials` | `/listcredentials` | Show platform names and key names (values hidden) |
| `/removecredentials` | `/removecredentials <platform>` | Remove all credentials for a platform |
| `/setinstructions` | `/setinstructions <platform>` | Interactive instruction setup wizard |
| `/getinstructions` | `/getinstructions <platform>` | Show saved instruction config for a platform |
| `/post` | `/post <platform> <product_or_service>` | Compose and publish immediately |
| `/schedulepost` | `/schedulepost <platform> <product> <YYYY-MM-DDTHH:MM>` | Schedule a post for a future time |
| `/listscheduled` | `/listscheduled` | List all scheduled posts |
| `/cancelscheduled` | `/cancelscheduled <job_id>` | Cancel a scheduled post by UUID |
| `/campaign` | `/campaign <campaign_name>` | Interactive campaign definition wizard |
| `/runcampaign` | `/runcampaign <campaign_name>` | Execute a saved campaign across all platforms |
| `/listcampaigns` | `/listcampaigns` | List campaigns and their statuses |
| `/generatecontent` | `/generatecontent <platform> <product>` | Generate a draft without posting |
| `/approve` | `/approve` | Publish the last generated draft |
| `/edit` | `/edit <new_text>` | Replace the last draft with new text and publish |
| `/analytics` | `/analytics <platform>` | Show local posting stats for a platform |
| `/clearlog` | `/clearlog <platform>` | Remove log entries for a specific platform |
| `/status` | `/status` | Show bot uptime and stored object counts |
| `/cancel` | `/cancel` | Cancel the current interactive conversation |

---

## 11. Contributing

Contributions are welcome. Follow these steps before opening a pull request.

**1. Fork and clone.**

```bash
git clone https://github.com/YOUR_USERNAME/openclawtor.git
cd openclawtor
```

**2. Create a feature branch.**

Use one of the following naming conventions:

- `feature/<short-description>` — new functionality
- `fix/<short-description>` — bug fixes
- `chore/<short-description>` — maintenance, refactoring, dependency updates

```bash
git checkout -b feature/my-new-feature
```

**3. Install dependencies.**

```bash
corepack enable
pnpm install --frozen-lockfile
source .venv/bin/activate
pip install "python-telegram-bot>=20,<22" "apscheduler>=3.10,<4" "cryptography>=42,<44" \
            "tweepy>=4.14,<5" "praw>=7.7,<8" "requests>=2.31,<3" \
            pytest ruff
```

**4. Install pre-commit hooks.**

```bash
pre-commit install
```

The pre-commit config is in `.pre-commit-config.yaml`. Hooks run automatically on `git commit`.

**5. Make your changes.**

Keep changes focused. Do not bundle unrelated fixes in a single PR.

**6. Run the full verification gate before submitting.**

```bash
# TypeScript
pnpm lint
pnpm test
pnpm build

# Python
ruff check .
pytest skills/ -v
```

All commands must exit 0.

**7. Check for secrets and dead code.**

```bash
# Ensure no secrets are committed
detect-secrets scan --baseline .secrets.baseline

# Check for dead code (optional but recommended)
pnpm deadcode:knip
```

**8. Open a pull request.**

Push your branch to your fork and open a PR against `copilot/add-telegram-marketing-bot` (or `main` as appropriate). Fill in all sections of the PR template (`.github/pull_request_template.md`).

**PR checklist:**

- All TypeScript tests pass (`pnpm test`)
- All Python tests pass (`pytest skills/`)
- Lint passes (`pnpm lint` and `ruff check .`)
- No secrets committed (`.detect-secrets.cfg` / `.secrets.baseline`)
- Markdown lint passes (`pnpm lint:docs`)
- No dead code introduced (`knip.config.ts`)

---

## 12. License

MIT License — see the [LICENSE](LICENSE) file for full text.

Copyright OpenClaw contributors.
