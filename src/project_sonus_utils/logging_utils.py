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
# ---------------------------------


class TeeHandler(logging.Handler):
    __slots__ = ("handlers",)
    """
    A custom logging handler that forwards log records to multiple other handlers.
    """

    def __init__(self, *handlers: logging.Handler) -> None:
        super().__init__()
        self.handlers = list(handlers)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Forwards the record to every handler in its list.
        """
        for handler in self.handlers:
            if record.levelno >= handler.level:
                handler.emit(record)

    def addHandler(self, handler: logging.Handler) -> None:
        """Adds a new handler to the list."""
        if handler not in self.handlers:
            self.handlers.append(handler)

    def removeHandler(self, handler: logging.Handler) -> None:
        """Removes a handler from the list."""
        if handler in self.handlers:
            self.handlers.remove(handler)
