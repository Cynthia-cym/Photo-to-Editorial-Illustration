#!/usr/bin/env python3
"""Resolve paths for the isolated photo-to-editorial-illustration image runtime."""

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from typing import Dict, Mapping, Optional, Sequence


RUNTIME_VERSION = "runtime-v1"
REQUIREMENTS_PATH = Path(__file__).resolve().parents[1] / "requirements-runtime.txt"
MANIFEST_NAME = "runtime-manifest.json"
EXPECTED_VERSIONS = {"Pillow": "12.3.0", "pillow_heif": "1.5.0"}
PYTHON_REQUIREMENT = ">=3.10"
MINIMUM_PYTHON = (3, 10)
PROBE_TIMEOUT_SECONDS = 30
INSTALL_TIMEOUT_SECONDS = 300
STDERR_SUMMARY_LIMIT = 240
SKILL_ROOT = Path(__file__).resolve().parents[1]
SOURCE_TREE_ROOT = Path(__file__).resolve().parents[2]


def resolve_cache_root(
    system_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return the versioned, user-owned runtime cache directory."""
    system_name = system_name or platform.system()
    environ = dict(os.environ if environ is None else environ)
    home = Path.home() if home is None else Path(home)

    if system_name == "Darwin":
        base = home / "Library" / "Caches"
    elif system_name == "Windows":
        override = environ.get("LOCALAPPDATA")
        base = (
            Path(override)
            if override and PureWindowsPath(override).is_absolute()
            else home / "AppData" / "Local"
        )
    else:
        override = environ.get("XDG_CACHE_HOME")
        candidate = Path(override) if override else None
        base = candidate if candidate and candidate.is_absolute() else home / ".cache"

    return base / "photo-to-editorial-illustration" / RUNTIME_VERSION


def _runtime_paths_from_root(
    root: Path, system_name: Optional[str] = None
) -> Dict[str, Path]:
    system_name = system_name or platform.system()
    python_path = root / (
        "Scripts/python.exe" if system_name == "Windows" else "bin/python"
    )
    return {
        "root": root,
        "python": python_path,
        "manifest": root / MANIFEST_NAME,
    }


def runtime_paths(root: Path, system_name: Optional[str] = None) -> Dict[str, Path]:
    """Return the canonical paths owned by a runtime rooted at ``root``."""
    root = Path(root).expanduser().resolve()
    return _runtime_paths_from_root(root, system_name)


def manifest_is_valid(payload: object) -> bool:
    """Return whether a runtime manifest has the expected schema and pins."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return False
    return all(
        payload.get(package) == version
        for package, version in EXPECTED_VERSIONS.items()
    )


def build_pip_command(isolated_python: Path):
    """Build the exact-pinned install command for an isolated interpreter."""
    return [
        str(isolated_python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(REQUIREMENTS_PATH),
    ]


def _controlled_environment(for_pip: bool = False) -> Dict[str, str]:
    """Return an environment without Python or pip redirection settings."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "PIP"))
        and key.upper() not in {"VIRTUAL_ENV", "__PYVENV_LAUNCHER__"}
    }
    environment["PIP_CONFIG_FILE"] = os.devnull
    if for_pip:
        environment.update(
            {
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_NO_INPUT": "1",
            }
        )
    return environment


def _stderr_summary(stderr: object) -> str:
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    if not isinstance(stderr, str) or not stderr:
        return ""
    printable = "".join(
        character if character.isprintable() else " " for character in stderr
    )
    summary = " ".join(printable.split())
    if len(summary) > STDERR_SUMMARY_LIMIT:
        summary = summary[: STDERR_SUMMARY_LIMIT - 3].rstrip() + "..."
    return summary


def _run_captured(command, label: str, timeout: int, for_pip: bool = False):
    """Run a setup subprocess without allowing output to reach CLI stdout."""
    try:
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=True,
            env=_controlled_environment(for_pip=for_pip),
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        summary = _stderr_summary(getattr(exc, "stderr", None))
        message = f"{label} failed"
        if summary:
            message = f"{message}: {summary}"
        raise RuntimeError(message) from exc


def _is_within(path: Path, root: Path) -> bool:
    try:
        Path(path).expanduser().resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _manifest_from_probe(payload: object, runtime_root: Path) -> Dict[str, object]:
    """Validate isolated-runtime identity and return the stable manifest fields."""
    if not isinstance(payload, dict):
        raise RuntimeError("isolated image runtime probe returned invalid data")

    python_version = payload.get("python")
    try:
        version = tuple(int(part) for part in python_version.split("."))
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("isolated image runtime probe returned invalid data") from exc
    if version[:2] < MINIMUM_PYTHON:
        raise RuntimeError(
            f"isolated image runtime requires Python {PYTHON_REQUIREMENT}"
        )

    try:
        prefix = Path(payload["prefix"]).expanduser().resolve()
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise RuntimeError("isolated image runtime probe returned invalid prefix") from exc
    runtime_root = runtime_root.resolve()
    if prefix != runtime_root:
        raise RuntimeError("isolated image runtime prefix is outside the runtime root")

    for field in (
        "Pillow_location",
        "pillow_heif_location",
        "pillow_heif_distribution_location",
    ):
        try:
            location = Path(payload[field])
        except (KeyError, TypeError) as exc:
            raise RuntimeError(
                "isolated image runtime probe returned invalid package locations"
            ) from exc
        if not _is_within(location, runtime_root):
            raise RuntimeError(
                "isolated image runtime package location is outside the runtime root"
            )

    manifest = {
        "schema_version": payload.get("schema_version"),
        "python": python_version,
        "Pillow": payload.get("Pillow"),
        "pillow_heif": payload.get("pillow_heif"),
    }
    if not manifest_is_valid(manifest):
        raise RuntimeError("isolated image runtime versions do not match exact pins")
    return manifest


def _read_installed_versions(isolated_python: Path) -> Dict[str, object]:
    """Probe Python and package versions inside the isolated interpreter."""
    script = (
        "import importlib.metadata, json, pathlib, platform, sys, PIL, pillow_heif; "
        "distribution = importlib.metadata.distribution('pillow-heif'); "
        "print(json.dumps({'schema_version': 1, "
        "'python': platform.python_version(), 'Pillow': PIL.__version__, "
        "'pillow_heif': importlib.metadata.version('pillow-heif'), "
        "'prefix': str(pathlib.Path(sys.prefix).resolve()), "
        "'Pillow_location': str(pathlib.Path(PIL.__file__).resolve()), "
        "'pillow_heif_location': str(pathlib.Path(pillow_heif.__file__).resolve()), "
        "'pillow_heif_distribution_location': "
        "str(pathlib.Path(distribution.locate_file('')).resolve())}, "
        "sort_keys=True))"
    )
    result = _run_captured(
        [str(isolated_python), "-I", "-B", "-c", script],
        "isolated image runtime probe",
        PROBE_TIMEOUT_SECONDS,
    )
    runtime_root = Path(isolated_python).expanduser().parent.parent.resolve()
    return _manifest_from_probe(json.loads(result.stdout), runtime_root)


def _base_python_version(base_python: Path):
    """Read the version tuple from the requested base interpreter."""
    result = _run_captured(
        [
            str(base_python),
            "-I",
            "-B",
            "-c",
            "import json, sys; print(json.dumps(list(sys.version_info[:3])))",
        ],
        "base Python version probe",
        PROBE_TIMEOUT_SECONDS,
    )
    try:
        version = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("base Python version probe returned invalid data") from exc
    if (
        not isinstance(version, list)
        or len(version) < 2
        or any(type(part) is not int for part in version)
    ):
        raise RuntimeError("base Python version probe returned invalid data")
    return tuple(version)


def _inspect_base_python(base_python: Optional[Path]) -> Dict[str, object]:
    requested = Path(sys.executable if base_python is None else base_python).expanduser()
    absolute = requested.absolute()
    metadata = {
        "base_python": str(absolute),
        "base_python_version": None,
        "base_python_compatible": False,
    }
    if not requested.is_file():
        return metadata
    try:
        version = _base_python_version(requested)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        return metadata
    metadata["base_python_version"] = ".".join(str(part) for part in version)
    metadata["base_python_compatible"] = version >= MINIMUM_PYTHON
    return metadata


def inspect_runtime(
    root: Path,
    system_name: Optional[str] = None,
    base_python: Optional[Path] = None,
) -> Dict[str, object]:
    """Inspect an isolated runtime without modifying the filesystem."""
    requested_root = Path(root).expanduser()
    base_metadata = _inspect_base_python(base_python)
    dangling_root = (
        os.path.lexists(requested_root)
        and requested_root.is_symlink()
        and not requested_root.exists()
    )
    paths = (
        _runtime_paths_from_root(requested_root.absolute(), system_name)
        if dangling_root
        else runtime_paths(requested_root, system_name)
    )
    payload = {
        "schema_version": 1,
        "root": str(paths["root"]),
        "python": str(paths["python"]),
        "manifest": str(paths["manifest"]),
        "requirements": str(REQUIREMENTS_PATH),
        "packages": dict(EXPECTED_VERSIONS),
        "python_requirement": PYTHON_REQUIREMENT,
        "network_required": True,
        "status": "missing",
        "install_required": True,
        **base_metadata,
    }
    if dangling_root:
        payload["status"] = "invalid"
        return payload
    if not paths["root"].exists():
        return payload
    if not paths["python"].is_file() or not paths["manifest"].is_file():
        payload["status"] = "invalid"
        return payload

    try:
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        payload["status"] = "invalid"
        return payload

    try:
        installed = _read_installed_versions(paths["python"])
    except (
        OSError,
        UnicodeError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ):
        payload["status"] = "invalid"
        return payload

    if manifest_is_valid(manifest) and installed == manifest:
        payload["status"] = "ready"
        payload["install_required"] = False
        payload["network_required"] = False
    else:
        payload["status"] = "invalid"
    return payload


def install_runtime(root: Path, base_python: Path) -> Dict[str, object]:
    """Create an isolated runtime after the CLI's explicit approval gate."""
    root = Path(root).expanduser()
    if os.path.lexists(root):
        raise FileExistsError(f"runtime path already exists: {root.absolute()}")
    paths = runtime_paths(root)
    if any(
        _is_within(paths["root"], forbidden_root)
        for forbidden_root in (SOURCE_TREE_ROOT, SKILL_ROOT)
    ):
        raise RuntimeError("runtime path must be outside the source or Skill tree")

    base_python = Path(base_python).expanduser().resolve()
    if not base_python.is_file():
        raise FileNotFoundError(f"base Python does not exist: {base_python}")
    if _base_python_version(base_python) < MINIMUM_PYTHON:
        raise RuntimeError("image runtime requires Python 3.10 or newer")

    paths["root"].parent.mkdir(parents=True, exist_ok=True)
    _run_captured(
        [str(base_python), "-m", "venv", str(paths["root"])],
        "image runtime virtual environment creation",
        INSTALL_TIMEOUT_SECONDS,
    )
    _run_captured(
        build_pip_command(paths["python"]),
        "image runtime dependency installation",
        INSTALL_TIMEOUT_SECONDS,
        for_pip=True,
    )

    manifest = _read_installed_versions(paths["python"])
    if not manifest_is_valid(manifest):
        raise RuntimeError("installed image runtime versions do not match exact pins")
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    inspection = inspect_runtime(paths["root"], base_python=base_python)
    if inspection.get("status") != "ready":
        raise RuntimeError("installed image runtime failed final validation")
    return inspection


def _parse_args(argv: Optional[Sequence[str]] = None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inspect", action="store_true")
    action.add_argument("--approve-install", action="store_true")
    parser.add_argument("--cache-root")
    parser.add_argument("--base-python", default=sys.executable)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None):
    args = _parse_args(argv)
    try:
        root = (
            Path(args.cache_root).expanduser()
            if args.cache_root
            else resolve_cache_root()
        )
        payload = (
            install_runtime(root, Path(args.base_python))
            if args.approve_install
            else inspect_runtime(root, base_python=Path(args.base_python))
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
