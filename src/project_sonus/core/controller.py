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
import atexit
import json
import logging
import os
import queue
import signal
import threading
import time
import warnings
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
from math import inf, isfinite
from typing import TYPE_CHECKING, ClassVar, Final, Literal, TypedDict, assert_never
# ---------------------------------

# --- Third-Party Imports ---
from comtypes import (
    COINIT_APARTMENTTHREADED,
    COINIT_MULTITHREADED,
    CoInitializeEx,
    COMObject,
    CoUninitialize,
)

# - Explicit COM init, and uninit registering at application exit -
CoInitializeEx(COINIT_APARTMENTTHREADED)
logger = logging.getLogger(__name__)
logger.info("COM apartment explicitly initialized.")


def _shutdown_com() -> None:
    try:
        CoUninitialize()
        logger.info("COM apartment explicitly uninitialized.")
    except Exception:
        logger.exception("COM uninit failed.")


atexit.register(_shutdown_com)
# --------

import pywintypes
import soundcard as sc
import win32api
import win32con
import win32gui
from pycaw.constants import EDataFlow
from pycaw.pycaw import AudioUtilities, IMMNotificationClient
# ---------------------------------

# --- Local Imports ---
from project_sonus.audio_engine.audio_capture import AudioCaptureWorker
from project_sonus.audio_engine.audio_processing import (
    AudioProcessor,
    AudioProcessorConfig,
)
from project_sonus.audio_engine.state import (
    AudioCaptureErrorEvent,
    AudioCaptureStatusEvent,
)
from project_sonus.common.constants import (
    AppConstants,
    ConfigKeys,
    HotkeyInfoKeys,
    HotkeyModifiers,
    PersistenceKeys,
    ProfileInfoKeys,
)
from project_sonus.common.runtime_paths import paths
from project_sonus.common.state import ErrorType, StatusType
from project_sonus.common.structures import ProfileInfo
from project_sonus.configuration.config_manager import config_manager
from project_sonus.configuration.persistence import persistence_manager
from project_sonus.ui.gui_theme import GUITheme
from project_sonus.ui.state import (
    Ack,
    AckType,
    AudioMetric,
    Calibrating,
    DialogErrorEvent,
    DialogStatusEvent,
    DoseStatus,
    DoseStatusType,
    NotifErrorEvent,
    NotifStatusEvent,
    SplLvl,
    UserEntriesEnum,
    VolCalcErrorEvent,
    VolCalcStatus,
    VolCalcStatusEvent,
    VolLvl,
)
# ---------------------------------

# --- Type checking imports ---
if TYPE_CHECKING:
    from types import FrameType

    from comtypes import IUnknown

    from project_sonus.ui.protocols import UI
# ---------------------------------


class DoseData(TypedDict, total=False):
    save_datetime: str
    dose: float
    reset_datetime: str


