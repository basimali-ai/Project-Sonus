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
from dataclasses import dataclass
from enum import Enum, auto
# ---------------------------------


class StatusType(Enum):
    DEVICE_RECONNECTED = auto()
    WAITING_AUDIO = auto()
    SCANNING_DEVICES = auto()
    CHANGING_DEVICE = auto()
    SAVE_SUCCESSFUL = auto()


class ErrorType(Enum):
    AUDIO_DEVICE_UNAVAILABLE = auto()
    CONNECTION_LOST_RETRYING = auto()
    CONNECTION_LOST_RETRY_FAILED = auto()
    SAVE_FAILED = auto()
    ENTRY_BASELINE = auto()
    ENTRY_TARGET = auto()


@dataclass(frozen=True, slots=True)
class Event:
    device_name: str | None = None
    attempt_str: str | None = None
