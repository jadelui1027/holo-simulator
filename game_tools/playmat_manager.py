#!/usr/bin/env python3
"""
hOCG Playmat Manager
====================
Manages the 9 zones on the hololive Official Card Game playmat.
Supports card placement/removal/movement, image rendering, and interactive GUI.

Zones (detected from playmat_with_marking.jpg):
  1. Life           - Top-left (tall)       - Face-down life cards
  2. Holo Power     - Top-right (small)     - Spent holo power cards
  3. Collabo        - Upper-mid-left        - Collab holomen position
  4. Centre         - Upper-mid-center      - Centre holomen position
  5. Oshi Holomen   - Upper-mid-right       - Your oshi holomen
  6. Deck           - Right-middle          - Main deck (face-down)
  7. Back           - Bottom-center (large) - Back position (max 4 cards)
  8. Yell Deck      - Bottom-left           - エールデッキ (cheer/yell deck)
  9. Archive        - Bottom-right          - Discarded cards

Usage:
  python3 game_tools/playmat.py              # Launch interactive GUI
  python3 game_tools/playmat.py --render     # Render current board as image
  python3 game_tools/playmat.py --demo       # Run demo with sample cards
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CARDS_DIR = os.path.join(PROJECT_DIR, "cards")
DB_PATH = os.path.join(PROJECT_DIR, "card_database.json")
PLAYMAT_IMG = os.path.join(SCRIPT_DIR, "playmat.jpg")
PLAYMAT_MARKED_IMG = os.path.join(SCRIPT_DIR, "playmat_with_marking.jpg")
CARD_BACK_IMG = os.path.join(SCRIPT_DIR, "card_back.webp")


class Zone(Enum):
    """The 9 playmat zones with their names and properties."""
    LIFE = "life"
    HOLO_POWER = "holo_power"
    COLLABO = "collabo"
    CENTRE = "centre"
    OSHI = "oshi"
    DECK = "deck"
    BACK = "back"
    YELL_DECK = "yell_deck"
    ARCHIVE = "archive"
    HAND = "hand"


@dataclass
class ZoneInfo:
    """Metadata for a playmat zone."""
    zone: Zone
    display_name: str
    display_name_jp: str
    # Bounding box on the 2040x1044 playmat image (x1, y1, x2, y2)
    bbox: tuple[int, int, int, int]
    max_cards: Optional[int] = None  # None = unlimited
    face_down: bool = False
    description: str = ""


# Zone definitions with bounding boxes detected from playmat_with_marking.jpg
ZONE_DEFINITIONS: dict[Zone, ZoneInfo] = {
    Zone.LIFE: ZoneInfo(
        zone=Zone.LIFE,
        display_name="Life",
        display_name_jp="ライフ",
        bbox=(59, 51, 361, 529),
        face_down=True,
        description="Face-down life cards. Lose one when your centre holomen takes a hit.",
    ),
    Zone.HOLO_POWER: ZoneInfo(
        zone=Zone.HOLO_POWER,
        display_name="Holo Power",
        display_name_jp="ホロパワー",
        bbox=(1678, 51, 1981, 266),
        description="Cards used as holo power for oshi skills.",
    ),
    Zone.COLLABO: ZoneInfo(
        zone=Zone.COLLABO,
        display_name="Collabo",
        display_name_jp="コラボ",
        bbox=(551, 121, 764, 422),
        max_cards=1,
        description="Collab holomen position on stage.",
    ),
    Zone.CENTRE: ZoneInfo(
        zone=Zone.CENTRE,
        display_name="Centre",
        display_name_jp="センター",
        bbox=(940, 121, 1153, 422),
        max_cards=1,
        description="Centre holomen position on stage.",
    ),
    Zone.OSHI: ZoneInfo(
        zone=Zone.OSHI,
        display_name="Oshi Holomen",
        display_name_jp="推しホロメン",
        bbox=(1345, 121, 1560, 422),
        max_cards=1,
        description="Your oshi holomen card.",
    ),
    Zone.DECK: ZoneInfo(
        zone=Zone.DECK,
        display_name="Deck",
        display_name_jp="デッキ",
        bbox=(1766, 335, 1981, 638),
        face_down=True,
        description="Main deck (face-down).",
    ),
    Zone.BACK: ZoneInfo(
        zone=Zone.BACK,
        display_name="Back",
        display_name_jp="バック",
        bbox=(455, 625, 1658, 1014),
        max_cards=5,
        description="Back stage positions (max 5 holomen).",
    ),
    Zone.YELL_DECK: ZoneInfo(
        zone=Zone.YELL_DECK,
        display_name="Yell Deck",
        display_name_jp="エールデッキ",
        bbox=(59, 687, 273, 988),
        face_down=True,
        description="Yell/Cheer deck for attaching yell cards.",
    ),
    Zone.ARCHIVE: ZoneInfo(
        zone=Zone.ARCHIVE,
        display_name="Archive",
        display_name_jp="アーカイブ",
        bbox=(1766, 687, 1981, 988),
        description="Discarded/archived cards.",
    ),
    Zone.HAND: ZoneInfo(
        zone=Zone.HAND,
        display_name="Hand",
        display_name_jp="手札",
        bbox=(59, 1060, 1981, 1280),
        max_cards=None,
        description="Cards in hand (face-up to player).",
    ),
}


@dataclass(eq=False)
class Card:
    """A card instance on the playmat."""
    card_number: str
    card_name: str
    card_type: str  # カードタイプ
    image_file: str  # local image filename in cards/
    face_up: bool = True
    bloom_level: str = ""  # Bloomレベル: Debut, 1st, 2nd, Spot
    resting: bool = False  # True = resting (horizontal), False = active (vertical)
    attached_yells: list = field(default_factory=list)  # yell cards attached to holomen
    attached_supports: list = field(default_factory=list)  # support cards attached (tool/mascot/fan)
    stacked_cards: list = field(default_factory=list)  # bloom stack (older cards underneath)
    damage: int = 0  # damage taken (for holomen)
    color: list = field(default_factory=list)  # card colors e.g. ['白','緑']
    hp: int = 0  # hit points (holomen only)
    arts: list = field(default_factory=list)  # arts list [{name, damage, エール, effect}]
    baton_touch: int = 0  # バトンタッチ cost (yells to archive for retreat)
    tags: list = field(default_factory=list)  # タグ e.g. ['#JP','#秘密結社holoX']
    debut_this_turn: bool = False  # True if this Debut was placed on stage this turn

    @property
    def image_path(self) -> str:
        return os.path.join(CARDS_DIR, self.image_file)

    def __repr__(self):
        face = "↑" if self.face_up else "↓"
        rest = " 💤" if self.resting else ""
        return f"Card({self.card_number} {self.card_name} {face}{rest})"


class PlaymatManager:
    """
    Manages the state of a hOCG playmat with 9 zones.
    Handles card placement, removal, movement, and rendering.
    """

    def __init__(self):
        self.zones: dict[Zone, list[Card]] = {zone: [] for zone in Zone}
        self._card_db: Optional[list[dict]] = None
        self._card_index: Optional[dict[str, dict]] = None

    # ── Card Database ────────────────────────────────────────────────

    def _load_db(self):
        """Lazy-load the card database."""
        if self._card_db is not None:
            return
        if not os.path.exists(DB_PATH):
            raise FileNotFoundError(f"Card database not found: {DB_PATH}")
        with open(DB_PATH, "r", encoding="utf-8") as f:
            self._card_db = json.load(f)
        # Build index by card_number
        self._card_index = {}
        for card_data in self._card_db:
            num = card_data.get("card_number", "")
            if num and num not in self._card_index:
                self._card_index[num] = card_data

    # ── Deck Loading from Decklog ────────────────────────────────────

    def load_deck_from_decklog(self, deck_code: str, deck_site: str = "jp") -> int:
        """
        Load a deck from decklog.bushiroad.com using its deck code.
        Populates OSHI, DECK, and YELL_DECK zones.
        Returns total number of cards loaded.
        """
        import urllib.request
        self._load_db()
        self.clear_all()
        # Support JP and Global decklog
        if deck_site == "global":
            url = f"https://decklog-en.bushiroad.com/system/app-ja/api/view/{deck_code}"
            headers = {
                "Referer": f"https://decklog-en.bushiroad.com/ja/view/{deck_code}",
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
        else:
            url = f"https://decklog.bushiroad.com/system/app/api/view/{deck_code}"
            headers = {
                "Referer": f"https://decklog.bushiroad.com/view/{deck_code}",
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
        req = urllib.request.Request(url, method="POST", headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        loaded = 0
        # Oshi (p_list)
        for item in data.get("p_list", []):
            cn = item.get("card_number", "")
            img_hint = item.get("img", "")
            for _ in range(int(item.get("num", 1))):
                try:
                    self.place_card_by_number(Zone.OSHI, cn, face_up=True,
                                             preferred_image=img_hint)
                    loaded += 1
                except ValueError:
                    print(f"⚠ Oshi card not found in DB: {cn}")

        # Main deck (list)
        for item in data.get("list", []):
            cn = item.get("card_number", "")
            img_hint = item.get("img", "")
            for _ in range(int(item.get("num", 1))):
                try:
                    self.place_card_by_number(Zone.DECK, cn, face_up=False,
                                             preferred_image=img_hint)
                    loaded += 1
                except ValueError:
                    print(f"⚠ Deck card not found in DB: {cn}")

        # Yell deck (sub_list)
        for item in data.get("sub_list", []):
            cn = item.get("card_number", "")
            img_hint = item.get("img", "")
            for _ in range(int(item.get("num", 1))):
                try:
                    self.place_card_by_number(Zone.YELL_DECK, cn, face_up=False,
                                             preferred_image=img_hint)
                    loaded += 1
                except ValueError:
                    print(f"⚠ Yell card not found in DB: {cn}")

        deck_title = data.get('title', '')
        if deck_title:
            print(f"📋 Deck: {deck_title}")
        print(f"✓ Loaded {loaded} card(s) from deck code {deck_code}")

        # Auto-setup: shuffle and move life cards
        self.setup_initial_board()
        return loaded

    def lookup_card(self, card_number: str) -> Optional[dict]:
        """Look up a card by its number (e.g., 'hSD01-001')."""
        self._load_db()
        return self._card_index.get(card_number)

    def create_card(self, card_number: str, preferred_image: str = "") -> Card:
        """Create a Card instance from a card number.
        If preferred_image is given (e.g. from decklog), prefer that variant."""
        data = self.lookup_card(card_number)
        if data is None:
            raise ValueError(f"Card not found: {card_number}")
        images = data.get("local_images", [])
        image_file = images[0] if images else ""
        # If a preferred image variant is specified, try to match it
        if preferred_image:
            # Extract basename from path like "hPR/hBP01-004_P.png"
            import os as _os
            pref_base = _os.path.basename(preferred_image)
            for img in images:
                if img == pref_base:
                    image_file = img
                    break
        return Card(
            card_number=data.get("card_number", card_number),
            card_name=data.get("card_name", "Unknown"),
            card_type=data.get("カードタイプ", ""),
            image_file=image_file,
            bloom_level=data.get("Bloomレベル", ""),
            color=data.get("色", []),
            hp=int(data.get("HP", 0) or 0),
            arts=data.get("arts", []),
            baton_touch=int(data.get("バトンタッチ", 0) or 0),
            tags=data.get("タグ", []),
        )

    # ── Initial Board Setup / Game Actions ────────────────────────────

    def setup_initial_board(self):
        """Shuffle decks, then move top X yell-deck cards to Life zone (face-down)."""
        oshi_cards = self.zones[Zone.OSHI]
        if not oshi_cards:
            print("⚠ No Oshi card placed — skipping life setup.")
            return

        self._load_db()
        oshi_cn = oshi_cards[0].card_number
        oshi_data = self._card_index.get(oshi_cn, {})
        life_count = oshi_data.get("LIFE", 0)
        if not life_count:
            print(f"⚠ Oshi {oshi_cn} has no LIFE stat — skipping life setup.")
            return

        self.clear_zone(Zone.LIFE)
        self.shuffle_deck()
        self.shuffle_yell_deck()

        moved = 0
        for _ in range(life_count):
            if not self.zones[Zone.YELL_DECK]:
                break
            card = self.zones[Zone.YELL_DECK].pop()
            card.face_up = False
            self.zones[Zone.LIFE].append(card)
            moved += 1

        print(f"✓ Placed {moved} card(s) from Yell Deck into Life zone "
              f"(Oshi LIFE = {life_count})")

    def draw_card(self, count: int = 1) -> list[Card]:
        """Draw card(s) from top of Deck into Hand (face-up)."""
        drawn: list[Card] = []
        for _ in range(count):
            if not self.zones[Zone.DECK]:
                print("⚠ Deck is empty — cannot draw.")
                break
            card = self.zones[Zone.DECK].pop()
            card.face_up = True
            self.zones[Zone.HAND].append(card)
            drawn.append(card)
        if drawn:
            names = ", ".join(c.card_name for c in drawn)
            print(f"✓ Drew {len(drawn)} card(s): {names}")
        return drawn

    def shuffle_deck(self):
        """Shuffle the main Deck."""
        import random
        random.shuffle(self.zones[Zone.DECK])
        print(f"✓ Shuffled Deck ({len(self.zones[Zone.DECK])} cards)")

    def shuffle_yell_deck(self):
        """Shuffle the Yell Deck."""
        import random
        random.shuffle(self.zones[Zone.YELL_DECK])
        print(f"✓ Shuffled Yell Deck ({len(self.zones[Zone.YELL_DECK])} cards)")

    # ── Zone Operations ──────────────────────────────────────────────

    def get_zone_info(self, zone: Zone) -> ZoneInfo:
        """Get metadata for a zone."""
        return ZONE_DEFINITIONS[zone]

    def get_cards(self, zone: Zone) -> list[Card]:
        """Get all cards in a zone."""
        return list(self.zones[zone])

    def card_count(self, zone: Zone) -> int:
        """Get the number of cards in a zone."""
        return len(self.zones[zone])

    def place_card(self, zone: Zone, card: Card, face_up: Optional[bool] = None) -> bool:
        """
        Place a card into a zone.
        Returns True if successful, False if zone is full.
        """
        info = ZONE_DEFINITIONS[zone]

        # Check capacity
        if info.max_cards is not None and len(self.zones[zone]) >= info.max_cards:
            print(f"✗ Cannot place in {info.display_name}: "
                  f"zone is full ({info.max_cards}/{info.max_cards})")
            return False

        # Set face orientation
        if face_up is not None:
            card.face_up = face_up
        elif info.face_down:
            card.face_up = False

        self.zones[zone].append(card)
        face_str = "face-up" if card.face_up else "face-down"
        print(f"✓ Placed {card.card_name} ({card.card_number}) "
              f"in {info.display_name} [{face_str}]")
        return True

    def place_card_by_number(self, zone: Zone, card_number: str,
                             face_up: Optional[bool] = None,
                             preferred_image: str = "") -> bool:
        """Create and place a card by its card number."""
        card = self.create_card(card_number, preferred_image=preferred_image)
        return self.place_card(zone, card, face_up)

    def remove_card(self, zone: Zone, index: int = -1) -> Optional[Card]:
        """
        Remove a card from a zone by index (default: last/top card).
        Returns the removed card, or None if zone is empty.
        """
        if not self.zones[zone]:
            print(f"✗ {ZONE_DEFINITIONS[zone].display_name} is empty")
            return None
        card = self.zones[zone].pop(index)
        print(f"✓ Removed {card.card_name} ({card.card_number}) "
              f"from {ZONE_DEFINITIONS[zone].display_name}")
        return card

    def move_card(self, from_zone: Zone, to_zone: Zone,
                  index: int = -1, face_up: Optional[bool] = None) -> bool:
        """
        Move a card from one zone to another.
        Returns True if successful.
        """
        card = self.remove_card(from_zone, index)
        if card is None:
            return False
        success = self.place_card(to_zone, card, face_up)
        if not success:
            # Put the card back if placement failed
            self.zones[from_zone].insert(
                index if index >= 0 else len(self.zones[from_zone]), card
            )
            print(f"↩ Returned {card.card_name} to {ZONE_DEFINITIONS[from_zone].display_name}")
        return success

    def clear_zone(self, zone: Zone) -> list[Card]:
        """Remove all cards from a zone. Returns the removed cards."""
        cards = self.zones[zone][:]
        self.zones[zone].clear()
        if cards:
            print(f"✓ Cleared {len(cards)} card(s) from {ZONE_DEFINITIONS[zone].display_name}")
        return cards

    def clear_all(self):
        """Remove all cards from all zones."""
        for zone in Zone:
            self.zones[zone].clear()
        print("✓ Cleared all zones")

    def attach_yell(self, zone: Zone, card_index: int, yell_card: Card):
        """Attach a yell card to a holomen in a zone."""
        if not self.zones[zone]:
            print(f"✗ No cards in {ZONE_DEFINITIONS[zone].display_name}")
            return
        target = self.zones[zone][card_index]
        target.attached_yells.append(yell_card)
        print(f"✓ Attached yell {yell_card.card_name} to {target.card_name}")

    # ── Board State ──────────────────────────────────────────────────

    def print_board(self):
        """Print a text representation of the board state."""
        print("\n" + "=" * 60)
        print("  hOCG Playmat Board State")
        print("=" * 60)
        for zone in Zone:
            info = ZONE_DEFINITIONS[zone]
            cards = self.zones[zone]
            cap = f"/{info.max_cards}" if info.max_cards else ""
            print(f"\n  [{info.display_name}] ({info.display_name_jp}) "
                  f"— {len(cards)}{cap} cards")
            if not cards:
                print("    (empty)")
            else:
                for i, card in enumerate(cards):
                    face = "↑" if card.face_up else "↓"
                    rest = " 💤" if card.resting else ""
                    yells = f" +{len(card.attached_yells)} yell(s)" if card.attached_yells else ""
                    stack = f" [bloom stack: {len(card.stacked_cards)}]" if card.stacked_cards else ""
                    print(f"    {i}: {face}{rest} {card.card_number} {card.card_name}"
                          f" [{card.card_type}]{yells}{stack}")
        print("\n" + "=" * 60)

    def _card_to_dict(self, card: Card) -> dict:
        """Serialize a single card to dict (recursive for stacks/yells)."""
        return {
            "card_number": card.card_number,
            "card_name": card.card_name,
            "card_type": card.card_type,
            "image_file": card.image_file,
            "face_up": card.face_up,
            "bloom_level": card.bloom_level,
            "resting": card.resting,
            "damage": card.damage,
            "color": card.color,
            "hp": card.hp,
            "arts": card.arts,
            "attached_yells": [self._card_to_dict(y) for y in card.attached_yells],
            "attached_supports": [self._card_to_dict(s) for s in card.attached_supports],
            "stacked_cards": [self._card_to_dict(s) for s in card.stacked_cards],
            "debut_this_turn": card.debut_this_turn,
        }

    def _card_from_dict(self, cd: dict) -> Card:
        """Deserialize a single card from dict (recursive for stacks/yells)."""
        card = Card(
            card_number=cd["card_number"],
            card_name=cd["card_name"],
            card_type=cd.get("card_type", ""),
            image_file=cd["image_file"],
            face_up=cd.get("face_up", True),
            bloom_level=cd.get("bloom_level", ""),
            resting=cd.get("resting", False),
            damage=cd.get("damage", 0),
            color=cd.get("color", []),
            hp=cd.get("hp", 0),
            arts=cd.get("arts", []),
            debut_this_turn=cd.get("debut_this_turn", False),
        )
        for yd in cd.get("attached_yells", []):
            card.attached_yells.append(self._card_from_dict(yd))
        for sd in cd.get("attached_supports", []):
            card.attached_supports.append(self._card_from_dict(sd))
        for sd in cd.get("stacked_cards", []):
            card.stacked_cards.append(self._card_from_dict(sd))
        return card

    def to_dict(self) -> dict:
        """Serialize the board state to a dictionary."""
        state = {}
        for zone in Zone:
            state[zone.value] = [self._card_to_dict(c) for c in self.zones[zone]]
        return state

    def save_state(self, filepath: str):
        """Save the board state to a JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"✓ Board state saved to {filepath}")

    def load_state(self, filepath: str):
        """Load a board state from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.clear_all()
        for zone_value, cards_data in state.items():
            zone = Zone(zone_value)
            for cd in cards_data:
                self.zones[zone].append(self._card_from_dict(cd))
        print(f"✓ Board state loaded from {filepath}")

    # ── Rendering ────────────────────────────────────────────────────

    def render(self, output_path: Optional[str] = None, show: bool = False):
        """
        Render the current board state on the playmat image.
        Cards are drawn in their respective zones.
        """
        from PIL import Image, ImageDraw, ImageFont

        # Load the base playmat
        playmat = Image.open(PLAYMAT_IMG).convert("RGBA")
        # Extend canvas below playmat for Hand zone
        CANVAS_H = 1280
        if playmat.height < CANVAS_H:
            extended = Image.new("RGBA", (playmat.width, CANVAS_H), (30, 30, 50, 255))
            extended.paste(playmat, (0, 0))
            playmat = extended
        overlay = Image.new("RGBA", playmat.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Try to load a font
        try:
            font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 16)
            font_small = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 12)
            font_big = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 20)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
                font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
                font_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
            except (OSError, IOError):
                font = ImageFont.load_default()
                font_small = font
                font_big = font

        # Draw zone labels and card counts
        for zone in Zone:
            info = ZONE_DEFINITIONS[zone]
            x1, y1, x2, y2 = info.bbox
            cards = self.zones[zone]

            # Draw semi-transparent zone overlay
            zone_color = (255, 255, 255, 40) if not cards else (200, 255, 200, 60)
            draw.rectangle([(x1, y1), (x2, y2)], fill=zone_color, outline=(255, 255, 255, 120), width=2)

            # Draw zone name and card count at top of zone
            label = f"{info.display_name} ({len(cards)})"
            draw.text((x1 + 5, y1 + 3), label, fill=(255, 255, 255, 220), font=font_small)

        # Composite overlay onto playmat
        playmat = Image.alpha_composite(playmat, overlay)

        # Now draw cards in each zone
        for zone in Zone:
            info = ZONE_DEFINITIONS[zone]
            x1, y1, x2, y2 = info.bbox
            cards = self.zones[zone]

            if not cards:
                continue

            zone_w = x2 - x1
            zone_h = y2 - y1

            if zone == Zone.HAND:
                self._render_hand(playmat, cards, x1, y1, zone_w, zone_h)
            elif zone == Zone.LIFE:
                self._render_life_stack(playmat, cards, x1, y1, zone_w, zone_h, draw, font)
            elif zone == Zone.BACK:
                # Back zone: up to 5 cards side by side
                self._render_cards_horizontal(playmat, cards, x1, y1, zone_w, zone_h, max_cols=5)
            elif zone == Zone.HOLO_POWER:
                # Holo Power: horizontal like Life
                self._render_holo_power_stack(playmat, cards, x1, y1, zone_w, zone_h, draw, font)
            elif zone in (Zone.DECK, Zone.YELL_DECK, Zone.ARCHIVE):
                # Stack zones: show top card + count
                self._render_stack(playmat, cards, x1, y1, zone_w, zone_h, draw, font, info)
            else:
                # Single card zones (Centre, Collabo, Oshi): show the card
                self._render_single_card(playmat, cards[0], x1, y1, zone_w, zone_h)

        # Convert back to RGB for saving as JPEG
        result = playmat.convert("RGB")

        if output_path:
            result.save(output_path)
            print(f"✓ Board rendered to {output_path}")

        if show:
            result.show()

        return result

    def _load_card_image(self, card: Card, target_w: int, target_h: int,
                         horizontal: bool = False):
        """Load and resize a card image to fit a target area."""
        from PIL import Image

        img_path = card.image_path
        if not os.path.exists(img_path):
            img = Image.new("RGBA", (target_w, target_h), (100, 100, 100, 200))
            if horizontal:
                img = img.rotate(90, expand=True)
                bw, bh = img.size
                s = min(target_w / bw, target_h / bh)
                img = img.resize((int(bw * s), int(bh * s)), Image.Resampling.LANCZOS)
            return img

        img = Image.open(img_path).convert("RGBA")

        if not card.face_up:
            if os.path.exists(CARD_BACK_IMG):
                back = Image.open(CARD_BACK_IMG).convert("RGBA")
                if horizontal:
                    back = back.rotate(90, expand=True)
                bw, bh = back.size
                s = min(target_w / bw, target_h / bh)
                back = back.resize((int(bw * s), int(bh * s)), Image.Resampling.LANCZOS)
                return back
            img = Image.new("RGBA", (target_w, target_h), (30, 30, 80, 230))
            return img

        if horizontal:
            img = img.rotate(90, expand=True)

        card_w, card_h = img.size
        scale = min(target_w / card_w, target_h / card_h)
        new_w = int(card_w * scale)
        new_h = int(card_h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        return img

    def _render_single_card(self, playmat, card: Card, x: int, y: int, w: int, h: int):
        """Render a single card in a zone, with bloom stack (15%) and yells (10%) visible."""
        padding = 8
        n_stacked = len(card.stacked_cards)
        n_yells = len(card.attached_yells)
        stack_strip = int((h - padding * 2) * 0.15) if n_stacked else 0
        yell_strip = int((h - padding * 2) * 0.10) if n_yells else 0
        total_stack_offset = n_stacked * stack_strip
        total_yell_offset = n_yells * yell_strip
        card_area_h = h - padding * 2 - total_yell_offset - total_stack_offset
        card_w = w - padding * 2

        # Draw yells first (bottommost)
        for yi, yell in enumerate(card.attached_yells):
            yell_img = self._load_card_image(yell, card_w, card_area_h)
            yy = y + padding + yi * yell_strip
            yx = x + (w - yell_img.width) // 2
            playmat.paste(yell_img, (yx, yy), yell_img)

        # Draw bloom stack (older cards underneath, 5% visible)
        base_y = y + padding + total_yell_offset
        for si, sc in enumerate(card.stacked_cards):
            sc_img = self._load_card_image(sc, card_w, card_area_h)
            sy = base_y + si * stack_strip
            sx = x + (w - sc_img.width) // 2
            playmat.paste(sc_img, (sx, sy), sc_img)

        # Main card on top
        card_img = self._load_card_image(card, card_w, card_area_h)
        cx = x + (w - card_img.width) // 2
        cy = base_y + total_stack_offset
        playmat.paste(card_img, (cx, cy), card_img)

        # Badges
        from PIL import ImageDraw as ID, ImageFont
        try:
            bfont = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 11)
        except (OSError, IOError):
            bfont = ImageFont.load_default()
        bd = ID.Draw(playmat)
        if n_yells:
            txt = f"Y×{n_yells}"
            bx, by = x + w - 40, y + h - 22
            bd.rounded_rectangle([(bx-2, by-2), (bx+35, by+16)], radius=6, fill=(255, 200, 0, 200))
            bd.text((bx+2, by), txt, fill=(0, 0, 0), font=bfont)
        if n_stacked:
            txt = f"B×{n_stacked}"
            bx2 = x + 5
            by2 = y + h - 22
            bd.rounded_rectangle([(bx2-2, by2-2), (bx2+35, by2+16)], radius=6, fill=(100, 200, 255, 200))
            bd.text((bx2+2, by2), txt, fill=(0, 0, 0), font=bfont)

    def _render_cards_horizontal(self, playmat, cards: list[Card],
                                  x: int, y: int, w: int, h: int, max_cols: int = 5):
        """Render multiple cards side by side in a zone, with attached yells."""
        n = min(len(cards), max_cols)
        if n == 0:
            return
        padding = 6
        card_w = (w - padding * (n + 1)) // n
        card_h = h - padding * 2

        from PIL import ImageDraw as ID, ImageFont
        try:
            bfont = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 10)
        except (OSError, IOError):
            bfont = ImageFont.load_default()

        for i, card in enumerate(cards[:max_cols]):
            slot_x = x + padding + i * (card_w + padding)
            slot_y = y + padding
            n_stacked = len(card.stacked_cards)
            n_yells = len(card.attached_yells)
            is_resting = getattr(card, 'resting', False)
            stack_strip = int(card_h * 0.15) if n_stacked else 0
            yell_strip = int(card_h * 0.10) if n_yells else 0
            total_stack = n_stacked * stack_strip
            total_yell = n_yells * yell_strip
            main_h = card_h - total_yell - total_stack

            # Yells (bottommost)
            for yi, yell in enumerate(card.attached_yells):
                yell_img = self._load_card_image(yell, card_w, main_h)
                yy = slot_y + yi * yell_strip
                playmat.paste(yell_img, (slot_x, yy), yell_img)

            # Bloom stack
            base_y = slot_y + total_yell
            for si, sc in enumerate(card.stacked_cards):
                sc_img = self._load_card_image(sc, card_w, main_h,
                                               horizontal=is_resting)
                playmat.paste(sc_img, (slot_x, base_y + si * stack_strip), sc_img)

            # Main card on top (rested = horizontal/rotated)
            card_img = self._load_card_image(card, card_w, main_h,
                                             horizontal=is_resting)
            offset_y = (main_h - card_img.height) // 2
            playmat.paste(card_img, (slot_x, base_y + total_stack + offset_y), card_img)

            bd = ID.Draw(playmat)
            if is_resting:
                # Draw a "💤" rest indicator
                bd.rounded_rectangle(
                    [(slot_x + card_w // 2 - 12, slot_y + 2),
                     (slot_x + card_w // 2 + 25, slot_y + 18)],
                    radius=5, fill=(80, 80, 160, 200))
                bd.text((slot_x + card_w // 2 - 8, slot_y + 3), "REST",
                        fill=(255, 255, 255), font=bfont)
            if n_yells:
                txt = f"Y×{n_yells}"
                bx = slot_x + card_w - 35
                by = slot_y + card_h - 18
                bd.rounded_rectangle([(bx-2, by-2), (bx+30, by+14)], radius=5, fill=(255, 200, 0, 200))
                bd.text((bx+1, by), txt, fill=(0, 0, 0), font=bfont)
            if n_stacked:
                txt = f"B×{n_stacked}"
                bx2 = slot_x + 2
                by2 = slot_y + card_h - 18
                bd.rounded_rectangle([(bx2-2, by2-2), (bx2+30, by2+14)], radius=5, fill=(100, 200, 255, 200))
                bd.text((bx2+1, by2), txt, fill=(0, 0, 0), font=bfont)

    def _render_stack(self, playmat, cards: list[Card],
                      x: int, y: int, w: int, h: int, draw, font, info: ZoneInfo):
        """Render a stack of cards (showing top card + count badge)."""
        from PIL import ImageDraw as ID

        padding = 8
        # Show the top card
        top_card = cards[-1]
        card_img = self._load_card_image(top_card, w - padding * 2, h - padding * 2 - 20)
        cx = x + (w - card_img.width) // 2
        cy = y + padding + 18
        playmat.paste(card_img, (cx, cy), card_img)

        # Draw count badge
        count_text = f"×{len(cards)}"
        badge_x = x + w - 45
        badge_y = y + h - 30
        badge_draw = ID.Draw(playmat)
        badge_draw.rounded_rectangle(
            [(badge_x - 2, badge_y - 2), (badge_x + 40, badge_y + 20)],
            radius=8, fill=(0, 0, 0, 180)
        )
        badge_draw.text((badge_x + 4, badge_y), count_text, fill=(255, 255, 255), font=font)

    def _render_horizontal_stack(self, playmat, cards: list, x: int, y: int,
                                 w: int, h: int, draw, font, visible_fraction: float = 0.15):
        """Render a zone with cards placed horizontally (rotated), stacked with given visible fraction."""
        from PIL import ImageDraw as ID
        if not cards:
            return
        padding = 8
        n = len(cards)
        card_w = w - padding * 2
        max_card_h = h - padding * 2 - 18
        if n == 1:
            card_h = max_card_h
        else:
            card_h = int(max_card_h / (1 + (n - 1) * visible_fraction))
        visible_strip = int(card_h * visible_fraction)
        start_y = y + padding + 18
        for i, card in enumerate(cards):
            cy = start_y + i * visible_strip
            card_img = self._load_card_image(card, card_w, card_h, horizontal=True)
            cx = x + (w - card_img.width) // 2
            playmat.paste(card_img, (cx, cy), card_img)
        badge_draw = ID.Draw(playmat)
        count_text = f"×{n}"
        badge_x = x + w - 45
        badge_y = y + h - 30
        badge_draw.rounded_rectangle(
            [(badge_x - 2, badge_y - 2), (badge_x + 40, badge_y + 20)],
            radius=8, fill=(0, 0, 0, 180)
        )
        badge_draw.text((badge_x + 4, badge_y), count_text,
                        fill=(255, 255, 255), font=font)

    def _render_life_stack(self, playmat, cards, x, y, w, h, draw, font):
        """Render Life zone: horizontal cards, 15% visible."""
        self._render_horizontal_stack(playmat, cards, x, y, w, h, draw, font, 0.15)

    def _render_holo_power_stack(self, playmat, cards, x, y, w, h, draw, font):
        """Render Holo Power zone: horizontal cards, 15% visible."""
        self._render_horizontal_stack(playmat, cards, x, y, w, h, draw, font, 0.15)

    def _render_hand(self, playmat, cards: list, x: int, y: int, w: int, h: int):
        """Render Hand zone: cards side-by-side, face-up, overlapping if many."""
        if not cards:
            return
        n = len(cards)
        padding = 6
        avail_w = w - padding * 2
        card_w = min(avail_w // max(n, 1), 140)
        card_h = h - padding * 2 - 20
        if n * card_w > avail_w:
            step = (avail_w - card_w) // max(n - 1, 1)
        else:
            step = card_w + padding
        for i, card in enumerate(cards):
            cx = x + padding + i * step
            cy = y + padding + 18
            card_img = self._load_card_image(card, card_w, card_h)
            playmat.paste(card_img, (cx, cy), card_img)

    # ── Interactive GUI ──────────────────────────────────────────────

    def launch_gui(self):
        """Launch an interactive tkinter GUI for the playmat."""
        import tkinter as tk
        from tkinter import ttk, messagebox, simpledialog
        from PIL import Image, ImageTk, ImageDraw
        from support_card_db import SupportCardExecutor, SUPPORT_CARD_DB, ActionType

        self._load_db()

        root = tk.Tk()
        root.title("hOCG Playmat — Interactive Board")
        root.configure(bg="#1a1a2e")

        # State
        selected_zone = [None]
        drag_data = {"zone": None, "index": None}

        # ── Support Card Executor ──
        support_executor = SupportCardExecutor(self)
        support_executor.start_turn()

        # ── Main layout ──
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: playmat canvas
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scale playmat to fit screen
        screen_w = root.winfo_screenwidth()
        CANVAS_H = 1280
        scale = min(1.0, (screen_w - 400) / 2040)
        display_w = int(2040 * scale)
        display_h = int(CANVAS_H * scale)

        canvas = tk.Canvas(canvas_frame, width=display_w, height=display_h,
                           bg="#2a2a3e", highlightthickness=0)
        canvas.pack(padx=5, pady=5)

        # Right: control panel
        panel = ttk.Frame(main_frame, width=350)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        panel.pack_propagate(False)

        ttk.Label(panel, text="hOCG Playmat Controls",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        # Zone info display
        info_frame = ttk.LabelFrame(panel, text="Selected Zone", padding=10)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        zone_label = ttk.Label(info_frame, text="Click a zone on the playmat",
                               wraplength=300)
        zone_label.pack()
        cards_listbox = tk.Listbox(info_frame, height=6, font=("Courier", 11))
        cards_listbox.pack(fill=tk.X, pady=5)

        # Card search
        search_frame = ttk.LabelFrame(panel, text="Add Card", padding=10)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text="Card Number:").pack(anchor=tk.W)
        card_entry = ttk.Entry(search_frame, width=30)
        card_entry.pack(fill=tk.X, pady=2)

        search_results = tk.Listbox(search_frame, height=4, font=("Courier", 10))
        search_results.pack(fill=tk.X, pady=2)

        def on_search(*_):
            query = card_entry.get().strip().lower()
            search_results.delete(0, tk.END)
            if len(query) < 2:
                return
            count = 0
            for card_data in self._card_db:
                cn = card_data.get("card_number", "")
                name = card_data.get("card_name", "")
                if query in cn.lower() or query in name.lower():
                    search_results.insert(tk.END, f"{cn} — {name}")
                    count += 1
                    if count >= 20:
                        break

        card_entry.bind("<KeyRelease>", on_search)

        def add_card_to_zone():
            zone = selected_zone[0]
            if zone is None:
                messagebox.showinfo("Info", "Select a zone first by clicking the playmat.")
                return
            # Get card number from search selection or entry
            sel = search_results.curselection()
            if sel:
                text = search_results.get(sel[0])
                card_num = text.split(" — ")[0].strip()
            else:
                card_num = card_entry.get().strip()

            if not card_num:
                messagebox.showinfo("Info", "Enter a card number or search for a card.")
                return

            try:
                self.place_card_by_number(zone, card_num)
                refresh_display()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(search_frame, text="Place in Zone", command=add_card_to_zone).pack(pady=5)

        # Deck code loader
        deck_frame = ttk.LabelFrame(panel, text="Load Deck (Decklog)", padding=10)
        deck_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(deck_frame, text="Deck Code:").pack(anchor=tk.W)
        deck_code_entry = ttk.Entry(deck_frame, width=20)
        deck_code_entry.pack(fill=tk.X, pady=2)

        def load_deck_action():
            code = deck_code_entry.get().strip()
            if not code:
                messagebox.showinfo("Info", "Enter a deck code.")
                return
            try:
                self.load_deck_from_decklog(code)
                refresh_display()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(deck_frame, text="Load Deck", command=load_deck_action).pack(pady=5)

        # Game actions
        game_frame = ttk.LabelFrame(panel, text="Game", padding=10)
        game_frame.pack(fill=tk.X, padx=5, pady=5)

        def _archive_card_flat(card):
            """Archive a card and all its stacked cards + attached yells individually."""
            # Archive attached yells
            for yc in card.attached_yells:
                yc.face_up = True
                self.zones[Zone.ARCHIVE].append(yc)
            card.attached_yells = []
            # Archive stacked cards (bloom stack)
            for sc in card.stacked_cards:
                # Recursively flatten in case stacked cards also have yells
                _archive_card_flat(sc)
            card.stacked_cards = []
            # Archive the card itself
            card.face_up = True
            card.resting = False
            self.zones[Zone.ARCHIVE].append(card)

        def draw_card_action():
            self.draw_card(1)
            refresh_display()

        def draw_seven_action():
            self.draw_card(7)
            refresh_display()

        def _shuffle_effect(zone_type):
            """Visual shuffle effect: flash the zone area on canvas."""
            info_z = ZONE_DEFINITIONS[zone_type]
            x1z, y1z, x2z, y2z = info_z.bbox
            sx1 = int(x1z * scale); sy1 = int(y1z * scale)
            sx2 = int(x2z * scale); sy2 = int(y2z * scale)
            colors = ["#ff6b6b", "#51cf66", "#339af0", "#fcc419", "#cc5de8"]
            def flash(i):
                if i >= len(colors):
                    canvas.delete("shuffle_fx")
                    refresh_display()
                    return
                canvas.delete("shuffle_fx")
                canvas.create_rectangle(sx1, sy1, sx2, sy2,
                    fill=colors[i], outline="white", width=3,
                    stipple="gray50", tags="shuffle_fx")
                canvas.create_text((sx1+sx2)//2, (sy1+sy2)//2,
                    text="Shuffle!", font=("Helvetica", 16, "bold"),
                    fill="white", tags="shuffle_fx")
                root.after(120, lambda: flash(i + 1))
            flash(0)

        def shuffle_deck_action():
            self.shuffle_deck()
            _shuffle_effect(Zone.DECK)

        def shuffle_yell_action():
            self.shuffle_yell_deck()
            _shuffle_effect(Zone.YELL_DECK)

        game_row1 = ttk.Frame(game_frame)
        game_row1.pack(fill=tk.X, pady=2)
        ttk.Button(game_row1, text="Draw 1", command=draw_card_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(game_row1, text="Draw 7", command=draw_seven_action).pack(side=tk.LEFT, padx=2)

        game_row2 = ttk.Frame(game_frame)
        game_row2.pack(fill=tk.X, pady=2)
        ttk.Button(game_row2, text="Shuffle Deck", command=shuffle_deck_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(game_row2, text="Shuffle Yell", command=shuffle_yell_action).pack(side=tk.LEFT, padx=2)

        def hand_to_deck_action():
            """Move all hand cards back to the deck."""
            count = len(self.zones[Zone.HAND])
            if count == 0:
                messagebox.showinfo("Info", "Hand is empty.")
                return
            while self.zones[Zone.HAND]:
                c = self.zones[Zone.HAND].pop()
                c.face_up = False
                self.zones[Zone.DECK].append(c)
            self.shuffle_deck()
            print(f"✓ Returned {count} cards from Hand → Deck (shuffled)")
            _shuffle_effect(Zone.DECK)

        def reset_step_action():
            """Reset step: Collabo → Back (resting), all Back holomen → resting."""
            moved = 0
            rested = 0
            # Move collabo holomen back to back position
            while self.zones[Zone.COLLABO]:
                c = self.zones[Zone.COLLABO].pop()
                c.resting = True
                if len(self.zones[Zone.BACK]) < 4:
                    self.zones[Zone.BACK].append(c)
                    moved += 1
                    print(f"✓ {c.card_name} Collabo → Back (resting)")
                else:
                    # Back full, keep in collabo
                    self.zones[Zone.COLLABO].append(c)
                    messagebox.showinfo("Reset", f"Back is full, {c.card_name} stays in Collabo.")
                    break
            # Set all back holomen to resting
            for c in self.zones[Zone.BACK]:
                if not c.resting:
                    c.resting = True
                    rested += 1
            if rested:
                print(f"✓ {rested} Back holomen set to resting")
            refresh_display()

        game_row2b = ttk.Frame(game_frame)
        game_row2b.pack(fill=tk.X, pady=2)
        ttk.Button(game_row2b, text="Hand → Deck", command=hand_to_deck_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(game_row2b, text="Reset Step", command=reset_step_action).pack(side=tk.LEFT, padx=2)

        game_row3 = ttk.Frame(game_frame)
        game_row3.pack(fill=tk.X, pady=2)

        def _image_search_popup(title, zone_key, actions, reverse=False, summary_fn=None):
            """Generic image-grid search popup for a zone.
            actions: list of (button_label, callback(card, idx, dlg))
            reverse: if True, show items in reverse order (top-of-deck first)
            summary_fn: optional callable returning summary text to show above grid
            """
            cards_in_zone = self.zones[zone_key]
            if not cards_in_zone:
                messagebox.showinfo("Info", f"{title}: empty.")
                return
            dlg = tk.Toplevel(root)
            dlg.title(title)
            dlg.geometry("820x600")
            dlg.transient(root)

            top_bar = ttk.Frame(dlg)
            top_bar.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(top_bar, text=title,
                      font=("Helvetica", 13, "bold")).pack(side=tk.LEFT)
            filter_var = tk.StringVar()
            ttk.Label(top_bar, text="  Filter:").pack(side=tk.LEFT, padx=(15, 2))
            ttk.Entry(top_bar, textvariable=filter_var, width=25).pack(side=tk.LEFT)

            # Optional summary bar (e.g., yell counts)
            summary_label = None
            if summary_fn:
                summary_bar = ttk.Frame(dlg)
                summary_bar.pack(fill=tk.X, padx=10, pady=(0, 3))
                summary_label = ttk.Label(summary_bar, text=summary_fn(),
                                          font=("Helvetica", 10))
                summary_label.pack(side=tk.LEFT)

            # Scrollable canvas for image grid
            outer = ttk.Frame(dlg)
            outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            popup_canvas = tk.Canvas(outer, bg="#2a2a3e", highlightthickness=0)
            vsb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=popup_canvas.yview)
            popup_canvas.configure(yscrollcommand=vsb.set)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            popup_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            inner = ttk.Frame(popup_canvas)
            popup_canvas.create_window((0, 0), window=inner, anchor=tk.NW)

            # Keep photo references alive
            dlg._photos = []

            THUMB_W, THUMB_H = 100, 140
            COLS = 6

            def populate(filter_text=""):
                for w in inner.winfo_children():
                    w.destroy()
                dlg._photos.clear()
                ft = filter_text.lower()
                col = 0
                row_frame = None
                zone_cards = list(self.zones[zone_key])
                if reverse:
                    indices = list(range(len(zone_cards) - 1, -1, -1))
                else:
                    indices = list(range(len(zone_cards)))
                for i in indices:
                    card = zone_cards[i]
                    lbl = f"{card.card_number} {card.card_name} {card.card_type}"
                    if ft and ft not in lbl.lower():
                        continue
                    if col % COLS == 0:
                        row_frame = ttk.Frame(inner)
                        row_frame.pack(fill=tk.X, padx=5, pady=3)
                    # Card frame
                    cf = ttk.Frame(row_frame)
                    cf.pack(side=tk.LEFT, padx=4, pady=2)
                    # Thumbnail
                    try:
                        pil_img = self._load_card_image(
                            Card(card.card_number, card.card_name,
                                 card.card_type, card.image_file, True),
                            THUMB_W, THUMB_H)
                        photo = ImageTk.PhotoImage(pil_img)
                    except Exception:
                        photo = None
                    if photo:
                        dlg._photos.append(photo)
                        img_label = tk.Label(cf, image=photo, bg="#2a2a3e")
                        img_label.pack()
                    ttk.Label(cf, text=card.card_name, wraplength=THUMB_W,
                              font=("Helvetica", 8)).pack()
                    ttk.Label(cf, text=card.card_number,
                              font=("Helvetica", 7)).pack()
                    # Action buttons per card
                    btn_f = ttk.Frame(cf)
                    btn_f.pack()
                    for alabel, acb in actions:
                        idx_copy = i
                        cb_copy = acb
                        ttk.Button(btn_f, text=alabel,
                            command=lambda idx=idx_copy, cb=cb_copy: cb(idx, dlg, populate, filter_var)
                        ).pack(side=tk.LEFT, padx=1)
                    col += 1
                inner.update_idletasks()
                popup_canvas.configure(scrollregion=popup_canvas.bbox("all"))
                # Update summary if present
                if summary_label and summary_fn:
                    summary_label.config(text=summary_fn())

            populate()
            filter_var.trace_add("write", lambda *_: populate(filter_var.get()))
            ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=5)

        def search_deck_popup():
            def to_hand(idx, dlg, repop, fvar):
                if idx >= len(self.zones[Zone.DECK]):
                    return
                card = self.zones[Zone.DECK].pop(idx)
                card.face_up = True
                self.zones[Zone.HAND].append(card)
                print(f"✓ {card.card_name} Deck → Hand")
                self.shuffle_deck()
                repop(fvar.get())
                refresh_display()

            def to_archive(idx, dlg, repop, fvar):
                if idx >= len(self.zones[Zone.DECK]):
                    return
                card = self.zones[Zone.DECK].pop(idx)
                card.face_up = True
                self.zones[Zone.ARCHIVE].append(card)
                print(f"✓ {card.card_name} Deck → Archive")
                self.shuffle_deck()
                repop(fvar.get())
                refresh_display()

            _image_search_popup("Search Deck", Zone.DECK,
                [("Hand", to_hand), ("Archive", to_archive)], reverse=True)

        def search_archive_popup():
            def to_deck_top(idx, dlg, repop, fvar):
                if idx >= len(self.zones[Zone.ARCHIVE]):
                    return
                card = self.zones[Zone.ARCHIVE].pop(idx)
                card.face_up = False
                self.zones[Zone.DECK].append(card)
                print(f"✓ {card.card_name} Archive → Deck Top")
                repop(fvar.get())
                refresh_display()

            def to_deck_bottom(idx, dlg, repop, fvar):
                if idx >= len(self.zones[Zone.ARCHIVE]):
                    return
                card = self.zones[Zone.ARCHIVE].pop(idx)
                card.face_up = False
                self.zones[Zone.DECK].insert(0, card)
                print(f"✓ {card.card_name} Archive → Deck Bottom")
                repop(fvar.get())
                refresh_display()

            def to_hand(idx, dlg, repop, fvar):
                if idx >= len(self.zones[Zone.ARCHIVE]):
                    return
                card = self.zones[Zone.ARCHIVE].pop(idx)
                card.face_up = True
                self.zones[Zone.HAND].append(card)
                print(f"✓ {card.card_name} Archive → Hand")
                repop(fvar.get())
                refresh_display()

            def to_yell_top(idx, dlg, repop, fvar):
                if idx >= len(self.zones[Zone.ARCHIVE]):
                    return
                card = self.zones[Zone.ARCHIVE].pop(idx)
                card.face_up = False
                self.zones[Zone.YELL_DECK].append(card)
                print(f"✓ {card.card_name} Archive → Yell Deck Top")
                repop(fvar.get())
                refresh_display()

            def to_yell_btm(idx, dlg, repop, fvar):
                if idx >= len(self.zones[Zone.ARCHIVE]):
                    return
                card = self.zones[Zone.ARCHIVE].pop(idx)
                card.face_up = False
                self.zones[Zone.YELL_DECK].insert(0, card)
                print(f"✓ {card.card_name} Archive → Yell Deck Bottom")
                repop(fvar.get())
                refresh_display()

            COLOR_MAP = {"白": "White", "緑": "Green", "赤": "Red",
                         "青": "Blue", "紫": "Purple", "黄": "Yellow"}

            def _archive_yell_summary():
                """Count yell cards in archive by color."""
                self._load_db()
                from collections import Counter
                color_counts = Counter()
                total = 0
                for c in self.zones[Zone.ARCHIVE]:
                    if c.card_type == 'エール':
                        total += 1
                        data = self._card_index.get(c.card_number, {})
                        for col in data.get('色', []):
                            color_counts[col] += 1
                parts = [f"Yells: {total}"]
                for jp, en in COLOR_MAP.items():
                    cnt = color_counts.get(jp, 0)
                    if cnt:
                        parts.append(f"{jp}({en}): {cnt}")
                return "  |  ".join(parts)

            _image_search_popup("Search Archive", Zone.ARCHIVE,
                [("Top", to_deck_top), ("Btm", to_deck_bottom), ("Hand", to_hand),
                 ("Y↑", to_yell_top), ("Y↓", to_yell_btm)],
                summary_fn=_archive_yell_summary)

        ttk.Button(game_row3, text="Search Deck",
                   command=search_deck_popup).pack(side=tk.LEFT, padx=2)
        ttk.Button(game_row3, text="Search Archive",
                   command=search_archive_popup).pack(side=tk.LEFT, padx=2)

        def deduct_life_action():
            """Deduct 1 life: pop top life card, choose a holomen to attach it as yell."""
            if not self.zones[Zone.LIFE]:
                messagebox.showinfo("Life", "No life cards remaining!")
                return
            life_card = self.zones[Zone.LIFE].pop()
            life_card.face_up = True
            print(f"✓ Life deducted: {life_card.card_name}")

            # Collect all holomen on stage (Centre, Back, Collabo)
            stage_holomen = []
            for z in [Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
                for ci, c in enumerate(self.zones[z]):
                    stage_holomen.append((z, ci, c))

            if not stage_holomen:
                # No holomen to attach to — send to archive
                self.zones[Zone.ARCHIVE].append(life_card)
                print(f"  No holomen on stage — {life_card.card_name} → Archive")
                refresh_display()
                return

            # Show popup to pick a holomen to attach the yell to
            dlg = tk.Toplevel(root)
            dlg.title(f"Attach Life ({life_card.card_name}) to Holomen")
            dlg.geometry("550x380")
            dlg.transient(root)
            ttk.Label(dlg, text=f"Attach {life_card.card_name} as yell to:",
                      font=("Helvetica", 11, "bold")).pack(pady=5)
            dlg._photos = []
            grid = ttk.Frame(dlg)
            grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            for z, ci, holo in stage_holomen:
                cf = ttk.Frame(grid)
                cf.pack(side=tk.LEFT, padx=8, pady=4)
                zname = ZONE_DEFINITIONS[z].display_name
                try:
                    pil_img = self._load_card_image(
                        Card(holo.card_number, holo.card_name, holo.card_type,
                             holo.image_file, True, holo.bloom_level), 80, 115)
                    photo = ImageTk.PhotoImage(pil_img)
                    dlg._photos.append(photo)
                    tk.Label(cf, image=photo, bg="#2a2a3e").pack()
                except Exception:
                    pass
                ttk.Label(cf, text=f"{holo.card_name}\n[{zname}]",
                          font=("Helvetica", 8), wraplength=90).pack()
                def do_attach(zone=z, idx=ci):
                    self.zones[zone][idx].attached_yells.append(life_card)
                    print(f"  Attached {life_card.card_name} to "
                          f"{self.zones[zone][idx].card_name}")
                    dlg.destroy()
                    refresh_display()
                ttk.Button(cf, text="Attach", command=do_attach).pack(pady=2)

            def to_archive():
                self.zones[Zone.ARCHIVE].append(life_card)
                print(f"  {life_card.card_name} → Archive (not attached)")
                dlg.destroy()
                refresh_display()
            ttk.Button(dlg, text="→ Archive Instead", command=to_archive).pack(pady=5)

        game_row4 = ttk.Frame(game_frame)
        game_row4.pack(fill=tk.X, pady=2)
        ttk.Button(game_row4, text="Deduct Life",
                   command=deduct_life_action).pack(side=tk.LEFT, padx=2)

        # ── Support card helpers ──
        def new_turn_action():
            """Reset turn state for support cards (LIMITED, per-turn limits, modifiers)."""
            support_executor.start_turn()
            msg = "New turn started.\n• LIMITED card usage reset\n• Per-turn limits reset\n• Turn modifiers cleared"
            print(f"✓ {msg}")
            messagebox.showinfo("New Turn", msg)

        def list_supports_popup():
            """Show all support cards in hand with their playability status."""
            supports = support_executor.list_playable_supports()
            if not supports:
                messagebox.showinfo("Supports", "No support cards in hand.")
                return

            dlg = tk.Toplevel(root)
            dlg.title("Support Cards in Hand")
            dlg.geometry("700x550")
            dlg.transient(root)
            dlg._photos = []

            ttk.Label(dlg, text="Support Cards in Hand",
                      font=("Helvetica", 13, "bold")).pack(pady=8)

            # Scrollable list
            outer = ttk.Frame(dlg)
            outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            popup_canvas = tk.Canvas(outer, bg="#2a2a3e", highlightthickness=0)
            vsb = ttk.Scrollbar(outer, orient=tk.VERTICAL,
                                command=popup_canvas.yview)
            popup_canvas.configure(yscrollcommand=vsb.set)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            popup_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            inner = ttk.Frame(popup_canvas)
            popup_canvas.create_window((0, 0), window=inner, anchor=tk.NW)

            THUMB_W, THUMB_H = 80, 115
            for si, sinfo in enumerate(supports):
                row = ttk.Frame(inner, relief=tk.RIDGE, borderwidth=1)
                row.pack(fill=tk.X, padx=5, pady=3)
                # Thumbnail
                try:
                    c_data = Card(sinfo["card_number"], sinfo["card_name"],
                                  sinfo["card_type"], "", True)
                    pil_img = self._load_card_image(c_data, THUMB_W, THUMB_H)
                    photo = ImageTk.PhotoImage(pil_img)
                    dlg._photos.append(photo)
                    tk.Label(row, image=photo, bg="#2a2a3e").pack(
                        side=tk.LEFT, padx=5, pady=3)
                except Exception:
                    pass
                # Info
                info_f = ttk.Frame(row)
                info_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
                name_txt = sinfo["card_name"]
                if sinfo.get("is_limited"):
                    name_txt += "  [LIMITED]"
                ttk.Label(info_f, text=name_txt,
                          font=("Helvetica", 11, "bold")).pack(anchor=tk.W)
                ttk.Label(info_f, text=f"{sinfo['card_number']}  •  {sinfo['card_type']}",
                          font=("Helvetica", 9)).pack(anchor=tk.W)
                ttk.Label(info_f, text=sinfo.get("summary", ""),
                          font=("Helvetica", 9), wraplength=350).pack(anchor=tk.W)
                # Status + button
                if sinfo["can_play"]:
                    fg_color = "#51cf66"
                    status = "✓ Playable"
                else:
                    fg_color = "#ff6b6b"
                    status = f"✗ {sinfo['reason']}"
                tk.Label(info_f, text=status, fg=fg_color,
                         bg="#2a2a3e", font=("Helvetica", 9)).pack(anchor=tk.W)
                # Play button
                if sinfo["can_play"]:
                    card_num = sinfo["card_number"]
                    def _play_from_list(cn=card_num, d=dlg):
                        # Find the card index in hand
                        for hi, hc in enumerate(self.zones[Zone.HAND]):
                            if hc.card_number == cn:
                                d.destroy()
                                _use_support_card(hi)
                                return
                    ttk.Button(info_f, text="▶ Play",
                               command=_play_from_list).pack(anchor=tk.W, pady=2)

            inner.update_idletasks()
            popup_canvas.configure(scrollregion=popup_canvas.bbox("all"))
            ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=5)

        game_row5 = ttk.Frame(game_frame)
        game_row5.pack(fill=tk.X, pady=2)
        ttk.Button(game_row5, text="New Turn",
                   command=new_turn_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(game_row5, text="Supports",
                   command=list_supports_popup).pack(side=tk.LEFT, padx=2)

        def _view_stack_popup(card):
            """Show all stacked cards and attached yells for a holomen."""
            dlg = tk.Toplevel(root)
            dlg.title(f"Stack — {card.card_name} ({card.bloom_level})")
            dlg.geometry("700x500")
            dlg.transient(root)
            dlg._photos = []

            outer = ttk.Frame(dlg)
            outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            popup_canvas = tk.Canvas(outer, bg="#2a2a3e", highlightthickness=0)
            vsb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=popup_canvas.yview)
            popup_canvas.configure(yscrollcommand=vsb.set)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            popup_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            inner = ttk.Frame(popup_canvas)
            popup_canvas.create_window((0, 0), window=inner, anchor=tk.NW)

            THUMB_W, THUMB_H = 100, 140

            # Active card
            ttk.Label(inner, text="Active Card:",
                      font=("Helvetica", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(8, 2))
            cf = ttk.Frame(inner)
            cf.pack(anchor=tk.W, padx=15, pady=2)
            try:
                pil_img = self._load_card_image(card, THUMB_W, THUMB_H)
                photo = ImageTk.PhotoImage(pil_img)
                dlg._photos.append(photo)
                tk.Label(cf, image=photo, bg="#2a2a3e").pack(side=tk.LEFT)
            except Exception:
                pass
            ttk.Label(cf, text=f"{card.card_name}\n{card.card_number}\n"
                      f"Level: {card.bloom_level}\nType: {card.card_type}",
                      font=("Helvetica", 10), wraplength=200).pack(side=tk.LEFT, padx=10)

            # Bloom stack
            if card.stacked_cards:
                ttk.Label(inner, text=f"Bloom Stack ({len(card.stacked_cards)}):",
                          font=("Helvetica", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))
                row = ttk.Frame(inner)
                row.pack(anchor=tk.W, padx=15, pady=2)
                for sc in card.stacked_cards:
                    sf = ttk.Frame(row)
                    sf.pack(side=tk.LEFT, padx=5)
                    try:
                        pil_img = self._load_card_image(sc, THUMB_W, THUMB_H)
                        photo = ImageTk.PhotoImage(pil_img)
                        dlg._photos.append(photo)
                        tk.Label(sf, image=photo, bg="#2a2a3e").pack()
                    except Exception:
                        pass
                    ttk.Label(sf, text=f"{sc.card_name}\n{sc.bloom_level}",
                              font=("Helvetica", 8), wraplength=90).pack()

            # Attached yells
            if card.attached_yells:
                ttk.Label(inner, text=f"Attached Yells ({len(card.attached_yells)}):",
                          font=("Helvetica", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))
                row2 = ttk.Frame(inner)
                row2.pack(anchor=tk.W, padx=15, pady=2)
                for yc in card.attached_yells:
                    yf = ttk.Frame(row2)
                    yf.pack(side=tk.LEFT, padx=5)
                    try:
                        pil_img = self._load_card_image(yc, THUMB_W, THUMB_H)
                        photo = ImageTk.PhotoImage(pil_img)
                        dlg._photos.append(photo)
                        tk.Label(yf, image=photo, bg="#2a2a3e").pack()
                    except Exception:
                        pass
                    ttk.Label(yf, text=f"{yc.card_name}\n{yc.card_number}",
                              font=("Helvetica", 8), wraplength=90).pack()

            if not card.stacked_cards and not card.attached_yells:
                ttk.Label(inner, text="(No bloom stack or attached yells)",
                          font=("Helvetica", 10)).pack(pady=20)

            inner.update_idletasks()
            popup_canvas.configure(scrollregion=popup_canvas.bbox("all"))
            ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=5)

        # Hand display (text list for reference)
        hand_frame = ttk.LabelFrame(panel, text="Hand", padding=5)
        hand_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(hand_frame, text="Click a card in Hand zone on playmat",
                  font=("Helvetica", 9), wraplength=300).pack()
        hand_listbox = tk.Listbox(hand_frame, height=4, font=("Courier", 10))
        hand_listbox.pack(fill=tk.X, pady=2)

        def update_hand_list():
            hand_listbox.delete(0, tk.END)
            for i, card in enumerate(self.zones[Zone.HAND]):
                holo = " ★" if "ホロメン" in card.card_type else ""
                hand_listbox.insert(tk.END,
                    f"{i}: {card.card_number} {card.card_name}{holo}")

        # Action buttons
        action_frame = ttk.LabelFrame(panel, text="Actions", padding=10)
        action_frame.pack(fill=tk.X, padx=5, pady=5)

        def remove_selected_card():
            zone = selected_zone[0]
            if zone is None:
                return
            sel = cards_listbox.curselection()
            idx = sel[0] if sel else -1
            self.remove_card(zone, idx)
            refresh_display()

        def move_card_dialog():
            zone = selected_zone[0]
            if zone is None or not self.zones[zone]:
                return
            # Pick target zone
            target_names = [f"{z.value} ({ZONE_DEFINITIONS[z].display_name})"
                            for z in Zone if z != zone]
            dialog = tk.Toplevel(root)
            dialog.title("Move Card To...")
            dialog.geometry("300x400")
            ttk.Label(dialog, text="Select destination zone:").pack(pady=5)
            lb = tk.Listbox(dialog, font=("Courier", 11))
            for name in target_names:
                lb.insert(tk.END, name)
            lb.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            def do_move():
                s = lb.curselection()
                if not s:
                    return
                target_value = target_names[s[0]].split(" (")[0]
                target_zone = Zone(target_value)
                sel = cards_listbox.curselection()
                idx = sel[0] if sel else -1
                self.move_card(zone, target_zone, idx)
                dialog.destroy()
                refresh_display()

            ttk.Button(dialog, text="Move", command=do_move).pack(pady=10)

        def clear_zone_action():
            zone = selected_zone[0]
            if zone is None:
                return
            self.clear_zone(zone)
            refresh_display()

        def save_state_action():
            path = os.path.join(PROJECT_DIR, "game_tools", "board_state.json")
            self.save_state(path)
            messagebox.showinfo("Saved", f"Board state saved to {path}")

        def load_state_action():
            path = os.path.join(PROJECT_DIR, "game_tools", "board_state.json")
            if os.path.exists(path):
                self.load_state(path)
                refresh_display()
            else:
                messagebox.showinfo("Info", "No saved state found.")

        def render_image_action():
            path = os.path.join(PROJECT_DIR, "game_tools", "board_render.jpg")
            self.render(output_path=path)
            messagebox.showinfo("Rendered", f"Board image saved to {path}")

        btn_row1 = ttk.Frame(action_frame)
        btn_row1.pack(fill=tk.X, pady=2)
        ttk.Button(btn_row1, text="Remove Card", command=remove_selected_card).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="Move Card", command=move_card_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="Clear Zone", command=clear_zone_action).pack(side=tk.LEFT, padx=2)

        btn_row2 = ttk.Frame(action_frame)
        btn_row2.pack(fill=tk.X, pady=2)
        ttk.Button(btn_row2, text="Save State", command=save_state_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="Load State", command=load_state_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="Render Image", command=render_image_action).pack(side=tk.LEFT, padx=2)

        btn_row3 = ttk.Frame(action_frame)
        btn_row3.pack(fill=tk.X, pady=2)
        ttk.Button(btn_row3, text="Print Board", command=self.print_board).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row3, text="Clear All", command=lambda: (self.clear_all(), refresh_display())).pack(side=tk.LEFT, padx=2)

        # ── Display functions ──

        def refresh_display():
            """Redraw the playmat canvas and update the cards list."""
            # Render the board
            board_img = self.render()
            board_img = board_img.resize((display_w, display_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(board_img)
            canvas.delete("all")
            canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            canvas._photo = photo  # Keep reference

            # Draw zone outlines on canvas
            for zone in Zone:
                info = ZONE_DEFINITIONS[zone]
                x1, y1, x2, y2 = info.bbox
                sx1, sy1 = int(x1 * scale), int(y1 * scale)
                sx2, sy2 = int(x2 * scale), int(y2 * scale)

                if zone == selected_zone[0]:
                    canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                            outline="#00ff88", width=3,
                                            tags=f"zone_{zone.value}")
                else:
                    canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                            outline="#888888", width=1,
                                            tags=f"zone_{zone.value}")

            # Update cards list
            update_card_list()
            update_hand_list()

        def update_card_list():
            cards_listbox.delete(0, tk.END)
            zone = selected_zone[0]
            if zone is None:
                zone_label.config(text="Click a zone on the playmat")
                return
            info = ZONE_DEFINITIONS[zone]
            cards = self.zones[zone]
            cap = f"/{info.max_cards}" if info.max_cards else ""
            zone_label.config(text=f"{info.display_name} ({info.display_name_jp})\n"
                              f"{len(cards)}{cap} cards — {info.description}")
            for i, card in enumerate(cards):
                face = "↑" if card.face_up else "↓"
                rest = " 💤" if card.resting else ""
                yells = f" +{len(card.attached_yells)}Y" if card.attached_yells else ""
                bloom = f" B×{len(card.stacked_cards)}" if card.stacked_cards else ""
                cards_listbox.insert(tk.END, f"{i}: {face}{rest} {card.card_number} {card.card_name}{yells}{bloom}")

        def _get_hand_card_index(px, py):
            """Given playmat coords, return the index of the hand card clicked, or None."""
            hi = ZONE_DEFINITIONS[Zone.HAND]
            hx1, hy1, hx2, hy2 = hi.bbox
            if not (hx1 <= px <= hx2 and hy1 <= py <= hy2):
                return None
            cards = self.zones[Zone.HAND]
            if not cards:
                return None
            n = len(cards)
            padding = 6
            w = hx2 - hx1
            avail_w = w - padding * 2
            card_w = min(avail_w // max(n, 1), 140)
            if n * card_w > avail_w:
                step = (avail_w - card_w) // max(n - 1, 1)
            else:
                step = card_w + padding
            # Check from last card (topmost) to first
            for i in range(n - 1, -1, -1):
                cx = hx1 + padding + i * step
                if cx <= px <= cx + card_w:
                    return i
            return None

        # ── Interactive card picker popups for support card execution ──

        def _pick_cards_popup(cards, min_pick, max_pick, title, message):
            """Show a popup allowing the user to select cards from a list.
            Blocks until user confirms. Returns list of selected Card objects."""
            result = {"picked": []}
            selected_set = set()  # indices of selected cards

            dlg = tk.Toplevel(root)
            dlg.title(title)
            dlg.geometry("780x600")
            dlg.transient(root)
            dlg.grab_set()
            dlg._photos = []

            ttk.Label(dlg, text=title,
                      font=("Helvetica", 13, "bold")).pack(pady=(8, 2))
            ttk.Label(dlg, text=message,
                      font=("Helvetica", 10), wraplength=720).pack(pady=(0, 8))

            # Selection counter
            sel_var = tk.StringVar(value=f"Selected: 0 / {max_pick}")
            sel_label = ttk.Label(dlg, textvariable=sel_var,
                                  font=("Helvetica", 11, "bold"))
            sel_label.pack()

            # Scrollable card grid
            outer = ttk.Frame(dlg)
            outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
            popup_canvas = tk.Canvas(outer, bg="#2a2a3e", highlightthickness=0)
            vsb = ttk.Scrollbar(outer, orient=tk.VERTICAL,
                                command=popup_canvas.yview)
            popup_canvas.configure(yscrollcommand=vsb.set)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            popup_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            inner = ttk.Frame(popup_canvas)
            popup_canvas.create_window((0, 0), window=inner, anchor=tk.NW)

            THUMB_W, THUMB_H = 100, 140
            COLS = 6
            card_frames = []  # (frame, border_label) for each card

            def _update_selection():
                count = len(selected_set)
                sel_var.set(f"Selected: {count} / {max_pick}")
                confirm_btn.config(
                    state=tk.NORMAL if min_pick <= count <= max_pick else tk.DISABLED)
                # Update visual highlight
                for idx, (cf, border_lbl) in enumerate(card_frames):
                    if idx in selected_set:
                        border_lbl.config(bg="#51cf66")
                    else:
                        border_lbl.config(bg="#2a2a3e")

            row_frame = None
            for ci, card in enumerate(cards):
                if ci % COLS == 0:
                    row_frame = ttk.Frame(inner)
                    row_frame.pack(fill=tk.X, padx=5, pady=3)

                cf = ttk.Frame(row_frame)
                cf.pack(side=tk.LEFT, padx=4, pady=2)

                # Coloured border label for selection highlight
                border_lbl = tk.Label(cf, bg="#2a2a3e", padx=3, pady=3)
                border_lbl.pack()

                # Thumbnail
                try:
                    pil_img = self._load_card_image(
                        Card(card.card_number, card.card_name,
                             card.card_type, card.image_file, True),
                        THUMB_W, THUMB_H)
                    photo = ImageTk.PhotoImage(pil_img)
                except Exception:
                    photo = None
                if photo:
                    dlg._photos.append(photo)
                    img_lbl = tk.Label(border_lbl, image=photo, bg="#2a2a3e")
                    img_lbl.pack()

                name_lbl = ttk.Label(cf, text=card.card_name,
                                     wraplength=THUMB_W,
                                     font=("Helvetica", 8))
                name_lbl.pack()
                num_lbl = ttk.Label(cf, text=f"{card.card_number}\n{card.card_type}",
                                    font=("Helvetica", 7), wraplength=THUMB_W)
                num_lbl.pack()

                card_frames.append((cf, border_lbl))

                # Toggle selection on click
                def _toggle(idx=ci):
                    if idx in selected_set:
                        selected_set.discard(idx)
                    else:
                        if len(selected_set) < max_pick:
                            selected_set.add(idx)
                    _update_selection()

                # Bind click to the entire card column
                for widget in [cf, border_lbl, name_lbl, num_lbl]:
                    widget.bind("<Button-1>", lambda e, t=_toggle: t())
                if photo:
                    img_lbl.bind("<Button-1>", lambda e, t=_toggle: t())

            inner.update_idletasks()
            popup_canvas.configure(scrollregion=popup_canvas.bbox("all"))

            # Buttons
            btn_frame = ttk.Frame(dlg)
            btn_frame.pack(pady=8)

            def _confirm():
                result["picked"] = [cards[i] for i in sorted(selected_set)]
                dlg.destroy()

            def _skip():
                result["picked"] = []
                dlg.destroy()

            confirm_btn = ttk.Button(btn_frame, text="✓ Confirm Selection",
                                     command=_confirm,
                                     state=tk.NORMAL if min_pick == 0 else tk.DISABLED)
            confirm_btn.pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Skip (pick none)",
                       command=_skip).pack(side=tk.LEFT, padx=5)

            _update_selection()

            dlg.wait_window()
            return result["picked"]

        def _pick_holomen_popup(holomen_list, title, message):
            """Show a popup allowing user to pick one holomen from a list.
            Blocks until user picks. Returns selected Card or None."""
            result = {"picked": None}

            dlg = tk.Toplevel(root)
            dlg.title(title)
            dlg.geometry("600x400")
            dlg.transient(root)
            dlg.grab_set()
            dlg._photos = []

            ttk.Label(dlg, text=title,
                      font=("Helvetica", 13, "bold")).pack(pady=(8, 2))
            ttk.Label(dlg, text=message,
                      font=("Helvetica", 10), wraplength=550).pack(pady=(0, 8))

            grid = ttk.Frame(dlg)
            grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            THUMB_W, THUMB_H = 90, 130

            for hi, holo in enumerate(holomen_list):
                cf = ttk.Frame(grid)
                cf.pack(side=tk.LEFT, padx=8, pady=4)
                try:
                    pil_img = self._load_card_image(
                        Card(holo.card_number, holo.card_name, holo.card_type,
                             holo.image_file, True, holo.bloom_level),
                        THUMB_W, THUMB_H)
                    photo = ImageTk.PhotoImage(pil_img)
                    dlg._photos.append(photo)
                    tk.Label(cf, image=photo, bg="#2a2a3e").pack()
                except Exception:
                    pass
                ttk.Label(cf, text=f"{holo.card_name}\n{holo.card_type}",
                          font=("Helvetica", 8), wraplength=90).pack()

                def _do_pick(c=holo):
                    result["picked"] = c
                    dlg.destroy()
                ttk.Button(cf, text="Select", command=_do_pick).pack(pady=2)

            ttk.Button(dlg, text="Cancel",
                       command=dlg.destroy).pack(pady=5)

            dlg.wait_window()
            return result["picked"]

        def _use_support_card(card_idx):
            """Show support card play confirmation popup and execute actions."""
            if card_idx >= len(self.zones[Zone.HAND]):
                return
            card = self.zones[Zone.HAND][card_idx]
            entry = SUPPORT_CARD_DB.get(card.card_number)
            if not entry:
                messagebox.showinfo("Support",
                    f"{card.card_name} ({card.card_number}) is not in the support card database.\n"
                    "It will need to be added to support_card_db.py.")
                return

            can, reason = support_executor.can_play(card.card_number)

            dlg = tk.Toplevel(root)
            dlg.title(f"Play Support — {card.card_name}")
            dlg.geometry("520x750")
            dlg.transient(root)
            dlg._photos = []

            # ── Card image ──
            try:
                pil_img = self._load_card_image(
                    Card(card.card_number, card.card_name, card.card_type,
                         card.image_file, True),
                    200, 280)
                photo = ImageTk.PhotoImage(pil_img)
                dlg._photos.append(photo)
                tk.Label(dlg, image=photo, bg="#2a2a3e").pack(pady=8)
            except Exception:
                pass

            # ── Card info ──
            info_parts = [f"{card.card_name}  ({card.card_number})",
                          f"Type: {card.card_type}"]
            if entry.get("is_limited"):
                info_parts.append("⚠ LIMITED (one per turn)")
            # Costs
            for cost in entry.get("costs", []):
                ctype = cost.get("type", "")
                if ctype == "archive_holo_power":
                    info_parts.append(f"Cost: Archive {cost.get('count',1)} Holo Power")
                elif ctype == "archive_hand_card":
                    info_parts.append(f"Cost: Archive {cost.get('count',1)} hand card(s)")
                elif ctype == "archive_stage_cheer":
                    info_parts.append(f"Cost: Archive {cost.get('count',1)} stage cheer")
                elif ctype:
                    info_parts.append(f"Cost: {ctype}")
            # Effect summary
            summary = support_executor._summarize_actions(entry)
            info_parts.append(f"\nEffect: {summary}")
            # Raw ability text
            self._load_db()
            db_data = self._card_index.get(card.card_number, {})
            ability = db_data.get('能力テキスト', '')
            if ability:
                info_parts.append(f"\n{ability}")

            ttk.Label(dlg, text="\n".join(info_parts),
                      font=("Helvetica", 10), wraplength=480,
                      justify=tk.LEFT).pack(padx=15, pady=5, anchor=tk.W)

            # ── Playability status ──
            if can:
                status_text = "✓ Ready to play"
                st_fg = "#51cf66"
            else:
                status_text = f"✗ Cannot play: {reason}"
                st_fg = "#ff6b6b"
            tk.Label(dlg, text=status_text, font=("Helvetica", 11, "bold"),
                     fg=st_fg, bg="#1a1a2e").pack(pady=4)

            # ── Action log ──
            log_frame = ttk.LabelFrame(dlg, text="Action Log", padding=5)
            log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            log_text = tk.Text(log_frame, height=8, font=("Courier", 9),
                               state=tk.DISABLED, bg="#1a1a2e", fg="white",
                               wrap=tk.WORD)
            log_text.pack(fill=tk.BOTH, expand=True)

            # ── Buttons ──
            btn_frame = ttk.Frame(dlg)
            btn_frame.pack(pady=8)

            def do_play():
                # Wire interactive callbacks so executor shows GUI pickers
                support_executor.pick_cards_cb = _pick_cards_popup
                support_executor.pick_holomen_cb = _pick_holomen_popup
                result = support_executor.play_support(card.card_number)
                # Clear callbacks after play
                support_executor.pick_cards_cb = None
                support_executor.pick_holomen_cb = None
                # Show results in log
                log_text.config(state=tk.NORMAL)
                log_text.delete("1.0", tk.END)
                if result["success"]:
                    log_text.insert(tk.END, f"✓ {result['message']}\n\n")
                    for i, desc in enumerate(result["actions_taken"], 1):
                        log_text.insert(tk.END, f"  {i}. {desc}\n")
                    # Show turn modifiers if any
                    mods = support_executor.get_turn_modifiers()
                    if mods:
                        log_text.insert(tk.END, f"\nActive modifiers this turn:\n")
                        for m in mods:
                            log_text.insert(tk.END,
                                f"  • {m.get('type')}: +{m.get('amount',0)} → {m.get('target','?')}\n")
                else:
                    log_text.insert(tk.END, f"✗ Failed: {result['message']}\n")
                log_text.config(state=tk.DISABLED)
                play_btn.config(state=tk.DISABLED)
                refresh_display()

            play_btn = ttk.Button(btn_frame, text="▶ Play Support Card",
                                  command=do_play,
                                  state=tk.NORMAL if can else tk.DISABLED)
            play_btn.pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel",
                       command=dlg.destroy).pack(side=tk.LEFT, padx=5)

        def _show_hand_card_menu(event, card_idx):
            """Show a context menu for a hand card."""
            card = self.zones[Zone.HAND][card_idx]
            menu = tk.Menu(root, tearoff=0)
            menu.add_command(label=f"── {card.card_name} ({card.bloom_level or card.card_type}) ──", state="disabled")
            menu.add_separator()
            is_holo = "ホロメン" in card.card_type
            if is_holo:
                def _to_centre(ci=card_idx):
                    if len(self.zones[Zone.CENTRE]) >= 1:
                        messagebox.showinfo("Info", "Centre already occupied.")
                        return
                    c = self.zones[Zone.HAND].pop(ci)
                    c.face_up = True
                    self.zones[Zone.CENTRE].append(c)
                    print(f"✓ Played {c.card_name} → Centre")
                    refresh_display()
                def _to_back(ci=card_idx):
                    if len(self.zones[Zone.BACK]) >= 5:
                        messagebox.showinfo("Info", "Back is full (5/5).")
                        return
                    c = self.zones[Zone.HAND].pop(ci)
                    c.face_up = True
                    self.zones[Zone.BACK].append(c)
                    print(f"✓ Played {c.card_name} → Back")
                    refresh_display()
                menu.add_command(label="→ Centre", command=_to_centre)
                menu.add_command(label="→ Back", command=_to_back)
            def _to_archive(ci=card_idx):
                c = self.zones[Zone.HAND].pop(ci)
                c.face_up = True
                self.zones[Zone.ARCHIVE].append(c)
                print(f"✓ Discarded {c.card_name} → Archive")
                refresh_display()
            def _to_deck_top(ci=card_idx):
                c = self.zones[Zone.HAND].pop(ci)
                c.face_up = False
                self.zones[Zone.DECK].append(c)
                print(f"✓ {c.card_name} → Deck Top")
                refresh_display()
            def _to_deck_bottom(ci=card_idx):
                c = self.zones[Zone.HAND].pop(ci)
                c.face_up = False
                self.zones[Zone.DECK].insert(0, c)
                print(f"✓ {c.card_name} → Deck Bottom")
                refresh_display()
            def _view_hand_card(ci=card_idx):
                """View large card image and details in a popup."""
                c = self.zones[Zone.HAND][ci]
                dlg = tk.Toplevel(root)
                dlg.title(f"Card — {c.card_name}")
                dlg.geometry("400x650")
                dlg.transient(root)
                dlg._photos = []
                # Large card image
                try:
                    pil_img = self._load_card_image(
                        Card(c.card_number, c.card_name, c.card_type, c.image_file, True),
                        280, 400)
                    photo = ImageTk.PhotoImage(pil_img)
                    dlg._photos.append(photo)
                    tk.Label(dlg, image=photo, bg="#2a2a3e").pack(pady=10)
                except Exception:
                    pass
                # Card details
                self._load_db()
                data = self._card_index.get(c.card_number, {})
                info_lines = [f"Name: {c.card_name}",
                              f"Number: {c.card_number}",
                              f"Type: {c.card_type}"]
                if c.bloom_level:
                    info_lines.append(f"Bloom Level: {c.bloom_level}")
                colors = data.get('色', [])
                if colors:
                    info_lines.append(f"Color: {', '.join(colors)}")
                hp_val = data.get('HP')
                if hp_val:
                    info_lines.append(f"HP: {hp_val}")
                arts = data.get('arts', [])
                if arts:
                    for art in arts:
                        info_lines.append(f"Art: {art.get('name','')} [{art.get('damage','')}]")
                ability = data.get('能力テキスト', '')
                if ability:
                    info_lines.append(f"\nAbility:\n{ability}")
                ttk.Label(dlg, text="\n".join(info_lines),
                          font=("Helvetica", 10), wraplength=360,
                          justify=tk.LEFT).pack(padx=15, pady=5, anchor=tk.W)
                ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=5)
            menu.add_command(label="View Card", command=_view_hand_card)
            # Support card play option
            is_support = "サポート" in card.card_type
            if is_support:
                entry_data = SUPPORT_CARD_DB.get(card.card_number)
                if entry_data:
                    can_p, p_reason = support_executor.can_play(card.card_number)
                    summary = support_executor._summarize_actions(entry_data)
                    def _do_use_support(ci=card_idx):
                        _use_support_card(ci)
                    if can_p:
                        menu.add_command(label=f"⚡ Use Support  ({summary})",
                                         command=_do_use_support)
                    else:
                        menu.add_command(
                            label=f"⚡ Use Support  ✗ {p_reason}",
                            state="disabled")
                else:
                    menu.add_command(label="⚡ Use Support  (not in DB)",
                                     state="disabled")
            menu.add_separator()
            menu.add_command(label="→ Archive", command=_to_archive)
            menu.add_command(label="→ Deck Top", command=_to_deck_top)
            menu.add_command(label="→ Deck Bottom", command=_to_deck_bottom)
            menu.tk_popup(event.x_root, event.y_root)

        def _get_back_card_index(px, py):
            """Given playmat coords, return the index of the Back zone card clicked, or None."""
            bi = ZONE_DEFINITIONS[Zone.BACK]
            bx1, by1, bx2, by2 = bi.bbox
            if not (bx1 <= px <= bx2 and by1 <= py <= by2):
                return None
            cards = self.zones[Zone.BACK]
            if not cards:
                return None
            n = min(len(cards), 5)
            padding = 6
            w = bx2 - bx1
            card_w = (w - padding * (n + 1)) // n
            for i in range(n - 1, -1, -1):
                cx = bx1 + padding + i * (card_w + padding)
                if cx <= px <= cx + card_w:
                    return i
            return None

        def _get_centre_card(px, py):
            """Check if Centre zone was clicked."""
            ci = ZONE_DEFINITIONS[Zone.CENTRE]
            x1, y1, x2, y2 = ci.bbox
            if x1 <= px <= x2 and y1 <= py <= y2 and self.zones[Zone.CENTRE]:
                return 0
            return None

        def _get_collabo_card(px, py):
            """Check if Collabo zone was clicked."""
            ci = ZONE_DEFINITIONS[Zone.COLLABO]
            x1, y1, x2, y2 = ci.bbox
            if x1 <= px <= x2 and y1 <= py <= y2 and self.zones[Zone.COLLABO]:
                return 0
            return None

        # Bloom level validation
        BLOOM_VALID = {
            "Debut": ["1st"],
            "1st": ["1st", "2nd"],
            "2nd": ["2nd"],
        }

        def _bloom_card(zone, card_idx, event):
            """Show bloom dialog: select a holomen from hand to bloom onto this card."""
            target = self.zones[zone][card_idx]
            target_bl = target.bloom_level
            allowed = BLOOM_VALID.get(target_bl, [])
            if not allowed:
                messagebox.showinfo("Bloom",
                    f"{target.card_name} ({target_bl}) cannot be bloomed further.")
                return
            # Find eligible hand cards (same bloom level target, holomen type)
            eligible = []
            for i, hc in enumerate(self.zones[Zone.HAND]):
                if "ホロメン" not in hc.card_type:
                    continue
                if hc.bloom_level in allowed:
                    eligible.append((i, hc))
            if not eligible:
                messagebox.showinfo("Bloom",
                    f"No eligible cards in hand to bloom {target.card_name} "
                    f"({target_bl} → {allowed}).")
                return
            # Show selection popup
            dlg = tk.Toplevel(root)
            dlg.title(f"Bloom {target.card_name} ({target_bl})")
            dlg.geometry("600x420")
            dlg.transient(root)
            ttk.Label(dlg, text=f"Select a card to bloom onto {target.card_name} ({target_bl}):",
                      font=("Helvetica", 11, "bold")).pack(pady=5)
            dlg._photos = []
            scroll_frame = ttk.Frame(dlg)
            scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            grid_canvas = tk.Canvas(scroll_frame, bg="#1e1e2e")
            grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            grid_inner = ttk.Frame(grid_canvas)
            grid_canvas.create_window((0, 0), window=grid_inner, anchor=tk.NW)
            col = 0
            row = 0
            for hand_i, hc in eligible:
                cf = ttk.Frame(grid_inner)
                cf.grid(row=row, column=col, padx=6, pady=4)
                try:
                    pil_img = self._load_card_image(
                        Card(hc.card_number, hc.card_name, hc.card_type,
                             hc.image_file, True, hc.bloom_level), 90, 130)
                    photo = ImageTk.PhotoImage(pil_img)
                    dlg._photos.append(photo)
                    tk.Label(cf, image=photo, bg="#2a2a3e").pack()
                except Exception:
                    pass
                ttk.Label(cf, text=f"{hc.card_name}\n{hc.bloom_level}",
                          font=("Helvetica", 8), wraplength=90).pack()
                def do_bloom(hi=hand_i):
                    bloom_card = self.zones[Zone.HAND].pop(hi)
                    bloom_card.face_up = True
                    # Transfer yells and existing stack from old card
                    bloom_card.attached_yells = target.attached_yells[:]
                    bloom_card.damage = target.damage
                    # Stack old card underneath (keep its own stack too)
                    old = self.zones[zone].pop(card_idx)
                    old_stack = old.stacked_cards[:]
                    old.stacked_cards = []
                    old.attached_yells = []
                    bloom_card.stacked_cards = old_stack + [old]
                    self.zones[zone].insert(card_idx, bloom_card)
                    print(f"✓ Bloomed {old.card_name} ({old.bloom_level}) → "
                          f"{bloom_card.card_name} ({bloom_card.bloom_level}) "
                          f"[stack: {len(bloom_card.stacked_cards)}]")
                    dlg.destroy()
                    refresh_display()
                ttk.Button(cf, text="Bloom", command=do_bloom).pack(pady=2)
                col += 1
                if col >= 4:
                    col = 0
                    row += 1

        def _collabo_action(zone, card_idx):
            """Collabo: move card to Collabo, top deck card → Holo Power face-down."""
            if len(self.zones[Zone.COLLABO]) >= 1:
                messagebox.showinfo("Collabo", "Collabo position already occupied.")
                return
            card = self.zones[zone].pop(card_idx)
            card.face_up = True
            self.zones[Zone.COLLABO].append(card)
            print(f"✓ {card.card_name} → Collabo")
            # Top deck card → Holo Power face-down
            if self.zones[Zone.DECK]:
                hp_card = self.zones[Zone.DECK].pop()
                hp_card.face_up = False
                self.zones[Zone.HOLO_POWER].append(hp_card)
                print(f"✓ Deck top → Holo Power (face-down)")
            else:
                print("⚠ Deck empty — no card to Holo Power")
            refresh_display()

        def _force_collabo_action(zone, card_idx):
            """Force Collabo: move card to Collabo WITHOUT adding a Holo Power card."""
            if len(self.zones[Zone.COLLABO]) >= 1:
                messagebox.showinfo("Force Collabo", "Collabo position already occupied.")
                return
            card = self.zones[zone].pop(card_idx)
            card.face_up = True
            self.zones[Zone.COLLABO].append(card)
            print(f"✓ {card.card_name} → Collabo (forced, no Holo Power)")
            refresh_display()

        def _attach_yell_action(zone, card_idx):
            """Attach a yell from Yell Deck to a holomen on stage."""
            if not self.zones[Zone.YELL_DECK]:
                messagebox.showinfo("Yell", "Yell Deck is empty.")
                return
            target = self.zones[zone][card_idx]
            yell = self.zones[Zone.YELL_DECK].pop()
            yell.face_up = True
            target.attached_yells.append(yell)
            print(f"✓ Attached {yell.card_name} to {target.card_name}")
            refresh_display()

        def _show_back_card_menu(event, card_idx):
            """Context menu for a card in Back zone."""
            card = self.zones[Zone.BACK][card_idx]
            rest_label = "💤 Resting" if card.resting else "⚡ Active"
            menu = tk.Menu(root, tearoff=0)
            menu.add_command(label=f"── {card.card_name} ({card.bloom_level}) [{rest_label}] ──", state="disabled")
            menu.add_separator()
            menu.add_command(label="Bloom",
                command=lambda: _bloom_card(Zone.BACK, card_idx, event))
            if not card.resting:
                # Active holomen can collabo
                menu.add_command(label="Collabo (deck → Holo Power)",
                    command=lambda: _collabo_action(Zone.BACK, card_idx))
                menu.add_command(label="Force Collabo (no Holo Power)",
                    command=lambda: _force_collabo_action(Zone.BACK, card_idx))
                # Active → Rest
                def _set_rest(ci=card_idx):
                    self.zones[Zone.BACK][ci].resting = True
                    print(f"✓ {self.zones[Zone.BACK][ci].card_name} → Resting")
                    refresh_display()
                menu.add_command(label="Set Rest (horizontal)", command=_set_rest)
            else:
                # Resting → Active
                def _set_active(ci=card_idx):
                    self.zones[Zone.BACK][ci].resting = False
                    print(f"✓ {self.zones[Zone.BACK][ci].card_name} → Active")
                    refresh_display()
                menu.add_command(label="Set Active (vertical)", command=_set_active)
            menu.add_command(label="Attach Yell",
                command=lambda: _attach_yell_action(Zone.BACK, card_idx))
            menu.add_command(label="View Stack / Yells",
                command=lambda: _view_stack_popup(self.zones[Zone.BACK][card_idx]))
            menu.add_separator()
            def _to_centre():
                if len(self.zones[Zone.CENTRE]) >= 1:
                    messagebox.showinfo("Info", "Centre already occupied.")
                    return
                c = self.zones[Zone.BACK].pop(card_idx)
                c.resting = False
                self.zones[Zone.CENTRE].append(c)
                print(f"✓ {c.card_name} Back → Centre")
                refresh_display()
            def _to_archive():
                c = self.zones[Zone.BACK].pop(card_idx)
                _archive_card_flat(c)
                print(f"✓ {c.card_name} Back → Archive (whole stack)")
                refresh_display()
            def _to_archive_card_only():
                c = self.zones[Zone.BACK][card_idx]
                if not c.stacked_cards and not c.attached_yells:
                    # No stack, just archive normally
                    c = self.zones[Zone.BACK].pop(card_idx)
                    c.face_up = True
                    c.resting = False
                    self.zones[Zone.ARCHIVE].append(c)
                    print(f"✓ {c.card_name} Back → Archive")
                else:
                    # Pop the top card, leave stack behind
                    top = self.zones[Zone.BACK][card_idx]
                    if top.stacked_cards:
                        # Promote next stacked card
                        new_top = top.stacked_cards.pop()
                        new_top.attached_yells = top.attached_yells
                        new_top.stacked_cards = top.stacked_cards
                        new_top.resting = top.resting
                        new_top.damage = top.damage
                        new_top.face_up = True
                        self.zones[Zone.BACK][card_idx] = new_top
                        top.attached_yells = []
                        top.stacked_cards = []
                        top.face_up = True
                        top.resting = False
                        self.zones[Zone.ARCHIVE].append(top)
                        print(f"✓ {top.card_name} → Archive (promoted {new_top.card_name})")
                    else:
                        c = self.zones[Zone.BACK].pop(card_idx)
                        _archive_card_flat(c)
                        print(f"✓ {c.card_name} Back → Archive (whole stack)")
                refresh_display()
            menu.add_command(label="→ Centre", command=_to_centre)
            menu.add_command(label="→ Archive (all)", command=_to_archive)
            menu.add_command(label="→ Archive (card only)", command=_to_archive_card_only)
            menu.tk_popup(event.x_root, event.y_root)

        def _show_stage_card_menu(event, zone, card_idx):
            """Context menu for Centre or Collabo card."""
            card = self.zones[zone][card_idx]
            zname = ZONE_DEFINITIONS[zone].display_name
            menu = tk.Menu(root, tearoff=0)
            menu.add_command(label=f"── {card.card_name} ({card.bloom_level}) [{zname}] ──", state="disabled")
            menu.add_separator()
            menu.add_command(label="Bloom",
                command=lambda: _bloom_card(zone, card_idx, event))
            menu.add_command(label="Attach Yell",
                command=lambda: _attach_yell_action(zone, card_idx))
            menu.add_command(label="View Stack / Yells",
                command=lambda: _view_stack_popup(self.zones[zone][card_idx]))
            menu.add_separator()
            def _to_back():
                if len(self.zones[Zone.BACK]) >= 5:
                    messagebox.showinfo("Info", "Back is full.")
                    return
                c = self.zones[zone].pop(card_idx)
                self.zones[Zone.BACK].append(c)
                print(f"✓ {c.card_name} {zname} → Back")
                refresh_display()
            def _to_archive():
                c = self.zones[zone].pop(card_idx)
                _archive_card_flat(c)
                print(f"✓ {c.card_name} {zname} → Archive (whole stack)")
                refresh_display()
            def _to_archive_card_only():
                c = self.zones[zone][card_idx]
                if not c.stacked_cards and not c.attached_yells:
                    c = self.zones[zone].pop(card_idx)
                    c.face_up = True
                    c.resting = False
                    self.zones[Zone.ARCHIVE].append(c)
                    print(f"✓ {c.card_name} {zname} → Archive")
                else:
                    top = self.zones[zone][card_idx]
                    if top.stacked_cards:
                        new_top = top.stacked_cards.pop()
                        new_top.attached_yells = top.attached_yells
                        new_top.stacked_cards = top.stacked_cards
                        new_top.resting = top.resting
                        new_top.damage = top.damage
                        new_top.face_up = True
                        self.zones[zone][card_idx] = new_top
                        top.attached_yells = []
                        top.stacked_cards = []
                        top.face_up = True
                        top.resting = False
                        self.zones[Zone.ARCHIVE].append(top)
                        print(f"✓ {top.card_name} → Archive (promoted {new_top.card_name})")
                    else:
                        c = self.zones[zone].pop(card_idx)
                        _archive_card_flat(c)
                        print(f"✓ {c.card_name} {zname} → Archive (whole stack)")
                refresh_display()
            menu.add_command(label="→ Back", command=_to_back)
            menu.add_command(label="→ Archive (all)", command=_to_archive)
            menu.add_command(label="→ Archive (card only)", command=_to_archive_card_only)
            menu.tk_popup(event.x_root, event.y_root)

        def on_canvas_click(event):
            """Determine which zone/card was clicked."""
            px = event.x / scale
            py = event.y / scale

            # Hand card
            hand_idx = _get_hand_card_index(px, py)
            if hand_idx is not None:
                _show_hand_card_menu(event, hand_idx)
                return

            # Back card
            back_idx = _get_back_card_index(px, py)
            if back_idx is not None:
                _show_back_card_menu(event, back_idx)
                return

            # Centre card
            centre_idx = _get_centre_card(px, py)
            if centre_idx is not None:
                _show_stage_card_menu(event, Zone.CENTRE, centre_idx)
                return

            # Collabo card
            collabo_idx = _get_collabo_card(px, py)
            if collabo_idx is not None:
                _show_stage_card_menu(event, Zone.COLLABO, collabo_idx)
                return

            clicked_zone = None
            for zone in Zone:
                info = ZONE_DEFINITIONS[zone]
                x1, y1, x2, y2 = info.bbox
                if x1 <= px <= x2 and y1 <= py <= y2:
                    clicked_zone = zone
                    break

            selected_zone[0] = clicked_zone
            refresh_display()

        canvas.bind("<Button-1>", on_canvas_click)

        # Initial render
        refresh_display()

        root.mainloop()


# ── Support Card Testing ──────────────────────────────────────────────

def test_support_cards(card_numbers: list[str] = None):
    """
    Interactive test harness for support card behaviour.

    Sets up a realistic board state, then plays each requested support card
    through the SupportCardExecutor, printing before/after snapshots so you
    can verify correctness.

    Usage:
        python playmat_manager.py --test-support hSD01-016 hBP05-080
        python playmat_manager.py --test-support   # runs default test suite
    """
    from support_card_db import SupportCardExecutor, SUPPORT_CARD_DB

    # ── Default test suite (the two user examples + a few more) ──────
    if not card_numbers:
        card_numbers = [
            "hSD01-016",   # 春先のどか → draw 3 [LIMITED]
            "hBP05-080",   # SorAZセレブレーション → draw 2, view top 5 pick 1st [LIMITED]
            "hSD01-017",   # マネちゃん → shuffle hand, draw 5 [LIMITED]
            "hBP01-106",   # あとは任せた！ → swap own center ↔ back
            "hSD01-020",   # ホロリスの輪 → dice roll, >=3 send archive cheer
            "hSD01-019",   # スゴイパソコン → cost 1 cheer, search deck 1st/2nd [LIMITED]
            "hBP01-108",   # じゃあ敵だね → swap opponent center ↔ back [LIMITED]
        ]

    pm = PlaymatManager()

    # ── Helpers ──────────────────────────────────────────────────────

    def build_test_board(pm: PlaymatManager):
        """Set up a realistic board state for testing."""
        pm.clear_all()

        # Deck – mix of holomen and supports (30 cards)
        deck_cards = [
            "hSD01-003", "hSD01-004", "hSD01-005", "hSD01-006",  # Debut holomen
            "hSD01-007", "hSD01-008", "hSD01-009", "hSD01-010",  # More Debut
            "hSD01-011", "hSD01-012", "hSD01-013",               # 1st holomen
            "hBP01-009", "hBP01-011", "hBP01-015",               # More holomen
            "hBP01-017", "hBP01-018", "hBP01-021",
            "hSD01-016", "hSD01-017", "hSD01-018",               # Support cards
            "hSD01-019", "hSD01-020", "hSD01-021",
            "hBP01-102", "hBP01-104", "hBP01-106",
            "hBP01-108", "hBP01-109", "hBP01-110",
            "hBP05-080",
        ]
        for cn in deck_cards:
            try:
                pm.place_card_by_number(Zone.DECK, cn)
            except Exception:
                pass  # skip cards not in DB
        pm.shuffle_deck()

        # Oshi
        try:
            pm.place_card_by_number(Zone.OSHI, "hSD01-001")
        except Exception:
            pass

        # Centre + Back holomen
        try:
            pm.place_card_by_number(Zone.CENTRE, "hSD01-011")
        except Exception:
            pass
        for cn in ["hSD01-004", "hSD01-009"]:
            try:
                pm.place_card_by_number(Zone.BACK, cn)
            except Exception:
                pass

        # Life (5 cards face-down)
        for cn in ["hBP01-025", "hBP01-028", "hBP01-029", "hBP01-033", "hBP01-034"]:
            try:
                pm.place_card_by_number(Zone.LIFE, cn)
            except Exception:
                pass

        # Yell deck (6 cheer cards)
        yell_cards = ["hSD01-016", "hSD01-017", "hSD01-018",
                      "hSD01-019", "hSD01-020", "hSD01-021"]
        for cn in yell_cards:
            try:
                pm.place_card_by_number(Zone.YELL_DECK, cn)
            except Exception:
                pass

        # Holo power (2 cards)
        try:
            pm.place_card_by_number(Zone.HOLO_POWER, "hBP01-034")
            pm.place_card_by_number(Zone.HOLO_POWER, "hBP01-033")
        except Exception:
            pass

        # Archive (a few cards to test archive-search effects)
        for cn in ["hBP01-011", "hBP01-015"]:
            try:
                pm.place_card_by_number(Zone.ARCHIVE, cn)
            except Exception:
                pass

        # Hand – 3 filler cards
        for cn in ["hSD01-005", "hSD01-006", "hSD01-007"]:
            try:
                pm.place_card_by_number(Zone.HAND, cn)
            except Exception:
                pass

    def snapshot(pm: PlaymatManager, label: str = ""):
        """Print a compact board snapshot."""
        print(f"\n{'─'*60}")
        if label:
            print(f"  📋 {label}")
            print(f"{'─'*60}")
        for zone in Zone:
            cards = pm.zones[zone]
            if not cards:
                continue
            names = [f"{c.card_name}({c.card_number})" for c in cards]
            display = ZONE_DEFINITIONS[zone].display_name
            print(f"  {display:12s} [{len(cards):2d}]: {', '.join(names)}")
        print(f"{'─'*60}")

    # ── Run tests ────────────────────────────────────────────────────

    separator = "═" * 70
    print(f"\n{separator}")
    print(f"  hOCG SUPPORT CARD TEST HARNESS")
    print(f"  Testing {len(card_numbers)} card(s)")
    print(f"{separator}")

    results = []

    for i, cn in enumerate(card_numbers, 1):
        entry = SUPPORT_CARD_DB.get(cn)
        if not entry:
            print(f"\n⚠ Card {cn} not found in SUPPORT_CARD_DB — skipping")
            results.append({"card": cn, "status": "NOT_FOUND"})
            continue

        print(f"\n{separator}")
        print(f"  TEST {i}/{len(card_numbers)}: {entry['card_name']} ({cn})")
        print(f"  Type: {entry['card_type']}")
        print(f"  Effect: {entry.get('raw_text', 'N/A')}")
        print(f"{separator}")

        # Fresh board + fresh executor per test
        build_test_board(pm)
        executor = SupportCardExecutor(pm)
        executor.start_turn()

        # Put the support card in hand
        try:
            pm.place_card_by_number(Zone.HAND, cn)
        except Exception as e:
            print(f"  ⚠ Could not create card {cn}: {e}")
            results.append({"card": cn, "status": "CREATE_FAILED", "error": str(e)})
            continue

        # Take snapshot before
        hand_before = [c.card_number for c in pm.zones[Zone.HAND]]
        deck_before = len(pm.zones[Zone.DECK])
        archive_before = len(pm.zones[Zone.ARCHIVE])
        hp_before = len(pm.zones[Zone.HOLO_POWER])
        snapshot(pm, f"BEFORE playing {entry['card_name']}")

        # Check if playable
        can, reason = executor.can_play(cn)
        print(f"\n  can_play? {'✓ YES' if can else '✗ NO'} — {reason}")

        if not can:
            print(f"  → Skipping execution (card not playable: {reason})")
            results.append({"card": cn, "status": "NOT_PLAYABLE", "reason": reason})
            continue

        # Play the card
        result = executor.play_support(cn)

        # Take snapshot after
        snapshot(pm, f"AFTER playing {entry['card_name']}")

        # Compute deltas
        hand_after = [c.card_number for c in pm.zones[Zone.HAND]]
        deck_after = len(pm.zones[Zone.DECK])
        archive_after = len(pm.zones[Zone.ARCHIVE])
        hp_after = len(pm.zones[Zone.HOLO_POWER])

        print(f"\n  📊 Deltas:")
        print(f"     Hand:       {len(hand_before)} → {len(hand_after)} "
              f"(net {len(hand_after) - len(hand_before):+d})")
        print(f"     Deck:       {deck_before} → {deck_after} "
              f"(net {deck_after - deck_before:+d})")
        print(f"     Archive:    {archive_before} → {archive_after} "
              f"(net {archive_after - archive_before:+d})")
        print(f"     Holo Power: {hp_before} → {hp_after} "
              f"(net {hp_after - hp_before:+d})")

        # Verify the support card ended up in archive
        in_archive = any(c.card_number == cn for c in pm.zones[Zone.ARCHIVE])
        in_hand = any(c.card_number == cn for c in pm.zones[Zone.HAND])
        print(f"     Card in archive? {'✓' if in_archive else '✗'}  "
              f"Still in hand? {'✗ BUG!' if in_hand else '✓ (removed)'}")

        # Verify LIMITED tracking
        if entry.get("is_limited"):
            print(f"     LIMITED tracked? {'✓' if executor._limited_used_this_turn else '✗ BUG!'}")
            # Try playing another LIMITED — should fail
            can2, reason2 = executor.can_play("hSD01-016")
            print(f"     2nd LIMITED blocked? {'✓' if not can2 else '✗ BUG!'} — {reason2}")

        # Active modifiers
        mods = executor.get_turn_modifiers()
        if mods:
            print(f"     Turn modifiers: {mods}")

        # Store result
        results.append({
            "card": cn,
            "name": entry["card_name"],
            "status": "OK" if result["success"] else "FAILED",
            "actions": result["actions_taken"],
            "hand_delta": len(hand_after) - len(hand_before),
            "deck_delta": deck_after - deck_before,
        })

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n\n{separator}")
    print(f"  TEST SUMMARY")
    print(f"{separator}")
    for r in results:
        status_icon = {"OK": "✅", "FAILED": "❌", "NOT_FOUND": "⚠️",
                       "NOT_PLAYABLE": "⏭️", "CREATE_FAILED": "💥"}.get(r["status"], "?")
        card_name = r.get("name", r["card"])
        print(f"  {status_icon} {r['card']} {card_name:30s} — {r['status']}")
        if r.get("hand_delta") is not None:
            print(f"      Hand {r['hand_delta']:+d}  Deck {r['deck_delta']:+d}")
    print(f"{separator}")

    passed = sum(1 for r in results if r["status"] == "OK")
    total = len(results)
    print(f"\n  {passed}/{total} tests passed\n")

    return results


# ── CLI + Demo ───────────────────────────────────────────────────────

def run_demo():
    """Run a demo placing some cards on the playmat."""
    pm = PlaymatManager()

    print("\n▶ Setting up a demo board...\n")

    # Place oshi
    pm.place_card_by_number(Zone.OSHI, "hSD01-001")

    # Place centre holomen
    pm.place_card_by_number(Zone.CENTRE, "hSD01-011")

    # Place collabo holomen
    pm.place_card_by_number(Zone.COLLABO, "hBP01-009")

    # Place some back stage holomen
    pm.place_card_by_number(Zone.BACK, "hSD01-004")
    pm.place_card_by_number(Zone.BACK, "hSD01-009")

    # Add some life cards (face-down)
    for cn in ["hBP01-015", "hBP01-017", "hBP01-018", "hBP01-021", "hBP01-024"]:
        pm.place_card_by_number(Zone.LIFE, cn)

    # Some deck cards
    for cn in ["hBP01-025", "hBP01-028", "hBP01-029"]:
        pm.place_card_by_number(Zone.DECK, cn)

    # Yell deck
    pm.place_card_by_number(Zone.YELL_DECK, "hSD01-016")
    pm.place_card_by_number(Zone.YELL_DECK, "hSD01-017")

    # Archive
    pm.place_card_by_number(Zone.ARCHIVE, "hBP01-011")

    # Holo power
    pm.place_card_by_number(Zone.HOLO_POWER, "hBP01-034")

    pm.print_board()

    # Render
    output = os.path.join(SCRIPT_DIR, "board_render.jpg")
    pm.render(output_path=output)

    return pm


def main():
    import argparse

    parser = argparse.ArgumentParser(description="hOCG Playmat Manager")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample cards")
    parser.add_argument("--render", action="store_true", help="Render board as image")
    parser.add_argument("--gui", action="store_true", help="Launch interactive GUI (default)")
    parser.add_argument("--output", "-o", default=None, help="Output image path for --render")
    parser.add_argument("--test-support", nargs="*", default=None, metavar="CARD",
                        help="Test support card behaviour. Optionally pass card numbers "
                             "(e.g. hSD01-016 hBP05-080). With no args, runs default suite.")
    args = parser.parse_args()

    if args.test_support is not None:
        test_support_cards(args.test_support if args.test_support else None)
    elif args.demo:
        pm = run_demo()
        if args.gui:
            pm.launch_gui()
    elif args.render:
        pm = PlaymatManager()
        output = args.output or os.path.join(SCRIPT_DIR, "board_render.jpg")
        pm.render(output_path=output)
    else:
        # Default: launch GUI
        pm = PlaymatManager()
        pm.launch_gui()


if __name__ == "__main__":
    main()
