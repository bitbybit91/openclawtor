# WebManager

`webmanager.py` is a standalone Telegram bot for provisioning and managing Apache sites exposed through Tor hidden services. It creates sites under `/var/www`, stores metadata in `/etc/webmanager/sites.json`, and controls Apache plus `tor@default` entirely from Telegram.

## Features

- Async Telegram bot built with `python-telegram-bot` v20+
- Creates `wordpress`, `html`, and `php` sites
- Provisions Apache vhosts in `/etc/apache2/sites-available`
- Appends Tor hidden service blocks to `/etc/tor/torrc`
- Waits for generated `.onion` hostnames and stores them in the registry
- Generates `sitemap.xml`, `robots.txt`, and `.htaccess`
- Enables, disables, checks, and repairs managed sites
- Posts site promotions to Reddit using Reddit's OAuth API
- Logs to `/var/log/webmanager.log` by default

## Requirements

- Python 3.10+
- Apache with `a2ensite`, `a2enmod`, and `apache2ctl`
- Tor configured with the `tor@default` service unit
- `systemctl`
- `mysql` CLI for WordPress site creation
- Root privileges (the script writes to `/etc`, `/var/lib/tor`, and `/var/www`)

## Install Python dependency

```bash
python3 -m pip install --upgrade python-telegram-bot==22.7
```

The script uses only the Python standard library besides `python-telegram-bot`.

## Environment variables

### Required

| Variable             | Purpose                               |
| -------------------- | ------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token                |
| `TELEGRAM_CHAT_ID`   | Only this chat ID can control the bot |

### Optional site-management configuration

| Variable                                | Default                               |
| --------------------------------------- | ------------------------------------- |
| `WEBMANAGER_BASE_WWW_DIR`               | `/var/www`                            |
| `WEBMANAGER_APACHE_SITES_AVAILABLE_DIR` | `/etc/apache2/sites-available`        |
| `WEBMANAGER_TORRC_PATH`                 | `/etc/tor/torrc`                      |
| `WEBMANAGER_HIDDEN_SERVICE_ROOT`        | `/var/lib/tor`                        |
| `WEBMANAGER_REGISTRY_PATH`              | `/etc/webmanager/sites.json`          |
| `WEBMANAGER_APACHE_SERVICE`             | `apache2`                             |
| `WEBMANAGER_TOR_SERVICE`                | `tor@default`                         |
| `WEBMANAGER_APACHE_USER`                | `www-data`                            |
| `WEBMANAGER_APACHE_GROUP`               | `www-data`                            |
| `WEBMANAGER_LOG_PATH`                   | `/var/log/webmanager.log`             |
| `WEBMANAGER_LOG_LEVEL`                  | `INFO`                                |
| `WEBMANAGER_COMMAND_TIMEOUT_SECONDS`    | `120`                                 |
| `WEBMANAGER_WORDPRESS_DOWNLOAD_URL`     | `https://wordpress.org/latest.tar.gz` |

### Optional MySQL configuration for WordPress

| Variable                           | Default     |
| ---------------------------------- | ----------- |
| `WEBMANAGER_MYSQL_ADMIN_USER`      | `root`      |
| `WEBMANAGER_MYSQL_ADMIN_PASSWORD`  | empty       |
| `WEBMANAGER_MYSQL_HOST`            | `127.0.0.1` |
| `WEBMANAGER_MYSQL_PORT`            | `3306`      |
| `WEBMANAGER_MYSQL_DATABASE_PREFIX` | `wm_`       |
| `WEBMANAGER_MYSQL_USER_PREFIX`     | `wm_`       |

### Optional Reddit configuration

`/postreddit` requires all of the following:

- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USERNAME`
- `REDDIT_PASSWORD`
- `REDDIT_USER_AGENT` (optional, defaults to `webmanager/1.0`)

## Running the bot

```bash
export TELEGRAM_BOT_TOKEN='123456:example'
export TELEGRAM_CHAT_ID='123456789'
sudo -E python3 webmanager.py
```

## Telegram commands

| Command                            | Description                                                           |
| ---------------------------------- | --------------------------------------------------------------------- |
| `/start`                           | Welcome message and command list                                      |
| `/help`                            | Show all commands                                                     |
| `/newsite <domain> <type>`         | Create a new site of type `wordpress`, `html`, or `php`               |
| `/listsites`                       | List all managed sites                                                |
| `/siteinfo <domain>`               | Show type, onion address, Apache config path, sitemap URL, and status |
| `/enablesite <domain>`             | Enable a vhost and reload Apache                                      |
| `/disablesite <domain>`            | Disable a vhost and reload Apache                                     |
| `/updateseo <domain>`              | Regenerate `sitemap.xml` and `robots.txt`                             |
| `/postreddit <domain> <subreddit>` | Submit a promotion post to Reddit                                     |
| `/checkstatus`                     | Check Apache, Tor, and all managed sites                              |
| `/fixsite <domain>`                | Rebuild common site configuration and permissions                     |

## What `/newsite` does

For every site type, WebManager:

1. Creates `/var/www/<domain>/public_html`
2. Writes an Apache vhost config at `/etc/apache2/sites-available/<domain>.conf`
3. Enables `rewrite`, `headers`, and `expires`
4. Enables the vhost with `a2ensite`
5. Reloads Apache
6. Appends a dedicated Tor hidden service block to `/etc/tor/torrc`
7. Reloads `tor@default`
8. Waits up to 30 seconds for the Tor `hostname` file
9. Regenerates SEO files and stores site metadata in `/etc/webmanager/sites.json`

Extra actions by type:

- `wordpress`: downloads the latest WordPress tarball, creates a MySQL database and user, and writes `wp-config.php`
- `html`: writes a styled `index.html`
- `php`: writes a styled `index.php` landing page instead of exposing `phpinfo()`

## SEO files

For every managed site, WebManager maintains:

- `sitemap.xml` with `lastmod`, `changefreq`, and `priority`
- `robots.txt` pointing at the current sitemap URL
- `.htaccess`
  - WordPress: rewrite rules for permalinks
  - HTML/PHP: cache headers and common security headers

## Registry format

Managed sites are stored in JSON at `/etc/webmanager/sites.json`. Each record includes:

- domain
- site type
- onion address
- Apache config path
- sitemap URL
- enablement state
- timestamps
- document root and Tor hidden service directory
- WordPress database details when applicable

## Operational notes

- Run the script as root or via a service account with equivalent privileges.
- The Apache config uses `ServerName <domain>` and automatically adds `ServerAlias <onion>` after the hidden service is created so the Tor hostname is routed to the correct vhost.
- Unauthorized Telegram chats are ignored silently and logged.
- The script returns explicit Telegram error messages for command failures.
- If Tor or Apache are down, `/checkstatus` and `/fixsite` will report that state.

## Suggested systemd unit

```ini
[Unit]
Description=WebManager Telegram bot
After=network-online.target apache2.service tor@default.service
Wants=network-online.target

[Service]
Type=simple
Environment=TELEGRAM_BOT_TOKEN=123456:example
Environment=TELEGRAM_CHAT_ID=123456789
ExecStart=/usr/bin/python3 /opt/webmanager/webmanager.py
WorkingDirectory=/opt/webmanager
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Validation

Useful local validation commands:

```bash
python3 -m py_compile webmanager.py
python3 -m pytest -q skills/webmanager/test_webmanager.py
```