class SonusController:
    __slots__ = (
        "ABS_GATE_LUFS",
        "AUDIO_BUFFER_SECONDS",
        "DANGEROUS_PEAK_DB_THRESHOLD",
        "DEFAULT_VOLUME_CORRECTION",
        "DOSE_BASELINE_DB",
        "DOSE_BASELINE_HOURS",
        "DOSE_EXCHANGE_RATE_DB",
        "GUI_STABILITY_THRESHOLD_DB",
        "HEARING_DAMAGE_DB_THRESHOLD",
        "REL_GATE_LU",
        "VOLUME_CALCULATOR_RED_TOLERANCE_DB",
        "VOLUME_CALCULATOR_YELLOW_TOLERANCE_DB",
        "_are_baselines_valid",
        "_are_targets_valid",
        "_current_loaded_device",
        "_device_notification_client",
        "_dose_lock",
        "_enumerator",
        "_first_scan_complete",
        "_internal_loop_threads",
        "_is_running",
        "_last_dose_status",
        "_last_valid_inputs",
        "_last_volume_text_content",
        "_model_buffers_primed",
        "_refresh_pending",
        "_stop_threads_event",
        "_volume_calc_paused",
        "_volume_control",
        "_volume_interface_lock",
        "active_error_type",
        "audio_capture_worker",
        "audio_processor",
        "audio_retry_delay",
        "block_duration",
        "block_size",
        "daily_dose_consumed",
        "default_baseline_db",
        "default_baseline_lufs",
        "default_safety_buffer_entry",
        "default_target_spl_entry",
        "discard_duration_s",
        "dose_accumulation_spl_threshold",
        "dose_data",
        "error_queue",
        "gain_constant",
        "gui_theme",
        "hotkey_manager",
        "hotkey_modifiers",
        "hotkey_trigger",
        "integrated_window_s",
        "is_closing",
        "is_retrying_connection",
        "is_switching_devices",
        "max_gui_refresh_interval_s",
        "min_gui_refresh_interval_s",
        "momentary_window_s",
        "priming_duration_s",
        "restart_needed",
        "sample_rate",
        "short_term_window_s",
        "silence_threshold",
        "stable_window_s",
        "true_peak_expensive_computation",
        "ui",
        "ui_func_queue",
        "volume_decrease_tolerance_db",
        "volume_increase_tolerance_db",
        "warmup_duration_s",
        "was_restarted",
    )

    def __init__(self, *, ui: "UI | None", was_restarted: bool = False) -> None:
        if not config_manager.config:
            config_manager.load_config()
        if not persistence_manager.data:
            persistence_manager.load()

        self.was_restarted = was_restarted

        logger.info(
            "[__init__] Registering SIGINT handler for user interruption (Ctrl+C)."
        )
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info(
            "[__init__] Registering SIGTERM handler for programmatic termination."
        )
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._initialize_constants()
        self._initialize_persistant_variables()
        self._initialize_config_variables()
        self._initialize_buffers_and_state()

        if ui:
            self.set_up_ui(ui)

    def _initialize_constants(self) -> None:
        self.GUI_STABILITY_THRESHOLD_DB: float = AppConstants.GUI_STABILITY_THRESHOLD_DB
        self.HEARING_DAMAGE_DB_THRESHOLD: float = (
            AppConstants.HEARING_DAMAGE_DB_THRESHOLD
        )
        self.DANGEROUS_PEAK_DB_THRESHOLD: float = (
            AppConstants.DANGEROUS_PEAK_DB_THRESHOLD
        )
        self.VOLUME_CALCULATOR_RED_TOLERANCE_DB: float = (
            AppConstants.VOLUME_CALCULATOR_RED_TOLERANCE_DB
        )
        self.VOLUME_CALCULATOR_YELLOW_TOLERANCE_DB: float = (
            AppConstants.VOLUME_CALCULATOR_YELLOW_TOLERANCE_DB
        )
        self.ABS_GATE_LUFS: float = AppConstants.ABS_GATE_LUFS
        self.REL_GATE_LU: float = AppConstants.REL_GATE_LU
        self.DOSE_BASELINE_DB: float = AppConstants.DOSE_BASELINE_DB
        self.DOSE_BASELINE_HOURS: float = AppConstants.DOSE_BASELINE_HOURS
        self.DOSE_EXCHANGE_RATE_DB: float = AppConstants.DOSE_EXCHANGE_RATE_DB
        self.AUDIO_BUFFER_SECONDS: float = AppConstants.AUDIO_BUFFER_SECONDS
        self.DEFAULT_VOLUME_CORRECTION: bool = AppConstants.DEFAULT_VOLUME_CORRECTION

    def _initialize_persistant_variables(self) -> None:
        hotkeys = persistence_manager.data[PersistenceKeys.HOTKEYS]
        self.hotkey_modifiers = hotkeys[HotkeyInfoKeys.MODIFIERS]
        self.hotkey_trigger = hotkeys[HotkeyInfoKeys.TRIGGER]

    def _initialize_config_variables(self) -> None:
        self.audio_retry_delay = config_manager.get_from_config(
            ConfigKeys.AUDIO_RETRY_DELAY,
        )
        self.true_peak_expensive_computation = config_manager.get_from_config(
            ConfigKeys.TRUE_PEAK_EXPENSIVE,
        )
        self.block_duration = (
            config_manager.get_from_config(
                ConfigKeys.BLOCK_DURATION,
            )
            / 1000
        )
        self.sample_rate = config_manager.get_from_config(
            ConfigKeys.SAMPLE_RATE,
        )
        self.block_size = int(self.sample_rate * self.block_duration)
        self.silence_threshold = config_manager.get_from_config(
            ConfigKeys.SILENCE_THRESHOLD,
        )
        self.discard_duration_s = config_manager.get_from_config(
            ConfigKeys.DISCARD_DURATION,
        )
        self.priming_duration_s = config_manager.get_from_config(
            ConfigKeys.PRIMING_DURATION,
        )
        self.warmup_duration_s = self.discard_duration_s + self.priming_duration_s
        self.default_baseline_lufs = config_manager.get_from_config(
            ConfigKeys.DEFAULT_BASELINE_LUFS,
        )
        self.default_baseline_db = config_manager.get_from_config(
            ConfigKeys.DEFAULT_BASELINE_DB,
        )
        min_gui_refresh_interval_ms = config_manager.get_from_config(
            ConfigKeys.MIN_GUI_REFRESH,
        )
        self.min_gui_refresh_interval_s = min_gui_refresh_interval_ms / 1000
        max_gui_refresh_interval_ms = config_manager.get_from_config(
            ConfigKeys.MAX_GUI_REFRESH,
        )
        self.max_gui_refresh_interval_s = max_gui_refresh_interval_ms / 1000
        self.default_target_spl_entry = config_manager.get_from_config(
            ConfigKeys.DEFAULT_TARGET_SPL,
        )
        self.default_safety_buffer_entry = config_manager.get_from_config(
            ConfigKeys.DEFAULT_SAFETY_BUFFER,
        )
        self.volume_decrease_tolerance_db = config_manager.get_from_config(
            ConfigKeys.VOL_DEC_TOLERANCE,
        )
        self.volume_increase_tolerance_db = config_manager.get_from_config(
            ConfigKeys.VOL_INC_TOLERANCE,
        )
        self.dose_accumulation_spl_threshold = config_manager.get_from_config(
            ConfigKeys.DOSE_ACCUM_THRESHOLD,
        )
        self.momentary_window_s = config_manager.get_from_config(
            ConfigKeys.MOMENTARY_WINDOW
        )
        self.short_term_window_s = config_manager.get_from_config(
            ConfigKeys.SHORT_TERM_WINDOW
        )
        self.stable_window_s = config_manager.get_from_config(
            ConfigKeys.CURRENT_SPL_WINDOW
        )
        self.integrated_window_s = config_manager.get_from_config(
            ConfigKeys.INTEGRATED_WINDOW
        )

    def _initialize_buffers_and_state(self) -> None:
        self.ui_func_queue: queue.Queue[Callable[[], None]] = queue.Queue()

        self.gui_theme = GUITheme(config_manager)
        self._last_volume_text_content = None

        self.audio_capture_worker: AudioCaptureWorker | None = None
        self.audio_processor: AudioProcessor | None = None
        self._current_loaded_device: str | None = None

        self._is_running = True
        self.is_closing = False
        self.restart_needed = False
        self._first_scan_complete = False
        self._refresh_pending = False
        self.is_retrying_connection = False
        self.is_switching_devices = False
        self._volume_calc_paused = False

        self._are_baselines_valid = False
        self._are_targets_valid = False
        self._last_valid_inputs: dict[UserEntriesEnum, float] = {}
        self.gain_constant = -inf
        self._last_dose_status: DoseStatusType | None = None

        self.error_queue: queue.Queue[
            AudioCaptureErrorEvent | AudioCaptureStatusEvent | None
        ] = queue.Queue()
        self.active_error_type: AudioCaptureErrorEvent | None = None

        self._volume_interface_lock = threading.Lock()
        self._dose_lock = threading.Lock()
        self._model_buffers_primed = threading.Event()
        self._stop_threads_event = threading.Event()

        self._set_up_dose()
        self._start_device_notif_client()
        self._volume_control = SystemVolumeControl(
            vol_refresh_callback=self.refresh_volume_control,
        )

    def set_up_ui(self, ui: "UI") -> None:
        self.ui = ui

        self._set_up_view()
        self.update_device_list()

        self.hotkey_manager = HotkeyManager(
            self.ui.get_window_handle(), self.handle_hotkey
        )
        mods_enum_list = [HotkeyModifiers(s) for s in self.hotkey_modifiers]
        if self.register_hotkey(True, mods_enum_list, self.hotkey_trigger):
            self.ui.set_hotkey(mods_enum_list, self.hotkey_trigger)

        self._start_internal_loops()

    def handle_hotkey(self) -> None:
        self.ui.toggle_overlay()

    def _set_up_view(self) -> None:
        self.ui.register_func_queue(self.ui_func_queue)
        self.ui.register_on_closing(lambda: self.shutdown("UI closed"))

        self._bind_view_callbacks()

        self.ui.set_user_inputs(
            {
                UserEntriesEnum.TARGET_DB: self.default_target_spl_entry,
                UserEntriesEnum.SAFETY_BUFFER_DB: self.default_safety_buffer_entry,
            }
        )

        self.ui.show()

        if not self.was_restarted:
            self.ui.bring_window_to_front()

    def _bind_view_callbacks(self) -> None:
        """Connects controller methods to the view's handlers."""
        self.ui.reset_metrics_handler = self.prompt_reset_metrics
        self.ui.reset_dose_handler = self.prompt_reset_dose
        self.ui.device_change_handler = self.on_device_change
        self.ui.refresh_devices_handler = self.update_device_list
        self.ui.save_profile_handler = self.save_profile
        self.ui.baseline_change_handler = self.on_baseline_change
        self.ui.vol_checkbox_handler = self.vol_checkbox_change
        self.ui.restore_last_valid_handler = self.restore_last_valid

        def register_hotkey_wrapper(
            register: bool,
            mods: list[HotkeyModifiers] | None,
            trigger_key_str: str | None,
        ) -> None:
            self.register_hotkey(register, mods, trigger_key_str)

        self.ui.register_hotkey_handler = register_hotkey_wrapper

    def _start_internal_loops(self) -> None:
        self._internal_loop_threads = []
        thread_defs = (
            self._dose_management_loop,
            self._update_gui_loop,
            self._process_event_queue,
        )

        for target_func in thread_defs:
            thread = threading.Thread(target=target_func, daemon=True)
            self._internal_loop_threads.append(thread)
            thread.start()

        threading.Thread(target=self._schedule_restart, daemon=True).start()

    def _schedule_restart(self) -> None:
        """Schedules the application to restart itself after a configured interval."""
        restart_interval_hours = config_manager.get_from_config(
            ConfigKeys.RESTART_INTERVAL
        )
        s_in_hour = 60 * 60
        restart_interval_s = restart_interval_hours * s_in_hour
        logger.info(
            f"[_schedule_restart] Application will automatically restart in {restart_interval_s / s_in_hour:.2f} hours."
        )
        time.sleep(restart_interval_s)
        self._initiate_restart()

    def _initiate_restart(self) -> None:
        """Flags the app for restart and begins the graceful shutdown process."""
        if self.is_closing:
            return
        logger.info(
            "[_initiate_restart] Scheduled restart triggered. Initiating graceful shutdown."
        )
        self.restart_needed = True
        self.shutdown("Auto-Restarting")

    def _start_device_notif_client(self) -> None:
        self._device_notification_client = DefaultDeviceNotification(
            default_device_change_handler=self.default_device_changed,
        )

        try:
            self._enumerator = AudioUtilities.GetDeviceEnumerator()
            self._enumerator.RegisterEndpointNotificationCallback(
                self._device_notification_client
            )
            logger.info(
                "[start_device_notif_client] Successfully registered for default device notifications."
            )
        except Exception as e:
            logger.error(
                f"[start_device_notif_client] Failed to register notification callback: {e}"
            )

    def acknowledge_error_from_dialog(self) -> None:
        """Callback function for when the user clicks OK on a dialog."""
        logger.info(
            f"[acknowledge_error_from_dialog] Error '{self.active_error_type}' acknowledged by user."
        )

        if (
            self.active_error_type is not None
            and self.active_error_type.error_type
            == ErrorType.CONNECTION_LOST_RETRY_FAILED
        ):
            logger.info(
                "[acknowledge_error_from_dialog][DEVICE_NOT_FOUND] Clearing all application notifications."
            )
            self.ui.clear_notifications()
            self.update_device_list()

    def _validate_and_update_state(self) -> VolCalcErrorEvent | None:
        """
        Reads all inputs from the view, validates them,
        and updates the controller's internal state.
        """
        user_input_values = self.ui.get_user_inputs().entries_data
        try:
            baseline_db = user_input_values[UserEntriesEnum.BASELINE_DB]
            baseline_lufs = user_input_values[UserEntriesEnum.BASELINE_LUFS]

            if baseline_db is None or baseline_lufs is None:
                raise TypeError("Baseline dB or Baseline LUFS is invalid.")

            self.gain_constant = baseline_db - baseline_lufs
            self._are_baselines_valid = True
            self._last_valid_inputs[UserEntriesEnum.BASELINE_DB] = baseline_db
            self._last_valid_inputs[UserEntriesEnum.BASELINE_LUFS] = baseline_lufs

        except (ValueError, TypeError):
            self.gain_constant = -inf
            self._are_baselines_valid = False
            return VolCalcErrorEvent(error_type=ErrorType.ENTRY_BASELINE)

        try:
            target_spl = user_input_values[UserEntriesEnum.TARGET_DB]
            safety_buffer = user_input_values[UserEntriesEnum.SAFETY_BUFFER_DB]

            if target_spl is None or safety_buffer is None:
                raise TypeError("Target SPL or Safety Buffer is invalid.")

            self._are_targets_valid = True
            self._last_valid_inputs[UserEntriesEnum.TARGET_DB] = target_spl
            self._last_valid_inputs[UserEntriesEnum.SAFETY_BUFFER_DB] = safety_buffer

        except (ValueError, TypeError):
            self._are_targets_valid = False
            return VolCalcErrorEvent(error_type=ErrorType.ENTRY_TARGET)

        return None

    def on_baseline_change(self) -> None:
        """Handles a committed user input change."""
        if not self._is_running:
            return
        error = self._validate_and_update_state()
        if error:
            self._render_vol_blocking(error)

    def _render_vol_blocking(
        self, state: Calibrating | VolCalcStatusEvent | VolCalcErrorEvent
    ) -> None:
        self._volume_calc_paused = True
        self._put_in_ui_func_queue(
            lambda: self.ui.render_volume_calculator_state(state)
        )

    def restore_last_valid(self, entry: UserEntriesEnum) -> None:
        if not self._is_running:
            return
        self.ui.set_user_inputs({entry: self._last_valid_inputs[entry]})
        self.on_baseline_change()

    def vol_checkbox_change(self) -> None:
        """Called when the volume checkbox changes. Currently a stub."""
        # if not self.is_running: return

    def _init_new_audio_worker(self, device_name: str) -> None:
        if self.audio_capture_worker:
            self.audio_capture_worker.stop()

        if self.audio_processor is None:
            raise RuntimeError("Audio processor should have been initialized.")

        logger.info(
            f"[_init_new_audio_worker] Starting new audio capture worker for device: '{device_name}'."
        )
        self.audio_capture_worker = AudioCaptureWorker(
            self.audio_processor.shared_audio_buffer,
            self.error_queue,
            device_name,
            self.sample_rate,
            self.block_size,
            self.audio_retry_delay,
        )

    def _init_new_model(self, dose_consumed: float) -> None:
        if self.audio_processor:
            self.audio_processor.stop_process_audio_loop()

        logger.info("[_init_new_model] Starting new audio processor.")
        audio_processor_config = AudioProcessorConfig(
            sample_rate=self.sample_rate,
            block_size=self.block_size,
            block_duration=self.block_duration,
            discard_duration_s=self.discard_duration_s,
            priming_duration_s=self.priming_duration_s,
            momentary_window_s=self.momentary_window_s,
            short_term_window_s=self.short_term_window_s,
            stable_window_s=self.stable_window_s,
            integrated_window_s=self.integrated_window_s,
            true_peak_expensive_computation=self.true_peak_expensive_computation,
            silence_threshold=self.silence_threshold,
            abs_gate_lufs=self.ABS_GATE_LUFS,
            rel_gate_lu=self.REL_GATE_LU,
            dose_baseline_db=self.DOSE_BASELINE_DB,
            dose_baseline_hours=self.DOSE_BASELINE_HOURS,
            dose_exchange_rate_db=self.DOSE_EXCHANGE_RATE_DB,
            audio_buffer_seconds=self.AUDIO_BUFFER_SECONDS,
        )
        self.audio_processor = AudioProcessor(
            audio_processor_config=audio_processor_config,
            daily_dose_consumed=dose_consumed,
        )

    def _reset_metrics(self) -> None:
        if not self._is_running or self.active_error_type:
            return

        if self.audio_processor is None:
            raise RuntimeError("Audio processor should have been initialized.")

        self.audio_processor.reset_metrics()
        persistence_manager.save()
        self._model_buffers_primed.clear()
        logger.info("[reset_metrics] Metrics Reset")

    def conditionally_reset_metrics(self, reset: bool | None = False) -> None:
        if reset is True:
            self._reset_metrics()

    def prompt_reset_metrics(self) -> None:
        self.ui.show_dialog(
            Ack(AckType.RESET_METRICS), self.conditionally_reset_metrics
        )

    def _set_up_dose(self) -> None:
        self.daily_dose_consumed = 0.0
        self.dose_data: DoseData = {}
        self._load_dose()

    def _dose_management_loop(self) -> None:
        while not self._stop_threads_event.is_set():
            if self.active_error_type:
                self._stop_threads_event.wait(timeout=600)
                continue

            recently_saved = False
            if not self.dose_data:
                self._save_dose()
                recently_saved = True

            reset_datetime_str = self.dose_data.get("reset_datetime")
            reset_dt = (
                datetime.fromisoformat(reset_datetime_str)
                if reset_datetime_str
                else None
            )
            current_dt = datetime.now()

            reset_dose_required = False
            if reset_dt is None:
                logger.info("[dose_management_loop] Missing reset_datetime key.")
                reset_dose_required = True
            elif current_dt >= reset_dt:
                reset_dose_required = True
            elif not isfinite(self.daily_dose_consumed):
                self._sanitize_dose()

            if reset_dose_required:
                logger.info("[dose_management_loop] Resetting Dose.")
                self._reset_dose()
            elif not recently_saved:
                self._save_dose()

            self._stop_threads_event.wait(timeout=600)

    def _sanitize_dose(self) -> None:
        if not self._is_running:
            return
        with self._dose_lock:
            if self.audio_processor:
                model_reported_dose = self.audio_processor.daily_dose_consumed
                if isfinite(model_reported_dose):
                    self.daily_dose_consumed = model_reported_dose
                else:
                    self.daily_dose_consumed = 0.0
                    self.audio_processor.reset_dose()
            else:
                self.daily_dose_consumed = 0.0

    def _reset_dose(self) -> None:
        if not self._is_running or self.active_error_type:
            return
        with self._dose_lock:
            self.daily_dose_consumed = 0.0
        self._save_dose(reset_trigger=True)
        if self.audio_processor:
            self.audio_processor.reset_dose()

    def conditionally_reset_dose(self, reset: bool | None = False) -> None:
        if reset is True:
            self._reset_dose()

    def prompt_reset_dose(self) -> None:
        self.ui.show_dialog(Ack(AckType.RESET_DOSE), self.conditionally_reset_dose)

    def _load_dose(self) -> None:
        if os.path.exists(paths.DOSE_FILE):
            try:
                with open(paths.DOSE_FILE, "r") as f:
                    data: DoseData = json.load(f)
                daily_dose = data.get("dose")
                if daily_dose is not None:
                    self.dose_data = data
                    self.daily_dose_consumed = daily_dose
                    logger.info(
                        f"[load_dose] Loaded previous dose: {self.daily_dose_consumed:.2f}%"
                    )
                else:
                    logger.info("[load_dose] daily_dose is None, Resetting dose...")
                    self._reset_dose()
            except Exception:
                logger.exception(
                    "[load_dose] Exception while reading dose file, Resetting dose..."
                )
                self._reset_dose()
        else:
            logger.warning("[load_dose] Dose file does not exist, Resetting dose...")
            self._reset_dose()

    def _save_dose(self, reset_trigger: bool = False) -> None:
        if not self._is_running:
            return
        if not isfinite(self.daily_dose_consumed):
            self._sanitize_dose()
        data = self.dose_data
        if not data:
            os.makedirs(os.path.dirname(paths.DOSE_FILE), exist_ok=True)
            data = {
                "save_datetime": datetime.now().isoformat(timespec="seconds"),
                "dose": 0.0,
                "reset_datetime": (datetime.now() + timedelta(hours=24)).isoformat(
                    timespec="seconds"
                ),
            }
        else:
            if reset_trigger or self.daily_dose_consumed == 0.0:
                data.update(
                    {
                        "save_datetime": datetime.now().isoformat(timespec="seconds"),
                        "dose": 0.0,
                        "reset_datetime": (
                            datetime.now() + timedelta(hours=24)
                        ).isoformat(timespec="seconds"),
                    }
                )
            else:
                data.update(
                    {
                        "save_datetime": datetime.now().isoformat(timespec="seconds"),
                        "dose": self.daily_dose_consumed,
                    }
                )
        with self._dose_lock:
            self.dose_data = data
        with open(paths.DOSE_FILE, "w") as f:
            json.dump(data, f)
        logger.info("[save_dose] Dose saved.")

    def _scan_for_devices_thread(self) -> None:
        """
        Performs the slow device scan in a background thread.

        **Note:**
        CoUninitialize is intentionally not called here.
        COM objects might still exist as Python GC is non-deterministic;
        could cause vtable crashes.
        Leaving COM initialized for this thread is safe;
        OS will clean up when the thread terminates.
        """
        CoInitializeEx(COINIT_MULTITHREADED)
        if not self._is_running:
            return
        try:
            speakers = sc.all_speakers()
            microphones = sc.all_microphones(include_loopback=True)

            excluded_terms = ("mic", "microphone", "webcam")
            filtered_mics = [
                mic
                for mic in microphones
                if not any(term in mic.name.lower() for term in excluded_terms)
            ]

            found_devices = {dev.name for dev in (*speakers, *filtered_mics)}
            device_list = sorted(found_devices)

            logger.info(
                f"[_scan_for_devices_thread] Scan complete. Found {len(device_list)} devices."
            )
            self._put_in_ui_func_queue(
                lambda: self.on_device_scan_complete(device_list)
            )

        except Exception:
            logger.exception("[_scan_for_devices_thread] Error getting devices.")
            self._put_in_ui_func_queue(lambda: self.on_device_scan_complete([]))

    def on_device_scan_complete(self, device_list: list[str]) -> None:
        """
        Called on the main thread after the device scan is complete.
        Updates the dropdown and handles the initial application startup.
        """
        if not self._is_running:
            return

        logger.info("[_on_device_scan_complete] Populating device list in the GUI.")
        self.ui.exit_scanning_state()
        target_device = self._current_loaded_device
        self.ui.update_devices(device_list, target_device)

        if not self._first_scan_complete:
            self._first_scan_complete = True
            speaker = AudioUtilities.GetSpeakers()
            if speaker is not None:
                target_device = str(speaker.FriendlyName)
                self.on_device_change(target_device)

        elif (
            self.active_error_type is not None
            and self.active_error_type.error_type
            == ErrorType.CONNECTION_LOST_RETRY_FAILED
        ):
            logger.info("Device scan complete during error recovery.")
            current_selection = self.ui.get_target_device()

            if (current_selection) and (current_selection in device_list):
                logger.info(
                    f"Attempting to automatically reconnect to '{current_selection}'."
                )
                self.on_device_change(current_selection)
            else:
                logger.warning(
                    "Previous device not found after rescan. Awaiting user selection."
                )
                self._render_vol_blocking(
                    VolCalcErrorEvent(error_type=ErrorType.AUDIO_DEVICE_UNAVAILABLE)
                )

    def update_device_list(self) -> None:
        """
        Updates the audio device list in a background thread.
        """
        if not self._is_running:
            return
        self.ui.enter_scanning_state()
        self._render_vol_blocking(
            VolCalcStatusEvent(status_type=StatusType.SCANNING_DEVICES)
        )

        scan_thread = threading.Thread(
            target=self._scan_for_devices_thread, daemon=True
        )
        scan_thread.start()

    def register_hotkey(
        self,
        register: bool,
        mods: list[HotkeyModifiers] | None,
        trigger_key_str: str | None,
    ) -> bool:
        if register:
            if not mods or not trigger_key_str:
                self.hotkey_manager.unregister()
                self.ui.set_hotkey(None, None)
                return False
            trigger_key_str = trigger_key_str.upper()
            if self.hotkey_manager.register(mods, trigger_key_str):
                self.hotkey_modifiers = [m.value for m in mods]
                self.hotkey_trigger = trigger_key_str
                hotkey_data = persistence_manager.data[PersistenceKeys.HOTKEYS]
                hotkey_data[HotkeyInfoKeys.MODIFIERS] = self.hotkey_modifiers
                hotkey_data[HotkeyInfoKeys.TRIGGER] = self.hotkey_trigger
                persistence_manager.save()
                return True
            else:
                self.ui.set_hotkey(None, None)
                return False
        elif self.hotkey_manager.unregister():
            self.ui.set_hotkey(None, None)
            return True
        else:
            return False

    def save_profile(
        self,
        _show_dialog: bool = True,
        device_name_override: str | None = None,
    ) -> None:
        if self.active_error_type or not self._is_running:
            return

        user_inputs = self.ui.get_user_inputs()

        input_values = user_inputs.entries_data
        target_device = (
            device_name_override if device_name_override else user_inputs.target_device
        )

        if not target_device:
            logger.warning(
                "[save_profile] Cannot save profile for an empty device name."
            )
            return

        baseline_db = input_values[UserEntriesEnum.BASELINE_DB]
        if baseline_db is None:
            baseline_db = self._last_valid_inputs.get(
                UserEntriesEnum.BASELINE_DB, self.default_baseline_db
            )
            logger.warning(
                "[save_profile] Baseline dB was invalid; saved using the last known valid or default value."
            )
        baseline_lufs = input_values[UserEntriesEnum.BASELINE_LUFS]
        if baseline_lufs is None:
            baseline_lufs = self._last_valid_inputs.get(
                UserEntriesEnum.BASELINE_LUFS, self.default_baseline_lufs
            )
            logger.warning(
                "[save_profile] Baseline LUFS were invalid; saved using the last known valid or default value."
            )

        persistence_manager.set_profile(
            target_device,
            ProfileInfo(
                {
                    ProfileInfoKeys.BASELINE_DB.value: baseline_db,
                    ProfileInfoKeys.BASELINE_LUFS.value: baseline_lufs,
                    ProfileInfoKeys.VOLUME_CORRECTION.value: self.ui.get_vol_check_box_bool(),
                }
            ),
        )

        if persistence_manager.save():
            logger.info(f"[save_profile] Profile for {target_device} saved.")
            self._save_dose()
            if _show_dialog:
                self.ui.show_dialog(
                    DialogStatusEvent(
                        device_name=target_device,
                        status_type=StatusType.SAVE_SUCCESSFUL,
                    )
                )

    def _set_volume_correction(self, is_enabled: bool) -> None:
        """Helper to set volume correction and trigger its logic."""
        self.ui.set_volume_correction(is_enabled)
        self.vol_checkbox_change()

    def _load_device_profile(self, device_name: str) -> None:
        profile = persistence_manager.get_profile(device_name)
        if not profile:
            baseline_db = self.default_baseline_db
            baseline_lufs = self.default_baseline_lufs
            volume_correction = self.DEFAULT_VOLUME_CORRECTION
        else:
            baseline_db = profile.get(
                ProfileInfoKeys.BASELINE_DB,
                self.default_baseline_db,
            )
            baseline_lufs = profile.get(
                ProfileInfoKeys.BASELINE_LUFS,
                self.default_baseline_lufs,
            )
            volume_correction = profile.get(
                ProfileInfoKeys.VOLUME_CORRECTION,
                self.DEFAULT_VOLUME_CORRECTION,
            )

        target_spl: float = self._last_valid_inputs.get(
            UserEntriesEnum.TARGET_DB, self.default_target_spl_entry
        )
        safety_buffer: float = self._last_valid_inputs.get(
            UserEntriesEnum.SAFETY_BUFFER_DB, self.default_safety_buffer_entry
        )

        current_user_input_values = self.ui.get_user_inputs().entries_data

        if (val := current_user_input_values[UserEntriesEnum.TARGET_DB]) is not None:
            target_spl = val

        if (
            val := current_user_input_values[UserEntriesEnum.SAFETY_BUFFER_DB]
        ) is not None:
            safety_buffer = val

        self.ui.set_user_inputs(
            {
                UserEntriesEnum.TARGET_DB: target_spl,
                UserEntriesEnum.SAFETY_BUFFER_DB: safety_buffer,
                UserEntriesEnum.BASELINE_DB: baseline_db,
                UserEntriesEnum.BASELINE_LUFS: baseline_lufs,
            }
        )
        self._set_volume_correction(volume_correction)
        self.on_baseline_change()
        logger.info(f"[load_device_profile] Profile loaded for {device_name}")

    def on_device_change(self, new_device: str) -> None:
        if not new_device or (
            not self.is_retrying_connection
            and self.audio_capture_worker
            and self.audio_capture_worker.device_name == new_device
        ):
            return

        if not self._is_running or self.is_switching_devices:
            return
        if (
            self.active_error_type
            and self.active_error_type.error_type
            != ErrorType.CONNECTION_LOST_RETRY_FAILED
        ):
            return

        try:
            self.is_switching_devices = True

            old_device = self._current_loaded_device
            if old_device:
                self.save_profile(_show_dialog=False, device_name_override=old_device)

            if self.is_retrying_connection:
                self.ui.clear_notifications()
                self.is_retrying_connection = False

            if (
                self.active_error_type is not None
                and self.active_error_type.error_type
                == ErrorType.CONNECTION_LOST_RETRY_FAILED
            ):
                self.ui.clear_notifications()
                self.active_error_type = None

            self.ui.select_device(new_device)
            self._load_device_profile(new_device)
            self._current_loaded_device = new_device

            self.ui.enter_scanning_state()
            self._render_vol_blocking(
                VolCalcStatusEvent(status_type=StatusType.CHANGING_DEVICE)
            )

            if self.audio_capture_worker:
                self.audio_capture_worker.stop()

            if self.audio_processor:
                self.audio_processor.stop_process_audio_loop()

            if persistence_manager.save():
                logger.info(
                    f"[on_device_change] Switched to and saved '{new_device}' as the target device."
                )
            else:
                self.ui.show_dialog(
                    DialogErrorEvent(
                        device_name=new_device,
                        error_type=ErrorType.SAVE_FAILED,
                    )
                )

            persisted_dose = (
                self.audio_processor.daily_dose_consumed
                if self.audio_processor
                else 0.0
            )
            self._init_new_model(persisted_dose)
            self._init_new_audio_worker(new_device)

            if self.audio_processor is None:
                raise RuntimeError("Audio processor should have been initialized.")

            if self.audio_capture_worker is None:
                raise RuntimeError("Audio capture worker should have been initialized.")

            self.audio_processor.start_process_audio_loop()
            self.audio_capture_worker.start()
            self.ui.exit_scanning_state()
            self._render_vol_blocking(Calibrating(self.warmup_duration_s))

        finally:
            self.is_switching_devices = False

    def _process_event_queue(self) -> None:
        has_sent_retry_notification = False
        while not self._stop_threads_event.is_set():
            if self.active_error_type:
                self._stop_threads_event.wait(timeout=0.2)
                continue

            event = self.error_queue.get()
            match event:
                case None:
                    break

                case AudioCaptureErrorEvent(
                    device_name=device_name,
                    attempt_str=attempt_str,
                    error_type=error_type,
                ):
                    match error_type:
                        case ErrorType.CONNECTION_LOST_RETRYING:
                            self.is_retrying_connection = True
                            self._render_vol_blocking(
                                VolCalcErrorEvent(
                                    device_name=device_name,
                                    attempt_str=attempt_str,
                                    error_type=error_type,
                                )
                            )
                            if not has_sent_retry_notification:
                                logger.info(
                                    "[process_event_queue][CONNECTION_LOST_RETRYING] Sending persistent OS notification for connection loss - Retrying."
                                )
                                self._put_in_ui_func_queue(
                                    partial(
                                        self.ui.send_notification,
                                        NotifErrorEvent(
                                            device_name=device_name,
                                            attempt_str=attempt_str,
                                            error_type=error_type,
                                        ),
                                        self.ui.bring_window_to_front,
                                    )
                                )
                                has_sent_retry_notification = True

                        case ErrorType.CONNECTION_LOST_RETRY_FAILED:
                            self.active_error_type = event
                            self._render_vol_blocking(
                                VolCalcErrorEvent(
                                    device_name=device_name,
                                    attempt_str=attempt_str,
                                    error_type=error_type,
                                )
                            )
                            logger.info(
                                "[process_event_queue][CONNECTION_LOST_RETRY_FAILED] Sending persistent OS notification for connection loss - Retry Failed."
                            )
                            self._put_in_ui_func_queue(
                                partial(
                                    self.ui.send_notification,
                                    NotifErrorEvent(
                                        device_name=device_name,
                                        attempt_str=attempt_str,
                                        error_type=error_type,
                                    ),
                                    self.ui.bring_window_to_front,
                                )
                            )
                            self._put_in_ui_func_queue(
                                partial(
                                    self.ui.show_dialog,
                                    DialogErrorEvent(
                                        device_name=device_name,
                                        attempt_str=attempt_str,
                                        error_type=error_type,
                                    ),
                                    lambda _: self.acknowledge_error_from_dialog(),
                                )
                            )

                        case _:
                            assert_never(error_type)

                case AudioCaptureStatusEvent(
                    device_name=device_name,
                    attempt_str=attempt_str,
                    status_type=status_type,
                ):
                    match status_type:
                        case StatusType.DEVICE_RECONNECTED:
                            self.is_retrying_connection = False
                            has_sent_retry_notification = False
                            logger.info(
                                "[process_event_queue][DEVICE_RECONNECTED] Sending OS notification for successful reconnection"
                            )
                            self._put_in_ui_func_queue(
                                partial(
                                    self.ui.send_notification,
                                    NotifStatusEvent(
                                        device_name=device_name,
                                        attempt_str=attempt_str,
                                        status_type=status_type,
                                    ),
                                )
                            )

                        case _:
                            assert_never(status_type)

                case _:
                    assert_never(event)

    def _put_in_ui_func_queue(self, func: Callable[[], None]) -> None:
        if self._is_running and self.ui:

            def wrapper() -> None:
                if self.ui:
                    func()

            self.ui_func_queue.put(wrapper)

    @staticmethod
    def _safe_diff(a: float, b: float) -> float:
        if a == b:
            return 0.0
        return abs(a - b) if isfinite(a) and isfinite(b) else inf

    def _update_gui_loop(self) -> None:
        _gui_last_values = None
        _gui_refresh_interval_s = self.min_gui_refresh_interval_s
        while not self._stop_threads_event.is_set():
            if (
                self.is_retrying_connection
                or self.is_switching_devices
                or self.active_error_type
            ):
                self._stop_threads_event.wait(timeout=self.max_gui_refresh_interval_s)
                continue

            volume_linear_gain = None

            if self.ui and self.ui.get_vol_check_box_bool():
                with self._volume_interface_lock:
                    if self._volume_control:
                        volume_linear_gain = self._volume_control.get_linear_gain()

            if self.audio_processor:
                vals = self.audio_processor.get_lufs_values(
                    volume_linear_gain_override=volume_linear_gain
                )
            else:
                vals = None

            if vals is None:
                self._stop_threads_event.wait(timeout=self.max_gui_refresh_interval_s)
                continue

            if vals["buffers_primed"]:
                self._model_buffers_primed.set()
            else:
                self._model_buffers_primed.clear()

            dbs_array = []
            baselines_valid = self._are_baselines_valid
            gain_constant = self.gain_constant

            if baselines_valid:
                keys: tuple[
                    Literal["integrated"],
                    Literal["short_term"],
                    Literal["momentary"],
                    Literal["peak"],
                ] = (
                    "integrated",
                    "short_term",
                    "momentary",
                    "peak",
                )
                dbs_array = [
                    ((vals[k] + gain_constant) if isfinite(vals[k]) else -inf)
                    for k in keys
                ]
            else:
                dbs_array = [-inf] * 4

            loudness_dbs: dict[
                Literal["integrated_db", "short_term_db", "momentary_db"],
                float,
            ] = {
                "integrated_db": dbs_array[0],
                "short_term_db": dbs_array[1],
                "momentary_db": dbs_array[2],
            }

            formatted_loudness_metrics: dict[
                Literal["integrated_db", "short_term_db", "momentary_db"],
                AudioMetric,
            ] = {}
            HEARING_DAMAGE_DB_THRESHOLD = self.HEARING_DAMAGE_DB_THRESHOLD
            for metric, db in loudness_dbs.items():
                value_str = "---" if db == -inf else f"{db:.2f}"
                spl_lvl = (
                    SplLvl.WARNING if db > HEARING_DAMAGE_DB_THRESHOLD else SplLvl.SAFE
                )
                formatted_loudness_metrics[metric] = {
                    "value_str": value_str,
                    "spl_lvl": spl_lvl,
                }

            peak_db = dbs_array[3]
            peak_spl_lvl = (
                SplLvl.DANGER
                if peak_db >= self.DANGEROUS_PEAK_DB_THRESHOLD
                else (
                    SplLvl.WARNING
                    if peak_db > gain_constant and baselines_valid
                    else SplLvl.SAFE
                )
            )

            stable_val = vals["stable"]

            self._put_in_ui_func_queue(
                partial(
                    self.ui.update_audio_metrics,
                    {
                        "integrated_db": formatted_loudness_metrics["integrated_db"],
                        "short_term_db": formatted_loudness_metrics["short_term_db"],
                        "momentary_db": formatted_loudness_metrics["momentary_db"],
                        "peak_db": {
                            "value_str": "---" if peak_db == -inf else f"{peak_db:.2f}",
                            "spl_lvl": peak_spl_lvl,
                        },
                        "current_stable_lufs": {
                            "value_str": "---"
                            if stable_val == -inf
                            else f"{stable_val:.2f}",
                            "spl_lvl": SplLvl.SAFE,
                        },
                    },
                )
            )

            self._update_volume_calculator(stable_val)
            self._update_dose_calculator(stable_val)

            diff_array = dbs_array
            diff_array.append(stable_val)
            if _gui_last_values is not None:
                max_diff = max(
                    self._safe_diff(a, b) for a, b in zip(diff_array, _gui_last_values)
                )
                if max_diff < self.GUI_STABILITY_THRESHOLD_DB:
                    _gui_refresh_interval_s = min(
                        self.max_gui_refresh_interval_s,
                        _gui_refresh_interval_s + self.min_gui_refresh_interval_s,
                    )
                else:
                    _gui_refresh_interval_s = self.min_gui_refresh_interval_s

            _gui_last_values = diff_array

            self._put_in_ui_func_queue(
                partial(self.ui.update_gui_refresh_interval, _gui_refresh_interval_s)
            )
            self._stop_threads_event.wait(timeout=_gui_refresh_interval_s)

    def _update_volume_calculator(self, current_lufs: float) -> None:
        if (
            self.active_error_type
            or self.is_switching_devices
            or self.is_retrying_connection
            or not self._are_baselines_valid
            or not self._are_targets_valid
        ):
            self._volume_calc_paused = True
            return

        self._volume_calc_paused = False
        state: Calibrating | VolCalcStatusEvent | VolCalcStatus

        if not self._model_buffers_primed.is_set():
            state = Calibrating(self.warmup_duration_s)
        elif not isfinite(current_lufs):
            state = VolCalcStatusEvent(status_type=StatusType.WAITING_AUDIO)
        else:
            inputs = self._last_valid_inputs
            current_spl_estimate = (
                current_lufs
                + self.gain_constant
                + inputs[UserEntriesEnum.SAFETY_BUFFER_DB]
            )
            target_lufs = (
                inputs[UserEntriesEnum.TARGET_DB]
                - inputs[UserEntriesEnum.SAFETY_BUFFER_DB]
            ) - self.gain_constant
            required_lufs_change = target_lufs - current_lufs

            if current_spl_estimate >= self.DANGEROUS_PEAK_DB_THRESHOLD:
                spl_level = SplLvl.DANGER
            elif current_lufs > target_lufs + self.volume_decrease_tolerance_db:
                spl_level = SplLvl.WARNING
            else:
                spl_level = SplLvl.SAFE

            if (
                -self.volume_decrease_tolerance_db
                <= required_lufs_change
                < self.volume_increase_tolerance_db
            ):
                volume_level = VolLvl.CORRECT
            elif required_lufs_change >= self.volume_increase_tolerance_db:
                volume_level = VolLvl.INCREASE
            else:
                volume_level = VolLvl.DECREASE

            state = VolCalcStatus(
                current_spl=current_spl_estimate,
                required_change=required_lufs_change,
                spl_level=spl_level,
                volume_level=volume_level,
            )
        self._put_in_ui_func_queue(
            lambda: (
                self.ui.render_volume_calculator_state(state)
                if self._volume_calc_paused is False
                else None
            )
        )

    def _update_dose_calculator(self, stable_lufs: float) -> None:
        if self.active_error_type:
            return

        if self.audio_processor:
            dose_data = self.audio_processor.update_and_get_dose_data(
                stable_lufs,
                self.gain_constant,
                self.dose_accumulation_spl_threshold,
            )
        else:
            dose_data = None

        if dose_data is None:
            return

        with self._dose_lock:
            self.daily_dose_consumed = dose_data["daily_dose_consumed"]
        if not isfinite(self.daily_dose_consumed):
            self._sanitize_dose()

        if self.daily_dose_consumed >= 100.0:
            dose_status = DoseStatusType.EXCEEDED
        elif self.daily_dose_consumed >= 90.0:
            dose_status = DoseStatusType.DANGER
        elif self.daily_dose_consumed >= 75.0:
            dose_status = DoseStatusType.WARNING
        else:
            dose_status = DoseStatusType.SAFE

        status = DoseStatus(
            dose_status=dose_status,
            daily_dose_consumed=self.daily_dose_consumed,
            time_to_fill_str=dose_data["time_to_fill_str"],
        )

        if dose_status not in (
            self._last_dose_status,
            DoseStatusType.SAFE,
        ):
            self._last_dose_status = dose_status
            self._put_in_ui_func_queue(lambda: self.ui.send_notification(status))

        self._put_in_ui_func_queue(lambda: self.ui.render_dose_meter_state(status))

    def default_device_changed(self, new_device_name: str) -> None:
        self.on_device_change(new_device_name)
        self.refresh_volume_control()

    def refresh_volume_control(self) -> None:
        """
        Orders the volume control to refresh
        """
        with self._volume_interface_lock:
            if self._volume_control:
                logger.info("[do_refresh] Ordering VolumeControl to refresh.")
                self._volume_control.refresh()

    def _shutdown_device_notif_client(self) -> None:
        logger.info(
            "[shutdown_device_notif_client] Shutting down Device Notification Client..."
        )
        if self._enumerator and self._device_notification_client:
            try:
                self._enumerator.UnregisterEndpointNotificationCallback(
                    self._device_notification_client
                )
                logger.info(
                    "[shutdown_device_notif_client] Unregistered Device Notification Client."
                )
            except Exception:
                logger.exception(
                    "[shutdown_device_notif_client] Failed to unregister Device Notification Client."
                )
            finally:
                self._device_notification_client = None  # type: ignore[assignment]
                self._enumerator = None

    def _handle_signal(self, sig: "signal._SIGNUM", frame: "FrameType | None") -> None:
        """Helper to Handle OS signals to initiate a graceful shutdown."""
        self.shutdown(f"Signal '{signal.strsignal(sig)}' (ID: {sig}) received")

    def _stop_internal_loops(self) -> None:
        self._stop_threads_event.set()
        if self._internal_loop_threads:
            self.error_queue.put(None)
            for thread in self._internal_loop_threads:
                thread.join(timeout=3)
                if thread.is_alive():
                    logger.warning(
                        f"[stop_loops] Timed out waiting to stop 'f{thread}'."
                    )
                else:
                    logger.info(f"[stop_loops] Successfully joined thread 'f{thread}'.")

    def shutdown(self, cause: str = "Unknown") -> None:
        """
        Handles the graceful shutdown of the application.

        This is the central cleanup method, triggered by various exit points
        (GUI close, OS signals). It ensures all workers are stopped and
        the profile is saved.

        :param cause: A string explaining what triggered the shutdown, used for logger.
        :type cause: str
        """
        if self.is_closing:
            return

        self.is_closing = True

        if self.ui:
            self.ui.hide()

        logger.info(f"[on_closing] Closing application... Cause: [{cause}]")
        self._shutdown_device_notif_client()

        try:
            if self.audio_capture_worker:
                self.audio_capture_worker.stop()
        except Exception:
            logger.exception("[on_closing] Error stopping Audio Worker.")
        finally:
            self.audio_capture_worker = None

        try:
            self._stop_internal_loops()
        except Exception:
            logger.exception("[on_closing] Error stopping controller loops.")
        finally:
            self._internal_loop_threads = None  # type: ignore[assignment]

        try:
            if self.audio_processor:
                self.audio_processor.stop_process_audio_loop()
        except Exception:
            logger.exception("[on_closing] Error stopping Model.")
        finally:
            self.audio_processor = None

        self.save_profile(_show_dialog=False)

        self._is_running = False
        try:
            if self.ui:
                self.ui.destroy()
        except Exception:
            logger.exception("[on_closing] Error destroying the main window.")
        finally:
            self.ui = None  # type: ignore[assignment]


