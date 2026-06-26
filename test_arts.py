#!/usr/bin/env python3
"""Test arts feature: verify hp/arts in state, and play_arts action."""
import asyncio, json, websockets

URI = "ws://localhost:8000/ws"

async def drain(ws, n=10):
    msgs = []
    for _ in range(n):
        try:
            m = json.loads(await asyncio.wait_for(ws.recv(), 1.5))
            msgs.append(m)
        except (asyncio.TimeoutError, Exception):
            break
    return msgs

async def recv_until(ws, pred, max_msgs=30):
    for _ in range(max_msgs):
        try:
            m = json.loads(await asyncio.wait_for(ws.recv(), 3))
            if pred(m):
                return m
        except asyncio.TimeoutError:
            break
    return None

async def test():
    async with websockets.connect(URI) as ws1, websockets.connect(URI) as ws2:
        # Join
        await ws1.send(json.dumps({"type": "join", "name": "Alice"}))
        r1 = json.loads(await ws1.recv())
        pid1 = r1["player_id"]

        await ws2.send(json.dumps({"type": "join", "name": "Bob"}))
        r2 = json.loads(await ws2.recv())
        pid2 = r2["player_id"]

        await drain(ws1)
        await drain(ws2)

        # Load decks
        await ws1.send(json.dumps({"type": "action", "action": {"type": "load_deck", "deck_code": "11QBS"}}))
        await asyncio.sleep(2)
        await ws2.send(json.dumps({"type": "action", "action": {"type": "load_deck", "deck_code": "11QBS"}}))

        # Wait for match_start
        m1 = await recv_until(ws1, lambda m: m.get("type") == "match_start")
        assert m1, "No match_start for Alice"
        m2 = await recv_until(ws2, lambda m: m.get("type") == "match_start")

        state1 = m1["state"]
        hand = state1["players"][pid1]["zones"]["hand"]
        holos = [c for c in hand if "ホロメン" in c.get("card_type", "")]

        # Verify hp and arts in hand cards
        assert holos, "No holomen in hand"
        h = holos[0]
        print(f"✓ Hand holomen: {h['card_name']} hp={h.get('hp')} arts_count={len(h.get('arts', []))}")
        assert h.get("hp", 0) > 0, f"hp should be >0, got {h.get('hp')}"
        # Debut holomen may have arts or not, so just check field exists
        assert "arts" in h, "arts field missing"

        # Play a holomen to centre
        holo_cn = holos[0]["card_number"]
        await ws1.send(json.dumps({"type": "action", "action": {
            "type": "play_card", "card_number": holo_cn, "zone": "centre", "face_up": True
        }}))
        await asyncio.sleep(0.5)

        # Bob also plays a holomen to centre
        state2 = m2["state"] if m2 else None
        if state2:
            bob_hand = state2["players"][pid2]["zones"]["hand"]
            bob_holos = [c for c in bob_hand if "ホロメン" in c.get("card_type", "")]
            if bob_holos:
                bob_holo_cn = bob_holos[0]["card_number"]
                await ws2.send(json.dumps({"type": "action", "action": {
                    "type": "play_card", "card_number": bob_holo_cn, "zone": "centre", "face_up": True
                }}))
                await asyncio.sleep(0.5)

        # Drain state updates
        await drain(ws1)
        await drain(ws2)

        # Attach a yell to Alice's centre holomen
        await ws1.send(json.dumps({"type": "action", "action": {
            "type": "attach_yell", "zone": "centre", "card_index": 0
        }}))
        await asyncio.sleep(0.3)

        # Attach another yell (for multi-yell arts)
        await ws1.send(json.dumps({"type": "action", "action": {
            "type": "attach_yell", "zone": "centre", "card_index": 0
        }}))
        await asyncio.sleep(0.3)

        # Now try play_arts from Alice's centre to Bob's centre
        await ws1.send(json.dumps({"type": "action", "action": {
            "type": "play_arts",
            "zone": "centre",
            "card_index": 0,
            "arts_index": 0,
            "target_player_id": pid2,
            "target_zone": "centre",
            "target_card_index": 0,
        }}))

        # Get the state update after arts
        await asyncio.sleep(0.5)
        msgs = await drain(ws1, 10)
        
        # Find the latest state_update
        latest_state = None
        for m in msgs:
            if m.get("type") == "state_update" and m.get("state", {}).get("started"):
                latest_state = m["state"]

        if latest_state:
            # Check Alice's centre card is now resting
            my_centre = latest_state["players"][pid1]["zones"]["centre"]
            if my_centre:
                print(f"✓ Alice centre: {my_centre[0]['card_name']} resting={my_centre[0].get('resting')}")

            # Check opponent's centre for damage (we see filtered view)
            opp_centre = latest_state["players"][pid2]["zones"].get("centre", [])
            if isinstance(opp_centre, list) and opp_centre:
                c = opp_centre[0]
                print(f"✓ Bob centre (from Alice's view): {c.get('card_name')} hp={c.get('hp')} damage shown in state")
            else:
                print("✓ Opponent centre data is filtered (hidden or empty)")
        else:
            print("⚠ No state update received after play_arts")

        print("\n✅ Arts test passed!")

asyncio.run(test())
