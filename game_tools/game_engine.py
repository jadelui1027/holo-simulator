from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import copy
import uuid
import random

from .playmat_manager import PlaymatManager, Zone
from .support_card_db import SupportCardExecutor, SUPPORT_CARD_DB
from .game_phases import GamePhasesMixin
from .game_actions import GameActionsMixin
from .pick_resolver import PickResolverMixin
from .game_state import GameStateMixin

@dataclass
class Player:
    id: str
    name: str
    playmat: PlaymatManager = field(default_factory=PlaymatManager)
    connection: Optional[object] = None
    deck_code: Optional[str] = None
    ready: bool = False
    dice_roll: Optional[int] = None
    support_executor: Optional[SupportCardExecutor] = field(default=None, repr=False)

    def __post_init__(self):
        if self.support_executor is None:
            self.support_executor = SupportCardExecutor(self.playmat)



class Match(GamePhasesMixin, GameActionsMixin, PickResolverMixin, GameStateMixin):
    """Server-authoritative match engine for two players.

    Game flow:
      1. Lobby – both players join & load decks
      2. Dice Roll – both roll; higher roller wins
      3. Choose Order – dice winner picks first or second
      4. Mulligan – both draw 7, mulligan if needed
      5. Setup – both place Debut holomen face-down on centre (+ optional back)
      6. Reveal – when both ready, all stage cards flip face-up
      7. Playing – turns cycle through 6 steps:
           Step 1  Reset     – collabo→back(rest), un-rest all, fill centre
           Step 2  Draw      – draw 1 card (deck empty → lose)
           Step 3  Cheer     – attach 1 yell to a stage holomen
           Step 4  Main      – place/bloom/collabo/support/baton-touch (free order)
           Step 5  Performance – use arts, knockouts trigger life deduction
           Step 6  End       – fill centre if empty, then pass turn
      8. Game Over – a player loses (no life / deck empty)
    """

    STEPS = ["reset", "draw", "cheer", "main", "performance", "end"]

    # Actions the turn player may perform in each step
    STEP_ACTIONS: Dict[str, set] = {
        "reset":       {"move_to_centre"},
        "draw":        set(),                                   # automatic
        "cheer":       {"attach_yell", "skip_cheer"},
        "main":        {"place_card", "play_card", "bloom", "collabo",
                        "force_collabo", "move", "toggle_rest",
                        "archive_card", "baton_touch", "end_main",
                        "draw", "peek_deck",
                        "attach_yell", "search_yell",
                        "play_support", "pick_support_cards",
                        "list_playable_supports",
                        "use_oshi_skill", "use_sp_oshi_skill",
                        "get_oshi_skill_info"},
        "performance": {"play_arts", "end_performance",
                        "use_oshi_skill", "use_sp_oshi_skill",
                        "get_oshi_skill_info"},
        "end":         {"move_to_centre", "end_turn"},
    }

    # Always allowed (info queries, pre-game, manual adjustments)
    ALWAYS_ALLOWED = {"get_zone_cards", "load_deck", "list_playable_supports",
                      "get_oshi_skill_info", "adjust_hp", "rollback",
                      "rewind_step", "retire"}

    # ── Constructor ─────────────────────────────────────────────────

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.players: Dict[str, Player] = {}

        # Game lifecycle
        self.game_state = "lobby"          # lobby | mulligan | dice_roll | choose_order | setup | playing | game_over
        self.turn_player_id: Optional[str] = None
        self.step_index = 0
        self.step_state: Dict[str, Any] = {}
        self.turn_number = 0

        # Win / lose
        self.winner: Optional[str] = None
        self.loser: Optional[str] = None
        self.lose_reason: str = ""

        # Pending interrupts
        self.pending_life_deduction: Optional[str] = None   # pid who must deduct
        self.pending_centre_fill: Optional[str] = None      # pid who must fill centre

        # Setup phase (pre-game holomen placement + mulligan)
        self.setup_state: Dict[str, Dict[str, Any]] = {}

        # First-turn tracking: skip reset on each player's very first turn
        self.players_first_turn_done: set = set()

        # Oshi skill tracking per player:
        #   {pid: {"oshi_skill_used_this_turn": bool, "sp_oshi_skill_used": bool}}
        self.oshi_skill_state: Dict[str, Dict[str, Any]] = {}

        # Event log (cleared each action, sent to clients)
        self.events: List[Dict[str, Any]] = []

        # Undo / rollback: store last snapshot
        self._snapshot: Optional[Dict[str, Any]] = None

    # ── Snapshot / Rollback ─────────────────────────────────────────

    def _take_snapshot(self):
        """Capture the full game state before an action for 1-step undo."""
        snap: Dict[str, Any] = {
            "game_state": self.game_state,
            "turn_player_id": self.turn_player_id,
            "step_index": self.step_index,
            "step_state": copy.deepcopy(self.step_state),
            "turn_number": self.turn_number,
            "winner": self.winner,
            "loser": self.loser,
            "lose_reason": self.lose_reason,
            "pending_life_deduction": self.pending_life_deduction,
            "pending_centre_fill": self.pending_centre_fill,
            "setup_state": copy.deepcopy(self.setup_state),
            "players_first_turn_done": set(self.players_first_turn_done),
            "oshi_skill_state": copy.deepcopy(self.oshi_skill_state),
            "players": {},
        }
        for pid, player in self.players.items():
            psnap = {
                "ready": player.ready,
                "dice_roll": player.dice_roll,
                "playmat": player.playmat.to_dict(),
                "executor": {
                    "_limited_used_this_turn": player.support_executor._limited_used_this_turn,
                    "_per_turn_trackers": dict(player.support_executor._per_turn_trackers),
                    "_game_trackers": dict(player.support_executor._game_trackers),
                    "_turn_modifiers": copy.deepcopy(player.support_executor._turn_modifiers),
                    "_prev_turn_own_downed": player.support_executor._prev_turn_own_downed,
                },
            }
            snap["players"][pid] = psnap
        self._snapshot = snap

    def _restore_snapshot(self):
        """Restore the game state from the last snapshot."""
        snap = self._snapshot
        if not snap:
            return False

        self.game_state = snap["game_state"]
        self.turn_player_id = snap["turn_player_id"]
        self.step_index = snap["step_index"]
        self.step_state = snap["step_state"]
        self.turn_number = snap["turn_number"]
        self.winner = snap["winner"]
        self.loser = snap["loser"]
        self.lose_reason = snap["lose_reason"]
        self.pending_life_deduction = snap["pending_life_deduction"]
        self.pending_centre_fill = snap["pending_centre_fill"]
        self.setup_state = snap["setup_state"]
        self.players_first_turn_done = snap["players_first_turn_done"]
        self.oshi_skill_state = snap["oshi_skill_state"]

        for pid, psnap in snap["players"].items():
            player = self.players[pid]
            player.ready = psnap["ready"]
            player.dice_roll = psnap["dice_roll"]
            # Restore playmat zones from serialized dict
            pm = player.playmat
            pm.clear_all()
            for zone_value, cards_data in psnap["playmat"].items():
                zone = Zone(zone_value)
                for cd in cards_data:
                    pm.zones[zone].append(pm._card_from_dict(cd))
            # Restore executor state
            ex = player.support_executor
            ex._limited_used_this_turn = psnap["executor"]["_limited_used_this_turn"]
            ex._per_turn_trackers = dict(psnap["executor"]["_per_turn_trackers"])
            ex._game_trackers = dict(psnap["executor"]["_game_trackers"])
            ex._turn_modifiers = psnap["executor"]["_turn_modifiers"]
            ex._prev_turn_own_downed = psnap["executor"]["_prev_turn_own_downed"]

        self._snapshot = None  # consumed
        return True

    # ── Lobby ───────────────────────────────────────────────────────

    def add_player(self, name: str) -> Player:
        pid = str(len(self.players) + 1)
        p = Player(id=pid, name=name)
        self.players[pid] = p
        return p

    def all_ready(self) -> bool:
        return len(self.players) == 2 and all(p.ready for p in self.players.values())

    def start_mulligan_phase(self):
        """Transition from choose_order → mulligan.
        Each player draws 7 cards. Mulligan / return cards here, no placement."""
        self.game_state = "mulligan"
        for pid, p in self.players.items():
            p.playmat.draw_card(7)
            has_debut = any(
                'ホロメン' in c.card_type and c.bloom_level == 'Debut'
                for c in p.playmat.zones[Zone.HAND]
            )
            self.setup_state[pid] = {
                "hand_number": 1,      # current hand attempt (1-based)
                "returning": 0,        # cards that must be returned to bottom
                "returned": 0,         # cards already returned this mulligan
                "has_debut": has_debut,
                "centre_placed": False,
                "ready": False,
            }

    def start_setup_phase(self):
        """Transition to setup (placement) after choose_order.
        Both players place Debut holomen on centre/back."""
        self.game_state = "setup"
        for pid in self.players:
            ss = self.setup_state.get(pid, {})
            ss["centre_placed"] = False
            ss["ready"] = False
            self.setup_state[pid] = ss

    def start_dice_phase(self):
        """Transition from lobby → dice_roll after both decks loaded."""
        self.game_state = "dice_roll"
        for p in self.players.values():
            p.dice_roll = None

    # ── Properties / helpers ────────────────────────────────────────

    @property
    def current_step(self) -> str:
        return self.STEPS[self.step_index]

    @property
    def started(self) -> bool:
        return self.game_state in ("playing", "game_over")

    def _opponent_id(self, pid: str) -> Optional[str]:
        for k in self.players:
            if k != pid:
                return k
        return None

    # ── Dice Roll / Choose Order ────────────────────────────────────

    def _handle_dice_roll(self, player_id: str) -> Dict[str, Any]:
        player = self.players[player_id]
        if player.dice_roll is not None:
            return {"success": False, "reason": "already rolled"}

        roll = random.randint(1, 6)
        player.dice_roll = roll
        self.events.append({"event": "dice_roll", "player_id": player_id,
                            "player_name": player.name, "roll": roll})

        all_rolled = all(p.dice_roll is not None for p in self.players.values())
        if all_rolled:
            rolls = {pid: p.dice_roll for pid, p in self.players.items()}
            pids = list(self.players.keys())
            if rolls[pids[0]] == rolls[pids[1]]:
                for p in self.players.values():
                    p.dice_roll = None
                self.events.append({"event": "dice_tie", "rolls": rolls})
                return {"success": True, "roll": roll, "tie": True}

            winner_id = pids[0] if rolls[pids[0]] > rolls[pids[1]] else pids[1]
            self.game_state = "dice_result"
            self.step_state = {"chooser": winner_id}
            self.events.append({"event": "dice_winner", "winner_id": winner_id,
                                "rolls": rolls})
        return {"success": True, "roll": roll}

    def _handle_choose_order(self, player_id: str, choice: str) -> Dict[str, Any]:
        chooser = self.step_state.get("chooser")
        if player_id != chooser:
            return {"success": False, "reason": "not your choice"}
        if choice not in ("first", "second"):
            return {"success": False, "reason": "choose 'first' or 'second'"}

        self.turn_player_id = player_id if choice == "first" else self._opponent_id(player_id)
        self.step_state = {}
        self.events.append({
            "event": "order_chosen",
            "first_player": self.turn_player_id,
            "first_player_name": self.players[self.turn_player_id].name,
        })

        # Go to mulligan phase (draw 7, mulligan)
        self.start_mulligan_phase()
        return {"success": True}

    # ── Step Management ─────────────────────────────────────────────

    def _enter_step(self):
        """Called on entering a new step. Runs auto-actions."""
        step = self.current_step
        player = self.players[self.turn_player_id]
        self.events.append({
            "event": "step_enter",
            "step": step,
            "step_index": self.step_index,
            "player_id": self.turn_player_id,
        })

        if step == "reset":
            self._auto_reset(player)
        elif step == "draw":
            self._auto_draw(player)
        elif step == "cheer":
            self._check_cheer(player)
        elif step == "main":
            self.step_state = {}          # free-form, no special state
        elif step == "performance":
            self.step_state = {}
        elif step == "end":
            self._check_end(player)

    # ── Auto-actions per step ───────────────────────────────────────

    def _auto_reset(self, player: Player):
        """Step 1: un-rest all, then collabo→back(rest), check centre.
        Skipped entirely on each player's very first turn."""
        pid = player.id

        # First turn: skip reset (no collabo to move, no resting holomen)
        if pid not in self.players_first_turn_done:
            self.players_first_turn_done.add(pid)
            self.events.append({"event": "first_turn_skip_reset", "player_id": pid})
            self._advance_step()
            return

        # 1. All resting holomen → active  (BEFORE moving collabo)
        for zone in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
            for c in player.playmat.zones[zone]:
                c.resting = False

        # 2. Collabo → back (resting)  (AFTER un-rest, so this card stays resting)
        collabo = player.playmat.zones[Zone.COLLABO]
        if collabo:
            card = collabo.pop()
            card.resting = True
            if len(player.playmat.zones[Zone.BACK]) < 5:
                player.playmat.zones[Zone.BACK].append(card)
                self.events.append({"event": "collabo_to_back", "card": card.card_name})
            else:
                collabo.append(card)     # back full — keep in collabo

        # 3. Centre check
        if not player.playmat.zones[Zone.CENTRE]:
            has_holomen = (
                bool(player.playmat.zones[Zone.BACK])
                or any("ホロメン" in c.card_type for c in player.playmat.zones[Zone.HAND])
            )
            if has_holomen:
                self.step_state = {"need_centre": True}
                self.events.append({"event": "need_centre", "reason": "centre_empty"})
            else:
                # No holomen anywhere to place — problematic, skip
                self.step_state = {"need_centre": True}
                self.events.append({"event": "need_centre", "reason": "no_holomen_available"})
        else:
            self._advance_step()

    def _auto_draw(self, player: Player):
        """Step 2: draw 1 card. Empty deck → lose."""
        if not player.playmat.zones[Zone.DECK]:
            self._set_game_over(player.id, "deck_empty")
            return
        drawn = player.playmat.draw_card(1)
        if drawn:
            self.events.append({"event": "drew_card", "card": drawn[0].card_name})
        self._advance_step()

    def _check_cheer(self, player: Player):
        """Step 3: if yell deck empty, auto-skip."""
        if not player.playmat.zones[Zone.YELL_DECK]:
            self.events.append({"event": "cheer_skip", "reason": "yell_deck_empty"})
            self._advance_step()
        else:
            self.step_state = {"cheer_done": False}

    def _check_end(self, player: Player):
        """Step 6: if centre empty, require fill; else pass turn."""
        if not player.playmat.zones[Zone.CENTRE]:
            has_back = bool(player.playmat.zones[Zone.BACK])
            has_hand = any("ホロメン" in c.card_type for c in player.playmat.zones[Zone.HAND])
            if has_back or has_hand:
                self.step_state = {"need_centre": True}
                self.events.append({"event": "need_centre", "reason": "end_step"})
            else:
                self._pass_turn()
        else:
            self._pass_turn()

    def _advance_step(self):
        """Move to the next step within the current turn."""
        self.step_index += 1
        self.step_state = {}
        if self.step_index >= len(self.STEPS):
            self._pass_turn()
            return
        self._enter_step()

    def _pass_turn(self):
        """Hand the turn to the opponent."""
        # Clear debut_this_turn markers for the current turn player
        old_player = self.players.get(self.turn_player_id)
        if old_player:
            for zone in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
                for c in old_player.playmat.zones[zone]:
                    c.debut_this_turn = False
        self.turn_player_id = self._opponent_id(self.turn_player_id)
        self.turn_number += 1
        self.step_index = 0
        self.step_state = {}
        # Reset support card executor for the new turn player
        turn_player = self.players.get(self.turn_player_id)
        if turn_player and turn_player.support_executor:
            turn_player.support_executor.start_turn()
        # Reset per-turn oshi skill usage for the new turn player
        tp_id = self.turn_player_id
        if tp_id in self.oshi_skill_state:
            self.oshi_skill_state[tp_id]["oshi_skill_used_this_turn"] = False
        self.events.append({
            "event": "turn_change",
            "new_turn_player": self.turn_player_id,
            "turn_number": self.turn_number,
        })
        self._enter_step()

    def _set_game_over(self, loser_id: str, reason: str):
        self.game_state = "game_over"
        self.loser = loser_id
        self.winner = self._opponent_id(loser_id)
        self.lose_reason = reason
        self.events.append({
            "event": "game_over",
            "winner": self.winner,
            "loser": self.loser,
            "reason": reason,
        })

    # ── Action validation ───────────────────────────────────────────

    def _validate_action(self, player_id: str, typ: str) -> Optional[str]:
        """Return an error string if the action is disallowed, else None."""
        if typ in self.ALWAYS_ALLOWED:
            return None
        if self.game_state == "game_over":
            return "game is over"
        if self.game_state != "playing":
            return f"game not in playing state ({self.game_state})"

        # Oshi skills can be used as interrupts (during life deduction, damage, etc.)
        OSHI_ACTIONS = {"use_oshi_skill", "use_sp_oshi_skill", "get_oshi_skill_info"}

        # Pending life deduction takes priority — but allow oshi skills as interrupt
        if self.pending_life_deduction:
            if typ in OSHI_ACTIONS:
                return None  # oshi skills allowed during life deduction
            if player_id == self.pending_life_deduction:
                if typ in ("deduct_life", "end_deduct_life"):
                    return None
                return "must deduct life first"
            return "waiting for opponent to deduct life"

        # Pending support card picks
        pending_support = self.step_state.get("pending_support")
        if pending_support and pending_support.get("picks"):
            if typ in OSHI_ACTIONS:
                return None  # oshi skills allowed during pending picks
            if player_id == pending_support["player_id"]:
                if typ == "pick_support_cards":
                    return None
                return "must resolve support card picks first"
            return "waiting for turn player to resolve support card picks"

        # Pending centre fill (opponent's holomen knocked out)
        if self.pending_centre_fill:
            if typ in OSHI_ACTIONS:
                return None  # oshi skills allowed during centre fill
            if player_id == self.pending_centre_fill:
                if typ in ("move_to_centre", "place_card"):
                    return None
                return "must fill centre position first"
            return "waiting for opponent to fill centre"

        # Oshi skills allowed for turn player at main/performance
        if typ in OSHI_ACTIONS:
            if player_id == self.turn_player_id:
                return None
            return "not your turn"

        # Normal: only turn player
        if player_id != self.turn_player_id:
            return "not your turn"

        step = self.current_step
        allowed = self.STEP_ACTIONS.get(step, set())
        if typ not in allowed:
            return f"action '{typ}' not allowed in step '{step}'"
        return None

    # ── Main dispatch ───────────────────────────────────────────────

    def apply_action(self, player_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        player = self.players.get(player_id)
        if player is None:
            return {"success": False, "reason": "player not in match"}

        typ = action.get("type")
        self.events = []

        # ── Rollback / Rewind / Retire (always allowed, no snapshot needed) ──
        if typ == "rollback":
            return self._handle_rollback(player_id)
        if typ == "rewind_step":
            return self._handle_rewind_step(player_id, action)
        if typ == "retire":
            return self._handle_retire(player_id)

        # ── Read-only / info queries (no snapshot) ──
        if typ in ("get_zone_cards", "list_playable_supports", "get_oshi_skill_info"):
            if typ == "get_zone_cards":
                return self._handle_get_zone_cards(player, action)
            if typ == "list_playable_supports":
                return self._handle_list_supports(player)
            return self._handle_get_oshi_skill_info(player_id, player)

        # ── Take snapshot before any mutating action ──
        if self.game_state not in ("lobby",):
            self._take_snapshot()

        # ── Pre-game: load deck ──
        if typ == "load_deck":
            return self._handle_load_deck(player, action)

        # ── Mulligan phase actions (both players act simultaneously) ──
        if self.game_state == "mulligan":
            if typ == "setup_mulligan":
                return self._handle_setup_mulligan(player_id, player)
            if typ == "setup_return_card":
                return self._handle_setup_return_card(player_id, player, action)
            if typ == "mulligan_ready":
                return self._handle_mulligan_ready(player_id, player)
            return {"success": False, "reason": "invalid action during mulligan"}

        # ── Setup phase actions (placement, both players act simultaneously) ──
        if self.game_state == "setup":
            if typ == "setup_place":
                return self._handle_setup_place(player_id, player, action)
            if typ == "setup_return_to_hand":
                return self._handle_setup_return_to_hand(player_id, player, action)
            if typ == "setup_ready":
                return self._handle_setup_ready(player_id, player)
            return {"success": False, "reason": "invalid action during setup"}

        # ── Dice roll ──
        if typ == "roll_dice":
            if self.game_state != "dice_roll":
                return {"success": False, "reason": "not in dice roll phase"}
            return self._handle_dice_roll(player_id)

        # ── Choose order ──
        if typ == "choose_order":
            if self.game_state != "choose_order":
                return {"success": False, "reason": "not in choose order phase"}
            return self._handle_choose_order(player_id, action.get("choice", ""))

        # ── Manual HP adjust (always allowed) ──
        if typ == "adjust_hp":
            return self._handle_adjust_hp(player_id, action)

        # ── Validate for current phase ──
        error = self._validate_action(player_id, typ)
        if error:
            return {"success": False, "reason": error}

        # ── Dispatch ──
        return self._dispatch_playing(player_id, player, action)

    # ── dispatch for playing state ──────────────────────────────────

    def _dispatch_playing(self, player_id: str, player: Player,
                          action: Dict[str, Any]) -> Dict[str, Any]:
        typ = action.get("type")

        # Step-flow controls
        if typ == "skip_cheer":
            self.events.append({"event": "cheer_skipped"})
            self._advance_step()
            return {"success": True}

        if typ == "end_main":
            self._advance_step()
            return {"success": True}

        if typ == "end_performance":
            self._advance_step()
            return {"success": True}

        if typ == "end_turn":
            if self.current_step == "end":
                self._pass_turn()
                return {"success": True}
            return {"success": False, "reason": "can only end turn in end step"}

        if typ == "move_to_centre":
            return self._handle_move_to_centre(player_id, player, action)

        # Standard game actions
        if typ == "draw":
            cnt = int(action.get("count", 1))
            drawn = player.playmat.draw_card(cnt)
            return {"success": True, "drawn": [c.card_number for c in drawn]}

        if typ == "shuffle_deck":
            player.playmat.shuffle_deck()
            return {"success": True}

        if typ == "play_card":
            return self._handle_play_card(player_id, player, action)

        if typ == "place_card":
            return self._handle_place_card(player, action)

        if typ == "move":
            return self._handle_move(player, action)

        if typ == "attach_yell":
            result = self._handle_attach_yell(player, action)
            if result.get("success") and self.current_step == "cheer":
                self._advance_step()
            return result

        if typ == "search_yell":
            return self._handle_search_yell(player, action)

        if typ == "toggle_rest":
            return self._handle_toggle_rest(player, action)

        if typ == "bloom":
            return self._handle_bloom(player, action)

        if typ == "collabo":
            return self._handle_collabo(player, action)

        if typ == "force_collabo":
            return self._handle_force_collabo(player, action)

        if typ == "deduct_life":
            return self._handle_deduct_life(player_id, player, action)

        if typ == "end_deduct_life":
            return self._handle_end_deduct_life(player_id, player)

        if typ == "archive_card":
            return self._handle_archive_card(player, action)

        if typ == "shuffle_yell":
            player.playmat.shuffle_yell_deck()
            return {"success": True}

        if typ == "hand_to_deck":
            return self._handle_hand_to_deck(player)

        if typ == "peek_deck":
            return self._handle_peek_deck(player, action)

        if typ == "play_arts":
            return self._handle_play_arts(player_id, player, action)

        if typ == "baton_touch":
            return self._handle_baton_touch(player, action)

        if typ == "reset_step":
            return self._handle_manual_reset_step(player)

        if typ == "play_support":
            return self._handle_play_support(player_id, player, action)

        if typ == "pick_support_cards":
            return self._handle_pick_support_cards(player_id, player, action)

        if typ == "list_playable_supports":
            return self._handle_list_supports(player)

        if typ == "use_oshi_skill":
            return self._handle_use_oshi_skill(player_id, player, action)

        if typ == "use_sp_oshi_skill":
            return self._handle_use_sp_oshi_skill(player_id, player, action)

        if typ == "get_oshi_skill_info":
            return self._handle_get_oshi_skill_info(player_id, player)

        return {"success": False, "reason": "unknown action"}

    # ── Manual HP adjustment ───────────────────────────────────────

    def _handle_adjust_hp(self, player_id: str,
                          action: Dict[str, Any]) -> Dict[str, Any]:
        """Manually adjust damage on any stage holomen.

        action keys:
          target_player: 'self' | 'opponent'
          zone: 'centre' | 'collabo' | 'back'
          card_index: int
          delta: int  (positive = deal damage, negative = heal)
        """
        from game_tools.playmat_manager import Zone

        target = action.get("target_player", "opponent")
        if target == "self":
            pid = player_id
        else:
            pid = self._opponent_id(player_id)
        if not pid or pid not in self.players:
            return {"success": False, "reason": "target player not found"}

        target_player = self.players[pid]
        pm = target_player.playmat
        zname = action.get("zone", "")
        zone_map = {"centre": Zone.CENTRE, "collabo": Zone.COLLABO, "back": Zone.BACK}
        zone = zone_map.get(zname)
        if not zone:
            return {"success": False, "reason": f"invalid zone: {zname}"}

        idx = int(action.get("card_index", 0))
        cards = pm.zones[zone]
        if idx < 0 or idx >= len(cards):
            return {"success": False, "reason": "card index out of range"}

        card = cards[idx]
        delta = int(action.get("delta", 0))
        if delta == 0:
            return {"success": False, "reason": "delta is zero"}

        old_damage = card.damage
        card.damage = max(0, card.damage + delta)
        new_damage = card.damage

        # Check effective HP (including support bonuses)
        effective_hp = getattr(card, 'hp', 0)
        if hasattr(target_player, 'support_executor') and target_player.support_executor:
            effective_hp = target_player.support_executor.get_effective_hp(card)

        knocked_out = effective_hp > 0 and new_damage >= effective_hp

        desc = f"+{delta} dmg" if delta > 0 else f"{delta} dmg (heal)"
        self.events.append({
            "event": "hp_adjusted",
            "card_name": card.card_name,
            "zone": zname,
            "delta": delta,
            "old_damage": old_damage,
            "new_damage": new_damage,
            "knocked_out": knocked_out,
        })

        result = {
            "success": True,
            "card_name": card.card_name,
            "old_damage": old_damage,
            "new_damage": new_damage,
            "knocked_out": knocked_out,
            "description": f"{card.card_name}: {desc} (damage {old_damage} → {new_damage})",
        }

        if knocked_out:
            archive = pm.zones[Zone.ARCHIVE]

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

            ko_card = cards.pop(idx)
            _archive_flat(ko_card)

            self.events.append({
                "event": "knockout",
                "card": card.card_name,
                "opponent_id": pid,
            })

            # Target player must deduct life
            opp_life = pm.zones[Zone.LIFE]
            if not opp_life:
                self._set_game_over(pid, "no_life")
            else:
                self.pending_life_deduction = pid
                result["pending_life_deduction"] = True

        return result

    # ── Rollback handler ───────────────────────────────────────────

    def _handle_rollback(self, player_id: str) -> Dict[str, Any]:
        """Undo the previous action by restoring the saved snapshot."""
        if not self._snapshot:
            print(f"[ROLLBACK] No snapshot available for player {player_id}")
            return {"success": False, "reason": "nothing to undo"}

        try:
            prev_step = self._snapshot.get("step_index", "?")
            ok = self._restore_snapshot()
            if not ok:
                return {"success": False, "reason": "rollback failed"}

            cur_step = self.current_step
            print(f"[ROLLBACK] Player {player_id} rolled back to step {cur_step} (index {prev_step})")
            self.events.append({"event": "rollback", "player_id": player_id,
                                "step": cur_step})
            return {"success": True, "description": f"Rolled back to {cur_step} step"}
        except Exception as e:
            print(f"[ROLLBACK] Error: {e}")
            import traceback; traceback.print_exc()
            return {"success": False, "reason": f"rollback error: {e}"}

    # ── Retire handler ──────────────────────────────────────────────

    def _handle_retire(self, player_id: str) -> Dict[str, Any]:
        """Player concedes the match."""
        if self.game_state == "game_over":
            return {"success": False, "reason": "game already over"}
        if self.game_state == "lobby":
            return {"success": False, "reason": "game not started"}
        self._set_game_over(player_id, "retired")
        print(f"[RETIRE] Player {player_id} retired")
        return {"success": True, "description": "You retired from the match"}

    # ── Rewind step handler ────────────────────────────────────────

    def _handle_rewind_step(self, player_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Go back to a previous step without full state rollback."""
        if self.game_state != "playing":
            return {"success": False, "reason": "not in playing state"}
        if player_id != self.turn_player_id:
            return {"success": False, "reason": "not your turn"}

        target = action.get("target_step")
        if target:
            # Go to a specific step by name
            if target not in self.STEPS:
                return {"success": False, "reason": f"unknown step '{target}'"}
            target_idx = self.STEPS.index(target)
        else:
            # Default: go back one step
            target_idx = self.step_index - 1

        if target_idx < 0:
            return {"success": False, "reason": "already at first step"}
        if target_idx >= self.step_index:
            return {"success": False, "reason": "can only rewind to earlier steps"}

        old_step = self.current_step
        self.step_index = target_idx
        new_step = self.current_step
        self.step_state = {}  # clear step-specific state
        print(f"[REWIND] Player {player_id}: {old_step} -> {new_step}")
        self.events.append({"event": "rewind_step", "player_id": player_id,
                            "from_step": old_step, "to_step": new_step})
        return {"success": True, "description": f"Rewound from {old_step} to {new_step}"}
