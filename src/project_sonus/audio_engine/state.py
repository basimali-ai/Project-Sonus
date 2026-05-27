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
from typing import Literal
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.state import ErrorType, Event, StatusType
# ---------------------------------

AudioCaptureStatusType = Literal[StatusType.DEVICE_RECONNECTED]
AudioCaptureErrorType = Literal[
    ErrorType.CONNECTION_LOST_RETRYING, ErrorType.CONNECTION_LOST_RETRY_FAILED
]


@dataclass(frozen=True, slots=True)
class AudioCaptureStatusEvent(Event):
    _: KW_ONLY
    status_type: AudioCaptureStatusType


@dataclass(frozen=True, slots=True)
class AudioCaptureErrorEvent(Event):
    _: KW_ONLY
    error_type: AudioCaptureErrorType
