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
from collections.abc import Callable
from typing import Any
# ---------------------------------

# --- Third-Party Imports ---
import wx
import wx.lib.buttons as gen
# ---------------------------------


class ThemedVListBox(wx.VListBox):  # type: ignore[misc]
    """
    The popup list content.
    """

    def __init__(
        self,
        parent: wx.PopupTransientWindow,
        choices: list[str],
        bg_color: str,
        fg_color: str,
        hl_bg_color: str,
        hl_fg_color: str,
        font: wx.Font,
        char_limit: int | None = None,
    ) -> None:
        super().__init__(parent, style=wx.BORDER_NONE)
        self.choices = choices
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hl_bg_color = hl_bg_color
        self.hl_fg_color = hl_fg_color
        self.font = font
        self.char_limit = char_limit
        self.last_tooltip_item = -1

        self.row_height = self._calculate_row_height()
        self.SetItemCount(len(self.choices))

        self.Bind(wx.EVT_LEFT_UP, self.on_click)
        self.Bind(wx.EVT_MOTION, self.on_mouse_move)

    def _calculate_row_height(self) -> int:
        dc = wx.ScreenDC()
        dc.SetFont(self.font)
        size = dc.GetTextExtent("Wg")
        h: int = size.GetHeight()
        return h + 10

    def OnMeasureItem(self, n: int) -> int:
        return self.row_height

    def OnDrawItem(self, dc: wx.DC, rect: wx.Rect, n: int) -> None:
        is_selected = self.GetSelection() == n
        bg = self.hl_bg_color if is_selected else self.bg_color
        fg = self.hl_fg_color if is_selected else self.fg_color

        dc.SetBrush(wx.Brush(wx.Colour(bg)))
        dc.SetPen(wx.Pen(wx.Colour(bg)))
        dc.DrawRectangle(rect)

        dc.SetFont(self.font)
        dc.SetTextForeground(wx.Colour(fg))

        full_text = self.choices[n] if n < len(self.choices) else ""

        if self.char_limit and len(full_text) > self.char_limit:
            display_text = full_text[: self.char_limit] + "..."
        else:
            display_text = full_text

        _, text_h = dc.GetTextExtent(display_text)
        y_pos = rect.y + (rect.height - text_h) // 2
        dc.DrawText(display_text, rect.x + 10, y_pos)

    def on_click(self, event: wx.Event) -> None:
        item = self.VirtualHitTest(event.GetPosition().y)
        if item != wx.NOT_FOUND:
            self.SetSelection(item)
            self.Refresh()
            evt = wx.CommandEvent(wx.EVT_LISTBOX.typeId, self.GetId())
            evt.SetEventObject(self)
            wx.PostEvent(self.GetParent(), evt)

    def on_mouse_move(self, event: wx.Event) -> None:
        pos = event.GetPosition()
        item = self.VirtualHitTest(pos.y)

        if item != self.last_tooltip_item:
            self.last_tooltip_item = item
            if item != wx.NOT_FOUND:
                text = self.choices[item]
                if self.char_limit and len(text) > self.char_limit:
                    self.SetToolTip(text)
                else:
                    self.UnsetToolTip()
            else:
                self.UnsetToolTip()

        if item != wx.NOT_FOUND and item != self.GetSelection():
            self.SetSelection(item)
            self.Refresh()


