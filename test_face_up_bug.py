"""
Test to reproduce the face_up bugs:
1. hBP01-104 second use makes first found card face_down
2. After bloom, some hand cards become face_down
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from game_tools.playmat_manager import PlaymatManager, Zone, Card
from game_tools.support_card_db import SupportCardExecutor, SUPPORT_CARD_DB
from game_tools.game_engine import Match, Player


def dump_face_up(pm, label=""):
    print(f"\n=== {label} ===")
    for z in [Zone.HAND, Zone.CENTRE, Zone.BACK, Zone.COLLABO]:
        cards = pm.zones[z]
        if cards:
            for i, c in enumerate(cards):
                print(f"  {z.value}[{i}]: {c.card_name} ({c.card_number}) face_up={c.face_up}")
    print()


def test_search_deck_to_stage_twice():
    """Simulate playing hBP01-104 twice and check face_up state."""
    print("\n" + "="*70)
    print("TEST: Search deck to stage (hBP01-104) twice")
    print("="*70)

    # Create a Match and set up a minimal game state
    match = Match()
    p1 = match.add_player("TestPlayer1")
    p2 = match.add_player("TestPlayer2")
    pid1 = p1.id

    pm = p1.playmat

    # Manually set up cards instead of loading from decklog
    # Put some Debut holomen in the deck
    for i in range(5):
        card = Card(
            card_number=f"hSD01-00{i+1}",
            card_name=f"Debut Holomen {i+1}",
            card_type="ホロメン",
            image_file="test.png",
            face_up=False,
            bloom_level="Debut",
        )
        pm.zones[Zone.DECK].append(card)

    # Put some non-holomen filler in deck
    for i in range(10):
        card = Card(
            card_number=f"FILLER-{i+1:03d}",
            card_name=f"Filler Card {i+1}",
            card_type="サポート・アイテム",
            image_file="test.png",
            face_up=False,
        )
        pm.zones[Zone.DECK].append(card)

    # Put two copies of hBP01-104 in hand
    for i in range(2):
        support_card = Card(
            card_number="hBP01-104",
            card_name="ふつうのパソコン",
            card_type="サポート・アイテム",
            image_file="test.png",
            face_up=True,
        )
        pm.zones[Zone.HAND].append(support_card)

    # Put some other cards in hand
    for i in range(3):
        hand_card = Card(
            card_number=f"HAND-{i+1:03d}",
            card_name=f"Hand Card {i+1}",
            card_type="ホロメン",
            image_file="test.png",
            face_up=True,
            bloom_level="Debut",
        )
        pm.zones[Zone.HAND].append(hand_card)

    # Put an oshi (required for some checks)
    oshi = Card(
        card_number="hSD01-001",
        card_name="Oshi",
        card_type="推しホロメン",
        image_file="test.png",
        face_up=True,
    )
    pm.zones[Zone.OSHI].append(oshi)

    dump_face_up(pm, "Initial state")

    # Simulate the match being in playing state
    match.game_state = "playing"
    match.turn_player_id = pid1
    match.step_index = 3  # main step

    # ── FIRST USE of hBP01-104 ──
    print("\n>>> Playing first hBP01-104...")
    result = match.apply_action(pid1, {"type": "play_support", "card_number": "hBP01-104"})
    print(f"Result: success={result.get('success')}")

    dump_face_up(pm, "After first play_support (before pick)")

    # Check pending
    pending = match.step_state.get("pending_support")
    if pending and pending["picks"]:
        pick = pending["picks"][0]
        print(f"Pick: {pick['title']}, {len(pick['cards'])} cards")
        # Find a Debut holomen to pick
        selectable = pick.get("selectable_numbers", [])
        print(f"Selectable: {selectable}")
        if selectable:
            chosen = selectable[0]
            print(f"Choosing: {chosen}")
            result2 = match.apply_action(pid1, {
                "type": "pick_support_cards",
                "pick_id": pick["pick_id"],
                "card_numbers": [chosen],
            })
            print(f"Pick result: success={result2.get('success')}")

    dump_face_up(pm, "After first pick resolved")

    # Verify back stage cards
    back_cards = pm.zones[Zone.BACK]
    print(f"BACK stage cards: {len(back_cards)}")
    for i, c in enumerate(back_cards):
        print(f"  [{i}] {c.card_name} ({c.card_number}) face_up={c.face_up}")
        assert c.face_up, f"BUG: {c.card_name} on BACK should be face_up!"

    # Verify hand cards
    hand_cards = pm.zones[Zone.HAND]
    print(f"\nHAND cards: {len(hand_cards)}")
    for i, c in enumerate(hand_cards):
        print(f"  [{i}] {c.card_name} ({c.card_number}) face_up={c.face_up}")
        assert c.face_up, f"BUG: {c.card_name} in HAND should be face_up!"

    # ── SECOND USE of hBP01-104 ──
    print("\n\n>>> Playing second hBP01-104...")
    result3 = match.apply_action(pid1, {"type": "play_support", "card_number": "hBP01-104"})
    print(f"Result: success={result3.get('success')}")

    dump_face_up(pm, "After second play_support (before pick)")

    # Check BACK card from first use is still face_up
    print(f"Back cards after second play (before pick):")
    for i, c in enumerate(pm.zones[Zone.BACK]):
        print(f"  [{i}] {c.card_name} ({c.card_number}) face_up={c.face_up}")
        if not c.face_up:
            print(f"  *** BUG FOUND: {c.card_name} became face_down after second play! ***")

    # Check hand cards
    print(f"\nHand cards after second play (before pick):")
    for i, c in enumerate(pm.zones[Zone.HAND]):
        print(f"  [{i}] {c.card_name} ({c.card_number}) face_up={c.face_up}")
        if not c.face_up:
            print(f"  *** BUG FOUND: {c.card_name} in hand became face_down! ***")

    # Resolve second pick
    pending2 = match.step_state.get("pending_support")
    if pending2 and pending2["picks"]:
        pick2 = pending2["picks"][0]
        selectable2 = pick2.get("selectable_numbers", [])
        if selectable2:
            chosen2 = selectable2[0]
            print(f"\nChoosing: {chosen2}")
            result4 = match.apply_action(pid1, {
                "type": "pick_support_cards",
                "pick_id": pick2["pick_id"],
                "card_numbers": [chosen2],
            })
            print(f"Pick result: success={result4.get('success')}")

    dump_face_up(pm, "After second pick resolved")

    # Final verification
    errors = []
    for i, c in enumerate(pm.zones[Zone.BACK]):
        if not c.face_up:
            errors.append(f"BACK[{i}] {c.card_name} face_up=False")
    for i, c in enumerate(pm.zones[Zone.HAND]):
        if not c.face_up:
            errors.append(f"HAND[{i}] {c.card_name} face_up=False")

    if errors:
        print("\n*** BUGS FOUND ***")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n✓ All cards have correct face_up state!")

    # Also check serialized state
    state = match.get_filtered_state(pid1)
    my_zones = state["players"][pid1]["zones"]
    print("\nSerialized state check:")
    for zname in ["back", "hand"]:
        cards = my_zones.get(zname, [])
        for i, cd in enumerate(cards):
            if not cd.get("face_up"):
                print(f"  *** SERIALIZED BUG: {zname}[{i}] {cd.get('card_name')} face_up={cd.get('face_up')} ***")


def test_bloom_hand_face_up():
    """Test that hand cards don't become face_down after bloom."""
    print("\n" + "="*70)
    print("TEST: Bloom doesn't affect hand cards face_up")
    print("="*70)

    match = Match()
    p1 = match.add_player("TestPlayer1")
    p2 = match.add_player("TestPlayer2")
    pid1 = p1.id
    pm = p1.playmat

    # Put a Debut holomen on centre
    debut = Card(
        card_number="hSD01-003",
        card_name="Centre Debut",
        card_type="ホロメン",
        image_file="test.png",
        face_up=True,
        bloom_level="Debut",
    )
    pm.zones[Zone.CENTRE].append(debut)

    # Put a 1st Bloom holomen in hand (matching card for bloom)
    bloom_card = Card(
        card_number="hSD01-004",
        card_name="1st Bloom Card",
        card_type="ホロメン",
        image_file="test.png",
        face_up=True,
        bloom_level="1st",
    )
    pm.zones[Zone.HAND].append(bloom_card)

    # Put some other cards in hand
    for i in range(4):
        c = Card(
            card_number=f"HAND-{i+1:03d}",
            card_name=f"Hand Card {i+1}",
            card_type="ホロメン",
            image_file="test.png",
            face_up=True,
            bloom_level="Debut",
        )
        pm.zones[Zone.HAND].append(c)

    # Put an oshi
    oshi = Card(
        card_number="hSD01-001", card_name="Oshi",
        card_type="推しホロメン", image_file="test.png",
        face_up=True,
    )
    pm.zones[Zone.OSHI].append(oshi)

    dump_face_up(pm, "Before bloom")

    match.game_state = "playing"
    match.turn_player_id = pid1
    match.step_index = 3  # main

    # Bloom
    result = match.apply_action(pid1, {
        "type": "bloom",
        "zone": "centre",
        "card_index": 0,
        "hand_card_number": "hSD01-004",
    })
    print(f"Bloom result: {result}")

    dump_face_up(pm, "After bloom")

    # Check hand cards
    errors = []
    for i, c in enumerate(pm.zones[Zone.HAND]):
        if not c.face_up:
            errors.append(f"HAND[{i}] {c.card_name} face_up=False")
    for i, c in enumerate(pm.zones[Zone.CENTRE]):
        if not c.face_up:
            errors.append(f"CENTRE[{i}] {c.card_name} face_up=False")

    if errors:
        print("\n*** BUGS FOUND ***")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n✓ All cards have correct face_up state after bloom!")


