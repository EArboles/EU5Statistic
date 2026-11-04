"""Identifying active mods from playsets.json"""

import json
import logging
from pathlib import Path


class ModsResolver:
    """Reads playsets.json and returns the paths of active mods"""

    PLAYSETS_FILE = "playsets.json"

    def __init__(self, user_data_folder: Path, logger: logging.Logger) -> None:
        self.user_data_folder = user_data_folder
        self.logger: logging.Logger = logger

    def get_active_mod_paths(self) -> list[Path]:
        """
        Returns the paths of active mods in order of priority.

        The order corresponds to `orderedListMods` in the active playset.
        Empty paths and disabled mods are filtered out.
        """
        playsets_file = self.user_data_folder / self.PLAYSETS_FILE
        if not playsets_file.is_file():
            self.logger.info("playsets.json not found — mods are not enabled")
            return []

        try:
            data = json.loads(playsets_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            self.logger.warning("Failed to read playsets.json: %s", e)
            return []

        playsets = data.get("playsets", [])
        active = next(
            (p for p in playsets if p.get("isActive")),
            None,
        )
        if active is None:
            self.logger.info("No active playset found — mods are not enabled")
            return []

        paths: list[Path] = []
        local_mods_without_loc: list[str] = []
        workshop_mods_without_loc: list[str] = []
        for mod in active.get("orderedListMods", []):
            if not mod.get("isEnabled"):
                continue
            path_str = (mod.get("path") or "").strip()
            if not path_str:
                continue
            path = Path(path_str)
            if path.is_dir():
                paths.append(path)
            else:
                mod_name = path.name

                if "workshop" in path_str.lower():
                    workshop_mods_without_loc.append(mod_name)
                else:
                    local_mods_without_loc.append(mod_name)

        if local_mods_without_loc or workshop_mods_without_loc:
            parts = []
            if local_mods_without_loc:
                parts.append(f"Local: {', '.join(local_mods_without_loc)}")
            if workshop_mods_without_loc:
                parts.append(f"Workshop: {', '.join(workshop_mods_without_loc)}")

            self.logger.warning("Mods folder not found: %s", " | ".join(parts))

        return paths
