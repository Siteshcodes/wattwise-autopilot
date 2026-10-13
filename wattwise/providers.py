"""Providers interpret intent only; they cannot optimize or approve actions."""
import json
import os
import re
from datetime import datetime, timedelta
from typing import Protocol

from pydantic import AwareDatetime

from .models import DomainError, Model


class Intent(Model):
    deadline: AwareDatetime


class Provider(Protocol):
    def parse(self, text: str, now: datetime) -> Intent: ...


class DeterministicProvider:
    def parse(self, text: str, now: datetime) -> Intent:
        # Deliberately narrow grammar: reject ambiguity instead of silently dropping constraints.
        match = re.fullmatch(r"\s*charge my ev (?:before|by) (\d{1,2})(?::(\d{2}))?\s*(am|pm)(?: using the cheapest available electricity)?[.!]?\s*", text, re.I)
        if not match:
            raise DomainError("UNSUPPORTED_REQUEST", "Try: Charge my EV before 7 AM using the cheapest available electricity. The demo supports this explicit EV/deadline grammar only.")
        hour, minute, period = match.groups()
        if not 1 <= int(hour) <= 12 or not 0 <= int(minute or 0) <= 59:
            raise DomainError("INVALID_DEADLINE", "Use a valid 12-hour time with AM or PM.")
        deadline = now.replace(hour=int(hour) % 12 + (12 if period.lower() == "pm" else 0), minute=int(minute or 0), second=0, microsecond=0)
        if deadline <= now:
            deadline += timedelta(days=1)
        return Intent(deadline=deadline)


class BedrockProvider:
    def __init__(self, client=None, model_id=None):
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID")
        if not self.model_id:
            raise DomainError("PROVIDER_CONFIGURATION", "Set BEDROCK_MODEL_ID to a model or inference profile you can access.")
        if client is None:
            import boto3
            client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        self.client = client

    def parse(self, text: str, now: datetime) -> Intent:
        try:
            response = self.client.converse(
                modelId=self.model_id,
                system=[{"text": f"Extract an EV charging deadline. Current simulated time: {now.isoformat()}. Resolve a time without a date to its next occurrence using this UTC offset. Return ONLY JSON with one key deadline (ISO8601 timestamp with offset). If not an unambiguous EV charging request, return {{\"error\":\"unsupported request\"}}. Do not approve or execute anything."}],
                messages=[{"role": "user", "content": [{"text": text}]}],
                inferenceConfig={"maxTokens": 160, "temperature": 0},
            )
            raw = "".join(c.get("text", "") for c in response["output"]["message"]["content"])
            intent = Intent.model_validate(json.loads(raw))
            if intent.deadline <= now:
                raise ValueError("Deadline is in the past")
            return intent
        except Exception as exc:
            raise DomainError("BEDROCK_FAILED", f"Bedrock inference or response validation failed ({type(exc).__name__}); no action was applied.") from exc


def provider() -> Provider:
    name = os.getenv("WATTWISE_PROVIDER", "deterministic")
    if name == "deterministic":
        return DeterministicProvider()
    if name == "bedrock":
        return BedrockProvider()
    raise DomainError("PROVIDER_CONFIGURATION", f"Unknown provider: {name}")
