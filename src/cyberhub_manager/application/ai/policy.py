"""Construct the configured assistant quota/audit persistence adapter."""


def create_policy_store(path, *, limits=None):
    from cyberhub_manager.infrastructure.ai.policy_store import SQLiteAssistantPolicyStore

    return SQLiteAssistantPolicyStore(path, limits=limits)
