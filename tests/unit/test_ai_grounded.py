"""Provider-independent source, format, context-budget and evidence checks."""

import json
from xml.etree import ElementTree as ET

import pytest

from cyberhub_manager.ai.errors import ContextBudgetError, InsufficientContextError, InvalidProviderResponseError
from cyberhub_manager.ai.grounded import GroundedJSONLLMProvider

QUOTE = "Số dư tối thiểu đủ 30 phút theo đơn giá máy."
PROMPT = f'<request><authorized_context><document ref="S1">{QUOTE}</document></authorized_context></request>'


def claim(**changes):
    return {"text": "Cần đủ số dư cho 30 phút.", "ref": "S1", "passage": "S1.P1"} | changes


class Provider(GroundedJSONLLMProvider):
    def __init__(self, result, **kwargs):
        super().__init__(None, model="test-provider", **kwargs)
        self.result = result
        self.calls = []
        self.supported = True

    def _complete(self, system, user, schema, max_tokens):
        self.calls.append((system, user, schema, max_tokens))
        if system.startswith("Verify claims"):
            count = len(json.loads(user)["evidence"])
            return json.dumps({"checks": [{"passage_meaning": "Required confirmation.",
                                          "claim_meaning": "Required confirmation.",
                                          "supported": self.supported}] * count,
                               "answers_question": True, "safe_scope": True})
        return self.result


def generate(result):
    return Provider(json.dumps(result)).generate(system_prompt="trusted rules", user_prompt=PROMPT)


def test_generation_uses_backend_resolved_source_passages_and_verifies_evidence():
    provider = Provider(json.dumps({"answerable": True, "claims": [claim()]}))
    assert provider.generate(system_prompt="trusted rules", user_prompt=PROMPT) == "Cần đủ số dư cho 30 phút. [S1]"
    assert len(provider.calls) == 2
    system, user, schema, max_tokens = provider.calls[0]
    assert system.startswith("trusted rules") and max_tokens == 768
    assert schema["required"] == ["answerable", "claims"]
    assert ET.fromstring(user).findtext("authorized_context/document/passage") == QUOTE
    evidence = json.loads(provider.calls[1][1])["evidence"]
    assert evidence == [{"claim": "Cần đủ số dư cho 30 phút.", "supporting_passage": QUOTE}]


@pytest.mark.parametrize("claims", [[], [claim()], [claim(ref="S99")], [{"text": "private unsupported content"}]])
def test_refusals_discard_all_claims_and_skip_verification(claims):
    provider = Provider(json.dumps({"answerable": False, "claims": claims}))
    with pytest.raises(InsufficientContextError):
        provider.generate(system_prompt="rules", user_prompt=PROMPT)
    assert len(provider.calls) == 1


def test_semantic_verifier_can_withhold_a_claim_with_a_real_source_passage():
    provider = Provider(json.dumps({"answerable": True, "claims": [claim()]}))
    provider.supported = False
    with pytest.raises(InsufficientContextError):
        provider.generate(system_prompt="rules", user_prompt=PROMPT)


@pytest.mark.parametrize("value", [
    {}, {"answerable": "true", "claims": []}, {"answerable": True, "claims": []},
    {"answerable": True, "claims": [claim()] * 5},
    {"answerable": True, "claims": [claim(ref="S99")]},
    {"answerable": True, "claims": [claim(passage="S1.P999")]},
    {"answerable": True, "claims": [claim(text="abc\nmore")]},
    {"answerable": True, "claims": [claim(text="hello [S1]")]},
    {"answerable": True, "claims": [claim(text=True)]},
    {"answerable": True, "claims": [claim(text="Cần số dư cho 60 phút.")]},
])
def test_malformed_claim_or_invented_passage_is_rejected(value):
    with pytest.raises(InvalidProviderResponseError):
        generate(value)


@pytest.mark.parametrize("raw", ["not json", "null", "[]", "{", ""])
def test_non_json_or_invalid_envelopes_are_rejected(raw):
    with pytest.raises(InvalidProviderResponseError):
        Provider(raw).generate(system_prompt="rules", user_prompt=PROMPT)


def test_oversized_evidence_is_rejected_without_model_call():
    provider = Provider("{}", context_window=4096)
    with pytest.raises(ContextBudgetError):
        provider.generate(system_prompt="rules", user_prompt=PROMPT.replace(QUOTE, QUOTE * 100))
    assert not provider.calls


@pytest.mark.parametrize("context_window", [True, "20480", 4095, 32769])
def test_invalid_context_window_is_rejected(context_window):
    with pytest.raises(ValueError, match="context window"):
        Provider("{}", context_window=context_window)


def test_vietnamese_claim_is_not_silently_returned_as_an_english_answer():
    provider = Provider(json.dumps({"answerable": True, "claims": [
        {"english_text": "Cần đủ số dư cho 30 phút.", "ref": "S1", "passage": "S1.P1"},
    ]}))
    with pytest.raises(InvalidProviderResponseError, match="English"):
        provider.generate(system_prompt="Answer in English", user_prompt=PROMPT.replace("<request>", '<request language="en">'))
