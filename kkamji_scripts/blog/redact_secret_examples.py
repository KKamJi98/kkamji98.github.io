#!/usr/bin/env python3
"""Redact secret-like examples in blog posts.

This replaces credentials, tokens, hashes, and secret output examples with
explicit placeholders so posts remain educational without publishing secret-like
values that trip gitleaks.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POSTS = ROOT / "_posts"

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # JWT-shaped values.
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "<REDACTED_JWT>"),
    # AWS access key shaped values.
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<AWS_ACCESS_KEY_ID_EXAMPLE>"),
    # kubeadm discovery CA hashes.
    (re.compile(r"sha256:[a-f0-9]{32,}"), "sha256:<DISCOVERY_CA_CERT_HASH>"),
    # Generic long hex values in obvious token/password/cache contexts.
    (re.compile(r"(?i)(cacheKey[\"']?\s*[:=]\s*[\"']?)[A-Fa-f0-9]{16,}([\"']?)"), r"\1<REDACTED_CACHE_KEY>\2"),
    (re.compile(r"(?i)(token[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9._/-]{16,}([\"']?)"), r"\1<REDACTED_TOKEN>\2"),
    (re.compile(r"(?i)(bearerToken[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9._/-]{16,}([\"']?)"), r"\1<REDACTED_BEARER_TOKEN>\2"),
    (re.compile(r"(?i)(SECRET_KEY\s*=\s*)[A-Za-z0-9._/-]{8,}"), r"\1<REDACTED_SECRET_KEY>"),
    (re.compile(r"(?i)(TOKEN=)[A-Za-z0-9._/-]{16,}"), r"\1<REDACTED_TOKEN>"),
    # Argo CD secret JSON output examples.
    (re.compile(r'("(?:accounts\.alice\.password|accounts\.alice\.passwordMtime|admin\.password|admin\.passwordMtime|server\.secretkey)"\s*:\s*")[^"]+(")'), r"\1<REDACTED_SECRET_DATA>\2"),
    # Vault view-secret output examples.
    (re.compile(r"(_raw='\{\"data\":\{\"password\":\")[^\"]+(\",\"username\":\")[^\"]+(\"\})"), r"\1<REDACTED_PASSWORD>\2<REDACTED_USERNAME>\3"),
    (re.compile(r"(password=')[^']+(')"), r"\1<REDACTED_PASSWORD>\2"),
    (re.compile(r"(postgres-password=')[^']+(')"), r"\1<REDACTED_PASSWORD>\2"),
    (re.compile(r"(\"password\"\s*:\s*\")[^\"]+(\")"), r"\1<REDACTED_PASSWORD>\2"),
    (re.compile(r"(\"username\"\s*:\s*\")[^\"]+(\")"), r"\1<REDACTED_USERNAME>\2"),
    # Kubernetes secret manifest sample values.
    (re.compile(r"(?i)(secret:\s*)[A-Za-z0-9+/=]{12,}"), r"\1<BASE64_ENCRYPTION_SECRET>"),
    (re.compile(r"(?i)(test_secret2:\s*)[A-Za-z0-9+/=]{12,}"), r"\1<BASE64_SECRET_VALUE>"),
]


def main() -> None:
    changed: list[str] = []
    for path in sorted(POSTS.glob("**/*.md")):
        text = path.read_text(encoding="utf-8")
        new_text = text
        for pattern, replacement in PATTERNS:
            new_text = pattern.sub(replacement, new_text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(path.relative_to(ROOT).as_posix())
    print(f"changed={len(changed)}")
    for rel in changed:
        print(rel)


if __name__ == "__main__":
    main()
