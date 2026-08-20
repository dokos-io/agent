from __future__ import annotations

import re
import unittest
from types import SimpleNamespace

from jinja2 import Environment, PackageLoader


def _render_bench_nginx_conf(standalone: bool) -> str:
    """Render bench/nginx.conf.jinja2 the same way Bench.generate_nginx_config() /
    Server._render_template() do, with a minimal but realistic context."""
    environment = Environment(loader=PackageLoader("agent", "templates"))
    template = environment.get_template("bench/nginx.conf.jinja2")

    sites = [SimpleNamespace(name="site1.example.com", host="site1.example.com")]
    domains = {"custom.example.com": "site1.example.com"}

    context = {
        "bench_name": "bench-0001",
        "bench_name_slug": "bench_0001",
        "domain": "example.com",
        "sites": sites,
        "domains": domains,
        "http_timeout": 120,
        "web_port": 18000,
        "socketio_port": 19000,
        "sites_directory": "/home/frappe/benches/bench-0001/sites",
        "standalone": standalone,
        "error_pages_directory": "/home/frappe/agent/error_pages",
        "nginx_directory": "/home/frappe/agent/nginx",
        "tls_protocols": "TLSv1.2 TLSv1.3",
        "code_server": {},
    }
    return template.render(**context)


class TestBenchNginxConfig(unittest.TestCase):
    """Regression test for the /protected/ location used to serve private files
    via X-Accel-Redirect.

    A regex-capture location (``location ~ ^/protected/(.*)``) preserves the raw,
    still percent-encoded text of the X-Accel-Redirect target in its captured
    group, so filenames containing characters that need URL-encoding (spaces,
    accents, parentheses, ...) 404 even though the file exists on disk with
    correct permissions. A plain prefix location with `alias` avoids this, since
    nginx decodes $uri before appending it to the alias path.
    """

    def _assert_protected_location_is_fixed(self, rendered: str):
        self.assertNotIn(
            "location ~ ^/protected/",
            rendered,
            "the /protected/ location must not be a regex-capture location; "
            "it preserves percent-encoded characters and breaks filenames "
            "with spaces/accents/etc.",
        )

        protected_blocks = re.findall(r"location /protected/ \{(.*?)\}", rendered, flags=re.S)
        self.assertGreaterEqual(len(protected_blocks), 1, "expected at least one /protected/ location block")
        for block in protected_blocks:
            self.assertIn("internal;", block)
            self.assertIn(
                "alias /home/frappe/benches/bench-0001/sites/$site_name_bench_0001/;",
                block,
            )

    def test_protected_location_standalone(self):
        rendered = _render_bench_nginx_conf(standalone=True)
        self._assert_protected_location_is_fixed(rendered)

    def test_protected_location_shared_proxy(self):
        rendered = _render_bench_nginx_conf(standalone=False)
        self._assert_protected_location_is_fixed(rendered)

    def test_public_file_try_files_unaffected(self):
        """The public /files/ try_files blocks use $uri (always decoded by nginx),
        not a regex capture group, so they're outside the scope of this bug and
        must be left untouched by the fix."""
        for standalone in (True, False):
            rendered = _render_bench_nginx_conf(standalone=standalone)
            self.assertIn("try_files /$site_name_bench_0001/public/$uri @webserver;", rendered)


if __name__ == "__main__":
    unittest.main()
