#!/usr/bin/env python3
"""Example: F5 AI Guardrails inline proxy with OpenAI via LangChain.

This example shows how to use ``ChatF5OpenAI`` to route all LLM traffic
through the F5 AI Guardrails proxy with session tracking enabled.

The F5 proxy:
  - Scans prompts and responses inline (no separate scan API calls)
  - Forwards traffic to the real OpenAI/compatible LLM
  - Tracks all calls via the ``x-cai-metadata-session-id`` header
  - Builds Agentic Fingerprints for multi-agent workflow visibility

Required environment variables::

    F5_GUARDRAIL_API_KEY_INLINE=your-calypsoai-token
    F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app
    F5_GUARDRAIL_PROVIDER_OPENAI=your-provider-name

Usage::

    python examples/07_inline_openai.py
"""
from __future__ import annotations

import os
import sys

# Load .env and add src/ to path (works without python-dotenv)
sys.path.insert(0, os.path.dirname(__file__))
import _env_loader  # noqa: E402, F401

from langchain_f5_aiguardrails import ChatF5OpenAI, F5SessionManager


def main() -> None:
    # --- 1. Create a session for the workflow ---
    # All agents sharing this session appear in one CalypsoAI swimlane.
    session = F5SessionManager(prefix="example-workflow")
    print(f"Session ID: {session.session_id}")

    # --- 2. Create the LLM routed through F5 proxy ---
    # This reads F5_GUARDRAIL_* env vars automatically.
    llm = ChatF5OpenAI.from_env(
        session_manager=session,
        model="gpt-5-mini",
        temperature=0.3,
    )

    # --- 3. Use it like any ChatOpenAI ---
    print("\n--- Single invoke ---")
    response = llm.invoke("What is the capital of France? Reply in one sentence.")
    print(f"Response: {response.content}")

    # --- 4. Multi-turn conversation ---
    print("\n--- Multi-turn ---")
    from langchain_core.messages import HumanMessage, AIMessage

    messages = [
        HumanMessage(content="My name is Laurent."),
    ]
    response = llm.invoke(messages)
    print(f"AI: {response.content}")

    messages.append(AIMessage(content=response.content))
    messages.append(HumanMessage(content="What's my name?"))
    response = llm.invoke(messages)
    print(f"AI: {response.content}")

    print(f"\nAll calls used session: {session.session_id}")
    print("Check CalypsoAI dashboard for the unified agent fingerprint view.")


if __name__ == "__main__":
    main()
