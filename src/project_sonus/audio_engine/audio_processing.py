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
import threading
import time
from collections import deque
from dataclasses import dataclass
from math import ceil, inf, isfinite, log10, pi, tan
from typing import Final, TypedDict
# ---------------------------------

# --- Third-Party Imports ---
import numpy as np
from numcircbuf import (
    BlockingCircBuffer,
    IntegratedGatedBuffer,
    RunningMeanBuffer,
    RunningMeanSqBuffer,
)
from scipy import signal
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import AppConstants
# ---------------------------------

logger = logging.getLogger(__name__)

REFERENCE_OFFSET = AppConstants.REFERENCE_OFFSET
EPS = AppConstants.EPS
SECONDS_IN_A_DAY = AppConstants.SECONDS_IN_A_DAY


class DoseReturn(TypedDict):
    daily_dose_consumed: float
    time_to_fill_str: str


class LufsReturn(TypedDict):
    stable: float
    integrated: float
    short_term: float
    momentary: float
    peak: float
    buffers_primed: bool


def design_k_weighting(
    sr: int, dtype: type[np.float64] | type[np.float32]
) -> np.ndarray:
    """
    Designs the two-stage K-weighting filter as per ITU-R BS.1770.
    Returns:
        np.ndarray: SOS coefficients of shape (2, 6) with the specified dtype.
    """
    f0_shelf = 1681.9744509555319
    G_shelf = 3.99984385397
    Q_shelf = 0.7071752369554193

    K_shelf = tan(pi * f0_shelf / sr)
    Vh = 10.0 ** (G_shelf / 20.0)
    Vb = Vh**0.499666774155

    a0_shelf = 1.0 + K_shelf / Q_shelf + K_shelf * K_shelf

    b_shelf = [
        (Vh + Vb * K_shelf / Q_shelf + K_shelf * K_shelf) / a0_shelf,
        2.0 * (K_shelf * K_shelf - Vh) / a0_shelf,
        (Vh - Vb * K_shelf / Q_shelf + K_shelf * K_shelf) / a0_shelf,
    ]
    a_shelf = [
        1.0,
        2.0 * (K_shelf * K_shelf - 1.0) / a0_shelf,
        (1.0 - K_shelf / Q_shelf + K_shelf * K_shelf) / a0_shelf,
    ]

    f0_hp = 38.13547087613982
    Q_hp = 0.5003270373253953

    K_hp = tan(pi * f0_hp / sr)
    a0_hp = 1.0 + K_hp / Q_hp + K_hp * K_hp

    b_hp = [1.0, -2.0, 1.0]
    a_hp = [
        1.0,
        2.0 * (K_hp * K_hp - 1.0) / a0_hp,
        (1.0 - K_hp / Q_hp + K_hp * K_hp) / a0_hp,
    ]

    return np.array(
        [
            b_hp + a_hp,
            b_shelf + a_shelf,
        ],
        dtype=dtype,
    )


def true_peak(samples: np.ndarray, oversample_factor: int = 4) -> float:
    """Upsamples by a factor (4× at least recommended by ITU-R BS.1770)"""
    upsampled = signal.resample_poly(samples, oversample_factor, 1)
    return float(np.max(np.abs(upsampled)))


@dataclass(frozen=True, slots=True)
class AudioProcessorConfig:
    """A structured container for all AudioProcessor configuration settings."""

    # --- Required Parameters ---

    # Core Audio Parameters
    sample_rate: int
    block_size: int
    block_duration: float
    silence_threshold: float

    # Timing & Window Parameters
    discard_duration_s: float
    momentary_window_s: float
    short_term_window_s: float
    stable_window_s: float
    integrated_window_s: float

    # --- Optional Parameters ---

    # Core Audio Parameters
    audio_buffer_seconds: float = AppConstants.AUDIO_BUFFER_SECONDS

    # Timing & Window Parameters
    priming_duration_s: float = AppConstants.DEFAULT_PRIMING_SECONDS

    # Calculation Settings
    true_peak_expensive_computation: bool = (
        AppConstants.DEFAULT_TRUE_PEAK_EXPENSIVE_COMPUTATION
    )

    # Loudness Gating Parameters
    abs_gate_lufs: float = AppConstants.ABS_GATE_LUFS
    rel_gate_lu: float = AppConstants.REL_GATE_LU

    # Dose Calculation Parameters
    dose_baseline_db: float = AppConstants.DOSE_BASELINE_DB
    dose_baseline_hours: float = AppConstants.DOSE_BASELINE_HOURS
    dose_exchange_rate_db: float = AppConstants.DOSE_EXCHANGE_RATE_DB


