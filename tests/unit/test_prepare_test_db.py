"""LI-09 — Unit test cho scripts/prepare_test_db.py, không cần MySQL.

scripts/ không phải package nằm trong pythonpath của pytest nên module được nạp
trực tiếp từ đường dẫn file.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from mysql.connector import errorcode
from mysql.connector.errors import InterfaceError, ProgrammingError

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "prepare_test_db.py"


@pytest.fixture
def script(monkeypatch):
    spec = importlib.util.spec_from_file_location("prepare_test_db", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # load_settings đặt lại MYSQL_DATABASE; monkeypatch trả về giá trị cũ sau test.
    monkeypatch.setenv("MYSQL_DATABASE", "cyberhub_manager")
    monkeypatch.setenv("MYSQL_USER", "tester")
    monkeypatch.setenv("MYSQL_PASSWORD", "secret")
    return module


SETTINGS = SimpleNamespace(
    mysql_host="127.0.0.1",
    mysql_port=3306,
    mysql_user="tester",
    mysql_password="secret",
)


class FakeConnection:
    def __init__(self, calls, error=None):
        self.calls = calls
        self.error = error

    def cursor(self):
        return self

    def execute(self, sql):
        self.calls.append(("execute", sql))
        if self.error is not None:
            raise self.error

    def close(self):
        self.calls.append(("close",))


@pytest.mark.parametrize(
    "database",
    [
        "cyberhub_manager",  # database development
        "cyberhub_manager_migration_test",  # có hậu tố _test nhưng không được chốt
        "other_test",
        "cyberhub_manager_test ",
        "CYBERHUB_MANAGER_TEST",
    ],
)
def test_require_test_database_refuses_anything_else(script, database):
    with pytest.raises(script.PrepareError) as exc_info:
        script.require_test_database(database)

    assert exc_info.value.exit_code == script.EXIT_REFUSED


def test_require_test_database_accepts_exact_name(script):
    assert script.require_test_database("cyberhub_manager_test") == (
        "cyberhub_manager_test"
    )


def test_main_refuses_development_database_without_connecting(
    script, monkeypatch, capsys
):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not connect")

    monkeypatch.setattr(script.mysql.connector, "connect", forbidden)

    assert script.main(["--database", "cyberhub_manager"]) == script.EXIT_REFUSED
    assert "Refusing to prepare database 'cyberhub_manager'" in capsys.readouterr().err


def test_main_prints_target_before_migrating(script, monkeypatch, capsys):
    steps = []
    monkeypatch.setattr(
        script,
        "create_database_if_missing",
        lambda settings, database: steps.append(("create", database)),
    )
    monkeypatch.setattr(
        script,
        "run_test_migrations",
        lambda database: steps.append(("migrate", database)),
    )

    assert script.main([]) == 0

    out = capsys.readouterr().out
    assert out.index("Target database: cyberhub_manager_test") < out.index("ready")
    assert steps == [
        ("create", "cyberhub_manager_test"),
        ("migrate", "cyberhub_manager_test"),
    ]


def test_create_database_uses_if_not_exists(script, monkeypatch):
    calls = []
    monkeypatch.setattr(
        script.mysql.connector, "connect", lambda **kw: FakeConnection(calls)
    )

    script.create_database_if_missing(SETTINGS, "cyberhub_manager_test")

    assert calls[0][0] == "execute"
    assert calls[0][1].startswith(
        "CREATE DATABASE IF NOT EXISTS `cyberhub_manager_test`"
    )
    assert ("close",) in calls


def test_mysql_down_returns_failure_with_instructions(script, monkeypatch, capsys):
    def down(**kwargs):
        raise InterfaceError(msg="refused", errno=errorcode.CR_CONN_HOST_ERROR)

    monkeypatch.setattr(script.mysql.connector, "connect", down)
    monkeypatch.setattr(
        script,
        "run_test_migrations",
        lambda database: pytest.fail("must not migrate"),
    )

    assert script.main([]) == script.EXIT_FAILED

    err = capsys.readouterr().err
    assert "MySQL test database is unavailable." in err
    assert "docker compose up -d mysql" in err
    assert "python scripts/prepare_test_db.py" in err


def test_missing_create_privilege_prints_grant_instructions(script, monkeypatch):
    denied = ProgrammingError(msg="denied", errno=errorcode.ER_DBACCESS_DENIED_ERROR)
    calls = []

    def connect(**kwargs):
        if "database" in kwargs:  # database chưa tồn tại / chưa được cấp quyền
            raise denied
        return FakeConnection(calls, error=denied)

    monkeypatch.setattr(script.mysql.connector, "connect", connect)

    with pytest.raises(script.PrepareError) as exc_info:
        script.create_database_if_missing(SETTINGS, "cyberhub_manager_test")

    message = str(exc_info.value)
    assert "cannot create database 'cyberhub_manager_test'" in message
    assert "GRANT ALL PRIVILEGES ON cyberhub_manager_test.* TO 'tester'@'%'" in message
    assert ("close",) in calls


def test_existing_database_without_create_privilege_is_accepted(script, monkeypatch):
    denied = ProgrammingError(msg="denied", errno=errorcode.ER_DBACCESS_DENIED_ERROR)
    calls = []

    def connect(**kwargs):
        if "database" in kwargs:  # database đã được tạo sẵn và cấp quyền
            return FakeConnection(calls)
        return FakeConnection(calls, error=denied)

    monkeypatch.setattr(script.mysql.connector, "connect", connect)

    script.create_database_if_missing(SETTINGS, "cyberhub_manager_test")


def test_migration_failure_returns_non_zero(script, monkeypatch, capsys):
    monkeypatch.setattr(script, "create_database_if_missing", lambda *args: None)

    def broken(database):
        raise RuntimeError("Migration failed: 002_indexes.sql")

    monkeypatch.setattr(script, "run_test_migrations", broken)

    assert script.main([]) == script.EXIT_FAILED
    assert "Migration failed: 002_indexes.sql" in capsys.readouterr().err


def test_script_does_not_seed_or_reset(script):
    source = SCRIPT.read_text(encoding="utf-8")

    assert "seed_db" not in source
    assert "reset_demo" not in source