def test_search_then_bloom():
    """Combined: search to stage then bloom, check hand cards."""
    print("\n" + "="*70)
    print("TEST: Search deck to stage → then bloom → check hand")
    print("="*70)

    match = Match()
    p1 = match.add_player("TestPlayer1")
    p2 = match.add_player("TestPlayer2")
    pid1 = p1.id
    pm = p1.playmat

    # Set up deck with Debut holomen
    for i in range(10):
        c = Card(
            card_number=f"DEBUT-{i+1:03d}",
            card_name=f"Deck Debut {i+1}",
            card_type="ホロメン",
            image_file="test.png",
            face_up=False,
            bloom_level="Debut",
        )
        pm.zones[Zone.DECK].append(c)
    for i in range(10):
        c = Card(
            card_number=f"FILLER-{i+1:03d}",
            card_name=f"Filler {i+1}",
            card_type="サポート・アイテム",
            image_file="test.png",
            face_up=False,
        )
        pm.zones[Zone.DECK].append(c)

    # Hand: 1 support + 1 bloom card + hand fillers
    support = Card(
        card_number="hBP01-104", card_name="ふつうのパソコン",
        card_type="サポート・アイテム", image_file="test.png", face_up=True,
    )
    pm.zones[Zone.HAND].append(support)

    bloom_card = Card(
        card_number="BLOOM-001", card_name="1st Bloom",
        card_type="ホロメン", image_file="test.png", face_up=True,
        bloom_level="1st",
    )
    pm.zones[Zone.HAND].append(bloom_card)

    for i in range(3):
        c = Card(
            card_number=f"HAND-{i+1:03d}", card_name=f"Hand Card {i+1}",
            card_type="ホロメン", image_file="test.png", face_up=True,
            bloom_level="Debut",
        )
        pm.zones[Zone.HAND].append(c)

    # Centre holomen (bloom target)
    centre = Card(
        card_number="CENTRE-001", card_name="Centre Debut",
        card_type="ホロメン", image_file="test.png", face_up=True,
        bloom_level="Debut",
    )
    pm.zones[Zone.CENTRE].append(centre)

    # Oshi
    oshi = Card(
        card_number="hSD01-001", card_name="Oshi",
        card_type="推しホロメン", image_file="test.png", face_up=True,
    )
    pm.zones[Zone.OSHI].append(oshi)

    match.game_state = "playing"
    match.turn_player_id = pid1
    match.step_index = 3  # main

    dump_face_up(pm, "Initial state")

    # Play support
    print("\n>>> Playing hBP01-104...")
    r1 = match.apply_action(pid1, {"type": "play_support", "card_number": "hBP01-104"})
    print(f"Result: {r1.get('success')}")

    # Resolve pick
    pending = match.step_state.get("pending_support")
    if pending and pending["picks"]:
        pick = pending["picks"][0]
        selectable = pick.get("selectable_numbers", [])
        if selectable:
            r2 = match.apply_action(pid1, {
                "type": "pick_support_cards",
                "pick_id": pick["pick_id"],
                "card_numbers": [selectable[0]],
            })
            print(f"Pick result: {r2.get('success')}")

    dump_face_up(pm, "After search+pick")

    # Now bloom
    print("\n>>> Blooming...")
    r3 = match.apply_action(pid1, {
        "type": "bloom",
        "zone": "centre",
        "card_index": 0,
        "hand_card_number": "BLOOM-001",
    })
    print(f"Bloom result: {r3.get('success')}")

    dump_face_up(pm, "After bloom")

    # Check all hand/stage face_up
    errors = []
    for i, c in enumerate(pm.zones[Zone.HAND]):
        if not c.face_up:
            errors.append(f"HAND[{i}] {c.card_name} ({c.card_number}) face_up=False")
    for z in [Zone.CENTRE, Zone.BACK]:
        for i, c in enumerate(pm.zones[z]):
            if not c.face_up:
                errors.append(f"{z.value}[{i}] {c.card_name} ({c.card_number}) face_up=False")

    if errors:
        print("\n*** BUGS FOUND ***")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n✓ All cards correct after search + bloom!")


