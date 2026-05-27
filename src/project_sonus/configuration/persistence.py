# Copyright 2026 Syed Basim Ali
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# --- Standard library imports ---
import json
import logging
import os
import shutil
from datetime import datetime
from typing import Any
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import PersistenceDefaults, PersistenceKeys
from project_sonus.common.runtime_paths import paths
from project_sonus.common.structures import PersistenceData, ProfileInfo
# ---------------------------------

logger = logging.getLogger(__name__)


class PersistenceManager:
    __slots__ = ("data",)

    def __init__(self) -> None:
        self.data = PersistenceData()

    def _get_defaults(self) -> dict[str, Any]:
        """Returns the default persistent data dict."""
        return {
            PersistenceKeys.PROFILES.value: PersistenceDefaults.PROFILES,
            PersistenceKeys.HOTKEYS.value: PersistenceDefaults.HOTKEYS,
            PersistenceKeys.WINDOW_DISPLAY_IDX.value: PersistenceDefaults.WINDOW_DISPLAY_IDX,
            PersistenceKeys.OVERLAY.value: PersistenceDefaults.OVERLAY,
        }

    def _deep_merge(
        self, defaults: dict[str, Any], loaded: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Recursively merges loaded JSON data into the defaults dictionary.
        """
        for key, value in loaded.items():
            if (
                key in defaults
                and isinstance(defaults[key], dict)
                and isinstance(value, dict)
            ):
                defaults[key] = self._deep_merge(defaults[key], value)
            else:
                defaults[key] = value
        return defaults

    def load(self) -> None:
        """Loads state from JSON. Resets to defaults if corrupt."""
        if not os.path.exists(paths.PERSISTENCE_FILE):
            self.data = PersistenceData(self._get_defaults())
            if not self.save():
                raise RuntimeError(
                    "[load] Failed to write default persistence data to disk."
                )
            return
        try:
            with open(paths.PERSISTENCE_FILE, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                self.data = PersistenceData(
                    self._deep_merge(self._get_defaults(), loaded_data)
                )
                if not self.save():
                    raise RuntimeError(
                        "[load] Failed to save loaded/updated persistence data to disk."
                    )
        except Exception:
            logger.exception(
                "[load] Exception while loading persistence file. Backing up and resetting."
            )
            try:
                backup_path = (
                    f"{paths.PERSISTENCE_FILE}.corrupt_"
                    f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                )
                shutil.copy2(paths.PERSISTENCE_FILE, backup_path)
                logger.warning(
                    f"[load] Corrupted persistence file backed up to: {backup_path}"
                )
                self.data = PersistenceData(self._get_defaults())
                if not self.save():
                    raise RuntimeError(
                        "[load] Failed to write default persistence data to disk after backup."
                    )
            except Exception as e:
                logger.exception(
                    "[load] Failed to create backup of the corrupted file. Cannot continue safely."
                )
                raise RuntimeError(
                    "Persistence file is corrupted and failed to create a backup. "
                    "Please repair or delete it."
                ) from e

    def save(self) -> bool:
        """Dumps state to JSON."""
        try:
            with open(paths.PERSISTENCE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            return True
        except Exception:
            logger.exception("[save] Failed to save persistence file.")
            return False

    def get_profile(self, device_name: str) -> ProfileInfo | None:
        return self.data[PersistenceKeys.PROFILES].get(device_name)

    def set_profile(self, device_name: str, settings: ProfileInfo) -> None:
        self.data[PersistenceKeys.PROFILES][device_name] = settings


persistence_manager = PersistenceManager()
