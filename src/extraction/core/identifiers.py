#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ID generation utilities for extraction system.

CRITICAL: These functions are used to generate stable IDs for documents and chunks.
The implementation MUST NOT change to maintain backward compatibility with existing IDs.
"""

import hashlib


def sha1(x: bytes) -> str:
    """Return SHA-1 hash of input bytes as a hex string."""
    return hashlib.sha1(x).hexdigest()


def stable_id(*parts: str) -> str:
    """Create a stable ID by hashing joined parts. Shorten to 16 hex chars."""
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:16]
