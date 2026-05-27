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
import math
import queue
from collections.abc import Callable
from ctypes import byref, c_int, sizeof, windll
from textwrap import dedent, wrap
from typing import Any, Literal, NamedTuple, assert_never, cast
# ---------------------------------

# --- Third-Party Imports ---
import win32con
import wx
import wx.lib.buttons as gen
from windows_toasts import (
    InteractableWindowsToaster,
    Toast,
    ToastButton,
    ToastDisplayImage,
    ToastDuration,
    ToastScenario,
)
from wx.richtext import RichTextCtrl
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import (
    USE_DEFAULT_DISPLAY,
    AppConstants,
    HotkeyModifiers,
    PersistenceKeys,
)
from project_sonus.common.runtime_paths import paths
from project_sonus.common.state import ErrorType, StatusType
from project_sonus.configuration.config_manager import config_manager
from project_sonus.configuration.persistence import persistence_manager

from .elements.combobox import ThemedComboBox
from .elements.overlay import Overlay
from .elements.settings_frame import SettingsFrame
from .gui_theme import GUITheme
from .state import (
    Ack,
    AckType,
    AudioMetrics,
    Calibrating,
    DialogErrorEvent,
    DialogStatusEvent,
    DoseStatus,
    DoseStatusType,
    NotifErrorEvent,
    NotifStatusEvent,
    SplLvl,
    UserEntriesEnum,
    UserInputData,
    VolCalcErrorEvent,
    VolCalcStatus,
    VolCalcStatusEvent,
    VolLvl,
)
# ---------------------------------


logger = logging.getLogger(__name__)


class EntryLabels(NamedTuple):
    target_db: str
    safety_buffer_db: str
    baseline_db: str
    baseline_lufs: str


class Entries(NamedTuple):
    target_db: wx.TextCtrl
    safety_buffer_db: wx.TextCtrl
    baseline_db: wx.TextCtrl
    baseline_lufs: wx.TextCtrl


class DoseMetricLabels(NamedTuple):
    dose_consumed: str
    time_to_fill: str
    status: str


class AudioMetricLabels(NamedTuple):
    integrated_db: str
    short_term_db: str
    momentary_db: str
    peak_db: str
    current_stable_lufs: str


class PanelWithGridSizer(wx.Panel):  # type: ignore[misc]
    grid_sizer: wx.GridBagSizer


