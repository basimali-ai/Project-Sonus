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
import re
import subprocess
from pathlib import Path
# ---------------------------------


def to_numeric_version(tag: str) -> str:
    """
    Converts a SemVer tag to a strictly numeric 4-part version string
    preserving correct Windows upgrade ordering (Alpha < Beta < RC < Stable).
    """
    version = tag.lstrip("v")

    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z]+)(?:\.?(\d+))?)?$", version)
    if not match:
        nums = re.findall(r"\d+", version)
        while len(nums) < 4:
            nums.append("0")
        return ".".join(nums[:4])

    major, minor, patch, pre_label, pre_num = match.groups()

    if not pre_label:
        return f"{major}.{minor}.{patch}.65535"

    label_map = {
        "alpha": {"base": 10000, "max": 19999},
        "beta": {"base": 20000, "max": 29999},
        "rc": {"base": 30000, "max": 39999},
    }

    config = label_map.get(pre_label.lower(), {"base": 10000, "max": 19999})
    pre_num_val = int(pre_num) if pre_num is not None else 0
    build_num = min(config["base"] + pre_num_val, config["max"])

    return f"{major}.{minor}.{patch}.{build_num}"


try:
    latest_tag = subprocess.check_output(
        ["git", "describe", "--tags", "--abbrev=0"], text=True
    ).strip()
except subprocess.CalledProcessError:
    latest_tag = "0.0.0.0"

numeric_version = to_numeric_version(latest_tag)
repo_root = Path(__file__).parent.parent

version_txt = repo_root / "version.txt"
version_txt.write_text(numeric_version + "\n", newline="\n")
print(f"Updated {version_txt} with {numeric_version}")

pyproject_file = repo_root / "pyproject.toml"
content = pyproject_file.read_text()
new_content = re.sub(
    r'version\s*=\s*"[^\"]+"', f'version = "{numeric_version}"', content
)
pyproject_file.write_text(new_content.rstrip("\n") + "\n", newline="\n")
print(f"Updated {pyproject_file} with {numeric_version}")
