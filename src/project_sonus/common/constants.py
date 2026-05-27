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
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Literal, cast
# ---------------------------------

# --- Local Imports ---
from .structures import (
    ConfigKey,
    FrozenNamespace,
    HotkeyInfo,
    OverlayInfo,
    PersistenceKey,
    ProfileInfo,
)
# ---------------------------------

ALLOWED_JSON_PRIMITIVES = (str, int, float, bool, type(None))
ALLOWED_JSON_CONTAINERS = (list, dict)
ALLOWED_JSON_TYPES = ALLOWED_JSON_PRIMITIVES + ALLOWED_JSON_CONTAINERS

USE_DEFAULT_DISPLAY: Final[Literal[-1]] = -1


def _generate_frozen_namespace(classes: list[type]) -> FrozenNamespace[str, object]:
    _data: dict[str, object] = {}
    for c in classes:
        _data |= {k: v for k, v in c.__dict__.items() if not k.startswith("__")}
    return FrozenNamespace(_data)


class HotkeyModifiers(StrEnum):
    SHIFT = "SHIFT"
    CTRL = "CTRL"
    ALT = "ALT"


class _AppConstants:
    # Application Constants
    DOSE_HISTORY_WINDOW_SECONDS: Final[int] = 60
    VALID_ENTRY_ABS_LIMIT: Final[int] = 200
    RESTART_EXIT_CODE: Final[int] = 25
    MAX_CONNECTION_RETRIES: Final[int] = 5
    GUI_STABILITY_THRESHOLD_DB: Final[float] = 0.01
    HEARING_DAMAGE_DB_THRESHOLD: Final[float] = 85.0
    DANGEROUS_PEAK_DB_THRESHOLD: Final[float] = 135.0
    VOLUME_CALCULATOR_RED_TOLERANCE_DB: Final[float] = 6.0
    VOLUME_CALCULATOR_YELLOW_TOLERANCE_DB: Final[float] = 1.0
    AUDIO_BUFFER_SECONDS: Final[float] = 2.0
    DEFAULT_PRIMING_SECONDS: Final[float] = 0.01
    DEFAULT_VOLUME_CORRECTION: Final[bool] = False
    DEFAULT_TRUE_PEAK_EXPENSIVE_COMPUTATION: Final[bool] = False

    # EBU R 128 Loudness Constants
    REFERENCE_OFFSET: Final[float] = -0.691
    EPS: Final[float] = 1e-12

    # ITU-R BS.1770 Gating Thresholds
    ABS_GATE_LUFS: Final[float] = -70.0
    REL_GATE_LU: Final[float] = -10.0

    # NIOSH Constants
    DOSE_BASELINE_DB: Final[float] = 85.0
    DOSE_BASELINE_HOURS: Final[float] = 8.0
    DOSE_EXCHANGE_RATE_DB: Final[float] = 3.0

    # General Constants
    SECONDS_IN_A_DAY: Final[int] = 86400


if TYPE_CHECKING:

    class _AppConstants_Type(_AppConstants, FrozenNamespace[str, object]): ...


AppConstants = cast("_AppConstants_Type", _generate_frozen_namespace([_AppConstants]))


class _KeysBP[KT]:
    _KEY_TYPE: type[KT]
    _KEYS: tuple[KT, ...]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if "_KEYS" in cls.__dict__ and cls._KEYS:
            return

        key_type = None
        for base in getattr(cls, "__orig_bases__", []):
            if getattr(base, "__origin__", base) is _KeysBP:
                args = getattr(base, "__args__", ())
                if args:
                    key_type = args[0]
                    break

        if key_type is None:
            raise TypeError(
                f"{cls.__name__} must inherit from KeysBP with a generic argument."
            )

        cls._KEY_TYPE = key_type
        origin_type = getattr(key_type, "__origin__", key_type)

        keys = []
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue

            val = getattr(cls, attr_name)
            if isinstance(val, origin_type):
                keys.append(val)

        cls._KEYS = tuple(keys)

    def __iter__(self) -> Iterator[KT]:
        return iter(self._KEYS)


