#!/usr/bin/env python3
"""Example 04: Environment variable configuration.

Shows how to configure the middleware entirely from F5_GUARDRAIL_*
environment variables using the from_env() factory methods.

Usage:
    # Set all config via environment:
    export F5_GUARDRAIL_API_KEY=your-api-key
    export F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app
    export F5_GUARDRAIL_MODE=enforce
    export F5_GUARDRAIL_FAIL_OPEN=true
    export F5_GUARDRAIL_TIMEOUT=30
    export F5_GUARDRAIL_PROJECT=my-project  # optional

    python examples/04_env_configuration.py
"""

from __future__ import annotations

import os
import sys

# Load .env and add src/ to path (works without python-dotenv)
sys.path.insert(0, os.path.dirname(__file__))
import _env_loader  # noqa: E402, F401

from langchain_f5_aiguardrails import (
    F5GuardrailMiddleware,
    F5GuardrailClient,
    GuardrailConfig,
)


def main() -> None:
    # ---- Method 1: Middleware from environment ----
    print("=" * 60)
    print("  Method 1: F5GuardrailMiddleware.from_env()")
    print("=" * 60)

    middleware = F5GuardrailMiddleware.from_env()
    print(f"  ✅ Middleware created")
    print(f"     Mode:      {middleware._config.mode}")
    print(f"     Base URL:  {middleware._config.base_url}")
    print(f"     Fail open: {middleware._config.fail_open}")
    print(f"     Timeout:   {middleware._config.timeout}s")
    print(f"     Project:   {middleware._config.project or '(none)'}")
    middleware.close()

    # ---- Method 2: Config then Client ----
    print()
    print("=" * 60)
    print("  Method 2: GuardrailConfig.from_env() → F5GuardrailClient")
    print("=" * 60)

    config = GuardrailConfig.from_env()
    print(f"  ✅ Config loaded from environment")
    print(f"     api_key:   {'*' * (len(config.api_key) - 4) + config.api_key[-4:]}")
    print(f"     base_url:  {config.base_url}")
    print(f"     mode:      {config.mode}")

    client = F5GuardrailClient.from_config(config)
    print(f"  ✅ Client created from config")
    client.close()

    # ---- Method 3: Client directly from environment ----
    print()
    print("=" * 60)
    print("  Method 3: F5GuardrailClient.from_env()")
    print("=" * 60)

    client = F5GuardrailClient.from_env()
    print(f"  ✅ Client created directly from environment")
    client.close()

    print()
    print("✅ All factory methods working correctly.")


if __name__ == "__main__":
    main()
