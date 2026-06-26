#!/usr/bin/env python3
"""Quick WebSocket end-to-end test for decklog loading + match start."""
import asyncio, json, sys

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'websockets'],
                          stdout=subprocess.DEVNULL)
    import websockets


async def test():
    uri = "ws://127.0.0.1:8000/ws"
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
        # Join
        await ws1.send(json.dumps({"type": "join", "name": "Alice"}))
        r1 = json.loads(await ws1.recv())
        print("Alice joined:", r1.get("type"), r1.get("player_id"))
        # drain lobby update
        await asyncio.wait_for(ws1.recv(), timeout=3)

        await ws2.send(json.dumps({"type": "join", "name": "Bob"}))
        r2 = json.loads(await ws2.recv())
        print("Bob joined:", r2.get("type"), r2.get("player_id"))
        # drain lobby updates
        for _ in range(3):
            try:
                await asyncio.wait_for(ws1.recv(), timeout=1)
            except:
                pass
            try:
                await asyncio.wait_for(ws2.recv(), timeout=1)
            except:
                pass

        # Load decks
        print("\n--- Loading deck for Alice ---")
        await ws1.send(json.dumps({"type": "action", "action": {"type": "load_deck", "deck_code": "11QBS"}}))
        m = json.loads(await asyncio.wait_for(ws1.recv(), timeout=20))
        print(f"Alice after load_deck: type={m.get('type')}")
        # drain any extra
        for _ in range(3):
            try:
                await asyncio.wait_for(ws1.recv(), timeout=1)
            except:
                break
            try:
                await asyncio.wait_for(ws2.recv(), timeout=1)
            except:
                break

        print("\n--- Loading deck for Bob ---")
        await ws2.send(json.dumps({"type": "action", "action": {"type": "load_deck", "deck_code": "11QBS"}}))

        # Should get match_start
        for _ in range(5):
            try:
                m = json.loads(await asyncio.wait_for(ws2.recv(), timeout=20))
                print(f"Bob recv: type={m.get('type')} started={m.get('state', {}).get('started')}")
                if m.get("type") == "match_start":
                    st = m["state"]
                    pid = r2["player_id"]
                    p = st["players"][pid]
                    zones = p.get("zones", {})
                    hand = zones.get("hand", [])
                    deck = zones.get("deck", [])
                    oshi = zones.get("oshi", [])
                    print(f"  Hand: {len(hand)} cards")
                    print(f"  Deck: {len(deck)} cards")
                    print(f"  Oshi: {len(oshi)} cards")
                    if hand:
                        c = hand[0]
                        print(f"  First hand card: {c.get('card_number')} "
                              f"{c.get('card_name')} img={c.get('image_file')}")
                    break
            except Exception as e:
                print(f"Error: {e}")
                break

        # Test draw
        print("\n--- Alice draws 1 ---")
        await ws1.send(json.dumps({"type": "action", "action": {"type": "draw", "count": 1}}))
        m = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
        pid1 = r1["player_id"]
        hand1 = m.get("state", {}).get("players", {}).get(pid1, {}).get("zones", {}).get("hand", [])
        print(f"  Alice hand now: {len(hand1)} cards")

        # Test play_card from hand
        if hand1:
            cn = hand1[0].get("card_number")
            print(f"\n--- Alice plays {cn} to centre ---")
            await ws1.send(json.dumps({"type": "action", "action": {"type": "play_card", "card_number": cn, "zone": "centre"}}))
            m = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
            centre = m.get("state", {}).get("players", {}).get(pid1, {}).get("zones", {}).get("centre", [])
            hand_after = m.get("state", {}).get("players", {}).get(pid1, {}).get("zones", {}).get("hand", [])
            print(f"  Centre: {len(centre)} cards")
            print(f"  Hand: {len(hand_after)} cards")
            if centre:
                c = centre[0]
                print(f"  Centre card: {c.get('card_number')} {c.get('card_name')} img={c.get('image_file')}")

    print("\nAll tests passed!")

asyncio.run(test())
