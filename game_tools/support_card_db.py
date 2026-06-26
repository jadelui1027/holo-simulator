#!/usr/bin/env python3
"""
hOCG Support Card Database & Executor -- Compatibility Facade
=============================================================
This module re-exports everything that was originally defined here,
now split across three focused modules:

  - card_types        : ActionType, ConditionType, CostType enums
  - card_data         : SUPPORT_CARD_DB dict + all card registrations
  - action_executor   : SupportCardExecutor class

Existing imports like ``from .support_card_db import SupportCardExecutor``
continue to work unchanged.
"""

from __future__ import annotations

import json
import os
from enum import Enum

# -- Re-exports (backwards compat) --
from .card_types import ActionType, ConditionType, CostType       # noqa: F401
from .card_data import SUPPORT_CARD_DB                            # noqa: F401
from .action_executor import SupportCardExecutor                  # noqa: F401

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ======================================================================
#  UTILITY: Export database as JSON
# ======================================================================

def export_db_json(filepath: str = None):
    """Export the support card database as a JSON file."""
    if filepath is None:
        filepath = os.path.join(SCRIPT_DIR, "support_card_db.json")

    def serialize(obj):
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(SUPPORT_CARD_DB, f, ensure_ascii=False, indent=2, default=serialize)
    print(f"Exported {len(SUPPORT_CARD_DB)} support cards to {filepath}")


# ======================================================================
#  CLI entry point
# ======================================================================

if __name__ == "__main__":
    import sys

    if "--export" in sys.argv:
        export_db_json()
    elif "--stats" in sys.argv:
        print(f"Total support cards in database: {len(SUPPORT_CARD_DB)}")
        from collections import Counter
        type_counts = Counter(e["card_type"] for e in SUPPORT_CARD_DB.values())
        for t, c in type_counts.most_common():
            print(f"  {t}: {c}")
        limited = sum(1 for e in SUPPORT_CARD_DB.values() if e.get("is_limited"))
        attachable = sum(1 for e in SUPPORT_CARD_DB.values() if e.get("attachment_type"))
        playable = len(SUPPORT_CARD_DB) - attachable
        print(f"\n  Playable cards: {playable}")
        print(f"  Attachable cards: {attachable}")
        print(f"  LIMITED cards: {limited}")
    elif "--list" in sys.argv:
        for cn, entry in sorted(SUPPORT_CARD_DB.items()):
            ltd = " [LIMITED]" if entry.get("is_limited") else ""
            att = f" [{entry['attachment_type']}]" if entry.get("attachment_type") else ""
            print(f"  {cn} | {entry['card_name']}{ltd}{att}")
    elif "--test" in sys.argv:
        sys.path.insert(0, SCRIPT_DIR)
        from playmat_manager import PlaymatManager, Zone

        pm = PlaymatManager()
        executor = SupportCardExecutor(pm)

        print("\n=== Test: hSD01-016 (Draw 3) ===")
        for i in range(10):
            pm.place_card_by_number(Zone.DECK, "hBP01-104", face_up=False)
        pm.place_card_by_number(Zone.HAND, "hSD01-016", face_up=True)
        result = executor.play_support("hSD01-016")
        print(f"\nResult: {result}")
        print(f"\nHand after: {[c.card_name for c in pm.zones[Zone.HAND]]}")

        print("\n=== Test: hBP05-080 (Draw 2 + View 5) ===")
        pm.clear_all()
        for i in range(20):
            pm.place_card_by_number(Zone.DECK, "hBP01-104", face_up=False)
        pm.place_card_by_number(Zone.HAND, "hBP05-080", face_up=True)
        executor.start_turn()
        result = executor.play_support("hBP05-080")
        print(f"\nResult: {result}")
        print(f"Hand after: {[c.card_name for c in pm.zones[Zone.HAND]]}")
    else:
        print("hOCG Support Card Database")
        print(f"  {len(SUPPORT_CARD_DB)} cards registered")
        print("\nUsage:")
        print("  --export   Export database as JSON")
        print("  --stats    Show database statistics")
        print("  --list     List all cards")
        print("  --test     Run test with PlaymatManager")
