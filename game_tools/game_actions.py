"""
hOCG Game Action Handlers Mixin
================================
In-game action handlers: card placement, bloom, collabo, arts,
baton touch, oshi skills, peek, archive, etc.
Extracted from game_engine.py for modularity.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .game_engine import Player

from .playmat_manager import Zone
from .card_data import SUPPORT_CARD_DB


class GameActionsMixin:
    """Mixin providing in-game action handlers for Match."""

    # ── Move to centre (step 1 / step 6 / pending fill) ───────────

    def _handle_move_to_centre(self, player_id: str, player: Player,
                               action: Dict[str, Any]) -> Dict[str, Any]:
        if player.playmat.zones[Zone.CENTRE]:
            return {"success": False, "reason": "centre already occupied"}

        from_zone_name = action.get("from_zone")
        card_number = action.get("card_number")
        card_idx = action.get("card_index")
        try:
            from_zone = Zone(from_zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}

        if from_zone not in {Zone.BACK, Zone.HAND}:
            return {"success": False, "reason": "can only move from back or hand"}

        zone_cards = player.playmat.zones[from_zone]
        idx = None
        if card_number:
            for i, c in enumerate(zone_cards):
                if c.card_number == card_number:
                    idx = i
                    break
        elif card_idx is not None:
            idx = int(card_idx)

        if idx is None or idx >= len(zone_cards):
            return {"success": False, "reason": "card not found"}

        card = zone_cards[idx]
        if "ホロメン" not in card.card_type:
            return {"success": False, "reason": "only holomen can be placed on centre"}

        zone_cards.pop(idx)
        card.face_up = True
        # Mark newly placed holomen from hand
        if from_zone == Zone.HAND and 'ホロメン' in (card.card_type or ''):
            card.debut_this_turn = True
        player.playmat.zones[Zone.CENTRE].append(card)
        self.events.append({"event": "holomen_to_centre", "card": card.card_name})

        # Clear pending_centre_fill if this was an interrupt
        if self.pending_centre_fill == player_id:
            self.pending_centre_fill = None
            return {"success": True}

        # Normal step flow
        if self.step_state.get("need_centre"):
            self.step_state = {}
            if self.current_step == "reset":
                self._advance_step()
            elif self.current_step == "end":
                self._pass_turn()
        return {"success": True}

    # ── Play card from hand ────────────────────────────────────────

    def _handle_play_card(self, player_id: str, player: Player,
                          action: Dict[str, Any]) -> Dict[str, Any]:
        cn = action.get("card_number")
        to_zone_name = action.get("zone")
        face_up = action.get("face_up", True)
        try:
            to_zone = Zone(to_zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}

        STAGE_ZONES = {Zone.CENTRE, Zone.COLLABO, Zone.BACK}
        hand = player.playmat.zones[Zone.HAND]
        idx = None
        for i, c in enumerate(hand):
            if c.card_number == cn:
                idx = i
                break
        if idx is None:
            return {"success": False, "reason": "card not in hand"}
        if to_zone in STAGE_ZONES and "ホロメン" not in hand[idx].card_type:
            return {"success": False, "reason": "only holomen can be placed on stage"}

        # Stage holomen limit: max 6 across centre + back + collabo
        if to_zone in STAGE_ZONES:
            total_stage = (len(player.playmat.zones[Zone.CENTRE])
                          + len(player.playmat.zones[Zone.BACK])
                          + len(player.playmat.zones[Zone.COLLABO]))
            if total_stage >= 6:
                return {"success": False, "reason": "stage is full (max 6 holomen)"}

        # If placing to centre during pending_centre_fill
        if to_zone == Zone.CENTRE and self.pending_centre_fill == player_id:
            card = hand.pop(idx)
            card.face_up = True
            card.debut_this_turn = True
            player.playmat.zones[Zone.CENTRE].append(card)
            self.pending_centre_fill = None
            self.events.append({"event": "holomen_to_centre", "card": card.card_name})
            return {"success": True}

        the_card = hand[idx]  # save ref before move_card pops it
        ok = player.playmat.move_card(Zone.HAND, to_zone, idx, face_up=face_up)
        if ok and to_zone in STAGE_ZONES and 'ホロメン' in (the_card.card_type or ''):
            # Mark newly placed holomen
            the_card.debut_this_turn = True
        return {"success": bool(ok)}

    # ── Place card by number ───────────────────────────────────────

    def _handle_place_card(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        zone_name = action.get("zone")
        cn = action.get("card_number")
        try:
            zone = Zone(zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        STAGE_ZONES = {Zone.CENTRE, Zone.COLLABO, Zone.BACK}
        if zone in STAGE_ZONES:
            card_obj = None
            for c in player.playmat.zones[Zone.HAND]:
                if c.card_number == cn:
                    card_obj = c
                    break
            if card_obj is None:
                for c in player.playmat.zones[Zone.DECK]:
                    if c.card_number == cn:
                        card_obj = c
                        break
            if card_obj and "ホロメン" not in card_obj.card_type:
                return {"success": False, "reason": "only holomen can be placed on stage"}
            total_stage = (len(player.playmat.zones[Zone.CENTRE])
                          + len(player.playmat.zones[Zone.BACK])
                          + len(player.playmat.zones[Zone.COLLABO]))
            if total_stage >= 6:
                return {"success": False, "reason": "stage is full (max 6 holomen)"}
        try:
            player.playmat.place_card_by_number(zone, cn, face_up=action.get("face_up", None))
            # Mark newly placed holomen
            if zone in STAGE_ZONES:
                placed = player.playmat.zones[zone][-1]
                if 'ホロメン' in (placed.card_type or ''):
                    placed.debut_this_turn = True
            return {"success": True}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    # ── Move card between zones ────────────────────────────────────

    def _handle_move(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        from_zone_name = action.get("from_zone")
        to_zone_name = action.get("to_zone")
        cn = action.get("card_number")
        face_up = action.get("face_up", None)
        try:
            from_zone = Zone(from_zone_name)
            to_zone = Zone(to_zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}

        # Cards moved to hand should always be face-up
        if to_zone == Zone.HAND and face_up is None:
            face_up = True

        zone_list = player.playmat.zones[from_zone]
        idx = None
        for i, c in enumerate(zone_list):
            if c.card_number == cn:
                idx = i
                break
        if idx is None:
            return {"success": False, "reason": "card not found in from_zone"}
        STAGE_ZONES = {Zone.CENTRE, Zone.COLLABO, Zone.BACK}
        if to_zone in STAGE_ZONES and "ホロメン" not in zone_list[idx].card_type:
            return {"success": False, "reason": "only holomen can be placed on stage"}
        # Stage holomen limit (skip if moving between stage zones)
        if to_zone in STAGE_ZONES and from_zone not in STAGE_ZONES:
            total_stage = (len(player.playmat.zones[Zone.CENTRE])
                          + len(player.playmat.zones[Zone.BACK])
                          + len(player.playmat.zones[Zone.COLLABO]))
            if total_stage >= 6:
                return {"success": False, "reason": "stage is full (max 6 holomen)"}
        position = action.get("position")  # 'bottom' to insert at index 0
        the_card = zone_list[idx]  # save ref before move_card pops it
        ok = player.playmat.move_card(from_zone, to_zone, idx, face_up=face_up)
        if ok and position == "bottom" and to_zone in (Zone.DECK, Zone.YELL_DECK):
            # move_card appends (top); shift to bottom
            card = player.playmat.zones[to_zone].pop()
            player.playmat.zones[to_zone].insert(0, card)
        # Mark newly placed holomen from hand
        if ok and from_zone == Zone.HAND and to_zone in STAGE_ZONES and 'ホロメン' in (the_card.card_type or ''):
            the_card.debut_this_turn = True
        return {"success": bool(ok)}

    # ── Attach yell ────────────────────────────────────────────────

    def _handle_attach_yell(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        zone_name = action.get("zone")
        card_idx = int(action.get("card_index", 0))
        try:
            zone = Zone(zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        yell_deck = player.playmat.zones[Zone.YELL_DECK]
        if not yell_deck:
            return {"success": False, "reason": "yell deck empty"}
        yell_card = yell_deck.pop()
        yell_card.face_up = True
        target_zone = player.playmat.zones[zone]
        if card_idx >= len(target_zone):
            yell_deck.append(yell_card)
            return {"success": False, "reason": "no card at that index"}
        target_zone[card_idx].attached_yells.append(yell_card)
        return {"success": True}

    # ── Search yell (pick a card from yell deck → attach or archive) ──

    def _handle_search_yell(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        card_number = action.get("card_number")
        destination = action.get("destination")  # "attach" or "archive"
        yell_deck = player.playmat.zones[Zone.YELL_DECK]
        if not yell_deck:
            return {"success": False, "reason": "yell deck empty"}
        # Find the card in yell deck
        idx = None
        for i, c in enumerate(yell_deck):
            if c.card_number == card_number:
                idx = i
                break
        if idx is None:
            return {"success": False, "reason": "card not found in yell deck"}

        if destination == "archive":
            card = yell_deck.pop(idx)
            card.face_up = True
            player.playmat.zones[Zone.ARCHIVE].append(card)
            return {"success": True}
        elif destination == "attach":
            zone_name = action.get("zone")
            card_idx = int(action.get("card_index", 0))
            try:
                zone = Zone(zone_name)
            except Exception:
                return {"success": False, "reason": "invalid zone"}
            target_zone = player.playmat.zones[zone]
            if card_idx >= len(target_zone):
                return {"success": False, "reason": "no card at that index"}
            card = yell_deck.pop(idx)
            card.face_up = True
            target_zone[card_idx].attached_yells.append(card)
            return {"success": True}
        else:
            return {"success": False, "reason": "invalid destination (attach or archive)"}

    # ── Toggle rest ────────────────────────────────────────────────

    def _handle_toggle_rest(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        zone_name = action.get("zone")
        card_idx = int(action.get("card_index", 0))
        try:
            zone = Zone(zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        cards = player.playmat.zones[zone]
        if card_idx >= len(cards):
            return {"success": False, "reason": "no card at index"}
        cards[card_idx].resting = not cards[card_idx].resting
        return {"success": True, "resting": cards[card_idx].resting}

    # ── Bloom ──────────────────────────────────────────────────────

    def _handle_bloom(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        zone_name = action.get("zone")
        card_idx = int(action.get("card_index", 0))
        hand_card_number = action.get("hand_card_number")
        try:
            zone = Zone(zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        target_cards = player.playmat.zones[zone]
        if card_idx >= len(target_cards):
            return {"success": False, "reason": "no card at index"}
        target = target_cards[card_idx]
        hand = player.playmat.zones[Zone.HAND]
        hi = None
        for i, c in enumerate(hand):
            if c.card_number == hand_card_number:
                hi = i
                break
        if hi is None:
            return {"success": False, "reason": "card not in hand"}
        bloom_card = hand.pop(hi)
        bloom_card.face_up = True
        bloom_card.attached_yells = target.attached_yells[:]
        bloom_card.attached_supports = getattr(target, 'attached_supports', [])[:]
        bloom_card.damage = target.damage
        old = target_cards.pop(card_idx)
        old_stack = old.stacked_cards[:]
        old.stacked_cards = []
        old.attached_yells = []
        old.attached_supports = []
        bloom_card.stacked_cards = old_stack + [old]
        target_cards.insert(card_idx, bloom_card)
        return {"success": True}

    # ── Collabo (deck → holo power) ────────────────────────────────

    def _handle_collabo(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        from_zone_name = action.get("from_zone")
        card_idx = int(action.get("card_index", 0))
        try:
            from_zone = Zone(from_zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        if len(player.playmat.zones[Zone.COLLABO]) >= 1:
            return {"success": False, "reason": "collabo occupied"}
        total_stage = (len(player.playmat.zones[Zone.CENTRE])
                      + len(player.playmat.zones[Zone.BACK])
                      + len(player.playmat.zones[Zone.COLLABO]))
        # Collabo from back doesn't increase total, from hand does
        if from_zone_name != 'back' and total_stage >= 6:
            return {"success": False, "reason": "stage is full (max 6 holomen)"}
        cards = player.playmat.zones[from_zone]
        if card_idx >= len(cards):
            return {"success": False, "reason": "no card at index"}
        card = cards.pop(card_idx)
        card.face_up = True
        player.playmat.zones[Zone.COLLABO].append(card)
        if player.playmat.zones[Zone.DECK]:
            hp = player.playmat.zones[Zone.DECK].pop()
            hp.face_up = False
            player.playmat.zones[Zone.HOLO_POWER].append(hp)
        return {"success": True}

    # ── Force collabo (no deck → HP) ───────────────────────────────

    def _handle_force_collabo(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        from_zone_name = action.get("from_zone")
        card_idx = int(action.get("card_index", 0))
        try:
            from_zone = Zone(from_zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        if len(player.playmat.zones[Zone.COLLABO]) >= 1:
            return {"success": False, "reason": "collabo occupied"}
        if from_zone_name != 'back':
            total_stage = (len(player.playmat.zones[Zone.CENTRE])
                          + len(player.playmat.zones[Zone.BACK])
                          + len(player.playmat.zones[Zone.COLLABO]))
            if total_stage >= 6:
                return {"success": False, "reason": "stage is full (max 6 holomen)"}
        cards = player.playmat.zones[from_zone]
        if card_idx >= len(cards):
            return {"success": False, "reason": "no card at index"}
        card = cards.pop(card_idx)
        card.face_up = True
        player.playmat.zones[Zone.COLLABO].append(card)
        return {"success": True}

    # ── Deduct life ────────────────────────────────────────────────

    def _handle_deduct_life(self, player_id: str, player: Player,
                            action: Dict[str, Any]) -> Dict[str, Any]:
        attach_zone_name = action.get("zone")
        card_idx = int(action.get("card_index", 0))
        life = player.playmat.zones[Zone.LIFE]
        if not life:
            # No life left → this player loses
            self._set_game_over(player_id, "no_life")
            return {"success": False, "reason": "no life cards — you lose!"}
        try:
            attach_zone = Zone(attach_zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        target_cards = player.playmat.zones[attach_zone]
        if card_idx >= len(target_cards):
            return {"success": False, "reason": "no card at index"}

        life_card = life.pop()
        life_card.face_up = True
        target_cards[card_idx].attached_yells.append(life_card)

        # Check if this was the last life
        if not life:
            self._set_game_over(player_id, "no_life")
            self.pending_life_deduction = None
            return {"success": True, "game_over": True, "reason": "no_life"}

        # Keep pending_life_deduction active — player uses end_deduct_life when done

        # Centre is now empty after knockout — do NOT immediately force fill.
        # Centre fill happens at reset step (step 1) or end step (step 6).
        if not player.playmat.zones[Zone.CENTRE]:
            self.events.append({"event": "centre_empty_after_knockout",
                                "player_id": player_id})

        return {"success": True}

    def _handle_end_deduct_life(self, player_id: str, player: Player) -> Dict[str, Any]:
        """Player signals done deducting life cards."""
        if self.pending_life_deduction != player_id:
            return {"success": False, "reason": "no pending life deduction"}
        self.pending_life_deduction = None
        self.events.append({"event": "end_deduct_life", "player_id": player_id})

        # Check if centre is empty after knockout — trigger fill
        if not player.playmat.zones[Zone.CENTRE]:
            has_back = bool(player.playmat.zones[Zone.BACK])
            if has_back:
                self.pending_centre_fill = player_id
                self.events.append({"event": "need_centre", "reason": "centre_empty_after_knockout"})
        return {"success": True}

    # ── Oshi skill helpers ─────────────────────────────────────────

    def _get_oshi_data(self, player: Player) -> Optional[Dict[str, Any]]:
        """Look up the oshi card's data from the card database."""
        oshi_cards = player.playmat.zones[Zone.OSHI]
        if not oshi_cards:
            return None
        player.playmat._load_db()
        return player.playmat._card_index.get(oshi_cards[0].card_number, {})

    def _pay_holo_power(self, player: Player, cost: int) -> bool:
        """Archive 'cost' cards from holo_power zone. Returns True if paid."""
        hp_zone = player.playmat.zones[Zone.HOLO_POWER]
        if len(hp_zone) < cost:
            return False
        archive = player.playmat.zones[Zone.ARCHIVE]
        for _ in range(cost):
            card = hp_zone.pop()
            card.face_up = True
            archive.append(card)
        return True

    # ── Get oshi skill info ────────────────────────────────────────

    def _handle_get_oshi_skill_info(self, player_id: str,
                                     player: Player) -> Dict[str, Any]:
        """Return info about this player's oshi skills and availability."""
        oshi_data = self._get_oshi_data(player)
        if not oshi_data:
            return {"success": False, "reason": "no oshi card"}

        state = self.oshi_skill_state.get(player_id, {})
        hp_count = len(player.playmat.zones[Zone.HOLO_POWER])

        oshi_skill = oshi_data.get("oshi_skill", {})
        sp_skill = oshi_data.get("sp_oshi_skill", {})

        oshi_cost = oshi_skill.get("ホロパワー", 0)
        sp_cost = sp_skill.get("ホロパワー", 0)

        # Check if oshi skill can be used
        oshi_available = True
        oshi_reason = ""
        if not oshi_skill:
            oshi_available = False
            oshi_reason = "no oshi skill"
        elif state.get("oshi_skill_used_this_turn"):
            oshi_available = False
            oshi_reason = "already used this turn"
        elif str(oshi_cost) != "X" and hp_count < int(oshi_cost):
            oshi_available = False
            oshi_reason = f"need {oshi_cost} holo power, have {hp_count}"

        # Check if SP skill can be used
        sp_available = True
        sp_reason = ""
        if not sp_skill:
            sp_available = False
            sp_reason = "no SP skill"
        elif state.get("sp_oshi_skill_used"):
            sp_available = False
            sp_reason = "already used (once per game)"
        elif hp_count < int(sp_cost):
            sp_available = False
            sp_reason = f"need {sp_cost} holo power, have {hp_count}"

        return {
            "success": True,
            "holo_power_count": hp_count,
            "oshi_skill": {
                "name": oshi_skill.get("name", ""),
                "effect": oshi_skill.get("effect", ""),
                "cost": oshi_cost,
                "available": oshi_available,
                "reason": oshi_reason,
                "used_this_turn": state.get("oshi_skill_used_this_turn", False),
            } if oshi_skill else None,
            "sp_oshi_skill": {
                "name": sp_skill.get("name", ""),
                "effect": sp_skill.get("effect", ""),
                "cost": sp_cost,
                "available": sp_available,
                "reason": sp_reason,
                "used_this_game": state.get("sp_oshi_skill_used", False),
            } if sp_skill else None,
        }

    # ── Use oshi skill ─────────────────────────────────────────────

    def _handle_use_oshi_skill(self, player_id: str, player: Player,
                               action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use the oshi holomen's oshi skill.
        Requires paying holo power cost (archive cards from holo_power zone).
        For cost "X", client sends {"x_cost": N} to specify how many to pay.
        Timing: [ターンに１回] = once per turn.
        """
        oshi_data = self._get_oshi_data(player)
        if not oshi_data:
            return {"success": False, "reason": "no oshi card"}

        oshi_skill = oshi_data.get("oshi_skill")
        if not oshi_skill:
            return {"success": False, "reason": "oshi has no skill"}

        state = self.oshi_skill_state.get(player_id)
        if not state:
            state = {"oshi_skill_used_this_turn": False, "sp_oshi_skill_used": False}
            self.oshi_skill_state[player_id] = state

        # Check once-per-turn limit
        if state.get("oshi_skill_used_this_turn"):
            return {"success": False, "reason": "oshi skill already used this turn"}

        cost = oshi_skill.get("ホロパワー", 0)
        hp_zone = player.playmat.zones[Zone.HOLO_POWER]

        if str(cost) == "X":
            # Variable cost: client decides how many to pay
            x_cost = int(action.get("x_cost", 0))
            if x_cost < 0:
                return {"success": False, "reason": "x_cost must be >= 0"}
            if x_cost > len(hp_zone):
                return {"success": False,
                        "reason": f"not enough holo power (have {len(hp_zone)}, want {x_cost})"}
            actual_cost = x_cost
        else:
            actual_cost = int(cost)
            if len(hp_zone) < actual_cost:
                return {"success": False,
                        "reason": f"not enough holo power (need {actual_cost}, have {len(hp_zone)})"}

        # Pay the cost
        if actual_cost > 0:
            if not self._pay_holo_power(player, actual_cost):
                return {"success": False, "reason": "failed to pay holo power"}

        # Mark as used this turn
        state["oshi_skill_used_this_turn"] = True

        oshi_card = player.playmat.zones[Zone.OSHI][0]
        self.events.append({
            "event": "oshi_skill_used",
            "player_id": player_id,
            "skill_name": oshi_skill.get("name", ""),
            "skill_effect": oshi_skill.get("effect", ""),
            "cost_paid": actual_cost,
        })

        return {
            "success": True,
            "skill_type": "oshi_skill",
            "skill_name": oshi_skill.get("name", ""),
            "skill_effect": oshi_skill.get("effect", ""),
            "cost_paid": actual_cost,
            "holo_power_remaining": len(player.playmat.zones[Zone.HOLO_POWER]),
        }

    # ── Use SP oshi skill ──────────────────────────────────────────

    def _handle_use_sp_oshi_skill(self, player_id: str, player: Player,
                                   action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use the oshi holomen's SP oshi skill.
        Requires paying holo power cost (archive cards from holo_power zone).
        Timing: [ゲームに１回] = once per game.
        """
        oshi_data = self._get_oshi_data(player)
        if not oshi_data:
            return {"success": False, "reason": "no oshi card"}

        sp_skill = oshi_data.get("sp_oshi_skill")
        if not sp_skill:
            return {"success": False, "reason": "oshi has no SP skill"}

        state = self.oshi_skill_state.get(player_id)
        if not state:
            state = {"oshi_skill_used_this_turn": False, "sp_oshi_skill_used": False}
            self.oshi_skill_state[player_id] = state

        # Check once-per-game limit
        if state.get("sp_oshi_skill_used"):
            return {"success": False, "reason": "SP oshi skill already used this game"}

        cost = int(sp_skill.get("ホロパワー", 0))
        hp_zone = player.playmat.zones[Zone.HOLO_POWER]

        if len(hp_zone) < cost:
            return {"success": False,
                    "reason": f"not enough holo power (need {cost}, have {len(hp_zone)})"}

        # Pay the cost
        if cost > 0:
            if not self._pay_holo_power(player, cost):
                return {"success": False, "reason": "failed to pay holo power"}

        # Mark as used (permanent for the game)
        state["sp_oshi_skill_used"] = True

        oshi_card = player.playmat.zones[Zone.OSHI][0]
        self.events.append({
            "event": "sp_oshi_skill_used",
            "player_id": player_id,
            "skill_name": sp_skill.get("name", ""),
            "skill_effect": sp_skill.get("effect", ""),
            "cost_paid": cost,
        })

        return {
            "success": True,
            "skill_type": "sp_oshi_skill",
            "skill_name": sp_skill.get("name", ""),
            "skill_effect": sp_skill.get("effect", ""),
            "cost_paid": cost,
            "holo_power_remaining": len(player.playmat.zones[Zone.HOLO_POWER]),
        }

    # ── Archive card ───────────────────────────────────────────────

    def _handle_archive_card(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        zone_name = action.get("zone")
        card_idx = int(action.get("card_index", 0))
        mode = action.get("mode", "all")
        try:
            zone = Zone(zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        cards = player.playmat.zones[zone]
        if card_idx >= len(cards):
            return {"success": False, "reason": "no card at index"}

        archive = player.playmat.zones[Zone.ARCHIVE]

        def _archive_flat(c):
            for yc in c.attached_yells:
                yc.face_up = True
                archive.append(yc)
            c.attached_yells = []
            for sp in getattr(c, 'attached_supports', []):
                sp.face_up = True
                archive.append(sp)
            c.attached_supports = []
            for sc in c.stacked_cards:
                _archive_flat(sc)
            c.stacked_cards = []
            c.face_up = True
            c.resting = False
            archive.append(c)

        if mode == "card_only":
            card = cards[card_idx]
            if card.stacked_cards:
                new_top = card.stacked_cards.pop()
                new_top.attached_yells = card.attached_yells[:]
                new_top.stacked_cards = card.stacked_cards[:]
                new_top.resting = card.resting
                new_top.damage = card.damage
                new_top.face_up = True
                cards[card_idx] = new_top
                card.attached_yells = []
                card.stacked_cards = []
                card.face_up = True
                card.resting = False
                archive.append(card)
            else:
                card = cards.pop(card_idx)
                _archive_flat(card)
        else:
            card = cards.pop(card_idx)
            _archive_flat(card)
        return {"success": True}

    # ── Hand to deck ───────────────────────────────────────────────

    def _handle_hand_to_deck(self, player: Player) -> Dict[str, Any]:
        hand = player.playmat.zones[Zone.HAND]
        count = len(hand)
        while hand:
            c = hand.pop()
            c.face_up = False
            player.playmat.zones[Zone.DECK].append(c)
        player.playmat.shuffle_deck()
        return {"success": True, "count": count}

    # ── Manual reset step (legacy compat) ──────────────────────────

    def _handle_manual_reset_step(self, player: Player) -> Dict[str, Any]:
        moved = 0
        while player.playmat.zones[Zone.COLLABO]:
            c = player.playmat.zones[Zone.COLLABO].pop()
            c.resting = True
            if len(player.playmat.zones[Zone.BACK]) < 5:
                player.playmat.zones[Zone.BACK].append(c)
                moved += 1
            else:
                player.playmat.zones[Zone.COLLABO].append(c)
                break
        for c in player.playmat.zones[Zone.BACK]:
            c.resting = True
        return {"success": True, "moved": moved}

    # ── Play arts (performance) ────────────────────────────────────

    def _handle_play_arts(self, player_id: str, player: Player,
                          action: Dict[str, Any]) -> Dict[str, Any]:
        zone_name = action.get("zone")
        card_idx = int(action.get("card_index", 0))
        arts_idx = int(action.get("arts_index", 0))
        target_pid = action.get("target_player_id")
        target_zone_name = action.get("target_zone")
        target_card_idx = int(action.get("target_card_index", 0))

        try:
            zone = Zone(zone_name)
        except Exception:
            return {"success": False, "reason": "invalid attacker zone"}
        if zone not in {Zone.CENTRE, Zone.COLLABO}:
            return {"success": False, "reason": "arts only from centre or collabo"}

        atk_cards = player.playmat.zones[zone]
        if card_idx >= len(atk_cards):
            return {"success": False, "reason": "no card at attacker index"}
        attacker = atk_cards[card_idx]

        if attacker.resting:
            return {"success": False, "reason": "resting holomen cannot use arts"}

        arts_list = getattr(attacker, 'arts', [])
        if not arts_list or arts_idx >= len(arts_list):
            return {"success": False, "reason": "invalid arts index"}
        art = arts_list[arts_idx]

        # check yell requirements
        required_colors = art.get("エール", [])
        attached = attacker.attached_yells[:]
        used = [False] * len(attached)
        for req_color in required_colors:
            matched = False
            for i, yell in enumerate(attached):
                if used[i]:
                    continue
                yell_colors = getattr(yell, 'color', []) or []
                if req_color == "無":
                    used[i] = True
                    matched = True
                    break
                elif req_color in yell_colors:
                    used[i] = True
                    matched = True
                    break
            if not matched:
                return {"success": False, "reason": f"not enough yells (need {req_color})"}

        target_player = self.players.get(target_pid)
        if target_player is None or target_pid == player_id:
            return {"success": False, "reason": "invalid target player"}

        try:
            target_zone = Zone(target_zone_name)
        except Exception:
            return {"success": False, "reason": "invalid target zone"}
        if target_zone not in {Zone.CENTRE, Zone.COLLABO, Zone.BACK}:
            return {"success": False, "reason": "can only target stage holomen"}

        tgt_cards = target_player.playmat.zones[target_zone]
        if target_card_idx >= len(tgt_cards):
            return {"success": False, "reason": "no card at target index"}
        target = tgt_cards[target_card_idx]

        raw_dmg = art.get("damage", 0)
        if isinstance(raw_dmg, str):
            m = re.match(r'(\d+)', str(raw_dmg))
            dmg = int(m.group(1)) if m else 0
        else:
            dmg = int(raw_dmg)

        # Apply support card arts modifier (tool/mascot/fan)
        if hasattr(player, 'support_executor') and player.support_executor:
            arts_mod = player.support_executor.get_arts_modifier(attacker)
            dmg += arts_mod
            # Apply one-turn modifiers from support cards
            for tm in player.support_executor.get_turn_modifiers():
                if tm.get("type") == "arts_plus":
                    dmg += tm.get("amount", 0)

        if dmg < 0:
            dmg = 0

        target.damage += dmg
        # Use effective HP (base + attached support HP modifiers)
        target_hp = getattr(target, 'hp', 0)
        if hasattr(target_player, 'support_executor') and target_player.support_executor:
            target_hp = target_player.support_executor.get_effective_hp(target)
        knocked_out = target_hp > 0 and target.damage >= target_hp

        result: Dict[str, Any] = {
            "success": True,
            "art_name": art.get("name", ""),
            "damage_dealt": dmg,
            "target_card": target.card_name,
            "target_total_damage": target.damage,
            "target_hp": target_hp,
            "knocked_out": knocked_out,
        }

        if knocked_out:
            archive = target_player.playmat.zones[Zone.ARCHIVE]

            def _archive_flat(c):
                for yc in c.attached_yells:
                    yc.face_up = True
                    archive.append(yc)
                c.attached_yells = []
                for sp in getattr(c, 'attached_supports', []):
                    sp.face_up = True
                    archive.append(sp)
                c.attached_supports = []
                for sc in c.stacked_cards:
                    _archive_flat(sc)
                c.stacked_cards = []
                c.face_up = True
                c.resting = False
                c.damage = 0
                archive.append(c)

            ko_card = tgt_cards.pop(target_card_idx)
            _archive_flat(ko_card)

            self.events.append({
                "event": "knockout",
                "card": target.card_name,
                "opponent_id": target_pid,
            })

            # Opponent must deduct life
            opp_life = target_player.playmat.zones[Zone.LIFE]
            if not opp_life:
                self._set_game_over(target_pid, "no_life")
            else:
                self.pending_life_deduction = target_pid
                result["pending_life_deduction"] = True

        return result

    # ── Baton touch (centre retreat) ───────────────────────────────

    def _handle_baton_touch(self, player: Player,
                            action: Dict[str, Any]) -> Dict[str, Any]:
        """Centre holomen retreats to back, archiving required yells as cost."""
        centre = player.playmat.zones[Zone.CENTRE]
        if not centre:
            return {"success": False, "reason": "no centre holomen"}

        card = centre[0]
        cost = getattr(card, 'baton_touch', 0)

        if cost > 0:
            attached = card.attached_yells
            if len(attached) < cost:
                return {"success": False,
                        "reason": f"need {cost} attached yell(s) to retreat, have {len(attached)}"}
            archive = player.playmat.zones[Zone.ARCHIVE]
            for _ in range(cost):
                yell = attached.pop(0)
                yell.face_up = True
                archive.append(yell)

        centre.pop(0)
        card.face_up = True
        if len(player.playmat.zones[Zone.BACK]) < 5:
            player.playmat.zones[Zone.BACK].append(card)
        return {"success": True, "cost_paid": cost}

    # ── Get zone cards (info) ──────────────────────────────────────

    def _handle_get_zone_cards(self, player: Player,
                               action: Dict[str, Any]) -> Dict[str, Any]:
        zone_name = action.get("zone")
        try:
            zone = Zone(zone_name)
        except Exception:
            return {"success": False, "reason": "invalid zone"}
        cards = player.playmat.zones[zone]
        return {
            "success": True,
            "cards": [player.playmat._card_to_dict(c) for c in cards],
        }

    # ── Peek deck (view top N) ─────────────────────────────────────

    def _handle_peek_deck(self, player: Player,
                          action: Dict[str, Any]) -> Dict[str, Any]:
        """View top N cards of deck. Optionally execute a sub-action on one card."""
        count = int(action.get("count", 5))
        count = min(count, len(player.playmat.zones[Zone.DECK]))
        if count <= 0:
            return {"success": False, "reason": "deck is empty"}

        sub = action.get("sub_action")
        if sub:
            # Perform a manipulation on one of the peeked cards
            sub_type = sub.get("type")
            deck = player.playmat.zones[Zone.DECK]
            top_start = len(deck) - count

            # ── Bulk operations: card_indices = ordered list of deck indices ──
            if sub_type in ("all_to_top", "all_to_bottom", "all_to_archive"):
                ordered_indices = sub.get("card_indices", [])
                if not ordered_indices:
                    return {"success": False, "reason": "no card_indices provided"}
                # Validate all indices are within peek range
                for ci in ordered_indices:
                    if ci < top_start or ci >= len(deck):
                        return {"success": False, "reason": f"index {ci} out of peek range"}
                # Gather cards in the user-specified order (remove from highest index first to keep indices stable)
                sorted_desc = sorted(ordered_indices, reverse=True)
                removed = {}
                for ci in sorted_desc:
                    removed[ci] = deck.pop(ci)
                cards_in_order = [removed[ci] for ci in ordered_indices]

                if sub_type == "all_to_top":
                    # First in list = top of deck → append in reverse so first ends up on top
                    for c in reversed(cards_in_order):
                        deck.append(c)
                    self.events.append({"event": "peek_all_to_top", "count": len(cards_in_order)})
                    return {"success": True}

                if sub_type == "all_to_bottom":
                    # Last in display order (#5) = deepest bottom → insert in forward order
                    for c in cards_in_order:
                        deck.insert(0, c)
                    self.events.append({"event": "peek_all_to_bottom", "count": len(cards_in_order)})
                    return {"success": True}

                if sub_type == "all_to_archive":
                    for c in cards_in_order:
                        c.face_up = True
                        player.playmat.zones[Zone.ARCHIVE].append(c)
                    self.events.append({"event": "peek_all_to_archive", "count": len(cards_in_order)})
                    return {"success": True}

            # ── Single card operations ──
            card_idx = int(sub.get("card_index", -1))       # index within deck (0=bottom)

            # Valid index range: top N cards = deck[-count:]
            if card_idx < top_start or card_idx >= len(deck):
                return {"success": False, "reason": "card index out of peek range"}

            card = deck[card_idx]

            if sub_type == "to_hand":
                deck.pop(card_idx)
                card.face_up = True
                player.playmat.zones[Zone.HAND].append(card)
                self.events.append({"event": "peek_to_hand", "card": card.card_name})
                return {"success": True}

            if sub_type == "to_archive":
                deck.pop(card_idx)
                card.face_up = True
                player.playmat.zones[Zone.ARCHIVE].append(card)
                self.events.append({"event": "peek_to_archive", "card": card.card_name})
                return {"success": True}

            if sub_type == "to_top":
                # Move card to the very top of deck
                deck.pop(card_idx)
                deck.append(card)       # top = end of list
                self.events.append({"event": "peek_reorder_top", "card": card.card_name})
                return {"success": True}

            if sub_type == "to_bottom":
                deck.pop(card_idx)
                deck.insert(0, card)    # bottom = start of list
                self.events.append({"event": "peek_to_bottom", "card": card.card_name})
                return {"success": True}

            return {"success": False, "reason": f"unknown sub_action type: {sub_type}"}

        # Just peek — return the cards (top = last elements of the list)
        # Deck layout: index 0 = bottom, index -1 = top
        deck = player.playmat.zones[Zone.DECK]
        actual_count = min(count, len(deck))
        result_cards = []
        for i in range(actual_count):
            # i=0 → top card (deck[-1]), i=1 → second from top, etc.
            deck_idx = len(deck) - 1 - i
            c = deck[deck_idx]
            result_cards.append({
                "deck_index": deck_idx,
                **player.playmat._card_to_dict(c),
            })
        return {"success": True, "cards": result_cards}