@dataclass(frozen=True, slots=True)
class _ProfileInfoKeys(_KeysBP[PersistenceKey[Any]]):
    BASELINE_DB: PersistenceKey[float] = PersistenceKey[float]("baseline_db")
    BASELINE_LUFS: PersistenceKey[float] = PersistenceKey[float]("baseline_lufs")
    VOLUME_CORRECTION: PersistenceKey[bool] = PersistenceKey[bool]("volume_correction")


ProfileInfoKeys = _ProfileInfoKeys()


@dataclass(frozen=True, slots=True)
class _HotkeyInfoKeys(_KeysBP[PersistenceKey[Any]]):
    MODIFIERS: PersistenceKey[list[str]] = PersistenceKey[list[str]]("modifiers")
    TRIGGER: PersistenceKey[str] = PersistenceKey[str]("trigger")


HotkeyInfoKeys = _HotkeyInfoKeys()


class _HotkeyInfoDefaults:
    MODIFIERS: Final[list[str]] = ["CTRL", "SHIFT"]
    TRIGGER: Final[str] = "K"


if TYPE_CHECKING:

    class _HotkeyInfoDefaults_Type(
        _HotkeyInfoDefaults, FrozenNamespace[str, object]
    ): ...


HotkeyInfoDefaults = cast(
    "_HotkeyInfoDefaults_Type", _generate_frozen_namespace([_HotkeyInfoDefaults])
)


@dataclass(frozen=True, slots=True)
class _OverlayInfoKeys(_KeysBP[PersistenceKey[Any]]):
    DISPLAY_IDX: PersistenceKey[int] = PersistenceKey[int]("display_idx")
    REL_POS: PersistenceKey[list[float]] = PersistenceKey[list[float]]("rel_pos")
    TRANSPARENT: PersistenceKey[bool] = PersistenceKey[bool]("transparent")
    BOX_OPACITY: PersistenceKey[float] = PersistenceKey[float]("box_opacity")
    SHOWING: PersistenceKey[bool] = PersistenceKey[bool]("showing")


OverlayInfoKeys = _OverlayInfoKeys()


class _OverlayInfoDefaults:
    DISPLAY_IDX: Final[int] = USE_DEFAULT_DISPLAY
    # [x, y] normalized coordinates relative to screen size.
    # 0.0 = Left/Top, 1.0 = Right/Bottom.
    REL_POS: Final[list[float]] = [1.0, 0.0]
    TRANSPARENT: Final[bool] = True
    BOX_OPACITY: Final[float] = 0.5
    SHOWING: Final[bool] = False


if TYPE_CHECKING:

    class _OverlayInfoDefaults_Type(
        _OverlayInfoDefaults, FrozenNamespace[str, object]
    ): ...


OverlayInfoDefaults = cast(
    "_OverlayInfoDefaults_Type", _generate_frozen_namespace([_OverlayInfoDefaults])
)


@dataclass(frozen=True, slots=True)
class _PersistenceKeys(_KeysBP[PersistenceKey[Any]]):
    LAST_DEVICE: PersistenceKey[str] = PersistenceKey[str]("last_device")
    PROFILES: PersistenceKey[dict[str, ProfileInfo]] = PersistenceKey[
        dict[str, ProfileInfo]
    ]("profiles")
    HOTKEYS: PersistenceKey[HotkeyInfo] = PersistenceKey[HotkeyInfo]("hotkeys")
    WINDOW_DISPLAY_IDX: PersistenceKey[int] = PersistenceKey[int]("window_display_idx")
    OVERLAY: PersistenceKey[OverlayInfo] = PersistenceKey[OverlayInfo]("overlay")


PersistenceKeys = _PersistenceKeys()


