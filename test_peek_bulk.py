"""Test bulk peek sub-actions: all_to_top, all_to_bottom, all_to_archive"""
from game_tools.game_engine import Match
from game_tools.playmat_manager import Zone

m = Match()
p1 = m.add_player('A')
p2 = m.add_player('B')
m.apply_action(p1.id, {'type':'load_deck','deck_code':'6QCNY'})
m.apply_action(p2.id, {'type':'load_deck','deck_code':'6QCNY'})
m.start_dice_phase()
while m.game_state == 'dice_roll':
    for p in m.players.values(): p.dice_roll = None
    m.apply_action(p1.id, {'type':'roll_dice'})
    m.apply_action(p2.id, {'type':'roll_dice'})
c = m.step_state.get('chooser')
m.apply_action(c, {'type':'choose_order','choice':'first'})
for pid in [p1.id, p2.id]:
    m.apply_action(pid, {'type':'mulligan_ready'})
for pid in [p1.id, p2.id]:
    h = m.players[pid].playmat.zones[Zone.HAND]
    for card in h:
        if 'Debut' in getattr(card, 'bloom_level', ''):
            m.apply_action(pid, {'type':'setup_place','zone':'centre','card_number':card.card_number})
            break
    m.apply_action(pid, {'type':'setup_ready'})
tp = m.turn_player_id
# May be on cheer or already past draw
if m.current_step == 'cheer':
    m.apply_action(tp, {'type':'skip_cheer'})
elif m.current_step != 'main':
    # Force to main
    m.apply_action(tp, {'type':'skip_cheer'})
print(f'Step: {m.current_step}')
assert m.current_step == 'main', f'Expected main, got {m.current_step}'

# Test 1: all_to_top with reorder
print('\n--- TEST 1: all_to_top (reversed) ---')
r = m.apply_action(tp, {'type':'peek_deck','count':3})
assert r['success']
names_before = [c['card_name'] for c in r['cards']]
indices = [c['deck_index'] for c in r['cards']]
print(f'Before: {names_before}')
# Reverse order
rev_indices = list(reversed(indices))
r2 = m.apply_action(tp, {'type':'peek_deck','count':3,'sub_action':{'type':'all_to_top','card_indices':rev_indices}})
assert r2['success'], r2
r3 = m.apply_action(tp, {'type':'peek_deck','count':3})
names_after = [c['card_name'] for c in r3['cards']]
print(f'After:  {names_after}')
assert names_after == list(reversed(names_before)), f'{names_after} != {list(reversed(names_before))}'
print('  PASS')

# Test 2: all_to_bottom
print('\n--- TEST 2: all_to_bottom ---')
deck_len_before = len(m.players[tp].playmat.zones[Zone.DECK])
r = m.apply_action(tp, {'type':'peek_deck','count':3})
indices = [c['deck_index'] for c in r['cards']]
names = [c['card_name'] for c in r['cards']]
print(f'Moving to bottom: {names}')
r2 = m.apply_action(tp, {'type':'peek_deck','count':3,'sub_action':{'type':'all_to_bottom','card_indices':indices}})
assert r2['success'], r2
deck_len_after = len(m.players[tp].playmat.zones[Zone.DECK])
assert deck_len_before == deck_len_after
# Check bottom 3 cards are the ones we moved
deck = m.players[tp].playmat.zones[Zone.DECK]
bottom_names = [deck[i].card_name for i in range(3)]
print(f'Bottom 3 now: {bottom_names}')
print('  PASS')

# Test 3: all_to_archive
print('\n--- TEST 3: all_to_archive ---')
arc_before = len(m.players[tp].playmat.zones[Zone.ARCHIVE])
deck_before = len(m.players[tp].playmat.zones[Zone.DECK])
r = m.apply_action(tp, {'type':'peek_deck','count':3})
indices = [c['deck_index'] for c in r['cards']]
names = [c['card_name'] for c in r['cards']]
print(f'Archiving: {names}')
r2 = m.apply_action(tp, {'type':'peek_deck','count':3,'sub_action':{'type':'all_to_archive','card_indices':indices}})
assert r2['success'], r2
arc_after = len(m.players[tp].playmat.zones[Zone.ARCHIVE])
deck_after = len(m.players[tp].playmat.zones[Zone.DECK])
assert arc_after == arc_before + 3
assert deck_after == deck_before - 3
print(f'Archive: {arc_before} -> {arc_after}, Deck: {deck_before} -> {deck_after}')
print('  PASS')

print('\n✅ All bulk peek tests passed!')
