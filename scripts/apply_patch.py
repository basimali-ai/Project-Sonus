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
import compileall
import shutil
import sys
from pathlib import Path
# ---------------------------------

# --- Third-Party Imports ---
import patch
# ---------------------------------


def get_py_path() -> Path:
    """Finds the root directory of the active Python interpreter."""
    return Path(sys.prefix)


def clear_cache_and_recompile(file_path: Path) -> None:
    """
    Removes the __pycache__ directory containing the compiled bytecode for
    the modified Python file and forces a fresh recompilation.
    """
    parent_dir = file_path.parent
    pycache_dir = parent_dir / "__pycache__"

    if pycache_dir.exists():
        try:
            shutil.rmtree(pycache_dir, ignore_errors=True)
        except Exception as e:
            print(
                f"  -> Note: Failed to remove cache folder at {pycache_dir}: {e}",
                file=sys.stderr,
            )
    try:
        compileall.compile_file(str(file_path), force=True, quiet=1)
    except Exception as e:
        print(
            f"  -> Note: Failed to recompile {file_path}: {e}",
            file=sys.stderr,
        )


def main() -> None:
    """Applies all .patch files found in the 'patches' directory."""
    script_dir = Path(__file__).parent.resolve()
    patches_dir = script_dir / "patches"

    py_path = get_py_path()
    site_packages = py_path / "Lib" / "site-packages"

    if not patches_dir.exists():
        print("No 'patches' directory found. Nothing to apply.")
        return

    patch_files = list(patches_dir.glob("*.patch"))
    if not patch_files:
        print("No .patch files found in 'patches' directory. Nothing to apply.")
        return

    print("--- Applying patches ---")
    all_successful = True
    for patch_file in patch_files:
        print(f"Applying '{patch_file.name}'...")
        try:
            patch_set = patch.fromfile(patch_file)
            if patch_set.apply(root=site_packages):
                print("  -> Success.")
                for p in patch_set:
                    target: bytes | None = p.target
                    if target:
                        target_str = target.decode("utf-8", errors="ignore")
                        target_path = site_packages / target_str
                        clear_cache_and_recompile(target_path)
            else:
                print(
                    "  -> WARNING: Patch did not apply cleanly. It may already be applied or the target file has changed.",
                    file=sys.stderr,
                )
                all_successful = False

        except Exception as e:
            print(
                "  -> ERROR: An unexpected error occurred while applying patch.",
                file=sys.stderr,
            )
            print(f"     {e}", file=sys.stderr)
            all_successful = False

    print("------------------------")
    if not all_successful:
        print(
            "One or more patches had issues. Please review the log.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
