"""
hOCG Game Phases Mixin
=======================
Setup, mulligan, and dice-roll handlers for the Match class.
Extracted from game_engine.py for modularity.
"""

from __future__ import annotations
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .game_engine import Player

from .playmat_manager import Zone


class GamePhasesMixin:
    """Mixin providing setup/mulligan/dice phase handlers for Match."""

    def _handle_load_deck(self, player: Player, action: Dict[str, Any]) -> Dict[str, Any]:
        if self.game_state != "lobby":
            return {"success": False, "reason": "can only load deck in lobby"}
        code = action.get("deck_code", "").strip()
        deck_site = action.get("deck_site", "jp")
        if not code:
            return {"success": False, "reason": "no deck code"}
        if player.ready:
            return {"success": False, "reason": "deck already loaded"}
        try:
            cnt = player.playmat.load_deck_from_decklog(code, deck_site)
            player.deck_code = code
            player.ready = True
            return {"success": True, "loaded": cnt, "all_ready": self.all_ready()}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    # ── Setup phase handlers ──────────────────────────────────────

    def _handle_setup_mulligan(self, player_id: str, player: Player) -> Dict[str, Any]:
        """Mulligan: return all cards to deck, reshuffle, redraw 7.
        Hand 1 = initial draw. Hand 2 = free mulligan. Hand 3+ = return (hand-2) cards.
        Hand 7 = immediate loss."""
        ss = self.setup_state.get(player_id)
        if not ss:
            return {"success": False, "reason": "no setup state"}
        if ss["ready"]:
            return {"success": False, "reason": "already ready"}

        # Free mulligan only on hand #1; after that, need no Debut to mulligan
        if ss["hand_number"] >= 2 and ss["has_debut"]:
            return {"success": False, "reason": "you already have Debut holomen — confirm your hand"}

        new_hand = ss["hand_number"] + 1
        if new_hand >= 7:
            self._set_game_over(player_id, "mulligan_limit")
            return {"success": True, "game_over": True}

        # Return all cards from hand / centre / back to deck
        for zone in [Zone.HAND, Zone.CENTRE, Zone.BACK]:
            while player.playmat.zones[zone]:
                c = player.playmat.zones[zone].pop()
                c.face_up = False
                c.resting = False
                player.playmat.zones[Zone.DECK].append(c)

        player.playmat.shuffle_deck()
        player.playmat.draw_card(7)

        penalty = max(0, new_hand - 2)
        has_debut = any(
            'ホロメン' in c.card_type and c.bloom_level == 'Debut'
            for c in player.playmat.zones[Zone.HAND]
        )

        ss["hand_number"] = new_hand
        ss["returning"] = penalty
        ss["returned"] = 0
        ss["has_debut"] = has_debut
        ss["centre_placed"] = False
        ss["ready"] = False

        self.events.append({
            "event": "mulligan", "player_id": player_id,
            "hand_number": new_hand, "penalty": penalty, "has_debut": has_debut,
        })
        return {"success": True, "hand_number": new_hand,
                "penalty": penalty, "has_debut": has_debut}

    def _handle_setup_return_card(self, player_id: str, player: Player,
                                   action: Dict[str, Any]) -> Dict[str, Any]:
        """Return a selected card from hand to bottom of deck (mulligan penalty)."""
        ss = self.setup_state.get(player_id)
        if not ss:
            return {"success": False, "reason": "no setup state"}
        remaining = ss["returning"] - ss["returned"]
        if remaining <= 0:
            return {"success": False, "reason": "no cards to return"}

        card_number = action.get("card_number")
        hand = player.playmat.zones[Zone.HAND]
        idx = None
        for i, c in enumerate(hand):
            if c.card_number == card_number:
                idx = i
                break
        if idx is None:
            return {"success": False, "reason": "card not in hand"}

        # Block returning the ONLY Debut card (would bypass mandatory Debut check)
        card = hand[idx]
        if 'ホロメン' in card.card_type and card.bloom_level == 'Debut':
            debut_count = sum(
                1 for c in hand
                if 'ホロメン' in c.card_type and c.bloom_level == 'Debut'
            )
            if debut_count <= 1:
                return {"success": False,
                        "reason": "cannot return your only Debut holomen"}

        hand.pop(idx)
        card.face_up = False
        player.playmat.zones[Zone.DECK].insert(0, card)   # bottom of deck
        ss["returned"] += 1
        new_remaining = ss["returning"] - ss["returned"]

        # Re-check debut after return
        ss["has_debut"] = any(
            'ホロメン' in c.card_type and c.bloom_level == 'Debut'
            for c in player.playmat.zones[Zone.HAND]
        )
        self.events.append({
            "event": "setup_return_card", "player_id": player_id,
            "remaining": new_remaining,
        })
        return {"success": True, "remaining": new_remaining}

    def _handle_mulligan_ready(self, player_id: str, player: Player) -> Dict[str, Any]:
        """Signal mulligan complete. Must have Debut in hand. When both ready → dice roll."""
        ss = self.setup_state.get(player_id)
        if not ss:
            return {"success": False, "reason": "no setup state"}
        if not ss.get("has_debut"):
            return {"success": False, "reason": "must have at least one Debut holomen in hand"}
        if ss["returning"] > ss["returned"]:
            return {"success": False,
                    "reason": f"must return {ss['returning'] - ss['returned']} more card(s)"}
        ss["ready"] = True
        all_ready = all(
            self.setup_state[pid]["ready"] for pid in self.players
        )
        if all_ready:
            self.start_setup_phase()
            self.events.append({"event": "mulligan_complete"})
        return {"success": True, "all_mulligan_ready": all_ready}

    def _handle_setup_place(self, player_id: str, player: Player,
                            action: Dict[str, Any]) -> Dict[str, Any]:
        """Place a Debut holomen from hand to centre or back during setup."""
        ss = self.setup_state.get(player_id)
        if not ss:
            return {"success": False, "reason": "no setup state"}
        if ss["ready"]:
            return {"success": False, "reason": "already ready"}
        if ss["returning"] > ss["returned"]:
            return {"success": False,
                    "reason": f"must return {ss['returning'] - ss['returned']} more card(s) first"}

        zone_name = action.get("zone")
        card_number = action.get("card_number")
        if zone_name not in ("centre", "back"):
            return {"success": False, "reason": "can only place to centre or back during setup"}

        zone = Zone(zone_name)
        hand = player.playmat.zones[Zone.HAND]
        idx = None
        for i, c in enumerate(hand):
            if c.card_number == card_number:
                idx = i
                break
        if idx is None:
            return {"success": False, "reason": "card not in hand"}

        card = hand[idx]
        if "ホロメン" not in card.card_type:
            return {"success": False, "reason": "only holomen can be placed on stage"}
        if card.bloom_level != "Debut":
            return {"success": False, "reason": "only Debut holomen during setup"}

        if zone == Zone.CENTRE and player.playmat.zones[Zone.CENTRE]:
            return {"success": False, "reason": "centre already occupied"}
        if zone == Zone.BACK and len(player.playmat.zones[Zone.BACK]) >= 5:
            return {"success": False, "reason": "back is full (max 5)"}

        hand.pop(idx)
        card.face_up = False    # placed face-down; revealed when both ready
        player.playmat.zones[zone].append(card)
        if zone == Zone.CENTRE:
            ss["centre_placed"] = True

        self.events.append({
            "event": "setup_place", "player_id": player_id,
            "card": card.card_name, "zone": zone_name,
        })
        return {"success": True}

    def _handle_setup_return_to_hand(self, player_id: str, player: Player,
                                      action: Dict[str, Any]) -> Dict[str, Any]:
        """Return a card from centre/back to hand during setup (undo placement)."""
        ss = self.setup_state.get(player_id)
        if not ss:
            return {"success": False, "reason": "no setup state"}
        if ss["ready"]:
            return {"success": False, "reason": "already ready"}

        zone_name = action.get("zone")
        card_number = action.get("card_number")
        if zone_name not in ("centre", "back"):
            return {"success": False, "reason": "can only return from centre or back"}

        zone = Zone(zone_name)
        cards = player.playmat.zones[zone]
        idx = None
        for i, c in enumerate(cards):
            if c.card_number == card_number:
                idx = i
                break
        if idx is None:
            return {"success": False, "reason": "card not found in zone"}

        card = cards.pop(idx)
        card.face_up = True
        player.playmat.zones[Zone.HAND].append(card)
        if zone == Zone.CENTRE and not player.playmat.zones[Zone.CENTRE]:
            ss["centre_placed"] = False
        return {"success": True}

    def _handle_setup_ready(self, player_id: str, player: Player) -> Dict[str, Any]:
        """Signal setup (placement) complete. When both ready, start the game."""
        ss = self.setup_state.get(player_id)
        if not ss:
            return {"success": False, "reason": "no setup state"}
        if not ss["centre_placed"]:
            return {"success": False, "reason": "must place a Debut holomen on centre"}

        ss["ready"] = True
        all_ready = all(
            self.setup_state[pid]["ready"] for pid in self.players
        )
        if all_ready:
            # Reveal all stage cards face-up
            for pid2 in self.players:
                p2 = self.players[pid2]
                for zone in [Zone.CENTRE, Zone.BACK]:
                    for c in p2.playmat.zones[zone]:
                        c.face_up = True
            self.events.append({"event": "reveal_stage"})
            # Start the game
            self.game_state = "playing"
            self.turn_number = 1
            self.step_index = 0
            self.step_state = {}
            # Initialize oshi skill tracking for both players
            for pid2 in self.players:
                self.oshi_skill_state[pid2] = {
                    "oshi_skill_used_this_turn": False,
                    "sp_oshi_skill_used": False,
                }
            self.events.append({
                "event": "game_start",
                "first_player": self.turn_player_id,
                "first_player_name": self.players[self.turn_player_id].name,
            })
            self._enter_step()
        return {"success": True, "all_setup_ready": all_ready}
