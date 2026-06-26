"""
hOCG Game State Mixin
======================
State serialization and query methods for the Match class.
Extracted from game_engine.py for modularity.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .game_engine import Player

from .playmat_manager import Zone
from .card_data import SUPPORT_CARD_DB


class GameStateMixin:
    """Mixin providing state serialization & query methods for Match."""

    # ═══════════════════════════════════════════════════════════════
    #  State serialization
    # ═══════════════════════════════════════════════════════════════

    def _get_available_oshi_actions(self, player_id: str) -> List[str]:
        """Return list of oshi skill actions currently available to this player."""
        actions = []
        player = self.players.get(player_id)
        if not player:
            return actions
        oshi_data = self._get_oshi_data(player)
        if not oshi_data:
            return actions

        state = self.oshi_skill_state.get(player_id, {})
        hp_count = len(player.playmat.zones[Zone.HOLO_POWER])

        oshi_skill = oshi_data.get("oshi_skill", {})
        if oshi_skill:
            cost = oshi_skill.get("ホロパワー", 0)
            can_use = (not state.get("oshi_skill_used_this_turn")
                       and (str(cost) == "X" or hp_count >= int(cost)))
            if can_use:
                actions.append("use_oshi_skill")

        sp_skill = oshi_data.get("sp_oshi_skill", {})
        if sp_skill:
            cost = int(sp_skill.get("ホロパワー", 0))
            can_use = (not state.get("sp_oshi_skill_used")
                       and hp_count >= cost)
            if can_use:
                actions.append("use_sp_oshi_skill")

        if oshi_skill or sp_skill:
            actions.append("get_oshi_skill_info")

        return actions

    def get_allowed_actions(self, player_id: str) -> List[str]:
        """Return list of action types available to this player right now."""

        # Mulligan phase: both players act simultaneously
        if self.game_state == "mulligan":
            ss = self.setup_state.get(player_id, {})
            if ss.get("ready"):
                return []   # waiting for opponent
            if ss.get("returning", 0) > ss.get("returned", 0):
                return ["setup_return_card"]
            actions = []
            # Free mulligan (hand #1) always; after that only without Debut
            if ss.get("hand_number", 1) <= 1 or not ss.get("has_debut"):
                actions.append("setup_mulligan")
            if ss.get("has_debut"):
                actions.append("mulligan_ready")
            return actions

        # Setup phase (placement): both players act simultaneously
        if self.game_state == "setup":
            ss = self.setup_state.get(player_id, {})
            if ss.get("ready"):
                return []   # waiting for opponent
            actions = ["setup_place", "setup_return_to_hand"]
            if ss.get("centre_placed"):
                actions.append("setup_ready")
            return actions

        if self.game_state == "dice_roll":
            p = self.players.get(player_id)
            if p and p.dice_roll is None:
                return ["roll_dice"]
            return []

        if self.game_state == "choose_order":
            if self.step_state.get("chooser") == player_id:
                return ["choose_order"]
            return []

        if self.game_state != "playing":
            return []

        # Pending interrupts — oshi skills can be used as interrupt by either player
        oshi_actions = self._get_available_oshi_actions(player_id)

        if self.pending_life_deduction:
            if player_id == self.pending_life_deduction:
                return ["deduct_life", "end_deduct_life"] + oshi_actions
            # Non-pending player can still use oshi skills as interrupt
            return oshi_actions

        # Pending support card picks
        pending_support = self.step_state.get("pending_support")
        if pending_support and pending_support.get("picks"):
            if player_id == pending_support["player_id"]:
                return ["pick_support_cards"] + oshi_actions
            return oshi_actions

        if self.pending_centre_fill:
            if player_id == self.pending_centre_fill:
                return ["move_to_centre"] + oshi_actions
            return oshi_actions

        if player_id != self.turn_player_id:
            return []

        step = self.current_step
        return sorted(self.STEP_ACTIONS.get(step, set()))

    def _filter_zone_for_opponent(self, zone: Zone, cards: list) -> Any:
        hidden_zones = {Zone.HAND, Zone.DECK, Zone.LIFE, Zone.YELL_DECK}
        if zone in hidden_zones:
            return {"count": len(cards), "hidden": True}
        result = []
        for c in cards:
            if c.face_up:
                result.append(self._card_to_minimal_dict(c))
            else:
                # Face-down card: reveal presence but not identity
                result.append({
                    "face_up": False,
                    "card_number": "???",
                    "card_name": "???",
                    "card_type": "???",
                    "image_file": "",
                    "bloom_level": "",
                    "resting": c.resting,
                    "damage": 0,
                    "color": [],
                    "hp": 0,
                    "arts": [],
                    "baton_touch": 0,
                    "attached_yells": [],
                    "stacked_cards": [],
                })
        return result

    # Bloom level ordering for bloom_gte comparisons
    _BLOOM_ORDER = {"Debut": 0, "Spot": 0, "1st": 1, "2nd": 2, "Buzz": 2}

    def _check_triggered_condition(self, condition: dict, card) -> bool:
        """Check if a triggered_effect condition matches the holomen card."""
        # holomen name match
        holo_name = condition.get("holomen")
        if holo_name and card.card_name != holo_name:
            return False
        # holomen name in list
        holo_in = condition.get("holomen_in")
        if holo_in and card.card_name not in holo_in:
            return False
        # exact bloom level
        bl = condition.get("bloom_level")
        if bl and getattr(card, 'bloom_level', '') != bl:
            return False
        # bloom level in list
        bl_in = condition.get("bloom_level_in")
        if bl_in and getattr(card, 'bloom_level', '') not in bl_in:
            return False
        # bloom_gte (>=)
        bl_gte = condition.get("bloom_gte")
        if bl_gte:
            card_bl = getattr(card, 'bloom_level', '')
            if self._BLOOM_ORDER.get(card_bl, -1) < self._BLOOM_ORDER.get(bl_gte, 99):
                return False
        # tag match
        tag = condition.get("tag")
        if tag:
            card_tags = getattr(card, 'tags', [])
            if tag not in card_tags:
                return False
        return True

    def _card_to_minimal_dict(self, card):
        # Calculate arts modifier and HP bonus from attached supports
        arts_mod = 0
        hp_bonus = 0
        for sp in getattr(card, 'attached_supports', []):
            sp_entry = SUPPORT_CARD_DB.get(sp.card_number, {})
            for pe in sp_entry.get("passive_effects", []):
                if pe.get("type") == "arts_modifier":
                    arts_mod += pe.get("amount", 0)
                elif pe.get("type") == "hp_modifier":
                    hp_bonus += pe.get("amount", 0)
            # Evaluate triggered_effects with passive trigger
            for te in sp_entry.get("triggered_effects", []):
                if not self._check_triggered_condition(te.get("condition", {}), card):
                    continue
                for eff in te.get("effects", []):
                    if eff.get("trigger") != "passive":
                        continue
                    effect_str = eff.get("effect", "")
                    # Parse "hp+N" / "arts+N"
                    if effect_str.startswith("hp+"):
                        try:
                            hp_bonus += int(effect_str[3:])
                        except ValueError:
                            pass
                    elif effect_str.startswith("arts+") and effect_str[5:].isdigit():
                        try:
                            arts_mod += int(effect_str[5:])
                        except ValueError:
                            pass
        return {
            "card_number": card.card_number,
            "card_name": card.card_name,
            "card_type": card.card_type,
            "image_file": getattr(card, 'image_file', ''),
            "face_up": card.face_up,
            "bloom_level": getattr(card, 'bloom_level', ''),
            "resting": card.resting,
            "damage": getattr(card, 'damage', 0),
            "color": getattr(card, 'color', []),
            "hp": getattr(card, 'hp', 0) + hp_bonus,
            "arts": getattr(card, 'arts', []),
            "baton_touch": getattr(card, 'baton_touch', 0),
            "arts_modifier": arts_mod,
            "attached_yells": [self._card_to_minimal_dict(y) for y in card.attached_yells],
            "stacked_cards": [self._card_to_minimal_dict(s) for s in card.stacked_cards],
            "attached_supports": [self._card_to_minimal_dict(sp) for sp in getattr(card, 'attached_supports', [])],
            "debut_this_turn": getattr(card, 'debut_this_turn', False),
        }

    def get_filtered_state(self, for_player_id: str) -> Dict[str, Any]:
        # Filter step_state: remove internal refs, include pending_support
        filtered_step_state = {
            k: v for k, v in self.step_state.items()
            if not k.startswith("_")
        }
        # Only show pending_support picks to the owning player
        ps = filtered_step_state.get("pending_support")
        if ps and ps.get("player_id") != for_player_id:
            filtered_step_state = {
                k: v for k, v in filtered_step_state.items()
                if k != "pending_support"
            }

        out: Dict[str, Any] = {
            "match_id": self.id,
            "game_state": self.game_state,
            "phase": self.current_step if self.game_state == "playing" else self.game_state,
            "step": self.current_step if self.game_state == "playing" else None,
            "step_index": self.step_index,
            "step_state": filtered_step_state,
            "turn_player_id": self.turn_player_id,
            "turn_number": self.turn_number,
            "started": self.started,
            "events": self.events,
            "allowed_actions": self.get_allowed_actions(for_player_id),
            "pending_life_deduction": self.pending_life_deduction,
            "pending_centre_fill": self.pending_centre_fill,
            "winner": self.winner,
            "loser": self.loser,
            "lose_reason": self.lose_reason,
            "oshi_skill_state": self.oshi_skill_state.get(for_player_id, {}),
            "players": {},
        }

        # Setup state (mulligan or placement)
        if self.game_state in ("mulligan", "setup"):
            out["setup_state"] = {}
            for pid in self.players:
                ss = self.setup_state.get(pid, {})
                if pid == for_player_id:
                    out["setup_state"][pid] = dict(ss)
                else:
                    # Opponent: only reveal limited info
                    out["setup_state"][pid] = {
                        "ready": ss.get("ready", False),
                        "hand_number": ss.get("hand_number", 1),
                        "centre_placed": ss.get("centre_placed", False),
                    }

        # Dice roll info
        if self.game_state in ("dice_roll", "dice_result", "choose_order"):
            out["dice_rolls"] = {
                pid: p.dice_roll for pid, p in self.players.items()
            }
            if self.game_state == "choose_order":
                out["dice_chooser"] = self.step_state.get("chooser")

        for pid, p in self.players.items():
            pinfo: Dict[str, Any] = {
                "name": p.name,
                "ready": p.ready,
                "deck_code": p.deck_code or "",
            }
            if pid == for_player_id:
                zones = {}
                for zone, cards in p.playmat.zones.items():
                    zones[zone.value] = [self._card_to_minimal_dict(c) for c in cards]
                pinfo["zones"] = zones
            else:
                zones: Dict[str, Any] = {}
                for zone in p.playmat.zones:
                    cards = p.playmat.zones[zone]
                    zones[zone.value] = self._filter_zone_for_opponent(zone, cards)
                pinfo["zones"] = zones
            out["players"][pid] = pinfo
        return out
