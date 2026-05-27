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

# --- Third-Party Imports ---
from ruamel.yaml.comments import CommentedMap
# ---------------------------------

# --- Local Imports ---
from project_sonus.common.constants import ConfigDefaults, ConfigKeys
# ---------------------------------


def get_default_config() -> CommentedMap:
    """Return default YAML content programmatically to ensure structure and comments are preserved correctly."""

    cfg = CommentedMap()
    cfg.yaml_set_start_comment("--- Optional Settings ---\n")

    # --- GUI Refresh Intervals ---
    cfg.yaml_set_comment_before_after_key(
        ConfigKeys.MIN_GUI_REFRESH.value,
        before="\nApplication Refresh/Restart Intervals",
    )
    cfg[ConfigKeys.MIN_GUI_REFRESH.value] = ConfigDefaults.MIN_GUI_REFRESH
    cfg.yaml_add_eol_comment(
        "The gui refreshes at this rate when the numbers are moving.",
        key=ConfigKeys.MIN_GUI_REFRESH.value,
    )
    cfg[ConfigKeys.MAX_GUI_REFRESH.value] = ConfigDefaults.MAX_GUI_REFRESH
    cfg.yaml_add_eol_comment(
        "The gui refreshes at this rate when the numbers are still.",
        key=ConfigKeys.MAX_GUI_REFRESH.value,
    )
    cfg[ConfigKeys.RESTART_INTERVAL.value] = ConfigDefaults.RESTART_INTERVAL
    cfg.yaml_add_eol_comment(
        "Application automatically restarts after this many hours, to prevent memory buildup over long runtimes.",
        key=ConfigKeys.RESTART_INTERVAL.value,
    )

    # --- Calculation Settings ---
    cfg.yaml_set_comment_before_after_key(
        ConfigKeys.SAMPLE_RATE.value, before="\nCalculation Settings"
    )
    cfg[ConfigKeys.SAMPLE_RATE.value] = ConfigDefaults.SAMPLE_RATE
    cfg.yaml_add_eol_comment(
        "Audio sampling rate in Hz.", key=ConfigKeys.SAMPLE_RATE.value
    )
    cfg[ConfigKeys.BLOCK_DURATION.value] = ConfigDefaults.BLOCK_DURATION
    cfg.yaml_add_eol_comment(
        "Audio is processed in blocks of this duration. Higher = more efficient, higher latency.",
        key=ConfigKeys.BLOCK_DURATION.value,
    )
    cfg[ConfigKeys.TRUE_PEAK_EXPENSIVE.value] = ConfigDefaults.TRUE_PEAK_EXPENSIVE
    cfg.yaml_add_eol_comment(
        "Enable oversampling for most accurate true peak (CPU intensive) (Only inaccurate by upto ~1dB if False).",
        key=ConfigKeys.TRUE_PEAK_EXPENSIVE.value,
    )
    cfg[ConfigKeys.DISCARD_DURATION.value] = ConfigDefaults.DISCARD_DURATION
    cfg.yaml_add_eol_comment(
        "First samples during this duration will be discarded to ensure no arifacts get through.",
        key=ConfigKeys.DISCARD_DURATION.value,
    )
    cfg[ConfigKeys.PRIMING_DURATION.value] = ConfigDefaults.PRIMING_DURATION
    cfg.yaml_add_eol_comment(
        "First valid samples during this duration will be accumulated to prime the meters instead of showing values instantly.",
        key=ConfigKeys.PRIMING_DURATION.value,
    )
    cfg[ConfigKeys.AUDIO_RETRY_DELAY.value] = ConfigDefaults.AUDIO_RETRY_DELAY
    cfg.yaml_add_eol_comment(
        "Audio connection will be retried if an error occurs with this delay.",
        key=ConfigKeys.AUDIO_RETRY_DELAY.value,
    )

    # --- SPL Averaging Windows ---
    cfg.yaml_set_comment_before_after_key(
        ConfigKeys.CURRENT_SPL_WINDOW.value, before="\nSPL Averaging Windows"
    )
    cfg[ConfigKeys.CURRENT_SPL_WINDOW.value] = ConfigDefaults.CURRENT_SPL_WINDOW
    cfg.yaml_add_eol_comment(
        "Current SPL will be averaged over the last N seconds.",
        key=ConfigKeys.CURRENT_SPL_WINDOW.value,
    )
    cfg[ConfigKeys.MOMENTARY_WINDOW.value] = ConfigDefaults.MOMENTARY_WINDOW
    cfg.yaml_add_eol_comment(
        "Momentary SPL will be averaged over the last N seconds.",
        key=ConfigKeys.MOMENTARY_WINDOW.value,
    )
    cfg[ConfigKeys.SHORT_TERM_WINDOW.value] = ConfigDefaults.SHORT_TERM_WINDOW
    cfg.yaml_add_eol_comment(
        "Short-Term SPL will be averaged over the last N seconds.",
        key=ConfigKeys.SHORT_TERM_WINDOW.value,
    )
    cfg[ConfigKeys.INTEGRATED_WINDOW.value] = ConfigDefaults.INTEGRATED_WINDOW
    cfg.yaml_add_eol_comment(
        "Integrated SPL will be averaged over the last N seconds.",
        key=ConfigKeys.INTEGRATED_WINDOW.value,
    )

    # --- Optional Calibration ---
    cfg.yaml_set_comment_before_after_key(
        ConfigKeys.SILENCE_THRESHOLD.value, before="\nOptional Calibration"
    )
    cfg[ConfigKeys.SILENCE_THRESHOLD.value] = ConfigDefaults.SILENCE_THRESHOLD
    cfg.yaml_add_eol_comment(
        "Audio samples below this amplitude are treated as silence.",
        key=ConfigKeys.SILENCE_THRESHOLD.value,
    )

    # --- Volume Calculator Settings ---
    cfg.yaml_set_comment_before_after_key(
        ConfigKeys.DEFAULT_TARGET_SPL.value,
        before="\nVolume Calculator Settings",
    )
    cfg[ConfigKeys.DEFAULT_TARGET_SPL.value] = ConfigDefaults.DEFAULT_TARGET_SPL
    cfg[ConfigKeys.DEFAULT_SAFETY_BUFFER.value] = ConfigDefaults.DEFAULT_SAFETY_BUFFER
    cfg[ConfigKeys.DEFAULT_BASELINE_DB.value] = ConfigDefaults.DEFAULT_BASELINE_DB
    cfg[ConfigKeys.DEFAULT_BASELINE_LUFS.value] = ConfigDefaults.DEFAULT_BASELINE_LUFS
    cfg[ConfigKeys.VOL_DEC_TOLERANCE.value] = ConfigDefaults.VOL_DEC_TOLERANCE
    cfg.yaml_add_eol_comment(
        "Will tell you to decrease volume when current dB > target dB + X.",
        key=ConfigKeys.VOL_DEC_TOLERANCE.value,
    )
    cfg[ConfigKeys.VOL_INC_TOLERANCE.value] = ConfigDefaults.VOL_INC_TOLERANCE
    cfg.yaml_add_eol_comment(
        "Will tell you to increase volume when current dB < target dB - X.",
        key=ConfigKeys.VOL_INC_TOLERANCE.value,
    )

    # --- Dose Meter Settings ---
    cfg.yaml_set_comment_before_after_key(
        ConfigKeys.DOSE_ACCUM_THRESHOLD.value, before="\nDose Meter Settings"
    )
    cfg[ConfigKeys.DOSE_ACCUM_THRESHOLD.value] = ConfigDefaults.DOSE_ACCUM_THRESHOLD
    cfg.yaml_add_eol_comment(
        "Minimum dB for dosage to accumulate.",
        key=ConfigKeys.DOSE_ACCUM_THRESHOLD.value,
    )

    # --- GUI Visuals ---
    cfg.yaml_set_comment_before_after_key(
        ConfigKeys.FONT_BOLD_NAME.value, before="\nGUI Visuals"
    )
    cfg[ConfigKeys.FONT_BOLD_NAME.value] = ConfigDefaults.FONT_BOLD_NAME
    cfg.yaml_add_eol_comment(
        "Bold Font Name (Any font installed on your system can be used).",
        key=ConfigKeys.FONT_BOLD_NAME.value,
    )
    cfg[ConfigKeys.FONT_BOLD_SIZE.value] = ConfigDefaults.FONT_BOLD_SIZE
    cfg[ConfigKeys.FONT_NORMAL_NAME.value] = ConfigDefaults.FONT_NORMAL_NAME
    cfg.yaml_add_eol_comment(
        "Normal Font Name (Any font installed on your system can be used).",
        key=ConfigKeys.FONT_NORMAL_NAME.value,
    )
    cfg[ConfigKeys.FONT_NORMAL_SIZE.value] = ConfigDefaults.FONT_NORMAL_SIZE
    cfg[ConfigKeys.BACKGROUND_COLOR.value] = ConfigDefaults.BACKGROUND_COLOR
    cfg[ConfigKeys.ACCENT_COLOR.value] = ConfigDefaults.ACCENT_COLOR
    cfg[ConfigKeys.CRITICAL_COLOR.value] = ConfigDefaults.CRITICAL_COLOR
    cfg.yaml_add_eol_comment(
        "Color used to show critical warnings.",
        key=ConfigKeys.CRITICAL_COLOR.value,
    )
    cfg[ConfigKeys.WARNING_COLOR.value] = ConfigDefaults.WARNING_COLOR
    cfg.yaml_add_eol_comment(
        "Color used to show non-critical warnings.",
        key=ConfigKeys.WARNING_COLOR.value,
    )
    cfg[ConfigKeys.OK_COLOR.value] = ConfigDefaults.OK_COLOR
    cfg.yaml_add_eol_comment(
        "Color used to show a safe/satisfactory state.",
        key=ConfigKeys.OK_COLOR.value,
    )
    cfg[ConfigKeys.TEXT_COLOR.value] = ConfigDefaults.TEXT_COLOR
    cfg[ConfigKeys.FIELD_COLOR.value] = ConfigDefaults.FIELD_COLOR
    cfg.yaml_add_eol_comment(
        "Color of entry fields, e.g. Target device dropdown, Baseline entries.",
        key=ConfigKeys.FIELD_COLOR.value,
    )
    return cfg
