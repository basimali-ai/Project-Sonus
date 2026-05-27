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
from typing import TYPE_CHECKING, Literal
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import ConfigKeys
# ---------------------------------

# --- Type checking imports ---
if TYPE_CHECKING:
    from project_sonus.configuration.config_manager import ConfigManager
# ---------------------------------


def adjust_color(
    hex_color: str,
    factor: float = 0.2,
    mode: Literal["darken", "lighten"] = "darken",
) -> str:
    """
    Adjust a hex color's brightness.

    :param hex_color: Hex color (e.g. "#ff3333")
    :type hex_color: str

    :param factor: Amount (0–1) to darken or lighten
    :type factor: float

    :param mode: "darken" or "lighten"
    :type mode: Literal["darken", "lighten"]

    :return: Adjusted hex color
    :rtype: str
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    if mode == "darken":
        r, g, b = (int(c * (1 - factor)) for c in (r, g, b))
    elif mode == "lighten":
        r, g, b = (int(c + (255 - c) * factor) for c in (r, g, b))
    else:
        raise ValueError("mode must be 'darken' or 'lighten'")

    return f"#{r:02x}{g:02x}{b:02x}"


class GUITheme:
    __slots__ = (
        "accent_color",
        "bg_color",
        "critical_color",
        "dark_field_color",
        "field_color",
        "font_bold",
        "font_normal",
        "gray_color",
        "light_accent_color",
        "ok_color",
        "text_color",
        "warning_color",
    )

    def __init__(self, config: "ConfigManager") -> None:
        self.font_bold = (
            config.get_from_config(ConfigKeys.FONT_BOLD_NAME),
            config.get_from_config(ConfigKeys.FONT_BOLD_SIZE),
        )
        self.font_normal = (
            config.get_from_config(ConfigKeys.FONT_NORMAL_NAME),
            config.get_from_config(ConfigKeys.FONT_NORMAL_SIZE),
        )

        self.bg_color = config.get_from_config(ConfigKeys.BACKGROUND_COLOR)
        self.accent_color = config.get_from_config(ConfigKeys.ACCENT_COLOR)
        self.light_accent_color = adjust_color(self.accent_color, 0.2, "lighten")
        self.gray_color = "#808080"
        self.critical_color = config.get_from_config(ConfigKeys.CRITICAL_COLOR)
        self.warning_color = config.get_from_config(ConfigKeys.WARNING_COLOR)
        self.ok_color = config.get_from_config(ConfigKeys.OK_COLOR)
        self.text_color = config.get_from_config(ConfigKeys.TEXT_COLOR)
        self.field_color = config.get_from_config(ConfigKeys.FIELD_COLOR)
        self.dark_field_color = adjust_color(self.field_color, 0.3, "darken")
