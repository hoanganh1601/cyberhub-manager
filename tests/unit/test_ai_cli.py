"""API evaluator configuration, quota-conscious limits and honest report labels."""

import json

import pytest

from cyberhub_manager.ai.fakes import FakeEmbeddingProvider, FakeLLMProvider
from cyberhub_manager.ai.models import KnowledgeDocument
from scripts import evaluate_rag_gemini


def test_evaluator_missing_key_does_not_initialize_provider(monkeypatch, capsys):
    monkeypatch.setattr(evaluate_rag_gemini, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("provider cannot start without a key")
    monkeypatch.setattr(evaluate_rag_gemini, "GeminiTransport", forbidden)
    with pytest.raises(SystemExit) as error:
        evaluate_rag_gemini.main([])
    assert error.value.code == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


@pytest.mark.parametrize("args", [["--limit", "0"], ["--threshold", "0"], ["--threshold", "1.1"]])
def test_evaluator_rejects_invalid_limits_before_network(monkeypatch, args):
    monkeypatch.setattr(evaluate_rag_gemini, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid settings cannot trigger API calls")
    monkeypatch.setattr(evaluate_rag_gemini, "GeminiTransport", forbidden)
    with pytest.raises(SystemExit) as error:
        evaluate_rag_gemini.main(args)
    assert error.value.code == 2


@pytest.mark.parametrize("retrieve_only", [False, True])
def test_api_evaluation_limits_cases_and_keeps_expected_labels_out_of_prompts(tmp_path, monkeypatch, retrieve_only):
    monkeypatch.setattr(evaluate_rag_gemini, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-private-key")
    monkeypatch.setattr(evaluate_rag_gemini, "GeminiTransport", lambda *args, **kwargs: object())
    embedding = FakeEmbeddingProvider()
    embedding.model = "test-embedding"
    monkeypatch.setattr(evaluate_rag_gemini, "GeminiEmbeddingProvider", lambda *args, **kwargs: embedding)
    llm = FakeLLMProvider(response="Số dư cần đủ 30 phút. [S1]")
    monkeypatch.setattr(evaluate_rag_gemini, "GeminiLLMProvider", lambda *args, **kwargs: llm)
    class Loader:
        def load(self):
            return [KnowledgeDocument("public", "Public", "Số dư cần đủ 30 phút.", "shared/public.md",
                                      ("CUSTOMER",), "APPROVED", 1)]
    monkeypatch.setattr(evaluate_rag_gemini, "KnowledgeDocumentLoader", lambda *args, **kwargs: Loader())
    cases = tmp_path / "cases.json"
    case = {"case_id": "one", "question": "Số dư cần bao nhiêu?", "role": "CUSTOMER", "language": "vi",
            "expected_source": "shared/public.md", "expected_keywords": ["EXPECTED_LABEL_MUST_NOT_REACH_PROVIDER"]}
    cases.write_text(json.dumps([case, case | {"case_id": "two"}]), encoding="utf-8")
    output = tmp_path / "new-results" / "report.json"
    args = ["--questions", str(cases), "--output", str(output), "--limit", "1"]
    if retrieve_only:
        args.append("--retrieve-only")
    evaluate_rag_gemini.main(args)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["mode"] == "gemini-api-real-model"
    assert report["complete"] is True and report["expected_case_count"] == len(report["cases"]) == 1
    assert report["cases"][0]["service_result"] == (None if retrieve_only else "ANSWERED")
    assert "test-private-key" not in output.read_text(encoding="utf-8")
    assert len(llm.calls) == (0 if retrieve_only else 1)
    for call in llm.calls:
        assert "EXPECTED_LABEL_MUST_NOT_REACH_PROVIDER" not in call.user_prompt
