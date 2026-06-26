/* ══════════════════════════════════════════════════════════════
   hOCG Web Client — WebSocket Connection & Message Routing
   ══════════════════════════════════════════════════════════════ */
import {
  ws, setWs, playerId, setPlayerId, matchId, setMatchId,
  lastState, setLastState, selectedCard, setSelectedCard,
  setStatus, lobbyEl, lobbyStatus, lobbyPlayers,
  diceOverlay, orderOverlay, gameoverOverlay,
} from './state.js';
import { renderGame } from './render.js';
import { renderSetupUI, showDiceOverlay, showOrderOverlay, showGameOver } from './setup.js';

/* ════════════════════ CONNECTION ════════════════════ */
export function connect(host, name){
  lobbyStatus.textContent = 'Connecting\u2026';
  const socket = new WebSocket(`ws://${host}/ws`);
  setWs(socket);
  socket.onopen = () => { socket.send(JSON.stringify({type:'join', name})); };
  socket.onmessage = ev => {
    try{ handleMsg(JSON.parse(ev.data)); }catch(e){console.error(e);}
  };
  socket.onclose = () => {
    setStatus('Disconnected');
    lobbyStatus.textContent = 'Disconnected';
  };
  socket.onerror = () => {
    setStatus('Connection error');
  };
}

/* ════════════════════ MESSAGE ROUTING ════════════════════ */
function handleMsg(msg){
  if(msg.type==='joined'){
    setPlayerId(msg.player_id);
    setMatchId(msg.match_id);
    lobbyStatus.textContent = `Joined as Player ${msg.player_id} \u2013 load your deck`;
    document.getElementById('deck_row').style.display = 'flex';
    return;
  }
  if(msg.type==='player_disconnected'){
    const who = msg.player_name || msg.player_id;
    alert(`Player "${who}" has disconnected. Returning to lobby.`);
    if(ws) ws.close();
    setWs(null);
    setPlayerId(null);
    setMatchId(null);
    setLastState(null);
    setSelectedCard(null);
    lobbyEl.classList.remove('hidden');
    document.getElementById('game_area').classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'none';
    lobbyStatus.textContent = 'Opponent disconnected. Connect again to start a new match.';
    return;
  }
  if(msg.type==='action_result'){
    const fb = document.getElementById('action_feedback');
    if(msg.result && !msg.result.success){
      console.warn('Action failed:', msg.result.reason);
      if(fb){
        fb.textContent = '\u274c ' + (msg.result.reason||'action failed');
        fb.style.color = '#ff6b6b';
        fb.style.opacity = '1';
        setTimeout(()=>{ fb.style.opacity = '0'; }, 3000);
      }
    } else if(msg.result && msg.result.description){
      if(fb){
        fb.textContent = '\u2705 ' + msg.result.description;
        fb.style.color = '#4fc3f7';
        fb.style.opacity = '1';
        setTimeout(()=>{ fb.style.opacity = '0'; }, 2500);
      }
    }
    return;
  }
  if(msg.type==='state_update'){
    setLastState(msg.state);
    if(lastState) updateFromState(lastState);
    return;
  }
  if(msg.type==='setup_phase'){
    setLastState(msg.state);
    lobbyEl.classList.add('hidden');
    renderSetupUI(lastState);
    renderGame(lastState);
    return;
  }
  if(msg.type==='dice_phase'){
    setLastState(msg.state);
    lobbyEl.classList.add('hidden');
    showDiceOverlay(lastState);
    return;
  }
  if(msg.type==='match_start'){
    setLastState(msg.state);
    lobbyEl.classList.add('hidden');
    diceOverlay.classList.add('hidden');
    orderOverlay.classList.add('hidden');
    if(lastState) renderGame(lastState);
    return;
  }
}

function updateFromState(state){
  const gs = state.game_state;

  if(gs === 'lobby'){
    const pids = Object.keys(state.players);
    let lines = pids.map(pid=>{
      const p = state.players[pid];
      const me = pid===playerId?' (you)':'';
      const rdy = p.ready?'\u2713 ready':'waiting\u2026';
      return `Player ${pid}${me}: ${p.name} \u2013 ${rdy}${p.deck_code?' ['+p.deck_code+']':''}`;
    });
    lobbyPlayers.innerHTML = lines.join('<br/>');
    return;
  }

  if(gs === 'mulligan'){
    lobbyEl.classList.add('hidden');
    diceOverlay.classList.add('hidden');
    orderOverlay.classList.add('hidden');
    gameoverOverlay.classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'block';
    renderSetupUI(state);
    renderGame(state);
    return;
  }

  if(gs === 'setup'){
    lobbyEl.classList.add('hidden');
    diceOverlay.classList.add('hidden');
    orderOverlay.classList.add('hidden');
    gameoverOverlay.classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'block';
    renderSetupUI(state);
    renderGame(state);
    return;
  }

  if(gs === 'dice_roll' || gs === 'dice_result'){
    lobbyEl.classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'none';
    showDiceOverlay(state);
    return;
  }

  if(gs === 'choose_order'){
    lobbyEl.classList.add('hidden');
    diceOverlay.classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'none';
    showOrderOverlay(state);
    return;
  }

  if(gs === 'game_over'){
    diceOverlay.classList.add('hidden');
    orderOverlay.classList.add('hidden');
    lobbyEl.classList.add('hidden');
    renderGame(state);
    showGameOver(state);
    return;
  }

  if(gs === 'playing' || state.started){
    lobbyEl.classList.add('hidden');
    diceOverlay.classList.add('hidden');
    orderOverlay.classList.add('hidden');
    gameoverOverlay.classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'none';
    renderGame(state);
    return;
  }
}
