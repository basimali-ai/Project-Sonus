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

from types import UnionType
from typing import TYPE_CHECKING, Any, Union

import pytest

from project_sonus.common.constants import (
    ALLOWED_JSON_CONTAINERS,
    ALLOWED_JSON_PRIMITIVES,
    ALLOWED_JSON_TYPES,
    ConfigDefaults,
    ConfigKeys,
    HotkeyInfoDefaults,
    HotkeyInfoKeys,
    OverlayInfoDefaults,
    OverlayInfoKeys,
    PersistenceDefaults,
    PersistenceKeys,
)
from project_sonus.common.structures import resolve_type_info

if TYPE_CHECKING:
    from project_sonus.common.constants import _KeysBP
    from project_sonus.common.structures import BaseKey, FrozenNamespace


def _is_json_value(val: object) -> bool:
    if isinstance(val, ALLOWED_JSON_PRIMITIVES):
        return True
    if isinstance(val, list):
        return all(_is_json_value(v) for v in val)
    if isinstance(val, dict):
        return all(isinstance(k, str) and _is_json_value(v) for k, v in val.items())
    return False


def _is_valid_type_hint(expected_type: Any) -> bool:
    origin, args = resolve_type_info(expected_type)

    if origin is None:
        if expected_type is Any:
            return True
        actual_type = type(None) if expected_type is None else expected_type
        return isinstance(actual_type, type) and issubclass(
            actual_type, ALLOWED_JSON_TYPES
        )

    if origin in (Union, UnionType):
        return all(_is_valid_type_hint(arg) for arg in args)

    if not (isinstance(origin, type) and issubclass(origin, ALLOWED_JSON_CONTAINERS)):
        return False

    if issubclass(origin, list):
        return _is_valid_type_hint(args[0]) if args else True

    if issubclass(origin, dict):
        if args:
            k_type, v_type = args
            k_origin = getattr(k_type, "__origin__", k_type)
            if k_origin is not str:
                return False
            return _is_valid_type_hint(v_type)
        return True

    return False


def _is_valid_type(value: object, expected_type: Any) -> bool:
    origin, args = resolve_type_info(expected_type)

    if origin is None:
        if expected_type is Any:
            return _is_json_value(value)

        actual_type = type(None) if expected_type is None else expected_type
        if actual_type is int and isinstance(value, bool):
            return False
        return isinstance(value, actual_type)

    if origin in (Union, UnionType):
        return any(_is_valid_type(value, arg) for arg in args)

    if not isinstance(value, origin):
        return False

    if not args:
        return True

    if issubclass(origin, list):
        item_type = args[0]
        return all(_is_valid_type(v, item_type) for v in value)

    elif issubclass(origin, dict):
        _, v_type = args
        return all(
            isinstance(k, str) and _is_valid_type(v, v_type) for k, v in value.items()
        )

    else:
        raise TypeError(f"Container '{origin}' is not allowed.")


def _assert_defaults_validity(
    keys: "_KeysBP[BaseKey[object]]", defaults: "FrozenNamespace[str, object]"
) -> None:
    for k in keys:
        key_name = k.name
        t_type = k._t_type

        if not _is_valid_type_hint(t_type):
            raise TypeError(
                f"The schema '{t_type}' defined on key '{k}' is not supported by JSON."
            )

        if not hasattr(defaults, key_name):
            continue

        val = getattr(defaults, key_name)
        val_min = getattr(defaults, f"{key_name}_MIN", None)
        val_max = getattr(defaults, f"{key_name}_MAX", None)

        values_to_check = [val]

        if val_min is not None or val_max is not None:
            if val_min is None or val_max is None:
                raise ValueError(
                    f"Both min and max limits must be defined together; "
                    f"Check {defaults} for {key_name}"
                )
            values_to_check.extend([val_min, val_max])

        for v in values_to_check:
            if not _is_valid_type(v, t_type):
                raise TypeError(
                    f"Wrong type in {defaults} for {key_name}. "
                    f"Value '{v}' does not match expected type '{t_type}'"
                )


@pytest.mark.parametrize(
    "keys, defaults",
    [
        (HotkeyInfoKeys, HotkeyInfoDefaults),
        (OverlayInfoKeys, OverlayInfoDefaults),
        (PersistenceKeys, PersistenceDefaults),
        (ConfigKeys, ConfigDefaults),
    ],
    ids=["HotkeyInfo", "OverlayInfo", "Persistence", "Config"],
)
def test_defaults_validity(
    keys: "_KeysBP[BaseKey[object]]", defaults: "FrozenNamespace[str, object]"
) -> None:
    _assert_defaults_validity(keys, defaults)
