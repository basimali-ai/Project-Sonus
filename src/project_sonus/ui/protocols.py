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
import inspect
import queue
from collections.abc import Callable
from typing import Protocol, get_type_hints, runtime_checkable
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import HotkeyModifiers

from .state import (
    Ack,
    AudioMetrics,
    Calibrating,
    DialogErrorEvent,
    DialogStatusEvent,
    DoseStatus,
    NotifErrorEvent,
    NotifStatusEvent,
    UserEntriesEnum,
    UserInputData,
    VolCalcErrorEvent,
    VolCalcStatus,
    VolCalcStatusEvent,
)
# ---------------------------------


@runtime_checkable
class UI(Protocol):
    def __init__(self, *, asserting: bool = False) -> None:
        """
        :param asserting: True if this UI instance is only for assertion purposes. Disable timers,
                          background tasks, UI widgets/elements creation and any OS handle creation.
        :type asserting: bool
        """
        ...

    # --- Scheduling functions ---
    def register_func_queue(self, func_queue: queue.Queue[Callable[[], None]]) -> None:
        """
        Registers a queue for the controller threads to send UI functions to be executed.
        This ensures every UI function is called in the UI thread.

        :param func_queue: Queue used to listen for UI function calls from the controller threads.
        :type func_queue: queue.Queue
        """
        ...

    def update_gui_refresh_interval(self, interval_s: float) -> None:
        """
        Sets a suggested polling interval for processing the UI function queue.
        It is recommended to flush the queue every time it is processed to avoid stale updates.

        :param interval_s: Polling interval in seconds
        :type interval_s: float
        """
        ...

    def MainLoop(self) -> None:
        """
        Starts the GUI event loop and blocks until the UI exits.

        This must be a blocking call so the main script can wait for the application
        to close before continuing shutdown logic.
        """
        ...

    # --- Closing and utility functions ---
    def register_on_closing(self, func: Callable[[], None]) -> None:
        """
        Registers the func to call when closing
        """
        ...

    def destroy(self) -> None:
        """
        Destroy this and all descendants widgets.
        """
        ...

    def show(self) -> None:
        """
        Tells the UI to show itself in the background/bottom without grabbing focus.
        """
        ...

    def hide(self) -> None:
        """
        Tells the UI to hide itself.
        """
        ...

    def bring_window_to_front(self) -> None:
        """
        Tells the UI to bring the app to top and grab focus.
        """
        ...

    # --- Notification and dialog functions ---
    def clear_notifications(self) -> None:
        """
        Clears all notifications
        """
        ...

    def send_notification(
        self,
        notification: NotifErrorEvent | NotifStatusEvent | DoseStatus,
        callback: Callable[[], None] | None = None,
    ) -> None:
        """
        Displays a notification based on the given event or status and optionally
        triggers a callback upon interaction.

        :param notification: The event or status payload to decide what type of notification to show.
        :type notification: NotifErrorEvent | NotifStatusEvent | DoseStatus

        :param callback: Function to execute when the notification is interacted with.
        :type callback: Callable[[], None]
        """
        ...

    def show_dialog(
        self,
        dialog: DialogStatusEvent | DialogErrorEvent | Ack,
        callback: Callable[[bool | None], None] | None = None,
    ) -> None:
        """
        Shows a dialog based on the given event or status and optionally
        triggers a callback upon interaction.

        Calls the function with a boolean input if user acknowledgment was required.

        :param dialog: The event or status payload to decide what type of dialog to show.
        :type dialog: DialogStatusEvent | DialogErrorEvent | Ack

        :param callback: Function to call when the dialog is interacted with,
        calls the function using a bool as input if the function required user acknowledgement
        :type callback: Optional[Callable[[Optional[bool]], None]]
        """
        ...

    def get_window_handle(self) -> int:
        """
        Returns the native Windows handle (HWND) for the main window.

        This is required for registering system-wide hotkeys (e.g. via win32),
        as the OS sends hotkey events to a specific window's message queue.
        """
        ...

    # --- User input functions ---
    def set_user_inputs(self, inputs: dict[UserEntriesEnum, float]) -> None:
        """
        Sets the user entry inputs (except the device dropdown) to the given values.

        :param inputs: Entries and their desired values.
        :type inputs: dict[UserEntriesEnum, float]
        """
        ...

    def get_user_inputs(self) -> UserInputData:
        """
        Returns a :class:`UserInputData` of all user inputs including the target device.
        User entry values that cannot be converted to float will be None,
        except the target device which will always be a str, can be an empty str to show invalidity.

        :return: All user inputs including the target device.
        :rtype: :class:`UserInputData`
        """
        ...

    def set_volume_correction(self, is_enabled: bool) -> None:
        """
        Sets the volume correction checkbox to the desired value

        :param is_enabled: Checked if True, unchecked if False
        :type is_enabled: bool
        """
        ...

    def get_vol_check_box_bool(self) -> bool:
        """
        Returns the current volume correction check box value as a bool

        :return: True if checked, False if unchecked
        :rtype: bool
        """
        ...

    def get_target_device(self) -> str:
        """
        Returns the target device name (the one currently selected in the device dropdown)

        :return: Name of the target device
        :rtype: str
        """
        ...

    def set_hotkey(
        self,
        mods: list[HotkeyModifiers] | None,
        trigger_key_str: str | None,
    ) -> None:
        """
        Updates the hotkey input field state.

        If either argument is None or empty, the field is cleared.

        :param mods: List of modifier enums. At least one modifier is required;
                     an empty list or None clears the hotkey.
        :type mods: Optional[list[HotkeyModifiers]]

        :param trigger_key_str: The trigger key string (e.g. 'M'). None or empty string clears the hotkey.
        :type trigger_key_str: Optional[str]
        """
        ...

    # --- Rendering text functions ---
    def update_audio_metrics(self, metrics: AudioMetrics) -> None: ...

    def render_volume_calculator_state(
        self,
        state: Calibrating | VolCalcStatusEvent | VolCalcErrorEvent | VolCalcStatus,
    ) -> None:
        """
        Renders the volume calculator area to show txt based on the given event or status

        :param state: The event or status payload to decide what to show.
        :type state: Calibrating | VolCalcStatusEvent | VolCalcErrorEvent | VolCalcStatus
        """
        ...

    def render_dose_meter_state(self, status: DoseStatus) -> None:
        """
        Renders the dose meter to show txt based on the given status

        :param state: The status payload to decide what to show.
        :type state: Calibrating | VolCalcStatusEvent | VolCalcErrorEvent | VolCalcStatus
        """
        ...

    # --- Device dropdown functions ---
    def enter_scanning_state(self) -> None:
        """
        Makes the device dropdown non-interactable
        """
        ...

    def exit_scanning_state(self) -> None:
        """
        Makes the device dropdown interactable
        """
        ...

    def update_devices(
        self, device_list: list[str], selected_device: str | None = None
    ) -> None:
        """
        Updates the list of available devices in the dropdown
        """
        ...

    def select_device(self, device_name: str) -> None:
        """Sets value of target device dropdown"""
        ...

    # --- Overlay functions ---
    def toggle_overlay(self) -> None:
        """Toggles overlay on or off"""
        ...

    # --- All handlers ---
    device_change_handler: Callable[[str], None] | None = None
    """
    Notifies controller when the target device is changed.

    :param device_name: The new target device name.
    :type device_name: str
    """

    restore_last_valid_handler: Callable[[UserEntriesEnum], None] | None = None
    """
    Notifies controller to restore the last valid value.

    :param label: Entry that the user triggered restore on.
    :type label: UserEntriesEnum
    """

    register_hotkey_handler: (
        Callable[[bool, list[HotkeyModifiers] | None, str | None], None] | None
    ) = None
    """
    Asks controller to register or unregister a Hotkey, based on user inputs.

    Both `modifiers` and `trigger_key` can be None if `register` is False.

    :param register: True to register, False to unregister.
    :type register: bool

    :param modifiers: Modifier enums (converted later).
    :type modifiers: list[HotkeyModifiers] | None
    
    :param trigger_key: Trigger key character/string (converted later with ord()).
    :type trigger_key: str | None
    """

    baseline_change_handler: Callable[[], None] | None = None
    reset_metrics_handler: Callable[[], None] | None = None
    reset_dose_handler: Callable[[], None] | None = None
    refresh_devices_handler: Callable[[], None] | None = None
    save_profile_handler: Callable[[], None] | None = None
    vol_checkbox_handler: Callable[[], None] | None = None


