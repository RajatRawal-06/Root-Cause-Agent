from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RemediationRequest:
    incident_id: str
    recommendation_id: str
    idempotency_key: str


class RequestValidationError(ValueError):
    pass


def parse_json_body(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise RequestValidationError("request body must be valid JSON") from exc
    if not isinstance(value, dict):
        raise RequestValidationError("request body must be a JSON object")
    return value


def _required_string(body: dict[str, Any], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str):
        raise RequestValidationError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise RequestValidationError(f"{field} is required")
    return value


def parse_remediation_request(body: dict[str, Any]) -> RemediationRequest:
    incident_id = _required_string(body, "incident_id")
    recommendation_id = _required_string(body, "recommendation_id")
    idempotency_key = _required_string(body, "idempotency_key")
    if len(idempotency_key) > 128:
        raise RequestValidationError("idempotency_key must be 128 characters or fewer")
    return RemediationRequest(incident_id, recommendation_id, idempotency_key)
