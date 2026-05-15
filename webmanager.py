#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import http.client
import json
import logging
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING
from xml.sax.saxutils import escape as xml_escape

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
except ImportError:
    Update = Any  # type: ignore[assignment]
    Application = None  # type: ignore[assignment]
    CommandHandler = None  # type: ignore[assignment]

    class _ContextTypes:
        DEFAULT_TYPE = Any

    ContextTypes = _ContextTypes()  # type: ignore[assignment]

if TYPE_CHECKING:
    from telegram.ext import ContextTypes as TelegramContextTypes


VALID_SITE_TYPES = {"wordpress", "html", "php"}
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{3,21}$")
WORDPRESS_URL = "https://wordpress.org/latest.tar.gz"
DEFAULT_COMMAND_TIMEOUT = 120

COMMAND_DESCRIPTIONS: list[tuple[str, str]] = [
    ("/start", "Welcome message and command overview"),
    ("/newsite <domain> <type>", "Create a new site (wordpress, html, php)"),
    ("/listsites", "List all managed sites"),
    ("/siteinfo <domain>", "Show detailed info for a site"),
    ("/enablesite <domain>", "Enable an Apache vhost and reload Apache"),
    ("/disablesite <domain>", "Disable an Apache vhost and reload Apache"),
    ("/updateseo <domain>", "Regenerate sitemap.xml and robots.txt"),
    ("/postreddit <domain> <subreddit>", "Post a promotion message to Reddit"),
    ("/checkstatus", "Check Apache, Tor, and site reachability"),
    ("/fixsite <domain>", "Repair common site configuration issues"),
    ("/help", "Show all commands"),
]


class WebManagerError(RuntimeError):
    """Raised when a managed site operation fails."""


class CommandExecutionError(WebManagerError):
    """Raised when a system command fails."""


@dataclass
class RuntimeConfig:
    telegram_bot_token: str
    telegram_chat_id: int
    base_www_dir: Path = Path("/var/www")
    apache_sites_available_dir: Path = Path("/etc/apache2/sites-available")
    torrc_path: Path = Path("/etc/tor/torrc")
    hidden_service_root: Path = Path("/var/lib/tor")
    registry_path: Path = Path("/etc/webmanager/sites.json")
    apache_service_name: str = "apache2"
    tor_service_name: str = "tor@default"
    apache_user: str = "www-data"
    apache_group: str = "www-data"
    log_path: Path = Path("/var/log/webmanager.log")
    log_level: str = "INFO"
    mysql_admin_user: str = "root"
    mysql_admin_password: str = ""
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database_prefix: str = "wm_"
    mysql_user_prefix: str = "wm_"
    wordpress_download_url: str = WORDPRESS_URL
    command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    reddit_password: str = ""
    reddit_user_agent: str = "webmanager/1.0"

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id_raw = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if not token:
            raise WebManagerError("TELEGRAM_BOT_TOKEN is required.")
        if not chat_id_raw:
            raise WebManagerError("TELEGRAM_CHAT_ID is required.")
        try:
            chat_id = int(chat_id_raw)
        except ValueError as exc:
            raise WebManagerError("TELEGRAM_CHAT_ID must be an integer.") from exc
        return cls(
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            base_www_dir=Path(os.environ.get("WEBMANAGER_BASE_WWW_DIR", "/var/www")),
            apache_sites_available_dir=Path(
                os.environ.get("WEBMANAGER_APACHE_SITES_AVAILABLE_DIR", "/etc/apache2/sites-available")
            ),
            torrc_path=Path(os.environ.get("WEBMANAGER_TORRC_PATH", "/etc/tor/torrc")),
            hidden_service_root=Path(
                os.environ.get("WEBMANAGER_HIDDEN_SERVICE_ROOT", "/var/lib/tor")
            ),
            registry_path=Path(os.environ.get("WEBMANAGER_REGISTRY_PATH", "/etc/webmanager/sites.json")),
            apache_service_name=os.environ.get("WEBMANAGER_APACHE_SERVICE", "apache2"),
            tor_service_name=os.environ.get("WEBMANAGER_TOR_SERVICE", "tor@default"),
            apache_user=os.environ.get("WEBMANAGER_APACHE_USER", "www-data"),
            apache_group=os.environ.get("WEBMANAGER_APACHE_GROUP", "www-data"),
            log_path=Path(os.environ.get("WEBMANAGER_LOG_PATH", "/var/log/webmanager.log")),
            log_level=os.environ.get("WEBMANAGER_LOG_LEVEL", "INFO"),
            mysql_admin_user=os.environ.get("WEBMANAGER_MYSQL_ADMIN_USER", "root"),
            mysql_admin_password=os.environ.get("WEBMANAGER_MYSQL_ADMIN_PASSWORD", ""),
            mysql_host=os.environ.get("WEBMANAGER_MYSQL_HOST", "127.0.0.1"),
            mysql_port=int(os.environ.get("WEBMANAGER_MYSQL_PORT", "3306")),
            mysql_database_prefix=os.environ.get("WEBMANAGER_MYSQL_DATABASE_PREFIX", "wm_"),
            mysql_user_prefix=os.environ.get("WEBMANAGER_MYSQL_USER_PREFIX", "wm_"),
            wordpress_download_url=os.environ.get("WEBMANAGER_WORDPRESS_DOWNLOAD_URL", WORDPRESS_URL),
            command_timeout_seconds=int(
                os.environ.get("WEBMANAGER_COMMAND_TIMEOUT_SECONDS", str(DEFAULT_COMMAND_TIMEOUT))
            ),
            reddit_client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
            reddit_client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
            reddit_username=os.environ.get("REDDIT_USERNAME", ""),
            reddit_password=os.environ.get("REDDIT_PASSWORD", ""),
            reddit_user_agent=os.environ.get("REDDIT_USER_AGENT", "webmanager/1.0"),
        )


