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
import subprocess
import sys
import time
# ---------------------------------

SLEEP_TIME_SECONDS = 3


def find_app_root() -> str:
    """
    Finds the application root directory using marker.
    """
    if getattr(sys, "frozen", False):
        start_path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        start_path = os.path.dirname(os.path.abspath(__file__))

    current_path = start_path
    while True:
        if os.path.exists(os.path.join(current_path, "_sonus_root.marker")):
            return current_path

        parent_path = os.path.dirname(current_path)

        if parent_path == current_path:
            raise FileNotFoundError(
                "[restarter][find_app_root] _sonus_root.marker not found."
            )

        current_path = parent_path


try:
    RUNTIME_DIR = find_app_root()
    py = os.path.join(RUNTIME_DIR, "main.py")
    exe = os.path.join(RUNTIME_DIR, "Project Sonus.exe")

    run_target = None
    if os.path.exists(py):
        run_target = py
    elif os.path.exists(exe):
        run_target = exe

    if run_target is not None:
        print(
            f"[restarter] Relaunching [{run_target}] in {SLEEP_TIME_SECONDS} seconds..."
        )
        time.sleep(SLEEP_TIME_SECONDS)
        print(f"[restarter] Relaunching [{run_target}]...")
        restart_code_arg = "--restarted"
        command = (
            [sys.executable, run_target, restart_code_arg]
            if run_target.endswith(".py")
            else [run_target, restart_code_arg]
        )
        subprocess.Popen(command)
    else:
        raise FileNotFoundError("run_target does not exist")
except Exception as e:
    with open("restarter_error.log", "w") as f:
        f.write(f"[restarter] Failed to restart:\n{e}\n")
finally:
    os._exit(0)
