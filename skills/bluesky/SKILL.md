---
name: bluesky
description: Post, reply, like, repost, follow, search, and manage a Bluesky account via the AT Protocol HTTP API. Use for social-media marketing automation, audience building, and content distribution on Bluesky.
homepage: https://bsky.app
metadata:
  {
    "openclaw":
      { "emoji": "🦋", "requires": { "env": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"] } },
  }
---

# Bluesky — AT Protocol Social Automation

Bluesky uses the AT Protocol (`atproto`). All API calls hit `https://bsky.social/xrpc/` (or your PDS host).

## Auth — create a session

```bash
SESSION=$(curl -s -X POST https://bsky.social/xrpc/com.atproto.server.createSession \
  -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$BLUESKY_HANDLE\",\"password\":\"$BLUESKY_APP_PASSWORD\"}")
ACCESS_JWT=$(echo "$SESSION" | jq -r '.accessJwt')
DID=$(echo "$SESSION" | jq -r '.did')
```

Store `ACCESS_JWT` in a shell variable; it expires in ~2 hours. Refresh with `com.atproto.server.refreshSession` using `refreshJwt`.

## Post (create record)

```bash
curl -s -X POST https://bsky.social/xrpc/com.atproto.repo.createRecord \
  -H "Authorization: Bearer $ACCESS_JWT" \
  -H "Content-Type: application/json" \
  -d "{
    \"repo\": \"$DID\",
    \"collection\": \"app.bsky.feed.post\",
    \"record\": {
      \"\$type\": \"app.bsky.feed.post\",
      \"text\": \"Hello from OpenClaw 🦞\",
      \"createdAt\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
    }
  }"
```

Max post length: **300 characters**.

## Reply to a post

Add a `reply` field with the parent's `uri` and `cid`:

```json
"reply": {
  "root": { "uri": "at://...", "cid": "..." },
  "parent": { "uri": "at://...", "cid": "..." }
}
```

## Like a post

```bash
curl -s -X POST https://bsky.social/xrpc/com.atproto.repo.createRecord \
  -H "Authorization: Bearer $ACCESS_JWT" \
  -H "Content-Type: application/json" \
  -d "{
    \"repo\": \"$DID\",
    \"collection\": \"app.bsky.feed.like\",
    \"record\": {
      \"\$type\": \"app.bsky.feed.like\",
      \"subject\": { \"uri\": \"at://...\", \"cid\": \"...\" },
      \"createdAt\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
    }
  }"
```

## Repost

```bash
# collection: app.bsky.feed.repost, same subject shape as like
```

## Follow a user

```bash
# collection: app.bsky.graph.follow
# record: { "$type": "app.bsky.graph.follow", "subject": "<did>", "createdAt": "..." }
```

## Unfollow / delete a record

```bash
curl -s -X POST https://bsky.social/xrpc/com.atproto.repo.deleteRecord \
  -H "Authorization: Bearer $ACCESS_JWT" \
  -H "Content-Type: application/json" \
  -d "{\"repo\":\"$DID\",\"collection\":\"app.bsky.feed.like\",\"rkey\":\"<rkey>\"}"
```

## Search posts

```bash
curl -s "https://bsky.social/xrpc/app.bsky.feed.searchPosts?q=openclaw&limit=10" \
  -H "Authorization: Bearer $ACCESS_JWT"
```

## Get timeline

```bash
curl -s "https://bsky.social/xrpc/app.bsky.feed.getTimeline?limit=20" \
  -H "Authorization: Bearer $ACCESS_JWT" | jq '.feed[].post.record.text'
```

## Get profile

```bash
curl -s "https://bsky.social/xrpc/app.bsky.actor.getProfile?actor=$BLUESKY_HANDLE" \
  -H "Authorization: Bearer $ACCESS_JWT"
```

## Marketing workflow tips

- Draft posts in bulk with the agent, then schedule them via `openclaw cron`.
- Use `app.bsky.feed.searchPosts` to monitor brand mentions or competitor topics.
- Chain: search → filter by relevance → like/reply to high-engagement posts — run as a daily cron job.
- Images: upload a blob first (`com.atproto.repo.uploadBlob`), then attach `embed.$type: app.bsky.embed.images`.

## Environment variables

| Variable               | Purpose                                        |
| ---------------------- | ---------------------------------------------- |
| `BLUESKY_HANDLE`       | Your handle, e.g. `yourname.bsky.social`       |
| `BLUESKY_APP_PASSWORD` | App password from Settings > App passwords     |
| `BLUESKY_PDS_HOST`     | Optional custom PDS host (default bsky.social) |