def get_device_name(device_id: str) -> str | None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        devices = AudioUtilities.GetAllDevices()
    for dev in devices:
        if dev.id == device_id:
            ret: str | None = dev.FriendlyName
            return ret
    return None


class DefaultDeviceNotification(COMObject):  # type: ignore[misc]
    _com_interfaces_: ClassVar[list[type["IUnknown"]]] = [IMMNotificationClient]

    def __init__(
        self, default_device_change_handler: Callable[[str], None] | None = None
    ) -> None:
        super().__init__()
        self.default_device_change_handler = default_device_change_handler
        self._last_device: str | None = None

    def _on_default_device_change(self, name: str) -> None:
        if self.default_device_change_handler:
            self.default_device_change_handler(name)

    def OnDefaultDeviceChanged(
        self,
        flow: Literal[0, 1, 2, 3],
        role: Literal[0, 1, 2, 3],
        device_id: str | None,
    ) -> Literal[0]:
        if flow != EDataFlow.eRender.value or device_id == self._last_device:
            return 0

        self._last_device = device_id
        name = get_device_name(device_id) if device_id is not None else None

        if name is not None:
            logger.info(
                "[OnDefaultDeviceChanged] Default device changed | "
                f"Flow={flow}, Role={role}, ID={device_id}, Name={name}"
            )
            self._on_default_device_change(name)
        else:
            logger.warning(
                "[OnDefaultDeviceChanged] `get_device_name` returned None | "
                f"Flow={flow}, Role={role}, ID={device_id}, Name={name}"
            )

        return 0


