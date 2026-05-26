#!/usr/bin/env python3
"""Example: Agentic tool-use loop via F5 AI Guardrails inline proxy.

This example mirrors a typical OpenAI Agents SDK workflow but uses LangChain's
``create_agent`` with ``ChatF5OpenAI``. The agent autonomously decides
when to call tools (get_current_time, calculate) and all LLM traffic is routed
through the F5 AI Guardrails proxy for inline scanning + Agentic Fingerprints.

The F5 proxy:
  - Scans every LLM call (prompt, tool calls, responses) inline
  - Tracks all calls via ``x-cai-metadata-session-id`` for swimlane view
  - Blocks unsafe content before it reaches the LLM or user

Required environment variables::

    F5_GUARDRAIL_API_KEY_INLINE=your-calypsoai-token
    F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app
    F5_GUARDRAIL_PROVIDER_OPENAI=your-provider-name

Usage::

    python examples/08_agentic_tools.py
    python examples/08_agentic_tools.py "What is 2^10 and what time is it?"
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

# Load .env and add src/ to path
sys.path.insert(0, os.path.dirname(__file__))
import _env_loader  # noqa: E402, F401

from langchain_core.tools import tool
from langchain.agents import create_agent

from langchain_f5_aiguardrails import ChatF5OpenAI, F5SessionManager


# ── Tools ─────────────────────────────────────────────────────────────────────
# LangChain auto-generates JSON schemas from type hints + docstrings.

@tool
def get_current_time() -> str:
    """Returns the current UTC date and time in ISO 8601 format."""
    return json.dumps({"utc_time": datetime.now(timezone.utc).isoformat()})


@tool
def calculate(expression: str) -> str:
    """Evaluates a basic arithmetic expression and returns the numeric result.

    Args:
        expression: Arithmetic expression to evaluate, e.g. '(128 * 7) + 42'
    """
    allowed = set("0123456789+-*/.() ")
    if not expression or not all(c in allowed for c in expression):
        return json.dumps({"error": f"Unsafe or empty expression: {expression!r}"})
    try:
        result = eval(expression, {"__builtins__": {}})  # noqa: S307
        return json.dumps({"expression": expression, "result": result})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ── Agent setup ───────────────────────────────────────────────────────────────

def run_agent(question: str) -> str:
    """Run a ReAct agent with tools, routed through F5 AI Guardrails proxy."""

    # 1. Session — all agent turns appear in one CalypsoAI swimlane
    session = F5SessionManager(prefix="agentic-demo")
    print("=" * 60)
    print(f"Session  : {session.session_id}")
    print(f"Question : {question}")
    print("=" * 60)

    # 2. LLM — drop-in ChatOpenAI routed through F5 proxy
    llm = ChatF5OpenAI.from_env(
        session_manager=session,
        model="gpt-5-mini",
        temperature=0,
    )

    # 3. Create agent with tools
    agent = create_agent(
        model=llm,
        tools=[get_current_time, calculate],
    )

    # 4. Run the agentic loop
    print("\n🤖 Agent is thinking...\n")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
    )

    # 5. Extract and display the result
    messages = result["messages"]

    # Show intermediate steps (tool calls, tool results)
    for msg in messages:
        msg_type = getattr(msg, "type", msg.get("type", "unknown") if isinstance(msg, dict) else "unknown")

        if msg_type == "human":
            pass  # Already printed above
        elif msg_type == "ai":
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"  🔧 Tool call: {tc['name']}({tc['args']})")
            elif msg.content:
                print(f"  💬 Agent: {msg.content}")
        elif msg_type == "tool":
            tool_name = getattr(msg, "name", "unknown")
            print(f"  📦 {tool_name} → {msg.content}")

    # Final answer is the last AI message with content
    final = messages[-1].content if messages else "(no response)"
    print(f"\n{'=' * 60}")
    print(f"✅ Final answer: {final}")
    print(f"Session ID: {session.session_id}")
    print(f"{'=' * 60}")

    return final


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "What is the current UTC time, and what is (128 * 7) + 42?"
    )
    run_agent(question)