class _PersistenceDefaults:
    PROFILES: Final[dict[str, ProfileInfo]] = {}
    HOTKEYS: Final[HotkeyInfo] = HotkeyInfo(
        {
            HotkeyInfoKeys.MODIFIERS.value: HotkeyInfoDefaults.MODIFIERS,
            HotkeyInfoKeys.TRIGGER.value: HotkeyInfoDefaults.TRIGGER,
        }
    )
    WINDOW_DISPLAY_IDX: Final[int] = USE_DEFAULT_DISPLAY
    OVERLAY: Final[OverlayInfo] = OverlayInfo(
        {
            OverlayInfoKeys.DISPLAY_IDX.value: OverlayInfoDefaults.DISPLAY_IDX,
            OverlayInfoKeys.REL_POS.value: OverlayInfoDefaults.REL_POS,
            OverlayInfoKeys.TRANSPARENT.value: OverlayInfoDefaults.TRANSPARENT,
            OverlayInfoKeys.BOX_OPACITY.value: OverlayInfoDefaults.BOX_OPACITY,
            OverlayInfoKeys.SHOWING.value: OverlayInfoDefaults.SHOWING,
        }
    )


if TYPE_CHECKING:

    class _PersistenceDefaults_Type(
        _PersistenceDefaults, FrozenNamespace[str, object]
    ): ...


PersistenceDefaults = cast(
    "_PersistenceDefaults_Type", _generate_frozen_namespace([_PersistenceDefaults])
)


@dataclass(frozen=True, slots=True)
class _ConfigKeys(_KeysBP[ConfigKey[Any]]):
    # ---
    MIN_GUI_REFRESH: ConfigKey[int] = ConfigKey[int]("Min GUI Refresh Interval (ms)")
    MAX_GUI_REFRESH: ConfigKey[int] = ConfigKey[int]("Max GUI Refresh Interval (ms)")
    RESTART_INTERVAL: ConfigKey[float] = ConfigKey[float](
        "Application Auto-Restart Interval (hours)"
    )

    # ---
    SAMPLE_RATE: ConfigKey[int] = ConfigKey[int]("Sample Rate (Hz)")
    BLOCK_DURATION: ConfigKey[float] = ConfigKey[float]("Block Duration (ms)")
    TRUE_PEAK_EXPENSIVE: ConfigKey[bool] = ConfigKey[bool](
        "True Peak Expensive Computation"
    )
    DISCARD_DURATION: ConfigKey[float] = ConfigKey[float](
        "Initial Discard Duration (s)"
    )
    PRIMING_DURATION: ConfigKey[float] = ConfigKey[float](
        "Measurement Priming Duration (s)"
    )
    AUDIO_RETRY_DELAY: ConfigKey[float] = ConfigKey[float](
        "Audio Device Retry Delay (s)"
    )

    # ---
    CURRENT_SPL_WINDOW: ConfigKey[float] = ConfigKey[float]("Current SPL Window (s)")
    MOMENTARY_WINDOW: ConfigKey[float] = ConfigKey[float]("Momentary SPL Window (s)")
    SHORT_TERM_WINDOW: ConfigKey[float] = ConfigKey[float]("Short-Term SPL Window (s)")
    INTEGRATED_WINDOW: ConfigKey[float] = ConfigKey[float]("Integrated SPL Window (s)")

    # ---
    SILENCE_THRESHOLD: ConfigKey[float] = ConfigKey[float]("Silence Threshold")

    # ---
    DEFAULT_TARGET_SPL: ConfigKey[float] = ConfigKey[float](
        "Default Target SPL entry (dB)"
    )
    DEFAULT_SAFETY_BUFFER: ConfigKey[float] = ConfigKey[float](
        "Default Safety Buffer entry (dB)"
    )
    DEFAULT_BASELINE_DB: ConfigKey[float] = ConfigKey[float](
        "Default Baseline dB entry"
    )
    DEFAULT_BASELINE_LUFS: ConfigKey[float] = ConfigKey[float](
        "Default Baseline LUFS entry"
    )

    # ---
    VOL_DEC_TOLERANCE: ConfigKey[float] = ConfigKey[float](
        "Volume Decrease Tolerance (dB)"
    )
    VOL_INC_TOLERANCE: ConfigKey[float] = ConfigKey[float](
        "Volume Increase Tolerance (dB)"
    )

    # ---
    DOSE_ACCUM_THRESHOLD: ConfigKey[float] = ConfigKey[float](
        "Dose Accumulation Threshold (dB)"
    )

    # ---
    FONT_BOLD_NAME: ConfigKey[str] = ConfigKey[str]("Bold Font Name")
    FONT_BOLD_SIZE: ConfigKey[int] = ConfigKey[int]("Bold Font Size")
    FONT_NORMAL_NAME: ConfigKey[str] = ConfigKey[str]("Normal Font Name")
    FONT_NORMAL_SIZE: ConfigKey[int] = ConfigKey[int]("Normal Font Size")

    # ---
    BACKGROUND_COLOR: ConfigKey[str] = ConfigKey[str]("Background Color")
    ACCENT_COLOR: ConfigKey[str] = ConfigKey[str]("Accent Color")
    CRITICAL_COLOR: ConfigKey[str] = ConfigKey[str]("Critical Color")
    WARNING_COLOR: ConfigKey[str] = ConfigKey[str]("Warning Color")
    OK_COLOR: ConfigKey[str] = ConfigKey[str]("Safe/Ok Color")
    TEXT_COLOR: ConfigKey[str] = ConfigKey[str]("Text Color")
    FIELD_COLOR: ConfigKey[str] = ConfigKey[str]("Entry/Field Color")


