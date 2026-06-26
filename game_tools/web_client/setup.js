/* ══════════════════════════════════════════════════════════════
   hOCG Web Client — Setup / Dice / Order / Game Over Phases
   ══════════════════════════════════════════════════════════════ */
import {
  playerId, stepBar, diceOverlay, orderOverlay, gameoverOverlay,
  sendAction,
} from './state.js';

/* ════════════════════ DICE ROLL ════════════════════ */
export function showDiceOverlay(state){
  diceOverlay.classList.remove('hidden');
  const pids = Object.keys(state.players);
  const rolls = state.dice_rolls || {};

  const p1 = state.players[pids[0]], p2 = state.players[pids[1]];
  document.getElementById('dice_p1_name').textContent = p1 ? p1.name + (pids[0]===playerId?' (You)':'') : '\u2014';
  document.getElementById('dice_p2_name').textContent = p2 ? p2.name + (pids[1]===playerId?' (You)':'') : '\u2014';

  const v1 = rolls[pids[0]], v2 = rolls[pids[1]];
  const d1El = document.getElementById('dice_p1_val');
  const d2El = document.getElementById('dice_p2_val');
  d1El.textContent = v1 != null ? v1 : '?';
  d1El.className = 'dice-value' + (v1==null?' waiting':'');
  d2El.textContent = v2 != null ? v2 : '?';
  d2El.className = 'dice-value' + (v2==null?' waiting':'');

  const myRoll = rolls[playerId];
  const diceBtn = document.getElementById('dice_btn');
  diceBtn.disabled = myRoll != null;
  diceBtn.textContent = myRoll != null ? `Rolled: ${myRoll}` : 'Roll Dice';

  const diceStatus = document.getElementById('dice_status');
  if(state.game_state === 'dice_result'){
    const winnerName = v1 > v2
      ? (state.players[pids[0]]?.name || '?')
      : (state.players[pids[1]]?.name || '?');
    diceStatus.textContent = `${winnerName} wins! (${v1} vs ${v2})`;
    diceBtn.disabled = true;
    diceBtn.textContent = `Rolled: ${myRoll}`;
  } else if(v1 != null && v2 != null && v1 === v2){
    diceStatus.textContent = `Tie! (${v1} vs ${v2}) \u2014 Roll again`;
    diceBtn.disabled = false;
    diceBtn.textContent = 'Roll Again';
  } else if(myRoll != null){
    diceStatus.textContent = 'Waiting for opponent to roll\u2026';
  } else {
    diceStatus.textContent = 'Click to roll your dice!';
  }
}

/* ════════════════════ CHOOSE ORDER ════════════════════ */
export function showOrderOverlay(state){
  orderOverlay.classList.remove('hidden');
  const chooser = state.dice_chooser;
  const isChooser = chooser === playerId;
  const rolls = state.dice_rolls || {};
  const pids = Object.keys(state.players);

  document.getElementById('order_status').textContent =
    isChooser
      ? `You rolled higher! (${rolls[pids[0]]} vs ${rolls[pids[1]]}) \u2014 Choose your turn order`
      : `Opponent rolled higher! (${rolls[pids[0]]} vs ${rolls[pids[1]]}) \u2014 waiting for their choice\u2026`;

  document.getElementById('order_first').style.display = isChooser ? '' : 'none';
  document.getElementById('order_second').style.display = isChooser ? '' : 'none';
  orderOverlay.querySelector('h2').textContent = isChooser ? '\ud83c\udfc6 You Won the Dice Roll!' : '\u23f3 Opponent Choosing\u2026';
}

/* ════════════════════ GAME OVER ════════════════════ */
export function showGameOver(state){
  gameoverOverlay.classList.remove('hidden');
  const isWinner = state.winner === playerId;
  const title = document.getElementById('gameover_title');
  title.textContent = isWinner ? 'YOU WIN!' : 'YOU LOSE';
  title.className = isWinner ? 'win' : 'lose';

  const reasons = {
    'no_life': 'No life cards remaining',
    'deck_empty': 'Deck empty \u2014 cannot draw',
    'mulligan_limit': 'Too many mulligans (7 attempts)',
    'retired': 'Player retired from the match',
  };
  document.getElementById('gameover_reason').textContent =
    reasons[state.lose_reason] || state.lose_reason || '';
}

