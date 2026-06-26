/* ══════════════════════════════════════════════════════════════
   hOCG Web Client – dual-playmat, full card functions, turn system
   ══════════════════════════════════════════════════════════════ */
let ws = null;
let playerId = null;
let matchId  = null;
let lastState = null;
let selectedCard = null;   // {card_number, from_zone}

const statusEl     = document.getElementById('status');
const phaseBadge   = document.getElementById('phase_badge');
const lobbyEl      = document.getElementById('lobby');
const lobbyStatus  = document.getElementById('lobby_status');
const lobbyPlayers = document.getElementById('lobby_players');
const handTray     = document.getElementById('hand_tray');
const playHint     = document.getElementById('play_hint');
const ctxMenu      = document.getElementById('context_menu');
const modalContainer = document.getElementById('modal_container');

/* Turn system elements */
const stepBar        = document.getElementById('step_bar');
const turnInfo       = document.getElementById('turn_info');
const stepInfo       = document.getElementById('step_info');
const pendingBanner  = document.getElementById('pending_banner');
const diceOverlay    = document.getElementById('dice_overlay');
const orderOverlay   = document.getElementById('order_overlay');
const gameoverOverlay= document.getElementById('gameover_overlay');

/* ── Zone bbox definitions (original 2040×1280 playmat) ── */
const ZONE_DEFS = {
  life:       [59,51,361,529],
  holo_power: [1678,51,1981,266],
  collabo:    [551,121,764,422],
  centre:     [940,121,1153,422],
  oshi:       [1345,121,1560,422],
  deck:       [1766,335,1981,638],
  back:       [455,625,1658,1014],
  yell_deck:  [59,687,273,988],
  archive:    [1766,687,1981,988],
  hand:       [59,1060,1981,1280]
};
const NAT_W = 2040, NAT_H = 1044;

/* Zone categories for rendering */
const STACK_ZONES  = ['deck', 'yell_deck', 'archive'];
const HSTACK_ZONES = ['life', 'holo_power'];
const SINGLE_ZONES = ['centre', 'collabo', 'oshi'];
const MULTI_ZONES  = ['back'];
const PLAY_ZONES   = ['centre','collabo','back','oshi','archive','holo_power'];
const CARD_BACK         = '/assets/card_back.webp';
const YELL_LIFE_BACK   = '/assets/yell_life_card_back.png';

/* ── Helpers ── */
function setStatus(t){ statusEl.textContent = t; }
function sendAction(action){
  if(!ws||ws.readyState!==1) return;
  ws.send(JSON.stringify({type:'action', action}));
}

/* Color mapping for yell cards: Japanese color name → CSS color */
const YELL_COLORS = {
  '白': '#e8e8e8',
  '赤': '#e03030',
  '青': '#3060e0',
  '緑': '#30b030',
  '黄': '#e0c020',
  '紫': '#9040c0',
};

/* Build a yell badge showing colored dots grouped by color */
function renderYellBadge(yellArr, parentEl, posAbsolute){
  if(!yellArr || !yellArr.length) return;
  /* Count yells per color */
  const colorCounts = {};
  for(const y of yellArr){
    const colors = Array.isArray(y.color) ? y.color : (y.color ? [y.color] : ['黄']);
    for(const c of colors){
      colorCounts[c] = (colorCounts[c]||0) + 1;
    }
  }
  const b = document.createElement('div');
  b.className = 'badge badge-yell yell-color-badge';
  if(posAbsolute) b.style.position = 'absolute';
  for(const [col, cnt] of Object.entries(colorCounts)){
    const dot = document.createElement('span');
    dot.className = 'yell-dot';
    dot.style.background = YELL_COLORS[col] || '#e0c020';
    dot.textContent = cnt > 1 ? cnt : '';
    b.appendChild(dot);
  }
  parentEl.appendChild(b);
}
function cardImgSrc(cd){
  if(cd && cd.face_up && cd.image_file) return `/cards/${cd.image_file}`;
  /* Use yell/life card back for yell-type cards */
  if(cd && cd.card_type === 'エール') return YELL_LIFE_BACK;
  return CARD_BACK;
}

/* ════════════════════ CONNECTION ════════════════════ */
document.getElementById('connect').onclick = () => {
  const host = document.getElementById('server').value.trim();
  const name = document.getElementById('name').value.trim()||'Player';
  lobbyStatus.textContent = 'Connecting…';
  ws = new WebSocket(`ws://${host}/ws`);
  ws.onopen = () => { ws.send(JSON.stringify({type:'join', name})); };
  ws.onmessage = ev => {
    try{ handleMsg(JSON.parse(ev.data)); }catch(e){console.error(e);}
  };
  ws.onclose = () => {
    setStatus('Disconnected');
    lobbyStatus.textContent = 'Disconnected';
  };
  ws.onerror = () => {
    setStatus('Connection error');
  };
};

/* ════════════════════ MESSAGE ROUTING ════════════════════ */
function handleMsg(msg){
  if(msg.type==='joined'){
    playerId = msg.player_id;
    matchId  = msg.match_id;
    lobbyStatus.textContent = `Joined as Player ${playerId} – load your deck`;
    document.getElementById('deck_row').style.display = 'flex';
    return;
  }
  if(msg.type==='player_disconnected'){
    const who = msg.player_name || msg.player_id;
    alert(`Player "${who}" has disconnected. Returning to lobby.`);
    /* Reset to lobby */
    ws.close();
    ws = null;
    playerId = null;
    matchId = null;
    lastState = null;
    selectedCard = null;
    document.getElementById('lobby').classList.remove('hidden');
    document.getElementById('game_area').classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'none';
    lobbyStatus.textContent = 'Opponent disconnected. Connect again to start a new match.';
    return;
  }
  if(msg.type==='action_result'){
    /* Optional: show brief feedback for failed actions */
    if(msg.result && !msg.result.success){
      console.warn('Action failed:', msg.result.reason);
    }
    return;
  }
  if(msg.type==='state_update'){
    lastState = msg.state;
    if(lastState) updateFromState(lastState);
    return;
  }
  if(msg.type==='setup_phase'){
    lastState = msg.state;
    lobbyEl.classList.add('hidden');
    renderSetupUI(lastState);
    renderGame(lastState);
    return;
  }
  if(msg.type==='dice_phase'){
    lastState = msg.state;
    lobbyEl.classList.add('hidden');
    showDiceOverlay(lastState);
    return;
  }
  if(msg.type==='match_start'){
    lastState = msg.state;
    lobbyEl.classList.add('hidden');
    diceOverlay.classList.add('hidden');
    orderOverlay.classList.add('hidden');
    if(lastState) renderGame(lastState);
    return;
  }
}

function updateFromState(state){
  const gs = state.game_state;

  /* Lobby */
  if(gs === 'lobby'){
    const pids = Object.keys(state.players);
    let lines = pids.map(pid=>{
      const p = state.players[pid];
      const me = pid===playerId?' (you)':'';
      const rdy = p.ready?'✓ ready':'waiting…';
      return `Player ${pid}${me}: ${p.name} – ${rdy}${p.deck_code?' ['+p.deck_code+']':''}`;
    });
    lobbyPlayers.innerHTML = lines.join('<br/>');
    return;
  }

  /* Mulligan phase (after dice & choose order) */
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

  /* Setup phase (placement after dice) */
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

  /* Dice roll */
  if(gs === 'dice_roll'){
    lobbyEl.classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'none';
    showDiceOverlay(state);
    return;
  }

  /* Choose order */
  if(gs === 'choose_order'){
    lobbyEl.classList.add('hidden');
    diceOverlay.classList.add('hidden');
    document.getElementById('setup_banner').style.display = 'none';
    showOrderOverlay(state);
    return;
  }

  /* Game over */
  if(gs === 'game_over'){
    diceOverlay.classList.add('hidden');
    orderOverlay.classList.add('hidden');
    lobbyEl.classList.add('hidden');
    renderGame(state);
    showGameOver(state);
    return;
  }

  /* Playing */
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

/* ════════════════════ DICE ROLL ════════════════════ */
function showDiceOverlay(state){
  diceOverlay.classList.remove('hidden');
  const pids = Object.keys(state.players);
  const rolls = state.dice_rolls || {};

  /* Show player names and rolls */
  const p1 = state.players[pids[0]], p2 = state.players[pids[1]];
  document.getElementById('dice_p1_name').textContent = p1 ? p1.name + (pids[0]===playerId?' (You)':'') : '—';
  document.getElementById('dice_p2_name').textContent = p2 ? p2.name + (pids[1]===playerId?' (You)':'') : '—';

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

  /* Status text */
  const diceStatus = document.getElementById('dice_status');
  if(v1 != null && v2 != null && v1 === v2){
    diceStatus.textContent = `Tie! (${v1} vs ${v2}) — Roll again`;
    diceBtn.disabled = false;
    diceBtn.textContent = 'Roll Again';
  } else if(myRoll != null) {
    diceStatus.textContent = 'Waiting for opponent to roll…';
  } else {
    diceStatus.textContent = 'Click to roll your dice!';
  }
}

document.getElementById('dice_btn').onclick = ()=>{
  sendAction({type:'roll_dice'});
};

/* ════════════════════ CHOOSE ORDER ════════════════════ */
function showOrderOverlay(state){
  orderOverlay.classList.remove('hidden');
  const chooser = state.dice_chooser;
  const isChooser = chooser === playerId;
  const rolls = state.dice_rolls || {};
  const pids = Object.keys(state.players);

  document.getElementById('order_status').textContent =
    isChooser
      ? `You rolled higher! (${rolls[pids[0]]} vs ${rolls[pids[1]]}) — Choose your turn order`
      : `Opponent rolled higher — waiting for their choice…`;

  document.getElementById('order_first').style.display = isChooser ? '' : 'none';
  document.getElementById('order_second').style.display = isChooser ? '' : 'none';
  orderOverlay.querySelector('h2').textContent = isChooser ? '🏆 You Won the Dice Roll!' : '⏳ Opponent Choosing…';
}

document.getElementById('order_first').onclick = ()=>{
  sendAction({type:'choose_order', choice:'first'});
};
document.getElementById('order_second').onclick = ()=>{
  sendAction({type:'choose_order', choice:'second'});
};

/* ════════════════════ GAME OVER ════════════════════ */
function showGameOver(state){
  gameoverOverlay.classList.remove('hidden');
  const isWinner = state.winner === playerId;
  const title = document.getElementById('gameover_title');
  title.textContent = isWinner ? 'YOU WIN!' : 'YOU LOSE';
  title.className = isWinner ? 'win' : 'lose';

  const reasons = {
    'no_life': 'No life cards remaining',
    'deck_empty': 'Deck empty — cannot draw',
    'mulligan_limit': 'Too many mulligans (7 attempts)',
  };
  document.getElementById('gameover_reason').textContent =
    reasons[state.lose_reason] || state.lose_reason || '';
}

/* ════════════════════ SETUP PHASE ════════════════════ */
function renderSetupUI(state){
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
      instruction.textContent = '✓ Hand confirmed! Waiting for opponent…';
      details.textContent = '';
      mulliganBtn.style.display = 'none';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = true;
      mulliganReadyBtn.textContent = '✓ Confirmed';
    } else if(remaining > 0){
      instruction.textContent = `Click ${remaining} card(s) in hand to return to bottom of deck`;
      details.textContent = `Hand #${mySetup.hand_number} — Mulligan penalty: return ${mySetup.returning} card(s)`;
      mulliganBtn.style.display = 'none';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = true;
    } else if(!mySetup.has_debut){
      instruction.textContent = 'No Debut holomen in hand! You must mulligan.';
      details.textContent = `Hand #${mySetup.hand_number}`;
      mulliganBtn.style.display = '';
      mulliganBtn.disabled = false;
      mulliganBtn.textContent = mySetup.hand_number >= 6 ? '🔄 Mulligan (LAST CHANCE!)' : '🔄 Mulligan';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = true;
    } else if(mySetup.hand_number <= 1){
      instruction.textContent = 'You have Debut holomen. Confirm hand or use free mulligan.';
      details.textContent = 'Hand #1 — Free mulligan available';
      mulliganBtn.style.display = '';
      mulliganBtn.disabled = false;
      mulliganBtn.textContent = '🔄 Free Mulligan';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = false;
      mulliganReadyBtn.textContent = '✓ Confirm Hand';
    } else {
      instruction.textContent = `Hand #${mySetup.hand_number} — You have Debut holomen. Confirm your hand.`;
      details.textContent = 'Free mulligan used — must confirm';
      mulliganBtn.style.display = 'none';
      mulliganReadyBtn.style.display = '';
      mulliganReadyBtn.disabled = false;
      mulliganReadyBtn.textContent = '✓ Confirm Hand';
    }

    if(oppSetup){
      oppInfo.textContent = oppSetup.ready
        ? 'Opponent: ✓ Hand confirmed'
        : `Opponent: Choosing hand… (Hand #${oppSetup.hand_number})`;
    }
    return;
  }

  /* ── Setup (placement) phase ── */
  mulliganBtn.style.display = 'none';
  mulliganReadyBtn.style.display = 'none';
  readyBtn.style.display = '';

  if(mySetup.ready){
    instruction.textContent = '✓ Ready! Waiting for opponent…';
    details.textContent = '';
    readyBtn.disabled = true;
    readyBtn.textContent = '✓ Ready';
  } else {
    instruction.textContent = mySetup.centre_placed
      ? 'Centre holomen placed (face-down)! Drag more to Back, or click Ready.'
      : 'Drag a Debut holomen from hand to Centre or Back (face-down)';
    details.textContent = `Place holomen face-down. Cards revealed when both ready. (First player: ${state.players[state.turn_player_id]?.name || '?'})`;
    readyBtn.disabled = !mySetup.centre_placed;
    readyBtn.textContent = '✓ Ready';
  }

  if(oppSetup){
    oppInfo.textContent = oppSetup.ready
      ? 'Opponent: ✓ Ready'
      : `Opponent: Placing holomen…`;
  }
}

