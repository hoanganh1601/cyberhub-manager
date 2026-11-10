"""Opt-in Gemini REST adapters; credentials and authorized context stay server-side."""

import json
import re
import socket
from threading import RLock
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .errors import (
    InvalidProviderResponseError, ProviderAuthenticationError, ProviderRateLimitError,
    ProviderTimeoutError, ProviderUnavailableError,
)
from .grounded import GroundedJSONLLMProvider
from .providers import validate_embedding_batch

DEFAULT_LLM_MODEL = "gemini-3.1-flash-lite"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models/"


def _model_name(model):
    if not isinstance(model, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}", model):
        raise ValueError("use an explicit Gemini model ID without a URL or models/ prefix")
    return model


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GeminiTransport:
    def __init__(self, api_key, *, timeout=30):
        # Google issues both legacy AIza... keys and newer AQ.... keys. Keep the
        # value header-safe while accepting the dot used by the newer format.
        if not isinstance(api_key, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,200}", api_key.strip()):
            raise ValueError("set GEMINI_API_KEY in the backend environment or .env")
        if type(timeout) not in (int, float) or not 0 < timeout <= 120:
            raise ValueError("Gemini timeout must be from 0 to 120 seconds")
        self._api_key = api_key.strip()
        self.timeout = float(timeout)
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def post(self, model, method, data):
        model = _model_name(model)
        if method not in {"generateContent", "batchEmbedContents", "embedContent"}:
            raise ValueError("unsupported Gemini method")
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if len(payload) > 512_000:
            raise InvalidProviderResponseError("provider input exceeds its transport budget")
        request = Request(_API_ROOT + model + ":" + method, data=payload, method="POST", headers={
            "Content-Type": "application/json", "x-goog-api-key": self._api_key,
        })
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise InvalidProviderResponseError("provider response exceeds its transport budget")
                result = json.loads(raw)
        except HTTPError as exc:
            status = exc.code
            invalid_key = False
            if status == 400:
                try:
                    error = json.loads(exc.read(8192)).get("error", {})
                    invalid_key = any(isinstance(detail, dict) and detail.get("reason") in {
                        "API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_SERVICE_BLOCKED",
                    } for detail in error.get("details", [])) if isinstance(error, dict) else False
                except (ValueError, TypeError, AttributeError, OSError):
                    pass
            exc.close()
            if status == 429:
                raise ProviderRateLimitError("Gemini request quota is exhausted") from None
            if status in {401, 403} or invalid_key:
                raise ProviderAuthenticationError("Gemini API credentials or permissions are invalid") from None
            raise ProviderUnavailableError("Gemini request was rejected; check the configured model") from None
        except (TimeoutError, socket.timeout):
            raise ProviderTimeoutError("Gemini request timed out") from None
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise ProviderTimeoutError("Gemini request timed out") from None
            raise ProviderUnavailableError("Gemini service is unavailable") from None
        except OSError:
            raise ProviderUnavailableError("Gemini connection failed") from None
        except (UnicodeError, ValueError):
            raise InvalidProviderResponseError("Gemini returned invalid JSON") from None
        if not isinstance(result, dict) or "error" in result:
            raise InvalidProviderResponseError("Gemini returned an invalid envelope")
        return result


class GeminiEmbeddingProvider:
    def __init__(self, transport, *, model=DEFAULT_EMBEDDING_MODEL, dimensions=768):
        if type(dimensions) is not int or not 128 <= dimensions <= 3072:
            raise ValueError("embedding dimensions must be 128-3072")
        self.transport = transport
        self.model = _model_name(model)
        self.dimensions = dimensions
        self._document_cache = {}
        self._cache_lock = RLock()

    def _request(self, text, task):
        return {"model": "models/" + self.model, "content": {"parts": [{"text": text}]},
                "taskType": task, "outputDimensionality": self.dimensions}

    def embed_documents(self, texts):
        if not isinstance(texts, list) or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("embedding inputs must be non-blank strings")
        if not texts:
            return []
        # Editing one document must not resend every unchanged chunk to Google.
        # This cache belongs to one fixed model/dimension configuration only.
        with self._cache_lock:
            missing = list(dict.fromkeys(text for text in texts if text not in self._document_cache))
            resolved = dict(self._document_cache)
            for start in range(0, len(missing), 16):
                batch = missing[start:start + 16]
                response = self.transport.post(self.model, "batchEmbedContents", {
                    "requests": [self._request(text, "RETRIEVAL_DOCUMENT") for text in batch],
                })
                items = response.get("embeddings")
                vectors = validate_embedding_batch(
                    [item.get("values") if isinstance(item, dict) else None for item in items]
                    if isinstance(items, list) else None,
                    expected_count=len(batch), expected_dimensions=self.dimensions,
                )
                resolved.update(zip(batch, vectors, strict=True))
            self._document_cache = dict(list(resolved.items())[-2048:])
            return [list(resolved[text]) for text in texts]

    def embed_query(self, text):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("embedding query must be non-blank")
        response = self.transport.post(self.model, "embedContent", self._request(text, "RETRIEVAL_QUERY"))
        item = response.get("embedding")
        return validate_embedding_batch(
            [item.get("values") if isinstance(item, dict) else None],
            expected_count=1, expected_dimensions=self.dimensions,
        )[0]


class GeminiLLMProvider(GroundedJSONLLMProvider):
    def __init__(self, transport, *, model=DEFAULT_LLM_MODEL, max_tokens=2048):
        super().__init__(transport, model=_model_name(model), max_tokens=max_tokens)

    def _complete(self, system, user, schema, max_tokens):
        generation = {"temperature": 0, "maxOutputTokens": max_tokens,
                      "responseMimeType": "application/json", "responseJsonSchema": schema}
        if self.model == DEFAULT_LLM_MODEL:
            generation["thinkingConfig"] = {"thinkingLevel": "MINIMAL"}
        response = self.transport.post(self.model, "generateContent", {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation,
        })
        candidates = response.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
            raise InvalidProviderResponseError("Gemini did not return a complete answer")
        candidate = candidates[0]
        if candidate.get("finishReason") != "STOP":
            raise InvalidProviderResponseError("Gemini answer was blocked or incomplete")
        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list) or not parts:
            raise InvalidProviderResponseError("Gemini answer must contain JSON text")
        texts = []
        for part in parts:
            if not isinstance(part, dict):
                raise InvalidProviderResponseError("Gemini returned an invalid answer part")
            if part.get("thought") is True:
                continue
            if not isinstance(part.get("text"), str):
                raise InvalidProviderResponseError("Gemini returned an unsupported answer part")
            texts.append(part["text"])
        text = "".join(texts)
        if not text.strip():
            raise InvalidProviderResponseError("Gemini answer must contain JSON text")
        return text
