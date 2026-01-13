#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
State machine for extractor lifecycle.

Enforces correct method call order during document extraction.
"""

from enum import Enum, auto


class ExtractorState(Enum):
    """
    States for extractor lifecycle.

    Lifecycle progression:
    CREATED → LOADED → PARSED → METADATA_READY → OUTPUT_READY

    States:
        CREATED: Extractor instantiated, no document loaded
        LOADED: Document loaded, ready to parse
        PARSED: Document parsed, chunks extracted
        METADATA_READY: Metadata extracted, ready for output
        OUTPUT_READY: Output data generated, ready to serialize
    """

    CREATED = auto()
    LOADED = auto()
    PARSED = auto()
    METADATA_READY = auto()
    OUTPUT_READY = auto()

    def can_load(self) -> bool:
        """Check if load() can be called in current state."""
        return self == ExtractorState.CREATED

    def can_parse(self) -> bool:
        """Check if parse() can be called in current state."""
        return self == ExtractorState.LOADED

    def can_extract_metadata(self) -> bool:
        """Check if extract_metadata() can be called in current state."""
        return self == ExtractorState.PARSED

    def can_get_output(self) -> bool:
        """Check if get_output_data() can be called in current state."""
        return self in (ExtractorState.METADATA_READY, ExtractorState.OUTPUT_READY)

    def is_ready_for_output(self) -> bool:
        """Check if extractor is ready to generate output."""
        return self in (ExtractorState.METADATA_READY, ExtractorState.OUTPUT_READY)
