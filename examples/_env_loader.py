"""Shared .env file loader for examples.

Automatically loads the .env file from the project root into os.environ.
Works without python-dotenv installed. If python-dotenv is available, it
will be used instead.

Usage in any example:
    import _env_loader  # noqa: F401 — just importing triggers the load
"""

from __future__ import annotations

import os
import sys

# Project root is the parent of the examples/ directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Add src/ to path so examples can import the package
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))


def load_env_file() -> None:
    """Load .env file from the project root into os.environ.

    Parses KEY=VALUE lines, skipping comments and blank lines.
    Does NOT override existing environment variables.
    """
    # Try python-dotenv first
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
        return
    except ImportError:
        pass

    # Fallback: parse .env manually
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.isfile(env_path):
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


# Auto-load on import
load_env_file()

# Fix Windows console encoding for emoji output
if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
