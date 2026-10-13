from datetime import datetime

import pytest

from wattwise.models import DomainError
from wattwise.providers import BedrockProvider, DeterministicProvider

NOW = datetime.fromisoformat("2026-10-12T20:00:00+05:30")


def test_parse_deadline_and_ambiguity():
    p = DeterministicProvider()
    assert p.parse("Charge my EV before 7 AM using the cheapest available electricity.",NOW).deadline.isoformat() == "2026-10-13T07:00:00+05:30"
    assert p.parse("Charge my EV by 12 AM",NOW).deadline.hour == 0
    for text in ["charge my EV soon", "Charge my EV by 13 AM", "Charge my EV by 7 AM tomorrow and turn on heating"]:
        with pytest.raises(DomainError):
            p.parse(text,NOW)


def test_bedrock_adapter_contract_not_live_aws():
    class Stub:
        def converse(self, **kwargs):
            assert kwargs["modelId"] == "test-model"
            return {"output":{"message":{"content":[{"text":'{"deadline":"2026-10-13T07:00:00+05:30"}'}]}}}
    assert BedrockProvider(Stub(),"test-model").parse("Charge my EV before 7 AM",NOW).deadline.hour == 7


def test_bedrock_failure_does_not_fallback():
    class Stub:
        def converse(self, **kwargs):
            raise RuntimeError("unavailable")
    with pytest.raises(DomainError, match="no action"):
        BedrockProvider(Stub(),"test-model").parse("charge",NOW)
