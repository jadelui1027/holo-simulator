"""
hOCG Support Card Action Executor
===================================
Drives support card effects through a PlaymatManager instance.
Extracted from support_card_db.py for modularity.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .playmat_manager import PlaymatManager, Card, Zone

from .card_types import ActionType, ConditionType, CostType
from .card_data import SUPPORT_CARD_DB

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

class SupportCardExecutor:
    """
    Executes support card effects using a PlaymatManager.

    Usage::

        executor = SupportCardExecutor(pm)
        result = executor.play_support("hSD01-016")  # Draw 3

    For interactive use, the executor prompts the player to make choices
    (e.g., which cards to pick from a revealed set).  For AI / automated
    play, subclass and override the ``choose_*`` methods.
    """

    def __init__(self, pm: "PlaymatManager"):
        # Import Zone from the same module as the pm instance to avoid
        # separate-enum-class issues when this file is imported from
        # playmat_manager directly.
        import sys
        pm_mod = sys.modules.get(type(pm).__module__)
        if pm_mod and hasattr(pm_mod, "Zone"):
            self.Zone = pm_mod.Zone
        else:
            from playmat_manager import Zone
            self.Zone = Zone
        self.pm = pm
        self._limited_used_this_turn = False
        self._per_turn_trackers: dict[str, int] = {}  # card_name → usage count
        self._game_trackers: dict[str, int] = {}       # card_name → usage count (game)
        self._turn_modifiers: list[dict] = []          # Active this-turn stat modifiers
        self._prev_turn_own_downed = False

        # ── GUI callbacks (set by GUI to enable interactive picking) ──
        # pick_cards_cb(cards, min_pick, max_pick, title, message) -> list[Card]
        #   Show a popup with cards to choose from. Returns list of selected cards.
        self.pick_cards_cb = None
        # pick_holomen_cb(holomen_list, title, message) -> Card or None
        #   Show a popup with stage holomen to choose from. Returns selected card.
        self.pick_holomen_cb = None
        # order_cards_cb(cards, title, message) -> list[Card]
        #   Let user reorder cards (e.g., for deck bottom order). Returns ordered list.
        self.order_cards_cb = None
        self._current_playing_card = None  # Card object currently being played
        self._pick_extra = None  # Extra context for pick callbacks (used by game engine)
        self._last_picked_count = 0  # Track how many cards were picked in last search (for CONDITIONAL)
        self._pending_conditional = None  # Deferred conditional for capture mode

    # ── Turn lifecycle ──────────────────────────────────────────────

    def start_turn(self):
        """Call at the start of each turn to reset per-turn state."""
        self._limited_used_this_turn = False
        self._per_turn_trackers.clear()
        self._turn_modifiers.clear()

    def end_turn(self):
        """Call at end of turn.  Records downed state etc."""
        pass

    def record_own_downed(self, downed: bool):
        """Record whether own holomen was downed last opponent turn."""
        self._prev_turn_own_downed = downed

    # ── Public API ──────────────────────────────────────────────────

    def get_card_info(self, card_number: str) -> Optional[dict]:
        """Look up a support card's structured data."""
        return SUPPORT_CARD_DB.get(card_number)

    def can_play(self, card_number: str) -> tuple[bool, str]:
        """
        Check whether a support card can legally be played right now.
        Returns (can_play, reason).
        """
        entry = SUPPORT_CARD_DB.get(card_number)
        if not entry:
            return False, f"Card {card_number} not found in support database"

        if entry.get("attachment_type"):
            # Check there are eligible holomen on stage
            Zone = self.Zone
            att_type = entry.get("attachment_type")
            att_limit = entry.get("attachment_limit")
            att_target = entry.get("attachment_target")

            stage_holomen = []
            for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
                for card in self.pm.zones[z]:
                    stage_holomen.append(card)

            if att_target:
                targets = [att_target] if isinstance(att_target, str) else att_target
                stage_holomen = [
                    h for h in stage_holomen
                    if any(t in h.card_name for t in targets)
                ]

            if att_limit:
                stage_holomen = [
                    h for h in stage_holomen
                    if sum(1 for s in getattr(h, 'attached_supports', [])
                           if SUPPORT_CARD_DB.get(s.card_number, {}).get("attachment_type") == att_type
                           ) < att_limit
                ]

            if not stage_holomen:
                return False, "No eligible holomen to attach to"

            # Check costs for attachment cards that have them
            for cost in entry.get("costs", []):
                ok, reason = self._check_cost_payable(cost)
                if not ok:
                    return False, reason

            return True, "Attachable card"

        # LIMITED check
        if entry.get("is_limited") and self._limited_used_this_turn:
            return False, "Already used a LIMITED card this turn"

        # Per-turn limit by card name/tag
        ptl = entry.get("per_turn_limit")
        if ptl:
            key = ptl.get("card_name") or ptl.get("tag", "")
            limit = ptl.get("limit", 1)
            if self._per_turn_trackers.get(key, 0) >= limit:
                return False, f"Per-turn limit reached for {key}"

        # Check conditions
        for cond in entry.get("conditions", []):
            ok, reason = self._check_condition(cond)
            if not ok:
                return False, reason

        # Check costs (verify payable, don't pay yet)
        for cost in entry.get("costs", []):
            ok, reason = self._check_cost_payable(cost)
            if not ok:
                return False, reason

        return True, "OK"

    def play_support(self, card_number: str) -> dict:
        """
        Play a support card from hand.

        Returns a result dict with:
          - success: bool
          - message: str
          - actions_taken: list of descriptions of what happened
        """
        result = {"success": False, "message": "", "actions_taken": []}

        entry = SUPPORT_CARD_DB.get(card_number)
        if not entry:
            result["message"] = f"Card {card_number} not in support database"
            return result

        # Legality check
        ok, reason = self.can_play(card_number)
        if not ok:
            result["message"] = reason
            return result

        card_name = entry["card_name"]
        print(f"\n{'='*50}")
        print(f"▶ Playing support: {card_name} ({card_number})")
        print(f"  Type: {entry['card_type']}")
        print(f"{'='*50}")

        # Track the card being played (for cost exclusion)
        Zone = self.Zone
        self._current_playing_card = None
        for c in self.pm.zones[Zone.HAND]:
            if c.card_number == card_number:
                self._current_playing_card = c
                break

        # ── Handle attachable support cards (tool/mascot/fan) ──
        if entry.get("attachment_type"):
            return self._play_attachment(card_number, entry, result)

        # Pay costs
        for cost in entry.get("costs", []):
            desc = self._pay_cost(cost)
            result["actions_taken"].append(f"Cost: {desc}")

        # Remove card from hand → archive
        self._move_card_hand_to_archive(card_number)
        result["actions_taken"].append(f"Moved {card_name} from hand to archive")

        # Track LIMITED usage
        if entry.get("is_limited"):
            self._limited_used_this_turn = True

        # Track per-turn limits
        ptl = entry.get("per_turn_limit")
        if ptl:
            key = ptl.get("card_name") or ptl.get("tag", "")
            self._per_turn_trackers[key] = self._per_turn_trackers.get(key, 0) + 1

        # Execute actions in order
        for action in entry.get("actions", []):
            desc = self._execute_action(action)
            if desc:
                result["actions_taken"].append(desc)

        result["success"] = True
        result["message"] = f"Successfully played {card_name}"

        print(f"\n✓ {card_name} resolved.")
        print(f"  Actions: {len(result['actions_taken'])}")
        for i, a in enumerate(result['actions_taken'], 1):
            print(f"  {i}. {a}")

        return result

    def get_turn_modifiers(self) -> list[dict]:
        """Return active this-turn modifiers (arts boost, cost reduce, etc.)."""
        return list(self._turn_modifiers)

    def list_playable_supports(self) -> list[dict]:
        """List all support cards in hand that can be played right now."""
        Zone = self.Zone
        playable = []
        for card in self.pm.zones[Zone.HAND]:
            if "サポート" not in card.card_type:
                continue
            ok, reason = self.can_play(card.card_number)
            entry = SUPPORT_CARD_DB.get(card.card_number, {})
            playable.append({
                "card_number": card.card_number,
                "card_name": card.card_name,
                "card_type": card.card_type,
                "can_play": ok,
                "reason": reason,
                "is_limited": entry.get("is_limited", False),
                "summary": self._summarize_actions(entry),
            })
        return playable

    # ── Attachment play flow ────────────────────────────────────────

    def _play_attachment(self, card_number: str, entry: dict,
                         result: dict) -> dict:
        """Play an attachable support card (tool/mascot/fan) to a holomen."""
        Zone = self.Zone
        card_name = entry["card_name"]
        att_type = entry.get("attachment_type")
        att_limit = entry.get("attachment_limit")
        att_target = entry.get("attachment_target")

        # Collect eligible stage holomen
        stage_holomen = []
        for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
            for card in self.pm.zones[z]:
                stage_holomen.append(card)

        # Filter by attachment target restriction (fan cards)
        if att_target:
            targets = [att_target] if isinstance(att_target, str) else att_target
            stage_holomen = [
                h for h in stage_holomen
                if any(t in h.card_name for t in targets)
            ]

        # Check attachment limit (tool/mascot: 1 per holomen)
        if att_limit:
            stage_holomen = [
                h for h in stage_holomen
                if sum(1 for s in getattr(h, 'attached_supports', [])
                       if SUPPORT_CARD_DB.get(s.card_number, {}).get("attachment_type") == att_type
                       ) < att_limit
            ]

        if not stage_holomen:
            result["message"] = f"No eligible holomen to attach {card_name} to"
            return result

        # Pay costs (some tools have costs, e.g. hBP05-082)
        for cost in entry.get("costs", []):
            desc = self._pay_cost(cost)
            result["actions_taken"].append(f"Cost: {desc}")

        # Select target holomen
        target = None
        if len(stage_holomen) == 1:
            target = stage_holomen[0]
        elif self.pick_holomen_cb:
            self._pick_extra = {"mode": "attach_support",
                                "card_number": card_number}
            target = self.pick_holomen_cb(
                stage_holomen, f"Attach {card_name}",
                f"Select a holomen to attach {card_name} ({att_type}) to.")
            self._pick_extra = None

        if target:
            # Direct mode (tkinter): attach immediately
            hand = self.pm.zones[Zone.HAND]
            for c in hand:
                if c.card_number == card_number:
                    hand.remove(c)
                    c.face_up = True
                    if not hasattr(target, 'attached_supports'):
                        target.attached_supports = []
                    target.attached_supports.append(c)
                    result["actions_taken"].append(
                        f"Attached {card_name} to {target.card_name}")

                    # ── Fire on_attach triggered effects ──
                    self._fire_on_attach(entry, target, result)
                    break
        else:
            # Capture mode: card stays in hand, pending pick for target selection
            result["actions_taken"].append(
                f"Attach {card_name} (pending target selection)")
            # Store entry ref for on_attach firing after pick resolution
            result["_pending_attach_entry"] = entry

        result["success"] = True
        result["message"] = f"Successfully played {card_name}"
        return result

    # ── Support card passive effect helpers ─────────────────────────

    def _fire_on_attach(self, entry: dict, target, result: dict):
        """Fire on_attach triggered effects after attaching a support card."""
        Zone = self.Zone
        triggered = entry.get("triggered_effects", [])
        cond_holder = entry.get("conditional_holder") if isinstance(entry.get("conditional_holder"), dict) else None
        # For entries using the _mascot helper, triggered_effects are nested differently
        for te in triggered:
            # Check if it's a conditional_effect wrapper
            effects_list = te.get("effects", [te])
            holder = te.get("condition", cond_holder)

            for eff in effects_list:
                if eff.get("trigger") != "on_attach":
                    continue

                # Check conditional holder matches the target holomen
                if holder:
                    holder_name = holder.get("holomen", "")
                    if holder_name and holder_name not in target.card_name:
                        continue
                    bloom_gte = holder.get("bloom_gte")
                    if bloom_gte:
                        level_order = {"Debut": 0, "1st": 1, "2nd": 2, "Spot": 1, "Buzz": 1}
                        tgt_lvl = level_order.get(getattr(target, 'bloom_level', 'Debut'), 0)
                        req_lvl = level_order.get(bloom_gte, 0)
                        if tgt_lvl < req_lvl:
                            continue

                effect_name = eff.get("effect", "")
                if effect_name == "archive_stage_yell_then_search_yell_deck_to_holomen":
                    self._on_attach_archive_yell_search_yell(target, result)

    def _on_attach_archive_yell_search_yell(self, target, result: dict):
        """On-attach effect: optionally archive 1 stage yell, then search yell deck to holomen.
        In capture mode (web), all 3 picks are generated upfront. The resolver handles
        the actual card movement and skipping remaining picks if user declines."""
        Zone = self.Zone

        # Step 1: Collect all yells from stage holomen
        stage_yells = []
        for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
            for holomen in self.pm.zones[z]:
                for yell in getattr(holomen, 'attached_yells', []):
                    stage_yells.append(yell)

        if not stage_yells:
            result["actions_taken"].append("No stage yells to archive (on_attach skipped)")
            return

        # Step 2: Ask player to pick a yell to archive (optional, min=0)
        capture_mode = False
        archived_yell = None
        if self.pick_cards_cb:
            for y in stage_yells:
                y.face_up = True
            self._pick_extra = {"mode": "select_cheer"}
            picked = self.pick_cards_cb(
                stage_yells, 0, 1,
                "Archive Stage Yell (on attach)",
                "You may archive 1 yell from your stage holomen to trigger the search effect.")
            self._pick_extra = None
            if picked is None:
                capture_mode = True  # Web mode — continue to generate remaining picks
            elif picked and len(picked) > 0:
                archived_yell = picked[0]
            else:
                # User explicitly chose not to archive (non-capture mode)
                result["actions_taken"].append("On-attach: chose not to archive a yell")
                return
        else:
            # Auto: pick first yell
            archived_yell = stage_yells[0]

        # Archive the selected yell (non-capture mode only)
        if not capture_mode:
            if archived_yell is None:
                result["actions_taken"].append("On-attach: chose not to archive a yell")
                return
            for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
                for holomen in self.pm.zones[z]:
                    if archived_yell in holomen.attached_yells:
                        holomen.attached_yells.remove(archived_yell)
                        archived_yell.face_up = True
                        self.pm.zones[Zone.ARCHIVE].append(archived_yell)
                        result["actions_taken"].append(
                            f"Archived yell {archived_yell.card_name} from {holomen.card_name}")
                        break

        # Step 3: Search yell deck for 1 yell
        yell_deck = self.pm.zones[Zone.YELL_DECK]
        if not yell_deck and not capture_mode:
            result["actions_taken"].append("Yell deck empty, cannot search")
            return

        picked_yell = None
        if self.pick_cards_cb and (yell_deck or capture_mode):
            if yell_deck:
                for y in yell_deck:
                    y.face_up = True
            picked = self.pick_cards_cb(
                list(yell_deck), 0, 1,
                "Search Yell Deck → Holomen (on attach)",
                "Select 1 yell to send to a stage holomen.")
            if picked is None:
                pass  # capture mode — pick captured
            elif picked and len(picked) > 0:
                picked_yell = picked[0]
            else:
                # Non-capture: user skipped
                for y in yell_deck:
                    y.face_up = False
                result["actions_taken"].append("On-attach: no yell selected from yell deck")
                return
        elif not capture_mode:
            picked_yell = yell_deck[0] if yell_deck else None

        # Handle yell deck operations (non-capture mode only)
        if not capture_mode:
            if picked_yell is None:
                result["actions_taken"].append("On-attach: no yell selected from yell deck")
                for y in yell_deck:
                    y.face_up = False
                return
            if picked_yell in yell_deck:
                yell_deck.remove(picked_yell)
            picked_yell.face_up = True
            for y in yell_deck:
                y.face_up = False
            self.pm.shuffle_yell_deck()

        # Step 4: Ask player to select a stage holomen to receive the yell
        all_stage = []
        for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
            for h in self.pm.zones[z]:
                all_stage.append(h)

        if not all_stage and not capture_mode:
            if picked_yell:
                self.pm.zones[Zone.ARCHIVE].append(picked_yell)
            result["actions_taken"].append("No stage holomen to receive yell")
            return

        recv_target = None
        if not capture_mode and len(all_stage) == 1:
            recv_target = all_stage[0]
        elif self.pick_holomen_cb and all_stage:
            self._pick_extra = {"mode": "holomen"}
            recv_target = self.pick_holomen_cb(
                all_stage, "Send Yell to Holomen (on attach)",
                f"Select a holomen to receive yell.")
            self._pick_extra = None

        if not capture_mode:
            if recv_target:
                recv_target.attached_yells.append(picked_yell)
                result["actions_taken"].append(
                    f"Sent {picked_yell.card_name} to {recv_target.card_name}")
            else:
                result["actions_taken"].append("Send yell to holomen (pending)")

    def get_effective_hp(self, card) -> int:
        """Get a holomen's HP including bonuses from attached supports."""
        base_hp = getattr(card, 'hp', 0)
        bonus = 0
        for sup in getattr(card, 'attached_supports', []):
            entry = SUPPORT_CARD_DB.get(sup.card_number, {})
            for eff in entry.get("passive_effects", []):
                if eff.get("type") == "hp_modifier":
                    bonus += eff.get("amount", 0)
        return base_hp + bonus

    def get_arts_modifier(self, card) -> int:
        """Get total arts damage modifier from attached supports."""
        bonus = 0
        for sup in getattr(card, 'attached_supports', []):
            entry = SUPPORT_CARD_DB.get(sup.card_number, {})
            for eff in entry.get("passive_effects", []):
                if eff.get("type") == "arts_modifier":
                    bonus += eff.get("amount", 0)
        return bonus

    # ── Condition checking ──────────────────────────────────────────

    def _check_condition(self, cond: dict) -> tuple[bool, str]:
        """Check a single condition. Returns (ok, reason)."""
        Zone = self.Zone
        ctype = cond.get("type", "")

        if ctype == ConditionType.HAND_SIZE_LTE:
            # Hand size (excluding the card being played) must be ≤ count
            hand_count = len(self.pm.zones[Zone.HAND]) - 1
            limit = cond["count"]
            if hand_count > limit:
                return False, f"Hand size {hand_count} exceeds limit of {limit}"
            return True, ""

        if ctype == ConditionType.HAND_SIZE_GTE:
            hand_count = len(self.pm.zones[Zone.HAND]) - 1
            limit = cond["count"]
            if hand_count < limit:
                return False, f"Hand size {hand_count} below minimum of {limit}"
            return True, ""

        if ctype == ConditionType.LIFE_LTE:
            life = len(self.pm.zones[Zone.LIFE])
            if life > cond["count"]:
                return False, f"Life {life} exceeds limit of {cond['count']}"
            return True, ""

        if ctype == ConditionType.LIFE_LT_OPPONENT:
            return True, ""  # TODO: needs opponent state

        if ctype == ConditionType.PREV_TURN_DOWNED_AND_LIFE_LT:
            if not self._prev_turn_own_downed:
                return False, "No holomen downed last opponent turn"
            return True, ""

        if ctype == ConditionType.ALL_STAGE_HAS_TAG:
            # Check all stage holomen have the required tag
            return True, ""  # TODO: needs tag lookup in card data

        if ctype == ConditionType.OSHI_IS:
            oshi = self.pm.zones[Zone.OSHI]
            if not oshi or oshi[0].card_name != cond["name"]:
                return False, f"Oshi is not {cond['name']}"
            return True, ""

        if ctype == ConditionType.TWO_DIFFERENT_COLORS_ON_STAGE:
            return True, ""  # TODO: needs color check

        if ctype == ConditionType.OWN_COLLAB_EXISTS_OR_NO_OPP_COLLAB:
            own_collab = len(self.pm.zones[Zone.COLLABO]) > 0
            return own_collab, "No own collab holomen" if not own_collab else ""

        if ctype == ConditionType.NO_OPPONENT_COLLAB:
            return True, ""  # TODO: needs opponent state

        return True, ""  # Unknown condition – allow by default

    # ── Cost handling ───────────────────────────────────────────────

    def _check_cost_payable(self, cost: dict) -> tuple[bool, str]:
        """Check if a cost can be paid."""
        Zone = self.Zone
        ctype = cost.get("type", "")

        if ctype == CostType.ARCHIVE_HOLO_POWER:
            count = cost.get("count", 1)
            if len(self.pm.zones[Zone.HOLO_POWER]) < count:
                return False, f"Not enough Holo Power ({len(self.pm.zones[Zone.HOLO_POWER])} < {count})"
            return True, ""

        if ctype == CostType.ARCHIVE_STAGE_CHEER:
            count = cost.get("count", 1)
            total_yells = 0
            for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
                for holomen in self.pm.zones[z]:
                    total_yells += len(holomen.attached_yells)
            if total_yells < count:
                return False, f"Not enough yells on stage ({total_yells} < {count})"
            return True, ""

        if ctype == CostType.ARCHIVE_HAND_CARD:
            count = cost.get("count", 1)
            if len(self.pm.zones[Zone.HAND]) < count + 1:  # +1 for the support card itself
                return False, "Not enough cards in hand to pay cost"
            return True, ""

        return True, ""

    def _pay_cost(self, cost: dict) -> str:
        """Pay a cost. Returns description."""
        Zone = self.Zone
        ctype = cost.get("type", "")

        if ctype == CostType.ARCHIVE_HOLO_POWER:
            count = cost.get("count", 1)
            for _ in range(count):
                card = self.pm.remove_card(Zone.HOLO_POWER)
                if card:
                    self.pm.place_card(Zone.ARCHIVE, card, face_up=True)
            return f"Archived {count} Holo Power"

        if ctype == CostType.ARCHIVE_STAGE_CHEER:
            count = cost.get("count", 1)
            # Collect all yells from stage holomen
            Zone = self.Zone
            all_yells = []
            for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
                for holomen in self.pm.zones[z]:
                    for yell in holomen.attached_yells:
                        all_yells.append(yell)

            if not all_yells:
                return f"No cheer on stage to archive"

            if self.pick_cards_cb:
                for y in all_yells:
                    y.face_up = True
                self._pick_extra = {"mode": "select_cheer"}
                selected = self.pick_cards_cb(
                    all_yells, count, count,
                    f"Cost: Archive {count} cheer from stage",
                    f"Select {count} cheer card(s) to archive from your stage holomen.")
                self._pick_extra = None

                if selected:
                    # Direct mode (tkinter) - actually archive
                    for yell in selected:
                        for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
                            for holomen in self.pm.zones[z]:
                                if yell in holomen.attached_yells:
                                    holomen.attached_yells.remove(yell)
                                    yell.face_up = True
                                    self.pm.zones[Zone.ARCHIVE].append(yell)
                                    break
                    return f"Archived {count} stage cheer"
                else:
                    # Capture mode - will be resolved later
                    return f"Archive {count} stage cheer (pending)"
            else:
                print(f"  💫 Cost: Archive {count} cheer from stage holomen")
                return f"Archive {count} stage cheer (player choice)"

        if ctype == CostType.ARCHIVE_HAND_CARD:
            count = cost.get("count", 1)
            if self.pick_cards_cb:
                Zone = self.Zone
                hand = [c for c in self.pm.zones[Zone.HAND]
                        if "サポート" not in c.card_type
                            or c != self._current_playing_card]
                picked = self.pick_cards_cb(
                    hand, count, count,
                    f"Cost: Archive {count} hand card(s)",
                    f"Choose {count} card(s) from hand to archive as cost.")
                if picked:
                    for card in picked:
                        if card in self.pm.zones[Zone.HAND]:
                            self.pm.zones[Zone.HAND].remove(card)
                            card.face_up = True
                            self.pm.zones[Zone.ARCHIVE].append(card)
                    return f"Archived {len(picked)} hand card(s) as cost"
            print(f"  💫 Cost: Archive {count} card(s) from hand")
            return f"Archive {count} hand card(s) (player choice)"

        return f"Paid cost: {ctype}"

    # ── Action execution ────────────────────────────────────────────

    def _execute_action(self, action: dict) -> str:
        """Execute a single action. Returns description string."""
        atype = action.get("type", "")

        if atype == ActionType.DRAW:
            count = action.get("count", 1)
            drawn = self.pm.draw_card(count)
            names = ", ".join(c.card_name for c in drawn)
            return f"Drew {len(drawn)} card(s): {names}"

        if atype == ActionType.SHUFFLE_HAND_DRAW:
            return self._exec_shuffle_hand_draw(action)

        if atype == ActionType.VIEW_DECK_TOP:
            return self._exec_view_deck_top(action)

        if atype == ActionType.SEARCH_DECK:
            return self._exec_search_deck(action)

        if atype == ActionType.SEARCH_DECK_TO_STAGE:
            return self._exec_search_deck_to_stage(action)

        if atype == ActionType.SEARCH_YELL_DECK:
            return self._exec_search_yell_deck(action)

        if atype == ActionType.SEARCH_ARCHIVE:
            return self._exec_search_archive(action)

        if atype == ActionType.SWAP_OPPONENT_CENTER_BACK:
            print("  ⚔ Swap opponent's center holomen with one of their back holomen")
            return "Opponent swaps center ↔ back (opponent chooses which back)"

        if atype == ActionType.SWAP_OWN_CENTER_BACK:
            return self._exec_swap_own_center_back(action)

        if atype == ActionType.MOVE_CHEER:
            return self._exec_move_cheer(action)

        if atype == ActionType.ARCHIVE_TO_YELL_DECK:
            return self._exec_archive_to_yell_deck(action)

        if atype == ActionType.ARCHIVE_CHEER_TO_HOLOMEN:
            return self._exec_archive_cheer_to_holomen(action)

        if atype == ActionType.DEAL_SPECIAL_DAMAGE:
            target = action.get("target", "?")
            amount = action.get("amount", 0)
            no_life = action.get("no_life_on_down", False)
            nlife = " (no life loss on down)" if no_life else ""
            print(f"  💥 Deal {amount} special damage to {target}{nlife}")
            return f"Special damage {amount} → {target}{nlife}"

        if atype == ActionType.HEAL:
            target = action.get("target", "selected_holomen")
            amount = action.get("amount", 0)
            print(f"  💚 Heal {amount} HP for {target}")
            return f"Heal {amount} HP → {target}"

        if atype == ActionType.ARTS_BOOST:
            target = action.get("target", action.get("target_holomen", "selected"))
            amount = action.get("amount", 0)
            alt = action.get("amount_if_buzz_or_2nd")
            per_ret = action.get("amount_per_returned")
            desc = f"Arts +{amount} this turn → {target}"
            if alt:
                desc += f" (or +{alt} if Buzz/2nd)"
            if per_ret:
                desc += f" (+{per_ret} per card returned)"
            self._turn_modifiers.append({
                "type": "arts_boost", "target": target,
                "amount": amount, "alt_amount": alt})
            print(f"  ⚡ {desc}")
            return desc

        if atype == ActionType.BATON_TOUCH_COST_REDUCE:
            target = action.get("target", "selected")
            reduce = action.get("reduce", 0)
            self._turn_modifiers.append({
                "type": "baton_touch_reduce", "target": target, "amount": reduce})
            print(f"  ⬇ Baton touch cost -{reduce} for {target} this turn")
            return f"Baton touch cost -{reduce} → {target}"

        if atype == ActionType.ARTS_COST_REDUCE:
            target = action.get("target_holomen", "?")
            reduce = action.get("colorless_reduce", 0)
            self._turn_modifiers.append({
                "type": "arts_cost_reduce", "target": target, "amount": reduce})
            print(f"  ⬇ Arts colorless cost -{reduce} for {target} this turn")
            return f"Arts colorless cost -{reduce} → {target}"

        if atype == ActionType.ROLL_DICE:
            return self._exec_roll_dice(action)

        if atype == ActionType.CONDITIONAL:
            return self._exec_conditional(action)

        if atype == ActionType.OPPONENT_MOVE_BACK_TO_COLLAB:
            print("  ⚔ Opponent must move a back holomen to collab position")
            return "Opponent moves back → collab"

        if atype == ActionType.OPPONENT_REST_TO_BACK:
            target = action.get("target", "?")
            skip = action.get("skip_next_reset", False)
            msg = f"Rest opponent's {target} and move to back"
            if skip:
                msg += " (skips next reset step)"
            print(f"  ⚔ {msg}")
            return msg

        if atype == ActionType.SEND_ARCHIVE_CHEER_SPLIT:
            total = action.get("total", 0)
            targets = action.get("targets", [])
            max_per = action.get("max_per_target", 0)
            print(f"  💫 Send {total} archive cheers split to {targets} (max {max_per} each)")
            return f"Split {total} archive cheers to {', '.join(targets)} (max {max_per} each)"

        if atype == ActionType.RETURN_STACKED_TO_HAND:
            count = action.get("count", {})
            print(f"  🔄 Return {count} stacked holomen to hand")
            return f"Return {count} stacked cards to hand"

        if atype == ActionType.HAND_CARD_TO_DECK_BOTTOM:
            return self._exec_hand_card_to_deck_bottom(action)

        if atype == ActionType.EXTRA_BLOOM:
            desc = action.get("description", "Extra bloom opportunity")
            print(f"  🌸 {desc}")
            return desc

        if atype == ActionType.YELL_DECK_TOP_TO_HOLOMEN:
            count = action.get("count", 1)
            print(f"  💫 Send top {count} yell deck card to holomen")
            return f"Yell deck top → holomen"

        if atype == ActionType.ARCHIVE_YELL_DECK_TOP:
            count = action.get("count", 1)
            Zone = self.Zone
            for _ in range(count):
                if self.pm.zones[Zone.YELL_DECK]:
                    card = self.pm.zones[Zone.YELL_DECK].pop()
                    card.face_up = True
                    self.pm.zones[Zone.ARCHIVE].append(card)
            return f"Archived top {count} yell deck card(s)"

        return f"Action: {atype} (manual resolution needed)"

    # ── Action implementations ──────────────────────────────────────

    def _exec_hand_card_to_deck_bottom(self, action: dict) -> str:
        """Pick card(s) from hand and put them to deck bottom."""
        Zone = self.Zone
        filt = action.get("filter", {})
        count = action.get("count", 1)
        desc = action.get("description", "")

        hand = self.pm.zones[Zone.HAND]
        if not hand:
            print("  ℹ No cards in hand to put to deck bottom")
            return "No hand cards available"

        # Filter hand cards
        if filt.get("any"):
            selectable = list(hand)
        else:
            selectable = [c for c in hand if self._card_matches_filter(c, filt)]

        if not selectable:
            print("  ℹ No matching cards in hand")
            return "No matching hand cards"

        # Let the player pick
        picked = None
        if self.pick_cards_cb:
            for c in selectable:
                c.face_up = True
            self._pick_extra = None
            picked = self.pick_cards_cb(
                selectable, count, count,
                f"Hand → Deck Bottom (pick {count})",
                desc or f"Select {count} card(s) from hand to put to deck bottom.")

            if picked is None:
                # Capture mode — will be resolved later
                return f"(pending) Hand card → deck bottom"

            # Validate picked cards are in selectable
            selectable_nums = {c.card_number for c in selectable}
            picked = [c for c in picked if c.card_number in selectable_nums]

        else:
            picked = selectable[:count]

        # Move picked cards to deck bottom
        names = []
        for card in picked:
            if card in hand:
                hand.remove(card)
            card.face_up = False
            self.pm.zones[Zone.DECK].insert(0, card)
            names.append(card.card_name)

        print(f"  📥 Put {len(picked)} card(s) to deck bottom: {', '.join(names)}")
        return f"Hand → deck bottom: {', '.join(names)}"

    def _exec_shuffle_hand_draw(self, action: dict) -> str:
        Zone = self.Zone
        draw_count = action.get("draw_count", 5)
        # Return all hand cards to deck
        hand_cards = self.pm.zones[Zone.HAND][:]
        for card in hand_cards:
            card.face_up = False
            self.pm.zones[Zone.DECK].append(card)
        self.pm.zones[Zone.HAND].clear()
        print(f"  🔄 Returned {len(hand_cards)} hand card(s) to deck")
        # Shuffle
        self.pm.shuffle_deck()
        # Draw
        drawn = self.pm.draw_card(draw_count)
        names = ", ".join(c.card_name for c in drawn)
        return f"Shuffled hand ({len(hand_cards)} cards) back, drew {draw_count}: {names}"

    def _exec_view_deck_top(self, action: dict) -> str:
        Zone = self.Zone
        count = action.get("count", 4)
        filt = action.get("filter", {})
        pick_count = action.get("pick_count", "any")
        rest_to = action.get("rest_to", "deck_bottom")

        # Reveal top N cards
        deck = self.pm.zones[Zone.DECK]
        revealed = []
        for _ in range(min(count, len(deck))):
            revealed.append(deck.pop())

        if not revealed:
            return "Deck empty – nothing to reveal"

        # Classify revealed cards
        print(f"\n  👁 Revealed top {len(revealed)} cards:")
        matching = []
        non_matching = []
        for i, card in enumerate(revealed):
            card.face_up = True
            is_match = self._card_matches_filter(card, filt)
            marker = "✓" if is_match else "✗"
            print(f"    [{i+1}] {marker} {card.card_name} ({card.card_number}) [{card.card_type}]")
            if is_match:
                matching.append(card)
            else:
                non_matching.append(card)

        # Determine max picks
        max_picks = len(matching)
        min_picks = 0
        if pick_count == "any":
            max_picks = len(matching)
        elif isinstance(pick_count, int):
            max_picks = min(pick_count, len(matching))
        elif isinstance(pick_count, dict) and "per_type" in pick_count:
            max_picks = len(matching)

        # Pick cards – show ALL revealed, mark which are selectable
        picked = []
        all_revealed = matching + non_matching
        if self.pick_cards_cb:
            # Set extra context so game engine capture knows selectable cards
            self._pick_extra = {
                "selectable_numbers": [c.card_number for c in matching],
                "rest_to": rest_to,
            }
            picked = self.pick_cards_cb(
                all_revealed, min_picks, max_picks,
                f"Select cards to add to hand (max {max_picks})",
                f"Revealed {len(revealed)} cards from deck top. "
                f"{len(matching)} match the filter. Pick up to {max_picks}.")
            self._pick_extra = None
            if picked is None:
                picked = []
        else:
            # Auto-pick for CLI / test mode
            if pick_count == "any":
                picked = matching[:]
                print(f"  → Auto-selecting all {len(picked)} matching card(s)")
            elif isinstance(pick_count, int):
                picked = matching[:pick_count]
            else:
                picked = matching[:]

        # Add picked to hand
        for card in picked:
            card.face_up = True
            self.pm.zones[Zone.HAND].append(card)

        # Put rest to deck – let player choose order if callback available
        rest = [c for c in all_revealed if c not in picked]
        if rest and self.order_cards_cb:
            ordered = self.order_cards_cb(
                rest, f"Order cards for {rest_to.replace('_',' ')}",
                "Drag to reorder. Top of list = first card placed.")
            if ordered:
                rest = ordered
        elif rest:
            random.shuffle(rest)

        for card in rest:
            card.face_up = False
            if rest_to == "deck_top":
                self.pm.zones[Zone.DECK].append(card)
            else:
                self.pm.zones[Zone.DECK].insert(0, card)  # Bottom of deck

        picked_names = ", ".join(c.card_name for c in picked)
        return f"Viewed top {len(revealed)}: picked {len(picked)} ({picked_names}), {len(rest)} to {rest_to.replace('_',' ')}"

    def _exec_search_deck(self, action: dict) -> str:
        Zone = self.Zone
        filt = action.get("filter", {})
        pick_count = action.get("pick_count", 1)
        shuffle = action.get("shuffle_after", True)

        deck = self.pm.zones[Zone.DECK]
        matching = [c for c in deck if self._card_matches_filter(c, filt)]

        limit = pick_count if isinstance(pick_count, int) else 1

        # Show ALL deck cards (player can check deck contents)
        # but only matching cards are selectable
        if self.pick_cards_cb:
            all_deck = list(deck)
            for c in all_deck:
                c.face_up = True
            selectable = [c.card_number for c in matching]
            self._pick_extra = {
                "selectable_numbers": selectable,
                "all_cards": all_deck,
            }
            picked = self.pick_cards_cb(
                all_deck, 0, limit,
                f"Search Deck → Hand (pick up to {limit})",
                f"{len(deck)} cards in deck. {len(matching)} match the filter. "
                f"Pick up to {limit} from matching cards.")
            self._pick_extra = None
            if picked is None:
                picked = []
            else:
                # Validate: only matching cards can be selected
                picked = [c for c in picked if c.card_number in selectable]
        else:
            picked = matching[:limit]

        for card in picked:
            if card in deck:
                deck.remove(card)
            card.face_up = True
            self.pm.zones[Zone.HAND].append(card)

        if shuffle:
            self.pm.shuffle_deck()

        # Restore face_down for remaining deck cards
        for c in deck:
            c.face_up = False

        names = ", ".join(c.card_name for c in picked)
        print(f"  🔍 Found and added to hand: {names}")
        return f"Searched deck: added {names} to hand"

    def _exec_search_deck_to_stage(self, action: dict) -> str:
        Zone = self.Zone
        filt = action.get("filter", {})
        pick_count = action.get("pick_count", 1)
        shuffle = action.get("shuffle_after", True)

        deck = self.pm.zones[Zone.DECK]
        matching = [c for c in deck if self._card_matches_filter(c, filt)]

        max_pick = pick_count if isinstance(pick_count, int) else pick_count.get("max", 1)
        min_pick = 0 if isinstance(pick_count, int) else pick_count.get("min", 0)

        # Show ALL deck cards, only matching are selectable
        if self.pick_cards_cb:
            all_deck = list(deck)
            for c in all_deck:
                c.face_up = True
            selectable = [c.card_number for c in matching]
            self._pick_extra = {
                "selectable_numbers": selectable,
                "all_cards": all_deck,
            }
            picked = self.pick_cards_cb(
                all_deck, min_pick, max_pick,
                f"Search Deck → Stage (pick {min_pick}~{max_pick})",
                f"{len(deck)} cards in deck. {len(matching)} match the filter. "
                f"Choose {min_pick}~{max_pick} to place on Back stage.")
            self._pick_extra = None
            if picked is None:
                picked = []
            else:
                picked = [c for c in picked if c.card_number in selectable]
        else:
            picked = matching[:max_pick]

        # Track how many cards were actually picked (for CONDITIONAL checks)
        self._last_picked_count = len(picked)

        for card in picked:
            if card in deck:
                deck.remove(card)
            card.face_up = True
            card.debut_this_turn = True
            self.pm.place_card(Zone.BACK, card, face_up=True)

        if shuffle:
            self.pm.shuffle_deck()

        # Restore face_down for remaining deck cards
        for c in deck:
            c.face_up = False

        names = ", ".join(c.card_name for c in picked)
        return f"Searched deck → stage: {names}"

    def _exec_search_yell_deck(self, action: dict) -> str:
        Zone = self.Zone
        shuffle = action.get("shuffle_after", True)
        pick_count = action.get("pick_count", 1)
        yell_deck = self.pm.zones[Zone.YELL_DECK]

        if not yell_deck:
            return "Yell deck empty"

        # Let player choose from yell deck – use GUI callback if available
        if self.pick_cards_cb:
            for c in yell_deck:
                c.face_up = True
            picked = self.pick_cards_cb(
                list(yell_deck), 0, pick_count,
                f"Search Yell Deck (pick up to {pick_count})",
                f"{len(yell_deck)} cards in yell deck. Choose up to {pick_count} to send to holomen.")
            if picked is None:
                picked = []
        else:
            picked = yell_deck[:pick_count]

        for card in picked:
            if card in yell_deck:
                yell_deck.remove(card)
            card.face_up = True

        if shuffle:
            self.pm.shuffle_yell_deck()

        names = ", ".join(c.card_name for c in picked)
        print(f"  💫 Searched yell deck: {names} → send to holomen (player choice)")
        return f"Yell deck search: {names} → holomen"

    def _exec_search_archive(self, action: dict) -> str:
        Zone = self.Zone
        filt = action.get("filter", {})
        pick_count = action.get("pick_count", 1)
        to = action.get("to", "hand")

        archive = self.pm.zones[Zone.ARCHIVE]
        matching = [c for c in archive if self._card_matches_filter(c, filt)]

        if not matching:
            return "No matching cards in archive"

        # Let player choose which card(s) – use GUI callback if available
        if self.pick_cards_cb:
            picked = self.pick_cards_cb(
                matching, 0, pick_count,
                f"Search Archive → {to.title()} (pick up to {pick_count})",
                f"{len(matching)} matching cards in archive. Choose up to {pick_count}.")
            if picked is None:
                picked = []
        else:
            picked = matching[:pick_count]

        for card in picked:
            archive.remove(card)
            card.face_up = True
            if to == "hand":
                self.pm.zones[Zone.HAND].append(card)

        names = ", ".join(c.card_name for c in picked)
        return f"Archive → hand: {names}"

    def _exec_swap_own_center_back(self, action: dict) -> str:
        Zone = self.Zone
        center = self.pm.zones[Zone.CENTRE]
        back = self.pm.zones[Zone.BACK]

        if not center:
            return "No center holomen to swap"

        # Find non-resting back holomen
        condition = action.get("back_condition", "")
        eligible = [c for c in back if not c.resting] if condition == "not_resting" else back[:]

        if not eligible:
            return "No eligible back holomen to swap with"

        # Let player choose which back holomen to swap with
        if self.pick_holomen_cb and len(eligible) > 1:
            swap_target = self.pick_holomen_cb(
                eligible, "Swap Center ↔ Back",
                f"Choose a back holomen to swap with {center[0].card_name}")
            if swap_target is None:
                swap_target = eligible[0]
        else:
            swap_target = eligible[0]
        idx = back.index(swap_target)
        center_card = center[0]

        # Swap
        center[0] = swap_target
        back[idx] = center_card

        print(f"  🔄 Swapped center {center_card.card_name} ↔ back {swap_target.card_name}")
        return f"Swapped center ({center_card.card_name}) ↔ back ({swap_target.card_name})"

    def _exec_move_cheer(self, action: dict) -> str:
        count = action.get("count", 1)
        if isinstance(count, dict):
            count = count.get("max", 1)
        target = action.get("target_holomen", action.get("to", "any holomen"))
        print(f"  💫 Move {count} cheer to {target} (player choice)")
        return f"Move {count} cheer → {target}"

    def _exec_archive_to_yell_deck(self, action: dict) -> str:
        Zone = self.Zone
        count = action.get("count", {"min": 1, "max": 1})
        shuffle = action.get("shuffle_after", True)

        if isinstance(count, dict):
            max_count = count.get("max", 1)
        else:
            max_count = count

        archive = self.pm.zones[Zone.ARCHIVE]
        # Find cheer cards in archive
        moved = 0
        to_move = []
        for card in archive:
            if "エール" in card.card_type or card.card_type == "":
                to_move.append(card)
                if len(to_move) >= max_count:
                    break

        for card in to_move:
            archive.remove(card)
            card.face_up = False
            self.pm.zones[Zone.YELL_DECK].append(card)
            moved += 1

        if shuffle and moved > 0:
            self.pm.shuffle_yell_deck()

        return f"Moved {moved} cheer from archive to yell deck"

    def _exec_archive_cheer_to_holomen(self, action: dict) -> str:
        source = action.get("source", "archive")
        count = action.get("count", 1)
        target = action.get("target_holomen", "any")
        color = action.get("color", "any")
        desc = f"Send {count} {color} cheer from {source} to {target} (player choice)"
        print(f"  💫 {desc}")
        return desc

    def _exec_roll_dice(self, action: dict) -> str:
        Zone = self.Zone
        outcomes = action.get("outcomes", {})
        roll = random.randint(1, 6)
        print(f"  🎲 Rolled: {roll}")

        result_actions = []
        for condition_str, effect_actions in outcomes.items():
            if self._dice_condition_met(roll, condition_str):
                print(f"    → Condition '{condition_str}' met!")
                for sub_action in effect_actions:
                    desc = self._execute_action(sub_action)
                    result_actions.append(desc)
                break
        else:
            print(f"    → No matching outcome for roll {roll}")

        return f"Dice roll: {roll} → {'; '.join(result_actions) if result_actions else 'no effect'}"

    def _exec_conditional(self, action: dict) -> str:
        cond = action.get("condition", {})
        then_actions = action.get("then", [])

        # Evaluate condition (simplified)
        met = True
        cond_desc = ""

        if "life_lte" in cond:
            Zone = self.Zone
            life = len(self.pm.zones[Zone.LIFE])
            met = life <= cond["life_lte"]
            cond_desc = f"life ≤ {cond['life_lte']} (actual: {life})"

        if "prev_turn_own_downed" in cond:
            met = met and self._prev_turn_own_downed
            cond_desc += " and own holomen downed last turn"

        if "life_lt_opponent" in cond:
            cond_desc += " and life < opponent"
            # Can't verify without opponent state, assume true

        if "target_cheer_gte" in cond:
            cond_desc += f" and target has ≥{cond['target_cheer_gte']} cheer"

        if "picked_count_eq" in cond:
            # In capture mode, _last_picked_count is 0 because the pick hasn't resolved yet.
            # Detect capture mode and defer the condition evaluation to the resolver.
            if self._last_picked_count == 0 and self.pick_cards_cb is not None:
                # Capture mode: always execute then-actions, but tag picks as conditional
                self._pending_conditional = {"picked_count_eq": cond["picked_count_eq"]}
                cond_desc += f" and picked {cond['picked_count_eq']} cards (deferred to resolver)"
            else:
                met = met and (self._last_picked_count == cond["picked_count_eq"])
                cond_desc += f" and picked {cond['picked_count_eq']} cards (actual: {self._last_picked_count})"

        if "own_cheer_lt_opponent" in cond:
            cond_desc += " and own cheer < opponent"

        if "yell_deck_empty" in cond:
            Zone = self.Zone
            met = met and len(self.pm.zones[Zone.YELL_DECK]) == 0
            cond_desc += " and yell deck empty"

        if "stage_has_tag" in cond:
            cond_desc += f" and stage has {cond['stage_has_tag']}"

        if met:
            results = []
            for sub in then_actions:
                desc = self._execute_action(sub)
                results.append(desc)
            return f"Condition ({cond_desc}): met → {'; '.join(results)}"
        else:
            print(f"  ℹ Condition not met: {cond_desc}")
            return f"Condition ({cond_desc}): not met"

    # ── Filter matching ─────────────────────────────────────────────

    def _card_matches_filter(self, card: "Card", filt: dict) -> bool:
        """Check if a card matches a filter specification."""
        if not filt:
            return True

        # bloom_level filter
        bl = filt.get("bloom_level")
        if bl:
            if isinstance(bl, str):
                if card.bloom_level != bl:
                    return False
            elif isinstance(bl, list):
                if card.bloom_level not in bl:
                    return False

        # card_category filter (ホロメン, サポート, etc.)
        cat = filt.get("card_category")
        if cat:
            if cat == "ホロメン":
                holomen_types = ["推しホロメン", "Debutホロメン", "1stホロメン",
                                 "2ndホロメン", "Spotホロメン", "Buzzホロメン"]
                if not any(t in card.card_type for t in holomen_types):
                    # Fallback: check if it's NOT a support card
                    if "サポート" in card.card_type or "エール" in card.card_type:
                        return False
            elif cat not in card.card_type:
                return False

        # card_type_contains filter
        ctc = filt.get("card_type_contains")
        if ctc:
            if ctc not in card.card_type:
                return False

        # card_type_in filter
        cti = filt.get("card_type_in")
        if cti:
            if not any(t in card.card_type for t in cti):
                return False

        # card_name_in filter
        cni = filt.get("card_name_in")
        if cni:
            if card.card_name not in cni:
                return False

        # card_name filter
        cn = filt.get("card_name")
        if cn:
            if card.card_name != cn:
                return False

        # tag filter (requires lookup in card DB)
        tag = filt.get("tag")
        if tag:
            # Look up the card in the full database to check tags
            card_data = self.pm.lookup_card(card.card_number)
            if card_data:
                ability_text = card_data.get("能力テキスト", "")
                tags_text = card_data.get("タグ", "")
                # Tags are typically found in card data or referenced in ability text
                if tag not in str(tags_text) and tag not in str(ability_text):
                    # Check 収録商品 or other fields
                    all_text = json.dumps(card_data, ensure_ascii=False)
                    if tag not in all_text:
                        return False

        # exclude_buzz
        if filt.get("exclude_buzz"):
            if "Buzz" in card.bloom_level:
                return False

        # has_extra filter (check card database 'extra' or '能力テキスト' fields)
        has_extra = filt.get("has_extra")
        if has_extra:
            card_data = self.pm.lookup_card(card.card_number)
            if card_data:
                extra_field = card_data.get("extra", "")
                ability_text = card_data.get("能力テキスト", "")
                if has_extra not in str(extra_field) and has_extra not in str(ability_text):
                    return False
            else:
                return False

        return True

    def _dice_condition_met(self, roll: int, condition_str: str) -> bool:
        """Check if a dice roll meets a condition string like '>=3', '<=3', '3,5,6'."""
        if condition_str.startswith(">="):
            return roll >= int(condition_str[2:])
        if condition_str.startswith("<="):
            return roll <= int(condition_str[2:])
        if "," in condition_str:
            values = [int(v.strip()) for v in condition_str.split(",")]
            return roll in values
        return roll == int(condition_str)

    # ── Helpers ─────────────────────────────────────────────────────

    def _move_card_hand_to_archive(self, card_number: str):
        """Move a specific card from hand to archive."""
        Zone = self.Zone
        hand = self.pm.zones[Zone.HAND]
        for i, card in enumerate(hand):
            if card.card_number == card_number:
                hand.pop(i)
                card.face_up = True
                self.pm.zones[Zone.ARCHIVE].append(card)
                return
        print(f"  ⚠ Card {card_number} not found in hand (may already be removed)")

    def _summarize_actions(self, entry: dict) -> str:
        """Generate a human-readable summary of a card's actions."""
        if not entry:
            return "Unknown card"
        parts = []
        for action in entry.get("actions", []):
            atype = action.get("type", "")
            if atype == ActionType.DRAW:
                parts.append(f"Draw {action.get('count', 1)}")
            elif atype == ActionType.VIEW_DECK_TOP:
                parts.append(f"View top {action.get('count')}, pick matching")
            elif atype == ActionType.SEARCH_DECK:
                parts.append("Search deck → hand")
            elif atype == ActionType.SEARCH_DECK_TO_STAGE:
                parts.append("Search deck → stage")
            elif atype == ActionType.SHUFFLE_HAND_DRAW:
                parts.append(f"Shuffle hand, draw {action.get('draw_count', 5)}")
            elif atype == ActionType.SWAP_OPPONENT_CENTER_BACK:
                parts.append("Swap opponent center ↔ back")
            elif atype == ActionType.SWAP_OWN_CENTER_BACK:
                parts.append("Swap own center ↔ back")
            elif atype == ActionType.ROLL_DICE:
                parts.append("Roll dice for effect")
            elif atype == ActionType.HEAL:
                parts.append(f"Heal {action.get('amount', 0)} HP")
            elif atype == ActionType.ARTS_BOOST:
                parts.append(f"Arts +{action.get('amount', 0)}")
            elif atype == ActionType.DEAL_SPECIAL_DAMAGE:
                parts.append(f"Special damage {action.get('amount', 0)}")
            elif atype == ActionType.CONDITIONAL:
                parts.append("Conditional bonus effect")
            else:
                parts.append(str(atype))
        if entry.get("is_limited"):
            parts.append("[LIMITED]")
