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

import copy
from typing import Any

import pytest
from ruamel.yaml.comments import CommentedMap

from project_sonus.common.constants import ConfigKeys
from project_sonus.configuration.config_manager import ConfigManager


@pytest.fixture
def manager():
    """Provides a ConfigManager instance for tests."""
    return ConfigManager()


@pytest.fixture
def default_config(manager):
    """Provides the default configuration map."""
    return manager.default_config


def test_sanitize_config_fixes_none_value(manager, default_config):
    """A None value in user config is replaced by the default."""
    cfg = copy.deepcopy(default_config)
    cfg[ConfigKeys.SAMPLE_RATE.value] = None

    sanitized_keys: dict[str, Any] = {}
    manager._sanitize_config_recursive(cfg, default_config, sanitized_keys)

    assert (
        cfg[ConfigKeys.SAMPLE_RATE.value]
        == default_config[ConfigKeys.SAMPLE_RATE.value]
    )
    assert ConfigKeys.SAMPLE_RATE.value in sanitized_keys


def test_sanitize_config_fixes_wrong_type(manager, default_config):
    """A string is correctly cast to bool."""
    cfg = copy.deepcopy(default_config)
    cfg[ConfigKeys.TRUE_PEAK_EXPENSIVE.value] = "true"

    sanitized_keys: dict[str, Any] = {}
    manager._sanitize_config_recursive(cfg, default_config, sanitized_keys)

    assert cfg[ConfigKeys.TRUE_PEAK_EXPENSIVE.value] is True
    assert ConfigKeys.TRUE_PEAK_EXPENSIVE.value in sanitized_keys


def test_merge_defaults_preserves_user_values(manager, default_config):
    """Existing user values are not overwritten by defaults."""
    user_cfg = CommentedMap()
    user_cfg[ConfigKeys.SAMPLE_RATE.value] = 96000

    merged_cfg, _, _ = manager.merge_defaults(user_cfg, default_config)

    assert merged_cfg[ConfigKeys.SAMPLE_RATE.value] == 96000


def test_merge_defaults_adds_missing_keys(manager, default_config):
    """Keys missing from user config are added from the defaults."""
    user_cfg = CommentedMap()
    user_cfg[ConfigKeys.SAMPLE_RATE.value] = 96000

    merged_cfg, _, _ = manager.merge_defaults(user_cfg, default_config)

    assert (
        merged_cfg[ConfigKeys.SAMPLE_RATE.value]
        == user_cfg[ConfigKeys.SAMPLE_RATE.value]
    )
    assert (
        merged_cfg[ConfigKeys.BLOCK_DURATION.value]
        == default_config[ConfigKeys.BLOCK_DURATION.value]
    )
