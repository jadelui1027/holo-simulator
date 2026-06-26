"""
hOCG Pick Resolver Mixin
==========================
Support card play initiation and multi-step pick resolution.
Extracted from game_engine.py for modularity.
"""

from __future__ import annotations
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .game_engine import Player

from .playmat_manager import Zone
from .card_data import SUPPORT_CARD_DB


class PickResolverMixin:
    """Mixin providing support card pick resolution for Match."""

    # ── Support card actions ───────────────────────────────────────

    def _handle_list_supports(self, player: Player) -> Dict[str, Any]:
        """Return list of support cards in hand with playability status."""
        executor = player.support_executor
        supports = executor.list_playable_supports()
        return {"success": True, "supports": supports}

    def _handle_play_support(self, player_id: str, player: Player,
                             action: Dict[str, Any]) -> Dict[str, Any]:
        """Play a support card. May require interactive picks (returned as pending)."""
        card_number = action.get("card_number")
        if not card_number:
            return {"success": False, "reason": "no card_number provided"}

        executor = player.support_executor
        entry = SUPPORT_CARD_DB.get(card_number)
        if not entry:
            return {"success": False, "reason": f"Card {card_number} not in support database"}

        # Check playability
        can, reason = executor.can_play(card_number)
        if not can:
            return {"success": False, "reason": reason}

        # Queue-based approach: intercept callbacks to collect pending picks.
        pending_picks = []
        revealed_cards_store = {}  # pick_id → list of Card objects

        def _capture_pick_cards(cards, min_pick, max_pick, title, message):
            """Capture a card-pick request. Reads executor._pick_extra for enrichment."""
            pick_id = f"pick_{len(pending_picks)}"
            card_dicts = [player.playmat._card_to_dict(c) for c in cards]
            extra = getattr(executor, '_pick_extra', None) or {}

            pick = {
                "pick_id": pick_id,
                "pick_type": extra.get("mode", "cards"),
                "title": title,
                "message": message,
                "min_pick": min_pick,
                "max_pick": max_pick,
                "cards": card_dicts,
            }
            # If selectable_numbers provided, include them for client
            # (send even when empty [] so client knows to enforce the filter)
            sel = extra.get("selectable_numbers")
            if sel is not None:
                pick["selectable_numbers"] = sel
            # Rest-to info for view_deck_top
            rt = extra.get("rest_to")
            if rt:
                pick["rest_to"] = rt

            pending_picks.append(pick)
            revealed_cards_store[pick_id] = cards

            # Check for deferred conditional from executor
            pend_cond = getattr(executor, '_pending_conditional', None)
            if pend_cond:
                pick["conditional"] = pend_cond
                executor._pending_conditional = None

            return None

        def _zone_for_card(card):
            """Return the zone name (centre/collabo/back) for a stage card."""
            from game_tools.playmat_manager import Zone
            for z in [Zone.CENTRE, Zone.COLLABO, Zone.BACK]:
                if card in player.playmat.zones[z]:
                    return z.value
            return ""

        def _capture_pick_holomen(holomen_list, title, message):
            pick_id = f"pick_{len(pending_picks)}"
            card_dicts = []
            for c in holomen_list:
                d = player.playmat._card_to_dict(c)
                d["zone"] = _zone_for_card(c)
                card_dicts.append(d)
            extra = getattr(executor, '_pick_extra', None) or {}

            pick = {
                "pick_id": pick_id,
                "pick_type": extra.get("mode", "holomen"),
                "title": title,
                "message": message,
                "min_pick": 1,
                "max_pick": 1,
                "cards": card_dicts,
            }
            # For attachment, include the support card_number
            if extra.get("card_number"):
                pick["support_card_number"] = extra["card_number"]

            pending_picks.append(pick)
            revealed_cards_store[pick_id] = holomen_list
            return None

        def _capture_order_cards(cards, title, message):
            """Capture a reorder request (e.g. remaining cards for deck bottom)."""
            pick_id = f"pick_{len(pending_picks)}"
            card_dicts = [player.playmat._card_to_dict(c) for c in cards]

            pending_picks.append({
                "pick_id": pick_id,
                "pick_type": "reorder",
                "title": title,
                "message": message,
                "min_pick": 0,
                "max_pick": len(cards),
                "cards": card_dicts,
            })
            revealed_cards_store[pick_id] = cards
            return None

        # Wire capture callbacks
        executor.pick_cards_cb = _capture_pick_cards
        executor.pick_holomen_cb = _capture_pick_holomen
        executor.order_cards_cb = _capture_order_cards

        # Execute the support card
        result = executor.play_support(card_number)

        # Clear callbacks
        executor.pick_cards_cb = None
        executor.pick_holomen_cb = None
        executor.order_cards_cb = None

        if not result.get("success"):
            return result

        # Store pending picks for multi-step client resolution
        if pending_picks:
            self.step_state["pending_support"] = {
                "player_id": player_id,
                "card_number": card_number,
                "card_name": entry.get("card_name", card_number),
                "picks": pending_picks,
            }
            self.step_state["_support_card_refs"] = revealed_cards_store

            self.events.append({
                "event": "support_needs_picks",
                "card_name": entry.get("card_name", card_number),
                "picks": pending_picks,
            })

        self.events.append({
            "event": "support_played",
            "card_name": entry.get("card_name", card_number),
            "card_number": card_number,
            "actions_taken": result.get("actions_taken", []),
        })

        return {
            "success": True,
            "card_name": entry.get("card_name", card_number),
            "actions_taken": result.get("actions_taken", []),
            "pending_picks": pending_picks if pending_picks else None,
            "turn_modifiers": [
                {"type": m.get("type"), "amount": m.get("amount", 0),
                 "target": m.get("target", "?")}
                for m in executor.get_turn_modifiers()
            ],
        }

    def _handle_pick_support_cards(self, player_id: str, player: Player,
                                    action: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a pending support card pick from the client."""
        pending = self.step_state.get("pending_support")
        if not pending or pending["player_id"] != player_id:
            return {"success": False, "reason": "no pending support pick for you"}

        pick_id = action.get("pick_id")
        selected_numbers = action.get("card_numbers", [])  # list of card_numbers

        card_refs = self.step_state.get("_support_card_refs", {})
        if pick_id not in card_refs:
            return {"success": False, "reason": f"unknown pick_id: {pick_id}"}

        available = card_refs[pick_id]  # list of actual Card objects

        # Find the pick spec
        pick_spec = None
        for p in pending["picks"]:
            if p["pick_id"] == pick_id:
                pick_spec = p
                break
        if not pick_spec:
            return {"success": False, "reason": "pick spec not found"}

        pick_type = pick_spec.get("pick_type", "cards")
        max_pick = pick_spec.get("max_pick", 0)
        title = pick_spec.get("title", "").lower()

        # Validate selectable_numbers if present (even empty [] means no cards allowed)
        selectable = pick_spec.get("selectable_numbers")
        if selectable is not None and pick_type == "cards":
            invalid = [cn for cn in selected_numbers if cn not in selectable]
            if invalid:
                return {"success": False,
                        "reason": f"card(s) not selectable: {invalid}"}

        if max_pick >= 0 and len(selected_numbers) > max_pick:
            return {"success": False,
                    "reason": f"too many selections (max {max_pick})"}

        # Find selected Card objects by card_number (order-preserving)
        selected_cards = []
        for cn in selected_numbers:
            for card in available:
                if card.card_number == cn and card not in selected_cards:
                    selected_cards.append(card)
                    break

        # ── Handle by pick_type ──────────────────────────────────
        if pick_type == "reorder":
            # Client sends card_numbers in the desired order.
            # Put them at deck bottom (or top if rest_to == "deck_top").
            rest_to = pick_spec.get("rest_to", "deck_bottom")
            ordered = []
            for cn in selected_numbers:
                for card in available:
                    if card.card_number == cn and card not in ordered:
                        ordered.append(card)
                        break
            # Include any cards not mentioned (append at end)
            for card in available:
                if card not in ordered:
                    ordered.append(card)
            # Remove from deck (they may still be there)
            deck = player.playmat.zones[Zone.DECK]
            for card in ordered:
                if card in deck:
                    deck.remove(card)
                card.face_up = False
            if rest_to == "deck_top":
                # Insert at top: first in ordered = top of deck
                for card in reversed(ordered):
                    deck.append(card)
            else:
                # Insert at bottom: first in ordered = bottom
                for card in ordered:
                    deck.insert(0, card)

        elif pick_type == "select_cheer":
            # Player is selecting yell(s) from stage holomen to archive as cost
            stage_zones = [Zone.CENTRE, Zone.BACK, Zone.COLLABO]
            for card in selected_cards:
                # Find this yell attached to a holomen
                found = False
                for sz in stage_zones:
                    for holomen in player.playmat.zones[sz]:
                        if card in getattr(holomen, 'attached_yells', []):
                            holomen.attached_yells.remove(card)
                            card.face_up = True
                            player.playmat.zones[Zone.ARCHIVE].append(card)
                            found = True
                            break
                    if found:
                        break
                if not found:
                    # Fallback: check if it's still in available list
                    card.face_up = True
                    player.playmat.zones[Zone.ARCHIVE].append(card)

            # On-attach chain: if user skipped (no selection), remove remaining
            # on-attach picks so the search/holomen steps don't fire
            if "on attach" in title and not selected_cards:
                pending["picks"] = [
                    p for p in pending["picks"]
                    if p["pick_id"] == pick_id or "on attach" not in p.get("title", "").lower()
                ]

        elif pick_type == "attach_support":
            # Selected a holomen to attach the support card to
            support_cn = pick_spec.get("support_card_number",
                                       pending.get("card_number"))
            if selected_cards:
                target_holomen = selected_cards[0]
                # Find the support card in hand
                support_card = None
                for hc in player.playmat.zones[Zone.HAND]:
                    if hc.card_number == support_cn:
                        support_card = hc
                        break
                if support_card:
                    player.playmat.zones[Zone.HAND].remove(support_card)
                    support_card.face_up = True
                    if not hasattr(target_holomen, 'attached_supports'):
                        target_holomen.attached_supports = []
                    target_holomen.attached_supports.append(support_card)

                    # Fire on_attach triggered effects
                    entry = SUPPORT_CARD_DB.get(support_cn, {})
                    if entry:
                        executor = player.support_executor
                        on_attach_picks = []
                        on_attach_refs = {}

                        def _cap_pick(cards, mn, mx, ttl, msg):
                            pid = f"pick_{len(pending['picks']) + len(on_attach_picks)}"
                            dicts = [player.playmat._card_to_dict(c) for c in cards]
                            extra = getattr(executor, '_pick_extra', None) or {}
                            p = {
                                "pick_id": pid,
                                "pick_type": extra.get("mode", "cards"),
                                "title": ttl, "message": msg,
                                "min_pick": mn, "max_pick": mx,
                                "cards": dicts,
                            }
                            sel = extra.get("selectable_numbers")
                            if sel is not None:
                                p["selectable_numbers"] = sel
                            rt = extra.get("rest_to")
                            if rt:
                                p["rest_to"] = rt
                            on_attach_picks.append(p)
                            on_attach_refs[pid] = cards
                            return None

                        def _cap_holomen(hl, ttl, msg):
                            pid = f"pick_{len(pending['picks']) + len(on_attach_picks)}"
                            from game_tools.playmat_manager import Zone as _Z
                            def _zfc(card):
                                for z in [_Z.CENTRE, _Z.COLLABO, _Z.BACK]:
                                    if card in player.playmat.zones[z]:
                                        return z.value
                                return ""
                            dicts = []
                            for c in hl:
                                d = player.playmat._card_to_dict(c)
                                d["zone"] = _zfc(c)
                                dicts.append(d)
                            extra = getattr(executor, '_pick_extra', None) or {}
                            on_attach_picks.append({
                                "pick_id": pid,
                                "pick_type": extra.get("mode", "holomen"),
                                "title": ttl, "message": msg,
                                "min_pick": 1, "max_pick": 1,
                                "cards": dicts,
                            })
                            on_attach_refs[pid] = hl
                            return None

                        executor.pick_cards_cb = _cap_pick
                        executor.pick_holomen_cb = _cap_holomen
                        attach_result = {"actions_taken": []}
                        executor._fire_on_attach(entry, target_holomen, attach_result)
                        executor.pick_cards_cb = None
                        executor.pick_holomen_cb = None

                        if on_attach_picks:
                            pending["picks"].extend(on_attach_picks)
                            card_refs.update(on_attach_refs)

        elif pick_type == "holomen":
            # Generic holomen pick (swap, select target, etc.)
            if "swap" in title or "center" in title:
                if selected_cards:
                    target = selected_cards[0]
                    centre = player.playmat.zones[Zone.CENTRE]
                    back = player.playmat.zones[Zone.BACK]
                    if centre and target in back:
                        idx = back.index(target)
                        centre_card = centre[0]
                        centre[0] = target
                        back[idx] = centre_card
            else:
                # Default holomen pick — context-specific
                # On-attach: send stored yell to selected holomen
                if "on attach" in title.lower():
                    stored_yell = self.step_state.pop("_on_attach_yell", None)
                    if stored_yell and selected_cards:
                        target = selected_cards[0]
                        target.attached_yells.append(stored_yell)

        else:
            # pick_type == "cards" (default)
            # NOTE: check "deck bottom" BEFORE "hand" because titles like
            # "Hand → Deck Bottom" contain both keywords.
            if "deck bottom" in title:
                for card in selected_cards:
                    if card in player.playmat.zones[Zone.HAND]:
                        player.playmat.zones[Zone.HAND].remove(card)
                    card.face_up = False
                    player.playmat.zones[Zone.DECK].insert(0, card)

            elif "hand" in title or "手札" in title:
                for card in selected_cards:
                    for src in [Zone.DECK, Zone.ARCHIVE]:
                        if card in player.playmat.zones[src]:
                            player.playmat.zones[src].remove(card)
                            break
                    card.face_up = True
                    player.playmat.zones[Zone.HAND].append(card)

                rest = [c for c in available if c not in selected_cards]
                rest_to = pick_spec.get("rest_to", "deck_bottom")
                for card in rest:
                    if card in player.playmat.zones[Zone.HAND]:
                        continue
                    for src in [Zone.DECK, Zone.ARCHIVE]:
                        if card in player.playmat.zones[src]:
                            player.playmat.zones[src].remove(card)
                            break
                    card.face_up = False
                    if rest_to == "deck_top":
                        player.playmat.zones[Zone.DECK].append(card)
                    else:
                        player.playmat.zones[Zone.DECK].insert(0, card)

            elif "stage" in title or "ステージ" in title:
                for card in selected_cards:
                    if card in player.playmat.zones[Zone.DECK]:
                        player.playmat.zones[Zone.DECK].remove(card)
                    card.face_up = True
                    card.debut_this_turn = True
                    player.playmat.zones[Zone.BACK].append(card)

                rest = [c for c in available if c not in selected_cards]
                for card in rest:
                    if card in player.playmat.zones[Zone.DECK]:
                        player.playmat.zones[Zone.DECK].remove(card)
                        card.face_up = False
                        player.playmat.zones[Zone.DECK].insert(0, card)

            elif "archive" in title and "cost" in title:
                for card in selected_cards:
                    if card in player.playmat.zones[Zone.HAND]:
                        player.playmat.zones[Zone.HAND].remove(card)
                    card.face_up = True
                    player.playmat.zones[Zone.ARCHIVE].append(card)

            elif "yell deck" in title and "on attach" in title:
                # On-attach: pick yell from yell deck → store for next holomen pick
                yell_deck = player.playmat.zones[Zone.YELL_DECK]
                for card in selected_cards:
                    if card in yell_deck:
                        yell_deck.remove(card)
                    card.face_up = True
                # Restore face_down on remaining yell deck
                for y in yell_deck:
                    y.face_up = False
                player.playmat.shuffle_yell_deck()
                # Store selected yell for the next holomen pick
                if selected_cards:
                    self.step_state["_on_attach_yell"] = selected_cards[0]
                else:
                    # User skipped yell deck search — remove remaining on-attach picks
                    self.step_state["_on_attach_yell"] = None
                    pending["picks"] = [
                        p for p in pending["picks"]
                        if p["pick_id"] == pick_id or
                        "on attach" not in p.get("title", "").lower()
                    ]

            else:
                # Fallback: selected → hand
                for card in selected_cards:
                    for src in [Zone.DECK, Zone.ARCHIVE, Zone.YELL_DECK]:
                        if card in player.playmat.zones[src]:
                            player.playmat.zones[src].remove(card)
                            break
                    card.face_up = True
                    player.playmat.zones[Zone.HAND].append(card)

        # Shuffle deck after search-type picks
        if "search" in title or "サーチ" in title:
            player.playmat.shuffle_deck()

        # ── After resolving a "cards" pick, update following "reorder" pick ──
        if pick_type == "cards" and selected_cards:
            for p in pending["picks"]:
                if p.get("pick_type") == "reorder" and p["pick_id"] in card_refs:
                    # Remove selected cards from the reorder list
                    reorder_refs = card_refs[p["pick_id"]]
                    updated = [c for c in reorder_refs if c not in selected_cards]
                    card_refs[p["pick_id"]] = updated
                    # Re-serialize with face_up=True so client can see the cards
                    updated_dicts = []
                    for c in updated:
                        d = player.playmat._card_to_dict(c)
                        d["face_up"] = True
                        updated_dicts.append(d)
                    p["cards"] = updated_dicts

        # Remove this resolved pick
        pending["picks"] = [p for p in pending["picks"] if p["pick_id"] != pick_id]
        if pick_id in card_refs:
            del card_refs[pick_id]

        # ── Evaluate deferred conditionals on the next pending pick ──
        # If the next pick is tagged conditional, check whether the condition is met
        # based on the actual results of this resolved pick.
        if pending["picks"]:
            next_pick = pending["picks"][0]
            cond = next_pick.get("conditional")
            if cond:
                skip = False
                if "picked_count_eq" in cond:
                    actual = len(selected_cards) if selected_cards else 0
                    if actual != cond["picked_count_eq"]:
                        skip = True
                        print(f"  ℹ Conditional skip: picked_count_eq "
                              f"{cond['picked_count_eq']} but actual {actual}")
                if skip:
                    # Remove the conditional pick — condition not met
                    skipped_id = next_pick["pick_id"]
                    pending["picks"] = [
                        p for p in pending["picks"]
                        if p["pick_id"] != skipped_id
                    ]
                    if skipped_id in card_refs:
                        del card_refs[skipped_id]

        # If all picks resolved, clear pending state
        if not pending["picks"]:
            self.step_state.pop("pending_support", None)
            self.step_state.pop("_support_card_refs", None)

        sel_names = ", ".join(c.card_name for c in selected_cards) if selected_cards else "(ordered)" if pick_type == "reorder" else "(none)"
        self.events.append({
            "event": "support_pick_resolved",
            "pick_id": pick_id,
            "pick_type": pick_type,
            "selected": sel_names,
        })
        return {
            "success": True,
            "selected": [c.card_number for c in selected_cards],
            "remaining_picks": len(pending.get("picks", [])),
        }