@dataclass
class SiteRecord:
    domain: str
    site_type: str
    onion_address: str
    apache_config_path: str
    sitemap_url: str
    enabled: bool
    created_at: str
    updated_at: str
    site_root: str
    document_root: str
    tor_hidden_service_dir: str
    status: str = "unknown"
    mysql_database: Optional[str] = None
    mysql_user: Optional[str] = None
    mysql_password: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SiteRecord":
        return cls(**payload)


class CommandRunner:
    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        command: list[str],
        *,
        check: bool = True,
        extra_env: Optional[dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            env=env,
        )
        if check and completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
            raise CommandExecutionError(f"Command failed ({' '.join(command)}): {stderr}")
        return completed


class RedditPublisher:
    def __init__(self, config: RuntimeConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger

    def _require_credentials(self) -> None:
        required = {
            "REDDIT_CLIENT_ID": self.config.reddit_client_id,
            "REDDIT_CLIENT_SECRET": self.config.reddit_client_secret,
            "REDDIT_USERNAME": self.config.reddit_username,
            "REDDIT_PASSWORD": self.config.reddit_password,
        }
        missing = sorted(name for name, value in required.items() if not value)
        if missing:
            raise WebManagerError(
                "Missing Reddit credentials: " + ", ".join(missing)
            )

    def _request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> dict[str, Any]:
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("User-Agent", self.config.reddit_user_agent)
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise WebManagerError(f"Reddit API error {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise WebManagerError(f"Failed to contact Reddit: {exc.reason}") from exc
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise WebManagerError("Reddit returned malformed JSON.") from exc

    def _get_access_token(self) -> str:
        self._require_credentials()
        body = urllib.parse.urlencode(
            {
                "grant_type": "password",
                "username": self.config.reddit_username,
                "password": self.config.reddit_password,
            }
        ).encode("utf-8")
        basic_auth = base64.b64encode(
            f"{self.config.reddit_client_id}:{self.config.reddit_client_secret}".encode("utf-8")
        ).decode("ascii")
        data = self._request_json(
            "https://www.reddit.com/api/v1/access_token",
            method="POST",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body=body,
        )
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise WebManagerError("Reddit did not return an access token.")
        return token

    def submit_post(self, site: SiteRecord, subreddit: str) -> str:
        validate_subreddit(subreddit)
        token = self._get_access_token()
        title = f"New hidden service: {site.domain}"
        target_url = f"http://{site.onion_address}" if site.onion_address else site.sitemap_url
        body = (
            f"I just launched {site.domain} as a Tor hidden service.\n\n"
            f"Visit: {target_url}\n"
            f"Sitemap: {site.sitemap_url}\n"
            f"Site type: {site.site_type}\n"
        )
        response = self._request_json(
            "https://oauth.reddit.com/api/submit",
            method="POST",
            headers={
                "Authorization": f"bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body=urllib.parse.urlencode(
                {
                    "api_type": "json",
                    "kind": "self",
                    "resubmit": "true",
                    "sr": subreddit,
                    "title": title,
                    "text": body,
                }
            ).encode("utf-8"),
        )
        errors = response.get("json", {}).get("errors", [])
        if errors:
            raise WebManagerError(f"Reddit rejected the post: {errors}")
        post_url = response.get("json", {}).get("data", {}).get("url")
        return post_url if isinstance(post_url, str) and post_url else f"Posted to r/{subreddit}."


class WebManager:
    def __init__(
        self,
        config: RuntimeConfig,
        *,
        runner: Optional[CommandRunner] = None,
        logger: Optional[logging.Logger] = None,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.runner = runner or CommandRunner(config.command_timeout_seconds)
        self.logger = logger or logging.getLogger("webmanager")
        self.sleep_func = sleep_func
        self.reddit = RedditPublisher(config, self.logger)

    def create_site(self, domain: str, site_type: str) -> str:
        domain = validate_domain(domain)
        site_type = validate_site_type(site_type)
        registry = self._load_registry()
        if domain in registry:
            raise WebManagerError(f"Site '{domain}' is already managed.")

        site_root = self._site_root(domain)
        document_root = self._document_root(domain)
        hidden_service_dir = self._hidden_service_dir(domain)
        apache_config_path = self._apache_config_path(domain)

        self.logger.info("Creating %s site for %s", site_type, domain)
        document_root.mkdir(parents=True, exist_ok=True)
        self._write_site_content(domain, site_type, document_root)
        self._write_text(apache_config_path, self.render_apache_config(domain, document_root))
        self._ensure_apache_modules()
        self._run_a2ensite(domain)
        self._reload_apache()
        self._ensure_tor_hidden_service(domain)
        self._reload_tor()
        onion_address = self._wait_for_onion_hostname(hidden_service_dir)
        self._write_text(
            apache_config_path,
            self.render_apache_config(domain, document_root, onion_address=onion_address),
        )
        self._reload_apache()
        self._apply_permissions(site_root)
        sitemap_url = self._regenerate_seo_assets(domain, site_type, document_root, onion_address)
        record = SiteRecord(
            domain=domain,
            site_type=site_type,
            onion_address=onion_address,
            apache_config_path=str(apache_config_path),
            sitemap_url=sitemap_url,
            enabled=True,
            created_at=utc_now(),
            updated_at=utc_now(),
            site_root=str(site_root),
            document_root=str(document_root),
            tor_hidden_service_dir=str(hidden_service_dir),
            status="online" if self._check_site_http(domain, onion_address) else "degraded",
        )
        if site_type == "wordpress":
            db_info = self._create_wordpress_database(domain)
            record.mysql_database = db_info["database"]
            record.mysql_user = db_info["user"]
            self._create_wordpress_config(document_root, db_info)
            self._apply_permissions(site_root)
            sitemap_url = self._regenerate_seo_assets(domain, site_type, document_root, onion_address)
            record.sitemap_url = sitemap_url
        registry[domain] = asdict(record)
        self._save_registry(registry)
        return (
            f"Created {site_type} site '{domain}'.\n"
            f"Onion: {onion_address}\n"
            f"Apache config: {apache_config_path}\n"
            f"Sitemap: {sitemap_url}"
        )

    def list_sites(self) -> str:
        registry = self._load_registry()
        if not registry:
            return "No managed sites found."
        lines = ["Managed sites:"]
        for domain in sorted(registry):
            site = SiteRecord.from_dict(registry[domain])
            lines.append(
                f"- {site.domain} [{site.site_type}] onion={site.onion_address or 'pending'} status={self._site_status(site)}"
            )
        return "\n".join(lines)

    def get_site_info(self, domain: str) -> str:
        site = self._get_site(domain)
        return "\n".join(
            [
                f"Domain: {site.domain}",
                f"Type: {site.site_type}",
                f"Onion: {site.onion_address or 'pending'}",
                f"Apache config: {site.apache_config_path}",
                f"Sitemap: {site.sitemap_url}",
                f"Status: {self._site_status(site)}",
                f"Enabled: {'yes' if site.enabled else 'no'}",
            ]
        )

    def enable_site(self, domain: str) -> str:
        site = self._get_site(domain)
        self._run_a2ensite(site.domain)
        self._reload_apache()
        self._update_site(site.domain, enabled=True)
        return f"Enabled site '{site.domain}' and reloaded Apache."

    def disable_site(self, domain: str) -> str:
        site = self._get_site(domain)
        self.runner.run(["a2dissite", f"{site.domain}.conf"])
        self._reload_apache()
        self._update_site(site.domain, enabled=False)
        return f"Disabled site '{site.domain}' and reloaded Apache."

    def update_seo(self, domain: str) -> str:
        site = self._get_site(domain)
        sitemap_url = self._regenerate_seo_assets(
            site.domain,
            site.site_type,
            Path(site.document_root),
            site.onion_address,
        )
        self._update_site(site.domain, sitemap_url=sitemap_url, status=self._site_status(site))
        return f"Regenerated sitemap.xml and robots.txt for '{site.domain}'.\nSitemap: {sitemap_url}"

    def post_reddit(self, domain: str, subreddit: str) -> str:
        site = self._get_site(domain)
        destination = self.reddit.submit_post(site, subreddit)
        return f"Posted promotion for '{site.domain}' to r/{subreddit}.\n{destination}"

    def check_status(self) -> str:
        apache_state = self._service_state(self.config.apache_service_name)
        tor_state = self._service_state(self.config.tor_service_name)
        lines = [f"Apache: {apache_state}", f"Tor: {tor_state}"]
        registry = self._load_registry()
        if not registry:
            lines.append("Sites: none")
            return "\n".join(lines)
        lines.append("Sites:")
        for domain in sorted(registry):
            site = SiteRecord.from_dict(registry[domain])
            lines.append(f"- {site.domain}: {self._site_status(site)}")
        return "\n".join(lines)

    def fix_site(self, domain: str) -> str:
        site = self._get_site(domain)
        document_root = Path(site.document_root)
        self._write_text(
            Path(site.apache_config_path),
            self.render_apache_config(site.domain, document_root, onion_address=site.onion_address),
        )
        self._ensure_apache_modules()
        self._ensure_tor_hidden_service(site.domain)
        self._regenerate_seo_assets(site.domain, site.site_type, document_root, site.onion_address)
        self._apply_permissions(Path(site.site_root))
        if site.enabled:
            self._run_a2ensite(site.domain)
        self._reload_apache()
        self._reload_tor()
        onion_address = site.onion_address or self._wait_for_onion_hostname(Path(site.tor_hidden_service_dir))
        status = "online" if self._check_site_http(site.domain, onion_address) else "degraded"
        self._update_site(site.domain, onion_address=onion_address, status=status)
        return f"Fixed common issues for '{site.domain}'. Current status: {status}."

    def _site_root(self, domain: str) -> Path:
        return self.config.base_www_dir / domain

    def _document_root(self, domain: str) -> Path:
        return self._site_root(domain) / "public_html"

    def _hidden_service_dir(self, domain: str) -> Path:
        return self.config.hidden_service_root / f"hidden_service_{domain}"

    def _apache_config_path(self, domain: str) -> Path:
        return self.config.apache_sites_available_dir / f"{domain}.conf"

    def _load_registry(self) -> dict[str, dict[str, Any]]:
        if not self.config.registry_path.exists():
            return {}
        raw = self.config.registry_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise WebManagerError("Registry file is malformed.")
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}

    def _save_registry(self, registry: dict[str, dict[str, Any]]) -> None:
        self.config.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_text(self.config.registry_path, json.dumps(registry, indent=2, sort_keys=True) + "\n")

    def _get_site(self, domain: str) -> SiteRecord:
        domain = validate_domain(domain)
        registry = self._load_registry()
        payload = registry.get(domain)
        if payload is None:
            raise WebManagerError(f"Site '{domain}' is not managed.")
        return SiteRecord.from_dict(payload)

    def _update_site(self, domain: str, **changes: Any) -> None:
        registry = self._load_registry()
        payload = registry.get(domain)
        if payload is None:
            raise WebManagerError(f"Site '{domain}' is not managed.")
        payload.update(changes)
        payload["updated_at"] = utc_now()
        registry[domain] = payload
        self._save_registry(registry)

    def _write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _ensure_apache_modules(self) -> None:
        self.runner.run(["a2enmod", "rewrite", "headers", "expires"])

    def _run_a2ensite(self, domain: str) -> None:
        self.runner.run(["a2ensite", f"{domain}.conf"])
        self.runner.run(["apache2ctl", "configtest"])

    def _reload_apache(self) -> None:
        self.runner.run(["systemctl", "reload", self.config.apache_service_name])

    def _reload_tor(self) -> None:
        self.runner.run(["systemctl", "reload", self.config.tor_service_name])

    def _service_state(self, service_name: str) -> str:
        result = self.runner.run(["systemctl", "is-active", service_name], check=False)
        output = (result.stdout or result.stderr).strip()
        return output or "unknown"

    def _ensure_tor_hidden_service(self, domain: str) -> None:
        hidden_service_dir = self._hidden_service_dir(domain)
        begin_marker = f"# BEGIN WEBMANAGER {domain}"
        end_marker = f"# END WEBMANAGER {domain}"
        block = "\n".join(
            [
                begin_marker,
                f"HiddenServiceDir {hidden_service_dir}/",
                "HiddenServicePort 80 127.0.0.1:80",
                end_marker,
            ]
        )
        torrc = self.config.torrc_path.read_text(encoding="utf-8") if self.config.torrc_path.exists() else ""
        if begin_marker in torrc and end_marker in torrc:
            return
        updated = (torrc.rstrip() + "\n\n" + block + "\n").lstrip("\n")
        self._write_text(self.config.torrc_path, updated)

    def _wait_for_onion_hostname(self, hidden_service_dir: Path) -> str:
        hostname_path = hidden_service_dir / "hostname"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if hostname_path.exists():
                hostname = hostname_path.read_text(encoding="utf-8").strip()
                if hostname:
                    return hostname
            self.sleep_func(1)
        raise WebManagerError(f"Timed out waiting for Tor hostname at {hostname_path}.")

    def _write_site_content(self, domain: str, site_type: str, document_root: Path) -> None:
        if site_type == "wordpress":
            self._install_wordpress(document_root)
        elif site_type == "html":
            self._write_text(document_root / "index.html", render_html_landing_page(domain))
        elif site_type == "php":
            self._write_text(document_root / "index.php", render_php_landing_page(domain))
        self._write_text(document_root / ".htaccess", build_htaccess(site_type))

    def _install_wordpress(self, document_root: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="webmanager-wordpress-") as tmp_dir:
            archive_path = Path(tmp_dir) / "wordpress.tar.gz"
            self.logger.info("Downloading WordPress from %s", self.config.wordpress_download_url)
            urllib.request.urlretrieve(self.config.wordpress_download_url, archive_path)
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(tmp_dir)
            source_root = Path(tmp_dir) / "wordpress"
            if not source_root.exists():
                raise WebManagerError("Downloaded WordPress archive was missing the wordpress directory.")
            for item in source_root.iterdir():
                target = document_root / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)

    def _create_wordpress_database(self, domain: str) -> dict[str, str]:
        slug = domain_to_slug(domain)
        database = sanitize_mysql_identifier(f"{self.config.mysql_database_prefix}{slug}")
        user = sanitize_mysql_identifier(f"{self.config.mysql_user_prefix}{slug}")
        password = generate_safe_secret(32)
        sql = "\n".join(
            [
                f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
                f"CREATE USER IF NOT EXISTS '{user}'@'localhost' IDENTIFIED BY '{password}';",
                f"ALTER USER '{user}'@'localhost' IDENTIFIED BY '{password}';",
                f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{user}'@'localhost';",
                "FLUSH PRIVILEGES;",
            ]
        )
        self.runner.run(
            [
                "mysql",
                f"--host={self.config.mysql_host}",
                f"--port={self.config.mysql_port}",
                f"--user={self.config.mysql_admin_user}",
                "--execute",
                sql,
            ],
            extra_env={"MYSQL_PWD": self.config.mysql_admin_password},
        )
        return {"database": database, "user": user, "password": password, "host": "localhost"}

    def _create_wordpress_config(self, document_root: Path, db_info: dict[str, str]) -> None:
        config_path = document_root / "wp-config.php"
        table_prefix = f"{domain_to_slug(document_root.parent.name)}_"
        self._write_text(config_path, render_wordpress_config(db_info, table_prefix))

    def _apply_permissions(self, site_root: Path) -> None:
        shutil.chown(site_root, user=self.config.apache_user, group=self.config.apache_group)
        for current_root, dirnames, filenames in os.walk(site_root):
            current_path = Path(current_root)
            shutil.chown(current_path, user=self.config.apache_user, group=self.config.apache_group)
            current_path.chmod(0o755)
            for dirname in dirnames:
                path = current_path / dirname
                shutil.chown(path, user=self.config.apache_user, group=self.config.apache_group)
                path.chmod(0o755)
            for filename in filenames:
                path = current_path / filename
                shutil.chown(path, user=self.config.apache_user, group=self.config.apache_group)
                if path.name in {"wp-config.php", ".htaccess"}:
                    path.chmod(0o640)
                else:
                    path.chmod(0o644)

    def _regenerate_seo_assets(
        self,
        domain: str,
        site_type: str,
        document_root: Path,
        onion_address: str,
    ) -> str:
        sitemap_url = build_sitemap_url(onion_address or domain)
        sitemap_content = build_sitemap_xml(document_root, site_type, onion_address or domain)
        robots_content = build_robots_txt(onion_address or domain, site_type)
        self._write_text(document_root / "sitemap.xml", sitemap_content)
        self._write_text(document_root / "robots.txt", robots_content)
        return sitemap_url

    def _check_site_http(self, domain: str, onion_address: str) -> bool:
        host_header = onion_address or domain
        connection: Optional[http.client.HTTPConnection] = None
        try:
            connection = http.client.HTTPConnection("127.0.0.1", 80, timeout=10)
            connection.request("GET", "/", headers={"Host": host_header})
            response = connection.getresponse()
            response.read()
            return 200 <= response.status < 500
        except OSError:
            return False
        finally:
            try:
                if connection is not None:
                    connection.close()
            except Exception:
                pass

    def _site_status(self, site: SiteRecord) -> str:
        apache_ok = self._service_state(self.config.apache_service_name) == "active"
        tor_ok = self._service_state(self.config.tor_service_name) == "active"
        config_ok = Path(site.apache_config_path).exists()
        onion_ok = bool(site.onion_address)
        http_ok = self._check_site_http(site.domain, site.onion_address) if site.enabled else False
        parts = [
            "enabled" if site.enabled else "disabled",
            "apache-ok" if apache_ok else "apache-down",
            "tor-ok" if tor_ok else "tor-down",
            "config-ok" if config_ok else "config-missing",
            "onion-ok" if onion_ok else "onion-missing",
        ]
        if site.enabled:
            parts.append("http-ok" if http_ok else "http-failed")
        return ", ".join(parts)

    @staticmethod
    def render_apache_config(domain: str, document_root: Path, onion_address: str = "") -> str:
        lines = [
            "<VirtualHost *:80>",
            f"    ServerName {domain}",
        ]
        if onion_address:
            lines.append(f"    ServerAlias {onion_address}")
        lines.extend(
            [
                f"    DocumentRoot {document_root}",
                "",
                f"    <Directory {document_root}>",
                "        AllowOverride All",
                "        Options -Indexes +FollowSymLinks",
                "        Require all granted",
                "    </Directory>",
                "",
                f"    ErrorLog ${'{APACHE_LOG_DIR}'}/{domain}_error.log",
                f"    CustomLog ${'{APACHE_LOG_DIR}'}/{domain}_access.log combined",
                "</VirtualHost>",
                "",
            ]
        )
        return "\n".join(lines)


def validate_domain(domain: str) -> str:
    normalized = domain.strip().lower()
    if not DOMAIN_RE.fullmatch(normalized):
        raise WebManagerError(f"Invalid domain: {domain}")
    return normalized


def validate_site_type(site_type: str) -> str:
    normalized = site_type.strip().lower()
    if normalized not in VALID_SITE_TYPES:
        raise WebManagerError("Site type must be one of: wordpress, html, php")
    return normalized


def validate_subreddit(subreddit: str) -> str:
    normalized = subreddit.strip().removeprefix("r/")
    if not SUBREDDIT_RE.fullmatch(normalized):
        raise WebManagerError(f"Invalid subreddit: {subreddit}")
    return normalized


def domain_to_slug(domain: str) -> str:
    return domain.replace("-", "_").replace(".", "_")


def sanitize_mysql_identifier(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    return sanitized[:64]


def generate_safe_secret(length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def escape_php_single_quoted_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_sitemap_url(host: str) -> str:
    return f"http://{host}/sitemap.xml"


def discover_site_urls(document_root: Path, site_type: str) -> list[str]:
    urls: set[str] = {"/"}
    for path in sorted(document_root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"robots.txt", "sitemap.xml", "wp-config.php", ".htaccess"}:
            continue
        suffix = path.suffix.lower()
        if site_type == "wordpress":
            if suffix not in {".php", ".html", ".htm"}:
                continue
        elif suffix not in {".html", ".htm", ".php"}:
            continue
        relative = path.relative_to(document_root).as_posix()
        if relative.startswith("wp-admin/") or relative.startswith("wp-includes/"):
            continue
        if relative.endswith("/index.html") or relative.endswith("/index.php"):
            urls.add("/" + str(Path(relative).parent).replace("\\", "/").strip(".").strip("/") + "/")
        elif relative in {"index.html", "index.php"}:
            urls.add("/")
        else:
            urls.add("/" + relative)
    return sorted({normalize_url_path(item) for item in urls})


def normalize_url_path(path: str) -> str:
    normalized = "/" + path.strip()
    normalized = normalized.replace("//", "/")
    if normalized != "/" and normalized.endswith("/."):
        normalized = normalized[:-2] + "/"
    return normalized


def build_sitemap_xml(document_root: Path, site_type: str, host: str) -> str:
    today = datetime.now(UTC).date().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url_path in discover_site_urls(document_root, site_type):
        priority = "1.0" if url_path == "/" else "0.8"
        lines.extend(
            [
                "  <url>",
                f"    <loc>{xml_escape(f'http://{host}{url_path}')}</loc>",
                f"    <lastmod>{today}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def build_robots_txt(host: str, site_type: str) -> str:
    lines = ["User-agent: *", "Allow: /"]
    if site_type == "wordpress":
        lines.extend(["Disallow: /wp-admin/", "Disallow: /wp-includes/"])
    lines.append(f"Sitemap: http://{host}/sitemap.xml")
    return "\n".join(lines) + "\n"


def build_htaccess(site_type: str) -> str:
    if site_type == "wordpress":
        return (
            "<IfModule mod_rewrite.c>\n"
            "RewriteEngine On\n"
            "RewriteBase /\n"
            "RewriteRule ^index\\.php$ - [L]\n"
            "RewriteCond %{REQUEST_FILENAME} !-f\n"
            "RewriteCond %{REQUEST_FILENAME} !-d\n"
            "RewriteRule . /index.php [L]\n"
            "</IfModule>\n"
        )
    return (
        "<IfModule mod_headers.c>\n"
        "Header always set X-Frame-Options \"SAMEORIGIN\"\n"
        "Header always set X-Content-Type-Options \"nosniff\"\n"
        "Header always set Referrer-Policy \"strict-origin-when-cross-origin\"\n"
        "</IfModule>\n\n"
        "<IfModule mod_expires.c>\n"
        "ExpiresActive On\n"
        "ExpiresByType text/html \"access plus 1 hour\"\n"
        "ExpiresByType application/x-httpd-php \"access plus 1 hour\"\n"
        "ExpiresByType text/css \"access plus 7 days\"\n"
        "ExpiresByType application/javascript \"access plus 7 days\"\n"
        "</IfModule>\n"
    )


def render_html_landing_page(domain: str) -> str:
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{domain}</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; display: grid; place-items: center; min-height: 100vh; margin: 0; }}
    main {{ max-width: 42rem; padding: 3rem; border-radius: 1rem; background: rgba(15, 23, 42, 0.86); box-shadow: 0 20px 45px rgba(15, 23, 42, 0.45); }}
    h1 {{ margin-top: 0; font-size: 2.5rem; }}
    p {{ line-height: 1.7; color: #cbd5e1; }}
  </style>
</head>
<body>
  <main>
    <h1>Welcome to {domain}</h1>
    <p>This site is online through Apache and available as a Tor hidden service.</p>
    <p>Use the Telegram bot to publish content, refresh SEO files, and manage uptime.</p>
  </main>
</body>
</html>
"""


def render_php_landing_page(domain: str) -> str:
    return f"""<?php
$siteName = '{domain}';
?><!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title><?php echo htmlspecialchars($siteName, ENT_QUOTES, 'UTF-8'); ?></title>
  <style>
    body {{ font-family: Arial, sans-serif; background: linear-gradient(135deg, #111827, #1d4ed8); color: #f8fafc; display: grid; place-items: center; min-height: 100vh; margin: 0; }}
    section {{ padding: 3rem; max-width: 42rem; border-radius: 1rem; background: rgba(15, 23, 42, 0.84); }}
  </style>
</head>
<body>
  <section>
    <h1><?php echo htmlspecialchars($siteName, ENT_QUOTES, 'UTF-8'); ?></h1>
    <p>This PHP landing page replaces the default phpinfo output with a production-safe welcome page.</p>
    <p>Deploy your application code into this directory and manage the site from Telegram.</p>
  </section>
</body>
</html>
"""


def render_wordpress_config(db_info: dict[str, str], table_prefix: str) -> str:
    escaped_db_name = escape_php_single_quoted_string(db_info["database"])
    escaped_db_user = escape_php_single_quoted_string(db_info["user"])
    escaped_db_password = escape_php_single_quoted_string(db_info["password"])
    escaped_db_host = escape_php_single_quoted_string(db_info["host"])
    escaped_table_prefix = escape_php_single_quoted_string(table_prefix)
    salts = "\n".join(
        f"define('{name}', '{escape_php_single_quoted_string(secrets.token_urlsafe(48))}');"
        for name in [
            "AUTH_KEY",
            "SECURE_AUTH_KEY",
            "LOGGED_IN_KEY",
            "NONCE_KEY",
            "AUTH_SALT",
            "SECURE_AUTH_SALT",
            "LOGGED_IN_SALT",
            "NONCE_SALT",
        ]
    )
    return f"""<?php
 define( 'DB_NAME', '{escaped_db_name}' );
 define( 'DB_USER', '{escaped_db_user}' );
 define( 'DB_PASSWORD', '{escaped_db_password}' );
 define( 'DB_HOST', '{escaped_db_host}' );
 define( 'DB_CHARSET', 'utf8mb4' );
 define( 'DB_COLLATE', '' );
 {salts}
 $table_prefix = '{escaped_table_prefix}';
 define( 'WP_DEBUG', false );
 if ( ! defined( 'ABSPATH' ) ) {{
     define( 'ABSPATH', __DIR__ . '/' );
 }}
 require_once ABSPATH . 'wp-settings.php';
"""


def build_help_text() -> str:
    lines = ["WebManager commands:"]
    lines.extend(f"{command} — {description}" for command, description in COMMAND_DESCRIPTIONS)
    return "\n".join(lines)


async def ensure_authorized(update: Update, config: RuntimeConfig, logger: logging.Logger) -> bool:
    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id != config.telegram_chat_id:
        logger.warning("Ignoring unauthorized chat id: %s", chat_id)
        return False
    return True


async def reply_with_result(update: Update, callback: Callable[[], str], logger: logging.Logger) -> None:
    try:
        message = await asyncio.to_thread(callback)
    except Exception as exc:
        logger.exception("Command failed")
        await update.message.reply_text(f"Error: {exc}")
        return
    await update.message.reply_text(message)


def setup_logging(config: RuntimeConfig) -> logging.Logger:
    logger = logging.getLogger("webmanager")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        config.log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(config.log_path, maxBytes=1_000_000, backupCount=3)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


def build_application(config: RuntimeConfig, manager: WebManager, logger: logging.Logger) -> Any:
    if Application is None or CommandHandler is None:
        raise WebManagerError(
            "python-telegram-bot is not installed. Install it with: pip install python-telegram-bot==22.7"
        )
    app = Application.builder().token(config.telegram_bot_token).build()

    async def guarded(update: Update, action: Callable[[], str]) -> None:
        if not await ensure_authorized(update, config, logger):
            return
        await reply_with_result(update, action, logger)

    async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await guarded(update, lambda: "Welcome to WebManager.\n\n" + build_help_text())

    async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await guarded(update, build_help_text)

    async def newsite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await ensure_authorized(update, config, logger):
            return
        args = list(context.args)
        if len(args) != 2:
            await update.message.reply_text("Usage: /newsite <domain> <wordpress|html|php>")
            return
        await reply_with_result(update, lambda: manager.create_site(args[0], args[1]), logger)

    async def listsites_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await guarded(update, manager.list_sites)

    async def siteinfo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await ensure_authorized(update, config, logger):
            return
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /siteinfo <domain>")
            return
        await reply_with_result(update, lambda: manager.get_site_info(context.args[0]), logger)

    async def enablesite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await ensure_authorized(update, config, logger):
            return
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /enablesite <domain>")
            return
        await reply_with_result(update, lambda: manager.enable_site(context.args[0]), logger)

    async def disablesite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await ensure_authorized(update, config, logger):
            return
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /disablesite <domain>")
            return
        await reply_with_result(update, lambda: manager.disable_site(context.args[0]), logger)

    async def updateseo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await ensure_authorized(update, config, logger):
            return
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /updateseo <domain>")
            return
        await reply_with_result(update, lambda: manager.update_seo(context.args[0]), logger)

    async def postreddit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await ensure_authorized(update, config, logger):
            return
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /postreddit <domain> <subreddit>")
            return
        await reply_with_result(update, lambda: manager.post_reddit(context.args[0], context.args[1]), logger)

    async def checkstatus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await guarded(update, manager.check_status)

    async def fixsite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await ensure_authorized(update, config, logger):
            return
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /fixsite <domain>")
            return
        await reply_with_result(update, lambda: manager.fix_site(context.args[0]), logger)

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("newsite", newsite_handler))
    app.add_handler(CommandHandler("listsites", listsites_handler))
    app.add_handler(CommandHandler("siteinfo", siteinfo_handler))
    app.add_handler(CommandHandler("enablesite", enablesite_handler))
    app.add_handler(CommandHandler("disablesite", disablesite_handler))
    app.add_handler(CommandHandler("updateseo", updateseo_handler))
    app.add_handler(CommandHandler("postreddit", postreddit_handler))
    app.add_handler(CommandHandler("checkstatus", checkstatus_handler))
    app.add_handler(CommandHandler("fixsite", fixsite_handler))
    return app


def main() -> int:
    try:
        config = RuntimeConfig.from_env()
        logger = setup_logging(config)
        manager = WebManager(config, logger=logger)
        application = build_application(config, manager, logger)
        logger.info("Starting WebManager bot")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Failed to start webmanager: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