def test_duplicate_cards_in_deck():
    """Test with DUPLICATE cards (same card_number) — this is the real scenario."""
    print("\n" + "="*70)
    print("TEST: Duplicate cards in deck (same card_number)")
    print("="*70)

    match = Match()
    p1 = match.add_player("TestPlayer1")
    p2 = match.add_player("TestPlayer2")
    pid1 = p1.id
    pm = p1.playmat

    # Put 4 copies of the SAME Debut holomen in deck
    for i in range(4):
        card = Card(
            card_number="hBP01-001",
            card_name="Tokino Sora",
            card_type="ホロメン",
            image_file="hBP01-001.png",
            face_up=False,
            bloom_level="Debut",
        )
        pm.zones[Zone.DECK].append(card)

    # Add filler
    for i in range(10):
        card = Card(
            card_number=f"FILLER-{i+1:03d}",
            card_name=f"Filler {i+1}",
            card_type="サポート・アイテム",
            image_file="test.png",
            face_up=False,
        )
        pm.zones[Zone.DECK].append(card)

    # Two copies of hBP01-104 in hand
    for i in range(2):
        support_card = Card(
            card_number="hBP01-104",
            card_name="ふつうのパソコン",
            card_type="サポート・アイテム",
            image_file="test.png",
            face_up=True,
        )
        pm.zones[Zone.HAND].append(support_card)

    # Some hand cards
    for i in range(3):
        c = Card(
            card_number=f"HAND-{i+1:03d}",
            card_name=f"Hand Card {i+1}",
            card_type="ホロメン",
            image_file="test.png",
            face_up=True,
            bloom_level="Debut",
        )
        pm.zones[Zone.HAND].append(c)

    # Oshi
    oshi = Card(
        card_number="hSD01-001", card_name="Oshi",
        card_type="推しホロメン", image_file="test.png", face_up=True,
    )
    pm.zones[Zone.OSHI].append(oshi)

    match.game_state = "playing"
    match.turn_player_id = pid1
    match.step_index = 3  # main

    # Print object ids to track identity
    deck = pm.zones[Zone.DECK]
    print(f"\nDeck debut holomen object ids:")
    for c in deck:
        if c.card_number == "hBP01-001":
            print(f"  id={id(c)} {c.card_name}")

    # ── FIRST USE ──
    print("\n>>> Playing first hBP01-104...")
    r1 = match.apply_action(pid1, {"type": "play_support", "card_number": "hBP01-104"})
    print(f"Result: {r1.get('success')}")

    # Get refs before pick
    card_refs = match.step_state.get("_support_card_refs", {})
    pending = match.step_state.get("pending_support")
    if pending and pending["picks"]:
        pick = pending["picks"][0]
        pick_id = pick["pick_id"]
        available = card_refs.get(pick_id, [])
        # Find the hBP01-001 card objects in available
        available_debuts = [c for c in available if c.card_number == "hBP01-001"]
        print(f"\nAvailable debut objects (from deck capture):")
        for c in available_debuts:
            print(f"  id={id(c)} face_up={c.face_up}")

        print(f"\nDeck debut objects right now:")
        for c in pm.zones[Zone.DECK]:
            if c.card_number == "hBP01-001":
                print(f"  id={id(c)} face_up={c.face_up}")

        # Pick the first hBP01-001
        r2 = match.apply_action(pid1, {
            "type": "pick_support_cards",
            "pick_id": pick_id,
            "card_numbers": ["hBP01-001"],
        })
        print(f"\nPick result: {r2.get('success')}")

    print(f"\nAfter first pick:")
    print(f"  BACK cards:")
    for c in pm.zones[Zone.BACK]:
        print(f"    id={id(c)} {c.card_name} face_up={c.face_up}")
    print(f"  Deck debut cards:")
    for c in pm.zones[Zone.DECK]:
        if c.card_number == "hBP01-001":
            print(f"    id={id(c)} face_up={c.face_up}")

    # Check: is any BACK card object ALSO in the deck?
    for bc in pm.zones[Zone.BACK]:
        for dc in pm.zones[Zone.DECK]:
            if bc is dc:
                print(f"\n  *** CRITICAL: BACK card id={id(bc)} is also in DECK! ***")

    # ── SECOND USE ──
    print("\n\n>>> Playing second hBP01-104...")
    r3 = match.apply_action(pid1, {"type": "play_support", "card_number": "hBP01-104"})
    print(f"Result: {r3.get('success')}")

    print(f"\nAfter second play (before pick):")
    print(f"  BACK cards:")
    for c in pm.zones[Zone.BACK]:
        print(f"    id={id(c)} {c.card_name} face_up={c.face_up}")
        if not c.face_up:
            print(f"    *** BUG: BACK card became face_down! ***")

    print(f"  HAND cards:")
    for c in pm.zones[Zone.HAND]:
        print(f"    id={id(c)} {c.card_name} face_up={c.face_up}")
        if not c.face_up:
            print(f"    *** BUG: HAND card is face_down! ***")


