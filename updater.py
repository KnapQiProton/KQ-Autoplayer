"""
GitHub Release Update Checker for KQ Autoplayer.

Checks the public GitHub API for the latest release tag without requiring authentication,
compares semantic version tuples, and returns update details.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import urllib.request
from typing import Optional, Tuple

logger = logging.getLogger('KQAutoplayer.Updater')
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%H:%M:%S')
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

GITHUB_API_LATEST_RELEASE = "https://api.github.com/repos/KnapQiProton/KQ-Autoplayer/releases/latest"


def parse_version(version_str: str) -> Tuple[int, ...]:
    """
    Parse a version string (e.g. 'v1.0.1', '1.0.0') into an integer tuple like (1, 0, 1).
    """
    if not version_str:
        return (0,)
    clean = version_str.strip().lstrip('vV')
    parts = re.findall(r'\d+', clean)
    return tuple(map(int, parts)) if parts else (0,)


def is_update_available(current: str, latest: str) -> bool:
    """
    Compare semantic version tuples. Return True if latest > current.
    """
    try:
        return parse_version(latest) > parse_version(current)
    except Exception as exc:
        logger.debug("Error comparing versions (%s vs %s): %s", current, latest, exc)
        return False


def get_latest_github_release() -> Optional[dict]:
    """
    Fetch the latest release information from GitHub API.
    Returns a dict containing 'version', 'url', and 'published_at', or None on error.
    """
    req = urllib.request.Request(
        GITHUB_API_LATEST_RELEASE,
        headers={
            "User-Agent": "KQ-Autoplayer-Desktop",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                tag_name = data.get("tag_name", "").strip()
                html_url = data.get("html_url", "").strip()
                published_at = data.get("published_at", "").strip()
                logger.info("Retrieved latest GitHub release: %s (%s)", tag_name, html_url)
                return {
                    "version": tag_name,
                    "url": html_url,
                    "published_at": published_at,
                }
    except Exception as exc:
        logger.warning("Failed to fetch latest GitHub release: %s", exc)
        return None
    return None
