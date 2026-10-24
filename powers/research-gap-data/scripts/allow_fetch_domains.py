#!/usr/bin/env python3
"""PreToolUse guard for the `fetch` MCP server.

Reads the hook JSON from stdin, extracts the fetch `url` argument, and blocks
(exit 2) any request whose host is not one of the health-safety allowed sources:
clinicaltrials.gov and data.cdc.gov (cdc.gov). Allowed requests exit 0.

Per the Research Gap Index health-safety rules: network access is limited to
clinicaltrials.gov and data.cdc.gov. mcp-server-fetch has no built-in allowlist,
so this hook enforces it. The matched URL host is echoed on block, never any
page content. This is a copy of .kiro/hooks/allow_fetch_domains.py so the power
is self-contained; keep the two in sync.
"""
from __future__ import annotations

import json
import sys
from urllib.parse import urlparse

# Allowed registrable domains. A host matches if it equals one of these or is a
# subdomain of one (e.g. www.cdc.gov, data.cdc.gov match "cdc.gov").
ALLOWED_DOMAINS = ("clinicaltrials.gov", "cdc.gov")


def _find_url(obj: object) -> str | None:
    """Depth-first search for a string value under a key named 'url'."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "url" and isinstance(value, str) and value.strip():
                return value.strip()
        for value in obj.values():
            found = _find_url(value)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_url(item)
            if found is not None:
                return found
    return None


def _host_allowed(host: str) -> bool:
    host = host.lower().strip().rstrip(".")
    if host.startswith("[") or host.replace(".", "").isdigit():
        return False  # reject raw IPs / IPv6 literals
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        # Unparseable payload: fail closed for a fetch guard.
        print("fetch blocked: could not parse hook payload", file=sys.stderr)
        return 2

    url = _find_url(payload)
    if url is None:
        # No URL present (not a fetch call we recognize); do not block.
        return 0

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        print("fetch blocked: only http(s) URLs are allowed", file=sys.stderr)
        return 2

    host = parsed.hostname or ""
    if not _host_allowed(host):
        print(
            "fetch blocked: host %r is not an allowed source. "
            "Allowed: clinicaltrials.gov, data.cdc.gov (cdc.gov)." % host,
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
