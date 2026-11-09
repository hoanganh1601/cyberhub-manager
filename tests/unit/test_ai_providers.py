"""Provider boundaries and deterministic fakes, with networking prohibited."""

from dataclasses import FrozenInstanceError
import math
import socket

import pytest

from cyberhub_manager.ai.chunking import MarkdownChunker
from cyberhub_manager.ai.documents import KnowledgeDocumentLoader
from cyberhub_manager.ai.errors import (
    InvalidProviderResponseError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from cyberhub_manager.ai.fakes import FakeEmbeddingProvider, FakeLLMProvider
from cyberhub_manager.ai.providers import (
    EmbeddingProvider,
    LLMProvider,
    validate_embedding,
    validate_embedding_batch,
    validate_generation,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("provider unit tests must never use a network")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.delenv("CYBERHUB_AI_API_KEY", raising=False)


def test_fake_providers_implement_public_interfaces():
    assert isinstance(FakeEmbeddingProvider(), EmbeddingProvider)
    assert isinstance(FakeLLMProvider(), LLMProvider)
    assert not isinstance(FakeLLMProvider(), EmbeddingProvider)


def test_custom_adapters_need_no_inheritance_or_sdk():
    class LocalEmbedding:
        def embed_documents(self, texts):
            return [[1.0, 0.0] for _ in texts]

        def embed_query(self, text):
            return [1.0, 0.0]

    class LocalLLM:
        def generate(self, *, system_prompt, user_prompt):
            return "Local response."

    assert isinstance(LocalEmbedding(), EmbeddingProvider)
    assert isinstance(LocalLLM(), LLMProvider)


def test_fake_embedding_default_is_constant_not_semantic():
    provider = FakeEmbeddingProvider(dimensions=3)
    assert provider.embed_documents(["Tiền bù", "Chủ đề khác"]) == [[1.0, 0.0, 0.0]] * 2
    assert provider.embed_query("Câu hỏi bất kỳ") == [1.0, 0.0, 0.0]
    assert provider.document_calls == [("Tiền bù", "Chủ đề khác")]
    assert provider.query_calls == ["Câu hỏi bất kỳ"]


def test_explicit_vectors_keep_input_order_duplicates_and_query_space():
    provider = FakeEmbeddingProvider(vectors={"A": [0.0, 1.0], "B": [1.0, 0.0]})
    batch = provider.embed_documents(["B", "A", "B"])
    assert batch == [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
    assert provider.embed_query("A") == batch[1]
    assert validate_embedding_batch(batch, expected_count=3, expected_dimensions=2) == batch


def test_fake_embedding_copies_configuration_results_and_call_inputs():
    vectors = {"A": [1.0, 2.0]}
    texts = ["A"]
    provider = FakeEmbeddingProvider(vectors=vectors)
    result = provider.embed_documents(texts)
    vectors["A"][0] = 999.0
    texts[0] = "changed"
    result[0][0] = -999.0
    assert provider.embed_query("A") == [1.0, 2.0]
    assert provider.document_calls == [("A",)]


@pytest.mark.parametrize("vectors", [{}, {"known": [1.0, 0.0]}])
def test_fake_unknown_text_fails_with_safe_error(vectors):
    provider = FakeEmbeddingProvider(vectors=vectors)
    with pytest.raises(ProviderUnavailableError) as error:
        provider.embed_query("private query content")
    assert "private query content" not in str(error.value)


def test_empty_embedding_batch_needs_no_model_and_returns_no_vectors():
    provider = FakeEmbeddingProvider(error=ProviderUnavailableError("Offline"))
    assert provider.embed_documents([]) == []
    assert validate_embedding_batch([], expected_count=0) == []


@pytest.mark.parametrize("method", ["embed_documents", "embed_query"])
@pytest.mark.parametrize("error", [
    ProviderUnavailableError("Offline"), ProviderTimeoutError("Timed out"),
])
def test_fake_embedding_simulates_failure_once_without_retry(method, error):
    provider = FakeEmbeddingProvider(error=error)
    with pytest.raises(type(error)):
        getattr(provider, method)(["A"] if method == "embed_documents" else "A")
    assert len(provider.document_calls) + len(provider.query_calls) == 1


@pytest.mark.parametrize("text", ["", "  ", None, 123])
def test_fake_embedding_rejects_invalid_input_before_work(text):
    provider = FakeEmbeddingProvider()
    with pytest.raises(ValueError):
        provider.embed_query(text)
    with pytest.raises(ValueError):
        provider.embed_documents(["valid", text])
    assert provider.document_calls == []
    assert provider.query_calls == []


@pytest.mark.parametrize("config", [
    {"dimensions": 0}, {"dimensions": True}, {"dimensions": 1.5},
    {"vectors": []}, {"vectors": {"": [1.0, 0.0]}},
    {"error": RuntimeError("wrong failure type")},
])
def test_fake_embedding_rejects_invalid_configuration(config):
    with pytest.raises(ValueError):
        FakeEmbeddingProvider(**config)


def test_fake_embedding_rejects_wrong_configured_dimension():
    with pytest.raises(InvalidProviderResponseError):
        FakeEmbeddingProvider(dimensions=2, vectors={"A": [1.0]})


def test_fake_embedding_rejects_a_string_instead_of_batch():
    with pytest.raises(ValueError):
        FakeEmbeddingProvider().embed_documents("A")


@pytest.mark.parametrize("vector", [
    None, "[1, 2]", (1.0, 2.0), [], [0.0, 0.0], [True, 1],
    ["secret payload", 1], [None, 1], [math.nan, 1], [math.inf, 1],
    [-math.inf, 1], [10 ** 400, 1],
])
def test_invalid_embedding_is_rejected_without_echoing_payload(vector):
    with pytest.raises(InvalidProviderResponseError) as error:
        validate_embedding(vector)
    assert "secret payload" not in str(error.value)


def test_embedding_validation_copies_values_without_normalizing_or_changing_order():
    source = [2, -3.0, 0]
    result = validate_embedding(source, expected_dimensions=3)
    assert result == [2.0, -3.0, 0.0]
    result[0] = 999
    assert source == [2, -3.0, 0]


@pytest.mark.parametrize("vectors, count", [
    (None, 1), ([[1.0, 0.0]], 2), ([[1.0, 0.0], [0.0, 1.0]], 1),
    ([[1.0], [1.0, 0.0]], 2), ([[1.0], []], 2), ([[1.0], [0.0]], 2),
])
def test_batch_validation_rejects_missing_extra_ragged_or_invalid_vectors(vectors, count):
    with pytest.raises(InvalidProviderResponseError):
        validate_embedding_batch(vectors, expected_count=count)


def test_batch_validation_checks_index_dimension():
    with pytest.raises(InvalidProviderResponseError, match="dimensions"):
        validate_embedding_batch([[1.0, 0.0]], expected_count=1, expected_dimensions=3)


@pytest.mark.parametrize("dimensions", [0, -1, True, "2"])
def test_invalid_expected_dimension_is_a_caller_configuration_error(dimensions):
    with pytest.raises(ValueError):
        validate_embedding([1.0], expected_dimensions=dimensions)


@pytest.mark.parametrize("count", [-1, True, "2"])
def test_invalid_expected_batch_count_is_a_caller_configuration_error(count):
    with pytest.raises(ValueError):
        validate_embedding_batch([], expected_count=count)


def test_fake_llm_keeps_system_and_user_prompts_separate_and_preserves_text():
    provider = FakeLLMProvider(response="  Trả lời thử nghiệm.\n")
    result = provider.generate(system_prompt="Quy tắc hệ thống", user_prompt="Câu hỏi")
    assert result == "  Trả lời thử nghiệm.\n"
    assert provider.calls[0].system_prompt == "Quy tắc hệ thống"
    assert provider.calls[0].user_prompt == "Câu hỏi"
    with pytest.raises(FrozenInstanceError):
        provider.calls[0].system_prompt = "changed"


@pytest.mark.parametrize("error", [
    ProviderUnavailableError("Offline"), ProviderTimeoutError("Timed out"),
    InvalidProviderResponseError("Invalid response"),
])
def test_fake_llm_simulates_provider_error_without_retry(error):
    provider = FakeLLMProvider(error=error)
    with pytest.raises(type(error)):
        provider.generate(system_prompt="Rules", user_prompt="Question")
    assert len(provider.calls) == 1
    assert isinstance(error, ProviderError)


@pytest.mark.parametrize("response", [None, "", " \n", {}, 42])
def test_invalid_generation_is_rejected(response):
    with pytest.raises(InvalidProviderResponseError):
        validate_generation(response)


@pytest.mark.parametrize("field", ["system_prompt", "user_prompt"])
def test_fake_llm_rejects_blank_prompt_before_work(field):
    provider = FakeLLMProvider()
    prompts = {"system_prompt": "Rules", "user_prompt": "Question", field: " "}
    with pytest.raises(ValueError):
        provider.generate(**prompts)
    assert provider.calls == []


def test_fake_llm_rejects_wrong_failure_type():
    with pytest.raises(ValueError):
        FakeLLMProvider(error=RuntimeError("wrong failure type"))


def test_fake_instances_do_not_share_prompt_or_embedding_histories():
    first, second = FakeLLMProvider(), FakeLLMProvider()
    first.generate(system_prompt="Rules", user_prompt="Question")
    assert second.calls == []
    embedding_a, embedding_b = FakeEmbeddingProvider(), FakeEmbeddingProvider()
    embedding_a.embed_query("A")
    assert embedding_b.query_calls == []


def test_real_corpus_can_pass_to_fake_embedding_without_network_or_keys():
    chunker = MarkdownChunker()
    chunks = [
        chunk for document in KnowledgeDocumentLoader().load()
        for chunk in chunker.split(document)
    ]
    provider = FakeEmbeddingProvider(dimensions=4)
    batch = provider.embed_documents([chunk.content for chunk in chunks])
    validated = validate_embedding_batch(batch, expected_count=len(chunks), expected_dimensions=4)
    assert len(validated) == len(chunks)
    assert validated[0] == provider.embed_query("Cách mở phiên?")
