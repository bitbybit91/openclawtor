from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

from webmanager import (
    WebManager,
    build_htaccess,
    build_robots_txt,
    build_sitemap_xml,
    discover_site_urls,
    validate_domain,
)


class TestWebManagerHelpers(TestCase):
    def test_validate_domain_accepts_expected_domain(self) -> None:
        self.assertEqual(validate_domain("Example.COM"), "example.com")

    def test_validate_domain_rejects_bad_input(self) -> None:
        with self.assertRaises(Exception):
            validate_domain("bad domain")

    def test_build_robots_txt_for_wordpress_blocks_admin_paths(self) -> None:
        content = build_robots_txt("example.onion", "wordpress")
        self.assertIn("Disallow: /wp-admin/", content)
        self.assertIn("Sitemap: http://example.onion/sitemap.xml", content)

    def test_build_htaccess_for_static_sites_sets_security_headers(self) -> None:
        content = build_htaccess("html")
        self.assertIn("X-Frame-Options", content)
        self.assertIn("mod_expires.c", content)

    def test_discover_site_urls_and_sitemap_cover_expected_files(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "index.html").write_text("hi", encoding="utf-8")
            (root / "about.html").write_text("about", encoding="utf-8")
            (root / "blog").mkdir()
            (root / "blog" / "index.php").write_text("<?php", encoding="utf-8")
            (root / "robots.txt").write_text("User-agent: *", encoding="utf-8")

            urls = discover_site_urls(root, "php")
            sitemap = build_sitemap_xml(root, "php", "example.onion")

            self.assertEqual(urls, ["/", "/about.html", "/blog/"])
            self.assertIn("http://example.onion/about.html", sitemap)
            self.assertIn("<changefreq>weekly</changefreq>", sitemap)

    def test_render_apache_config_includes_server_alias_when_onion_exists(self) -> None:
        config = WebManager.render_apache_config(
            "example.com", Path("/var/www/example.com/public_html"), onion_address="abc123.onion"
        )
        self.assertIn("ServerName example.com", config)
        self.assertIn("ServerAlias abc123.onion", config)


if __name__ == "__main__":
    main()
