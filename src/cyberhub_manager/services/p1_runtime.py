"""Lazy database adapters: the in-memory demo must not load MySQL or .env."""

from contextlib import contextmanager
from functools import wraps


@contextmanager
def errors(memory=False):
    if memory:
        yield
    else:
        from .db_errors import translate_db_errors

        with translate_db_errors():
            yield


def retry_on_transient(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        if self._memory:
            return function(self, *args, **kwargs)
        from .db_errors import retry_on_transient as retry

        return retry(function)(self, *args, **kwargs)

    return wrapped
