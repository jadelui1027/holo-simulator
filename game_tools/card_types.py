"""
hOCG Card Type Enumerations
============================
Lightweight enum definitions shared across the card data, executor, and engine.
Extracted from support_card_db.py for cleaner imports and zero circular deps.
"""

from __future__ import annotations
from enum import Enum


# ─── Action type enumeration ───────────────────────────────────────────────

class ActionType(str, Enum):
    """Atomic action types that the executor understands."""
    # ── Drawing / hand manipulation ──
    DRAW = "draw"                           # Draw N cards from deck
    SHUFFLE_HAND_DRAW = "shuffle_hand_draw" # Return entire hand to deck, shuffle, draw N

    # ── Viewing / searching deck ──
    VIEW_DECK_TOP = "view_deck_top"         # Look at top N, pick matching, rest to bottom
    SEARCH_DECK = "search_deck"             # Search entire deck for card(s), add to hand
    SEARCH_DECK_TO_STAGE = "search_deck_to_stage"  # Search deck, put on stage

    # ── Searching other zones ──
    SEARCH_YELL_DECK = "search_yell_deck"   # Search yell deck for cheer
    SEARCH_ARCHIVE = "search_archive"       # Return card(s) from archive

    # ── Movement / swapping ──
    SWAP_OPPONENT_CENTER_BACK = "swap_opponent_center_back"
    SWAP_OWN_CENTER_BACK = "swap_own_center_back"
    MOVE_CHEER = "move_cheer"               # Re-attach cheer between holomen
    OPPONENT_MOVE_BACK_TO_COLLAB = "opponent_move_back_to_collab"
    OPPONENT_REST_TO_BACK = "opponent_rest_to_back"      # Rest opponent + move to back
    RETURN_STACKED_TO_HAND = "return_stacked_to_hand"    # Return bloom stack cards

    # ── Cheer / Yell management ──
    ARCHIVE_TO_YELL_DECK = "archive_to_yell_deck"       # Return archive cheers to yell deck
    ARCHIVE_CHEER_TO_HOLOMEN = "archive_cheer_to_holomen"
    YELL_DECK_TOP_TO_HOLOMEN = "yell_deck_top_to_holomen"
    SEND_ARCHIVE_CHEER_SPLIT = "send_archive_cheer_split"  # Split cheers to center+collab
    ARCHIVE_YELL_DECK_TOP = "archive_yell_deck_top"      # Archive top card of yell deck

    # ── Combat / damage ──
    DEAL_SPECIAL_DAMAGE = "deal_special_damage"
    HEAL = "heal"

    # ── Stat modifiers (this-turn) ──
    ARTS_BOOST = "arts_boost"
    BATON_TOUCH_COST_REDUCE = "baton_touch_cost_reduce"
    ARTS_COST_REDUCE = "arts_cost_reduce"

    # ── Dice ──
    ROLL_DICE = "roll_dice"

    # ── Extra bloom ──
    EXTRA_BLOOM = "extra_bloom"

    # ── Card-specific complex ──
    HAND_CARD_TO_DECK_BOTTOM = "hand_card_to_deck_bottom"  # Put a hand card to deck bottom
    SEARCH_DECK_EVOLVED = "search_deck_evolved"  # Search for 1st matching a Debut you returned
    ARCHIVE_TOP_DECK = "archive_top_deck"        # Archive top card of main deck

    # ── Conditional wrapper ──
    CONDITIONAL = "conditional"   # Wraps another action behind a game-state condition

    # ── Attachable card effects (passive / triggered) ──
    STAT_MODIFIER = "stat_modifier"
    TRIGGERED_EFFECT = "triggered_effect"
    PASSIVE_ABILITY = "passive_ability"


# ─── Condition type enumeration ─────────────────────────────────────────────

class ConditionType(str, Enum):
    """Pre-conditions that must be met before a support card can be played."""
    HAND_SIZE_LTE = "hand_size_lte"         # Hand (excl. this card) ≤ N
    HAND_SIZE_GTE = "hand_size_gte"         # Hand (excl. this card) ≥ N
    LIFE_LTE = "life_lte"                   # Own life ≤ N
    LIFE_LT_OPPONENT = "life_lt_opponent"   # Own life < opponent's life
    PREV_TURN_OWN_DOWNED = "prev_turn_own_downed"
    PREV_TURN_DOWNED_AND_LIFE_LT = "prev_turn_downed_and_life_lt"
    ALL_STAGE_HAS_TAG = "all_stage_has_tag" # All own stage holomen have tag
    OSHI_IS = "oshi_is"                     # Oshi holomen is specific name
    OWN_COLLAB_EXISTS_OR_NO_OPP_COLLAB = "own_collab_or_no_opp_collab"
    TWO_DIFFERENT_COLORS_ON_STAGE = "two_different_colors_on_stage"
    STAGE_HAS_HOLOMEN = "stage_has_holomen" # Specific holomen on stage
    NO_OPPONENT_COLLAB = "no_opponent_collab"


# ─── Cost type enumeration ──────────────────────────────────────────────────

class CostType(str, Enum):
    """Costs that must be paid to play a support card."""
    ARCHIVE_STAGE_CHEER = "archive_stage_cheer"   # Archive N cheer from own stage
    ARCHIVE_HOLO_POWER = "archive_holo_power"     # Archive N holo power
    ARCHIVE_HAND_CARD = "archive_hand_card"        # Archive a hand card
    ARCHIVE_STAGE_TOOL = "archive_stage_tool"      # Archive a specific tool from stage