document.getElementById('setup_mulligan_btn').onclick = ()=> sendAction({type:'setup_mulligan'});
document.getElementById('mulligan_ready_btn').onclick = ()=> sendAction({type:'mulligan_ready'});
document.getElementById('setup_ready_btn').onclick = ()=> sendAction({type:'setup_ready'});

/* ════════════════════ LOAD DECK ════════════════════ */
document.getElementById('load_deck').onclick = () => {
  const code = document.getElementById('deck_code').value.trim();
  const site = document.querySelector('input[name="deck_site"]:checked').value;
  if(!code) return;
  lobbyStatus.textContent = 'Loading deck…';
  document.getElementById('load_deck').disabled = true;
  sendAction({type:'load_deck', deck_code:code, deck_site:site});
  setTimeout(()=> document.getElementById('load_deck').disabled = false, 3000);
};

/* ════════════════════ GAME RENDERING ════════════════════ */

const STEP_NAMES = ['reset','draw','cheer','main','performance','end'];
const STEP_LABELS = {
  reset: '1. Reset', draw: '2. Draw', cheer: '3. Cheer',
  main: '4. Main', performance: '5. Performance', end: '6. End',
};
const STEP_DESCRIPTIONS = {
  reset: 'Collabo→Back, un-rest holomen, fill centre if empty',
  draw: 'Drawing a card…',
  cheer: 'Click a stage holomen or drag from Yell Deck to attach yell (or skip)',
  main: 'Place / Bloom / Collabo / Support / Baton Touch',
  performance: 'Use arts to attack opponent holomen',
  end: 'End of turn. Fill centre if empty.',
};

function renderGame(state){
  if(!playerId) return;
  const myData = state.players[playerId];
  const oppId  = Object.keys(state.players).find(k=>k!==playerId);
  const opData = oppId ? state.players[oppId] : null;
  const isMyTurn = state.turn_player_id === playerId;
  const step = state.step;
  const allowed = state.allowed_actions || [];

  /* Phase badge */
  phaseBadge.textContent = step || state.game_state || '—';

  /* Status */
  if(state.game_state === 'mulligan'){
    setStatus('Mulligan Phase — Choose your starting hand');
  } else if(state.game_state === 'setup'){
    setStatus('Setup Phase — Place holomen face-down');
  } else if(state.pending_life_deduction === playerId){
    setStatus('⚡ Your holomen was knocked out! Deduct a life card.');
  } else if(state.pending_centre_fill === playerId){
    setStatus('🎯 Move a holomen to centre position!');
  } else if(state.pending_life_deduction || state.pending_centre_fill){
    setStatus('Waiting for opponent…');
  } else if(state.step_state && state.step_state.pending_support){
    setStatus(`⚡ Select cards for ${state.step_state.pending_support.card_name}`);
  } else {
    setStatus(isMyTurn ? "Your turn" : "Opponent's turn");
  }

  /* Player labels */
  document.getElementById('you_label').textContent = `You – ${myData.name}`;
  document.getElementById('opp_label').textContent = opData ? opData.name : 'Opponent';

  /* Debug JSON */
  document.getElementById('you_json').textContent = JSON.stringify(myData,null,2);
  document.getElementById('opp_json').textContent = JSON.stringify(opData,null,2);

  /* Step bar */
  if(state.game_state === 'playing'){
    stepBar.style.display = 'flex';
    turnInfo.textContent = `Turn ${state.turn_number} — ${isMyTurn ? 'Your Turn' : "Opponent's Turn"}`;

    const stepIdx = state.step_index;
    stepBar.querySelectorAll('.step-chip').forEach((chip, i) => {
      chip.classList.remove('active','done','upcoming');
      if(isMyTurn){
        if(i < stepIdx) chip.classList.add('done');
        else if(i === stepIdx) chip.classList.add('active');
        else chip.classList.add('upcoming');
      } else {
        chip.classList.add('upcoming');
      }
    });
    stepInfo.textContent = isMyTurn ? (STEP_DESCRIPTIONS[step]||'') : '';

    /* Next-step button in step bar (always visible at top) */
    const nextStepBtn = document.getElementById('next_step_btn');
    if(isMyTurn && step === 'cheer'){
      nextStepBtn.style.display = '';
      nextStepBtn.textContent = 'Skip Cheer →';
      nextStepBtn.onclick = ()=> sendAction({type:'skip_cheer'});
    } else if(isMyTurn && step === 'main'){
      nextStepBtn.style.display = '';
      nextStepBtn.textContent = 'End Main →';
      nextStepBtn.onclick = ()=> sendAction({type:'end_main'});
    } else if(isMyTurn && step === 'performance'){
      nextStepBtn.style.display = '';
      nextStepBtn.textContent = 'End Performance →';
      nextStepBtn.onclick = ()=> sendAction({type:'end_performance'});
    } else {
      nextStepBtn.style.display = 'none';
    }
  } else {
    stepBar.style.display = 'none';
  }

  /* Pending banner */
  if(state.pending_life_deduction === playerId){
    pendingBanner.textContent = '⚡ KNOCKOUT — Click "Deduct Life" to attach a life card to one of your holomen';
    pendingBanner.style.display = 'block';
    pendingBanner.style.background = '#8b1313';
  } else if(state.pending_centre_fill === playerId){
    pendingBanner.textContent = '🎯 Centre is empty! Right-click a holomen in Back or Hand → move to Centre';
    pendingBanner.style.display = 'block';
    pendingBanner.style.background = '#8b4513';
  } else if(state.step_state && state.step_state.pending_support){
    const ps = state.step_state.pending_support;
    const remaining = ps.picks ? ps.picks.length : 0;
    pendingBanner.textContent = `⚡ ${ps.card_name} — ${remaining} pick${remaining!==1?'s':''} remaining`;
    pendingBanner.style.display = 'block';
    pendingBanner.style.background = '#1a4a6a';
  } else {
    pendingBanner.style.display = 'none';
  }

  /* Update action buttons visibility based on allowed actions */
  updateActionButtons(state, isMyTurn, allowed);

  /* Render playmats */
  renderPlaymat('you_playmat', myData.zones, true);
  renderPlaymat('opp_playmat', opData ? opData.zones : null, false);
  renderHandTray(myData.zones.hand || []);

  /* Check for pending support picks and auto-show picker */
  if(state.game_state === 'playing'){
    checkPendingSupportPicks(state);
  }
}

/* ── Show/hide action buttons per step ── */
function updateActionButtons(state, isMyTurn, allowed){
  const step = state.step;

  /* Hide all first */
  const btns = ['draw','skip_cheer','end_main','end_performance','end_turn',
                'shuffle','shuffle_yell','deduct_life_btn','hand_to_deck',
                'search_deck_btn','search_archive_btn','peek_top3_btn','peek_top5_btn'];
  btns.forEach(id => {
    const el = document.getElementById(id);
    if(el) el.style.display = 'none';
  });

  /* Pending life deduction — show deduct life for this player */
  if(state.pending_life_deduction === playerId){
    show('deduct_life_btn');
    return;
  }

  /* Not my turn and no pending actions — hide all */
  if(!isMyTurn) return;

  /* Step-based buttons */
  if(step === 'cheer'){
    show('skip_cheer');
  }
  if(step === 'main'){
    show('draw');
    show('end_main');
    show('shuffle');
    show('shuffle_yell');
    show('hand_to_deck');
    show('search_deck_btn');
    show('search_archive_btn');
    show('peek_top3_btn');
    show('peek_top5_btn');
  }
  if(step === 'performance'){
    show('end_performance');
  }
  if(step === 'end'){
    show('end_turn');
  }

  function show(id){ const e = document.getElementById(id); if(e) e.style.display = ''; }
}

/* ── Scale bbox relative to playmat img ── */
function scaledBBox(bbox, img){
  const r = img.getBoundingClientRect();
  const sx = r.width/NAT_W, sy = r.height/NAT_H;
  return [Math.round(bbox[0]*sx), Math.round(bbox[1]*sy),
          Math.round(bbox[2]*sx), Math.round(bbox[3]*sy)];
}

/* ════════════════════ RENDER PLAYMAT ════════════════════ */
function renderPlaymat(id, zones, isOwner){
  const wrap = document.getElementById(id);
  const img  = wrap.querySelector('img.playmat-bg');
  wrap.querySelectorAll('.zone').forEach(n=>n.remove());
  if(!zones) return;

  for(const zname of Object.keys(ZONE_DEFS)){
    if(zname==='hand') continue;
    const zd = zones[zname];
    if(zd===undefined) continue;

    const z = document.createElement('div');
    z.className = 'zone';
    z.dataset.zone = zname;
    const [x1,y1,x2,y2] = scaledBBox(ZONE_DEFS[zname], img);
    const zw = x2-x1, zh = y2-y1;
    Object.assign(z.style,{left:x1+'px',top:y1+'px',width:zw+'px',height:zh+'px'});

    const count = Array.isArray(zd) ? zd.length : (zd&&zd.count!=null ? zd.count : 0);
    const titleEl = document.createElement('div');
    titleEl.className = 'zone-title';
    titleEl.textContent = `${zname} (${count})`;
    z.appendChild(titleEl);

    const cards = document.createElement('div');
    cards.className = 'zone-cards';

    /* Determine rendering mode */
    if(zd && zd.hidden){
      /* Opponent hidden zone → card backs, zone-aware */
      renderHiddenZone(cards, zd.count, zw, zh, zname);
    } else if(STACK_ZONES.includes(zname)){
      renderStackZone(cards, Array.isArray(zd)?zd:[], zname, zw, zh, isOwner);
    } else if(HSTACK_ZONES.includes(zname)){
      renderHStackZone(cards, Array.isArray(zd)?zd:[], zname, zw, zh, isOwner);
    } else if(SINGLE_ZONES.includes(zname)){
      renderSingleZone(cards, Array.isArray(zd)?zd:[], zname, zw, zh, isOwner);
    } else if(MULTI_ZONES.includes(zname)){
      renderMultiZone(cards, Array.isArray(zd)?zd:[], zname, zw, zh, isOwner);
    }

    z.appendChild(cards);

    /* Drop target & click-to-play (owner only) */
    if(isOwner){
      z.addEventListener('dragover', ev=>{ev.preventDefault();z.classList.add('drag-over');});
      z.addEventListener('dragleave', ()=>z.classList.remove('drag-over'));
      z.addEventListener('drop', ev=>{
        ev.preventDefault(); z.classList.remove('drag-over');
        try{
          const d = JSON.parse(ev.dataTransfer.getData('text/plain'));

          /* ── Setup phase: drag Debut holomen from hand → place face-down ── */
          if(lastState && lastState.game_state === 'setup'){
            const mySetup = lastState.setup_state?.[playerId];
            const remaining = (mySetup?.returning || 0) - (mySetup?.returned || 0);
            if(remaining <= 0 && d.from === 'hand' && d.card_type && d.card_type.includes('ホロメン') && d.bloom_level === 'Debut'){
              if(zname === 'centre' || zname === 'back'){
                sendAction({type:'setup_place', zone:zname, card_number:d.card});
              }
            }
            return;
          }

          /* ── Cheer step: drop onto stage holomen → attach yell ── */
          if(lastState && lastState.step === 'cheer' && ['centre','collabo','back'].includes(zname)){
            let targetIdx = 0;
            if(MULTI_ZONES.includes(zname)){
              const slots = z.querySelectorAll('.multi-slot');
              let minDist = Infinity;
              slots.forEach((sl, si) => {
                const r = sl.getBoundingClientRect();
                const cx = r.left + r.width/2;
                const dist = Math.abs(ev.clientX - cx);
                if(dist < minDist){ minDist = dist; targetIdx = si; }
              });
            }
            sendAction({type:'attach_yell', zone:zname, card_index:targetIdx});
            return;
          }

          /* Bloom shortcut: dropping a holomen from hand onto a card image in an occupied stage zone */
          const stageHasCard = (SINGLE_ZONES.includes(zname) || MULTI_ZONES.includes(zname))
            && Array.isArray(zd) && zd.length > 0;
          const fromHand = d.from === 'hand';
          const isHolomen = d.card_type && d.card_type.includes('ホロメン');
          /* Only bloom if drop landed on the card image itself */
          const droppedOnCard = ev.target.closest('.main-card,.card-in-slot');
          if(stageHasCard && fromHand && isHolomen && droppedOnCard){
            /* Single zones bloom onto index 0; multi zones: find closest slot via drop position */
            let targetIdx = 0;
            if(MULTI_ZONES.includes(zname)){
              const slots = z.querySelectorAll('.multi-slot');
              let minDist = Infinity;
              slots.forEach((sl, si) => {
                const r = sl.getBoundingClientRect();
                const cx = r.left + r.width/2;
                const dist = Math.abs(ev.clientX - cx);
                if(dist < minDist){ minDist = dist; targetIdx = si; }
              });
            }
            sendAction({type:'bloom', zone:zname, card_index:targetIdx, hand_card_number:d.card});
          } else {
            /* Drop to holo_power should be face-down */
            const faceUp = zname === 'holo_power' ? false : true;
            sendAction({type:'move', from_zone:d.from, to_zone:zname, card_number:d.card, face_up:faceUp});
          }
        }catch(e){}
      });
      z.addEventListener('click', ev=>{
        if(!selectedCard) return;
        if(ev.target.closest('.main-card,.card-in-slot,.card-thumb,.stack-card')) return;
        sendAction({type:'play_card', card_number:selectedCard.card_number, zone:zname, face_up:true});
        clearSelection();
      });
    }

    z.classList.toggle('play-target', isOwner && !!selectedCard && PLAY_ZONES.includes(zname));
    wrap.appendChild(z);
  }
}

