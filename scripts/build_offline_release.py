"""Export a curated offline reproducibility candidate without publishing it.

Evidence is copied byte-for-byte. This is a public-repository candidate, not
an anonymization tool: historical provenance can contain local filesystem paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def selected_paths() -> list[Path]:
    """Export the curated tracked tree, never unreviewed local files."""
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached"], cwd=ROOT
    ).decode("utf-8").split("\\0")
    return sorted((ROOT / name for name in tracked if name),
                  key=lambda path: path.relative_to(ROOT).as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New directory outside this checkout; existing paths are refused.")
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if destination.is_relative_to(ROOT) or destination.exists():
        parser.error("Use a new output directory outside the repository.")
    archive_path = destination.with_suffix(".zip")
    if archive_path.exists():
        parser.error("The output archive already exists.")
    rows = []
    for source in selected_paths():
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Missing or symlinked release input: {source.relative_to(ROOT)}")
        relative = source.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        content = target.read_bytes()
        rows.append({"path": relative.as_posix(), "bytes": len(content),
                     "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {
        "status": "local_offline_candidate_unpublished",
        "anonymity": "public_repository_export; not_certified_anonymous",
        "files": rows,
        "exclusions": [".git", ".env", "virtual environments", "reviews",
                       "model weights", "trace_db", "local logs/render histories",
                       "duplicate reproduction outputs", "collection finalizer state"],
    }
    (destination / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(destination).as_posix())
    print(json.dumps({"status": manifest["status"], "file_count": len(rows),
                      "uncompressed_bytes": sum(row["bytes"] for row in rows),
                      "archive": str(archive_path), "archive_bytes": archive_path.stat().st_size,
                      "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