ConfigKeys = _ConfigKeys()


class _ConfigDefaults:
    # ---
    MIN_GUI_REFRESH: Final[int] = 100
    MIN_GUI_REFRESH_MIN: Final[int] = 1
    MIN_GUI_REFRESH_MAX: Final[int] = 1000

    MAX_GUI_REFRESH: Final[int] = 500
    MAX_GUI_REFRESH_MIN: Final[int] = 1
    MAX_GUI_REFRESH_MAX: Final[int] = 2000

    RESTART_INTERVAL: Final[float] = 12.0
    RESTART_INTERVAL_MIN: Final[float] = 0.5
    RESTART_INTERVAL_MAX: Final[float] = 24.0

    # ---
    SAMPLE_RATE: Final[int] = 48000
    SAMPLE_RATE_MIN: Final[int] = 1
    SAMPLE_RATE_MAX: Final[int] = 256000

    BLOCK_DURATION: Final[float] = 50.0
    BLOCK_DURATION_MIN: Final[float] = 1.0
    BLOCK_DURATION_MAX: Final[float] = 5000.0

    TRUE_PEAK_EXPENSIVE: Final[bool] = False

    DISCARD_DURATION: Final[float] = 0.25
    DISCARD_DURATION_MIN: Final[float] = 0.25
    DISCARD_DURATION_MAX: Final[float] = 2.0

    PRIMING_DURATION: Final[float] = 1.25
    PRIMING_DURATION_MIN: Final[float] = 0.1
    PRIMING_DURATION_MAX: Final[float] = 10.0

    AUDIO_RETRY_DELAY: Final[float] = 3.0
    AUDIO_RETRY_DELAY_MIN: Final[float] = 0.1
    AUDIO_RETRY_DELAY_MAX: Final[float] = 120.0

    # ---
    CURRENT_SPL_WINDOW: Final[float] = 5.0
    CURRENT_SPL_WINDOW_MIN: Final[float] = 0.001
    CURRENT_SPL_WINDOW_MAX: Final[float] = 300.0

    MOMENTARY_WINDOW: Final[float] = 0.4
    MOMENTARY_WINDOW_MIN: Final[float] = 0.001
    MOMENTARY_WINDOW_MAX: Final[float] = 60.0

    SHORT_TERM_WINDOW: Final[float] = 3.0
    SHORT_TERM_WINDOW_MIN: Final[float] = 0.001
    SHORT_TERM_WINDOW_MAX: Final[float] = 3600.0

    INTEGRATED_WINDOW: Final[float] = 3600.0
    INTEGRATED_WINDOW_MIN: Final[float] = 0.001
    INTEGRATED_WINDOW_MAX: Final[float] = 86400.0

    # ---
    SILENCE_THRESHOLD: Final[float] = 0.0004
    SILENCE_THRESHOLD_MIN: Final[float] = 0.0
    SILENCE_THRESHOLD_MAX: Final[float] = 0.99

    # ---
    DEFAULT_TARGET_SPL: Final[float] = 75.0
    DEFAULT_TARGET_SPL_MIN: Final[float] = 1.0
    DEFAULT_TARGET_SPL_MAX: Final[float] = 120.0

    DEFAULT_SAFETY_BUFFER: Final[float] = 0.0
    DEFAULT_SAFETY_BUFFER_MIN: Final[float] = 0.0
    DEFAULT_SAFETY_BUFFER_MAX: Final[float] = 50.0

    DEFAULT_BASELINE_DB: Final[float] = 100.0
    DEFAULT_BASELINE_DB_MIN: Final[float] = 0.0
    DEFAULT_BASELINE_DB_MAX: Final[float] = 200.0

    DEFAULT_BASELINE_LUFS: Final[float] = 0.0
    DEFAULT_BASELINE_LUFS_MIN: Final[float] = -200.0
    DEFAULT_BASELINE_LUFS_MAX: Final[float] = 50.0

    # ---
    VOL_DEC_TOLERANCE: Final[float] = 1.0
    VOL_DEC_TOLERANCE_MIN: Final[float] = 0.0
    VOL_DEC_TOLERANCE_MAX: Final[float] = 24.0

    VOL_INC_TOLERANCE: Final[float] = 3.0
    VOL_INC_TOLERANCE_MIN: Final[float] = 0.0
    VOL_INC_TOLERANCE_MAX: Final[float] = 24.0

    # ---
    DOSE_ACCUM_THRESHOLD: Final[float] = 40.0
    DOSE_ACCUM_THRESHOLD_MIN: Final[float] = 0.0
    DOSE_ACCUM_THRESHOLD_MAX: Final[float] = 70.0

    # ---
    FONT_BOLD_NAME: Final[str] = "Consolas"

    FONT_BOLD_SIZE: Final[int] = 14
    FONT_BOLD_SIZE_MIN: Final[int] = 8
    FONT_BOLD_SIZE_MAX: Final[int] = 26

    FONT_NORMAL_NAME: Final[str] = "Consolas"

    FONT_NORMAL_SIZE: Final[int] = 12
    FONT_NORMAL_SIZE_MIN: Final[int] = 8
    FONT_NORMAL_SIZE_MAX: Final[int] = 26

    # ---
    BACKGROUND_COLOR: Final[str] = "#1c1c1c"
    ACCENT_COLOR: Final[str] = "#ff3333"
    CRITICAL_COLOR: Final[str] = "#ff3333"
    WARNING_COLOR: Final[str] = "#ffff00"
    OK_COLOR: Final[str] = "#32cd32"
    TEXT_COLOR: Final[str] = "#f0f0f0"
    FIELD_COLOR: Final[str] = "#3a3a3a"


if TYPE_CHECKING:

    class _ConfigDefaults_Type(_ConfigDefaults, FrozenNamespace[str, object]): ...


ConfigDefaults = cast(
    "_ConfigDefaults_Type", _generate_frozen_namespace([_ConfigDefaults])
)

for name, val in list(globals().items()):
    if isinstance(val, FrozenNamespace) and not val._name:
        object.__setattr__(val, "_name", name)