/* ═══════ ZONE RENDERERS ═══════ */

/* ── Hidden zone: card backs for opponent (zone-aware) ── */
function renderHiddenZone(container, count, zw, zh, zname){
  const d = document.createElement('div');
  if(count <= 0){ d.className = 'hidden-display'; container.appendChild(d); return; }

  if(HSTACK_ZONES.includes(zname)){
    /* Life / Holo Power: horizontal card backs stacked 15% visible */
    d.className = 'hstack-display';
    const pad = 4;
    const visibleFraction = 0.15;
    /* Card portrait: cw×ch. After rotate 90° visual = ch × cw */
    const maxVisualW = zw - pad*2;
    let ch = maxVisualW;  /* after rotation, visual_width = ch */
    let cw = ch * 0.717;
    const maxVisualH = zh - pad*2 - 14;
    if(count === 1){
      if(cw > maxVisualH) { cw = maxVisualH; ch = cw / 0.717; if(ch > maxVisualW){ ch = maxVisualW; cw = ch * 0.717; } }
    } else {
      const needed = cw * (1 + (count-1)*visibleFraction);
      if(needed > maxVisualH){ cw = maxVisualH / (1 + (count-1)*visibleFraction); ch = cw / 0.717; if(ch > maxVisualW){ ch = maxVisualW; cw = ch * 0.717; } }
    }
    const visibleStrip = Math.round(cw * visibleFraction);
    const startY = pad + 12;
    const offsetX = (ch - cw) / 2;
    const offsetY = (cw - ch) / 2;
    for(let i = 0; i < count; i++){
      const img = document.createElement('img');
      img.className = 'hstack-card';
      img.src = (zname === 'life') ? YELL_LIFE_BACK : CARD_BACK;
      img.style.width = cw + 'px';
      img.style.height = ch + 'px';
      img.style.left = (pad + offsetX) + 'px';
      img.style.top = (startY + i * visibleStrip + offsetY) + 'px';
      img.style.transform = 'rotate(90deg)';
      img.style.zIndex = i;
      d.appendChild(img);
    }
    const badge = document.createElement('div');
    badge.className = 'count-badge';
    badge.textContent = `×${count}`;
    d.appendChild(badge);
  } else {
    /* Deck / Yell / Archive / Hand: single card back stack */
    d.className = 'hidden-display';
    const pad = 6;
    const cardW = Math.min(zw - pad*2, (zh - pad*2 - 16) * 0.717);
    const cardH = cardW / 0.717;
    const img = document.createElement('img');
    img.className = 'back-img';
    img.src = (zname === 'yell_deck' || zname === 'life') ? YELL_LIFE_BACK : CARD_BACK;
    img.style.width = cardW+'px';
    img.style.height = cardH+'px';
    d.appendChild(img);
    if(count > 1){
      const shadow = document.createElement('img');
      shadow.className = 'back-img';
      shadow.src = (zname === 'yell_deck' || zname === 'life') ? YELL_LIFE_BACK : CARD_BACK;
      shadow.style.cssText = `width:${cardW}px;height:${cardH}px;position:absolute;z-index:-1;filter:brightness(0.6);`;
      shadow.style.transform = 'translate(3px,3px)';
      d.appendChild(shadow);
    }
    const badge = document.createElement('div');
    badge.className = 'count-badge';
    badge.textContent = `×${count}`;
    d.appendChild(badge);
  }
  container.appendChild(d);
}

/* ── Stack zone: deck, archive (show top card + count) ── */
function renderStackZone(container, cards, zname, zw, zh, isOwner){
  const d = document.createElement('div');
  d.className = 'stack-display';
  if(!cards.length){ container.appendChild(d); return; }

  const pad = 4;
  const topCard = cards[cards.length - 1];
  const cardW = Math.min(zw - pad*2, (zh - pad*2 - 14) * 0.717);
  const cardH = cardW / 0.717;

  /* Deck/yell_deck face-down (card back), archive face-up (top card visible) */
  const faceDown = (zname === 'deck' || zname === 'yell_deck');
  const backImg = (zname === 'yell_deck') ? YELL_LIFE_BACK : CARD_BACK;
  const imgSrc = faceDown ? backImg : cardImgSrc(topCard);

  const img = document.createElement('img');
  img.className = 'stack-card';
  img.src = imgSrc;
  img.style.width = cardW+'px';
  img.style.height = cardH+'px';
  img.style.cursor = 'pointer';
  if(!faceDown) img.addEventListener('click', ()=> showZoom(img.src));
  /* Make yell_deck top card draggable during cheer step */
  if(isOwner && zname === 'yell_deck'){
    img.draggable = true;
    img.addEventListener('dragstart', ev=>{
      ev.dataTransfer.setData('text/plain', JSON.stringify({card:'yell_top', from:'yell_deck'}));
    });
  }
  if(isOwner && zname === 'archive'){
    img.addEventListener('contextmenu', ev=>{
      ev.preventDefault(); ev.stopPropagation();
      showCardContextMenu(ev.clientX, ev.clientY, zname, cards.length-1, topCard);
    });
  }
  d.appendChild(img);
  /* Depth shadow for stacks > 1 */
  if(cards.length > 1){
    const shadow = document.createElement('img');
    shadow.className = 'stack-card';
    shadow.src = imgSrc;
    shadow.style.cssText = `width:${cardW}px;height:${cardH}px;position:absolute;z-index:-1;filter:brightness(0.6);`;
    shadow.style.transform = 'translate(2px,2px)';
    d.appendChild(shadow);
  }

  const badge = document.createElement('div');
  badge.className = 'count-badge';
  badge.textContent = `×${cards.length}`;
  d.appendChild(badge);
  container.appendChild(d);
}

/* ── Horizontal stack zone: life, holo_power, yell_deck ── */
function renderHStackZone(container, cards, zname, zw, zh, isOwner){
  const d = document.createElement('div');
  d.className = 'hstack-display';
  if(!cards.length){ container.appendChild(d); return; }

  const pad = 4;
  const n = cards.length;
  const visibleFraction = 0.15;

  /* Cards displayed rotated 90° (landscape), stacked top-to-bottom.
     Card portrait: cw × ch.  After CSS rotate(90deg): visual = ch × cw.
     We want visual_width (= ch) ≤ zone_width. */
  const maxVisualW = zw - pad*2;
  let ch = maxVisualW;          /* portrait height → becomes visual width */
  let cw = ch * 0.717;          /* portrait width  → becomes visual height */
  const maxVisualH = zh - pad*2 - 14;
  if(n === 1){
    if(cw > maxVisualH){ cw = maxVisualH; ch = cw / 0.717; if(ch > maxVisualW){ ch = maxVisualW; cw = ch * 0.717; }}
  } else {
    const needed = cw * (1 + (n-1)*visibleFraction);
    if(needed > maxVisualH){ cw = maxVisualH / (1 + (n-1)*visibleFraction); ch = cw / 0.717; if(ch > maxVisualW){ ch = maxVisualW; cw = ch * 0.717; }}
  }
  const visibleStrip = Math.round(cw * visibleFraction);
  const startY = pad + 12;
  /* rotate(90deg) offset: element dims cw×ch → visual ch×cw, center stays */
  const offsetX = (ch - cw) / 2;
  const offsetY = (cw - ch) / 2;

  for(let i = 0; i < n; i++){
    const card = cards[i];
    const img = document.createElement('img');
    img.className = 'hstack-card';
    img.src = cardImgSrc(card);
    img.style.width = cw + 'px';
    img.style.height = ch + 'px';
    img.style.left = (pad + offsetX) + 'px';
    img.style.top = (startY + i * visibleStrip + offsetY) + 'px';
    img.style.transform = 'rotate(90deg)';
    img.style.zIndex = i;
    img.addEventListener('click', ()=> showZoom(img.src));
    d.appendChild(img);
  }

  const badge = document.createElement('div');
  badge.className = 'count-badge';
  badge.textContent = `×${n}`;
  d.appendChild(badge);
  container.appendChild(d);
}

/* ── Helper: render peeking bloom & yell cards behind a front card ── */
function renderPeekCards(wrapper, card, cw, ch, isResting){
  /* Bloom stack: 13% visible each, peeking from bottom */
  const bloomArr = Array.isArray(card.stacked_cards) ? card.stacked_cards : [];
  const yellArr  = Array.isArray(card.attached_yells) ? card.attached_yells : [];
  const bloomPeek = 0.13;
  const yellPeek  = 0.10;

  /* Position everything absolutely inside wrapper */
  /* Calculate total extra space needed */
  const bloomExtra = bloomArr.length * (ch * bloomPeek);
  const yellExtra  = yellArr.length * (cw * yellPeek);

  /* Bloom cards peek from bottom (rendered below front card, stacking down) */
  for(let b = 0; b < bloomArr.length; b++){
    const bc = bloomArr[b];
    const bloomImg = document.createElement('img');
    bloomImg.className = 'peek-card peek-bloom';
    bloomImg.src = cardImgSrc(bc);
    bloomImg.style.width = cw + 'px';
    bloomImg.style.height = ch + 'px';
    bloomImg.style.position = 'absolute';
    bloomImg.style.bottom = -(bloomArr.length - b) * (ch * bloomPeek) + 'px';
    bloomImg.style.left = '50%';
    bloomImg.style.transform = 'translateX(-50%)' + (isResting ? ' rotate(90deg)' : '');
    bloomImg.style.zIndex = b;
    bloomImg.addEventListener('click', ()=> showZoom(bloomImg.src));
    wrapper.appendChild(bloomImg);
  }

  /* Yell cards peek from right side (stacking right) */
  for(let y = 0; y < yellArr.length; y++){
    const yc = yellArr[y];
    const yellImg = document.createElement('img');
    yellImg.className = 'peek-card peek-yell';
    yellImg.src = cardImgSrc(yc);
    yellImg.style.width = cw + 'px';
    yellImg.style.height = ch + 'px';
    yellImg.style.position = 'absolute';
    yellImg.style.right = -(yellArr.length - y) * (cw * yellPeek) + 'px';
    yellImg.style.top = '50%';
    yellImg.style.transform = 'translateY(-50%)';
    yellImg.style.zIndex = y;
    yellImg.addEventListener('click', ()=> showZoom(yellImg.src));
    wrapper.appendChild(yellImg);
  }
}

