"""
Configuration file support for extraction CLI.

Supports loading defaults from:
1. CLI flags (highest priority)
2. ./extraction.toml (project-level)
3. pyproject.toml [tool.extraction] section
4. ~/.config/extraction/config.toml (user-level)
5. Built-in defaults (lowest priority)
"""

import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib


DEFAULT_CONFIG = {
    "chunking_strategy": "rag",
    "min_chunk_words": 100,
    "max_chunk_words": 500,
    "filter_noise": True,
    "filter_tiny_chunks": "conservative",
    "preserve_small_chunks": True,
    "detect_front_matter": False,
    "filter_front_matter": False,
    "detect_references": False,
    "detect_visual_headings": False,
    "visual_heading_font_threshold": 1.3,
    "toc_hierarchy_level": 1,
    "preserve_hierarchy_across_docs": False,
    "analyzer": "generic",
}


def find_config_files() -> list[Path]:
    """
    Find all config files in priority order (highest first).

    Returns:
        List of existing config file paths
    """
    candidates = []

    # Project-level: ./extraction.toml
    project_config = Path("extraction.toml")
    if project_config.exists():
        candidates.append(project_config)

    # pyproject.toml in current directory or parent directories
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            candidates.append(pyproject)
            break

    # User-level: ~/.config/extraction/config.toml
    user_config = Path.home() / ".config" / "extraction" / "config.toml"
    if user_config.exists():
        candidates.append(user_config)

    return candidates


def load_toml_file(path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def extract_config_from_toml(data: dict[str, Any], is_pyproject: bool = False) -> dict[str, Any]:
    """
    Extract extraction config from TOML data.

    Args:
        data: Parsed TOML data
        is_pyproject: If True, look under [tool.extraction]

    Returns:
        Config dictionary (may be empty)
    """
    if is_pyproject:
        return data.get("tool", {}).get("extraction", {})
    return data


def load_config() -> dict[str, Any]:
    """
    Load merged configuration from all sources.

    Returns:
        Merged config dictionary with all defaults applied
    """
    config = DEFAULT_CONFIG.copy()

    # Load from files in reverse priority order (lowest first)
    config_files = find_config_files()

    for path in reversed(config_files):
        try:
            data = load_toml_file(path)
            is_pyproject = path.name == "pyproject.toml"
            file_config = extract_config_from_toml(data, is_pyproject)

            # Only update keys that exist in DEFAULT_CONFIG
            for key, value in file_config.items():
                if key in DEFAULT_CONFIG:
                    config[key] = value
        except Exception:
            pass

    return config


def get_config_value(key: str, cli_value: Any = None) -> Any:
    """
    Get a config value with CLI override support.

    Args:
        key: Config key name
        cli_value: Value from CLI (None if not provided)

    Returns:
        Final config value
    """
    if cli_value is not None:
        return cli_value

    config = load_config()
    return config.get(key, DEFAULT_CONFIG.get(key))


def show_config_sources() -> str:
    """
    Show which config files are being used.

    Returns:
        Human-readable string describing config sources
    """
    lines = ["Configuration sources (highest priority first):"]

    config_files = find_config_files()
    if not config_files:
        lines.append("  (no config files found, using defaults)")
    else:
        for path in config_files:
            lines.append(f"  - {path}")

    lines.append(f"  - Built-in defaults")

    return "\n".join(lines)


def generate_sample_config() -> str:
    """
    Generate a sample config file with all options documented.

    Returns:
        TOML string for extraction.toml
    """
    return '''# Extraction configuration
# Place this file as:
#   - ./extraction.toml (project-level)
#   - ~/.config/extraction/config.toml (user-level)
# Or add [tool.extraction] section to pyproject.toml

# Chunking strategy: "rag" (100-500 words) or "nlp" (paragraph-level)
chunking_strategy = "rag"
min_chunk_words = 100
max_chunk_words = 500

# Noise filtering
filter_noise = true
filter_tiny_chunks = "conservative"  # off, conservative, standard, aggressive
preserve_small_chunks = true

# Front/back matter detection (EPUB only)
detect_front_matter = false
filter_front_matter = false

# Reference block detection (EPUB only)
detect_references = false

# Visual heading detection (EPUB only)
detect_visual_headings = false
visual_heading_font_threshold = 1.3

# Hierarchy settings (EPUB only)
toc_hierarchy_level = 1
preserve_hierarchy_across_docs = false

# Default analyzer: "generic" or "catholic"
analyzer = "generic"
'''
