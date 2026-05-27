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
# ---------------------------------

# --- Third-Party Imports ---
import win32con
import win32gui
import wx
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import (
    USE_DEFAULT_DISPLAY,
    OverlayInfoDefaults,
    OverlayInfoKeys,
    PersistenceKeys,
)
from project_sonus.common.structures import OverlayInfo
from project_sonus.configuration.persistence import persistence_manager
# ---------------------------------


logger = logging.getLogger(__name__)


class Overlay(wx.Frame):  # type: ignore[misc]
    def __init__(self, font: wx.Font) -> None:
        super().__init__(
            None, style=wx.STAY_ON_TOP | wx.NO_BORDER | wx.FRAME_TOOL_WINDOW
        )

        self.font = font
        self.SetFont(self.font)

        self.is_dragging = False
        self.is_edit_mode = False

        self.info = persistence_manager.data.get(
            PersistenceKeys.OVERLAY,
            OverlayInfo(
                {
                    OverlayInfoKeys.DISPLAY_IDX.value: OverlayInfoDefaults.DISPLAY_IDX,
                    OverlayInfoKeys.REL_POS.value: OverlayInfoDefaults.REL_POS,
                    OverlayInfoKeys.TRANSPARENT.value: OverlayInfoDefaults.TRANSPARENT,
                    OverlayInfoKeys.BOX_OPACITY.value: OverlayInfoDefaults.BOX_OPACITY,
                    OverlayInfoKeys.SHOWING.value: OverlayInfoDefaults.SHOWING,
                }
            ),
        )

        self.transparent = self.info[OverlayInfoKeys.TRANSPARENT]
        self.alpha = max(
            20,
            int(255 * self.info[OverlayInfoKeys.BOX_OPACITY]),
        )
        self.spl_color = "#00FF00"
        self.dose_color = "#00FF00"

        self.spl_label = "Current SPL:"
        self.spl_val = "---"

        self.dose_label = "Time to 100% Dose:"
        self.dose_val = "---"

        self.max_spl_val = "888.8 dB"
        self.max_dose_val = "> 48 hours"

        self.padding_x = 10
        self.padding_y = 5
        self.column_gap = 15

        self.CHROMA_KEY = (1, 1, 1)

        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_PAINT, self.on_paint)

        self.SetDoubleBuffered(True)
        self.apply_styles()
        self.update_fixed_size()

        display_idx = self.info[OverlayInfoKeys.DISPLAY_IDX]
        if display_idx == USE_DEFAULT_DISPLAY:
            display_idx = wx.Display.GetFromPoint(wx.Point(0, 0))
            if display_idx == wx.NOT_FOUND:
                display_idx = 0

        display = wx.Display(display_idx)
        display_geometry = display.GetGeometry()

        rel_pos = self.info[OverlayInfoKeys.REL_POS]
        x_rel, y_rel = rel_pos
        win_w, win_h = self.GetSize()

        x = int(display_geometry.x + (display_geometry.width * x_rel) - (win_w * x_rel))
        y = int(
            display_geometry.y + (display_geometry.height * y_rel) - (win_h * y_rel)
        )

        self.SetPosition(wx.Point(x, y))

        self.topmost_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.enforce_topmost, self.topmost_timer)

        if self.info[OverlayInfoKeys.SHOWING]:
            self.ShowWithoutActivating()

    def get_layout_metrics(self, dc: wx.DC) -> tuple[int, int, int]:
        """
        Calculates layout based on the MOCK (Max) values,
        not the current values.
        """
        w_lbl_1, h1 = dc.GetTextExtent(self.spl_label)
        w_lbl_2, h2 = dc.GetTextExtent(self.dose_label)
        col_label_w = max(w_lbl_1, w_lbl_2)

        w_val_1, _ = dc.GetTextExtent(self.max_spl_val)
        w_val_2, _ = dc.GetTextExtent(self.max_dose_val)
        col_val_w = max(w_val_1, w_val_2)

        row_height = max(h1, h2)

        return col_label_w, col_val_w, row_height

    def update_fixed_size(self) -> None:
        """
        Sets the window size based on the max mock strings.
        This is only called during initialization or font changes.
        """
        dc = wx.ClientDC(self)
        dc.SetFont(self.font)

        col_lbl_w, col_val_w, row_h = self.get_layout_metrics(dc)

        total_w = (
            self.padding_x + col_lbl_w + self.column_gap + col_val_w + self.padding_x
        )
        total_h = self.padding_y + row_h + row_h + self.padding_y

        self.SetSize(wx.Size(total_w, total_h))

        self.cached_label_width = col_lbl_w
        self.cached_row_height = row_h

    def update_spl(self, value: float | str, color_hex: str | None = None) -> None:
        if isinstance(value, (float, int)):
            self.spl_val = f"{value:.1f} dB"
        else:
            self.spl_val = str(value)

        if color_hex:
            if isinstance(color_hex, str) and not color_hex.startswith("#"):
                color_hex = "#" + color_hex
            self.spl_color = color_hex

        self.Refresh()

    def update_dose_time(self, text: str, color_hex: str | None = None) -> None:
        self.dose_val = text

        if color_hex:
            if isinstance(color_hex, str) and not color_hex.startswith("#"):
                color_hex = "#" + color_hex
            self.dose_color = color_hex

        self.Refresh()

    def set_edit_mode(self, enable: bool) -> None:
        if not enable:
            self._save_pos()
        self.is_edit_mode = enable
        self.apply_styles()
        self.Refresh()

    def _save_pos(self) -> None:
        current_display_idx = wx.Display.GetFromWindow(self)

        if current_display_idx == wx.NOT_FOUND:
            current_display_idx = USE_DEFAULT_DISPLAY
            x_rel, y_rel = OverlayInfoDefaults.REL_POS

        else:
            win_x, win_y = self.GetPosition()
            win_w, win_h = self.GetSize()

            display = wx.Display(current_display_idx)
            display_geometry = display.GetGeometry()

            movable_width = max(1, display_geometry.width - win_w)
            movable_height = max(1, display_geometry.height - win_h)

            x_rel = (win_x - display_geometry.x) / movable_width
            y_rel = (win_y - display_geometry.y) / movable_height

            x_rel = max(0.0, min(1.0, x_rel))
            y_rel = max(0.0, min(1.0, y_rel))

        self.info[OverlayInfoKeys.DISPLAY_IDX] = current_display_idx
        self.info[OverlayInfoKeys.REL_POS] = [x_rel, y_rel]
        self.save_info()

    def set_visual_settings(self, transparent: bool, alpha: int) -> None:
        self.info[OverlayInfoKeys.TRANSPARENT] = transparent
        self.info[OverlayInfoKeys.BOX_OPACITY] = alpha / 255
        self.save_info()

        self.transparent = transparent
        self.alpha = alpha
        self.apply_styles()
        self.Refresh()

    def apply_styles(self) -> None:
        hwnd = self.GetHandle()
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        except Exception:
            return

        if self.is_edit_mode:
            style = style & ~win32con.WS_EX_TRANSPARENT
            style = style | win32con.WS_EX_LAYERED
            self.SetBackgroundColour(wx.Colour(50, 50, 50))
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
        else:
            style = (
                style
                | win32con.WS_EX_TRANSPARENT
                | win32con.WS_EX_LAYERED
                | win32con.WS_EX_NOACTIVATE
            )
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

            if self.transparent:
                self.SetBackgroundColour(wx.Colour(self.CHROMA_KEY))
                win32gui.SetLayeredWindowAttributes(
                    hwnd, 0x010101, 0, win32con.LWA_COLORKEY
                )
            else:
                self.SetBackgroundColour(wx.BLACK)
                win32gui.SetLayeredWindowAttributes(
                    hwnd, 0, self.alpha, win32con.LWA_ALPHA
                )

        self.Refresh()

    def on_paint(self, event: wx.Event) -> None:
        try:
            dc = wx.PaintDC(self)
            dc.SetFont(self.font)

            if self.is_edit_mode:
                dc.SetPen(wx.Pen(wx.Colour(255, 255, 0), 2))
                dc.SetBrush(wx.Brush(wx.Colour(50, 50, 50)))
                w, h = self.GetSize()
                dc.DrawRectangle(0, 0, w, h)
                dc.SetTextForeground(wx.Colour(255, 255, 255))
                dc.DrawText("DRAG ME", 5, 5)
            else:
                col_lbl_w, _, row_h = self.get_layout_metrics(dc)

                x_labels = self.padding_x
                x_values = self.padding_x + col_lbl_w + self.column_gap
                y_row1 = self.padding_y
                y_row2 = self.padding_y + row_h

                dc.SetTextForeground(wx.Colour(self.spl_color))
                dc.DrawText(self.spl_label, x_labels, y_row1)
                dc.DrawText(self.spl_val, x_values, y_row1)

                dc.SetTextForeground(wx.Colour(self.dose_color))
                dc.DrawText(self.dose_label, x_labels, y_row2)
                dc.DrawText(self.dose_val, x_values, y_row2)

        except Exception:
            logger.exception("[on_paint] Error in painting overlay.")
            return

    def on_left_down(self, event: wx.Event) -> None:
        if self.is_edit_mode:
            self.CaptureMouse()
            self.is_dragging = True
            pos = win32gui.GetCursorPos()
            origin = self.GetPosition()
            self.drag_start_offset = (pos[0] - origin[0], pos[1] - origin[1])

    def on_left_up(self, event: wx.Event) -> None:
        if self.is_dragging:
            if self.HasCapture():
                self.ReleaseMouse()
            self.is_dragging = False

    def on_motion(self, event: wx.MouseEvent) -> None:
        if self.is_dragging and event.Dragging():
            pos = win32gui.GetCursorPos()
            x = pos[0] - self.drag_start_offset[0]
            y = pos[1] - self.drag_start_offset[1]
            self.SetPosition(wx.Point(x, y))

    def enforce_topmost(self, event: wx.Event | None = None) -> None:
        if not self.is_dragging:
            hwnd = self.GetHandle()
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
            )

    def ShowWithoutActivating(self, save: bool = False) -> None:
        super().ShowWithoutActivating()
        if not self.topmost_timer.IsRunning():
            self.topmost_timer.Start(2000)
        self.enforce_topmost()
        if save:
            self.info[OverlayInfoKeys.SHOWING] = True
            self.save_info()

    def Show(self, show: bool = True, save: bool = False) -> bool:
        res: bool = super().Show(show)

        if show:
            if not self.topmost_timer.IsRunning():
                self.topmost_timer.Start(2000)
            self.enforce_topmost()
        else:
            self.topmost_timer.Stop()

        if save:
            self.info[OverlayInfoKeys.SHOWING] = show
            self.save_info()

        return res

    def Hide(self, save: bool = False) -> bool:
        return self.Show(False, save=save)

    def toggle(self) -> None:
        if self.IsShown():
            self.Hide(save=True)
        else:
            self.ShowWithoutActivating(save=True)

    def save_info(self) -> bool:
        persistence_manager.data[PersistenceKeys.OVERLAY] = self.info
        return persistence_manager.save()
