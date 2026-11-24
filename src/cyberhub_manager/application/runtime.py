"""Application startup and fallback error boundary shared by both presentations."""
from cyberhub_manager.infrastructure.db_errors import MySQLError as StorageError
from cyberhub_manager.infrastructure.db_errors import to_application_error as storage_error


def load_settings():
    from cyberhub_manager.infrastructure.config import load_settings as load

    return load()
