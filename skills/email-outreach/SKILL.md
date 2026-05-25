---
name: email-outreach
description: Draft, personalize, and send marketing or outreach emails via SMTP (sendmail / curl / Python smtplib). Use for email campaign drafting, bulk personalized sends, follow-up sequences, and newsletter dispatch. Also useful for transactional notifications from automation workflows.
metadata:
  {
    "openclaw":
      {
        "emoji": "📧",
        "requires":
          {
            "env": ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"],
            "anyBins": ["curl", "python3", "sendmail"],
          },
      },
  }
---

# Email Outreach

Draft and send emails via SMTP. Covers one-off sends, personalized bulk campaigns, and scheduled sequences.

## Quick send (Python — most portable)

```python
import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASSWORD"]
FROM_NAME = os.environ.get("SMTP_FROM_NAME", SMTP_USER)

def send_email(to: str, subject: str, body_text: str, body_html: str | None = None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.ehlo()
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [to], msg.as_string())
        print(f"Sent to {to}")

# Example
send_email(
    to="prospect@example.com",
    subject="Quick question about your project",
    body_text="Hi Jane,\n\nI noticed you're working on X...",
)
```

Save as `/tmp/send_email.py` and invoke: `python3 /tmp/send_email.py`

## Bulk personalized send

Given a CSV `leads.csv` with columns `name,email,company`:

```python
import csv, time

with open("leads.csv") as f:
    for row in csv.DictReader(f):
        send_email(
            to=row["email"],
            subject=f"Quick question for {row['company']}",
            body_text=f"Hi {row['name']},\n\nWe help companies like {row['company']}...",
        )
        time.sleep(1)  # rate limit — 1 email/sec
```

## Send via curl (Mailgun example)

```bash
curl -s --user "api:$MAILGUN_API_KEY" \
  "https://api.mailgun.net/v3/$MAILGUN_DOMAIN/messages" \
  -F from="OpenClaw <openclaw@$MAILGUN_DOMAIN>" \
  -F to="prospect@example.com" \
  -F subject="Hello" \
  -F text="Body text here"
```

## Scheduling a sequence with openclaw cron

```bash
# Day 0: initial outreach
openclaw cron add --name "outreach-d0" \
  --at "$(date -u -d '+0 hours' +%Y-%m-%dT%H:%M:%SZ)" \
  --session main \
  --system-event "Send initial outreach email to leads.csv" \
  --wake now --delete-after-run

# Day 3: follow-up
openclaw cron add --name "outreach-d3" \
  --at "$(date -u -d '+3 days' +%Y-%m-%dT%H:%M:%SZ)" \
  --session main \
  --system-event "Send follow-up email (day 3) to non-responders in leads.csv" \
  --wake now --delete-after-run
```

## Copywriting tips (agent-assisted)

Ask the agent to draft subject lines and body copy first:

> "Write 3 cold email subject line variants for [product/service] targeting [audience]. Keep each under 50 characters."

> "Write a 3-sentence cold email body for [product] to [persona]. Focus on [pain point]. End with a soft CTA to reply."

## Environment variables

| Variable          | Purpose                              |
| ----------------- | ------------------------------------ |
| `SMTP_HOST`       | SMTP server hostname                 |
| `SMTP_PORT`       | SMTP port (usually 587 for STARTTLS) |
| `SMTP_USER`       | SMTP username / sender address       |
| `SMTP_PASSWORD`   | SMTP password or app password        |
| `SMTP_FROM_NAME`  | Display name for the From header     |
| `MAILGUN_API_KEY` | Optional — Mailgun API key           |
| `MAILGUN_DOMAIN`  | Optional — Mailgun sending domain    |
