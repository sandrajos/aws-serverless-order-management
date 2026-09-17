"""Build deployment ZIPs for the project's AWS Lambda functions.

The script is intentionally cross-platform so packaging works on Windows,
Linux, and macOS without shell-specific commands.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
BUILD_ROOT = PROJECT_ROOT / "terraform" / ".build"

FUNCTIONS = {
    "create_order": ["handler.py"],
    "process_order": ["handler.py"],
    "notify": ["handler.py"],
}


def add_file(zip_file: ZipFile, source: Path, archive_name: str) -> None:
    """Add a file using deterministic ZIP metadata."""

    info = ZipInfo(archive_name)
    info.date_time = (2020, 1, 1, 0, 0, 0)
    info.compress_type = ZIP_DEFLATED

    with source.open("rb") as file:
        zip_file.writestr(info, file.read())


def build_function(function_name: str, files: list[str]) -> Path:
    """Create one Lambda deployment ZIP."""

    function_dir = SRC_ROOT / function_name
    output = BUILD_ROOT / f"{function_name}.zip"

    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        output.unlink()

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as zip_file:
        for relative_file in sorted(files):
            source = function_dir / relative_file

            if not source.is_file():
                raise FileNotFoundError(f"Missing Lambda file: {source}")

            add_file(zip_file, source, relative_file)

        common_dir = SRC_ROOT / "common"

        for source in sorted(common_dir.glob("*.py")):
            add_file(
                zip_file,
                source,
                f"common/{source.name}",
            )

    return output


def main() -> None:
    """Build all Lambda deployment packages."""

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)

    for function_name, files in FUNCTIONS.items():
        output = build_function(function_name, files)
        print(f"Created: {output}")


if __name__ == "__main__":
    main()