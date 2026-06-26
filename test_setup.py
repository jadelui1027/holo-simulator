"""Smoke test for setup phase, mulligan, and first-turn skip."""
from game_tools.game_engine import Match
from game_tools.playmat_manager import Zone, Card


def make_debut(name, num):
    c = Card(card_number=num, card_name=name, card_type='ホロメン', image_file='test.webp')
    c.bloom_level = 'Debut'
    c.face_up = False
    return c


def make_support(name, num):
    c = Card(card_number=num, card_name=name, card_type='サポート', image_file='test.webp')
    c.face_up = False
    return c


def build_match():
    m = Match()
    p1 = m.add_player('Alice')
    p2 = m.add_player('Bob')

    for i in range(20):
        p1.playmat.zones[Zone.DECK].append(make_debut(f'Holo{i}', f'hSD01-{i:03d}'))
        p2.playmat.zones[Zone.DECK].append(make_debut(f'Holo{i}', f'hSD02-{i:03d}'))

    for i in range(6):
        for pid, prefix in [('1', 'y1'), ('2', 'y2')]:
            y = Card(card_number=f'{prefix}-{i}', card_name=f'Yell{i}', card_type='エール', image_file='test.webp')
            y.face_up = False
            m.players[pid].playmat.zones[Zone.YELL_DECK].append(y)

    for i in range(5):
        for pid, prefix in [('1', 'l1'), ('2', 'l2')]:
            lc = Card(card_number=f'{prefix}-{i}', card_name=f'Life{i}', card_type='エール', image_file='test.webp')
            lc.face_up = False
            m.players[pid].playmat.zones[Zone.LIFE].append(lc)

    for pid, num in [('1', 'oshi-1'), ('2', 'oshi-2')]:
        o = Card(card_number=num, card_name='Oshi', card_type='推し', image_file='test.webp')
        o.face_up = True
        m.players[pid].playmat.zones[Zone.OSHI].append(o)

    p1.ready = True
    p2.ready = True
    return m


def test_basic_setup():
    print("=== Test: Basic Setup Phase ===")
    m = build_match()
    m.start_setup_phase()

    assert m.game_state == "setup", f"Expected setup, got {m.game_state}"
    assert len(m.players['1'].playmat.zones[Zone.HAND]) == 7
    assert len(m.players['2'].playmat.zones[Zone.HAND]) == 7
    print(f"  P1 setup: {m.setup_state['1']}")
    print(f"  P2 setup: {m.setup_state['2']}")

    # Both have debut holomen (all cards are debut)
    assert m.setup_state['1']['has_debut'] == True
    assert m.setup_state['2']['has_debut'] == True

    # P1 places centre
    hand1 = m.players['1'].playmat.zones[Zone.HAND]
    cn1 = hand1[0].card_number
    res = m.apply_action('1', {'type': 'setup_place', 'zone': 'centre', 'card_number': cn1})
    assert res['success'], f"Place failed: {res}"
    assert m.setup_state['1']['centre_placed'] == True
    print(f"  P1 placed {cn1} on centre")

    # P1 ready
    res = m.apply_action('1', {'type': 'setup_ready'})
    assert res['success'], f"Ready failed: {res}"
    assert m.setup_state['1']['ready'] == True
    assert m.game_state == "setup"  # Still setup, P2 not ready
    print("  P1 ready")

    # P2 places centre
    hand2 = m.players['2'].playmat.zones[Zone.HAND]
    cn2 = hand2[0].card_number
    res = m.apply_action('2', {'type': 'setup_place', 'zone': 'centre', 'card_number': cn2})
    assert res['success']
    print(f"  P2 placed {cn2} on centre")

    # P2 ready -> transitions to dice_roll
    res = m.apply_action('2', {'type': 'setup_ready'})
    assert res['success']
    assert res.get('all_setup_ready') == True
    assert m.game_state == "dice_roll", f"Expected dice_roll, got {m.game_state}"
    print(f"  P2 ready -> game_state={m.game_state}")
    print("  PASSED\n")


def test_mulligan_penalty():
    print("=== Test: Mulligan with Penalty ===")
    m = build_match()

    # Replace P1 hand with non-debut cards
    p1 = m.players['1']
    for i in range(20):
        p1.playmat.zones[Zone.DECK].clear()
    for i in range(20):
        p1.playmat.zones[Zone.DECK].append(make_support(f'Support{i}', f'sup-{i:03d}'))
    # Add some debut holomen deeper in deck
    for i in range(5):
        p1.playmat.zones[Zone.DECK].insert(0, make_debut(f'DebutDeep{i}', f'deep-{i:03d}'))

    m.start_setup_phase()

    # P1 has no debut (all supports in top 7)
    print(f"  P1 has_debut: {m.setup_state['1']['has_debut']}")
    # Check - all top 7 are supports
    hand1 = p1.playmat.zones[Zone.HAND]
    has_any_debut = any('ホロメン' in c.card_type and c.bloom_level == 'Debut' for c in hand1)
    print(f"  P1 hand has debut: {has_any_debut}")

    # Mulligan 1 (hand #2, free)
    res = m.apply_action('1', {'type': 'setup_mulligan'})
    assert res['success'], f"Mulligan failed: {res}"
    assert res['hand_number'] == 2
    assert res['penalty'] == 0
    print(f"  Mulligan 1: hand #{res['hand_number']}, penalty={res['penalty']}")

    # If still no debut, mulligan 2 (hand #3, return 1)
    if not m.setup_state['1']['has_debut']:
        res = m.apply_action('1', {'type': 'setup_mulligan'})
        assert res['success']
        assert res['hand_number'] == 3
        assert res['penalty'] == 1
        print(f"  Mulligan 2: hand #{res['hand_number']}, penalty={res['penalty']}")
        print(f"  P1 returning: {m.setup_state['1']['returning']}, returned: {m.setup_state['1']['returned']}")

        # Must return 1 card
        hand1 = p1.playmat.zones[Zone.HAND]
        ret_cn = hand1[0].card_number
        res = m.apply_action('1', {'type': 'setup_return_card', 'card_number': ret_cn})
        assert res['success']
        assert res['remaining'] == 0
        print(f"  Returned {ret_cn}, remaining={res['remaining']}")
        print(f"  P1 hand size: {len(p1.playmat.zones[Zone.HAND])}")

    print("  PASSED\n")


