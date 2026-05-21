"""Pydantic models for F5 AI Guardrails API request/response types.

These models map to the OpenAPI schema in ``openapi.json`` for type-safe
serialization and validation of the POST /backend/v1/scans endpoint.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScanDirection(str, Enum):
    """Direction indicator for a scan: prompt (user input) or response (LLM output)."""

    PROMPT = "prompt"
    RESPONSE = "response"


class ScanRequest(BaseModel):
    """Request payload for POST /backend/v1/scans (maps to PostScansBody)."""

    model_config = ConfigDict(populate_by_name=True)

    input: str = Field(..., description="Text content to scan.")
    project: str | None = Field(default=None, description="Project ID or friendly ID.")
    verbose: bool = Field(default=False, description="Return detailed scanner results.")
    flag_only: bool = Field(default=True, alias="flagOnly", description="Flag vs block behavior.")
    disabled: list[str] = Field(default_factory=list, description="Scanners to disable by type/ID.")
    force_enabled: list[str] = Field(default_factory=list, alias="forceEnabled", description="Scanners to force-enable.")
    config_overrides: dict[str, Any] = Field(default_factory=dict, alias="configOverrides")
    external_metadata: dict[str, str] | None = Field(default=None, alias="externalMetadata")

    @field_validator("external_metadata")
    @classmethod
    def validate_metadata_size(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is not None and len(v) > 10:
            raise ValueError("external_metadata cannot have more than 10 items.")
        return v

    def to_api_payload(self) -> dict[str, Any]:
        """Serialize to the JSON structure expected by the F5 scan API."""
        payload: dict[str, Any] = {"input": self.input}
        if self.project:
            payload["project"] = self.project
        if self.verbose:
            payload["verbose"] = True
        if not self.flag_only:
            payload["flagOnly"] = False
        if self.disabled:
            payload["disabled"] = self.disabled
        if self.force_enabled:
            payload["forceEnabled"] = self.force_enabled
        if self.config_overrides:
            payload["configOverrides"] = self.config_overrides
        if self.external_metadata:
            payload["externalMetadata"] = self.external_metadata
        return payload


class ScannerResult(BaseModel):
    """Result from a single scanner within a scan (maps to Scan in scannerResults)."""

    model_config = ConfigDict(populate_by_name=True)

    scanner_id: str = Field(..., alias="scannerId")
    outcome: str = Field(..., description="passed | flagged | blocked | redacted")
    scan_direction: str = Field(..., alias="scanDirection", description="request | response")
    started_date: datetime | None = Field(default=None, alias="startedDate")
    completed_date: datetime | None = Field(default=None, alias="completedDate")
    data: dict[str, Any] | None = Field(default=None, description="Scanner-specific result data.")
    custom_config: bool = Field(default=False, alias="customConfig")


class ScanResult(BaseModel):
    """Aggregated result containing outcome and individual scanner results."""

    model_config = ConfigDict(populate_by_name=True)

    outcome: Literal["cleared", "flagged", "redacted", "blocked"]
    scanner_results: list[ScannerResult] = Field(default_factory=list, alias="scannerResults")


class ScanResponse(BaseModel):
    """Response from POST /backend/v1/scans (maps to PostScansResponse)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, description="Scan request UUID (if recording enabled).")
    result: ScanResult
    redacted_input: str = Field(default="", alias="redactedInput")
    scanners: dict[str, Any] | None = Field(default=None, description="Scanner config if verbose.")

    @property
    def is_safe(self) -> bool:
        """Return True if the scan outcome is 'cleared'."""
        return self.result.outcome == "cleared"

    @property
    def outcome(self) -> str:
        """Convenience accessor for the result outcome."""
        return self.result.outcome
