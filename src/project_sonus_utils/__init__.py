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

"""
Utility Package for Project Sonus.

Provides internal helper tools currently including:
- SplashScreen: handles the application splash screen.
- TeeHandler: a logging utility that duplicates output to console and file.

Author: Syed Basim Ali <basim.ali.contact@gmail.com>
License: Apache-2.0
"""

__author__ = "Syed Basim Ali"
__email__ = "basim.ali.contact@gmail.com"
__license__ = "Apache-2.0"

from .splash_screen import SplashScreen
from .logging_utils import TeeHandler

__all__ = [
    "SplashScreen",
    "TeeHandler",
]

if __name__ == "__main__":
    print(
        "Project Sonus Utility Package\n"
        "-----------------------------\n"
        "This module provides internal tools and cannot be executed directly.\n"
        "To launch the application, run: python -m project_sonus\n"
        "If module is not found then install by following instructions at:\n"
        "https://github.com/basimali-ai/Project-Sonus"
    )
