#!/usr/bin/env python3
import traceback
from game_tools.playmat_manager import PlaymatManager

pm = PlaymatManager()
code = '1SEUP'
try:
    cnt = pm.load_deck_from_decklog(code, deck_site='global')
    print('Loaded', cnt)
except Exception as e:
    print('EXCEPTION:', e)
    traceback.print_exc()