def test_search_to_hand_then_bloom_duplicates():
    """Search deck to hand with duplicates, then bloom. 
    Tests both bugs with a real scenario."""
    print("\n" + "="*70)
    print("TEST: Search → hand (duplicates) then bloom")
    print("="*70)

    match = Match()
    p1 = match.add_player("TestPlayer1")
    p2 = match.add_player("TestPlayer2")
    pid1 = p1.id
    pm = p1.playmat

    # 4 copies of same Debut holomen in deck
    for i in range(4):
        c = Card(
            card_number="hBP01-001", card_name="Tokino Sora",
            card_type="ホロメン", image_file="hBP01-001.png",
            face_up=False, bloom_level="Debut",
        )
        pm.zones[Zone.DECK].append(c)
    # Filler
    for i in range(10):
        c = Card(
            card_number=f"FILLER-{i+1:03d}", card_name=f"Filler {i+1}",
            card_type="サポート・アイテム", image_file="test.png", face_up=False,
        )
        pm.zones[Zone.DECK].append(c)

    # Hand: support + 1st bloom + other cards
    support = Card(
        card_number="hBP01-104", card_name="ふつうのパソコン",
        card_type="サポート・アイテム", image_file="test.png", face_up=True,
    )
    pm.zones[Zone.HAND].append(support)
    bloom_c = Card(
        card_number="hBP01-010", card_name="1st Bloom Sora",
        card_type="ホロメン", image_file="test.png", face_up=True, bloom_level="1st",
    )
    pm.zones[Zone.HAND].append(bloom_c)
    # Add a duplicate hand card (same as deck debut)
    hand_dup = Card(
        card_number="hBP01-001", card_name="Tokino Sora",
        card_type="ホロメン", image_file="hBP01-001.png",
        face_up=True, bloom_level="Debut",
    )
    pm.zones[Zone.HAND].append(hand_dup)

    # Put one debut on centre
    centre = Card(
        card_number="hBP01-001", card_name="Tokino Sora",
        card_type="ホロメン", image_file="hBP01-001.png",
        face_up=True, bloom_level="Debut",
    )
    pm.zones[Zone.CENTRE].append(centre)

    oshi = Card(
        card_number="hSD01-001", card_name="Oshi",
        card_type="推しホロメン", image_file="test.png", face_up=True,
    )
    pm.zones[Zone.OSHI].append(oshi)

    match.game_state = "playing"
    match.turn_player_id = pid1
    match.step_index = 3

    dump_face_up(pm, "Initial")

    # Play support: search deck to stage
    r1 = match.apply_action(pid1, {"type": "play_support", "card_number": "hBP01-104"})
    pending = match.step_state.get("pending_support")
    if pending and pending["picks"]:
        pick = pending["picks"][0]
        r2 = match.apply_action(pid1, {
            "type": "pick_support_cards",
            "pick_id": pick["pick_id"],
            "card_numbers": ["hBP01-001"],
        })

    dump_face_up(pm, "After search+pick")

    # Now bloom centre with 1st Bloom
    r3 = match.apply_action(pid1, {
        "type": "bloom", "zone": "centre", "card_index": 0,
        "hand_card_number": "hBP01-010",
    })

    dump_face_up(pm, "After bloom")

    # Check all  
    errors = []
    for z in [Zone.HAND, Zone.CENTRE, Zone.BACK]:
        for i, c in enumerate(pm.zones[z]):
            if not c.face_up:
                errors.append(f"{z.value}[{i}] {c.card_name} ({c.card_number}) face_up=False")

    if errors:
        print("*** BUGS FOUND ***")
        for e in errors:
            print(f"  - {e}")
    else:
        print("✓ All cards correct after search + bloom with duplicates!")


if __name__ == "__main__":
    test_search_deck_to_stage_twice()
    test_bloom_hand_face_up()
    test_search_then_bloom()
    test_duplicate_cards_in_deck()
    test_search_to_hand_then_bloom_duplicates()
