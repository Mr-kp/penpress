"""Cross-platform packaging and binary compilation tool for PenPress.

Produces standalone single-file distribution binaries using PyInstaller
for Linux, macOS, and Windows.
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
RELEASE_DIR = ROOT / "release"


def compute_sha256(path: Path) -> str:
    """Calculate the hex SHA256 digest of a binary file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_standalone_binary(
    dist_dir: Path = DIST_DIR,
    build_dir: Path = BUILD_DIR,
    onefile: bool = True,
) -> Path:
    """Compile penpress entrypoint into a standalone executable via PyInstaller."""
    entry_script = SRC_DIR / "penpress" / "__main__.py"
    if not entry_script.is_file():
        raise FileNotFoundError(f"Entry script not found at {entry_script}")

    system = platform.system().lower()
    binary_name = "penpress.exe" if system == "windows" else "penpress"

    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    # Hidden imports and data folders
    web_dir = ROOT / "web"
    data_dir = SRC_DIR / "penpress" / "core" / "data"
    sep = ";" if system == "windows" else ":"
    data_args: list[str] = []
    if web_dir.is_dir():
        data_args.extend(["--add-data", f"{web_dir}{sep}web"])
    if data_dir.is_dir():
        data_args.extend(["--add-data", f"{data_dir}{sep}penpress/core/data"])
    r21_dir = ROOT / "research" / "R2-1"
    if r21_dir.is_dir():
        mathjax_js = r21_dir / "mathjax_layout.js"
        if mathjax_js.is_file():
            data_args.extend(["--add-data", f"{mathjax_js}{sep}research/R2-1"])
        pkg_json = r21_dir / "package.json"
        if pkg_json.is_file():
            data_args.extend(["--add-data", f"{pkg_json}{sep}research/R2-1"])
        node_modules = r21_dir / "node_modules"
        if node_modules.is_dir():
            data_args.extend(["--add-data", f"{node_modules}{sep}research/R2-1/node_modules"])

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--collect-all",
        "penpress",
        "--name",
        "penpress",
        "--clean",
        "--noconfirm",
        "--workpath",
        str(build_dir),
        "--distpath",
        str(dist_dir),
        "--paths",
        str(SRC_DIR),
        *data_args,
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols",
        "--hidden-import",
        "uvicorn.protocols.http",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.lifespan",
        "--hidden-import",
        "uvicorn.lifespan.on",
    ]

    if onefile:
        cmd.append("--onefile")

    cmd.append(str(entry_script))

    print(f"Building standalone binary for {system}...")
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller build failed with exit code {result.returncode}")

    target_binary = dist_dir / binary_name
    if not target_binary.is_file():
        raise FileNotFoundError(f"Expected compiled binary not found at {target_binary}")

    size = target_binary.stat().st_size
    print(f"Successfully compiled standalone executable: {target_binary} ({size} bytes)")
    return target_binary


def generate_release_manifest(
    artifacts: list[Path],
    release_dir: Path = RELEASE_DIR,
    version: str = "v0.1.0",
) -> tuple[Path, Path]:
    """Generate SHA256 checksums and markdown release manifest for distributions."""
    release_dir.mkdir(parents=True, exist_ok=True)

    checksum_file = release_dir / "checksums.sha256"
    manifest_file = release_dir / "MANIFEST.md"

    checksum_lines: list[str] = []
    manifest_rows: list[str] = []

    for artifact in artifacts:
        if not artifact.is_file():
            continue
        checksum = compute_sha256(artifact)
        size_mb = artifact.stat().st_size / (1024 * 1024)
        checksum_lines.append(f"{checksum}  {artifact.name}\n")
        manifest_rows.append(f"| `{artifact.name}` | {size_mb:.2f} MB | `{checksum}` |")

    checksum_file.write_text("".join(checksum_lines), encoding="utf-8")

    manifest_md = f"""# PenPress Release {version} Manifest

Commercial distribution artifacts for PenPress {version}.

## Integrity Verification (SHA-256)

| Artifact | Size | SHA-256 Checksum |
|---|---|---|
{chr(10).join(manifest_rows)}

## Verification Command
```bash
sha256sum -c checksums.sha256
```
"""
    manifest_file.write_text(manifest_md, encoding="utf-8")
    print(f"Generated manifest at {manifest_file} and checksums at {checksum_file}")
    return manifest_file, checksum_file


def main(argv: list[str] | None = None) -> int:
    """CLI runner for standalone packaging."""
    parser = argparse.ArgumentParser(description="PenPress packaging tool.")
    parser.add_argument(
        "--dist",
        type=Path,
        default=DIST_DIR,
        help="Target distribution directory.",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Generate release checksums and manifest.",
    )
    args = parser.parse_args(argv)

    try:
        binary = build_standalone_binary(dist_dir=args.dist)
        if args.release:
            generate_release_manifest([binary])
        return 0
    except Exception as exc:
        print(f"Packaging error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
