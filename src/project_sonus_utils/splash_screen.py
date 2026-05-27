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
import ctypes
import logging
import struct
from collections.abc import Callable
# ---------------------------------

# --- Third-Party Imports ---
import numpy as np
import wx
from PIL import Image
# ---------------------------------

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

ULW_ALPHA = 0x00000002
AC_SRC_ALPHA = 0x01
AC_SRC_OVER = 0x00
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x20
GWL_EXSTYLE = -20


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class SplashScreen:
    """
    A modular splash/overlay window that supports alpha transparency.
    Offers a callback function to return control.
    """

    __slots__ = (
        "app",
        "click_through",
        "frame",
        "grab_focus",
        "height",
        "image_path",
        "position",
        "width",
    )

    def __init__(
        self,
        width: int = 512,
        height: int = 512,
        image_path: str | None = None,
        click_through: bool = False,
        grab_focus: bool = True,
        position: tuple[int, int] | list[int] | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.image_path = image_path
        self.click_through = click_through
        self.grab_focus = grab_focus
        self.position = position
        self.app: wx.App | None = None
        self.frame: wx.Frame | None = None

    def _premultiply_alpha(self, pil_img: Image.Image) -> bytes:
        """
        Windows UpdateLayeredWindow requires 'pre-multiplied alpha'.
        R = (R * A) / 255, etc.
        Also converts to BGRA (Windows standard).
        """
        img = pil_img.convert("RGBA")

        r, g, b, a = img.split()

        arr_r = np.array(r, dtype=np.uint16)
        arr_g = np.array(g, dtype=np.uint16)
        arr_b = np.array(b, dtype=np.uint16)
        arr_a = np.array(a, dtype=np.uint16)

        arr_r = (arr_r * arr_a) // 255
        arr_g = (arr_g * arr_a) // 255
        arr_b = (arr_b * arr_a) // 255

        bgra = np.dstack(
            (
                arr_b.astype(np.uint8),
                arr_g.astype(np.uint8),
                arr_r.astype(np.uint8),
                arr_a.astype(np.uint8),
            )
        )
        return bgra.flatten().tobytes()

    def _set_layered_window_bitmap(self) -> None:
        """Loads image and calls UpdateLayeredWindow."""
        if not self.frame:
            logger.warning(
                "[SplashScreen] `_set_layered_window_bitmap` called when "
                "self.frame does not exist."
            )
            return

        if not self.image_path:
            logger.warning(
                "[SplashScreen] `_set_layered_window_bitmap` called when "
                "self.image_path does not exist, image will not be shown."
            )
            return

        try:
            pil_img = Image.open(self.image_path).resize(
                (self.width, self.height), Image.Resampling.LANCZOS
            )
            img_data = self._premultiply_alpha(pil_img)

            hwnd = self.frame.GetHandle()
            h_screen_dc = user32.GetDC(0)
            h_mem_dc = gdi32.CreateCompatibleDC(h_screen_dc)

            bmi = ctypes.create_string_buffer(40)
            # Use -self.height to tell Windows the data is Top-Down
            # 'IiiHHIIIIII' corresponds to:
            # biSize(I), biWidth(i), biHeight(i), biPlanes(H), biBitCount(H), Compression(I)...
            struct.pack_into(
                "IiiHHIIIIII",
                bmi,
                0,
                40,
                self.width,
                -self.height,
                1,
                32,
                0,
                0,
                0,
                0,
                0,
                0,
            )

            pvBits = ctypes.c_void_p()
            h_bitmap = gdi32.CreateDIBSection(
                h_mem_dc, bmi, 0, ctypes.byref(pvBits), 0, 0
            )
            ctypes.memmove(pvBits, img_data, len(img_data))

            old_bitmap = gdi32.SelectObject(h_mem_dc, h_bitmap)
            ptSrc = POINT(0, 0)

            # Note: Must ensure layout is calculated before getting rect
            rect = self.frame.GetRect()
            ptDst = POINT(rect.x, rect.y)
            wSize = SIZE(self.width, self.height)

            blend = BLENDFUNCTION()
            blend.BlendOp = AC_SRC_OVER
            blend.BlendFlags = 0
            blend.SourceConstantAlpha = 255
            blend.AlphaFormat = AC_SRC_ALPHA

            user32.UpdateLayeredWindow(
                hwnd,
                h_screen_dc,
                ctypes.byref(ptDst),
                ctypes.byref(wSize),
                h_mem_dc,
                ctypes.byref(ptSrc),
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            )

            gdi32.SelectObject(h_mem_dc, old_bitmap)
            gdi32.DeleteObject(h_bitmap)
            gdi32.DeleteDC(h_mem_dc)
            user32.ReleaseDC(0, h_screen_dc)

        except Exception:
            logger.exception("[SplashScreen] Failed to update layered window.")

    def show(self, callback: Callable[[], None] | None = None) -> None:
        self.app = wx.App(False)
        self.frame = wx.Frame(
            None, style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.NO_BORDER
        )

        hwnd = self.frame.GetHandle()
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_style = ex_style | WS_EX_LAYERED | WS_EX_NOACTIVATE

        if self.click_through:
            new_style |= WS_EX_TRANSPARENT

        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

        self.frame.SetSize(self.width, self.height)
        if self.position:
            self.set_position(self.position[0], self.position[1])
        else:
            self.frame.SetPosition(wx.Point(self._center_pos()))

        if self.image_path:
            self._set_layered_window_bitmap()

        if self.grab_focus:
            self.frame.Show(True)
        else:
            self.frame.ShowWithoutActivating()

        logger.info("[SplashScreen] Splash is visible.")
        if callback:
            wx.CallAfter(callback)
        self.app.MainLoop()

    def hide(self) -> None:
        """Hides the splash window immediately."""
        if not self.frame:
            logger.warning(
                "[SplashScreen] `hide` called when self.frame does not exist."
            )
            return

        wx.CallAfter(self.frame.Hide)

    def set_position(self, x: int, y: int) -> None:
        if not self.frame:
            logger.warning(
                "[SplashScreen] `set_position` called when self.frame does not exist."
            )
            return

        wx.CallAfter(self.frame.SetPosition, wx.Point(x, y))

    def destroy(self) -> None:
        if self.frame:
            wx.CallAfter(self.frame.Destroy)
        if self.app:
            wx.CallAfter(self.app.ExitMainLoop)

    def _center_pos(self) -> tuple[int, int]:
        sw, sh = wx.DisplaySize()
        x = (sw - self.width) // 2
        y = (sh - self.height) // 2
        return (x, y)

    def _make_click_through(self) -> None:
        if not self.frame:
            logger.warning(
                "[SplashScreen] `_make_click_through` called when "
                "self.frame does not exist."
            )
            return

        try:
            hwnd = self.frame.GetHandle()
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT)
        except Exception:
            logger.warning("[SplashScreen] Exception in `_make_click_through`.")
