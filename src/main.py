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
import queue
import subprocess
import sys
from logging.handlers import MemoryHandler
from typing import Any, Never
# ---------------------------------

# --- Local Imports ---
from project_sonus_utils import SplashScreen, TeeHandler
# ---------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s [T%(thread)d][%(name)s] %(levelname)s: %(message)s"
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

memory_handler = MemoryHandler(capacity=100)
logger.addHandler(memory_handler)


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
                "[main][find_app_root] _sonus_root.marker not found."
            )

        current_path = parent_path


def start_app(
    runtime_dir: str, was_restarted: bool, splash: SplashScreen, q: queue.Queue[Any]
) -> None:
    try:
        sys.path.insert(0, runtime_dir)

        from project_sonus.common.constants import AppConstants
        from project_sonus.common.runtime_paths import paths
        from project_sonus.configuration.config_manager import config_manager
        from project_sonus.configuration.persistence import persistence_manager
        from project_sonus.core.controller import SonusController
        from project_sonus.ui.protocols import assert_ui_compliance
        from project_sonus.ui.ui import SonusUI

        paths.initialize(runtime_dir)

        fh1 = logging.FileHandler(paths.LOG_FILE, mode="w", encoding="utf-8")
        fh2 = logging.FileHandler(paths.LOG_FILE_TXT, mode="w", encoding="utf-8")
        for fh in (fh1, fh2):
            fh.setFormatter(formatter)

        tee_handler = TeeHandler(fh1, fh2)
        memory_handler.setTarget(tee_handler)
        memory_handler.flush()
        logger.removeHandler(memory_handler)
        memory_handler.close()
        logger.addHandler(tee_handler)
        logger.info(
            "[main][start_app] Multi-file logging initialized. "
            "Buffered logs written to all targets."
        )

        persistence_manager.load()
        config_manager.load_config()
        temp_ui = SonusUI(asserting=True)
        assert_ui_compliance(temp_ui)
        controller = SonusController(ui=None, was_restarted=was_restarted)
        q.put((SonusUI, controller, AppConstants))
        logger.info("[main][start_app] Destroying splash screen...")
        splash.hide()
        splash.destroy()

    except Exception:
        logger.exception("[main][start_app] Critical error occurred during startup.")
        sys.exit(1)


def main(RUNTIME_DIR: str | None = None) -> Never:
    logo = r"""
    ██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗
    ██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝
    ██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║   
    ██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║   
    ██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║   
    ╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝   
                                                              
        ███████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗          
        ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝          
        ███████╗██║   ██║██╔██╗ ██║██║   ██║███████╗          
        ╚════██║██║   ██║██║╚██╗██║██║   ██║╚════██║          
        ███████║╚██████╔╝██║ ╚████║╚██████╔╝███████║          
        ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝          
    """
    try:
        print(logo)
    except UnicodeEncodeError:
        print("=== PROJECT SONUS ===")

    if not RUNTIME_DIR:
        try:
            RUNTIME_DIR = find_app_root()
        except FileNotFoundError as e:
            logger.critical(
                "[main][main] Exiting with FAILURE code (1) "
                f"because application root was not found.\n[{e}]"
            )
            sys.exit(1)

    was_restarted = "--restarted" in sys.argv

    if not was_restarted:
        logo_path = os.path.join(RUNTIME_DIR, "Assets", "logo.png")
        splash = SplashScreen(
            width=512,
            height=512,
            image_path=logo_path,
        )
    else:
        logo_path = os.path.join(RUNTIME_DIR, "Assets", "restarting.png")
        splash = SplashScreen(
            width=500,
            height=181,
            image_path=logo_path,
            click_through=True,
            grab_focus=False,
            position=(10, 10),
        )

    q: queue.Queue[Any] = queue.Queue()
    splash.show(lambda: start_app(RUNTIME_DIR, was_restarted, splash, q))  # Blocking
    ui_class, controller, AppConstants = q.get()

    logger.info("[main][main] Setting up the UI...")
    ui = ui_class()
    controller.set_up_ui(ui)
    logger.info("[main][main] Starting UI MainLoop...")
    ui.MainLoop()
    logger.info("[main][main] MainLoop finished. Application is exiting.")

    if controller.restart_needed:
        try:
            py = os.path.join(RUNTIME_DIR, "restarter.py")
            exe = os.path.join(RUNTIME_DIR, "Project Sonus Restarter.exe")

            restarter_path = None
            if os.path.exists(py):
                restarter_path = py
            elif os.path.exists(exe):
                restarter_path = exe

            if restarter_path is not None:
                logger.info(f"[main][main] Launching Restarter: [{restarter_path}]...")
                command = (
                    [sys.executable, restarter_path]
                    if restarter_path.endswith(".py")
                    else [restarter_path]
                )
                subprocess.Popen(command)
            else:
                raise FileNotFoundError("restarter_path does not exist")
        except Exception:
            logger.exception("[main][main] Failed to restart.")
        finally:
            logger.info(
                "[main][main] Exiting with RESTART code "
                f"({AppConstants.RESTART_EXIT_CODE})."
            )
            sys.exit(AppConstants.RESTART_EXIT_CODE)
    else:
        logger.info("[main][main] Exiting with NORMAL code (0).")
        logger.info(
            "[main][main] NOTE: The terminal may appear to hang "
            "if controlled by a restart script. "
            "After the COM uninitialized logs, press Ctrl+C to exit in such a case."
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