class SystemVolumeControl:
    __slots__ = (
        "_refresh_flag_lock",
        "_refresh_needed",
        "_refresh_queued",
        "_volume_interface",
        "_volume_refresh_lock",
        "vol_refresh_callback",
    )

    def __init__(self, vol_refresh_callback: Callable[[], None]) -> None:
        self._volume_interface = None
        self._volume_refresh_lock = threading.Lock()
        self._refresh_needed = True
        self._refresh_queued = False
        self._refresh_flag_lock = threading.Lock()
        self.vol_refresh_callback = vol_refresh_callback
        self.refresh()

    def refresh(self) -> bool:
        if not self._volume_refresh_lock.acquire(blocking=False):
            return False
        try:
            speakers = AudioUtilities.GetSpeakers()
            if speakers is None:
                raise RuntimeError("`AudioUtilities.GetSpeakers()` returned None")
            self._volume_interface = speakers.EndpointVolume
            with self._refresh_flag_lock:
                self._refresh_needed = False
                self._refresh_queued = False
            logger.info("[SystemVolumeControl][refresh] Volume interface refreshed.")
            return True
        except Exception:
            logger.exception(
                "[SystemVolumeControl][refresh] Failed to acquire volume interface."
            )
            self._volume_interface = None
            with self._refresh_flag_lock:
                self._refresh_needed = True
                self._refresh_queued = False
            return False
        finally:
            self._volume_refresh_lock.release()

    def get_linear_gain(self) -> float | None:
        with self._volume_refresh_lock:
            iface = self._volume_interface

        if iface is None:
            with self._refresh_flag_lock:
                if not self._refresh_queued:
                    self.vol_refresh_callback()
                    self._refresh_queued = True
            return None

        try:
            if iface.GetMute():
                return 0.0
            db: float = iface.GetMasterVolumeLevel()
            return 10.0 ** (db / 20.0)
        except Exception:
            with self._refresh_flag_lock:
                self._refresh_needed = True
                self._refresh_queued = False
            return None


