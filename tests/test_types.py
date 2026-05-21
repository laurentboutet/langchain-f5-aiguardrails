"""Tests for Pydantic models in langchain_f5_aiguardrails.types."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from langchain_f5_aiguardrails import (
    ScanDirection,
    ScannerResult,
    ScanRequest,
    ScanResponse,
    ScanResult,
)


# ---------------------------------------------------------------------------
# ScanRequest
# ---------------------------------------------------------------------------

class TestScanRequest:
    def test_minimal(self):
        req = ScanRequest(input="hello world")
        assert req.input == "hello world"
        assert req.project is None
        assert req.verbose is False
        assert req.flag_only is True
        assert req.disabled == []
        assert req.force_enabled == []
        assert req.config_overrides == {}
        assert req.external_metadata is None

    def test_full(self):
        req = ScanRequest(
            input="test content",
            project="my-project",
            verbose=True,
            flag_only=False,
            disabled=["scanner-a"],
            force_enabled=["scanner-b"],
            config_overrides={"scanner-b": {"threshold": 0.5}},
            external_metadata={"user": "alice", "session": "xyz"},
        )
        assert req.project == "my-project"
        assert req.verbose is True
        assert req.flag_only is False
        assert req.disabled == ["scanner-a"]
        assert req.force_enabled == ["scanner-b"]
        assert req.external_metadata == {"user": "alice", "session": "xyz"}

    def test_metadata_limit(self):
        metadata = {f"key{i}": f"val{i}" for i in range(11)}
        with pytest.raises(ValidationError, match="external_metadata"):
            ScanRequest(input="test", external_metadata=metadata)

    def test_metadata_at_limit(self):
        metadata = {f"key{i}": f"val{i}" for i in range(10)}
        req = ScanRequest(input="test", external_metadata=metadata)
        assert len(req.external_metadata) == 10

    def test_to_api_payload_minimal(self):
        req = ScanRequest(input="hello")
        payload = req.to_api_payload()
        assert payload == {"input": "hello"}
        assert "project" not in payload
        assert "verbose" not in payload

    def test_to_api_payload_full(self):
        req = ScanRequest(
            input="test",
            project="proj",
            verbose=True,
            flag_only=False,
            disabled=["a"],
            force_enabled=["b"],
            config_overrides={"x": 1},
            external_metadata={"k": "v"},
        )
        payload = req.to_api_payload()
        assert payload["input"] == "test"
        assert payload["project"] == "proj"
        assert payload["verbose"] is True
        assert payload["flagOnly"] is False
        assert payload["disabled"] == ["a"]
        assert payload["forceEnabled"] == ["b"]
        assert payload["configOverrides"] == {"x": 1}
        assert payload["externalMetadata"] == {"k": "v"}


# ---------------------------------------------------------------------------
# ScannerResult
# ---------------------------------------------------------------------------

class TestScannerResult:
    def test_parsing(self):
        data = {
            "scannerId": "scanner-pii",
            "outcome": "flagged",
            "scanDirection": "request",
            "startedDate": "2025-01-01T00:00:00Z",
            "completedDate": "2025-01-01T00:00:01Z",
            "data": {"matches": ["email"]},
            "customConfig": True,
        }
        result = ScannerResult.model_validate(data)
        assert result.scanner_id == "scanner-pii"
        assert result.outcome == "flagged"
        assert result.scan_direction == "request"
        assert result.custom_config is True
        assert result.data == {"matches": ["email"]}
        assert result.started_date is not None
        assert result.completed_date is not None

    def test_minimal(self):
        data = {
            "scannerId": "scanner-x",
            "outcome": "passed",
            "scanDirection": "response",
        }
        result = ScannerResult.model_validate(data)
        assert result.scanner_id == "scanner-x"
        assert result.data is None
        assert result.custom_config is False


# ---------------------------------------------------------------------------
# ScanResult
# ---------------------------------------------------------------------------

class TestScanResult:
    def test_cleared(self):
        data = {"outcome": "cleared", "scannerResults": []}
        result = ScanResult.model_validate(data)
        assert result.outcome == "cleared"
        assert result.scanner_results == []

    def test_with_scanner_results(self):
        data = {
            "outcome": "blocked",
            "scannerResults": [
                {"scannerId": "s1", "outcome": "blocked", "scanDirection": "request"}
            ],
        }
        result = ScanResult.model_validate(data)
        assert result.outcome == "blocked"
        assert len(result.scanner_results) == 1


# ---------------------------------------------------------------------------
# ScanResponse
# ---------------------------------------------------------------------------

class TestScanResponse:
    def test_is_safe_cleared(self, cleared_response_json):
        resp = ScanResponse.model_validate(cleared_response_json)
        assert resp.is_safe is True
        assert resp.outcome == "cleared"

    def test_is_safe_blocked(self, blocked_response_json):
        resp = ScanResponse.model_validate(blocked_response_json)
        assert resp.is_safe is False
        assert resp.outcome == "blocked"

    def test_is_safe_flagged(self, flagged_response_json):
        resp = ScanResponse.model_validate(flagged_response_json)
        assert resp.is_safe is False
        assert resp.outcome == "flagged"

    def test_redacted_input(self, redacted_response_json):
        resp = ScanResponse.model_validate(redacted_response_json)
        assert resp.outcome == "redacted"
        assert "[REDACTED]" in resp.redacted_input

    def test_id_field(self, cleared_response_json):
        resp = ScanResponse.model_validate(cleared_response_json)
        assert resp.id == "scan-001"


# ---------------------------------------------------------------------------
# ScanDirection
# ---------------------------------------------------------------------------

class TestScanDirection:
    def test_values(self):
        assert ScanDirection.PROMPT.value == "prompt"
        assert ScanDirection.RESPONSE.value == "response"

    def test_string_comparison(self):
        assert ScanDirection.PROMPT == "prompt"
        assert ScanDirection.RESPONSE == "response"
