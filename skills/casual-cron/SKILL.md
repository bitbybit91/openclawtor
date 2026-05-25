---
name: casual-cron
description: Create OpenClaw cron jobs from natural-language time descriptions. Use when a user says things like "remind me every Monday at 9am", "run this script every hour", "ping me daily at noon", or "check X every 30 minutes". Translates intent into `openclaw cron add` commands with the correct cron expression, session, and wake mode.
metadata: { "openclaw": { "emoji": "⏰" } }
---

# Casual Cron — Natural Language Cron Scheduling

Translate natural language into `openclaw cron` commands. No guessing cron syntax.

## Quick reference

```bash
# Add a job
openclaw cron add \
  --name "Job name"  \
  --cron "*/15 * * * *" \
  --session main \
  --system-event "Your prompt/event text" \
  --wake now

# One-shot at a specific time
openclaw cron add \
  --name "One-shot reminder" \
  --at "2026-06-01T09:00:00Z" \
  --session main \
  --system-event "Time to review the report" \
  --wake now \
  --delete-after-run

# List jobs
openclaw cron list

# Remove a job
openclaw cron remove --name "Job name"
# or by id
openclaw cron remove --id <id>

# Pause / resume
openclaw cron pause --name "Job name"
openclaw cron resume --name "Job name"
```

## Natural language → cron expression

| User says                   | Cron expression |
| --------------------------- | --------------- |
| every minute                | `* * * * *`     |
| every 5 minutes             | `*/5 * * * *`   |
| every 15 minutes            | `*/15 * * * *`  |
| every 30 minutes            | `*/30 * * * *`  |
| every hour                  | `0 * * * *`     |
| every 2 hours               | `0 */2 * * *`   |
| every day at noon           | `0 12 * * *`    |
| every day at 9am            | `0 9 * * *`     |
| every weekday at 8am        | `0 8 * * 1-5`   |
| every Monday at 9am         | `0 9 * * 1`     |
| every Sunday at 6pm         | `0 18 * * 0`    |
| first of every month at 7am | `0 7 1 * *`     |
| every 6 hours               | `0 */6 * * *`   |

All times are UTC unless the user specifies a timezone — convert to UTC before generating the cron expression.

## Standard flags

| Flag                 | Description                                                       |
| -------------------- | ----------------------------------------------------------------- |
| `--name`             | Human-readable name (required, unique)                            |
| `--cron`             | Standard 5-field cron expression                                  |
| `--at`               | ISO 8601 timestamp for a one-shot job                             |
| `--session`          | Session to wake (usually `main`)                                  |
| `--system-event`     | Text injected as a system event / prompt when the job fires       |
| `--wake`             | `now` = wake immediately when triggered; `heartbeat` = next cycle |
| `--delete-after-run` | Remove the job automatically after it runs once                   |
| `--disabled`         | Create the job in paused state                                    |

## Full example workflow

User: "Remind me to check my email every weekday morning at 8am London time"

1. Convert 8am London (BST = UTC+1) → 7am UTC → cron `0 7 * * 1-5`
2. Run:

```bash
openclaw cron add \
  --name "Morning email check" \
  --cron "0 7 * * 1-5" \
  --session main \
  --system-event "Good morning! Time to check your email." \
  --wake now
```

3. Confirm with: `openclaw cron list`

## Rules

- Always convert to UTC before writing the cron expression.
- Use `--delete-after-run` for one-off reminders; use `--at` instead of `--cron` when the user gives a specific date and time.
- Never overwrite an existing job name; check `openclaw cron list` first and suggest a unique name if there is a conflict.
- Keep `--system-event` text action-oriented — the agent will see it as a prompt.
