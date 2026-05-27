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
import atexit
import logging
import threading
from typing import TYPE_CHECKING
# ---------------------------------

# --- Third-Party Imports ---
from comtypes import (
    COINIT_APARTMENTTHREADED,
    COINIT_MULTITHREADED,
    CoInitializeEx,
    CoUninitialize,
)

# - Explicit COM init, and uninit registering at application exit -
CoInitializeEx(COINIT_APARTMENTTHREADED)
logger = logging.getLogger(__name__)
logger.info("COM apartment explicitly initialized.")


def _shutdown_com() -> None:
    try:
        CoUninitialize()
        logger.info("COM apartment explicitly uninitialized.")
    except Exception:
        logger.exception("COM uninit failed.")


atexit.register(_shutdown_com)
# --------

import numpy as np
import soundcard as sc
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import AppConstants
from project_sonus.common.state import ErrorType, StatusType

from .state import AudioCaptureErrorEvent, AudioCaptureStatusEvent
# ---------------------------------

# --- Type checking imports ---
if TYPE_CHECKING:
    from queue import Queue

    from numcircbuf import BlockingCircBuffer
# ---------------------------------


class AudioCaptureWorker:
    __slots__ = (
        "MAX_CONNECTION_RETRIES",
        "_stop_event",
        "_thread",
        "audio_buffer",
        "audio_retry_delay",
        "block_size",
        "device_name",
        "error_queue",
        "sample_rate",
    )

    def __init__(
        self,
        audio_buffer: "BlockingCircBuffer",
        error_queue: "Queue[AudioCaptureErrorEvent | AudioCaptureStatusEvent | None]",
        device_name: str,
        sample_rate: int,
        block_size: int,
        audio_retry_delay: float,
    ) -> None:
        self.audio_buffer = audio_buffer
        self.error_queue = error_queue
        self.device_name = device_name

        self.sample_rate = sample_rate
        self.block_size = block_size

        self.audio_retry_delay = audio_retry_delay
        self.MAX_CONNECTION_RETRIES: int = AppConstants.MAX_CONNECTION_RETRIES

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._stop_event.is_set():
            logger.info(f"[stop] Stop command issued for worker '{self.device_name}'.")
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
            if self._thread.is_alive():
                logger.warning(
                    f"[stop] Timed out waiting for worker '{self.device_name}' to stop. It may still be running."
                )
            else:
                logger.info(
                    f"[stop] Successfully joined worker thread for '{self.device_name}'."
                )

    def _run(self) -> None:
        """
        Captures audio with an informed, limited retry mechanism.
        Communicates its state (retrying, reconnected, failed) to the controller.
        """
        CoInitializeEx(COINIT_MULTITHREADED)
        consecutive_failures = 0

        try:
            while not self._stop_event.is_set():
                try:
                    target_mic = sc.get_microphone(
                        id=self.device_name, include_loopback=True
                    )

                    with target_mic.recorder(
                        samplerate=self.sample_rate,
                        blocksize=self.block_size,
                        exclusive_mode=False,
                    ) as mic:
                        if consecutive_failures > 0:
                            self.error_queue.put(
                                AudioCaptureStatusEvent(
                                    device_name=self.device_name,
                                    status_type=StatusType.DEVICE_RECONNECTED,
                                )
                            )

                        logger.info(
                            f"[_run] Audio stream started for '{self.device_name}'."
                        )
                        consecutive_failures = 0

                        while not self._stop_event.is_set():
                            samples = mic.record(numframes=self.block_size)
                            np.clip(samples, -1.0, 1.0, out=samples)
                            if samples.ndim > 1:
                                samples = samples.mean(axis=1)
                            else:
                                samples = samples.flatten()
                            self.audio_buffer.write_extend(samples)

                except (RuntimeError, IndexError, TypeError):
                    if self._stop_event.is_set():
                        break

                    consecutive_failures += 1
                    logger.warning(
                        f"[_run] Connection failed (Attempt {consecutive_failures}/{self.MAX_CONNECTION_RETRIES})"
                    )

                    if consecutive_failures >= self.MAX_CONNECTION_RETRIES:
                        logger.error(
                            "[_run] Reached max retries. Declaring device not found."
                        )
                        self.error_queue.put(
                            AudioCaptureErrorEvent(
                                device_name=self.device_name,
                                attempt_str=f"{self.MAX_CONNECTION_RETRIES}/{self.MAX_CONNECTION_RETRIES}",
                                error_type=ErrorType.CONNECTION_LOST_RETRY_FAILED,
                            )
                        )
                        break
                    else:
                        self.error_queue.put(
                            AudioCaptureErrorEvent(
                                device_name=self.device_name,
                                attempt_str=f"{consecutive_failures}/{self.MAX_CONNECTION_RETRIES}",
                                error_type=ErrorType.CONNECTION_LOST_RETRYING,
                            )
                        )

                    self._stop_event.wait(self.audio_retry_delay)

                except Exception:
                    if self._stop_event.is_set():
                        break
                    logger.exception("[_run] Unexpected Error.")
                    self._stop_event.wait(self.audio_retry_delay)
        finally:
            CoUninitialize()
            logger.info(f"[_run] Worker for '{self.device_name}' has shut down.")
