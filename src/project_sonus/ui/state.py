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
from dataclasses import KW_ONLY, dataclass
from enum import Enum, StrEnum, auto
from typing import Literal, TypedDict
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.state import ErrorType, Event, StatusType
# ---------------------------------

DialogStatusType = Literal[StatusType.SAVE_SUCCESSFUL]
DialogErrorType = Literal[ErrorType.CONNECTION_LOST_RETRY_FAILED, ErrorType.SAVE_FAILED]

NotifStatusType = Literal[StatusType.DEVICE_RECONNECTED]
NotifErrorType = Literal[
    ErrorType.CONNECTION_LOST_RETRYING, ErrorType.CONNECTION_LOST_RETRY_FAILED
]

VolCalcStatusType = Literal[
    StatusType.WAITING_AUDIO, StatusType.SCANNING_DEVICES, StatusType.CHANGING_DEVICE
]
VolCalcErrorType = Literal[
    ErrorType.AUDIO_DEVICE_UNAVAILABLE,
    ErrorType.CONNECTION_LOST_RETRYING,
    ErrorType.CONNECTION_LOST_RETRY_FAILED,
    ErrorType.ENTRY_BASELINE,
    ErrorType.ENTRY_TARGET,
]


@dataclass(frozen=True, slots=True)
class DialogStatusEvent(Event):
    _: KW_ONLY
    status_type: DialogStatusType


@dataclass(frozen=True, slots=True)
class DialogErrorEvent(Event):
    _: KW_ONLY
    error_type: DialogErrorType


@dataclass(frozen=True, slots=True)
class NotifStatusEvent(Event):
    _: KW_ONLY
    status_type: NotifStatusType


@dataclass(frozen=True, slots=True)
class NotifErrorEvent(Event):
    _: KW_ONLY
    error_type: NotifErrorType


@dataclass(frozen=True, slots=True)
class VolCalcStatusEvent(Event):
    _: KW_ONLY
    status_type: VolCalcStatusType


@dataclass(frozen=True, slots=True)
class VolCalcErrorEvent(Event):
    _: KW_ONLY
    error_type: VolCalcErrorType


class UserEntriesEnum(StrEnum):
    TARGET_DB = "target_db"
    SAFETY_BUFFER_DB = "safety_buffer_db"
    BASELINE_DB = "baseline_db"
    BASELINE_LUFS = "baseline_lufs"


@dataclass(frozen=True, slots=True)
class UserInputData:
    target_device: str
    entries_data: dict[UserEntriesEnum, float | None]


class SplLvl(Enum):
    DANGER = auto()
    WARNING = auto()
    SAFE = auto()


class VolLvl(Enum):
    CORRECT = auto()
    INCREASE = auto()
    DECREASE = auto()


class AckType(Enum):
    RESET_METRICS = auto()
    RESET_DOSE = auto()


class DoseStatusType(Enum):
    EXCEEDED = auto()
    DANGER = auto()
    WARNING = auto()
    SAFE = auto()


@dataclass(frozen=True, slots=True)
class Calibrating:
    wait_seconds: float


@dataclass(frozen=True, slots=True)
class VolCalcStatus:
    current_spl: float
    required_change: float | None = None
    _: KW_ONLY
    spl_level: SplLvl
    volume_level: VolLvl


@dataclass(frozen=True, slots=True)
class Ack:
    ack_type: AckType


class AudioMetric(TypedDict):
    value_str: str
    spl_lvl: SplLvl


class AudioMetrics(TypedDict):
    integrated_db: AudioMetric
    short_term_db: AudioMetric
    momentary_db: AudioMetric
    peak_db: AudioMetric
    current_stable_lufs: AudioMetric


@dataclass(frozen=True, slots=True)
class DoseStatus:
    """
    Represents the daily dose status.

    :param dose_status: The status of the dose.
    :type dose_status: :class:`DoseStatusType`

    :param daily_dose_consumed: Daily dose consumed as a percentage (0 to 100).
    :type daily_dose_consumed: float

    :param time_to_fill_str: Time remaining to reach 100% dose, preformatted for direct display.
    :type time_to_fill_str: str
    """

    dose_status: DoseStatusType
    daily_dose_consumed: float
    time_to_fill_str: str
