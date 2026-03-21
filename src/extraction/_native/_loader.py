import ctypes
import logging
import platform
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)

ABI_VERSION = 1


class LibraryLoadError(Exception):
    pass


def _find_library(name: str) -> Path | None:
    lib_dir = Path(__file__).parent / "lib"
    system = platform.system()
    if system == "Darwin":
        suffix = ".dylib"
    elif system == "Linux":
        suffix = ".so"
    elif system == "Windows":
        suffix = ".dll"
    else:
        suffix = ".so"

    candidates = [
        lib_dir / f"lib{name}{suffix}",
        lib_dir / f"{name}{suffix}",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def load_library(name: str, expected_abi: int = ABI_VERSION) -> ctypes.CDLL:
    path = _find_library(name)
    if path is None:
        raise LibraryLoadError(
            f"Native library '{name}' not found in {Path(__file__).parent / 'lib'}"
        )

    try:
        lib = ctypes.CDLL(str(path))
    except OSError as e:
        raise LibraryLoadError(f"Failed to load {path}: {e}") from e

    lib.de_abi_version.argtypes = []
    lib.de_abi_version.restype = ctypes.c_uint32
    version = lib.de_abi_version()
    if version != expected_abi:
        raise LibraryLoadError(
            f"ABI version mismatch: library={version}, expected={expected_abi}"
        )

    return lib
