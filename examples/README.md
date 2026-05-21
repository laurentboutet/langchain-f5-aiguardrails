# Examples Guide — langchain-f5-aiguardrails

This directory contains 6 runnable examples to help you test, validate, and understand the F5 AI Guardrails middleware for LangChain.

---

## Prerequisites

### 1. Install the package

From the project root:

```bash
# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# Install package with dev + example dependencies
pip install -e ".[dev,examples]"
```

### 2. Configure environment variables

Copy the `.env.example` file to `.env` and fill in your values:

```bash
cp .env.example .env
```

**Required variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `F5_GUARDRAIL_API_KEY` | Your F5 AI Guardrails API key | `cai_xxxxxxxxxxxx` |
| `F5_GUARDRAIL_BASE_URL` | Base URL for your F5 instance | `https://us1.calypsoai.app` |

**Optional variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `F5_GUARDRAIL_PROJECT` | *(none)* | Project ID or friendly name |
| `F5_GUARDRAIL_MODE` | `enforce` | `enforce` / `monitor` / `off` |
| `F5_GUARDRAIL_FAIL_OPEN` | `true` | Allow requests if scan API is down |
| `F5_GUARDRAIL_TIMEOUT` | `30` | HTTP timeout in seconds |

You can set them in a `.env` file (auto-loaded by examples using `python-dotenv`) or export them in your shell:

```bash
# Windows (cmd)
set F5_GUARDRAIL_API_KEY=your-api-key-here
set F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app

# Windows (PowerShell)
$env:F5_GUARDRAIL_API_KEY = "your-api-key-here"
$env:F5_GUARDRAIL_BASE_URL = "https://us1.calypsoai.app"

# macOS/Linux
export F5_GUARDRAIL_API_KEY=your-api-key-here
export F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app
```

---

## Examples Overview

| # | File | What it tests | LLM Key Needed? |
|---|------|---------------|:---:|
| 01 | `01_basic_enforce.py` | Enforce mode — blocks unsafe content | No |
| 02 | `02_monitor_mode.py` | Monitor mode — logs but never blocks | No |
| 03 | `03_custom_callback.py` | Custom violation callback with metrics & audit | No |
| 04 | `04_env_configuration.py` | Factory methods (`from_env()`) | No |
| 05 | `05_with_tools.py` | Agent + tools + guardrail integration | No* |
| 06 | `06_manual_scan_test.py` | Direct API test (no LangChain) | No |

> \*Examples 01 and 05 contain **commented-out** LangChain agent code that requires `OPENAI_API_KEY`. The default mode tests middleware hooks directly — no LLM key needed.

---

## Running the Examples

### Recommended order for first-time testing

#### Step 1 — Validate API connectivity (start here!)

```bash
python examples/06_manual_scan_test.py
```

This tests the F5 scan API directly without LangChain. It sends 5 test payloads (benign, injection, PII, toxic, metadata) and shows the outcomes. **If this works, your API key and base URL are correct.**

You can also pass arguments directly:

```bash
python examples/06_manual_scan_test.py --api-key YOUR_KEY --base-url https://us1.calypsoai.app --project my-project
```

**Expected output:**
```
🔧 Configuration:
   Base URL: https://us1.calypsoai.app
   Project:  (default)
   Timeout:  30s

============================================================
  Test 1: Benign text (should be cleared)
============================================================
  ✅ Benign text
     Outcome: cleared
     Time: 0.45s
...
```

#### Step 2 — Test enforce mode

```bash
python examples/01_basic_enforce.py
```

Tests the `before_model` hook with a safe prompt and an injection attempt. In enforce mode, unsafe content is **blocked**.

**Expected output:**
```
✅ F5GuardrailMiddleware created in ENFORCE mode
--- Testing before_model hook directly ---
✅ Safe prompt: ALLOWED (scan returned cleared)
✅ Injection prompt: BLOCKED — This request has been blocked by F5 AI Guardrails security policy.
```

#### Step 3 — Test monitor mode

```bash
python examples/02_monitor_mode.py
```

Same tests but in monitor mode. Violations are **logged** but never blocked. The `on_violation` callback prints details.