class AudioProcessor:
    __slots__ = (
        "_stop_event",
        "_thread",
        "abs_gate_lufs",
        "audio_buffer_size",
        "block_duration",
        "block_size",
        "buffers_primed",
        "daily_dose_consumed",
        "discard_chunks",
        "discard_chunks_remaining",
        "dose_baseline_db",
        "dose_baseline_hours",
        "dose_exchange_rate_db",
        "dose_history",
        "dtype",
        "filter_primed",
        "filter_zi",
        "integrated_buffer",
        "integrated_lufs",
        "integrated_window_s",
        "k_sos",
        "last_dose_update_time",
        "momentary_buffer",
        "momentary_lufs",
        "momentary_window_s",
        "peak_lufs",
        "peak_max",
        "peak_max_old",
        "priming_chunks",
        "priming_chunks_remaining",
        "read_timeout",
        "rel_gate_lu",
        "sample_rate",
        "shared_audio_buffer",
        "short_term_lufs",
        "short_term_window_s",
        "shortterm_buffer_m_sq",
        "silence_threshold",
        "silence_threshold_sq",
        "stable_buffer_m_sq",
        "stable_lufs",
        "stable_window_s",
        "true_peak_expensive_computation",
        "true_peak_margin_db",
        "volume_linear_gain_override",
    )

    def __init__(
        self, audio_processor_config: AudioProcessorConfig, daily_dose_consumed: float
    ) -> None:
        self.sample_rate = audio_processor_config.sample_rate
        self.block_size = audio_processor_config.block_size
        self.block_duration = audio_processor_config.block_duration

        self.discard_chunks = max(
            1,
            ceil(audio_processor_config.discard_duration_s / self.block_duration),
        )
        self.priming_chunks = max(
            1,
            ceil(audio_processor_config.priming_duration_s / self.block_duration),
        )

        self.true_peak_expensive_computation = (
            audio_processor_config.true_peak_expensive_computation
        )
        self.true_peak_margin_db = 0.0 if self.true_peak_expensive_computation else 1.0

        self.silence_threshold = audio_processor_config.silence_threshold

        self.momentary_window_s = audio_processor_config.momentary_window_s
        self.short_term_window_s = audio_processor_config.short_term_window_s
        self.stable_window_s = audio_processor_config.stable_window_s
        self.integrated_window_s = audio_processor_config.integrated_window_s

        self.audio_buffer_size = ceil(
            self.sample_rate * audio_processor_config.audio_buffer_seconds
        )

        self.abs_gate_lufs = audio_processor_config.abs_gate_lufs
        self.rel_gate_lu = audio_processor_config.rel_gate_lu

        self.dose_baseline_db = audio_processor_config.dose_baseline_db
        self.dose_baseline_hours = audio_processor_config.dose_baseline_hours
        self.dose_exchange_rate_db = audio_processor_config.dose_exchange_rate_db

        self.daily_dose_consumed = daily_dose_consumed

        self.dtype: Final[type[np.float32 | np.float64]] = np.float32
        self._initialize_buffers_and_state()
        self.reset_metrics()

    def _initialize_buffers_and_state(self) -> None:
        """Initializes all data buffers, queues, and state flags."""
        self.read_timeout = self.block_duration + 0.25
        self.volume_linear_gain_override = 1.0

        self.buffers_primed = False
        self.filter_primed = False

        self.shared_audio_buffer = BlockingCircBuffer(
            maxlen=self.audio_buffer_size, dtype=self.dtype
        )

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self.k_sos = design_k_weighting(self.sample_rate, self.dtype)
        self.filter_zi: np.ndarray = signal.sosfilt_zi(self.k_sos)

        self.silence_threshold_sq = self.silence_threshold**2

        self.momentary_buffer = RunningMeanSqBuffer(
            maxlen=max(1, ceil(self.momentary_window_s * self.sample_rate)),
            operation_focus="extend/append",
            recalc_threshold=3600 * self.sample_rate,  # s
            dtype=self.dtype,
        )

        self.shortterm_buffer_m_sq = RunningMeanBuffer(
            maxlen=max(1, ceil(self.short_term_window_s / self.block_duration)),
            operation_focus="calculation",
            dtype=self.dtype,
        )

        self.stable_buffer_m_sq = RunningMeanBuffer(
            maxlen=max(1, ceil(self.stable_window_s / self.block_duration)),
            operation_focus="calculation",
            dtype=self.dtype,
        )

        self.integrated_buffer = IntegratedGatedBuffer(
            maxlen=max(1, ceil(self.integrated_window_s / self.block_duration)),
            abs_gate_lufs=self.abs_gate_lufs,
            rel_gate_lu=self.rel_gate_lu,
            recalc_threshold=int(3600 / self.block_duration),  # s
            dtype=self.dtype,
        )

        self.last_dose_update_time = time.time()
        self.dose_history: deque[tuple[float, float]] = deque(
            maxlen=AppConstants.DOSE_HISTORY_WINDOW_SECONDS
        )

    def reset_dose(self) -> None:
        """Resets the daily dose calculation."""
        self.daily_dose_consumed = 0.0
        self.dose_history.clear()
        self.last_dose_update_time = time.time()
        logger.info("[reset_dose] Daily dose reset")

    def reset_metrics(self) -> None:
        """Resets metrics"""
        self.integrated_lufs = -inf
        self.short_term_lufs = -inf
        self.momentary_lufs = -inf
        self.stable_lufs = -inf
        self.peak_lufs = -inf
        self.peak_max = -inf
        self.peak_max_old = -inf

        self.integrated_buffer.clear()
        self.momentary_buffer.clear()
        self.shortterm_buffer_m_sq.clear()
        self.stable_buffer_m_sq.clear()

        self.filter_zi = signal.sosfilt_zi(self.k_sos)

        self.buffers_primed = False
        self.filter_primed = False

        self.priming_chunks_remaining = self.priming_chunks
        self.discard_chunks_remaining = self.discard_chunks

        logger.info("[reset_metrics] Metrics Reset")

    def calculate_permissible_hours(self, spl: float) -> float:
        """Outputs max exposure time in hours, based on SPL"""

        if spl < 20:
            return inf

        exponent = (self.dose_baseline_db - spl) / self.dose_exchange_rate_db
        return self.dose_baseline_hours * (2**exponent)

    def update_and_get_dose_data(
        self,
        current_lufs: float,
        gain_constant: float,
        dose_accumulation_spl_threshold: float,
    ) -> DoseReturn | None:
        """Updates the daily dose budget based on current SPL."""

        current_time = time.time()
        delta_time = current_time - self.last_dose_update_time

        if (delta_time < 1.0) or (
            not isfinite(gain_constant) or not isfinite(current_lufs)
        ):
            return None

        current_spl = current_lufs + gain_constant
        if current_spl > dose_accumulation_spl_threshold:
            permissible_hours = self.calculate_permissible_hours(current_spl)
            if isfinite(permissible_hours):
                permissible_seconds = permissible_hours * 3600
                dose_this_interval = (delta_time / max(1e-9, permissible_seconds)) * 100
                self.daily_dose_consumed += dose_this_interval

        self.last_dose_update_time = current_time
        self.dose_history.append((current_time, self.daily_dose_consumed))

        time_to_fill_str = "---"
        if len(self.dose_history) > 1 and self.daily_dose_consumed < 100:
            time_span = self.dose_history[-1][0] - self.dose_history[0][0]
            dose_span = self.dose_history[-1][1] - self.dose_history[0][1]

            if dose_span > 1e-6 and time_span > 1e-9:
                dose_rate_per_sec = dose_span / time_span
                remaining_dose = 100.0 - self.daily_dose_consumed
                seconds_to_fill = remaining_dose / max(1e-9, dose_rate_per_sec)

                if seconds_to_fill < SECONDS_IN_A_DAY * 2:
                    hours = int(seconds_to_fill // 3600)
                    minutes = int((seconds_to_fill % 3600) // 60)
                    time_to_fill_str = f"{hours}h {minutes}m"
                else:
                    time_to_fill_str = "> 48 hours"

        return {
            "daily_dose_consumed": self.daily_dose_consumed,
            "time_to_fill_str": time_to_fill_str,
        }

    def start_process_audio_loop(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._process_audio_worker, daemon=True)
        self._thread.start()

    def _process_audio_worker(self) -> None:
        """
        Continuously reads from the shared audio buffer and processes the data.
        """
        items_to_read = round(self.block_size * 1.5)
        read_into_arr = np.empty(items_to_read, dtype=self.dtype)
        while not self._stop_event.is_set():
            items_read = self.shared_audio_buffer.read_into_unchecked(
                read_into_arr, timeout=self.read_timeout
            )
            if items_read:
                self.process_audio_chunk(read_into_arr[:items_read])

    def stop_process_audio_loop(self) -> None:
        if not self._stop_event.is_set():
            logger.info("[stop_process_audio_loop] Stop command issued.")
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            timeout = self.read_timeout + 0.25
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("[stop_process_audio_loop] Timed out waiting to stop.")
            else:
                logger.info("[stop_process_audio_loop] Successfully joined thread.")

    def process_audio_chunk(self, chunk: np.ndarray) -> None:
        """
        Processes raw audio and populates the data buffers.
        """
        try:
            if self.discard_chunks_remaining:
                discard_chunks_remaining = self.discard_chunks_remaining
                if discard_chunks_remaining == self.discard_chunks:
                    logger.info(
                        f"[process_audio_loop] Discarding {discard_chunks_remaining} chunks..."
                    )
                self.discard_chunks_remaining = discard_chunks_remaining - 1
                if discard_chunks_remaining == 1:
                    logger.info("[process_audio_loop] Finished discarding chunks")
                return

            elif not self.filter_primed:
                logger.info(
                    "[process_audio_loop] Priming filter state with first clean audio chunk..."
                )

                _, self.filter_zi = signal.sosfilt(self.k_sos, chunk, zi=self.filter_zi)
                if not np.all(np.isfinite(self.filter_zi)):
                    self.filter_zi = signal.sosfilt_zi(self.k_sos)
                    logger.warning(
                        "[process_audio_loop] Filter priming resulted in non-finite state. Resetting."
                    )
                    return

                self.filter_primed = True
                logger.info(
                    "[process_audio_loop] Filter is now primed. Proceeding to analysis."
                )
                return

            else:
                weighted, self.filter_zi = signal.sosfilt(
                    self.k_sos, chunk, zi=self.filter_zi
                )
                if not np.all(np.isfinite(weighted)):
                    self.filter_zi = signal.sosfilt_zi(self.k_sos)
                    return

                volume_linear_gain_override = self.volume_linear_gain_override
                if volume_linear_gain_override != 1.0:
                    scaled_weighted = weighted * volume_linear_gain_override
                else:
                    scaled_weighted = weighted

                if self.true_peak_expensive_computation:
                    peak_amp = true_peak(scaled_weighted)
                else:
                    peak_amp = float(np.max(np.abs(scaled_weighted)))

                if peak_amp > self.silence_threshold:
                    self.peak_max = max(self.peak_max, peak_amp)

                mean_sq: float = (
                    float(np.dot(scaled_weighted, scaled_weighted))
                    / scaled_weighted.size
                )
                if not isfinite(mean_sq):
                    return

                self.momentary_buffer.extend(scaled_weighted)

                if mean_sq > self.silence_threshold_sq:
                    self.shortterm_buffer_m_sq.append(mean_sq)
                    self.stable_buffer_m_sq.append(mean_sq)
                    self.integrated_buffer.append(mean_sq, already_squared=True)
                else:
                    self.shortterm_buffer_m_sq.append(0.0)
                    self.stable_buffer_m_sq.append(0.0)

                if not self.buffers_primed:
                    priming_chunks_remaining = self.priming_chunks_remaining
                    if priming_chunks_remaining == self.priming_chunks:
                        logger.info(
                            "[process_audio_loop] Priming buffers with "
                            f"{priming_chunks_remaining} chunks..."
                        )
                    self.priming_chunks_remaining = priming_chunks_remaining - 1
                    if priming_chunks_remaining == 1:
                        self.buffers_primed = True
                        logger.info(
                            "[process_audio_loop] Finished priming buffers. GUI is live."
                        )

        except Exception:
            logger.exception(
                "[process_audio_loop] Error in process_audio_loop, skipping chunk."
            )
            return

    def calculate_all_lufs(self) -> None:
        """
        Performs all LUFS calculations based on the current state of the data buffers and updates
        the model's internal state variables.
        """
        if not self.buffers_primed:
            return

        silence_threshold_sq = self.silence_threshold_sq

        stable_buffer_m_sq_avg = self.stable_buffer_m_sq.mean()
        if stable_buffer_m_sq_avg > silence_threshold_sq:
            self.stable_lufs = self.sq_to_lufs(stable_buffer_m_sq_avg)
        else:
            self.stable_lufs = -inf
            self.momentary_lufs = -inf
            self.short_term_lufs = -inf
            return

        momentary_buffer_m_sq = self.momentary_buffer.mean_square()
        self.momentary_lufs = (
            self.sq_to_lufs(momentary_buffer_m_sq)
            if momentary_buffer_m_sq > silence_threshold_sq
            else -inf
        )

        shortterm_buffer_m_sq_avg = self.shortterm_buffer_m_sq.mean()
        self.short_term_lufs = (
            self.sq_to_lufs(shortterm_buffer_m_sq_avg)
            if shortterm_buffer_m_sq_avg > silence_threshold_sq
            else -inf
        )

        final_gated_mean_sq = self.integrated_buffer.gated_mean_square()
        self.integrated_lufs = (
            self.sq_to_lufs(final_gated_mean_sq) if final_gated_mean_sq > 0 else -inf
        )

        peak_max = self.peak_max
        if peak_max > self.peak_max_old:
            self.peak_max_old = peak_max
            self.peak_lufs = (
                ((20 * log10(peak_max)) + self.true_peak_margin_db)
                if peak_max > EPS
                else -inf
            )

    @staticmethod
    def sq_to_lufs(sq: float) -> float:
        """Converts a squared audio signal value to LUFS."""
        return REFERENCE_OFFSET + 10.0 * log10(max(sq, EPS))

    def get_lufs_values(
        self, volume_linear_gain_override: float | None = None
    ) -> LufsReturn:
        """
        Calculates all LUFS values. If a `volume_linear_gain_override` is provided,
        it updates the gain override for future incoming audio chunks.
        """
        self.volume_linear_gain_override = (
            volume_linear_gain_override
            if volume_linear_gain_override is not None
            else 1.0
        )

        self.calculate_all_lufs()

        return {
            "stable": self.stable_lufs,
            "integrated": self.integrated_lufs,
            "short_term": self.short_term_lufs,
            "momentary": self.momentary_lufs,
            "peak": self.peak_lufs,
            "buffers_primed": self.buffers_primed,
        }