/* ── Single card zone: centre, collabo, oshi ── */
function renderSingleZone(container, cards, zname, zw, zh, isOwner){
  const d = document.createElement('div');
  d.className = 'single-display';
  if(!cards.length){ container.appendChild(d); return; }

  const card = cards[0];
  const pad = 4;
  const isResting = card.resting;

  /* Calculate card size with room for peeks */
  const bloomArr = Array.isArray(card.stacked_cards) ? card.stacked_cards : [];
  const yellArr  = Array.isArray(card.attached_yells) ? card.attached_yells : [];
  const bloomPeek = 0.13;
  const yellPeek  = 0.10;

  let cw, ch;
  if(isResting){
    ch = Math.min(zw - pad*2, (zh - pad*2 - 14));
    cw = ch * 0.717;
  } else {
    cw = Math.min(zw - pad*2, (zh - pad*2 - 14) * 0.717);
    ch = cw / 0.717;
  }
  /* Shrink if peeks would overflow */
  const yellExtraW = yellArr.length * (cw * yellPeek);
  const bloomExtraH = bloomArr.length * (ch * bloomPeek);
  if(cw + yellExtraW > zw - pad*2){
    const scale = (zw - pad*2) / (cw + yellExtraW);
    cw *= scale; ch *= scale;
  }
  if(ch + bloomExtraH > zh - pad*2 - 14){
    const scale = (zh - pad*2 - 14) / (ch + bloomExtraH);
    cw *= scale; ch *= scale;
  }

  /* Wrapper for card + peeks */
  const wrap = document.createElement('div');
  wrap.style.position = 'relative';
  wrap.style.width = cw + 'px';
  wrap.style.height = ch + 'px';
  wrap.style.zIndex = 10;

  /* Peek cards behind */
  renderPeekCards(wrap, card, cw, ch, isResting);

  /* Front card */
  const img = document.createElement('img');
  img.className = 'main-card' + (isResting ? ' resting' : '');
  img.src = cardImgSrc(card);
  img.style.width = cw+'px';
  img.style.height = ch+'px';
  img.style.position = 'relative';
  img.style.zIndex = 20;

  img.addEventListener('click', ()=>{
    /* During cheer step, clicking stage holomen attaches yell */
    if(isOwner && lastState && lastState.step === 'cheer' && ['centre','collabo','back'].includes(zname)){
      sendAction({type:'attach_yell', zone:zname, card_index:0});
      return;
    }
    showZoom(img.src);
  });
  img.addEventListener('dblclick', ev=>{ ev.stopPropagation(); showZoom(img.src); });

  if(isOwner){
    img.draggable = true;
    img.addEventListener('dragstart', ev=>{
      ev.dataTransfer.setData('text/plain', JSON.stringify({card:card.card_number, from:zname}));
    });
    img.addEventListener('contextmenu', ev=>{
      ev.preventDefault(); ev.stopPropagation();
      showCardContextMenu(ev.clientX, ev.clientY, zname, 0, card);
    });
  }
  wrap.appendChild(img);
  d.appendChild(wrap);

  /* Badges */
  const nYells = yellArr.length;
  const nStack = bloomArr.length;
  if(nYells){
    renderYellBadge(yellArr, d, false);
  }
  if(nStack){
    const b = document.createElement('div');
    b.className = 'badge badge-bloom';
    b.textContent = `B×${nStack}`;
    d.appendChild(b);
  }
  if(isResting){
    const b = document.createElement('div');
    b.className = 'badge badge-rest';
    b.textContent = 'REST';
    d.appendChild(b);
  }
  if(card.hp > 0){
    const b = document.createElement('div');
    b.className = 'badge badge-dmg';
    b.textContent = card.damage > 0 ? `${card.hp - card.damage}/${card.hp}` : `HP:${card.hp}`;
    if(card.damage > 0) b.style.background = 'rgba(220,40,40,0.9)';
    d.appendChild(b);
  }

  /* Attached supports badge */
  const nSupps = (card.attached_supports || []).length;
  if(nSupps){
    const sb = document.createElement('div');
    sb.className = 'badge';
    sb.style.background = 'rgba(200,80,180,0.85)';
    sb.textContent = `🔧×${nSupps}`;
    d.appendChild(sb);
  }

  container.appendChild(d);
}

/* ── Multi card zone: back (side by side) ── */
function renderMultiZone(container, cards, zname, zw, zh, isOwner){
  const d = document.createElement('div');
  d.className = 'multi-display';
  if(!cards.length){ container.appendChild(d); return; }

  const n = cards.length;
  const slotW = Math.floor(zw / Math.max(n, 1));

  for(let i = 0; i < n; i++){
    const card = cards[i];
    const slot = document.createElement('div');
    slot.className = 'multi-slot';

    const isResting = card.resting;

    /* Calculate card size with room for peeks */
    const bloomArr = Array.isArray(card.stacked_cards) ? card.stacked_cards : [];
    const yellArr  = Array.isArray(card.attached_yells) ? card.attached_yells : [];
    const bloomPeek = 0.13;
    const yellPeek  = 0.10;

    const pad = 2;
    let cw, ch;
    if(isResting){
      ch = Math.min(slotW - pad*2, zh - pad*2 - 4);
      cw = ch * 0.717;
    } else {
      cw = Math.min(slotW - pad*2, (zh - pad*2 - 4) * 0.717);
      ch = cw / 0.717;
    }
    /* Shrink if peeks overflow the slot */
    const yellExW = yellArr.length * (cw * yellPeek);
    const bloomExH = bloomArr.length * (ch * bloomPeek);
    if(cw + yellExW > slotW - pad*2){
      const s = (slotW-pad*2)/(cw+yellExW); cw*=s; ch*=s;
    }
    if(ch + bloomExH > zh - pad*2 - 4){
      const s = (zh-pad*2-4)/(ch+bloomExH); cw*=s; ch*=s;
    }

    /* Wrapper for card + peeks */
    const wrap = document.createElement('div');
    wrap.style.position = 'relative';
    wrap.style.width = cw + 'px';
    wrap.style.height = ch + 'px';

    renderPeekCards(wrap, card, cw, ch, isResting);

    const img = document.createElement('img');
    img.className = 'card-in-slot' + (isResting ? ' resting' : '');
    img.src = cardImgSrc(card);
    img.style.width = cw+'px';
    img.style.height = ch+'px';
    img.style.position = 'relative';
    img.style.zIndex = 20;

    img.addEventListener('click', ()=>{
      /* During cheer step, clicking stage holomen attaches yell */
      if(isOwner && lastState && lastState.step === 'cheer' && ['centre','collabo','back'].includes(zname)){
        sendAction({type:'attach_yell', zone:zname, card_index:i});
        return;
      }
      showZoom(img.src);
    });
    if(isOwner){
      img.draggable = true;
      img.addEventListener('dragstart', ev=>{
        ev.dataTransfer.setData('text/plain', JSON.stringify({card:card.card_number, from:zname}));
      });
      img.addEventListener('contextmenu', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        showCardContextMenu(ev.clientX, ev.clientY, zname, i, card);
      });
    }
    wrap.appendChild(img);
    slot.appendChild(wrap);

    /* Badges */
    const nYells = yellArr.length;
    const nStack = bloomArr.length;
    if(nYells){
      renderYellBadge(yellArr, slot, true);
    }
    if(nStack){
      const b = document.createElement('div');
      b.className = 'badge badge-bloom';
      b.textContent = `B×${nStack}`;
      b.style.position = 'absolute';
      slot.appendChild(b);
    }
    if(isResting){
      const b = document.createElement('div');
      b.className = 'badge badge-rest';
      b.textContent = 'REST';
      b.style.position = 'absolute';
      slot.appendChild(b);
    }
    if(card.hp > 0){
      const b = document.createElement('div');
      b.className = 'badge badge-dmg';
      b.textContent = card.damage > 0 ? `${card.hp - card.damage}/${card.hp}` : `HP:${card.hp}`;
      if(card.damage > 0) b.style.background = 'rgba(220,40,40,0.9)';
      b.style.position = 'absolute';
      slot.appendChild(b);
    }

    /* Attached supports badge */
    const nSupps = (card.attached_supports || []).length;
    if(nSupps){
      const sb = document.createElement('div');
      sb.className = 'badge';
      sb.style.cssText = 'background:rgba(200,80,180,0.85);position:absolute';
      sb.textContent = `🔧×${nSupps}`;
      slot.appendChild(sb);
    }

    d.appendChild(slot);
  }
  container.appendChild(d);
}

/* ════════════════════ HAND TRAY ════════════════════ */
function renderHandTray(handCards){
  handTray.innerHTML = '<div class="hand-label">HAND</div>';
  if(!Array.isArray(handCards)) return;
  handCards.forEach((cd, idx) => {
    const img = document.createElement('img');
    img.className = 'card-thumb';
    img.src = cardImgSrc(cd);
    img.title = `${cd.card_name||''} ${cd.card_number}`;
    img.draggable = true;
    img.dataset.card = cd.card_number;

    /* Click to select */
    img.addEventListener('click', ev=>{
      ev.stopPropagation();
      /* During mulligan returning phase, click to return card to deck */
      if(lastState && (lastState.game_state === 'mulligan' || lastState.game_state === 'setup')){
        const mySetup = lastState.setup_state?.[playerId];
        const remaining = (mySetup?.returning || 0) - (mySetup?.returned || 0);
        if(remaining > 0){
          sendAction({type:'setup_return_card', card_number:cd.card_number});
          return;
        }
      }
      if(selectedCard && selectedCard.card_number===cd.card_number){
        clearSelection();
      } else {
        selectedCard = {card_number:cd.card_number, from_zone:'hand'};
        handTray.querySelectorAll('.card-thumb').forEach(i=>i.classList.remove('selected'));
        img.classList.add('selected');
        playHint.textContent = `Selected ${cd.card_name||cd.card_number} — click zone to play`;
        if(lastState) renderGame(lastState);
      }
    });

    /* Right-click context menu */
    img.addEventListener('contextmenu', ev=>{
      ev.preventDefault(); ev.stopPropagation();
      showHandContextMenu(ev.clientX, ev.clientY, idx, cd);
    });

    /* Double-click zoom */
    img.addEventListener('dblclick', ev=>{
      ev.stopPropagation();
      showZoom(img.src);
    });

    /* Drag from hand */
    img.addEventListener('dragstart', ev=>{
      ev.dataTransfer.setData('text/plain', JSON.stringify({card:cd.card_number, from:'hand', card_type:cd.card_type||'', bloom_level:cd.bloom_level||''}));
    });

    handTray.appendChild(img);
  });
}

function clearSelection(){
  selectedCard = null;
  handTray.querySelectorAll('.card-thumb').forEach(i=>i.classList.remove('selected'));
  playHint.textContent = '';
  document.querySelectorAll('.zone.play-target').forEach(z=>z.classList.remove('play-target'));
}

/* ════════════════════ CONTEXT MENUS ════════════════════ */
function hideContextMenu(){ ctxMenu.style.display = 'none'; }
document.addEventListener('click', hideContextMenu);
document.addEventListener('contextmenu', ev=>{
  /* Only hide if not on a card */
  if(!ev.target.closest('.main-card,.card-in-slot,.card-thumb,.stack-card'))
    hideContextMenu();
});

function showContextMenuAt(x, y, items){
  ctxMenu.innerHTML = '';
  items.forEach(item => {
    if(item.type === 'header'){
      const h = document.createElement('div');
      h.className = 'menu-header';
      h.textContent = item.text;
      ctxMenu.appendChild(h);
    } else if(item.type === 'sep'){
      const s = document.createElement('div');
      s.className = 'menu-sep';
      ctxMenu.appendChild(s);
    } else {
      const m = document.createElement('div');
      m.className = 'menu-item' + (item.disabled ? ' disabled' : '');
      m.textContent = item.text;
      if(!item.disabled && item.action){
        m.addEventListener('click', ev=>{
          ev.stopPropagation();
          hideContextMenu();
          item.action();
        });
      }
      ctxMenu.appendChild(m);
    }
  });
  ctxMenu.style.left = x + 'px';
  ctxMenu.style.top = y + 'px';
  ctxMenu.style.display = 'block';
  /* Keep on screen */
  const rect = ctxMenu.getBoundingClientRect();
  if(rect.right > window.innerWidth) ctxMenu.style.left = (x - rect.width)+'px';
  if(rect.bottom > window.innerHeight) ctxMenu.style.top = (y - rect.height)+'px';
}