**Expected output:**
```
📋 F5GuardrailMiddleware created in MONITOR mode
--- Test 2: Unsafe prompt (should log but NOT block) ---
  📋 VIOLATION LOGGED [prompt]:
     Outcome: blocked
  Result: ALLOWED (monitor mode)
```

#### Step 4 — Test custom callbacks

```bash
python examples/03_custom_callback.py
```

Demonstrates combining metrics collection and audit logging in a single `on_violation` callback. Scans 4 different prompts and prints a metrics summary at the end.

**Expected output:**
```
🔧 Middleware with custom callback (enforce mode)

--- Safe prompt ---
  ✅ ALLOWED

--- Injection attempt ---
  📝 AUDIT LOG: {"timestamp":"...","direction":"prompt","outcome":"blocked",...}
  ❌ BLOCKED: This request has been blocked by F5 AI Guardrails security policy.

============================================================
📊 Violation Metrics Summary:
{
  "total_violations": 3,
  "by_direction": {"prompt": 3, "response": 0},
  ...
}
```

#### Step 5 — Test environment configuration

```bash
python examples/04_env_configuration.py
```

Shows all three ways to create components from environment variables:
- `F5GuardrailMiddleware.from_env()`
- `GuardrailConfig.from_env()` → `F5GuardrailClient.from_config()`
- `F5GuardrailClient.from_env()`

**Expected output:**
```
============================================================
  Method 1: F5GuardrailMiddleware.from_env()
============================================================
  ✅ Middleware created
     Mode:      enforce
     Base URL:  https://us1.calypsoai.app
     ...
✅ All factory methods working correctly.
```

#### Step 6 — Test with tools context

```bash
python examples/05_with_tools.py
```

Tests middleware in a tools context — scanning tool-related prompts and responses containing sensitive data. Includes commented-out LangChain agent code you can uncomment when ready.

---

## Using with a Real LangChain Agent

Examples 01 and 05 include commented-out code for full LangChain agent integration. To use it:

1. Install `langchain-openai`:
   ```bash
   pip install langchain-openai
   ```

2. Set your OpenAI API key:
   ```bash
   set OPENAI_API_KEY=your-openai-key
   ```

3. Uncomment the "Option A" / "Full LangChain agent" block in the example file.

4. Run the example:
   ```bash
   python examples/01_basic_enforce.py
   ```

The middleware will automatically scan prompts via `before_model` and responses via `after_model` within the agent loop.

---

## Troubleshooting

### `KeyError: 'F5_GUARDRAIL_API_KEY'`
You haven't set the API key. Set it via environment variable or `.env` file.

### `F5GuardrailAuthError: HTTP 401`
Your API key is invalid or expired. Check the key value and ensure it has permissions for the scan API.

### `F5GuardrailAuthError: HTTP 403`
Your API key is valid but lacks permissions for the target project or endpoint.

### `F5GuardrailTimeoutError`
The scan API didn't respond in time. Try increasing the timeout:
```bash
set F5_GUARDRAIL_TIMEOUT=60
```

### `ConnectionError` or network issues
Check that your `F5_GUARDRAIL_BASE_URL` is correct and reachable from your network. Common base URLs:
- US: `https://us1.calypsoai.app`
- EU: `https://eu1.calypsoai.app`

### Safe content gets blocked unexpectedly
Check your project's scanner configuration in the F5 AI Guardrails dashboard. Some scanners may be very sensitive by default.

### Unsafe content is not blocked
The scan API outcome depends on your project's scanners. Not all scanners are enabled by default. Check your project configuration in the F5 dashboard.

---

## Quick Reference

```python
# Minimal usage — test a single scan directly
from langchain_f5_aiguardrails import F5GuardrailClient, ScanRequest

client = F5GuardrailClient(api_key="your-key", base_url="https://us1.calypsoai.app")
response = client.scan(ScanRequest(input="Hello world"))
print(f"Outcome: {response.outcome}, Safe: {response.is_safe}")
client.close()
```

```python
# Middleware usage — protect a LangChain agent
from langchain_f5_aiguardrails import F5GuardrailMiddleware

middleware = F5GuardrailMiddleware.from_env()
# Pass to: create_agent(model=..., tools=..., middleware=[middleware])
```
