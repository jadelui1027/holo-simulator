/* ══════════════════════════════════════════════════════════════
   hOCG Web Client — Entry Point
   Wires all button handlers, keyboard shortcuts, and resize.
   ══════════════════════════════════════════════════════════════ */
import {
  lastState, playerId, lobbyStatus, ws,
  sendAction,
} from './state.js';
import { connect } from './connection.js';
import { renderGame, clearSelection } from './render.js';
import { hideContextMenu } from './menus.js';

/* ════════════════════ CONNECT ════════════════════ */
document.getElementById('connect').onclick = () => {
  const host = document.getElementById('server').value.trim();
  const name = document.getElementById('name').value.trim() || 'Player';
  connect(host, name);
};

/* ════════════════════ LOAD DECK ════════════════════ */
document.getElementById('load_deck').onclick = () => {
  const code = document.getElementById('deck_code').value.trim();
  const site = document.querySelector('input[name="deck_site"]:checked').value;
  if(!code) return;
  lobbyStatus.textContent = 'Loading deck\u2026';
  document.getElementById('load_deck').disabled = true;
  sendAction({type:'load_deck', deck_code:code, deck_site:site});
  setTimeout(()=> document.getElementById('load_deck').disabled = false, 3000);
};

/* ════════════════════ SETUP BUTTONS ════════════════════ */
document.getElementById('setup_mulligan_btn').onclick = ()=> sendAction({type:'setup_mulligan'});
document.getElementById('mulligan_ready_btn').onclick = ()=> sendAction({type:'mulligan_ready'});
document.getElementById('setup_ready_btn').onclick    = ()=> sendAction({type:'setup_ready'});

/* ════════════════════ DICE / ORDER ════════════════════ */
document.getElementById('dice_btn').onclick     = ()=> sendAction({type:'roll_dice'});
document.getElementById('order_first').onclick  = ()=> sendAction({type:'choose_order', choice:'first'});
document.getElementById('order_second').onclick = ()=> sendAction({type:'choose_order', choice:'second'});

/* ════════════════════ ACTION BUTTONS ════════════════════ */
document.getElementById('draw').onclick            = ()=> sendAction({type:'draw', count:1});
document.getElementById('skip_cheer').onclick      = ()=> sendAction({type:'skip_cheer'});
document.getElementById('end_main').onclick        = ()=> sendAction({type:'end_main'});
document.getElementById('end_performance').onclick = ()=> sendAction({type:'end_performance'});
document.getElementById('end_turn').onclick        = ()=> sendAction({type:'end_turn'});
document.getElementById('hand_to_deck').onclick    = ()=> sendAction({type:'hand_to_deck'});

document.getElementById('end_deduct_life_btn').onclick = ()=> sendAction({type:'end_deduct_life'});

document.getElementById('undo_btn').onclick = ()=> {
  sendAction({type:'rollback'});
};

document.getElementById('rewind_step_btn').onclick = ()=> {
  sendAction({type:'rewind_step'});
};

document.getElementById('retire_btn').onclick = ()=> {
  if(confirm('Are you sure you want to retire? This will count as a loss.')){
    sendAction({type:'retire'});
  }
};

document.getElementById('back_to_lobby_btn').onclick = ()=> {
  if(ws) ws.close();
  location.reload();
};

/* ════════════════════ CONTEXT MENU DISMISS ════════════════════ */
document.addEventListener('click', hideContextMenu);
document.addEventListener('contextmenu', ev=>{
  if(!ev.target.closest('.main-card,.card-in-slot,.card-thumb,.stack-card'))
    hideContextMenu();
});

/* ════════════════════ RESIZE & KEYBOARD ════════════════════ */
window.addEventListener('resize', ()=>{
  if(lastState && (lastState.started || lastState.game_state === 'setup' || lastState.game_state === 'mulligan'))
    renderGame(lastState);
});
document.addEventListener('keydown', ev=>{
  if(ev.key==='Escape'){ clearSelection(); hideContextMenu(); }
});
