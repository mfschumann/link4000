"""Enumerations used throughout the link4000 application."""

from enum import Enum, auto


class TagMatchMode(Enum):
    """Match mode for tag filtering."""

    OR = auto()      # Match ANY tag (items with at least one selected tag)
    AND = auto()     # Match ALL tags (items must have every selected tag)
    NONE = auto()    # Match NO tags (items must have none of the selected tags)
