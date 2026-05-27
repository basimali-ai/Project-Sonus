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
import copy
from collections.abc import ItemsView, Iterator, Mapping, Sequence, ValuesView
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Never, TypeVar, cast, get_args, get_origin
# ---------------------------------

type JsonValue = (
    str | int | float | bool | None | Sequence[JsonValue] | Mapping[str, JsonValue]
)

_P = TypeVar("_P", bound=JsonValue)
_C = TypeVar("_C", bound=float | int | bool | str)


@lru_cache
def resolve_type_info(t_type: Any) -> tuple[Any, tuple[Any, ...]]:
    return get_origin(t_type), get_args(t_type)


@dataclass(frozen=True, slots=True)
class BaseKey[T]:
    value: str
    name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        if not self.name:
            object.__setattr__(self, "name", name)

    @classmethod
    def __class_getitem__(cls, item: Any) -> type:

        class ParameterizedKey(cls):  # type: ignore[valid-type, misc]
            __slots__ = ()
            _t_type = item

        item_name = getattr(item, "__name__", str(item))
        ParameterizedKey.__name__ = f"{cls.__name__}[{item_name}]"
        ParameterizedKey.__qualname__ = f"{cls.__qualname__}[{item_name}]"
        ParameterizedKey.__origin__ = cls
        ParameterizedKey.__args__ = (item,)

        return ParameterizedKey


@dataclass(frozen=True, slots=True)
class PersistenceKey(BaseKey[_P]): ...


@dataclass(frozen=True, slots=True)
class ConfigKey(BaseKey[_C]): ...


class DataDict(dict[Any, Any]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.sanitized_ids: set[int] = set()
        super().__init__(*args, **kwargs)

    def _discard_id_by_val(self, val: Any) -> None:
        if isinstance(val, dict) and not isinstance(val, DataDict):
            self.sanitized_ids.discard(id(val))

    def _discard_id_by_key(self, resolved_key: Any) -> None:
        if super().__contains__(resolved_key):
            self._discard_id_by_val(super().__getitem__(resolved_key))

    def _sanitize_dict(self, key: Any, resolved_key: Any, val: Any) -> Any:
        t_type = getattr(key, "_t_type", None)

        if t_type is None:
            return val

        if t_type is dict:
            self.sanitized_ids.add(id(val))
            return val

        origin, args = resolve_type_info(t_type)
        changed = False

        if origin is not None:
            k_type = args[0] if len(args) > 0 else Any
            v_type = args[1] if len(args) > 1 else Any

            new_dict = {}

            for k, v in val.items():
                if (
                    isinstance(k_type, type)
                    and issubclass(k_type, DataDict)
                    and not isinstance(k, k_type)
                ):
                    k = k_type(k)
                    changed = True

                if (
                    isinstance(v_type, type)
                    and issubclass(v_type, DataDict)
                    and not isinstance(v, v_type)
                ):
                    v = v_type(v)
                    changed = True

                new_dict[k] = v

            if changed:
                wrapped = origin(new_dict)
            elif not isinstance(val, origin):
                wrapped = origin(val)
                changed = True
            else:
                wrapped = val

        else:
            if not isinstance(val, t_type):
                wrapped = t_type(val)
                changed = True
            else:
                wrapped = val

        if changed:
            super().__setitem__(resolved_key, wrapped)

        if not isinstance(wrapped, DataDict):
            self.sanitized_ids.add(id(wrapped))

        return wrapped

    def _sanitize_val(self, key: Any, resolved_key: Any, val: Any) -> Any:
        if (
            isinstance(val, dict)
            and not isinstance(val, DataDict)
            and id(val) not in self.sanitized_ids
        ):
            val = self._sanitize_dict(key, resolved_key, val)

        return val

    def __setitem__(self, key: Any, value: Any) -> None:
        resolved_key = getattr(key, "value", key)
        self._discard_id_by_key(resolved_key)
        super().__setitem__(resolved_key, value)

    def __delitem__(self, key: Any) -> None:
        resolved_key = getattr(key, "value", key)
        self._discard_id_by_key(resolved_key)
        super().__delitem__(resolved_key)

    def pop(self, key: Any, *args: Any) -> Any:
        resolved_key = getattr(key, "value", key)
        self._discard_id_by_key(resolved_key)
        return super().pop(resolved_key, *args)

    def popitem(self) -> tuple[Any, Any]:
        key, val = super().popitem()
        self._discard_id_by_val(val)
        return key, val

    def clear(self) -> None:
        self.sanitized_ids.clear()
        super().clear()

    def __contains__(self, key: Any) -> bool:
        return super().__contains__(getattr(key, "value", key))

    def __getitem__(self, key: Any) -> Any:
        resolved_key = getattr(key, "value", key)
        val = super().__getitem__(resolved_key)
        return self._sanitize_val(key, resolved_key, val)

    def get(self, key: Any, default: Any = None) -> Any:
        resolved_key = getattr(key, "value", key)
        if not super().__contains__(resolved_key):
            return default

        val = super().get(resolved_key, default)
        return self._sanitize_val(key, resolved_key, val)

    def update(self, *args: Any, **kwargs: Any) -> None:
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def items(self) -> Any:
        return ItemsView(self)

    def values(self) -> Any:
        return ValuesView(self)


class PersistenceData(DataDict): ...


class ProfileInfo(PersistenceData): ...


class HotkeyInfo(PersistenceData): ...


class OverlayInfo(PersistenceData): ...


class FrozenNamespace[K: str, V]:
    _data: dict[K, V]
    __slots__ = ("_data", "_name")

    def __init__(self, data: dict[K, V], name: str = "") -> None:
        object.__setattr__(self, "_data", copy.deepcopy(data))
        object.__setattr__(self, "_name", name)

    def __set_name__(self, owner: type, name: str) -> None:
        if not self._name:
            object.__setattr__(self, "_name", name)

    def _get_safe_value(self, value: V) -> V:
        if isinstance(value, (int, str, float, bool, type(None))):
            return value  # type: ignore[return-value]
        return copy.deepcopy(value)

    def __getattr__(self, name: str) -> V:
        try:
            return self._get_safe_value(self._data[cast("K", name)])
        except KeyError:
            raise AttributeError(f"{self} has no attribute {name!r}")

    def __getitem__(self, key: K) -> V:
        return self._get_safe_value(self._data[key])

    def __setattr__(self, key: Any, value: Any) -> Never:
        raise TypeError(f"{self} is immutable")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._name} ({len(self._data)} keys)>"

    def __iter__(self) -> Iterator[tuple[K, V]]:
        for k, v in self._data.items():
            yield k, self._get_safe_value(v)
