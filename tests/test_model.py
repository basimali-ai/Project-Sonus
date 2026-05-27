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

# mypy: disable-error-code=no-untyped-def

import numpy as np
import pytest
from scipy import signal

from project_sonus.audio_engine.audio_processing import (
    AudioProcessor,
    design_k_weighting,
)
from project_sonus.common.constants import AppConstants


def test_sq_to_lufs_at_reference_level():
    """
    sq_to_lufs conversion with a mean square of 1.0.
    Since log10(1.0) is 0, the result should be just the reference offset.
    """
    mean_square = 1.0
    expected_lufs = AppConstants.REFERENCE_OFFSET
    assert AudioProcessor.sq_to_lufs(mean_square) == pytest.approx(expected_lufs)


def test_sq_to_lufs_below_reference():
    """
    sq_to_lufs conversion with a value below the reference.
    10 * log10(0.1) = -10.
    """
    mean_square = 0.1
    expected_lufs = AppConstants.REFERENCE_OFFSET - 10.0
    assert AudioProcessor.sq_to_lufs(mean_square) == pytest.approx(expected_lufs)


def test_k_weighting_filter_properties():
    """
    Verifies that the designed filter matches the expected physical characteristics
    of the K-weighting curve (ITU-R BS.1770) at a standard sample rate of 48 kHz.
    """
    sr = 48000
    dtype = np.float64
    sos = design_k_weighting(sr, dtype)

    assert isinstance(sos, np.ndarray)
    assert sos.shape == (2, 6)
    assert sos.dtype == dtype

    test_freqs = [10.0, 1000.0, 15000.0]
    _, h = signal.freqz_sos(sos, worN=test_freqs, fs=sr)
    gains_db = 20 * np.log10(np.abs(h))

    assert gains_db[0] < -20.0, (
        f"Expected low-frequency attenuation, got {gains_db[0]:.2f} dB"
    )
    assert np.isclose(gains_db[1], 0.7, atol=0.05), (
        f"Expected ~0.7 dB at 1 kHz, got {gains_db[1]:.2f} dB"
    )
    assert np.isclose(gains_db[2], 4.0, atol=0.05), (
        f"Expected ~4 dB at high frequencies, got {gains_db[2]:.2f} dB"
    )


@pytest.mark.parametrize("sr", [44100, 48000, 88200, 96000, 192000])
def test_k_weighting_stability(sr):
    """
    Ensures that the designed filters are stable across all standard audio
    sample rates by verifying that all poles lie inside the unit circle.
    """
    sos = design_k_weighting(sr, np.float64)

    for section in range(sos.shape[0]):
        a = sos[section, 3:6]
        poles = np.roots(a)
        for pole in poles:
            assert np.abs(pole) < 1.0, (
                f"Unstable pole detected at sample rate {sr}: {pole}"
            )


def test_k_weighting_data_types():
    """
    Verifies that the function respects the requested precision (float32 vs float64).
    """
    sr = 48000
    for dt in [np.float32, np.float64]:
        sos = design_k_weighting(sr, dt)
        assert sos.dtype == dt


def test_k_weighting_exact_coefficients_48k():
    """
    Verifies that the generated coefficients perfectly match Table 1
    of the ITU-R BS.1770-4 specification for 48 kHz.
    """
    sr = 48000
    sos = design_k_weighting(sr, np.float64)

    expected_hp_b = np.array([1.0, -2.0, 1.0])
    expected_hp_a = np.array([1.0, -1.99004745483398, 0.99007225036621])

    expected_shelf_b = np.array([1.53512485958697, -2.69169618940638, 1.19839281085285])
    expected_shelf_a = np.array([1.0, -1.69065929318241, 0.73248077421585])

    hp_section = sos[0]
    shelf_section = sos[1]

    assert np.allclose(hp_section[:3], expected_hp_b, atol=1e-7)
    assert np.allclose(hp_section[3:], expected_hp_a, atol=1e-7)

    assert np.allclose(shelf_section[:3], expected_shelf_b, atol=1e-7)
    assert np.allclose(shelf_section[3:], expected_shelf_a, atol=1e-7)
