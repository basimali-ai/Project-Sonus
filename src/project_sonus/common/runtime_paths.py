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
import os
from typing import Never
# ---------------------------------

# --- Third-Party Imports ---
from appdirs import user_config_dir, user_data_dir
# ---------------------------------


class Paths:
    __slots__ = (
        "ASSETS_DIR",
        "CONFIG_FILE",
        "DOSE_FILE",
        "IS_DEPLOYED",
        "LOGO_FILE",
        "LOG_DIR",
        "LOG_FILE",
        "LOG_FILE_TXT",
        "PERSISTENCE_FILE",
        "PROJECT_ROOT",
        "RUNTIME_DIR",
        "SETTINGS_DIR",
        "USER_DATA_DIR",
        "_initialized",
    )

    def __init__(self) -> None:
        self._initialized = False

    def initialize(self, runtime_dir: str) -> None:
        self.RUNTIME_DIR = runtime_dir
        self.PROJECT_ROOT = os.path.dirname(runtime_dir)
        self._set_dir_path_constants()
        self._set_file_path_constants()
        self._initialized = True

    def __getattr__(self, name: str) -> Never:
        if not self._initialized:
            raise RuntimeError(f"Paths accessed before initialize(): '{name}'")
        raise AttributeError(name)

    def _set_dir_path_constants(self) -> None:
        deployed_marker_path = os.path.join(self.RUNTIME_DIR, "_deployed.marker")
        self.IS_DEPLOYED = os.path.exists(deployed_marker_path)
        if self.IS_DEPLOYED:
            app_name = "ProjectSonus"
            app_author = "ProjectSonus"
            self.USER_DATA_DIR = user_data_dir(app_name, app_author)
            self.LOG_DIR = os.path.join(self.USER_DATA_DIR, "Logs")
            self.SETTINGS_DIR = user_config_dir(app_name, app_author)
        else:
            project_root = os.path.dirname(self.RUNTIME_DIR)
            self.USER_DATA_DIR = os.path.join(project_root, "UserData")
            self.SETTINGS_DIR = os.path.join(project_root, "Settings")
            self.LOG_DIR = os.path.join(project_root, "Logs")

        self.ASSETS_DIR = os.path.join(self.RUNTIME_DIR, "Assets")

        os.makedirs(self.USER_DATA_DIR, exist_ok=True)
        os.makedirs(self.SETTINGS_DIR, exist_ok=True)
        os.makedirs(self.LOG_DIR, exist_ok=True)

    def _set_file_path_constants(self) -> None:
        self.DOSE_FILE = os.path.join(self.USER_DATA_DIR, "dose_data.json")
        self.PERSISTENCE_FILE = os.path.join(self.USER_DATA_DIR, "persistence.json")
        self.CONFIG_FILE = os.path.join(self.SETTINGS_DIR, "config.yaml")
        self.LOGO_FILE = os.path.join(self.ASSETS_DIR, "logo.ico")

        self.LOG_FILE = os.path.join(self.LOG_DIR, "project_sonus.log")
        self.LOG_FILE_TXT = os.path.join(self.LOG_DIR, "project_sonus_log.txt")


paths = Paths()