def test_first_turn_skip_reset():
    print("=== Test: First Turn Skip Reset ===")
    m = build_match()
    m.start_setup_phase()

    # Both place and ready
    for pid in ['1', '2']:
        cn = m.players[pid].playmat.zones[Zone.HAND][0].card_number
        m.apply_action(pid, {'type': 'setup_place', 'zone': 'centre', 'card_number': cn})
        m.apply_action(pid, {'type': 'setup_ready'})

    assert m.game_state == "dice_roll"

    # Roll dice
    m.apply_action('1', {'type': 'roll_dice'})
    m.apply_action('2', {'type': 'roll_dice'})

    if m.game_state == 'dice_roll':
        # Tie, roll again
        m.apply_action('1', {'type': 'roll_dice'})
        m.apply_action('2', {'type': 'roll_dice'})

    if m.game_state == 'choose_order':
        chooser = m.step_state['chooser']
        m.apply_action(chooser, {'type': 'choose_order', 'choice': 'first'})

    assert m.game_state == "playing", f"Expected playing, got {m.game_state}"
    first_player = m.turn_player_id
    print(f"  First player: P{first_player}")
    print(f"  Current step: {m.current_step}")
    print(f"  Players first turn done: {m.players_first_turn_done}")

    # First turn should have skipped reset -> draw -> now on cheer (or further)
    # Reset was skipped, draw auto-ran, should be at cheer
    assert first_player in m.players_first_turn_done, "First player should be in first_turn_done"
    assert m.current_step in ('cheer', 'main', 'performance', 'end'), \
        f"Expected past reset/draw, got {m.current_step}"
    print(f"  Step after first turn skip: {m.current_step} (reset was skipped!)")

    # Get allowed actions
    allowed = m.get_allowed_actions(first_player)
    print(f"  Allowed actions: {allowed}")

    # Get filtered state
    state = m.get_filtered_state(first_player)
    print(f"  game_state={state['game_state']}, step={state['step']}")
    print("  PASSED\n")


def test_setup_return_to_hand():
    print("=== Test: Setup Return to Hand ===")
    m = build_match()
    m.start_setup_phase()

    cn = m.players['1'].playmat.zones[Zone.HAND][0].card_number
    m.apply_action('1', {'type': 'setup_place', 'zone': 'centre', 'card_number': cn})
    assert m.setup_state['1']['centre_placed'] == True

    # Return to hand
    res = m.apply_action('1', {'type': 'setup_return_to_hand', 'zone': 'centre', 'card_number': cn})
    assert res['success']
    assert m.setup_state['1']['centre_placed'] == False
    assert len(m.players['1'].playmat.zones[Zone.CENTRE]) == 0
    print(f"  Returned {cn} from centre to hand")
    print("  PASSED\n")


def test_mulligan_with_debut_blocked():
    print("=== Test: Mulligan Blocked When Has Debut ===")
    m = build_match()
    m.start_setup_phase()

    # P1 has debut holomen
    assert m.setup_state['1']['has_debut'] == True

    # Try to mulligan -> should fail
    res = m.apply_action('1', {'type': 'setup_mulligan'})
    assert not res['success'], "Mulligan should fail when has debut"
    print(f"  Mulligan blocked: {res['reason']}")
    print("  PASSED\n")


def test_filtered_state_setup():
    print("=== Test: Filtered State During Setup ===")
    m = build_match()
    m.start_setup_phase()

    state = m.get_filtered_state('1')
    assert 'setup_state' in state
    assert '1' in state['setup_state']
    assert '2' in state['setup_state']

    # Own state has full info
    my_ss = state['setup_state']['1']
    assert 'has_debut' in my_ss
    assert 'returning' in my_ss

    # Opponent state has limited info
    opp_ss = state['setup_state']['2']
    assert 'ready' in opp_ss
    assert 'hand_number' in opp_ss
    assert 'has_debut' not in opp_ss  # hidden from opponent
    print(f"  Own setup_state keys: {list(my_ss.keys())}")
    print(f"  Opponent setup_state keys: {list(opp_ss.keys())}")
    print("  PASSED\n")


if __name__ == '__main__':
    test_basic_setup()
    test_mulligan_penalty()
    test_first_turn_skip_reset()
    test_setup_return_to_hand()
    test_mulligan_with_debut_blocked()
    test_filtered_state_setup()
    print("=== ALL TESTS PASSED ===")