/* ── Hand card context menu ── */
function showHandContextMenu(x, y, idx, card){
  const isHolo = card.card_type && card.card_type.includes('ホロメン');
  const isDebut = card.bloom_level === 'Debut';
  const items = [
    {type:'header', text:`${card.card_name} (${card.bloom_level||card.card_type})`},
  ];

  /* Mulligan phase: limited actions */
  if(lastState && lastState.game_state === 'mulligan'){
    const mySetup = lastState.setup_state?.[playerId];
    const remaining = (mySetup?.returning || 0) - (mySetup?.returned || 0);
    if(remaining > 0){
      items.push({text:`Return to Deck (${remaining} left)`, action:()=>
        sendAction({type:'setup_return_card', card_number:card.card_number})});
    }
    items.push({type:'sep'});
    items.push({text:'View Card', action:()=> showZoom(cardImgSrc(card))});
    showContextMenuAt(x, y, items);
    return;
  }

  /* Setup (placement) phase: limited actions */
  if(lastState && lastState.game_state === 'setup'){
    const mySetup = lastState.setup_state?.[playerId];
    const remaining = (mySetup?.returning || 0) - (mySetup?.returned || 0);
    if(remaining > 0){
      items.push({text:`Return to Deck (${remaining} left)`, action:()=>
        sendAction({type:'setup_return_card', card_number:card.card_number})});
    } else {
      if(isHolo && isDebut){
        items.push({text:'→ Centre (Setup)', action:()=>
          sendAction({type:'setup_place', zone:'centre', card_number:card.card_number})});
        items.push({text:'→ Back (Setup)', action:()=>
          sendAction({type:'setup_place', zone:'back', card_number:card.card_number})});
      } else {
        items.push({text:'(Only Debut holomen can be placed)', disabled:true});
      }
    }
    items.push({type:'sep'});
    items.push({text:'View Card', action:()=> showZoom(cardImgSrc(card))});
    showContextMenuAt(x, y, items);
    return;
  }

  const isSupport = card.card_type && card.card_type.includes('サポート');

  if(isHolo){
    items.push({text:'→ Centre', action:()=> sendAction({type:'move_to_centre', from_zone:'hand', card_number:card.card_number})});
    items.push({text:'→ Back', action:()=> sendAction({type:'play_card', card_number:card.card_number, zone:'back', face_up:true})});
  }
  if(isSupport){
    items.push({text:'⚡ Use Support', action:()=> playSupportCard(card.card_number)});
  }
  items.push({type:'sep'});
  items.push({text:'→ Archive', action:()=> sendAction({type:'move', from_zone:'hand', to_zone:'archive', card_number:card.card_number})});
  items.push({text:'→ Deck Top', action:()=> sendAction({type:'move', from_zone:'hand', to_zone:'deck', card_number:card.card_number})});
  items.push({text:'→ Deck Bottom', action:()=> sendAction({type:'move', from_zone:'hand', to_zone:'deck', card_number:card.card_number, position:'bottom'})});
  items.push({text:'→ Holo Power', action:()=> sendAction({type:'move', from_zone:'hand', to_zone:'holo_power', card_number:card.card_number})});
  items.push({type:'sep'});
  items.push({text:'View Card', action:()=> showZoom(cardImgSrc(card))});
  showContextMenuAt(x, y, items);
}

/* ── Stage/field card context menu ── */
function showCardContextMenu(x, y, zname, idx, card){
  const items = [
    {type:'header', text:`${card.card_name} [${zname}]`},
  ];

  /* Setup phase: only allow returning to hand */
  if(lastState && lastState.game_state === 'setup'){
    if(['centre','back'].includes(zname)){
      items.push({text:'→ Hand (undo)', action:()=>
        sendAction({type:'setup_return_to_hand', zone:zname, card_number:card.card_number})});
    }
    items.push({text:'View Card', action:()=> showZoom(cardImgSrc(card))});
    showContextMenuAt(x, y, items);
    return;
  }

  const isStage = ['centre','collabo','back'].includes(zname);

  if(isStage){
    items.push({text:'Bloom', action:()=> showBloomPicker(zname, idx, card)});
    items.push({text:'Attach Yell', action:()=> sendAction({type:'attach_yell', zone:zname, card_index:idx})});
    items.push({text: card.resting ? 'Set Active' : 'Set Rest', action:()=> sendAction({type:'toggle_rest', zone:zname, card_index:idx})});
    items.push({type:'sep'});
  }

  if(zname === 'back'){
    items.push({text:'Collabo (deck→HP)', action:()=> sendAction({type:'collabo', from_zone:'back', card_index:idx})});
    items.push({text:'Force Collabo', action:()=> sendAction({type:'force_collabo', from_zone:'back', card_index:idx})});
    items.push({text:'→ Centre', action:()=> sendAction({type:'move_to_centre', from_zone:'back', card_number:card.card_number, card_index:idx})});
    items.push({type:'sep'});
  }
  if(zname === 'centre' || zname === 'collabo'){
    items.push({text:'Play Arts', action:()=> showArtsPicker(zname, idx, card)});
    items.push({text:'→ Back', action:()=> sendAction({type:'move', from_zone:zname, to_zone:'back', card_number:card.card_number})});
    if(zname === 'centre'){
      const cost = card.baton_touch || 0;
      const yellCount = (card.attached_yells||[]).length;
      const canBaton = yellCount >= cost;
      items.push({text:`Baton Touch (cost: ${cost} yell)`, disabled:!canBaton,
        action:()=> sendAction({type:'baton_touch'})});
    }
    items.push({type:'sep'});
  }

  if(isStage){
    items.push({text:'→ Archive (all)', action:()=> sendAction({type:'archive_card', zone:zname, card_index:idx, mode:'all'})});
    items.push({text:'→ Archive (card only)', action:()=> sendAction({type:'archive_card', zone:zname, card_index:idx, mode:'card_only'})});
  }

  if(zname === 'archive'){
    items.push({text:'→ Hand', action:()=> sendAction({type:'move', from_zone:'archive', to_zone:'hand', card_number:card.card_number})});
    items.push({text:'→ Deck Top', action:()=> sendAction({type:'move', from_zone:'archive', to_zone:'deck', card_number:card.card_number})});
    items.push({text:'→ Yell Deck Top', action:()=> sendAction({type:'move', from_zone:'archive', to_zone:'yell_deck', card_number:card.card_number})});
  }

  if(zname === 'holo_power'){
    items.push({text:'→ Archive', action:()=> sendAction({type:'move', from_zone:'holo_power', to_zone:'archive', card_number:card.card_number})});
  }

  /* Oshi skill actions */
  if(zname === 'oshi'){
    const allowed = lastState ? (lastState.allowed_actions || []) : [];
    const oshiState = lastState ? (lastState.oshi_skill_state || {}) : {};
    const hpCount = lastState ? (lastState.players[playerId]?.zones?.holo_power || []).length : 0;

    if(allowed.includes('use_oshi_skill')){
      items.push({text:'⚡ Use Oshi Skill', action:()=> showOshiSkillActivation('oshi_skill')});
    }
    if(allowed.includes('use_sp_oshi_skill')){
      items.push({text:'🌟 Use SP Oshi Skill', action:()=> showOshiSkillActivation('sp_oshi_skill')});
    }
    if(oshiState.oshi_skill_used_this_turn){
      items.push({text:'Oshi Skill (used this turn)', disabled:true});
    }
    if(oshiState.sp_oshi_skill_used){
      items.push({text:'SP Skill (used this game)', disabled:true});
    }
    items.push({text:`Holo Power: ${hpCount}`, disabled:true});
  }

  if(isStage || zname === 'oshi'){
    items.push({type:'sep'});
    items.push({text:'View Stack / Yells', action:()=> showStackPopup(zname, idx, card)});
  }

  items.push({text:'View Card', action:()=> showZoom(cardImgSrc(card))});

  showContextMenuAt(x, y, items);
}

/* ════════════════════ BLOOM PICKER ════════════════════ */
function showBloomPicker(zname, idx, targetCard){
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const hand = myData.zones.hand || [];

  /* Bloom level validation */
  const BLOOM_VALID = {'Debut':['1st'], '1st':['1st','2nd'], '2nd':['2nd']};
  const allowed = BLOOM_VALID[targetCard.bloom_level] || [];
  if(!allowed.length){
    alert(`${targetCard.card_name} (${targetCard.bloom_level}) cannot be bloomed further.`);
    return;
  }

  const eligible = hand.filter(c =>
    c.card_type && c.card_type.includes('ホロメン') && allowed.includes(c.bloom_level)
  );
  if(!eligible.length){
    alert(`No eligible cards in hand to bloom ${targetCard.card_name}`);
    return;
  }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = `Bloom ${targetCard.card_name} (${targetCard.bloom_level})`;
  overlay.appendChild(h);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';

  eligible.forEach(card => {
    const mc = document.createElement('div');
    mc.className = 'modal-card';
    const img = document.createElement('img');
    img.src = cardImgSrc(card);
    mc.appendChild(img);
    const name = document.createElement('div');
    name.className = 'mc-name';
    name.textContent = `${card.card_name} (${card.bloom_level})`;
    mc.appendChild(name);
    mc.addEventListener('click', ()=>{
      overlay.remove();
      sendAction({type:'bloom', zone:zname, card_index:idx, hand_card_number:card.card_number});
    });
    grid.appendChild(mc);
  });

  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Cancel';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  modalContainer.appendChild(overlay);
}

/* ════════════════════ ARTS PICKER ════════════════════ */

/* Check if attached yells satisfy an art's color requirements.
   Returns true if the yells can cover all required colors.
   無 (colorless) = any yell card satisfies that slot. */
function canPayYells(artReq, attachedYells){
  const required = artReq || [];
  if(!required.length) return true;
  const used = new Array(attachedYells.length).fill(false);
  for(const reqColor of required){
    let matched = false;
    for(let i = 0; i < attachedYells.length; i++){
      if(used[i]) continue;
      const yellColors = Array.isArray(attachedYells[i].color) ? attachedYells[i].color : [];
      if(reqColor === '無' || yellColors.includes(reqColor)){
        used[i] = true;
        matched = true;
        break;
      }
    }
    if(!matched) return false;
  }
  return true;
}

/* Build yell requirement dots for an art */
function renderArtYellReq(reqColors){
  const span = document.createElement('span');
  span.className = 'art-yell-req';
  for(const c of (reqColors||[])){
    const dot = document.createElement('span');
    dot.className = 'yell-dot';
    if(c === '無'){
      dot.style.background = '#999';
      dot.style.border = '1px dashed #666';
    } else {
      dot.style.background = YELL_COLORS[c] || '#e0c020';
    }
    span.appendChild(dot);
  }
  return span;
}

function showArtsPicker(zname, idx, card){
  const artsList = card.arts || [];
  if(!artsList.length){
    alert(`${card.card_name} has no arts.`);
    return;
  }

  if(card.resting){
    alert(`${card.card_name} is resting and cannot use arts.`);
    return;
  }

  const yells = card.attached_yells || [];

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = `Arts — ${card.card_name}`;
  h.style.marginBottom = '4px';
  overlay.appendChild(h);

  /* Show HP and damage info, including arts modifier */
  const hpInfo = document.createElement('div');
  hpInfo.style.cssText = 'color:#aaa;font-size:13px;margin-bottom:12px;text-align:center;';
  let hpText = `HP: ${card.hp || '?'}  |  Damage: ${card.damage || 0}  |  Yells: ${yells.length}`;
  const mod = card.arts_modifier || 0;
  if(mod > 0) hpText += `  |  🔧 Arts +${mod}`;
  hpInfo.textContent = hpText;
  overlay.appendChild(hpInfo);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';
  grid.style.flexDirection = 'column';
  grid.style.alignItems = 'center';
  grid.style.gap = '8px';

  artsList.forEach((art, artIdx) => {
    const canUse = canPayYells(art['エール'], yells);
    const row = document.createElement('div');
    row.className = 'arts-row' + (canUse ? ' arts-usable' : ' arts-disabled');
    row.style.cssText = `display:flex;align-items:center;gap:10px;padding:10px 16px;
      border-radius:8px;cursor:${canUse?'pointer':'not-allowed'};width:90%;max-width:420px;
      background:${canUse?'rgba(50,180,80,0.15)':'rgba(80,80,80,0.2)'};
      border:1px solid ${canUse?'#4a4':'#555'};opacity:${canUse?1:0.5};`;

    /* Arts name */
    const nameEl = document.createElement('div');
    nameEl.style.cssText = 'flex:1;font-weight:bold;font-size:14px;color:#eee;';
    nameEl.textContent = art.name || `Art ${artIdx+1}`;
    row.appendChild(nameEl);

    /* Yell requirement dots */
    row.appendChild(renderArtYellReq(art['エール']));

    /* Damage — show base + modifier */
    const dmgEl = document.createElement('div');
    dmgEl.style.cssText = 'font-size:16px;font-weight:bold;color:#f44;min-width:60px;text-align:right;';
    const baseDmg = parseInt(art.damage) || 0;
    const totalMod = card.arts_modifier || 0;
    if(totalMod > 0){
      dmgEl.innerHTML = `${baseDmg} <span style="color:#f9a;font-size:12px">+${totalMod}</span>`;
    } else {
      dmgEl.textContent = art.damage || '0';
    }
    row.appendChild(dmgEl);

    if(canUse){
      row.addEventListener('click', ()=>{
        overlay.remove();
        showArtsTargetPicker(zname, idx, artIdx, art);
      });
    }

    grid.appendChild(row);
  });

  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Cancel';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  modalContainer.appendChild(overlay);
}

