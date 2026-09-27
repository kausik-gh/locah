"""Public URLs of a business's website, for links sent to customers.

Mirrors `businessSiteUrl` in packages/config: `https://{slug}.{domain}` under a
real platform domain, otherwise the path form `{web}/{slug}` the web app also
serves (local and preview stacks).
"""

from __future__ import annotations

import os


def business_site_url(slug: str, path: str = "") -> str:
    suffix = path if not path or path.startswith("/") else f"/{path}"
    domain = (os.getenv("PLATFORM_DOMAIN") or os.getenv("NEXT_PUBLIC_PLATFORM_DOMAIN") or "").strip().lower()
    if domain and "." in domain and not domain.replace(".", "").isdigit():
        return f"https://{slug}.{domain}{suffix}"
    web = (os.getenv("PUBLIC_WEB_URL") or os.getenv("NEXT_PUBLIC_WEB_URL") or "http://localhost:3100").rstrip("/")
    return f"{web}/{slug}{suffix}"