class HotkeyManager:
    MOD_MAP: ClassVar[dict[HotkeyModifiers, int]] = {
        HotkeyModifiers.CTRL: win32con.MOD_CONTROL,
        HotkeyModifiers.SHIFT: win32con.MOD_SHIFT,
        HotkeyModifiers.ALT: win32con.MOD_ALT,
    }
    HOTKEY_ID: int = 2525
    ERROR_HOTKEY_NOT_REGISTERED: Final[int] = 1419

    __slots__ = (
        "current_key",
        "hotkey_handler",
        "hwnd",
        "old_proc",
    )

    def __init__(self, hwnd: int, hotkey_handler: Callable[[], None]) -> None:
        self.hwnd = hwnd
        self.hotkey_handler = hotkey_handler
        self.current_key: int | None = None
        self.old_proc: int | None = None
        self.old_proc = win32gui.SetWindowLong(
            self.hwnd, win32con.GWL_WNDPROC, self.handler
        )

    def unregister(self) -> bool:
        try:
            win32gui.UnregisterHotKey(self.hwnd, self.HOTKEY_ID)
            logger.info("[HotkeyManager][unregister] Unregistered Hotkey successfully.")
            return True
        except pywintypes.error as e:
            ret: bool = e.winerror == HotkeyManager.ERROR_HOTKEY_NOT_REGISTERED
            return ret
        except Exception:
            logger.exception(
                "[HotkeyManager][unregister] Exception occured while trying to unregister hotkey."
            )
            return False

    def register(self, mods: list[HotkeyModifiers], key_str: str) -> bool:
        self.unregister()
        mods_value = 0
        for mod in mods:
            mods_value |= self.MOD_MAP[mod]

        key_code = ord(key_str.upper())

        try:
            win32gui.RegisterHotKey(self.hwnd, self.HOTKEY_ID, mods_value, key_code)
            self.current_key = key_code
            logger.info(
                f"[HotkeyManager][register] Registered Hotkey successfully, '{' + '.join(mods).title()} + {key_str.upper()}'"
            )
            return True
        except Exception:
            logger.exception(
                f"[HotkeyManager][register] Failed to register hotkey, '{' + '.join(mods).title()} + {key_str.upper()}'"
            )
            return False

    def handler(self, hWnd: int, msg: int, wParam: int, lParam: int) -> int:
        if msg == win32con.WM_HOTKEY and wParam == self.HOTKEY_ID:
            self.hotkey_handler()
            return 0

        ret: int

        if msg == win32con.WM_DESTROY and self.old_proc:
            win32api.SetWindowLong(self.hwnd, win32con.GWL_WNDPROC, self.old_proc)
            old_proc_temp = self.old_proc
            self.old_proc = None
            ret = win32gui.CallWindowProc(old_proc_temp, hWnd, msg, wParam, lParam)
            return ret

        if self.old_proc:
            ret = win32gui.CallWindowProc(self.old_proc, hWnd, msg, wParam, lParam)
            return ret

        return 0

    def __del__(self) -> None:
        if getattr(self, "old_proc", None):
            try:
                import win32api
                import win32con

                win32api.SetWindowLong(self.hwnd, win32con.GWL_WNDPROC, self.old_proc)
            except Exception:  # noqa: S110
                pass