/* ── Target picker: choose opponent holomen to hit ── */
function showArtsTargetPicker(atkZone, atkIdx, artsIdx, art){
  if(!lastState) return;
  const oppId = Object.keys(lastState.players).find(k=>k!==playerId);
  if(!oppId){
    alert('No opponent found.');
    return;
  }
  const oppData = lastState.players[oppId];
  if(!oppData || !oppData.zones) return;

  /* Gather opponent stage holomen */
  const targets = [];
  ['centre','collabo','back'].forEach(zname => {
    const cards = oppData.zones[zname];
    if(!Array.isArray(cards)) return;
    cards.forEach((c, idx) => targets.push({zone:zname, idx, card:c}));
  });

  if(!targets.length){
    alert('Opponent has no holomen on stage.');
    return;
  }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = `${art.name || 'Arts'} (${art.damage} dmg) — Select target`;
  overlay.appendChild(h);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';

  targets.forEach(({zone, idx, card}) => {
    const mc = document.createElement('div');
    mc.className = 'modal-card';
    const img = document.createElement('img');
    img.src = cardImgSrc(card);
    mc.appendChild(img);
    const name = document.createElement('div');
    name.className = 'mc-name';
    const hp = card.hp || '?';
    const dmg = card.damage || 0;
    name.textContent = `${card.card_name} [${zone}] HP:${hp} Dmg:${dmg}`;
    mc.appendChild(name);
    mc.addEventListener('click', ()=>{
      overlay.remove();
      sendAction({
        type:'play_arts',
        zone: atkZone,
        card_index: atkIdx,
        arts_index: artsIdx,
        target_player_id: oppId,
        target_zone: zone,
        target_card_index: idx,
      });
    });
    grid.appendChild(mc);
  });

  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Cancel';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  modalContainer.appendChild(overlay);
}

/* ════════════════════ STACK/YELL POPUP ════════════════════ */
function showStackPopup(zname, idx, card){
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = `${card.card_name} – Stack & Yells`;
  overlay.appendChild(h);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';

  /* Active card */
  const activeLabel = document.createElement('h3');
  activeLabel.textContent = 'Active Card';
  activeLabel.style.width = '100%';
  activeLabel.style.textAlign = 'center';
  activeLabel.style.color = '#8f8';
  grid.appendChild(activeLabel);

  const mainCard = document.createElement('div');
  mainCard.className = 'modal-card';
  const mainImg = document.createElement('img');
  mainImg.src = cardImgSrc(card);
  mainCard.appendChild(mainImg);
  const mainName = document.createElement('div');
  mainName.className = 'mc-name';
  mainName.textContent = `${card.card_name} (${card.bloom_level||card.card_type})`;
  mainCard.appendChild(mainName);
  mainCard.addEventListener('click', ()=> showZoom(cardImgSrc(card)));
  grid.appendChild(mainCard);

  /* Bloom stack */
  const stacked = Array.isArray(card.stacked_cards) ? card.stacked_cards : [];
  if(stacked.length){
    const stackLabel = document.createElement('h3');
    stackLabel.textContent = `Bloom Stack (${stacked.length})`;
    stackLabel.style.width = '100%';
    stackLabel.style.textAlign = 'center';
    stackLabel.style.color = '#7af';
    grid.appendChild(stackLabel);
    stacked.forEach(sc => {
      const mc = document.createElement('div');
      mc.className = 'modal-card';
      const img = document.createElement('img');
      img.src = cardImgSrc(sc);
      mc.appendChild(img);
      const n = document.createElement('div');
      n.className = 'mc-name';
      n.textContent = `${sc.card_name} (${sc.bloom_level||''})`;
      mc.appendChild(n);
      mc.addEventListener('click', ()=> showZoom(cardImgSrc(sc)));
      grid.appendChild(mc);
    });
  }

  /* Attached yells */
  const yells = Array.isArray(card.attached_yells) ? card.attached_yells : [];
  if(yells.length){
    const yellLabel = document.createElement('h3');
    yellLabel.textContent = `Attached Yells (${yells.length})`;
    yellLabel.style.width = '100%';
    yellLabel.style.textAlign = 'center';
    yellLabel.style.color = '#ffa';
    grid.appendChild(yellLabel);
    yells.forEach(yc => {
      const mc = document.createElement('div');
      mc.className = 'modal-card';
      const img = document.createElement('img');
      img.src = cardImgSrc(yc);
      mc.appendChild(img);
      const n = document.createElement('div');
      n.className = 'mc-name';
      n.textContent = `${yc.card_name}`;
      mc.appendChild(n);
      mc.addEventListener('click', ()=> showZoom(cardImgSrc(yc)));
      grid.appendChild(mc);
    });
  }

  if(!stacked.length && !yells.length){
    const empty = document.createElement('div');
    empty.style.cssText = 'color:#888;padding:20px;font-size:14px';
    empty.textContent = 'No bloom stack or attached yells';
    grid.appendChild(empty);
  }

  /* Attached support cards (tool/mascot/fan) */
  const supps = Array.isArray(card.attached_supports) ? card.attached_supports : [];
  if(supps.length){
    const suppLabel = document.createElement('h3');
    suppLabel.textContent = `Attached Supports (${supps.length})`;
    suppLabel.style.width = '100%';
    suppLabel.style.textAlign = 'center';
    suppLabel.style.color = '#f9a';
    grid.appendChild(suppLabel);
    supps.forEach(sc => {
      const mc = document.createElement('div');
      mc.className = 'modal-card';
      const img = document.createElement('img');
      img.src = cardImgSrc(sc);
      mc.appendChild(img);
      const n = document.createElement('div');
      n.className = 'mc-name';
      n.textContent = `${sc.card_name || sc.card_number}`;
      mc.appendChild(n);
      mc.addEventListener('click', ()=> showZoom(cardImgSrc(sc)));
      grid.appendChild(mc);
    });
  }

  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Close';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  modalContainer.appendChild(overlay);
}

/* ════════════════════ SEARCH DECK / ARCHIVE ════════════════════ */
function openSearchModal(zoneKey, title, actions){
  /* Request full card list from server */
  sendAction({type:'get_zone_cards', zone:zoneKey});

  /* Listen for the response - we'll use a one-time wrapper */
  const origHandler = ws.onmessage;
  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if(msg.type === 'state_update'){
      /* Also update state */
      lastState = msg.state;
      if(lastState && lastState.started) renderGame(lastState);
    }
    /* Check if the state contains the zone cards we need */
    /* Since get_zone_cards might not broadcast, use the owner's zones */
    ws.onmessage = origHandler;
    origHandler(ev);

    /* Build modal from current state */
    if(!lastState) return;
    const myData = lastState.players[playerId];
    const cards = myData.zones[zoneKey] || [];
    buildSearchModalUI(title, zoneKey, cards, actions);
  };
}

function buildSearchModalUI(title, zoneKey, cards, actions){
  if(!cards.length){
    alert(`${title}: empty`);
    return;
  }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = `${title} (${cards.length} cards)`;
  overlay.appendChild(h);

  const filter = document.createElement('input');
  filter.className = 'modal-filter';
  filter.placeholder = 'Filter by name/number...';
  overlay.appendChild(filter);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';

  function populate(ft){
    grid.innerHTML = '';
    const filtered = ft ? cards.filter(c =>
      `${c.card_number} ${c.card_name} ${c.card_type}`.toLowerCase().includes(ft.toLowerCase())
    ) : cards;

    /* Show cards in reverse (top of deck first) if deck */
    const ordered = zoneKey === 'deck' ? [...filtered].reverse() : filtered;

    ordered.forEach((card, displayIdx) => {
      /* Find actual index in the zone */
      const actualIdx = cards.indexOf(card);
      const mc = document.createElement('div');
      mc.className = 'modal-card';
      const img = document.createElement('img');
      img.src = cardImgSrc({...card, face_up:true});
      mc.appendChild(img);
      const name = document.createElement('div');
      name.className = 'mc-name';
      name.textContent = card.card_name;
      mc.appendChild(name);

      const btns = document.createElement('div');
      btns.className = 'mc-actions';
      actions.forEach(a => {
        const btn = document.createElement('button');
        btn.textContent = a.label;
        btn.addEventListener('click', ev => {
          ev.stopPropagation();
          a.action(card, actualIdx);
          overlay.remove();
        });
        btns.appendChild(btn);
      });
      mc.appendChild(btns);
      grid.appendChild(mc);
    });
  }

  populate('');
  filter.addEventListener('input', ()=> populate(filter.value));

  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Close';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  overlay.addEventListener('click', ev=>{
    if(ev.target === overlay) overlay.remove();
  });
  modalContainer.appendChild(overlay);
}

/* ════════════════════ SUPPORT CARD SYSTEM ════════════════════ */

/**
 * Play a support card from hand. Sends action and handles response:
 * - If server returns pending_picks → shows the first picker modal
 * - Otherwise → shows a brief toast with the result
 */
function playSupportCard(cardNumber){
  /* Send play_support and intercept the action_result */
  sendAction({type:'play_support', card_number: cardNumber});

  const handler = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch{ return; }
    if(data.type !== 'action_result') return;
    ws.removeEventListener('message', handler);
    const res = data.result;
    if(!res || !res.success){
      showSupportToast(`❌ ${res?.reason || 'Failed'}`, '#c33');
      return;
    }
    /* Success toast with actions taken */
    const acts = res.actions_taken || [];
    const cardName = res.card_name || cardNumber;
    if(acts.length){
      showSupportToast(`⚡ ${cardName}: ${acts.join(', ')}`, '#2a6');
    } else {
      showSupportToast(`⚡ ${cardName} played`, '#2a6');
    }
    /* If there were turn modifiers, show those too */
    if(res.turn_modifiers && res.turn_modifiers.length){
      const mods = res.turn_modifiers.map(m =>
        `${m.target}: ${m.amount >= 0 ? '+' : ''}${m.amount} (${m.type})`
      ).join(', ');
      showSupportToast(`📊 ${mods}`, '#26a', 4000);
    }
    /* pending_picks are handled via state_update → checkPendingSupportPicks() */
  };
  ws.addEventListener('message', handler);
}

/** Brief toast notification for support card results */
function showSupportToast(text, color, duration){
  duration = duration || 3000;
  const toast = document.createElement('div');
  toast.style.cssText = `position:fixed;top:60px;left:50%;transform:translateX(-50%);
    background:${color || '#333'};color:#fff;padding:8px 20px;border-radius:8px;
    font-size:13px;font-weight:600;z-index:700;pointer-events:none;
    opacity:1;transition:opacity 0.5s`;
  toast.textContent = text;
  document.body.appendChild(toast);
  setTimeout(()=>{ toast.style.opacity='0'; }, duration - 500);
  setTimeout(()=>{ toast.remove(); }, duration);
}

/* ═══════════════════ OSHI SKILL ACTIVATION ═══════════════════ */

/**
 * Show oshi skill activation overlay.
 * Fetches skill info from server, displays cost & effect, then confirms.
 * For X-cost skills, shows a slider/input to choose how many holo power to pay.
 * @param {string} skillType - 'oshi_skill' or 'sp_oshi_skill'
 */
function showOshiSkillActivation(skillType){
  /* First, request skill info from server */
  sendAction({type:'get_oshi_skill_info'});

  const handler = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch{ return; }
    if(data.type !== 'action_result') return;
    ws.removeEventListener('message', handler);
    const res = data.result;
    if(!res || !res.success){
      showSupportToast(`❌ ${res?.reason || 'Failed to get skill info'}`, '#c33');
      return;
    }

    const skill = skillType === 'sp_oshi_skill' ? res.sp_oshi_skill : res.oshi_skill;
    if(!skill){
      showSupportToast('❌ Skill not found', '#c33');
      return;
    }
    if(!skill.available){
      showSupportToast(`❌ ${skill.name}: ${skill.reason}`, '#c33');
      return;
    }

    _showOshiSkillModal(skillType, skill, res.holo_power_count);
  };
  ws.addEventListener('message', handler);
}

