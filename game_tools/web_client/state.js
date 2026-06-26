/* ══════════════════════════════════════════════════════════════
   hOCG Web Client — Shared State & Constants
   ══════════════════════════════════════════════════════════════ */

/* ── Mutable shared state ── */
export let ws = null;
export let playerId = null;
export let matchId  = null;
export let lastState = null;
export let selectedCard = null;   // {card_number, from_zone}

export function setWs(v)          { ws = v; }
export function setPlayerId(v)    { playerId = v; }
export function setMatchId(v)     { matchId = v; }
export function setLastState(v)   { lastState = v; }
export function setSelectedCard(v){ selectedCard = v; }

/* ── DOM references (cached once) ── */
export const statusEl      = document.getElementById('status');
export const phaseBadge    = document.getElementById('phase_badge');
export const lobbyEl       = document.getElementById('lobby');
export const lobbyStatus   = document.getElementById('lobby_status');
export const lobbyPlayers  = document.getElementById('lobby_players');
export const handTray      = document.getElementById('hand_tray');
export const playHint      = document.getElementById('play_hint');
export const ctxMenu       = document.getElementById('context_menu');
export const modalContainer= document.getElementById('modal_container');
export const stepBar       = document.getElementById('step_bar');
export const turnInfo      = document.getElementById('turn_info');
export const stepInfo      = document.getElementById('step_info');
export const pendingBanner = document.getElementById('pending_banner');
export const diceOverlay   = document.getElementById('dice_overlay');
export const orderOverlay  = document.getElementById('order_overlay');
export const gameoverOverlay = document.getElementById('gameover_overlay');

/* ── Zone bbox definitions (original 2040x1280 playmat) ── */
export const ZONE_DEFS = {
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
export const NAT_W = 2040, NAT_H = 1044;

/* Zone categories for rendering */
export const STACK_ZONES  = ['deck', 'yell_deck', 'archive'];
export const HSTACK_ZONES = ['life', 'holo_power'];
export const SINGLE_ZONES = ['centre', 'collabo', 'oshi'];
export const MULTI_ZONES  = ['back'];
export const PLAY_ZONES   = ['centre','collabo','back','oshi','archive','holo_power'];
export const CARD_BACK        = '/assets/card_back.webp';
export const YELL_LIFE_BACK   = '/assets/yell_life_card_back.png';

/* ── Helpers ── */
export function setStatus(t){ statusEl.textContent = t; }

export function sendAction(action){
  if(!ws||ws.readyState!==1) return;
  ws.send(JSON.stringify({type:'action', action}));
}

/* Color mapping for yell cards */
export const YELL_COLORS = {
  '\u767d': '#e8e8e8',
  '\u8d64': '#e03030',
  '\u9752': '#3060e0',
  '\u7dd1': '#30b030',
  '\u9ec4': '#e0c020',
  '\u7d2b': '#9040c0',
};

/* Build a yell badge showing colored dots grouped by color */
export function renderYellBadge(yellArr, parentEl, posAbsolute){
  if(!yellArr || !yellArr.length) return;
  const colorCounts = {};
  for(const y of yellArr){
    const colors = Array.isArray(y.color) ? y.color : (y.color ? [y.color] : ['\u9ec4']);
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

export function cardImgSrc(cd){
  if(cd && cd.face_up && cd.image_file) return `/cards/${cd.image_file}`;
  if(cd && cd.card_type === '\u30a8\u30fc\u30eb') return YELL_LIFE_BACK;
  return CARD_BACK;
}

/* Step label maps */
export const STEP_NAMES = ['reset','draw','cheer','main','performance','end'];
export const STEP_LABELS = {
  reset:'1. Reset', draw:'2. Draw', cheer:'3. Cheer',
  main:'4. Main', performance:'5. Performance', end:'6. End'
};
export const STEP_DESCRIPTIONS = {
  reset: 'Collabo\u2192Back, un-rest holomen, fill centre if empty',
  draw: 'Drawing a card\u2026',
  cheer: 'Click a stage holomen or drag from Yell Deck to attach yell (or skip)',
  main: 'Place / Bloom / Collabo / Support / Baton Touch',
  performance: 'Use arts to attack opponent holomen',
  end: 'End of turn. Fill centre if empty.',
};
