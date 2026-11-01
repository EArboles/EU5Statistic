"""Tests for ModsResolver: reading playsets.json."""

import json
from pathlib import Path

from eu5statistic.core.mods_resolver import ModsResolver


def _write_playsets(folder: Path, data: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "playsets.json").write_text(json.dumps(data), encoding="utf-8")


def test_no_playsets_file(tmp_path: Path) -> None:
    resolver = ModsResolver(tmp_path)
    assert resolver.get_active_mod_paths() == []


def test_no_active_playset(tmp_path: Path) -> None:
    _write_playsets(tmp_path, {"playsets": [{"isActive": False}]})
    resolver = ModsResolver(tmp_path)
    assert resolver.get_active_mod_paths() == []


def test_active_playset_with_mods(tmp_path: Path) -> None:
    mod1 = tmp_path / "mod1"
    mod2 = tmp_path / "mod2"
    mod1.mkdir()
    mod2.mkdir()

    _write_playsets(
        tmp_path,
        {
            "playsets": [
                {
                    "isActive": True,
                    "orderedListMods": [
                        {"isEnabled": True, "path": str(mod1)},
                        {"isEnabled": True, "path": str(mod2)},
                    ],
                }
            ]
        },
    )
    resolver = ModsResolver(tmp_path)
    paths = resolver.get_active_mod_paths()
    assert paths == [mod1, mod2]


def test_disabled_mods_skipped(tmp_path: Path) -> None:
    mod1 = tmp_path / "mod1"
    mod2 = tmp_path / "mod2"
    mod1.mkdir()
    mod2.mkdir()

    _write_playsets(
        tmp_path,
        {
            "playsets": [
                {
                    "isActive": True,
                    "orderedListMods": [
                        {"isEnabled": False, "path": str(mod1)},
                        {"isEnabled": True, "path": str(mod2)},
                    ],
                }
            ]
        },
    )
    resolver = ModsResolver(tmp_path)
    assert resolver.get_active_mod_paths() == [mod2]


def test_empty_path_skipped(tmp_path: Path) -> None:
    _write_playsets(
        tmp_path,
        {
            "playsets": [
                {
                    "isActive": True,
                    "orderedListMods": [{"isEnabled": True, "path": "  "}],
                }
            ]
        },
    )
    resolver = ModsResolver(tmp_path)
    assert resolver.get_active_mod_paths() == []


def test_missing_mod_folder_skipped(tmp_path: Path) -> None:
    nonexistent = tmp_path / "nonexistent"
    _write_playsets(
        tmp_path,
        {
            "playsets": [
                {
                    "isActive": True,
                    "orderedListMods": [{"isEnabled": True, "path": str(nonexistent)}],
                }
            ]
        },
    )
    resolver = ModsResolver(tmp_path)
    assert resolver.get_active_mod_paths() == []


def test_corrupted_json_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "playsets.json").write_text("not json", encoding="utf-8")
    resolver = ModsResolver(tmp_path)
    assert resolver.get_active_mod_paths() == []