/**
 * Display the oshi skill confirmation modal.
 * For X-cost, includes a number input. For fixed cost, just confirm/cancel.
 */
function _showOshiSkillModal(skillType, skill, hpCount){
  const isX = (String(skill.cost) === 'X');
  const isSP = skillType === 'sp_oshi_skill';
  const actionType = isSP ? 'use_sp_oshi_skill' : 'use_oshi_skill';

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.style.zIndex = '800';

  /* Title */
  const title = document.createElement('h3');
  title.style.cssText = 'margin:0 0 8px; color:#fff;';
  title.textContent = isSP ? `🌟 SP Oshi Skill: ${skill.name}` : `⚡ Oshi Skill: ${skill.name}`;
  overlay.appendChild(title);

  /* Effect text */
  const effectEl = document.createElement('p');
  effectEl.style.cssText = 'margin:0 0 12px; color:#ccc; font-size:13px; max-width:400px; line-height:1.5;';
  effectEl.textContent = skill.effect;
  overlay.appendChild(effectEl);

  /* Cost info */
  const costInfo = document.createElement('div');
  costInfo.style.cssText = 'margin:0 0 12px; color:#ffd700; font-size:14px; font-weight:600;';
  if(isX){
    costInfo.textContent = `Holo Power Cost: X (you choose) — Available: ${hpCount}`;
  } else {
    costInfo.textContent = `Holo Power Cost: ${skill.cost} — Available: ${hpCount}`;
  }
  overlay.appendChild(costInfo);

  /* Timing badge */
  const timingEl = document.createElement('div');
  timingEl.style.cssText = 'margin:0 0 16px; font-size:12px;';
  if(isSP){
    timingEl.innerHTML = '<span style="background:#8b1313;color:#fff;padding:2px 8px;border-radius:4px;">Once per Game</span>';
    if(skill.used_this_game){
      timingEl.innerHTML += ' <span style="color:#f66;">— Already Used!</span>';
    }
  } else {
    timingEl.innerHTML = '<span style="background:#1a4a6a;color:#fff;padding:2px 8px;border-radius:4px;">Once per Turn</span>';
    if(skill.used_this_turn){
      timingEl.innerHTML += ' <span style="color:#f66;">— Already Used!</span>';
    }
  }
  overlay.appendChild(timingEl);

  /* X-cost input */
  let xInput = null;
  if(isX){
    const inputWrap = document.createElement('div');
    inputWrap.style.cssText = 'margin:0 0 16px; display:flex; align-items:center; gap:8px;';

    const label = document.createElement('label');
    label.style.cssText = 'color:#fff; font-size:13px;';
    label.textContent = 'Holo Power to pay (X):';
    inputWrap.appendChild(label);

    xInput = document.createElement('input');
    xInput.type = 'number';
    xInput.min = '0';
    xInput.max = String(hpCount);
    xInput.value = '0';
    xInput.style.cssText = 'width:60px; padding:4px 8px; border-radius:4px; border:1px solid #555; background:#222; color:#fff; font-size:14px; text-align:center;';
    inputWrap.appendChild(xInput);

    const maxLabel = document.createElement('span');
    maxLabel.style.cssText = 'color:#888; font-size:12px;';
    maxLabel.textContent = `(max: ${hpCount})`;
    inputWrap.appendChild(maxLabel);

    overlay.appendChild(inputWrap);
  }

  /* Buttons */
  const btnWrap = document.createElement('div');
  btnWrap.style.cssText = 'display:flex; gap:12px; justify-content:center;';

  const confirmBtn = document.createElement('button');
  confirmBtn.style.cssText = 'padding:8px 24px; border:none; border-radius:6px; font-size:14px; font-weight:600; cursor:pointer; ' +
    (isSP ? 'background:#c8a000; color:#000;' : 'background:#2a8; color:#fff;');
  confirmBtn.textContent = isSP ? '🌟 Activate SP Skill' : '⚡ Activate Skill';
  confirmBtn.onclick = () => {
    const action = {type: actionType};
    if(isX && xInput){
      action.x_cost = parseInt(xInput.value) || 0;
    }
    overlay.remove();
    sendAction(action);

    /* Listen for result */
    const resHandler = (ev2) => {
      let d2;
      try { d2 = JSON.parse(ev2.data); } catch{ return; }
      if(d2.type !== 'action_result') return;
      ws.removeEventListener('message', resHandler);
      const r = d2.result;
      if(!r || !r.success){
        showSupportToast(`❌ ${r?.reason || 'Failed'}`, '#c33');
        return;
      }
      const paid = r.cost_paid || 0;
      const remaining = r.holo_power_remaining != null ? r.holo_power_remaining : '?';
      showSupportToast(
        `${isSP ? '🌟' : '⚡'} ${r.skill_name} activated! (Cost: ${paid} HP, Remaining: ${remaining})`,
        isSP ? '#8b6914' : '#2a6', 4000
      );
    };
    ws.addEventListener('message', resHandler);
  };
  btnWrap.appendChild(confirmBtn);

  const cancelBtn = document.createElement('button');
  cancelBtn.style.cssText = 'padding:8px 24px; border:1px solid #555; border-radius:6px; background:#333; color:#ccc; font-size:14px; cursor:pointer;';
  cancelBtn.textContent = 'Cancel';
  cancelBtn.onclick = () => overlay.remove();
  btnWrap.appendChild(cancelBtn);

  overlay.appendChild(btnWrap);

  /* Close on backdrop click */
  overlay.addEventListener('click', ev => {
    if(ev.target === overlay) overlay.remove();
  });

  document.body.appendChild(overlay);
}

/**
 * Check state for pending support picks and auto-show the picker modal.
 * Called after every state update during 'playing' phase.
 */
let _supportPickerShown = null;  // track which pick_id is currently shown

function checkPendingSupportPicks(state){
  const ss = state.step_state || {};
  const pending = ss.pending_support;

  if(!pending || !pending.picks || !pending.picks.length){
    _supportPickerShown = null;
    return;
  }

  /* Show the first unresolved pick */
  const firstPick = pending.picks[0];
  if(_supportPickerShown === firstPick.pick_id) return;  // already showing
  _supportPickerShown = firstPick.pick_id;

  showSupportPickerModal(pending.card_name, firstPick);
}

/**
 * Modal for resolving a pending support pick.
 * Supports pick_type: "cards" (with optional selectable_numbers),
 * "reorder" (drag-reorder), "select_cheer", "holomen", "attach_support".
 */
function showSupportPickerModal(cardName, pick){
  /* Remove any existing support picker */
  document.querySelectorAll('.support-picker-overlay').forEach(e => e.remove());

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay support-picker-overlay';

  /* Header */
  const h = document.createElement('h3');
  h.textContent = `⚡ ${cardName}`;
  h.style.color = '#7af';
  overlay.appendChild(h);

  const sub = document.createElement('div');
  sub.style.cssText = 'font-size:13px;color:#ccc;margin-bottom:4px;text-align:center';
  sub.textContent = pick.title || '';
  overlay.appendChild(sub);

  if(pick.message){
    const msg = document.createElement('div');
    msg.style.cssText = 'font-size:12px;color:#999;margin-bottom:8px;text-align:center';
    msg.textContent = pick.message;
    overlay.appendChild(msg);
  }

  const pickType = pick.pick_type || 'cards';
  const maxPick = (pick.max_pick != null) ? pick.max_pick : 1;
  const minPick = pick.min_pick || 0;
  const selectableSet = pick.selectable_numbers ? new Set(pick.selectable_numbers) : null;

  // ─── REORDER MODE ───────────────────────────────────────────
  if(pickType === 'reorder'){
    const info = document.createElement('div');
    info.style.cssText = 'font-size:12px;color:#adf;margin-bottom:8px;text-align:center';
    info.textContent = 'Drag cards to set the order (top → bottom). First card = top.';
    overlay.appendChild(info);

    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:4px;max-height:60vh;overflow-y:auto;padding:4px';
    const orderedNumbers = [];

    (pick.cards || []).forEach((card, i) => {
      orderedNumbers.push(card.card_number);
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:6px 10px;background:#1a1a2e;border:1px solid #333;border-radius:6px;cursor:grab;user-select:none';
      row.draggable = true;
      row.dataset.idx = i;

      const num = document.createElement('span');
      num.style.cssText = 'color:#888;font-size:11px;min-width:20px';
      num.textContent = `${i+1}.`;
      num.className = 'reorder-num';
      row.appendChild(num);

      const img = document.createElement('img');
      img.src = cardImgSrc(card);
      img.style.cssText = 'height:48px;border-radius:3px';
      row.appendChild(img);

      const name = document.createElement('span');
      name.style.cssText = 'color:#eee;font-size:13px;flex:1';
      name.textContent = card.card_name || card.card_number;
      row.appendChild(name);

      // Drag handlers
      row.addEventListener('dragstart', e => {
        e.dataTransfer.effectAllowed = 'move';
        row.style.opacity = '0.5';
        row._dragIdx = Array.from(list.children).indexOf(row);
      });
      row.addEventListener('dragend', () => { row.style.opacity = '1'; });
      row.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; });
      row.addEventListener('drop', e => {
        e.preventDefault();
        const from = row._dragIdx !== undefined ? row._dragIdx : 0;
        // Find which row is being dragged
        const dragged = list.querySelector('[style*="opacity: 0.5"]') || list.querySelector('[style*="opacity:0.5"]');
        if(dragged && dragged !== row){
          const rect = row.getBoundingClientRect();
          const mid = rect.top + rect.height / 2;
          if(e.clientY < mid){
            list.insertBefore(dragged, row);
          } else {
            list.insertBefore(dragged, row.nextSibling);
          }
          // Update numbers
          Array.from(list.children).forEach((r, i) => {
            const n = r.querySelector('.reorder-num');
            if(n) n.textContent = `${i+1}.`;
          });
        }
      });

      // Right-click zoom
      row.addEventListener('contextmenu', ev => {
        ev.preventDefault();
        showZoom(cardImgSrc(card));
      });

      list.appendChild(row);
    });

    overlay.appendChild(list);

    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:10px;margin-top:12px';
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'modal-close';
    confirmBtn.style.background = '#2d5bff';
    confirmBtn.textContent = 'Confirm Order';
    confirmBtn.addEventListener('click', ()=>{
      // Read order from DOM
      const finalOrder = [];
      Array.from(list.children).forEach(row => {
        const img = row.querySelector('img');
        if(img){
          const cn = (pick.cards || []).find(c => cardImgSrc(c) === img.src);
          if(cn) finalOrder.push(cn.card_number);
        }
      });
      // Fallback: use original order if DOM parse fails
      const toSend = finalOrder.length ? finalOrder : orderedNumbers;
      overlay.remove();
      _supportPickerShown = null;
      sendAction({ type: 'pick_support_cards', pick_id: pick.pick_id, card_numbers: toSend });
    });
    btnRow.appendChild(confirmBtn);
    overlay.appendChild(btnRow);
    modalContainer.appendChild(overlay);
    return;
  }

  // ─── STANDARD SELECTION MODE (cards, select_cheer, holomen, attach_support) ──

  /* Selection counter */
  const counter = document.createElement('div');
  counter.style.cssText = 'font-size:12px;color:#aaa;margin-bottom:8px;text-align:center';
  overlay.appendChild(counter);

  const selected = new Set();  // Set of indices (from forEach) to support duplicate card_numbers

  function updateCounter(){
    const label = pickType === 'select_cheer' ? 'Yells' :
                  pickType === 'holomen' || pickType === 'attach_support' ? 'Holomen' : 'Cards';
    counter.textContent = `Selected ${label}: ${selected.size} / ${maxPick}${minPick > 0 ? ` (min ${minPick})` : ''}`;
    confirmBtn.disabled = selected.size < minPick;
  }

  /* Card grid */
  const grid = document.createElement('div');
  grid.className = 'modal-grid';

  (pick.cards || []).forEach((card, cardIdx) => {
    const cn = card.card_number;
    const isSelectable = !selectableSet || selectableSet.has(cn);

    const mc = document.createElement('div');
    mc.className = 'modal-card';
    mc.style.transition = 'border-color 0.15s, box-shadow 0.15s';

    // Dim non-selectable cards
    if(!isSelectable){
      mc.style.opacity = '0.4';
      mc.style.pointerEvents = 'none';
    }

    const img = document.createElement('img');
    img.src = cardImgSrc(card);
    img.style.cursor = isSelectable ? 'pointer' : 'default';
    mc.appendChild(img);

    const name = document.createElement('div');
    name.className = 'mc-name';
    let label = card.card_name || card.card_number;
    // For select_cheer, show which color
    if(pickType === 'select_cheer' && card.color){
      label += ` [${Array.isArray(card.color) ? card.color.join('/') : card.color}]`;
    }
    // For holomen, show hp
    if((pickType === 'holomen' || pickType === 'attach_support') && card.hp){
      label += ` (HP:${card.hp})`;
    }
    name.textContent = label;
    mc.appendChild(name);

    // Show selectable marker
    if(selectableSet && isSelectable){
      const marker = document.createElement('div');
      marker.style.cssText = 'position:absolute;top:2px;right:2px;background:#5f5;color:#000;font-size:9px;padding:1px 4px;border-radius:3px;font-weight:bold';
      marker.textContent = '✓ match';
      mc.style.position = 'relative';
      mc.appendChild(marker);
    }

    if(isSelectable){
      mc.addEventListener('click', ()=>{
        if(selected.has(cardIdx)){
          selected.delete(cardIdx);
          mc.style.borderColor = '#333';
          mc.style.boxShadow = 'none';
        } else {
          if(selected.size >= maxPick){
            if(maxPick === 1){
              selected.clear();
              grid.querySelectorAll('.modal-card').forEach(c => {
                c.style.borderColor = '#333';
                c.style.boxShadow = 'none';
              });
            } else {
              return;
            }
          }
          selected.add(cardIdx);
          mc.style.borderColor = '#5f5';
          mc.style.boxShadow = '0 0 8px rgba(80,255,80,0.4)';
        }
        updateCounter();
      });
    }

    mc.addEventListener('contextmenu', ev=>{
      ev.preventDefault();
      showZoom(cardImgSrc(card));
    });

    grid.appendChild(mc);
  });

  overlay.appendChild(grid);

  /* Buttons */
  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex;gap:10px;margin-top:12px';

  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'modal-close';
  confirmBtn.style.background = '#2d5bff';
  confirmBtn.textContent = pickType === 'attach_support' ? 'Attach' :
                            pickType === 'select_cheer' ? 'Archive Yell(s)' :
                            `Confirm (${maxPick})`;
  confirmBtn.disabled = minPick > 0;
  confirmBtn.addEventListener('click', ()=>{
    overlay.remove();
    _supportPickerShown = null;
    sendAction({
      type: 'pick_support_cards',
      pick_id: pick.pick_id,
      card_numbers: Array.from(selected).map(i => pick.cards[i].card_number),
    });
  });
  btnRow.appendChild(confirmBtn);

  if(minPick === 0){
    const skipBtn = document.createElement('button');
    skipBtn.className = 'modal-close';
    skipBtn.textContent = 'Skip';
    skipBtn.addEventListener('click', ()=>{
      overlay.remove();
      _supportPickerShown = null;
      sendAction({
        type: 'pick_support_cards',
        pick_id: pick.pick_id,
        card_numbers: [],
      });
    });
    btnRow.appendChild(skipBtn);
  }

  overlay.appendChild(btnRow);
  updateCounter();
  modalContainer.appendChild(overlay);
}

