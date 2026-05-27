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
import logging
import os
import shutil
from datetime import datetime
from typing import Any, Final, TypedDict
# ---------------------------------

# --- Third-Party Imports ---
from ruamel.yaml import YAML, scalarbool, scalarfloat, scalarint, scalarstring
from ruamel.yaml.comments import CommentedMap
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import ConfigDefaults, ConfigKeys
from project_sonus.common.runtime_paths import paths
from project_sonus.common.structures import _C, ConfigKey

from .default_config import get_default_config
# ---------------------------------


logger = logging.getLogger(__name__)

yaml = YAML(typ="rt")
yaml.indent(sequence=4, offset=2)
yaml.preserve_quotes = True


def _parse_bool(val: Any) -> bool | None:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        val = val.strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
        elif val in ("0", "false", "no", "off"):
            return False
    if isinstance(val, (int, float)):
        if val == 1:
            return True
        elif val == 0:
            return False
    return None


class SanitizeInfo(TypedDict, total=False):
    reason: str
    was_fixed: bool
    was_clamped: bool


class ConfigManager:
    yaml_floats = tuple(getattr(scalarfloat, name) for name in scalarfloat.__all__)
    yaml_ints = tuple(getattr(scalarint, name) for name in scalarint.__all__)
    yaml_strings = tuple(getattr(scalarstring, name) for name in scalarstring.__all__)
    yaml_bools = tuple(getattr(scalarbool, name) for name in scalarbool.__all__)

    type_map: Final = {
        float: yaml_floats,
        int: yaml_ints,
        str: yaml_strings,
        bool: yaml_bools,
    }

    def __init__(self) -> None:
        self.config = CommentedMap()
        self.default_config = get_default_config()

    @staticmethod
    def merge_defaults(
        user_cfg: CommentedMap, default_cfg: CommentedMap
    ) -> tuple[CommentedMap, bool, bool]:
        """
        Recursively merge defaults into `user_cfg`, preserving user-modified keys
        while adding missing default keys in the correct order.
        """
        program_modified = False
        user_modified = False
        merged_cfg = CommentedMap()

        if default_cfg.ca.comment:
            merged_cfg.ca.comment = default_cfg.ca.comment

        for key, default_val in default_cfg.items():
            merged_cfg.ca.items[key] = default_cfg.ca.items.get(key)

            if key in user_cfg:
                user_val = user_cfg[key]
                if isinstance(default_val, CommentedMap) and isinstance(
                    user_val, CommentedMap
                ):
                    (
                        merged_nested_val,
                        child_program_modified,
                        child_user_modified,
                    ) = ConfigManager.merge_defaults(user_val, default_val)
                    merged_cfg[key] = merged_nested_val

                    if child_program_modified:
                        program_modified = True
                    if child_user_modified:
                        user_modified = True
                else:
                    merged_cfg[key] = user_val
            else:
                merged_cfg[key] = default_val
                program_modified = True

        for key, user_val in user_cfg.items():
            if key not in merged_cfg:
                merged_cfg[key] = user_val
                user_modified = True

        if len(user_cfg) != len(merged_cfg) and not user_modified:
            program_modified = True

        return merged_cfg, program_modified, user_modified

    def _normalize_value(
        self, merged_val: Any, default_val: Any
    ) -> tuple[float | int | bool | str, bool]:
        for py_type, yaml_types in self.type_map.items():
            if isinstance(merged_val, yaml_types):
                merged_val = py_type(merged_val)
                break

        if isinstance(default_val, float) and isinstance(merged_val, int):
            merged_val = float(merged_val)
        elif (
            isinstance(default_val, int)
            and isinstance(merged_val, float)
            and merged_val == int(merged_val)
        ):
            merged_val = int(merged_val)

        was_fixed = False
        if type(merged_val) is not type(default_val):
            try:
                original_val = merged_val
                if isinstance(default_val, bool):
                    parsed = _parse_bool(merged_val)
                    merged_val = parsed if parsed is not None else False
                try:
                    merged_val = type(default_val)(merged_val)
                except (ValueError, TypeError):
                    merged_val = default_val

                if type(merged_val) is not type(original_val):
                    was_fixed = True

            except (ValueError, TypeError):
                merged_val = default_val
                was_fixed = True

        return merged_val, was_fixed

    @staticmethod
    def _clamp_value(key_obj: ConfigKey[_C], value: float) -> tuple[float | int, bool]:
        key_name = key_obj.name
        min_val: float | int = getattr(ConfigDefaults, f"{key_name}_MIN")
        max_val: float | int = getattr(ConfigDefaults, f"{key_name}_MAX")

        val_before = value
        value = max(min_val, value)
        value = min(max_val, value)
        return value, value != val_before

    def _sanitize_key(
        self,
        merged_cfg: CommentedMap,
        key: str,
        default_val: Any,
        sanitized_keys: dict[str, SanitizeInfo],
        full_path: str,
    ) -> None:
        if key not in merged_cfg:
            return

        key_obj = next(k for k in ConfigKeys if k.value == key)

        val = merged_cfg[key]
        if val is None:
            merged_cfg[key] = default_val
            sanitized_keys[full_path] = {
                "was_fixed": True,
                "was_clamped": False,
                "reason": "None value",
            }
            return

        val, was_fixed = self._normalize_value(val, default_val)
        if isinstance(val, (float, int)) and not isinstance(val, bool):
            val, was_clamped = self._clamp_value(key_obj, val)
        else:
            was_clamped = False

        if was_fixed or was_clamped:
            sanitized_keys[full_path] = {
                "was_fixed": was_fixed,
                "was_clamped": was_clamped,
            }

        merged_cfg[key] = val

    def _sanitize_config_recursive(
        self,
        merged_cfg: CommentedMap,
        default_cfg: CommentedMap,
        sanitized_keys: dict[str, SanitizeInfo],
        path: str = "",
    ) -> None:
        for key, default_val in default_cfg.items():
            full_path = f"{path}.{key}" if path else key

            if isinstance(default_val, CommentedMap):
                child_cfg = merged_cfg.get(key)
                if not isinstance(child_cfg, dict):
                    continue
                self._sanitize_config_recursive(
                    merged_cfg[key], default_val, sanitized_keys, full_path
                )
            else:
                self._sanitize_key(
                    merged_cfg, key, default_val, sanitized_keys, full_path
                )

    def get_from_config(self, key_obj: ConfigKey[_C]) -> _C:
        """
        Fetch a config value.
        """
        if not self.config:
            raise RuntimeError("`get_from_config` called before `load_config`")
        ret: _C = self.config[key_obj.value]
        return ret

    @staticmethod
    def _log_sanitized_keys(
        sanitized_keys: dict[str, SanitizeInfo], func_name: str
    ) -> None:
        log_details = []
        for path, info in sanitized_keys.items():
            reasons = []
            if reason := info.get("reason"):
                reasons.append(reason)
            if info.get("was_fixed"):
                reasons.append("type corrected")
            if info.get("was_clamped"):
                reasons.append("out of range - clamped")

            if reasons:
                log_details.append(f"{path} ({', '.join(reasons)})")

        if log_details:
            logger.warning(
                f"[{func_name}] Sanity check triggered; Corrected the following keys:\n"
                + "\n".join(log_details)
            )

    def load_config(self) -> None:
        """Load config, preserving comments and structure."""
        if not os.path.exists(paths.CONFIG_FILE):
            logger.info("[load_config] Config missing - creating default.")
            self.config = self.default_config
            if not self.save_config():
                raise RuntimeError(
                    "[load_config] Failed to write default configuration to disk."
                )
            return

        try:
            with open(paths.CONFIG_FILE, "r", encoding="utf-8") as f:
                current_cfg = yaml.load(f) or CommentedMap()

            current_cfg, program_modified, user_modified = self.merge_defaults(
                current_cfg, self.default_config
            )
            logger.info("[load_config] Config loaded successfully.")

            sanitized_keys: dict[str, SanitizeInfo] = {}
            self._sanitize_config_recursive(
                current_cfg, self.default_config, sanitized_keys
            )

            if sanitized_keys:
                self._log_sanitized_keys(sanitized_keys, "load_config")

            if program_modified or sanitized_keys:
                logger.info(
                    "[load_config] Config updated with missing or invalid keys. Saving."
                )

            if user_modified:
                logger.info("[load_config] Config had user modified/added keys")

            self.config = current_cfg
            if not self.save_config():
                raise RuntimeError(
                    "[load_config] Failed to save loaded/updated configuration to disk."
                )
        except Exception:
            logger.exception(
                "[load_config] Exception while loading config file. Backing up and resetting."
            )
            try:
                backup_path = (
                    f"{paths.CONFIG_FILE}.corrupt_"
                    f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
                )
                shutil.copy2(paths.CONFIG_FILE, backup_path)
                logger.warning(
                    f"[load_config] Corrupted configuration backed up to: {backup_path}"
                )
                self.config = self.default_config
                if not self.save_config():
                    raise RuntimeError(
                        "[load_config] Failed to write default configuration to disk after backup."
                    )
            except Exception as e:
                logger.exception(
                    "[load_config] Failed to create backup of the corrupted file. "
                    "Cannot continue safely."
                )
                raise RuntimeError(
                    "Configuration file is corrupted and failed to create a backup. "
                    "Please repair or delete it."
                ) from e

    def save_config(self) -> bool:
        """Save YAML with formatting intact."""
        try:
            with open(paths.CONFIG_FILE, "w", encoding="utf-8") as f:
                yaml.dump(self.config, f)
            logger.info("[save_config] Config saved.")
            return True
        except Exception:
            logger.exception("[save_config] Error saving config.")
            return False


config_manager = ConfigManager()
