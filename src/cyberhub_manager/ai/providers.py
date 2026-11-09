"""Small synchronous interfaces shared by local, cloud and test adapters.

Importing this module does not initialize an SDK, load a model, read credentials
or call a network. A concrete adapter owns credentials, model settings, bounded
timeouts and output limits; the RAG service must not depend on its vendor SDK.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from .errors import InvalidProviderResponseError


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Use the same model/dimensions for indexing and query embeddings.

    Return one finite, non-zero vector per input, in input order. All vectors
    must have a stable positive dimension. An empty batch returns an empty list.
    A different model/index configuration requires rebuilding the index.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Return non-blank generated text or raise a typed ProviderError.

    Keep system and user prompts separate in the concrete model API. Generation
    does not establish authorization, factual grounding or valid citations.
    """

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        ...


@runtime_checkable
class FormattedLLMProvider(LLMProvider, Protocol):
    """Optional transport-format instructions, converted back to cited text.

    A structured provider must not receive conflicting plain-text formatting
    instructions. Authorization and evidence policies remain in the core prompt.
    """

    def format_instructions(self, language: str) -> str:
        ...


def validate_embedding(
    vector: object,
    *,
    expected_dimensions: int | None = None,
) -> list[float]:
    """Validate external output before cosine search; return an owned copy.

    Adapters must convert SDK-specific arrays/numbers to built-in lists/numbers.
    Failure messages intentionally omit the original input/output payload.
    """
    _positive_dimensions(expected_dimensions)
    if not isinstance(vector, list) or not vector:
        raise InvalidProviderResponseError("embedding must be a non-empty list")
    if expected_dimensions is not None and len(vector) != expected_dimensions:
        raise InvalidProviderResponseError("embedding dimensions do not match the index")
    result = []
    for value in vector:
        if type(value) not in (int, float):
            raise InvalidProviderResponseError("embedding coordinates must be finite numbers")
        try:
            coordinate = float(value)
        except OverflowError as exc:
            raise InvalidProviderResponseError("embedding coordinate is out of range") from exc
        if not math.isfinite(coordinate):
            raise InvalidProviderResponseError("embedding coordinates must be finite numbers")
        result.append(coordinate)
    if not any(value != 0.0 for value in result):
        raise InvalidProviderResponseError("embedding must have a non-zero magnitude")
    return result


def validate_embedding_batch(
    vectors: object,
    *,
    expected_count: int,
    expected_dimensions: int | None = None,
) -> list[list[float]]:
    """Reject missing, extra or ragged vectors without returning a partial batch."""
    if type(expected_count) is not int or expected_count < 0:
        raise ValueError("expected_count must be a non-negative integer")
    _positive_dimensions(expected_dimensions)
    if not isinstance(vectors, list) or len(vectors) != expected_count:
        raise InvalidProviderResponseError("embedding count does not match the input batch")
    result = []
    dimensions = expected_dimensions
    for vector in vectors:
        validated = validate_embedding(vector, expected_dimensions=dimensions)
        dimensions = len(validated)
        result.append(validated)
    return result


def validate_generation(response: object) -> str:
    """Check the text envelope only, never claim that its contents are grounded."""
    if not isinstance(response, str) or not response.strip():
        raise InvalidProviderResponseError("generation must be non-blank text")
    return response


def _positive_dimensions(value: int | None) -> None:
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError("expected_dimensions must be a positive integer or None")