/* ════════════════════ DEDUCT LIFE PICKER ════════════════════ */
function showDeductLifePicker(){
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const lifeCount = Array.isArray(myData.zones.life) ? myData.zones.life.length :
                    (myData.zones.life?.count || 0);
  if(!lifeCount){
    alert('No life cards remaining!');
    return;
  }

  /* Collect stage holomen */
  const holomen = [];
  ['centre','back','collabo'].forEach(zname => {
    const cards = myData.zones[zname];
    if(!Array.isArray(cards)) return;
    cards.forEach((c, idx) => holomen.push({zone:zname, idx, card:c}));
  });

  if(!holomen.length){
    alert('No holomen on stage to attach life card to.');
    return;
  }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = 'Deduct Life — Select holomen to attach';
  overlay.appendChild(h);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';

  holomen.forEach(({zone, idx, card}) => {
    const mc = document.createElement('div');
    mc.className = 'modal-card';
    const img = document.createElement('img');
    img.src = cardImgSrc(card);
    mc.appendChild(img);
    const name = document.createElement('div');
    name.className = 'mc-name';
    name.textContent = `${card.card_name} [${zone}]`;
    mc.appendChild(name);
    mc.addEventListener('click', ()=>{
      overlay.remove();
      sendAction({type:'deduct_life', zone:zone, card_index:idx});
    });
    grid.appendChild(mc);
  });

  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Cancel';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  modalContainer.appendChild(overlay);
}

/* ════════════════════ ZOOM ════════════════════ */
function showZoom(src){
  const m = document.createElement('div');
  m.className = 'zoom-modal';
  const big = document.createElement('img');
  big.src = src;
  m.appendChild(big);
  m.addEventListener('click', ()=>m.remove());
  document.getElementById('zoom_container').appendChild(m);
}

/* ════════════════════ ACTION BUTTONS ════════════════════ */
document.getElementById('draw').onclick       = ()=> sendAction({type:'draw', count:1});
document.getElementById('shuffle').onclick    = ()=> sendAction({type:'shuffle_deck'});
document.getElementById('shuffle_yell').onclick = ()=> sendAction({type:'shuffle_yell'});
document.getElementById('skip_cheer').onclick = ()=> sendAction({type:'skip_cheer'});
document.getElementById('end_main').onclick   = ()=> sendAction({type:'end_main'});
document.getElementById('end_performance').onclick = ()=> sendAction({type:'end_performance'});
document.getElementById('end_turn').onclick   = ()=> sendAction({type:'end_turn'});
document.getElementById('hand_to_deck').onclick = ()=> sendAction({type:'hand_to_deck'});

document.getElementById('deduct_life_btn').onclick = ()=> showDeductLifePicker();

document.getElementById('search_deck_btn').onclick = ()=> {
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const cards = myData.zones.deck || [];
  buildSearchModalUI('Search Deck', 'deck', cards, [
    {label:'Hand', action:(card)=> sendAction({type:'move', from_zone:'deck', to_zone:'hand', card_number:card.card_number})},
    {label:'Archive', action:(card)=> sendAction({type:'move', from_zone:'deck', to_zone:'archive', card_number:card.card_number})},
  ]);
};

document.getElementById('search_archive_btn').onclick = ()=> {
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const cards = myData.zones.archive || [];
  buildSearchModalUI('Search Archive', 'archive', cards, [
    {label:'Top', action:(card)=> sendAction({type:'move', from_zone:'archive', to_zone:'deck', card_number:card.card_number})},
    {label:'Hand', action:(card)=> sendAction({type:'move', from_zone:'archive', to_zone:'hand', card_number:card.card_number})},
    {label:'Y↑', action:(card)=> sendAction({type:'move', from_zone:'archive', to_zone:'yell_deck', card_number:card.card_number})},
  ]);
};

/* ── Peek Top N ── */
function openPeekModal(count){
  sendAction({type:'peek_deck', count});
  /* After sending, wait for action_result to come back with cards */
  const handler = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch{ return; }
    if(data.type !== 'action_result') return;
    ws.removeEventListener('message', handler);
    const res = data.result;
    if(!res.success){
      alert(res.reason || 'Peek failed');
      return;
    }
    showPeekModal(count, res.cards);
  };
  ws.addEventListener('message', handler);
}

function showPeekModal(count, cards){
  if(!cards || !cards.length){
    alert('No cards to show');
    return;
  }

  /* Mutable ordered list of peeked cards; user can drag to reorder */
  let orderedCards = cards.slice();

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';

  function rebuildGrid(){
    /* Clear overlay children */
    overlay.innerHTML = '';

    const h = document.createElement('h3');
    h.textContent = `Top ${count} Cards — drag to reorder (left = top of deck)`;
    overlay.appendChild(h);

    const grid = document.createElement('div');
    grid.className = 'modal-grid';

    orderedCards.forEach((card, displayIdx) => {
      const mc = document.createElement('div');
      mc.className = 'modal-card';
      mc.draggable = true;
      mc.dataset.idx = displayIdx;

      /* Drag handle */
      const handle = document.createElement('div');
      handle.className = 'drag-handle';
      handle.textContent = '☰';
      mc.appendChild(handle);

      /* Order label */
      const order = document.createElement('div');
      order.className = 'mc-order';
      order.textContent = `#${displayIdx+1}`;
      mc.appendChild(order);

      const img = document.createElement('img');
      img.src = cardImgSrc({...card, face_up:true});
      mc.appendChild(img);

      const name = document.createElement('div');
      name.className = 'mc-name';
      name.textContent = card.card_name;
      mc.appendChild(name);

      /* Individual card actions */
      const btns = document.createElement('div');
      btns.className = 'mc-actions';
      const deckIdx = card.deck_index;

      const mkBtn = (label, subType) => {
        const btn = document.createElement('button');
        btn.textContent = label;
        btn.addEventListener('click', ev => {
          ev.stopPropagation();
          sendAction({type:'peek_deck', count, sub_action:{type:subType, card_index:deckIdx}});
          /* Remove from ordered list and refresh, or close if last card */
          orderedCards = orderedCards.filter(c => c.deck_index !== deckIdx);
          if(orderedCards.length === 0){ overlay.remove(); return; }
          rebuildGrid();
        });
        return btn;
      };

      btns.appendChild(mkBtn('Hand', 'to_hand'));
      btns.appendChild(mkBtn('Archive', 'to_archive'));
      btns.appendChild(mkBtn('Top', 'to_top'));
      btns.appendChild(mkBtn('Bottom', 'to_bottom'));

      mc.appendChild(btns);

      /* Drag-reorder events */
      mc.addEventListener('dragstart', ev => {
        ev.dataTransfer.effectAllowed = 'move';
        ev.dataTransfer.setData('text/plain', String(displayIdx));
        mc.classList.add('dragging');
      });
      mc.addEventListener('dragend', () => mc.classList.remove('dragging'));
      mc.addEventListener('dragover', ev => { ev.preventDefault(); mc.classList.add('drag-over-card'); });
      mc.addEventListener('dragleave', () => mc.classList.remove('drag-over-card'));
      mc.addEventListener('drop', ev => {
        ev.preventDefault(); ev.stopPropagation();
        mc.classList.remove('drag-over-card');
        const fromIdx = parseInt(ev.dataTransfer.getData('text/plain'));
        const toIdx = displayIdx;
        if(fromIdx === toIdx) return;
        const moved = orderedCards.splice(fromIdx, 1)[0];
        orderedCards.splice(toIdx, 0, moved);
        rebuildGrid();
      });

      grid.appendChild(mc);
    });

    overlay.appendChild(grid);

    /* Bulk action buttons */
    const bulk = document.createElement('div');
    bulk.className = 'modal-bulk';

    const mkBulk = (label, subType) => {
      const btn = document.createElement('button');
      btn.textContent = label;
      btn.addEventListener('click', () => {
        const indices = orderedCards.map(c => c.deck_index);
        sendAction({type:'peek_deck', count, sub_action:{type:subType, card_indices:indices}});
        overlay.remove();
      });
      return btn;
    };

    bulk.appendChild(mkBulk('⬆ All to Top (in order)', 'all_to_top'));
    bulk.appendChild(mkBulk('⬇ All to Bottom (in order)', 'all_to_bottom'));
    bulk.appendChild(mkBulk('🗑 Archive All', 'all_to_archive'));
    overlay.appendChild(bulk);

    const close = document.createElement('button');
    close.className = 'modal-close';
    close.textContent = 'Close';
    close.addEventListener('click', ()=> overlay.remove());
    overlay.appendChild(close);
  }

  rebuildGrid();

  overlay.addEventListener('click', ev=>{
    if(ev.target === overlay) overlay.remove();
  });
  modalContainer.appendChild(overlay);
}

document.getElementById('peek_top3_btn').onclick = ()=> openPeekModal(3);
document.getElementById('peek_top5_btn').onclick = ()=> openPeekModal(5);

/* ── Responsive redraw ── */
window.addEventListener('resize', ()=>{ if(lastState && (lastState.started || lastState.game_state === 'setup' || lastState.game_state === 'mulligan')) renderGame(lastState); });
/* Clear selection on Escape */
document.addEventListener('keydown', ev=>{ if(ev.key==='Escape'){ clearSelection(); hideContextMenu(); }});
