"""Role migration requires an explicit complete approved mapping."""

import pytest

from scripts.rbac_cutover import validate_manifest


def test_cutover_mapping_requires_admin_and_director():
    employees = [
        {"id": 1, "username": "tech", "role": "ADMIN", "status": "ACTIVE"},
        {"id": 2, "username": "owner", "role": "ADMIN", "status": "ACTIVE"},
    ]
    manifest = {"approval_reference": "RBAC-APPROVED-01", "accounts": [
        {"employee_id": 1, "username": "tech", "expected_role": "ADMIN", "target_role": "ADMIN"},
        {"employee_id": 2, "username": "owner", "expected_role": "ADMIN", "target_role": "DIRECTOR"},
    ]}
    assert len(validate_manifest(manifest, employees)) == 2
    with pytest.raises(ValueError, match="every active ADMIN"):
        validate_manifest({**manifest, "accounts": manifest["accounts"][:1]}, employees)
    with pytest.raises(ValueError, match="at least one"):
        validate_manifest({**manifest, "accounts": [{**x, "target_role": "DIRECTOR"} for x in manifest["accounts"]]}, employees)