/* ════════════════════ SETUP PHASE ════════════════════ */
export function renderSetupUI(state){
  const setupBanner = document.getElementById('setup_banner');
  setupBanner.style.display = 'block';
  stepBar.style.display = 'none';

  const gs = state.game_state;
  const mySetup = state.setup_state?.[playerId];
  const oppId = Object.keys(state.players).find(k=>k!==playerId);
  const oppSetup = oppId ? state.setup_state?.[oppId] : null;
  if(!mySetup) return;

  const instruction = document.getElementById('setup_instruction');
  const details = document.getElementById('setup_details');
  const mulliganBtn = document.getElementById('setup_mulligan_btn');
  const mulliganReadyBtn = document.getElementById('mulligan_ready_btn');
  const readyBtn = document.getElementById('setup_ready_btn');
  const oppInfo = document.getElementById('setup_opponent_info');

  const remaining = (mySetup.returning || 0) - (mySetup.returned || 0);

  /* ── Mulligan phase ── */
  if(gs === 'mulligan'){
    readyBtn.style.display = 'none';

    if(mySetup.ready){
      instruction.textContent = '\u2713 Hand confirmed! Waiting for opponent\u2026';
      details.textContent = '';
      mulliganBtn.style.display = 'none';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = true;
      mulliganReadyBtn.textContent = '\u2713 Confirmed';
    } else if(remaining > 0){
      instruction.textContent = `Click ${remaining} card(s) in hand to return to bottom of deck`;
      details.textContent = `Hand #${mySetup.hand_number} \u2014 Mulligan penalty: return ${mySetup.returning} card(s)`;
      mulliganBtn.style.display = 'none';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = true;
    } else if(!mySetup.has_debut){
      instruction.textContent = 'No Debut holomen in hand! You must mulligan.';
      details.textContent = `Hand #${mySetup.hand_number}`;
      mulliganBtn.style.display = '';
      mulliganBtn.disabled = false;
      mulliganBtn.textContent = mySetup.hand_number >= 6 ? '\ud83d\udd04 Mulligan (LAST CHANCE!)' : '\ud83d\udd04 Mulligan';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = true;
    } else if(mySetup.hand_number <= 1){
      instruction.textContent = 'You have Debut holomen. Confirm hand or use free mulligan.';
      details.textContent = 'Hand #1 \u2014 Free mulligan available';
      mulliganBtn.style.display = '';
      mulliganBtn.disabled = false;
      mulliganBtn.textContent = '\ud83d\udd04 Free Mulligan';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = false;
      mulliganReadyBtn.textContent = '\u2713 Confirm Hand';
    } else {
      instruction.textContent = `Hand #${mySetup.hand_number} \u2014 You have Debut holomen. Confirm your hand.`;
      details.textContent = 'Free mulligan used \u2014 must confirm';
      mulliganBtn.style.display = 'none';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = false;
      mulliganReadyBtn.textContent = '\u2713 Confirm Hand';
    }

    if(oppSetup){
      oppInfo.textContent = oppSetup.ready
        ? 'Opponent: \u2713 Hand confirmed'
        : `Opponent: Choosing hand\u2026 (Hand #${oppSetup.hand_number})`;
    }
    return;
  }

  /* ── Setup (placement) phase ── */
  mulliganBtn.style.display = 'none';
  mulliganReadyBtn.style.display = 'none';
  readyBtn.style.display = '';

  if(mySetup.ready){
    instruction.textContent = '\u2713 Ready! Waiting for opponent\u2026';
    details.textContent = '';
    readyBtn.disabled = true;
    readyBtn.textContent = '\u2713 Ready';
  } else {
    instruction.textContent = mySetup.centre_placed
      ? 'Centre holomen placed (face-down)! Drag more to Back, or click Ready.'
      : 'Drag a Debut holomen from hand to Centre or Back (face-down)';
    details.textContent = `Place holomen face-down. Cards revealed when both ready. (First player: ${state.players[state.turn_player_id]?.name || '?'})`;
    readyBtn.disabled = !mySetup.centre_placed;
    readyBtn.textContent = '\u2713 Ready';
  }

  if(oppSetup){
    oppInfo.textContent = oppSetup.ready
      ? 'Opponent: \u2713 Ready'
      : `Opponent: Placing holomen\u2026`;
  }
}
