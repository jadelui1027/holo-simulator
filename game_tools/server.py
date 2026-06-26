from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import asyncio
import json
from typing import Dict
import os

from .game_engine import Match

app = FastAPI()

# Serve minimal web client
client_dir = os.path.join(os.path.dirname(__file__), 'web_client')
if os.path.isdir(client_dir):
    app.mount('/client', StaticFiles(directory=client_dir), name='client')

# Serve card images and playmat assets so the web client can render them
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
cards_dir = os.path.join(project_root, 'cards')
if os.path.isdir(cards_dir):
    app.mount('/cards', StaticFiles(directory=cards_dir), name='cards')

assets_dir = os.path.join(os.path.dirname(__file__))
app.mount('/assets', StaticFiles(directory=assets_dir), name='assets')

# Simple lobby: only support one match at a time for now
_current_match: Match | None = None


async def _send(ws: WebSocket, data: dict):
    try:
        await ws.send_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass


async def _broadcast_state(match: Match):
    """Send each player their own filtered view + any events."""
    for pid, p in match.players.items():
        if p.connection:
            view = match.get_filtered_state(pid)
            await _send(p.connection, {"type": "state_update", "state": view})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    pid = None
    match = None
    try:
        # Expect a join message first
        data = await ws.receive_text()
        msg = json.loads(data)
        if msg.get("type") != "join":
            await _send(ws, {"error": "first message must be join"})
            return
        name = msg.get("name", "Player")

        global _current_match
        if _current_match is None or len(_current_match.players) >= 2:
            _current_match = Match()
        match = _current_match
        player = match.add_player(name)
        pid = player.id
        player.connection = ws

        await _send(ws, {"type": "joined", "player_id": pid, "match_id": match.id})

        # Tell every connected player about the lobby update
        await _broadcast_state(match)

        # Main receive loop
        while True:
            text = await ws.receive_text()
            try:
                msg = json.loads(text)
            except Exception:
                continue

            if msg.get("type") == "action":
                action = msg.get("action", {})

                # load_deck uses blocking HTTP — run in thread
                if action.get("type") == "load_deck":
                    res = await asyncio.to_thread(match.apply_action, pid, action)
                else:
                    try:
                        res = match.apply_action(pid, action)
                    except Exception as e:
                        import traceback; traceback.print_exc()
                        res = {"success": False, "reason": f"server error: {e}"}

                # If both players just became ready, auto-start mulligan phase
                if action.get("type") == "load_deck" and res.get("success") and match.all_ready():
                    match.start_dice_phase()
                    for other_pid, p in match.players.items():
                        if p.connection:
                            view = match.get_filtered_state(other_pid)
                            await _send(p.connection, {"type": "dice_phase", "state": view})
                    continue

                # Send action result to the acting player
                await _send(ws, {"type": "action_result", "result": res})

                # Broadcast updated state to all
                await _broadcast_state(match)

                # Dice result pause: show results for 1.5s then transition
                if match.game_state == "dice_result":
                    await asyncio.sleep(1.5)
                    match.game_state = "choose_order"
                    await _broadcast_state(match)

    except WebSocketDisconnect:
        pass
    finally:
        if pid and match:
            try:
                if pid in match.players:
                    match.players[pid].connection = None
                    # Notify remaining players about the disconnect
                    name = match.players[pid].name
                    for other_pid, p in match.players.items():
                        if other_pid != pid and p.connection:
                            await _send(p.connection, {
                                "type": "player_disconnected",
                                "player_id": pid,
                                "player_name": name,
                            })
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("game_tools.server:app", host="0.0.0.0", port=8000, log_level="info")
