"""Unit tests for the self-updater (utilities/system_update.py).

Docker isn't available in CI, so anything that would shell out is mocked.
These tests lock in the fixes for the updater's historical failure modes:
invisible sidecar logs, absolute compose paths, detached-HEAD branch
detection, unsafe/unbounded backups, and compose-ps JSON parsing.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utilities.system_update import SystemUpdateManager


@pytest.fixture
def manager(tmp_path):
    return SystemUpdateManager(repo_path=str(tmp_path))


# --- branch detection -------------------------------------------------

def test_update_branch_env_override(manager, monkeypatch):
    monkeypatch.setenv("UPDATE_BRANCH", "release")
    assert manager._get_update_branch() == "release"


def test_update_branch_normal(manager, monkeypatch):
    monkeypatch.delenv("UPDATE_BRANCH", raising=False)
    monkeypatch.setattr(manager, "run_command",
                        lambda cmd, **kw: (True, "main") if "rev-parse" in cmd else (False, ""))
    assert manager._get_update_branch() == "main"


def test_update_branch_detached_head_falls_back_to_origin_default(manager, monkeypatch):
    monkeypatch.delenv("UPDATE_BRANCH", raising=False)

    def fake_run(cmd, **kw):
        if "rev-parse" in cmd:
            return True, "HEAD"  # detached
        if "symbolic-ref" in cmd:
            return True, "refs/remotes/origin/production"
        return False, ""

    monkeypatch.setattr(manager, "run_command", fake_run)
    assert manager._get_update_branch() == "production"


def test_update_branch_last_resort_main(manager, monkeypatch):
    monkeypatch.delenv("UPDATE_BRANCH", raising=False)
    monkeypatch.setattr(manager, "run_command", lambda cmd, **kw: (False, ""))
    assert manager._get_update_branch() == "main"


# --- backups -----------------------------------------------------------

def test_backup_copies_sqlite_safely_and_prunes(manager, tmp_path):
    # A real sqlite db so the online-backup API path is exercised
    db_dir = tmp_path / "master_db"
    db_dir.mkdir()
    conn = sqlite3.connect(db_dir / "master.db")
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES ('hello')")
    conn.commit()
    conn.close()

    backup_root = tmp_path / "backups"
    # Pre-seed more than BACKUP_RETENTION old backups to verify pruning
    for i in range(SystemUpdateManager.BACKUP_RETENTION + 3):
        (backup_root / f"backup_2020010{i:02d}_000000").mkdir(parents=True)

    ok, message = manager.create_backup(backup_dir=str(backup_root))
    assert ok, message

    remaining = sorted(p.name for p in backup_root.glob("backup_*"))
    assert len(remaining) == SystemUpdateManager.BACKUP_RETENTION

    # The new backup survives pruning and the copied DB is intact
    newest = backup_root / remaining[-1]
    copied = newest / "master_db" / "master.db"
    assert copied.exists()
    conn = sqlite3.connect(copied)
    assert conn.execute("SELECT v FROM t").fetchone() == ("hello",)
    conn.close()


def test_backup_reports_nothing_to_backup(manager):
    ok, message = manager.create_backup()
    assert not ok
    assert "No database directories" in message


# --- restart log location ----------------------------------------------

def test_restart_log_reads_shared_backups_location(manager, tmp_path):
    log = tmp_path / "backups" / "restart_output.log"
    log.parent.mkdir()
    log.write_text("=== SUCCESS ===")
    assert "SUCCESS" in manager.get_restart_log()


def test_restart_log_falls_back_to_legacy_location(manager, tmp_path):
    (tmp_path / "restart_output.log").write_text("legacy content")
    assert "legacy content" in manager.get_restart_log()


def test_restart_log_missing(manager):
    assert "No restart log found" in manager.get_restart_log()


# --- sidecar construction ----------------------------------------------

def test_sidecar_mounts_working_dir_at_same_path_and_logs_to_backups(manager, monkeypatch):
    captured = {}
    manager._project_info = {
        "project_name": "kbm",
        "working_dir": "/opt/kbm",
        "config_file": "/opt/kbm/compose.yaml",
        "config_files": ["/opt/kbm/compose.yaml", "/opt/kbm/compose.traefik.yaml"],
        "container_id": "abc123",
    }
    monkeypatch.setattr(manager, "check_docker_available", lambda: (True, "ok"))
    monkeypatch.setattr(manager, "_get_own_image", lambda: "kbm-python-app:latest")

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return True, ""

    monkeypatch.setattr(manager, "run_command", fake_run)

    ok, message = manager.restart_containers(rebuild=True)
    assert ok, message

    cmd = captured["cmd"]
    # Same-path mount so the absolute -f paths from compose labels resolve
    assert "/opt/kbm:/opt/kbm" in cmd
    script = cmd[-1]
    assert "-f /opt/kbm/compose.yaml" in script
    assert "-f /opt/kbm/compose.traefik.yaml" in script
    assert "--build" in script
    # Log goes to the bind-mounted backups dir, and failure is marked
    assert "/opt/kbm/backups/restart_output.log" in script
    assert "FAILED" in script


# --- container status parsing ------------------------------------------

def test_container_status_parses_json_array(manager, monkeypatch):
    payload = json.dumps([
        {"Name": "python-app", "State": "running", "Status": "Up 2 hours"},
        {"Name": "caddy", "State": "running", "Status": "Up 2 hours"},
    ])
    manager._project_info = {"project_name": "kbm", "working_dir": "/opt/kbm",
                             "config_file": "compose.yaml",
                             "config_files": ["compose.yaml"], "container_id": "x"}
    monkeypatch.setattr(manager, "run_command", lambda cmd, **kw: (True, payload))
    result = manager.get_container_status()
    assert [c["name"] for c in result] == ["python-app", "caddy"]


def test_container_status_parses_ndjson(manager, monkeypatch):
    payload = '\n'.join([
        json.dumps({"Name": "python-app", "State": "running", "Status": "Up"}),
        json.dumps({"Name": "caddy", "State": "exited", "Status": "Exited (0)"}),
    ])
    manager._project_info = {"project_name": "kbm", "working_dir": "/opt/kbm",
                             "config_file": "compose.yaml",
                             "config_files": ["compose.yaml"], "container_id": "x"}
    monkeypatch.setattr(manager, "run_command", lambda cmd, **kw: (True, payload))
    result = manager.get_container_status()
    assert [c["state"] for c in result] == ["running", "exited"]


# --- preflight -----------------------------------------------------------

def test_preflight_returns_structured_checks_without_docker(manager):
    """In an environment with no docker at all, preflight must degrade to a
    structured failure report — never raise."""
    result = manager.preflight()
    assert isinstance(result["ok"], bool)
    names = [c["name"] for c in result["checks"]]
    assert "Docker access" in names
    assert "Backups directory writable" in names
    for check in result["checks"]:
        assert set(check) == {"name", "ok", "detail"}
