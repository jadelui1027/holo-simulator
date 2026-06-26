#!/usr/bin/env python3
"""Quick E2E test for the updated hOCG PvP server."""
import asyncio, json, websockets

URI = "ws://localhost:8000/ws"

async def test():
    async with websockets.connect(URI) as ws1, websockets.connect(URI) as ws2:
        # Join
        await ws1.send(json.dumps({"type":"join","name":"Alice"}))
        r1 = json.loads(await ws1.recv())
        assert r1["type"]=="joined", f"ws1 join failed: {r1}"
        pid1 = r1["player_id"]
        print(f"✓ Alice joined as P{pid1}")

        await ws2.send(json.dumps({"type":"join","name":"Bob"}))
        r2 = json.loads(await ws2.recv())
        assert r2["type"]=="joined", f"ws2 join failed: {r2}"
        pid2 = r2["player_id"]
        print(f"✓ Bob joined as P{pid2}")

        # Drain lobby states
        for _ in range(4):
            try:
                await asyncio.wait_for(ws1.recv(), 0.5)
            except: pass
        for _ in range(4):
            try:
                await asyncio.wait_for(ws2.recv(), 0.5)
            except: pass

        # Load decks
        await ws1.send(json.dumps({"type":"action","action":{"type":"load_deck","deck_code":"11QBS"}}))
        await asyncio.sleep(3)
        # drain
        while True:
            try:
                await asyncio.wait_for(ws1.recv(), 0.3)
            except: break

        await ws2.send(json.dumps({"type":"action","action":{"type":"load_deck","deck_code":"11QBS"}}))
        await asyncio.sleep(3)

        # After both load, match should auto-start. Collect match_start messages.
        match_started = False
        for _ in range(10):
            try:
                raw = await asyncio.wait_for(ws1.recv(), 1)
                msg = json.loads(raw)
                if msg.get("type") == "match_start":
                    match_started = True
                    state = msg["state"]
                    break
                if msg.get("type") == "state_update" and msg.get("state",{}).get("started"):
                    match_started = True
                    state = msg["state"]
                    break
            except:
                break

        assert match_started, "Match never started"
        print("✓ Match started")

        my = state["players"][pid1]
        opp = state["players"][pid2]

        hand = my["zones"]["hand"]
        print(f"✓ Alice hand: {len(hand)} cards")
        assert len(hand) == 7

        # Check opponent zones have hidden flag
        opp_deck = opp["zones"]["deck"]
        assert opp_deck.get("hidden") == True, f"Expected hidden flag on opponent deck: {opp_deck}"
        print(f"✓ Opponent deck: count={opp_deck['count']}, hidden=True")

        opp_life = opp["zones"]["life"]
        assert opp_life.get("hidden") == True
        print(f"✓ Opponent life: count={opp_life['count']}, hidden=True")

        # Test toggle_rest: play a holomen card to centre, then toggle rest
        # Find first holomen in hand (card_type contains ホロメン)
        holomen = None
        for c in hand:
            if 'ホロメン' in c.get('card_type', ''):
                holomen = c
                break
        if holomen is None:
            # Fallback: try first card anyway
            holomen = hand[0]
        cn = holomen["card_number"]
        await ws1.send(json.dumps({"type":"action","action":{"type":"play_card","card_number":cn,"zone":"centre","face_up":True}}))
        await asyncio.sleep(0.5)

        # Drain and get state
        latest = None
        for _ in range(5):
            try:
                raw = await asyncio.wait_for(ws1.recv(), 0.5)
                msg = json.loads(raw)
                if msg.get("type") == "state_update":
                    latest = msg["state"]
            except: break

        if latest:
            centre = latest["players"][pid1]["zones"]["centre"]
            print(f"✓ Centre has {len(centre)} card(s): {centre[0]['card_name'] if centre else 'empty'}")

            # Toggle rest
            await ws1.send(json.dumps({"type":"action","action":{"type":"toggle_rest","zone":"centre","card_index":0}}))
            await asyncio.sleep(0.3)
            for _ in range(5):
                try:
                    raw = await asyncio.wait_for(ws1.recv(), 0.3)
                    msg = json.loads(raw)
                    if msg.get("type") == "state_update":
                        latest = msg["state"]
                except: break
            if latest:
                resting = latest["players"][pid1]["zones"]["centre"][0]["resting"]
                print(f"✓ Toggle rest → resting={resting}")

        # Test shuffle_yell
        await ws1.send(json.dumps({"type":"action","action":{"type":"shuffle_yell"}}))
        await asyncio.sleep(0.3)
        for _ in range(3):
            try: await asyncio.wait_for(ws1.recv(), 0.3)
            except: break
        print("✓ Shuffle yell action sent")

        # Test reset_step
        await ws1.send(json.dumps({"type":"action","action":{"type":"reset_step"}}))
        await asyncio.sleep(0.3)
        for _ in range(3):
            try: await asyncio.wait_for(ws1.recv(), 0.3)
            except: break
        print("✓ Reset step action sent")

        print("\n✅ All tests passed!")

asyncio.run(test())
