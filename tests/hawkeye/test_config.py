"""Config merge and validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scout.hawkeye.config import merge_by_id, validate_antipatterns, validate_rules


def test_merge_by_id_overlay_wins() -> None:
    base = [{"id": "R1", "type": "path_glob", "severity": "warning", "path_glob": "a/**"}]
    overlay = [{"id": "R1", "type": "path_glob", "severity": "error", "path_glob": "b/**"}]
    merged = merge_by_id(base, overlay)
    assert len(merged) == 1
    assert merged[0]["severity"] == "error"
    assert merged[0]["path_glob"] == "b/**"


def test_merge_by_id_does_not_mutate_base() -> None:
    base = [{"id": "R1", "type": "path_glob", "severity": "warning", "path_glob": "a/**"}]
    overlay = [{"id": "R1", "severity": "error"}]
    merged = merge_by_id(base, overlay)
    merged[0]["severity"] = "note"
    assert base[0]["severity"] == "warning"


def test_validate_rules_requires_fields() -> None:
    with pytest.raises(ValueError, match="missing fields"):
        validate_rules([{"id": "X"}])


def test_validate_antipatterns_duplicate_id() -> None:
    items = [
        {"id": "AP1", "type": "text_regex", "severity": "error"},
        {"id": "AP1", "type": "text_regex", "severity": "warning"},
    ]
    with pytest.raises(ValueError, match="duplicate"):
        validate_antipatterns(items)


def test_setup_writes_config(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod
    from scout.hawkeye.setup_cmd import run_setup

    target = tmp_path / ".hawkeye"
    orig_global = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = target
        dest = run_setup(
            scout_api="http://127.0.0.1:8741/v1",
            space="testspace",
            force=True,
        )
        assert dest == target
        assert (target / "config.yaml").is_file()
        assert (target / "rules.yaml").is_file()
        assert (target / "antipatterns.yaml").is_file()
        data = yaml.safe_load((target / "rules.yaml").read_text())
        ids = {r["id"] for r in data["rules"]}
        assert "HKY-AUTH-001" in ids
        assert "HKY-API-005" in ids
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig_global


def test_load_config_missing_scout_api(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    cfg_dir = tmp_path / ".hawkeye"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text("default_space: myapp\n")
    orig_global = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
        with pytest.raises(ValueError, match="missing required field scout_api"):
            cfg_mod.load_config()
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig_global


def test_load_config_missing_default_space(tmp_path: Path) -> None:
    from scout.hawkeye import config as cfg_mod

    cfg_dir = tmp_path / ".hawkeye"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text("scout_api: http://127.0.0.1:8741/v1\n")
    orig_global = cfg_mod.GLOBAL_HAWKEYE_DIR
    try:
        cfg_mod.GLOBAL_HAWKEYE_DIR = cfg_dir
        with pytest.raises(ValueError, match="missing required field default_space"):
            cfg_mod.load_config()
    finally:
        cfg_mod.GLOBAL_HAWKEYE_DIR = orig_global


def test_load_pack_yaml_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scout.hawkeye import config as cfg_mod

    def _missing_pack(name: str) -> dict:
        raise ValueError(f"Failed to load default rule pack ({name}): missing")

    monkeypatch.setattr(cfg_mod, "_read_pack_yaml", _missing_pack)
    with pytest.raises(ValueError, match="Failed to load default rule pack"):
        cfg_mod.load_rules_from_paths()


def test_validate_rules_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="invalid type"):
        validate_rules(
            [{"id": "R1", "type": "not_a_real_type", "severity": "warning", "path_glob": "**"}]
        )


def test_load_yaml_file_parse_error(tmp_path: Path) -> None:
    from scout.hawkeye.config import load_yaml_file

    bad = tmp_path / "bad.yaml"
    bad.write_text("rules: [\n")
    with pytest.raises(ValueError, match="invalid YAML"):
        load_yaml_file(bad)


def test_merge_by_id_warns_on_replace(capsys: pytest.CaptureFixture[str]) -> None:
    base = [{"id": "R1", "type": "path_glob", "severity": "warning", "path_glob": "a/**"}]
    overlay = [{"id": "R1", "type": "path_glob", "severity": "error", "path_glob": "b/**"}]
    merge_by_id(base, overlay)
    assert "replaced by overlay" in capsys.readouterr().err
