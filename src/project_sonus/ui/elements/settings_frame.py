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
import random
import time
from typing import TYPE_CHECKING
# ---------------------------------

# --- Third-Party Imports ---
import wx
import wx.lib.buttons as gen
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import HotkeyModifiers

from .overlay import Overlay
# ---------------------------------

# --- Type checking imports ---
if TYPE_CHECKING:
    from project_sonus.ui.ui import SonusUI
# ---------------------------------


class HotkeyCapture(wx.TextCtrl):  # type: ignore[misc]
    def __init__(
        self,
        parent: wx.Panel,
        default_mods: list[HotkeyModifiers] | None = None,
        default_trigger_key_str: str | None = None,
    ) -> None:
        super().__init__(parent, style=wx.TE_READONLY | wx.BORDER_NONE)
        self.modifiers: list[HotkeyModifiers] = default_mods or []
        self.key = default_trigger_key_str
        self.SetValue(self._display_text())
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def _display_text(self) -> str:
        mods_str = [mod.value for mod in self.modifiers]
        if self.key:
            return " + ".join(mods_str + [self.key])
        return " + ".join(mods_str)

    def on_key_down(self, event: wx.KeyEvent) -> None:
        self.modifiers = []
        key_code = event.GetKeyCode()

        if event.ControlDown():
            self.modifiers.append(HotkeyModifiers.CTRL)
        if event.ShiftDown():
            self.modifiers.append(HotkeyModifiers.SHIFT)
        if event.AltDown():
            self.modifiers.append(HotkeyModifiers.ALT)

        if key_code in [wx.WXK_CONTROL, wx.WXK_SHIFT, wx.WXK_ALT]:
            self.key = None
            self.SetValue(self._display_text())
            return

        if self.modifiers:
            if 32 <= key_code <= 126:
                self.key = chr(key_code).upper()
            else:
                self.key = None
        else:
            self.key = None

        self.SetValue(self._display_text())
        event.Skip()

    def Clear(self) -> None:
        self.modifiers = []
        self.key = None
        super().Clear()

    def Set(
        self,
        mods: list[HotkeyModifiers] | None,
        trigger_key_str: str | None,
    ) -> None:
        self.Clear()
        if mods and trigger_key_str:
            self.modifiers = mods
            self.key = trigger_key_str

    def get_mods_and_trigger(
        self,
    ) -> tuple[list[HotkeyModifiers], str] | tuple[None, None]:
        if self.modifiers and self.key:
            return self.modifiers, self.key
        else:
            return None, None


