"""Public failures for knowledge ingestion and provider-independent RAG."""


class KnowledgeError(Exception):
    """The knowledge pipeline failed; do not publish partial or stale results."""


class InvalidMetadataError(KnowledgeError):
    """A document does not follow the approved metadata contract."""


class DuplicateDocumentError(KnowledgeError):
    """Two files declare the same document ID, regardless of status."""


class KnowledgePathError(KnowledgeError):
    """An input path is outside the configured root or uses a symlink."""


class DocumentTooLargeError(KnowledgeError):
    """A document exceeds the configured byte limit."""


class KnowledgeReadError(KnowledgeError):
    """The configured corpus cannot be read completely."""


class ChunkingError(KnowledgeError):
    """A document cannot be split without violating the chunking contract."""


class ProviderError(KnowledgeError):
    """Provider failure with a safe message, without credentials or prompts."""


class ProviderUnavailableError(ProviderError):
    """A provider is unavailable; the service decides whether to retry."""


class ProviderTimeoutError(ProviderUnavailableError):
    """A provider exceeded its configured timeout."""


class ProviderBusyError(ProviderUnavailableError):
    """The bounded provider runner has no available worker slot."""


class InvalidProviderResponseError(ProviderError):
    """Provider output violates the shared vector/text contract."""


class KnowledgeIndexUnavailableError(KnowledgeError):
    """No complete current snapshot is available; rebuild before serving."""


class KnowledgeAccessError(KnowledgeError):
    """Requested context is unauthorized, changed or absent from the index."""


class InvalidQuestionError(KnowledgeError):
    """A question is blank, invalid or exceeds the input limit."""


class InsufficientContextError(KnowledgeError):
    """No approved authorized context can be used to build a grounded prompt."""


class ContextBudgetError(KnowledgeError):
    """Context exceeds the configured budget; never silently truncate a rule."""


class InvalidContextError(KnowledgeError):
    """Context cannot be represented safely in the prompt's XML envelope."""
