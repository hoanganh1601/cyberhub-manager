"""Generators for opaque domain identifiers shared across use cases."""

from uuid import uuid4


TRANSACTION_CODE_PREFIX = "TX-"
TRANSACTION_CODE_HEX_LENGTH = 17


def new_transaction_code() -> str:
    """Return a transaction code that fits ``account_transactions.code``."""

    return TRANSACTION_CODE_PREFIX + uuid4().hex[:TRANSACTION_CODE_HEX_LENGTH]