class DropdownBtn(gen.GenButton):  # type: ignore[misc]
    """
    A custom button that looks like a dropdown face.
    """

    def __init__(
        self, parent: wx.Panel, label: str, char_limit: int | None = None, **kwargs: Any
    ) -> None:
        self.char_limit = char_limit
        super().__init__(parent, label=label, **kwargs)

    def DoGetBestSize(self) -> wx.Size:
        """
        Calculate the size based on the char_limit.
        """
        dc = wx.ClientDC(self)
        dc.SetFont(self.GetFont())

        if self.char_limit:
            measure_str = "W" * self.char_limit + "..."
        else:
            measure_str = self.GetLabel()
            if len(measure_str) < 5:
                measure_str = "WWWWW"

        w, h = dc.GetTextExtent(measure_str)

        total_w = w + 30
        total_h = h + 14

        return wx.Size(total_w, total_h)

    def DrawLabel(
        self, dc: wx.DC, width: int, height: int, dx: int = 0, dy: int = 0
    ) -> None:
        dc.SetFont(self.GetFont())
        if self.IsEnabled():
            dc.SetTextForeground(self.GetForegroundColour())
        else:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        arrow_w = 10
        arrow_h = 6
        arrow_x = width - arrow_w - 10
        arrow_y = (height - arrow_h) // 2

        pt1 = (arrow_x, arrow_y)
        pt2 = (arrow_x + arrow_w, arrow_y)
        pt3 = (arrow_x + (arrow_w // 2), arrow_y + arrow_h)

        dc.SetBrush(wx.Brush(self.GetForegroundColour()))
        dc.SetPen(wx.Pen(self.GetForegroundColour()))
        dc.DrawPolygon([pt1, pt2, pt3])

        full_label = self.GetLabel()

        if self.char_limit and len(full_label) > self.char_limit:
            display_label = full_label[: self.char_limit] + "..."
        else:
            display_label = full_label

        _, text_h = dc.GetTextExtent(display_label)
        text_y = (height - text_h) // 2

        dc.DrawText(display_label, 10, text_y)


class ThemedComboBox(wx.Panel):  # type: ignore[misc]
    def __init__(
        self,
        parent: wx.Panel,
        choices: list[str],
        default: str | None = None,
        char_limit: int = 35,
        bg_color: str = "#3a3a3a",
        fg_color: str = "#f0f0f0",
        hover_bg_color: str = "#505050",
        sel_bg_color: str = "#ff3333",
        font: wx.Font | None = None,
    ) -> None:
        super().__init__(parent)

        self.choices = choices
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hover_bg_color = hover_bg_color
        self.sel_bg_color = sel_bg_color
        self.font = font or wx.Font(
            10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        )
        self.char_limit = char_limit
        self.on_change: Callable[[str], None] | None = None

        self.value = default if default else (choices[0] if choices else "")

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.sizer)

        self.btn = DropdownBtn(
            self,
            label=self.value,
            char_limit=self.char_limit,
            style=wx.BORDER_NONE,
        )
        self.btn.SetBackgroundColour(wx.Colour(self.bg_color))
        self.btn.SetForegroundColour(wx.Colour(self.fg_color))
        self.btn.SetFont(self.font)
        self.btn.SetBezelWidth(0)
        self.btn.SetUseFocusIndicator(False)

        self._update_btn_tooltip()

        self.btn.Bind(wx.EVT_BUTTON, self.on_toggle_dropdown)
        self.btn.Bind(wx.EVT_ENTER_WINDOW, self.on_btn_hover)
        self.btn.Bind(wx.EVT_LEAVE_WINDOW, self.on_btn_leave)

        self.sizer.Add(self.btn, 1, wx.EXPAND)

        self.popup = wx.PopupTransientWindow(self)
        self.popup_sizer = wx.BoxSizer(wx.VERTICAL)
        self.popup.SetSizer(self.popup_sizer)

        self.listbox = ThemedVListBox(
            self.popup,
            choices=self.choices,
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            hl_bg_color=self.sel_bg_color,
            hl_fg_color=self.fg_color,
            font=self.font,
            char_limit=self.char_limit,
        )

        self.popup.Bind(wx.EVT_LISTBOX, self.on_select)
        self.popup_sizer.Add(self.listbox, 1, wx.EXPAND)

    def _update_btn_tooltip(self) -> None:
        """Only show tooltip on the button if the value is truncated."""
        if self.char_limit and len(self.value) > self.char_limit:
            self.btn.SetToolTip(self.value)
        else:
            self.btn.UnsetToolTip()

    def on_btn_hover(self, event: wx.Event) -> None:
        self.btn.SetBackgroundColour(wx.Colour(self.hover_bg_color))
        self.btn.Refresh()

    def on_btn_leave(self, event: wx.Event) -> None:
        self.btn.SetBackgroundColour(wx.Colour(self.bg_color))
        self.btn.Refresh()

    def on_toggle_dropdown(self, event: wx.Event) -> None:
        if not self.choices:
            return

        if self.popup.IsShown():
            self.popup.Dismiss()
        else:
            self._show_popup()

    def _show_popup(self) -> None:
        btn_size = self.btn.GetSize()
        total_h = self.listbox.row_height * len(self.choices)
        popup_height = min(total_h, 300)

        self.listbox.SetMinSize(wx.Size(btn_size.width, popup_height))
        self.popup.SetSize(wx.Size(btn_size.width, popup_height))
        self.popup.Layout()

        pos = self.btn.ClientToScreen(wx.Point(0, btn_size.height))
        self.popup.SetPosition(pos)

        if self.value in self.choices:
            idx = self.choices.index(self.value)
            self.listbox.SetSelection(idx)

        self.popup.Popup()
        self.listbox.SetFocus()

    def on_select(self, event: wx.Event) -> None:
        idx = self.listbox.GetSelection()
        if idx != -1:
            self.value = self.choices[idx]
            self.btn.SetLabel(self.value)
            self._update_btn_tooltip()
            self.btn.Refresh()
            self.popup.Dismiss()

            if self.on_change and callable(self.on_change):
                self.on_change(self.value)

    def GetValue(self) -> str:
        return self.value

    def GetValues(self) -> list[str]:
        """
        Returns the list of choices currently available in the dropdown.
        """
        return self.choices

    def BindOnChange(self, callback: Callable[[str], None]) -> None:
        self.on_change = callback

    def SetChoices(self, choices: list[str]) -> None:
        self.choices = choices
        self.listbox.choices = choices
        if not hasattr(self.listbox, "row_height"):
            self.listbox.row_height = self.listbox._calculate_row_height()
        self.listbox.SetItemCount(len(choices))
        self.listbox.Refresh()

        if choices:
            if self.value not in choices:
                self.value = choices[0]
                self.btn.SetLabel(self.value)
                self._update_btn_tooltip()
                self.btn.Refresh()
        else:
            self.value = ""
            self.btn.SetLabel("")
            self.btn.UnsetToolTip()
            self.btn.Refresh()

    def Enable(self, enable: bool = True) -> bool:
        """
        Enables or disables the combobox.
        When disabled (enable=False), the button ignores clicks and text turns gray.
        """
        if not enable and self.popup.IsShown():
            self.popup.Dismiss()

        self.btn.Enable(enable)
        super().Enable(enable)

        self.btn.Refresh()
        return enable

    def SetValue(self, value: str) -> None:
        """
        Sets the value.
        Does not trigger the on_change callback (standard wxPython behavior).
        """
        self.value = value
        self.btn.SetLabel(value)
        self._update_btn_tooltip()

        if value in self.choices:
            idx = self.choices.index(value)
            self.listbox.SetSelection(idx)
        else:
            self.listbox.SetSelection(wx.NOT_FOUND)

        self.btn.Refresh()
