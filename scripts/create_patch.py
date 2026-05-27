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
import difflib
import filecmp
from pathlib import Path
# ---------------------------------


def create_patch_for_file(
    original_file: Path, patched_file: Path, patches_dir: Path
) -> None:
    """
    Compares two files and, if different, creates a .patch file.
    The patch filename is derived from the file's relative path.
    """
    relative_path = patched_file.relative_to(patches_dir.parent / "staging" / "patched")

    patch_name = str(relative_path).replace("\\", "/").replace("/", "-")
    patch_name = Path(patch_name).with_suffix(".patch").name
    patch_output_file = patches_dir / patch_name

    print(f"  -> Comparing '{relative_path}'...")

    if filecmp.cmp(original_file, patched_file, shallow=False):
        print("     Files are identical. Skipping patch creation.")
        if patch_output_file.exists():
            print(f"     Deleting obsolete patch file: '{patch_output_file.name}'")
            patch_output_file.unlink()
        return

    print(f"     Files differ. Generating patch: '{patch_output_file.name}'")

    with open(original_file, "r", encoding="utf-8") as f:
        original_lines = f.readlines()

    with open(patched_file, "r", encoding="utf-8") as f:
        patched_lines = f.readlines()

    diff_from_path = str(
        original_file.relative_to(patches_dir.parent / "staging" / "original")
    ).replace("\\", "/")
    diff_to_path = str(
        patched_file.relative_to(patches_dir.parent / "staging" / "patched")
    ).replace("\\", "/")

    diff_generator = difflib.unified_diff(
        original_lines,
        patched_lines,
        fromfile=diff_from_path,
        tofile=diff_to_path,
    )

    diff_text = "".join(diff_generator)

    patches_dir.mkdir(exist_ok=True)
    with open(patch_output_file, "w", encoding="utf-8") as f:
        f.write(diff_text)


def main() -> None:
    """
    Scans the 'staging/patched' directory and creates patch files for any
    files that differ from their counterparts in 'staging/original'.
    """
    script_dir = Path(__file__).parent.resolve()

    original_base = script_dir / "staging" / "original"
    patched_base = script_dir / "staging" / "patched"
    patches_dir = script_dir / "patches"

    if not original_base.is_dir() or not patched_base.is_dir():
        print(
            "ERROR: Both 'staging/original' and 'staging/patched' directories must exist."
        )
        return

    print(f"--- Scanning for modified files in '{patched_base}' ---")

    files_processed = 0
    for patched_file in patched_base.rglob("*"):
        if not patched_file.is_file():
            continue

        files_processed += 1

        relative_path = patched_file.relative_to(patched_base)
        original_file = original_base / relative_path

        if not original_file.exists():
            print(
                f"  -> WARNING: Found patched file '{relative_path}' but no corresponding original file. Skipping."
            )
            continue

        create_patch_for_file(original_file, patched_file, patches_dir)

    if files_processed == 0:
        print("No files found in the 'staging/patched' directory to process.")

    print("-------------------------------------------------")
    print("Patch creation process complete.")


if __name__ == "__main__":
    main()
