"""Test: Debut return block, draw in main, peek deck."""
from game_tools.game_engine import Match
from game_tools.playmat_manager import Zone

# ── Setup a game to main phase ──
def setup_to_main():
    m = Match()
    p1 = m.add_player('Alice')
    p2 = m.add_player('Bob')
    m.apply_action(p1.id, {'type':'load_deck','deck_code':'6QCNY'})
    m.apply_action(p2.id, {'type':'load_deck','deck_code':'6QCNY'})
    m.start_dice_phase()
    # Roll until no tie
    while m.game_state == 'dice_roll':
        for p in m.players.values(): p.dice_roll = None
        m.apply_action(p1.id, {'type':'roll_dice'})
        m.apply_action(p2.id, {'type':'roll_dice'})
    chooser = m.step_state.get('chooser')
    m.apply_action(chooser, {'type':'choose_order','choice':'first'})
    return m, p1, p2

m, p1, p2 = setup_to_main()
print(f'=== State: {m.game_state} ===')

# ── Test 1: Block returning only Debut during mulligan ──
print('\n--- TEST 1: Debut return block ---')

# Use free mulligan first (hand #1 -> hand #2 with penalty)
r = m.apply_action(p1.id, {'type':'setup_mulligan'})
ss = m.setup_state[p1.id]
print(f'After free mulligan: hand #{ss["hand_number"]}, penalty={ss.get("returning",0)}')

hand = m.players[p1.id].playmat.zones[Zone.HAND]
debuts = [c for c in hand if 'ホロメン' in c.card_type and c.bloom_level == 'Debut']
non_debuts = [c for c in hand if c not in debuts]
print(f'Debuts: {len(debuts)}, Non-debuts: {len(non_debuts)}')

if debuts and ss.get('returning', 0) > 0:
    if len(debuts) == 1:
        r = m.apply_action(p1.id, {'type':'setup_return_card','card_number':debuts[0].card_number})
        print(f'Try return only Debut: success={r.get("success")}, reason={r.get("reason","ok")}')
        assert not r['success'], 'Should have blocked!'
        print('  PASS: only Debut blocked')
    if non_debuts:
        r = m.apply_action(p1.id, {'type':'setup_return_card','card_number':non_debuts[0].card_number})
        print(f'Return non-debut: success={r.get("success")}')
else:
    print('(no penalty to test, skipping)')

# Finish mulligan for both players
for pid in [p1.id, p2.id]:
    ss2 = m.setup_state[pid]
    while (ss2.get('returning',0) - ss2.get('returned',0)) > 0:
        h = m.players[pid].playmat.zones[Zone.HAND]
        nondebuts = [c for c in h if not('ホロメン' in c.card_type and c.bloom_level=='Debut')]
        if nondebuts:
            m.apply_action(pid, {'type':'setup_return_card','card_number':nondebuts[0].card_number})
        else:
            break
        ss2 = m.setup_state[pid]
    if not ss2.get('ready'):
        m.apply_action(pid, {'type':'mulligan_ready'})

# Place and ready
for pid in [p1.id, p2.id]:
    h = m.players[pid].playmat.zones[Zone.HAND]
    for c in h:
        if 'ホロメン' in c.card_type and c.bloom_level == 'Debut':
            m.apply_action(pid, {'type':'setup_place','zone':'centre','card_number':c.card_number})
            break
    m.apply_action(pid, {'type':'setup_ready'})

print(f'\nGame state: {m.game_state}')
assert m.game_state == 'playing'

# Skip to main
tp = m.turn_player_id
m.apply_action(tp, {'type':'skip_cheer'})
print(f'Step: {m.current_step}')
assert m.current_step == 'main'

# ── Test 2: Draw 1 in main phase ──
print('\n--- TEST 2: Draw 1 in main ---')
hand_before = len(m.players[tp].playmat.zones[Zone.HAND])
r = m.apply_action(tp, {'type':'draw','count':1})
hand_after = len(m.players[tp].playmat.zones[Zone.HAND])
print(f'Draw 1: success={r["success"]}, hand {hand_before} -> {hand_after}')
assert r['success'] and hand_after == hand_before + 1
print('  PASS')

# ── Test 3: Peek deck top 3 ──
print('\n--- TEST 3: Peek top 3 ---')
r = m.apply_action(tp, {'type':'peek_deck','count':3})
print(f'Peek 3: success={r["success"]}, cards={len(r.get("cards",[]))}')
for c in r.get('cards',[]):
    print(f'  #{c["deck_index"]}: {c["card_name"]}')
assert r['success'] and len(r['cards']) == 3

# Test sub-action: to_hand
top_idx = r['cards'][0]['deck_index']
r2 = m.apply_action(tp, {'type':'peek_deck','count':3,'sub_action':{'type':'to_hand','card_index':top_idx}})
print(f'Peek to_hand: success={r2["success"]}')
assert r2['success']
print('  PASS: card moved to hand')

# ── Test 4: Peek deck top 5 ──
print('\n--- TEST 4: Peek top 5 ---')
r = m.apply_action(tp, {'type':'peek_deck','count':5})
print(f'Peek 5: success={r["success"]}, cards={len(r.get("cards",[]))}')
assert r['success'] and len(r['cards']) == 5

# Test to_archive
top_idx = r['cards'][0]['deck_index']
r2 = m.apply_action(tp, {'type':'peek_deck','count':5,'sub_action':{'type':'to_archive','card_index':top_idx}})
print(f'Peek to_archive: success={r2["success"]}')
assert r2['success']

# Test to_top
r = m.apply_action(tp, {'type':'peek_deck','count':5})
second_idx = r['cards'][1]['deck_index']
r2 = m.apply_action(tp, {'type':'peek_deck','count':5,'sub_action':{'type':'to_top','card_index':second_idx}})
print(f'Peek to_top: success={r2["success"]}')
assert r2['success']

# Test to_bottom
r = m.apply_action(tp, {'type':'peek_deck','count':5})
top_idx = r['cards'][0]['deck_index']
r2 = m.apply_action(tp, {'type':'peek_deck','count':5,'sub_action':{'type':'to_bottom','card_index':top_idx}})
print(f'Peek to_bottom: success={r2["success"]}')
assert r2['success']
print('  PASS: all peek sub-actions work')

print('\n✅ All tests passed!')
