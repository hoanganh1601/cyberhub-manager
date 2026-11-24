"""Unit tests for commercial repository query scope."""

import cyberhub_manager.infrastructure.repositories.commercial_repository as repository_module
from cyberhub_manager.infrastructure.repositories.commercial_repository import CommercialRepository


def test_manager_overview_limits_placements_to_global_and_own_store(monkeypatch):
    calls = []

    def fake_rows(_conn, query, params=()):
        calls.append((query, params))
        return []

    monkeypatch.setattr(repository_module, "rows", fake_rows)

    result = CommercialRepository().overview(object(), 17, include_global=False)

    assert result == {
        "partners": [],
        "contracts": [],
        "settlements": [],
        "placements": [],
    }
    placement_query, placement_params = calls[0]
    assert "pl.store_id IS NULL OR pl.store_id=%s" in placement_query
    assert placement_params == (17,)
    assert len(calls) == 1


def test_admin_overview_reads_all_placements_and_management_data(monkeypatch):
    calls = []

    def fake_rows(_conn, query, params=()):
        calls.append((query, params))
        return []

    monkeypatch.setattr(repository_module, "rows", fake_rows)

    result = CommercialRepository().overview(object(), 17, include_global=True)

    assert set(result) == {"partners", "contracts", "settlements", "placements"}
    placement_query, placement_params = calls[0]
    assert "pl.store_id IS NULL OR pl.store_id=%s" not in placement_query
    assert placement_params == ()
    assert len(calls) == 4