class SonusUI:
    __slots__ = (
        "_last_volume_text_content",
        "app",
        "arrow_cursor",
        "audio_metric_labels",
        "baseline_change_handler",
        "bold_font",
        "db_panel",
        "device_change_handler",
        "dialog_window",
        "dose_metric_labels",
        "dose_panel",
        "entries",
        "entry_labels",
        "frame",
        "func_queue",
        "gui_refresh_interval",
        "gui_theme",
        "icon",
        "is_shutting_down",
        "labels",
        "left_sizer",
        "main_sizer",
        "normal_font",
        "overlay",
        "panel",
        "refresh_devices_handler",
        "register_hotkey_handler",
        "reset_dose_handler",
        "reset_metrics_handler",
        "restore_last_valid_handler",
        "save_profile_handler",
        "settings_window",
        "sizer",
        "symbol_font",
        "target_device_dropdown",
        "toaster",
        "update_timer",
        "vol_check_box",
        "vol_checkbox_handler",
        "vol_font",
        "volume_result_text",
    )

    def __init__(self, *, asserting: bool = False) -> None:
        """
        :param asserting: True if this UI instance is only for assertion/testing purposes. Disables timers,
                          background tasks, UI widgets/elements creation and any OS handle creation.
        :type asserting: bool
        """
        self._initialize_handlers()
        self.func_queue: queue.Queue[Callable[[], None]] | None = None
        self.audio_metric_labels = AudioMetricLabels(
            integrated_db="Integrated dB:",
            short_term_db="Short-Term dB:",
            momentary_db="Momentary dB:",
            peak_db="True Peak est. (dB):",
            current_stable_lufs="Current LUFS:",
        )
        self.dose_metric_labels = DoseMetricLabels(
            dose_consumed="Dose Consumed (%):",
            time_to_fill="Time to 100% Dose:",
            status="Status:",
        )
        self.entry_labels = EntryLabels(
            target_db="Target SPL (dB):",
            safety_buffer_db="Safety Buffer (dB):",
            baseline_db="Baseline dB (for Calc):",
            baseline_lufs="Baseline LUFS (for Calc):",
        )

        if not asserting:
            self._initialize_runtime()

    def _initialize_runtime(self) -> None:
        self.app = wx.GetApp()
        if self.app is None:
            self.app = wx.App(False)

        self.is_shutting_down = False
        frame_style = wx.DEFAULT_FRAME_STYLE & ~wx.MAXIMIZE_BOX & ~wx.RESIZE_BORDER
        self.frame = wx.Frame(parent=None, title="Project Sonus", style=frame_style)

        self.apply_dark_title_bar(self.frame)

        self.gui_theme = GUITheme(config_manager)
        self.toaster = InteractableWindowsToaster("Project Sonus")

        self.icon = wx.Icon(paths.LOGO_FILE, wx.BITMAP_TYPE_ICO)
        self.frame.SetIcon(self.icon)

        self._last_volume_text_content: tuple[str, ...] | None = None
        self.update_timer: wx.CallLater | None = None
        self.settings_window: SettingsFrame | None = None

        self.labels: dict[str, wx.StaticText] = {}

        self._create_gui()

    def toggle_overlay(self) -> None:
        self.overlay.toggle()

    def MainLoop(self) -> None:
        self.app.MainLoop()

    def get_window_handle(self) -> int:
        """
        Returns the native Windows handle (HWND) for the main window.

        This is required for registering system-wide hotkeys (e.g. via win32),
        as the OS sends hotkey events to a specific window's message queue.
        """
        ret: int = self.frame.GetHandle()
        return ret

    def _create_font(
        self, font_name: str, font_size: int, font_weight: wx.FontWeight
    ) -> wx.Font:
        return wx.Font(
            font_size,
            wx.FONTFAMILY_DEFAULT,
            wx.FONTSTYLE_NORMAL,
            font_weight,
            faceName=font_name,
        )

    def _create_fonts(self) -> None:
        normal_font_name, normal_font_size = self.gui_theme.font_normal
        bold_font_name, bold_font_size = self.gui_theme.font_bold

        self.normal_font = self._create_font(
            normal_font_name, normal_font_size, wx.FONTWEIGHT_NORMAL
        )
        self.bold_font = self._create_font(
            bold_font_name, bold_font_size, wx.FONTWEIGHT_BOLD
        )
        self.symbol_font = self._create_font(
            "Segoe UI Symbol", bold_font_size, wx.FONTWEIGHT_NORMAL
        )
        self.vol_font = self._create_font(
            bold_font_name, bold_font_size * 6, wx.FONTWEIGHT_BOLD
        )

    @staticmethod
    def apply_dark_title_bar(frame: wx.Frame) -> None:
        """
        Attempts to apply the dark theme to the title bar.
        Tries the modern attribute (20) first, falls back to legacy (19).
        """
        try:
            hwnd = frame.GetHandle()

            value = c_int(1)
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Win 10 2004+ and Win 11
            DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY = 19  # Win 10 1809 - 1909

            result = windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                byref(value),
                sizeof(value),
            )

            if result != 0:
                windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY,
                    byref(value),
                    sizeof(value),
                )

            frame.Refresh()
            frame.Update()

        except Exception:
            logger.exception("[apply_dark_title_bar] Falied")

    def enter_scanning_state(self) -> None:
        """
        Makes the device dropdown non-interactable
        """
        self.target_device_dropdown.Enable(False)

    def exit_scanning_state(self) -> None:
        """
        Makes the device dropdown interactable
        """
        self.target_device_dropdown.Enable()

    def get_target_device(self) -> str:
        """
        Returns the target device name (the one currently selected in the device dropdown)

        :return: Name of the target device
        :rtype: str
        """
        return self.target_device_dropdown.GetValue()

    def set_volume_correction(self, is_enabled: bool) -> None:
        """
        Sets the volume correction checkbox to the desired value

        :param is_enabled: Checked if True, unchecked if False
        :type is_enabled: bool
        """
        self.vol_check_box.SetValue(is_enabled)

    def get_vol_check_box_bool(self) -> bool:
        """
        Returns the current volume correction check box value as a bool

        :return: True if checked, False if unchecked
        :rtype: bool
        """
        ret: bool = self.vol_check_box.GetValue()
        return ret

    def _register_hotkey(
        self,
        register: bool,
        mods: list[HotkeyModifiers] | None,
        key_str: str | None,
    ) -> None:
        if self.register_hotkey_handler:
            self.register_hotkey_handler(register, mods, key_str)

    def _initialize_handlers(self) -> None:
        self.device_change_handler: Callable[[str], None] | None = None
        self.restore_last_valid_handler: Callable[[UserEntriesEnum], None] | None = None
        self.register_hotkey_handler: (
            Callable[[bool, list[HotkeyModifiers] | None, str | None], None] | None
        ) = None
        self.baseline_change_handler: Callable[[], None] | None = None
        self.reset_metrics_handler: Callable[[], None] | None = None
        self.reset_dose_handler: Callable[[], None] | None = None
        self.refresh_devices_handler: Callable[[], None] | None = None
        self.save_profile_handler: Callable[[], None] | None = None
        self.vol_checkbox_handler: Callable[[], None] | None = None

    def register_on_closing(self, func: Callable[[], None]) -> None:
        """
        Registers the func to call when closing
        """
        self.frame.Bind(wx.EVT_CLOSE, lambda e: func() if callable(func) else e.Skip())

    def bring_window_to_front(self) -> None:
        """
        Tells the UI to bring the app to top and grab focus.
        """
        if self.frame.IsIconized():
            self.frame.Iconize(False)

        self.frame.Show()
        self.frame.Raise()

        style = self.frame.GetWindowStyle()
        self.frame.SetWindowStyle(style | wx.STAY_ON_TOP)
        self.frame.SetWindowStyle(style & ~wx.STAY_ON_TOP)
        self.frame.SetFocus()

    def show(self) -> None:
        """
        Tells the UI to show itself in the background/bottom without grabbing focus.
        """
        hwnd = self.frame.GetHandle()
        user32 = windll.user32

        display_idx = persistence_manager.data[PersistenceKeys.WINDOW_DISPLAY_IDX]
        if display_idx == USE_DEFAULT_DISPLAY:
            display_idx = wx.Display.GetFromPoint(wx.Point(0, 0))
            if display_idx == wx.NOT_FOUND:
                display_idx = 0

        display = wx.Display(display_idx)
        display_geometry = display.GetGeometry()

        x_rel, y_rel = 0, 0
        win_w, win_h = self.frame.GetSize()

        x = int(display_geometry.x + (display_geometry.width * x_rel) - (win_w * x_rel))
        y = int(
            display_geometry.y + (display_geometry.height * y_rel) - (win_h * y_rel)
        )

        self.frame.SetPosition(wx.Point(x, y))

        user32.SetWindowPos(
            hwnd,
            win32con.HWND_BOTTOM,
            x,
            y,
            win_w,
            win_h,
            win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
        )

    def hide(self) -> None:
        """
        Tells the UI to hide itself.
        """
        self.frame.Hide()

    def destroy(self) -> None:
        """
        Destroy this and all descendant/child widgets.
        """
        try:
            self.is_shutting_down = True
            if self.frame:
                current_display_idx = wx.Display.GetFromWindow(self.frame)
                if current_display_idx == wx.NOT_FOUND:
                    current_display_idx = USE_DEFAULT_DISPLAY

                persistence_manager.data[PersistenceKeys.WINDOW_DISPLAY_IDX] = (
                    current_display_idx
                )
                persistence_manager.save()

                self.frame.Hide()

            self.func_queue = None

            if self.update_timer and self.update_timer.IsRunning():
                self.update_timer.Stop()
                self.update_timer = None

            if self.overlay:
                self.overlay.Hide()
                self.overlay.Destroy()

            if self.settings_window:
                self.settings_window.Hide()
                self.settings_window.Destroy()

        except Exception:
            logger.exception("[destroy] Cleanup error.")

        finally:
            if self.frame:
                self.frame.Destroy()

            if self.app and self.app.IsMainLoopRunning():
                self.app.ExitMainLoop()

    def update_gui_refresh_interval(self, interval_s: float) -> None:
        """
        Sets a suggested polling interval for processing the UI function queue.
        It is recommended to flush the queue every time it is processed to avoid stale updates.

        :param interval_s: Polling interval in seconds
        :type interval_s: float
        """
        self.gui_refresh_interval = int(interval_s * 1000)

    def register_func_queue(self, func_queue: queue.Queue[Callable[[], None]]) -> None:
        """
        Registers a queue for the controller threads to send UI functions to be executed.
        This ensures every UI function is called in the UI thread.

        :param func_queue: Queue used to listen for UI function calls from the controller threads.
        :type func_queue: queue.Queue
        """
        self.func_queue = func_queue
        self.gui_refresh_interval = 16
        self.process_func_queue()

    def process_func_queue(self) -> None:
        if self.func_queue is None:
            return

        try:
            while True:
                func = self.func_queue.get_nowait()
                func()
        except queue.Empty:
            pass
        except Exception:
            logger.exception("[process_func_queue]")

        if self.func_queue is not None:
            self.update_timer = wx.CallLater(
                self.gui_refresh_interval, self.process_func_queue
            )

    def _show_dialog(
        self,
        title: str,
        message: str,
        text_alignment: Literal["left", "center", "right"] = "center",
        button_type: Literal["ok", "yes_no"] = "ok",
        callback: Callable[[bool | None], None] | None = None,
    ) -> None:
        """
        Local function to display a generic, non-blocking dialog window.
        Ensures only one dialog is open at a time.
        """
        if getattr(self, "dialog_window", None):
            return

        align_map = {
            "left": wx.ALIGN_LEFT,
            "center": wx.ALIGN_CENTER_HORIZONTAL,
            "right": wx.ALIGN_RIGHT,
        }
        style_align = align_map.get(text_alignment, wx.ALIGN_CENTER_HORIZONTAL)

        self.dialog_window: wx.Dialog | None = wx.Dialog(
            self.frame, title=title, style=wx.DEFAULT_DIALOG_STYLE
        )
        panel = wx.Panel(self.dialog_window)
        panel.SetBackgroundColour(wx.Colour(self.gui_theme.bg_color))

        sizer = wx.BoxSizer(wx.VERTICAL)

        msg = wx.StaticText(panel, label=message, style=style_align)
        msg.SetForegroundColour(wx.Colour(self.gui_theme.text_color))
        msg.SetFont(self.normal_font)
        msg.Wrap(400)
        sizer.Add(msg, 0, wx.ALL, 10)

        def on_ack(result: bool | None = None) -> None:
            if callback:
                if result is None:
                    callback(None)
                else:
                    callback(result)

            if self.frame:
                self.frame.Enable()
                self.frame.Raise()

            if self.dialog_window:
                self.dialog_window.Destroy()
                self.dialog_window = None

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        if button_type == "ok":
            ok_btn = self.create_button(
                gen.GenButton, panel, "Ok", self.bold_font, lambda: on_ack()
            )
            self.dialog_window.Bind(wx.EVT_CLOSE, lambda e: on_ack())
            btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
            ok_btn.SetFocus()

        elif button_type == "yes_no":
            yes_btn = self.create_button(
                gen.GenButton,
                panel,
                "Yes",
                self.bold_font,
                lambda: on_ack(True),
            )
            no_btn = self.create_button(
                gen.GenButton,
                panel,
                "No",
                self.bold_font,
                lambda: on_ack(False),
            )
            self.dialog_window.Bind(wx.EVT_CLOSE, lambda e: on_ack(False))
            btn_sizer.Add(yes_btn, 0, wx.ALL, 5)
            btn_sizer.Add(no_btn, 0, wx.ALL, 5)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        panel.SetSizerAndFit(sizer)

        dlg_sizer = wx.BoxSizer(wx.VERTICAL)
        dlg_sizer.Add(panel, 1, wx.EXPAND)
        self.dialog_window.SetSizerAndFit(dlg_sizer)

        self.dialog_window.Fit()
        self.dialog_window.CentreOnParent()
        self.frame.Disable()
        self.dialog_window.Show()

    def set_user_inputs(self, inputs: dict[UserEntriesEnum, float]) -> None:
        """
        Sets the user entry inputs (except the device dropdown) to the given values.

        :param inputs: Entries and their desired values.
        :type inputs: dict[UserEntriesEnum, float]
        """
        entries = self.entries
        entry_map: dict[UserEntriesEnum, wx.TextCtrl] = {
            UserEntriesEnum.TARGET_DB: entries.target_db,
            UserEntriesEnum.SAFETY_BUFFER_DB: entries.safety_buffer_db,
            UserEntriesEnum.BASELINE_DB: entries.baseline_db,
            UserEntriesEnum.BASELINE_LUFS: entries.baseline_lufs,
        }
        for enum, value in inputs.items():
            entry = entry_map[enum]
            if (str_value := str(value)) != entry.GetValue():
                entry.SetValue(str_value)

    def _parse_float_from_entry(self, entry_widget: wx.TextCtrl) -> float | None:
        """Safely parses a finite and valid float from a wx.TextCtrl, returning None on failure."""
        try:
            value = float(entry_widget.GetValue())
            if math.isinf(value) or math.isnan(value):
                return None
            if (
                value > AppConstants.VALID_ENTRY_ABS_LIMIT
                or value < -AppConstants.VALID_ENTRY_ABS_LIMIT
            ):
                return None
            return value
        except ValueError:
            return None

    def get_user_inputs(self) -> UserInputData:
        """
        Returns a :class:`UserInputData` of all user inputs including the target device.
        User entry values that cannot be converted to float will be None,
        except the target device which will always be a str, can be an empty str to show invalidity.

        :return: All user inputs including the target device.
        :rtype: :class:`UserInputData`
        """
        entries = self.entries
        return UserInputData(
            target_device=self.target_device_dropdown.GetValue(),
            entries_data={
                UserEntriesEnum.TARGET_DB: self._parse_float_from_entry(
                    entries.target_db,
                ),
                UserEntriesEnum.SAFETY_BUFFER_DB: self._parse_float_from_entry(
                    entries.safety_buffer_db,
                ),
                UserEntriesEnum.BASELINE_DB: self._parse_float_from_entry(
                    entries.baseline_db,
                ),
                UserEntriesEnum.BASELINE_LUFS: self._parse_float_from_entry(
                    entries.baseline_lufs,
                ),
            },
        )

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
        text_alignment: Literal["left", "center"] = "center"
        button_type: Literal["ok", "yes_no"] = "ok"
        title = ""
        message = ""

        match dialog:
            case DialogErrorEvent(device_name=device_name, error_type=error_type):
                match error_type:
                    case ErrorType.CONNECTION_LOST_RETRY_FAILED:
                        title = "Audio Device Error"
                        message = dedent(f"""\
                            Could not connect to the selected audio device:
                            '{device_name}'

                            Please check if the device is connected and enabled, then refresh the device list and choose it from the list.
                            
                            This can happen if:
                                1. The device is disconnected
                                   or disabled.

                                2. Another application is using
                                   the device in exclusive mode.""")
                        text_alignment = "left"

                    case ErrorType.SAVE_FAILED:
                        title = "Save Failed"
                        message = f"Could not save the device setting for '{device_name}'. Please retry."

                    case _:
                        assert_never(error_type)

            case DialogStatusEvent(device_name=device_name, status_type=status_type):
                match status_type:
                    case StatusType.SAVE_SUCCESSFUL:
                        title = "Saving Sucessful"
                        message = f"'{device_name}' Device Profile, and universal Dose saved succesfully!"

                    case _:
                        assert_never(status_type)

            case Ack(ack_type=ack_type):
                button_type = "yes_no"
                match ack_type:
                    case AckType.RESET_DOSE:
                        title = "Reset Dose?"
                        message = "Are you sure you want to reset Dose?"

                    case AckType.RESET_METRICS:
                        title = "Reset Metrics/Integrated?"
                        message = "Are you sure you want to reset Metrics/Integrated?"
                    case _:
                        assert_never(ack_type)

            case _:
                assert_never(dialog)

        self._show_dialog(
            title=title,
            message=message,
            text_alignment=text_alignment,
            button_type=button_type,
            callback=callback,
        )

    def dismiss_dialog(self) -> None:
        """Programmatically closes the active dialog window, if it exists."""
        if self.dialog_window and self.dialog_window.IsShown():
            self.dialog_window.Destroy()
            self.dialog_window = None

    def select_device(self, device_name: str) -> None:
        """Sets value of target device dropdown"""
        self.target_device_dropdown.SetValue(device_name)

    def update_devices(
        self, device_list: list[str], selected_device: str | None = None
    ) -> None:
        """
        Updates the list of available devices in the dropdown.
        """
        self.target_device_dropdown.SetChoices(device_list)
        if selected_device and selected_device in device_list:
            self.target_device_dropdown.SetValue(selected_device)
        else:
            self.target_device_dropdown.SetValue("")

    def attach_tooltip(
        self,
        widget: wx.Control,
        text: str,
        width: int = 40,
        border_padding: int = 5,
    ) -> None:
        tip = wx.PopupWindow(widget, wx.BORDER_SIMPLE)
        tip.SetBackgroundColour(wx.Colour(self.gui_theme.bg_color))

        wrapped_paragraphs = []
        for para in text.split("\n\n"):
            wrapped_paragraphs.append("\n".join(wrap(para, width=width)))
        wrapped_text = "\n\n".join(wrapped_paragraphs)

        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(tip, label=wrapped_text)
        label.SetFont(self.normal_font)
        label.SetForegroundColour(wx.Colour(self.gui_theme.text_color))
        sizer.Add(label, 1, wx.ALL, border_padding)

        tip.SetSizerAndFit(sizer)

        def show_tooltip(e: wx.Event) -> None:
            pos = widget.ClientToScreen(wx.Point(0, widget.GetSize()[1]))
            tip.Position(pos, wx.Size(0, 0))
            tip.Show()
            if isinstance(widget, (gen.GenButton, FlatSymbolButton)):
                self.on_hover(e, widget)

        def hide_tooltip(e: wx.Event) -> None:
            tip.Hide()
            if isinstance(widget, (gen.GenButton, FlatSymbolButton)):
                self.on_leave(e, widget)

        widget.Bind(wx.EVT_ENTER_WINDOW, show_tooltip)
        widget.Bind(wx.EVT_LEAVE_WINDOW, hide_tooltip)

    def create_button(
        self,
        btn_class: type[gen.GenButton],
        panel: wx.Panel,
        label: str,
        font: wx.Font,
        handler: Callable[[], None],
        tooltip_txt: str | None = None,
    ) -> gen.GenButton:
        button = btn_class(parent=panel, label=label)
        button.SetBezelWidth(0)
        button.SetUseFocusIndicator(False)
        button.SetFont(font)
        button.SetForegroundColour(wx.Colour(self.gui_theme.bg_color))
        button.SetBackgroundColour(wx.Colour(self.gui_theme.accent_color))
        button.Bind(wx.EVT_ENTER_WINDOW, lambda e, b=button: self.on_hover(e, b))
        button.Bind(wx.EVT_LEAVE_WINDOW, lambda e, b=button: self.on_leave(e, b))
        button.Bind(wx.EVT_BUTTON, lambda e: handler())
        if tooltip_txt:
            self.attach_tooltip(button, tooltip_txt)
        return button

    def _gui_create_vol_calc(self) -> None:
        box = wx.StaticBox(self.panel, label="Volume Calculator")
        box.SetFont(self.bold_font)
        box.SetForegroundColour(wx.Colour(self.gui_theme.text_color))
        self.sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        entries: list[wx.TextCtrl] = []
        grid = wx.FlexGridSizer(cols=2, hgap=8, vgap=20)
        grid.AddGrowableCol(1, 0)

        tooltips = [
            "Enter the desired/max listening level you want to achieve (e.g., 79 dB for safe, long-term listening).",
            "Optional safety buffer to stay below the target SPL.\n\nNote: Your daily dose is still accumulated at the original SPL without the buffer having an effect, so this is mainly for peace of mind.",
            "Device-specific baseline dB.\n\nWhen calibrating, Download any sound meter app on your phone, start monitoring sound from that app in your particular listening postion, and enter the value it shows in this entry field.",
            f"Device-specific baseline LUFS.\n\nWhen calibrating, In the DB Meter pane, you will see a '{self.audio_metric_labels.current_stable_lufs}' value. Type that value in this entry field.",
        ]

        entry_labels = self.entry_labels
        label_map: dict[UserEntriesEnum, str] = {
            UserEntriesEnum.TARGET_DB: entry_labels.target_db,
            UserEntriesEnum.SAFETY_BUFFER_DB: entry_labels.safety_buffer_db,
            UserEntriesEnum.BASELINE_DB: entry_labels.baseline_db,
            UserEntriesEnum.BASELINE_LUFS: entry_labels.baseline_lufs,
        }

        for i, (enum, label) in enumerate(label_map.items()):
            txt_label = wx.StaticText(self.panel, label=label)
            entry = wx.TextCtrl(
                self.panel,
                value="100.0",
                style=wx.BORDER_NONE | wx.TE_PROCESS_ENTER,
            )

            txt_label.SetFont(self.normal_font)
            txt_label.SetForegroundColour(wx.Colour(self.gui_theme.text_color))

            self.attach_tooltip(txt_label, tooltips[i])

            entry.SetBackgroundColour(wx.Colour(self.gui_theme.field_color))
            entry.SetForegroundColour(wx.Colour(self.gui_theme.text_color))
            entry.SetFont(self.normal_font)

            entry.Bind(
                wx.EVT_LEAVE_WINDOW,
                lambda e: (
                    self.baseline_change_handler and self.baseline_change_handler()
                ),
            )

            entry.Bind(
                wx.EVT_TEXT_ENTER,
                lambda e: (
                    self.baseline_change_handler and self.baseline_change_handler(),
                    self.db_panel.SetFocus(),  # Remove focus from entry
                ),
            )

            def restore_handler(enum: UserEntriesEnum = enum) -> None:
                if self.restore_last_valid_handler:
                    self.restore_last_valid_handler(enum)

            entry_reset_button = self.create_button(
                FlatSymbolButton,
                self.panel,
                "⟳",
                self.symbol_font,
                restore_handler,
                "Restore last valid entry.",
            )

            entry_container = wx.BoxSizer(wx.HORIZONTAL)
            entry_container.Add(entry, 1, wx.EXPAND)
            entry_container.Add(entry_reset_button, 0, wx.LEFT, 10)

            entries.append(entry)
            grid.Add(txt_label, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(entry_container, 0, wx.ALIGN_RIGHT)

        self.entries: Entries = Entries(*entries)
        self.sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)

        row = wx.BoxSizer(wx.HORIZONTAL)

        self.target_device_dropdown: ThemedComboBox = ThemedComboBox(
            self.panel,
            choices=["24G4 (NVIDIA High Definition Audio)", "B", "C"],
            bg_color=self.gui_theme.field_color,
            fg_color=self.gui_theme.text_color,
            hover_bg_color=self.gui_theme.dark_field_color,
            sel_bg_color=self.gui_theme.dark_field_color,
            font=self.normal_font,
        )
        self.target_device_dropdown.BindOnChange(self._on_device_change)

        btn_refresh = self.create_button(
            FlatSymbolButton,
            self.panel,
            "⟳",
            self.symbol_font,
            lambda: self.refresh_devices_handler and self.refresh_devices_handler(),
            "Refresh devices.",
        )

        btn_save = self.create_button(
            FlatSymbolButton,
            self.panel,
            "💾",
            self.symbol_font,
            lambda: self.save_profile_handler and self.save_profile_handler(),
            "Save device profile.",
        )

        txt_label = wx.StaticText(self.panel, label="Target Device:")
        txt_label.SetFont(self.normal_font)
        txt_label.SetForegroundColour(wx.Colour(self.gui_theme.text_color))
        self.attach_tooltip(
            txt_label,
            "Audio device the app will listen on, dropdown will show you all detected sound devices.",
        )

        row.Add(
            txt_label,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.BOTTOM | wx.RIGHT,
            10,
        )
        row.AddStretchSpacer()
        row.Add(
            self.target_device_dropdown,
            0,
            wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT,
            10,
        )
        row.Add(btn_refresh, 0, wx.LEFT | wx.TOP, 10)
        row.Add(btn_save, 0, wx.LEFT | wx.TOP, 10)

        self.sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.vol_check_box: wx.CheckBox = wx.CheckBox(
            self.panel, label="Apply Volume Correction ℹ️"
        )
        self.vol_check_box.SetFont(self.normal_font)
        self.vol_check_box.SetForegroundColour(wx.Colour(self.gui_theme.text_color))
        self.vol_check_box.Bind(
            wx.EVT_CHECKBOX,
            lambda e: self.vol_checkbox_handler and self.vol_checkbox_handler(),
        )
        self.attach_tooltip(
            self.vol_check_box,
            "Corrects measurements using the windows volume, of your current default Windows audio device.\n\n(Uncheck this, then turn Windows volume to 0% to test.)",
        )

        self.overlay: Overlay = Overlay(font=self.bold_font)

        btn_toggle_overlay = self.create_button(
            gen.GenButton,
            self.panel,
            "Toggle Overlay",
            self.bold_font,
            self.overlay.toggle,
        )

        btn_show_settings = self.create_button(
            gen.GenButton,
            self.panel,
            "Overlay Settings",
            self.bold_font,
            self.on_open_settings,
        )

        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        h_sizer.Add(
            self.vol_check_box,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT,
            10,
        )
        h_sizer.Add(
            btn_toggle_overlay,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT,
            10,
        )
        h_sizer.Add(
            btn_show_settings,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT,
            10,
        )
        self.sizer.Add(h_sizer, 0, wx.ALIGN_RIGHT)

        self.volume_result_text = RichTextCtrl(self.panel, style=wx.BORDER_NONE)
        self.volume_result_text.EnableVerticalScrollbar(False)
        self.volume_result_text.SetEditable(False)
        self.volume_result_text.SetBackgroundColour(wx.Colour(self.gui_theme.bg_color))
        self.volume_result_text.SetFont(self.vol_font)

        self.arrow_cursor = wx.Cursor(wx.CURSOR_ARROW)
        self.volume_result_text.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.volume_result_text.Bind(wx.EVT_LEFT_DCLICK, lambda event: None)
        self.volume_result_text.Bind(wx.EVT_SET_CURSOR, self.on_set_cursor)
        self.volume_result_text.Bind(wx.EVT_SET_FOCUS, self.on_focus)

        self.sizer.Add(self.volume_result_text, 0, wx.EXPAND | wx.ALL, 10)
        self.panel.Layout()

        dc = wx.ClientDC(self.volume_result_text)

        total_height = 0
        max_width = 0

        dc.SetFont(self.bold_font)
        w, h = dc.GetTextExtent("Current SPL:")
        total_height += h
        max_width = max(max_width, w)

        dc.SetFont(self.vol_font)
        w, h = dc.GetTextExtent("88.88 dB")
        total_height += h
        max_width = max(max_width, w)

        dc.SetFont(self.normal_font)
        w, h = dc.GetTextExtent("------------------------")
        total_height += h
        max_width = max(max_width, w)

        dc.SetFont(self.normal_font)
        w, h = dc.GetTextExtent("Increase volume to add ~ 10.00 dB")
        total_height += h
        max_width = max(max_width, w)

        padding_w = 30
        padding_h = 30

        final_w = max_width + padding_w
        final_h = total_height + padding_h

        self.volume_result_text.SetMinSize(wx.Size(final_w, final_h))
        self.volume_result_text.SetSize(wx.Size(final_w, final_h))

        self.panel.Layout()

    def on_open_settings(self, event: wx.Event | None = None) -> None:
        if self.is_shutting_down:
            return

        if self.settings_window is None:
            raise RuntimeError("settings_window accessed before initialization.")

        self.settings_window.Show()

    def on_left_down(self, event: wx.MouseEvent) -> None:
        """
        Steal focus from the other entry widget.
        Block the native logic so no text selection happens.
        """
        self.volume_result_text.SetFocus()
        # Not calling event.Skip()
        # to prevent the "I-Beam placement" and "Selection" logic.

    def on_set_cursor(self, event: wx.SetCursorEvent) -> None:
        """Forces the Arrow cursor without CPU spikes."""
        event.SetCursor(self.arrow_cursor)

    def on_focus(self, event: wx.FocusEvent) -> None:
        """
        When we steal focus in on_left_down, this triggers.
        We let focus happen (so the other entry loses it), but hide the blinker.
        """
        event.Skip()
        self.volume_result_text.SetCaret(None)

    def render_dose_meter_state(self, status: DoseStatus) -> None:
        """
        Renders the dose meter to show txt based on the given status

        :param state: The status payload to decide what to show.
        :type state: Calibrating | VolCalcStatusEvent | VolCalcErrorEvent | VolCalcStatus
        """
        match status.dose_status:
            case DoseStatusType.EXCEEDED:
                status_text, status_color = (
                    "BUDGET EXCEEDED!",
                    wx.Colour(self.gui_theme.critical_color),
                )
            case DoseStatusType.DANGER:
                status_text, status_color = (
                    "DANGER",
                    wx.Colour(self.gui_theme.critical_color),
                )
            case DoseStatusType.WARNING:
                status_text, status_color = (
                    "Alert",
                    wx.Colour(self.gui_theme.warning_color),
                )
            case DoseStatusType.SAFE:
                status_text, status_color = (
                    "Safe",
                    wx.Colour(self.gui_theme.ok_color),
                )
            case _:
                assert_never(status.dose_status)

        labels = self.labels
        dose_metric_labels = self.dose_metric_labels

        changed = False
        for st, text in (
            (
                labels[dose_metric_labels.dose_consumed],
                f"{status.daily_dose_consumed:.2f}%",
            ),
            (
                labels[dose_metric_labels.time_to_fill],
                status.time_to_fill_str,
            ),
            (
                labels[dose_metric_labels.status],
                status_text,
            ),
        ):
            if st.GetLabel() != text:
                st.SetLabel(text)
                changed = True

        if st.GetForegroundColour() != status_color:
            st.SetForegroundColour(status_color)
            changed = True

        if changed:
            st.GetParent().Layout()

        self.overlay.update_dose_time(status.time_to_fill_str, status_color)

    def render_volume_calculator_state(
        self,
        state: Calibrating | VolCalcStatusEvent | VolCalcErrorEvent | VolCalcStatus,
    ) -> None:
        """
        Renders the volume calculator area to show txt based on the given event or status

        :param state: The event or status payload to decide what to show.
        :type state: Calibrating | VolCalcStatusEvent | VolCalcErrorEvent | VolCalcStatus
        """
        styled_parts: list[tuple[str, str, wx.Font]] = []
        spl_overlay: tuple[float | str, str] = ("---", self.gui_theme.ok_color)
        dose_overlay: tuple[str, str] | None = None

        match state:
            case VolCalcErrorEvent(
                device_name=device_name,
                attempt_str=attempt_str,
                error_type=error_type,
            ):
                spl_overlay = dose_overlay = ("Error", self.gui_theme.critical_color)
                if self.settings_window:
                    self.settings_window.simulating_spl = False

                match error_type:
                    case ErrorType.AUDIO_DEVICE_UNAVAILABLE:
                        styled_parts = [
                            (
                                "Audio device unavailable.",
                                self.gui_theme.critical_color,
                                self.bold_font,
                            ),
                            (
                                "Please select a new device from the list above.",
                                self.gui_theme.warning_color,
                                self.normal_font,
                            ),
                            (
                                "Refresh the list if device is reconnected/available now.",
                                self.gui_theme.warning_color,
                                self.normal_font,
                            ),
                        ]
                    case ErrorType.CONNECTION_LOST_RETRY_FAILED:
                        styled_parts = [
                            (
                                f"Connection lost to '{device_name}'",
                                self.gui_theme.critical_color,
                                self.bold_font,
                            ),
                            (
                                f"({attempt_str}) Retry Attempts Failed",
                                self.gui_theme.critical_color,
                                self.normal_font,
                            ),
                        ]
                    case ErrorType.CONNECTION_LOST_RETRYING:
                        styled_parts = [
                            (
                                f"Connection lost to '{device_name}'",
                                self.gui_theme.warning_color,
                                self.bold_font,
                            ),
                            (
                                f"Attempting to reconnect... ({attempt_str})",
                                self.gui_theme.warning_color,
                                self.normal_font,
                            ),
                        ]
                    case ErrorType.ENTRY_BASELINE:
                        styled_parts = [
                            (
                                "Invalid Baseline Input.",
                                self.gui_theme.critical_color,
                                self.bold_font,
                            ),
                            (
                                "All dB values are disabled.",
                                self.gui_theme.critical_color,
                                self.bold_font,
                            ),
                            (
                                "Dose accumulation is also paused.",
                                self.gui_theme.critical_color,
                                self.bold_font,
                            ),
                        ]
                    case ErrorType.ENTRY_TARGET:
                        styled_parts = [
                            (
                                "Invalid Target SPL or Safety Buffer.",
                                self.gui_theme.warning_color,
                                self.bold_font,
                            ),
                        ]
                        dose_overlay = None
                    case _:
                        assert_never(error_type)

            case VolCalcStatusEvent(status_type=status_type):
                match status_type:
                    case StatusType.SCANNING_DEVICES:
                        styled_parts = [
                            (
                                "Scanning for available devices...",
                                self.gui_theme.warning_color,
                                self.bold_font,
                            ),
                        ]
                    case StatusType.CHANGING_DEVICE:
                        styled_parts = [
                            (
                                "Changing audio device...",
                                self.gui_theme.warning_color,
                                self.bold_font,
                            ),
                        ]
                    case StatusType.WAITING_AUDIO:
                        styled_parts = [
                            (
                                "Waiting for audio signal...",
                                self.gui_theme.warning_color,
                                self.bold_font,
                            ),
                        ]
                    case _:
                        assert_never(status_type)

            case Calibrating(wait_seconds=wait_seconds):
                styled_parts = [
                    (
                        "Calibrating...",
                        self.gui_theme.warning_color,
                        self.bold_font,
                    ),
                    (
                        f"Please wait for ~ {wait_seconds:.2f} seconds",
                        self.gui_theme.warning_color,
                        self.bold_font,
                    ),
                ]

            case VolCalcStatus(
                current_spl=current_spl,
                required_change=required_change,
                spl_level=spl_level,
                volume_level=volume_level,
            ):
                match spl_level:
                    case SplLvl.SAFE:
                        spl_color = self.gui_theme.ok_color
                    case SplLvl.DANGER:
                        spl_color = self.gui_theme.critical_color
                    case SplLvl.WARNING:
                        spl_color = self.gui_theme.warning_color
                    case _:
                        assert_never(spl_level)

                styled_parts.append(("Current SPL (est.):", spl_color, self.bold_font))
                styled_parts.append((f"{current_spl:.1f} dB", spl_color, self.vol_font))
                styled_parts.append(
                    ("-" * 25, self.gui_theme.gray_color, self.normal_font)
                )

                match volume_level:
                    case VolLvl.CORRECT:
                        recommendation_text = ">>> Volume is correct <<<"
                        recommendation_color = self.gui_theme.ok_color
                    case VolLvl.INCREASE:
                        recommendation_text = (
                            f"Increase volume to add ~ {required_change:.1f} dB"
                        )
                        recommendation_color = self.gui_theme.gray_color
                    case VolLvl.DECREASE:
                        if required_change is None:
                            raise RuntimeError(
                                "required_change is None in `case VmVolLvl.DECREASE`."
                            )
                        recommendation_text = (
                            f"Decrease volume to cut ~ {abs(required_change):.1f} dB"
                        )
                        recommendation_color = self.gui_theme.warning_color
                    case _:
                        assert_never(volume_level)

                styled_parts.append(
                    (
                        recommendation_text,
                        recommendation_color,
                        self.normal_font,
                    )
                )
                spl_overlay = (current_spl, spl_color)
            case _:
                assert_never(state)

        current_content = tuple(part[0] for part in styled_parts)
        if current_content != self._last_volume_text_content:
            self.volume_result_text.Clear()
            for i, (text, color, font) in enumerate(styled_parts, start=1):
                line_content = (
                    text if (i - 1) == (len(styled_parts) - 1) else f"{text}\n"
                )
                self._write_tag(line_content, color, font)
            self._last_volume_text_content = current_content

        if dose_overlay is not None:
            self.overlay.update_dose_time(*dose_overlay)

        if self.settings_window and not self.settings_window.simulating_spl:
            self.overlay.update_spl(*spl_overlay)

    def _write_tag(self, text: str, color: str, font: wx.Font | None = None) -> None:
        if font:
            self.volume_result_text.BeginFont(font)
        self.volume_result_text.BeginTextColour(wx.Colour(color))
        self.volume_result_text.WriteText(text)
        self.volume_result_text.EndTextColour()
        if font:
            self.volume_result_text.EndFont()

    def _on_device_change(self, device_name: str) -> None:
        """
        Notifies controller when the target device is changed

        :param device_name: The new target device name
        :type device_name: str
        """
        if self.device_change_handler:
            self.device_change_handler(device_name)

    def _create_gui(self) -> None:
        self.panel = wx.Panel(self.frame)
        self.panel.SetBackgroundColour(wx.Colour(self.gui_theme.bg_color))

        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.panel.SetSizer(self.main_sizer)

        self.left_sizer = wx.BoxSizer(wx.VERTICAL)

        self._create_fonts()
        self._gui_create_db_meter()
        self._gui_create_dose_frame()
        self._gui_create_vol_calc()

        self.main_sizer.Add(self.left_sizer, 0, wx.ALL | wx.EXPAND, 10)
        self.main_sizer.Add(self.sizer, 0, wx.ALL | wx.EXPAND, 20)

        self.panel.SetSizerAndFit(self.main_sizer)
        self.frame.SetClientSize(self.panel.GetSize())
        self.frame.SetMinSize(self.frame.GetSize())

        for label in self.dose_metric_labels:
            self.labels[label].SetLabel("---")
            self.dose_panel.Layout()

        for label in self.audio_metric_labels:
            self.labels[label].SetLabel("---")
            self.db_panel.Layout()

    def _add_label_value(
        self, parent: PanelWithGridSizer, label_name: str, row: int, value_text: str
    ) -> None:
        """Add a label/value pair to a GridBagSizer"""
        label = wx.StaticText(parent, label=label_name)
        value = wx.StaticText(parent, label=value_text, style=wx.ALIGN_RIGHT)

        label.SetFont(self.normal_font)
        label.SetForegroundColour(wx.Colour(self.gui_theme.text_color))
        value.SetFont(self.bold_font)
        value.SetForegroundColour(wx.Colour(self.gui_theme.text_color))

        value_container = wx.BoxSizer(wx.HORIZONTAL)
        value_container.AddStretchSpacer()
        value_container.Add(value, 0, wx.ALIGN_CENTER_VERTICAL)

        parent.grid_sizer.Add(
            label,
            pos=(row, 0),
            flag=wx.ALL | wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL,
            border=10,
        )
        parent.grid_sizer.Add(
            value_container, pos=(row, 1), flag=wx.ALL | wx.EXPAND, border=10
        )

        audio_metric_labels = self.audio_metric_labels
        dose_metric_labels = self.dose_metric_labels
        tooltips = {
            audio_metric_labels.integrated_db: "Long-term average loudness.\n\nPress 'Reset Integrated' to restart this measurement.",
            audio_metric_labels.short_term_db: "Moderately fast meter showing recent loudness changes.",
            audio_metric_labels.momentary_db: "Fastest-reacting meter showing immediate loudness changes.",
            audio_metric_labels.peak_db: "The loudest sound measured.\n\nTurns yellow if your audio is at the risk of clipping or red if it gets dangerously high.",
            audio_metric_labels.current_stable_lufs: f"Represents a LUFS value between Short-Term and Momentary dBs in terms of reactivity.\n\nYou will use this value to calibrate the app by entering it in the '{self.entry_labels.baseline_lufs}' field.",
            dose_metric_labels.dose_consumed: "The goal is to stay under 100% for the day to minimize the risk of hearing damage.",
            dose_metric_labels.time_to_fill: "Estimated time to reach 100% dose based on recent listening levels.",
        }

        if label_name in tooltips:
            self.attach_tooltip(label, tooltips[label_name])

        self.labels[label_name] = value

    def _gui_create_db_meter(self) -> None:

        self.db_panel = PanelWithGridSizer(self.panel)
        db_box = wx.StaticBox(self.db_panel, label="DB Meter")
        db_box.SetFont(self.bold_font)
        db_box.SetForegroundColour(wx.Colour(self.gui_theme.text_color))
        db_sizer = wx.StaticBoxSizer(db_box, wx.VERTICAL)
        self.db_panel.SetSizer(db_sizer)

        grid = wx.GridBagSizer(vgap=5, hgap=10)
        self.db_panel.grid_sizer = grid

        for i, metric in enumerate(self.audio_metric_labels):
            self._add_label_value(self.db_panel, metric, i, "-" * 4)

        grid.AddGrowableCol(1, 0)

        db_sizer.Add(grid, 0, flag=wx.EXPAND)

        btn_reset = self.create_button(
            gen.GenButton,
            self.db_panel,
            "Reset Integrated",
            self.bold_font,
            lambda: self.reset_metrics_handler and self.reset_metrics_handler(),
            "Resets the Integrated dBs and all other Meters. Integrated dB is a long term average so this helps for a quick reset to get rid of invalid/testing values.",
        )

        db_sizer.Add(btn_reset, 0, wx.ALL | wx.ALIGN_CENTER, 20)

        self.left_sizer.Add(self.db_panel, 0, flag=wx.ALL | wx.EXPAND, border=10)

    def _gui_create_dose_frame(self) -> None:
        self.dose_panel = PanelWithGridSizer(self.panel)
        dose_box = wx.StaticBox(self.dose_panel, label="Daily Dose Meter")
        dose_box.SetFont(self.bold_font)
        dose_box.SetForegroundColour(wx.Colour(self.gui_theme.text_color))

        dose_sizer = wx.StaticBoxSizer(dose_box, wx.VERTICAL)
        self.dose_panel.SetSizer(dose_sizer)

        grid = wx.GridBagSizer(vgap=5, hgap=10)
        self.dose_panel.grid_sizer = grid

        for i, label in enumerate(self.dose_metric_labels):
            self._add_label_value(self.dose_panel, label, i, "-" * 20)

        grid.AddGrowableCol(1, 0)

        dose_sizer.Add(grid, 0, flag=wx.EXPAND)

        btn_reset_dose = self.create_button(
            gen.GenButton,
            self.dose_panel,
            "Reset Dose",
            self.bold_font,
            lambda: self.reset_dose_handler and self.reset_dose_handler(),
            "The dose is automatically reset every 24 hours, but you can reset the daily dose at any time. The dose is saved automatically when you close the application or Save device profile.",
        )

        dose_sizer.Add(btn_reset_dose, 0, wx.ALL | wx.ALIGN_CENTER, 20)

        self.left_sizer.Add(self.dose_panel, 0, flag=wx.ALL | wx.EXPAND, border=10)

    def set_btn_bg(self, button: wx.Control, color: str) -> None:
        if button.GetBackgroundColour() != wx.Colour(color):
            button.SetBackgroundColour(wx.Colour(color))
            button.Refresh()

    def on_hover(self, e: wx.Event, button: wx.Control) -> None:
        if getattr(self, "is_shutting_down", False) or not wx.GetApp():
            return
        self.set_btn_bg(button, self.gui_theme.light_accent_color)

    def on_leave(self, e: wx.Event, button: wx.Control) -> None:
        if getattr(self, "is_shutting_down", False) or not wx.GetApp():
            return
        self.set_btn_bg(button, self.gui_theme.accent_color)

    def update_audio_metrics(self, metrics: AudioMetrics) -> None:
        labels = self.labels
        audio_metric_labels = self.audio_metric_labels
        metric_map = {
            labels[audio_metric_labels.integrated_db]: metrics["integrated_db"],
            labels[audio_metric_labels.short_term_db]: metrics["short_term_db"],
            labels[audio_metric_labels.momentary_db]: metrics["momentary_db"],
            labels[audio_metric_labels.peak_db]: metrics["peak_db"],
            labels[audio_metric_labels.current_stable_lufs]: metrics[
                "current_stable_lufs"
            ],
        }

        changed = False
        for st, metric in metric_map.items():
            match metric["spl_lvl"]:
                case SplLvl.DANGER:
                    color = wx.Colour(self.gui_theme.critical_color)
                case SplLvl.WARNING:
                    color = wx.Colour(self.gui_theme.warning_color)
                case SplLvl.SAFE:
                    color = wx.Colour(self.gui_theme.text_color)
                case _:
                    assert_never(metric["spl_lvl"])

            value_str = metric["value_str"]
            if st.GetLabel() != value_str:
                st.SetLabel(value_str)
                changed = True

            if st.GetForegroundColour() != color:
                st.SetForegroundColour(color)
                changed = True

        if changed:
            st.GetParent().Layout()

    def clear_notifications(self) -> None:
        """
        Clears all notifications
        """
        self.toaster.clear_toasts()

    def _show_toast(
        self,
        text_fields: list[str | None] | None = None,
        duration: ToastDuration = ToastDuration.Default,
        scenario: ToastScenario = ToastScenario.Default,
        on_activated_function: Callable[[], None] | None = None,
    ) -> None:
        """
        Internal helper for showing toast notifications

        :param text_fields: Text to show
        :type text_fields: list

        :param duration: Duration to show the toast for
        :type duration: ToastDuration

        :param scenario: Optional Scenario for the toast, e.g. Alarm, Reminder
        :type scenario: ToastScenario

        :param on_activated_function: Function to call when the notification is interacted with.
        :type on_activated_function: Callable[[], None]
        """
        if self.toaster:
            logger.info("[_show_toast] Clearing all application notifications.")
            self.clear_notifications()
            try:
                logo_image = ToastDisplayImage.fromPath(paths.LOGO_FILE)
                new_toast = Toast(
                    text_fields=text_fields,
                    images=[logo_image],
                    duration=duration,
                    scenario=scenario,
                    on_activated=lambda _: (
                        on_activated_function() if on_activated_function else None
                    ),
                )
                if scenario != ToastScenario.Default:
                    new_toast.AddAction(ToastButton("Dismiss", arguments="dismiss"))
                self.toaster.show_toast(new_toast)
                logger.info("[_show_toast] Showing Notification.")
            except Exception:
                logger.exception("[_show_toast] Could not show Notification.")
        else:
            logger.warning("[_show_toast] self.toaster invalid; Skipping notification.")

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
        duration = ToastDuration.Default  # shortest duration
        scenario = ToastScenario.Default
        text_fields: list[str | None] | None = None

        match notification:
            case NotifErrorEvent(device_name=device_name, error_type=error_type):
                match error_type:
                    case ErrorType.CONNECTION_LOST_RETRYING:
                        scenario = ToastScenario.Reminder
                        text_fields = [
                            "Project Sonus - Connection Lost - Retrying",
                            f"Lost connection to '{device_name}'. Actively trying to reconnect. Dose tracking is paused.",
                        ]
                    case ErrorType.CONNECTION_LOST_RETRY_FAILED:
                        scenario = ToastScenario.Reminder
                        text_fields = [
                            "Project Sonus - Connection Lost - Retry Attempts Failed",
                            f"Connection to '{device_name}' couldn't be recovered. Please manually inspect app. Dose tracking is paused.",
                        ]
                    case _:
                        assert_never(error_type)

            case NotifStatusEvent(
                device_name=device_name,
                status_type=StatusType.DEVICE_RECONNECTED,
            ):
                duration = ToastDuration.Short
                text_fields = [
                    "Project Sonus - Reconnected",
                    f"Successfully reconnected to '{device_name}'. Dose tracking has resumed.",
                ]
            case DoseStatus(
                dose_status=dose_status,
                daily_dose_consumed=daily_dose_consumed,
            ):
                rounded_dose = round(daily_dose_consumed)
                match dose_status:
                    case DoseStatusType.EXCEEDED:
                        scenario = ToastScenario.Reminder
                        text_fields = [
                            "Project Sonus - DOSE BUDGET EXCEEDED!",
                            f"Risk of Hearning Damage! Daily dose greater than {rounded_dose}%!",
                        ]
                    case DoseStatusType.DANGER:
                        duration = ToastDuration.Short
                        text_fields = [
                            "Project Sonus - DOSE WARNING!",
                            f"Lower Volume! Daily dose greater than {rounded_dose}%!",
                        ]
                    case DoseStatusType.WARNING:
                        duration = ToastDuration.Short
                        text_fields = [
                            "Project Sonus - Dose Alert.",
                            f"Daily Dose has exceeded {rounded_dose}%.",
                        ]
                    case DoseStatusType.SAFE:
                        raise ValueError(
                            "send_notification called with DoseStatusType.SAFE"
                        )
                    case _:
                        assert_never(dose_status)
            case _:
                assert_never(notification)

        self._show_toast(
            text_fields=text_fields,
            duration=duration,
            scenario=scenario,
            on_activated_function=callback,
        )

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
        if not self.settings_window:
            self.settings_window = SettingsFrame(
                self.overlay,
                self,
                mods,
                cast(str, trigger_key_str),
            )
        else:
            self.settings_window.hotkey_capture.Set(mods, trigger_key_str)

    def register_hotkey(self, register: bool, event: wx.Event | None = None) -> None:
        if self.is_shutting_down:
            return

        if self.settings_window is None:
            raise RuntimeError("settings_window accessed before initialization.")

        mods, key_str = self.settings_window.hotkey_capture.get_mods_and_trigger()
        if register and not (mods and key_str):
            return
        self._register_hotkey(register, mods, key_str)


class FlatSymbolButton(gen.GenButton):  # type: ignore[misc]
    def __init__(self, parent: wx.Panel, label: str, **kwargs: Any) -> None:
        super().__init__(parent, label=label, **kwargs)
        self.Fit()

    def DoGetBestSize(self) -> wx.Size:
        w, h = self.GetTextExtent(self.GetLabel())
        return wx.Size(w + 8, h)