def assert_ui_compliance(ui: object) -> None:
    type_hints = get_type_hints(UI)
    handler_attrs = [attr for attr in type_hints if attr.endswith("_handler")]

    for attr in handler_attrs:
        if not hasattr(ui, attr):
            raise AssertionError(
                f"Missing required handler: '{ui.__class__.__name__}.{attr}'. "
            )
        if (val := getattr(ui, attr)) is not None:
            raise AssertionError(
                f"Expected '{ui.__class__.__name__}.{attr}' to be uninitialized (None), "
                f"got {val!r} (type: {type(val).__name__})."
            )

    for name, proto_func in inspect.getmembers(UI, predicate=inspect.isfunction):
        if not hasattr(ui, name):
            raise AssertionError(f"{ui.__class__.__name__} is missing method '{name}'")

        impl_func = getattr(ui, name)

        if not callable(impl_func):
            raise AssertionError(f"Attribute '{name}' exists but is not callable")  # noqa: TRY004

        proto_sig = inspect.signature(proto_func)
        impl_sig = inspect.signature(impl_func)

        if inspect.ismethod(impl_func):
            params = list(proto_sig.parameters.values())
            if params and params[0].name == "self":
                new_params = params[1:]
                proto_sig = proto_sig.replace(parameters=new_params)

        if proto_sig != impl_sig:
            raise AssertionError(
                f"Method '{name}' has wrong signature.\n"
                f"Expected: {proto_sig}\n"
                f"Got:      {impl_sig}"
            )