class SettingsFrame(wx.Frame):  # type: ignore[misc]
    def __init__(
        self,
        overlay_ref: Overlay,
        ui_ref: "SonusUI",
        hotkey_mods: list[HotkeyModifiers] | None = None,
        trigger_key_str: str = "K",
    ) -> None:
        if hotkey_mods is None:
            hotkey_mods = [HotkeyModifiers.CTRL, HotkeyModifiers.SHIFT]

        frame_style = (
            wx.DEFAULT_FRAME_STYLE & ~wx.MAXIMIZE_BOX & ~wx.RESIZE_BORDER
            | wx.STAY_ON_TOP
        )
        super().__init__(None, title="Overlay Settings", style=frame_style)

        self.ui_ref = ui_ref
        self.ui_ref.apply_dark_title_bar(self)
        self.overlay = overlay_ref
        self.overlay_unlocked = False
        self.simulating_spl = False

        self.SetIcon(self.ui_ref.icon)
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(self.ui_ref.gui_theme.bg_color))
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Position Controls
        sb1 = wx.StaticBox(panel, label="Positioning")
        sb1.SetFont(self.ui_ref.bold_font)
        sb1.SetForegroundColour(wx.Colour(self.ui_ref.gui_theme.text_color))
        sbs1 = wx.StaticBoxSizer(sb1, wx.VERTICAL)

        self.btn_unlock = self.ui_ref.create_button(
            gen.GenButton,
            panel,
            "Unlock / Move Overlay",
            self.ui_ref.bold_font,
            self.on_toggle_move,
        )
        sbs1.Add(self.btn_unlock, 0, wx.ALL | wx.EXPAND, 5)
        label = wx.StaticText(panel, label="(When unlocked, drag the overlay box)")
        label.SetFont(self.ui_ref.normal_font)
        label.SetForegroundColour(wx.Colour(self.ui_ref.gui_theme.text_color))
        sbs1.Add(label, 0, wx.ALL, 5)

        # Appearance Controls
        sb2 = wx.StaticBox(panel, label="Appearance")
        sb2.SetFont(self.ui_ref.bold_font)
        sb2.SetForegroundColour(wx.Colour(self.ui_ref.gui_theme.text_color))
        sbs2 = wx.StaticBoxSizer(sb2, wx.VERTICAL)

        # Mode Selection
        modes = ["Transparent Text Only", "Semi-Transparent Box"]
        self.radio_buttons = []
        for mode in modes:
            rb = wx.RadioButton(panel, label=mode)
            rb.SetCanFocus(False)
            rb.SetFont(self.ui_ref.normal_font)
            rb.SetForegroundColour(wx.Colour(self.ui_ref.gui_theme.text_color))
            rb.Bind(wx.EVT_RADIOBUTTON, self.on_update_style)
            sbs2.Add(rb, 0, wx.ALL, 5)
            self.radio_buttons.append(rb)
        self.radio_buttons[0].SetValue(self.overlay.transparent)
        self.radio_buttons[1].SetValue(not self.overlay.transparent)

        # Alpha Slider
        sb2 = wx.StaticText(panel, label="Box Opacity:")
        sb2.SetFont(self.ui_ref.normal_font)
        sb2.SetForegroundColour(wx.Colour(self.ui_ref.gui_theme.text_color))
        sbs2.Add(sb2, 0, wx.TOP | wx.LEFT, 5)
        self.slider_alpha = wx.Slider(
            panel, value=self.overlay.alpha, minValue=20, maxValue=255
        )
        self.slider_alpha.Bind(wx.EVT_SLIDER, self.on_update_style)
        label = wx.StaticText(
            panel, label="(Box Opacity only works with Semi-Transparent Box)"
        )
        label.SetFont(self.ui_ref.normal_font)
        label.SetForegroundColour(wx.Colour(self.ui_ref.gui_theme.text_color))
        sbs2.Add(self.slider_alpha, 0, wx.ALL | wx.EXPAND, 5)
        sbs2.Add(label, 0, wx.ALL | wx.EXPAND, 5)

        # Test Controls
        sb3 = wx.StaticBox(panel, label="Testing")
        sb3.SetFont(self.ui_ref.bold_font)
        sb3.SetForegroundColour(wx.Colour(self.ui_ref.gui_theme.text_color))
        sbs3 = wx.StaticBoxSizer(sb3, wx.VERTICAL)
        btn_test = self.ui_ref.create_button(
            gen.GenButton,
            panel,
            "Toggle: Simulate Random SPL",
            self.ui_ref.bold_font,
            self.on_simulate,
        )
        sbs3.Add(btn_test, 0, wx.ALL | wx.EXPAND, 5)

        # Hotkey Settings
        sb4 = wx.StaticBox(panel, label="Overlay Hotkey")
        sb4.SetFont(self.ui_ref.bold_font)
        sb4.SetForegroundColour(wx.Colour(self.ui_ref.gui_theme.text_color))
        sbs4 = wx.StaticBoxSizer(sb4, wx.VERTICAL)
        self.hotkey_capture = HotkeyCapture(
            panel,
            default_mods=hotkey_mods,
            default_trigger_key_str=trigger_key_str,
        )
        self.hotkey_capture.SetFont(self.ui_ref.normal_font)
        self.hotkey_capture.SetForegroundColour(
            wx.Colour(self.ui_ref.gui_theme.text_color)
        )
        self.hotkey_capture.SetBackgroundColour(
            wx.Colour(self.ui_ref.gui_theme.field_color)
        )
        btn = self.ui_ref.create_button(
            gen.GenButton,
            panel,
            "Register Hotkey",
            self.ui_ref.bold_font,
            lambda: self.ui_ref.register_hotkey(True),
        )
        btn2 = self.ui_ref.create_button(
            gen.GenButton,
            panel,
            "Unregister Hotkey",
            self.ui_ref.bold_font,
            lambda: self.ui_ref.register_hotkey(False),
        )
        sbs4.Add(self.hotkey_capture, 0, wx.ALL | wx.EXPAND, 5)
        sbs4.Add(btn, 0, wx.ALL | wx.EXPAND, 5)
        sbs4.Add(btn2, 0, wx.ALL | wx.EXPAND, 5)

        vbox.Add(sbs1, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(sbs2, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(sbs3, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(sbs4, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizerAndFit(vbox)
        self.SetClientSize(panel.GetSize())
        self.SetMinSize(self.GetSize())
        self.Bind(wx.EVT_CLOSE, lambda e: self.Hide())

    def on_toggle_move(self, event: wx.Event | None = None) -> None:
        if not self.overlay.IsShown():
            self.overlay.Show(save=True)
        self.overlay_unlocked = not self.overlay_unlocked
        if self.overlay_unlocked:
            self.btn_unlock.SetLabel("Lock Position (Click to Finish)")
            self.overlay.set_edit_mode(True)
        else:
            self.btn_unlock.SetLabel("Unlock / Move Overlay")
            self.overlay.set_edit_mode(False)

    def on_update_style(self, event: wx.Event | None = None) -> None:
        if not self.overlay.IsShown():
            self.overlay.Show(save=True)
        mode_idx = next(
            (i for i, rb in enumerate(self.radio_buttons) if rb.GetValue()), 0
        )
        transparent = mode_idx == 0
        alpha = self.slider_alpha.GetValue()

        self.overlay.set_visual_settings(transparent, alpha)

    def on_simulate(self, event: wx.Event | None = None) -> None:
        if self.simulating_spl:
            self.simulating_spl = False
            return

        if not self.overlay.IsShown():
            self.overlay.Show(save=True)

        end = time.time() + 6.0
        self.simulating_spl = True
        colors = [
            self.ui_ref.gui_theme.ok_color,
            self.ui_ref.gui_theme.warning_color,
            self.ui_ref.gui_theme.critical_color,
        ]
        color_index = 0

        def tick() -> None:
            nonlocal color_index
            if time.time() >= end or self.simulating_spl is False:
                self.simulating_spl = False
                return

            val = round(random.uniform(40.0, 100.0), 1)
            color = colors[color_index]

            self.overlay.update_spl(val, color)

            color_index = (color_index + 1) % len(colors)

            wx.CallLater(500, tick)

        wx.CallLater(0, tick)

    def Show(self, show: bool = True) -> bool:
        if show:
            main_x, main_y = self.ui_ref.frame.GetPosition()
            self.SetPosition(wx.Point(main_x, main_y))
            self.Raise()
            if not self.HasFocus():
                self.SetFocus()

        ret: bool = super().Show(show)
        return ret
