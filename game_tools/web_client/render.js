/* ══════════════════════════════════════════════════════════════
   hOCG Web Client — Rendering Pipeline
   renderGame, updateActionButtons, scaledBBox, renderPlaymat,
   all zone renderers, hand tray, clearSelection
   ══════════════════════════════════════════════════════════════ */
import {
  playerId, lastState, selectedCard, setSelectedCard, setLastState,
  setStatus, sendAction, cardImgSrc, renderYellBadge,
  ZONE_DEFS, NAT_W, NAT_H,
  STACK_ZONES, HSTACK_ZONES, SINGLE_ZONES, MULTI_ZONES, PLAY_ZONES,
  CARD_BACK, YELL_LIFE_BACK,
  phaseBadge, stepBar, turnInfo, stepInfo, pendingBanner,
  handTray, playHint,
  STEP_DESCRIPTIONS,
} from './state.js';
import { showCardContextMenu, showHandContextMenu, showZoneContextMenu, showOppCardContextMenu } from './menus.js';
import { showZoom, checkPendingSupportPicks, showCentreFillPicker, resetCentreFillFlag } from './modals.js';

/* ════════════════════ GAME RENDERING ════════════════════ */

export function renderGame(state){
  if(!playerId) return;
  const myData = state.players[playerId];
  const oppId  = Object.keys(state.players).find(k=>k!==playerId);
  const opData = oppId ? state.players[oppId] : null;
  const isMyTurn = state.turn_player_id === playerId;
  const step = state.step;
  const allowed = state.allowed_actions || [];

  /* Phase badge */
  phaseBadge.textContent = step || state.game_state || '\u2014';

  /* Status */
  if(state.game_state === 'mulligan'){
    setStatus('Mulligan Phase \u2014 Choose your starting hand');
  } else if(state.game_state === 'setup'){
    setStatus('Setup Phase \u2014 Place holomen face-down');
  } else if(state.pending_life_deduction === playerId){
    setStatus('\u26a1 Your holomen was knocked out! Deduct a life card.');
  } else if(state.pending_centre_fill === playerId){
    setStatus('\ud83c\udfaf Move a holomen to centre position!');
  } else if(state.pending_life_deduction || state.pending_centre_fill){
    setStatus('Waiting for opponent\u2026');
  } else if(state.step_state && state.step_state.pending_support){
    setStatus(`\u26a1 Select cards for ${state.step_state.pending_support.card_name}`);
  } else {
    setStatus(isMyTurn ? "Your turn" : "Opponent's turn");
  }

  /* Player labels */
  document.getElementById('you_label').textContent = `You \u2013 ${myData.name}`;
  document.getElementById('opp_label').textContent = opData ? opData.name : 'Opponent';

  /* Debug JSON */
  document.getElementById('you_json').textContent = JSON.stringify(myData,null,2);
  document.getElementById('opp_json').textContent = JSON.stringify(opData,null,2);

  /* Step bar */
  if(state.game_state === 'playing'){
    stepBar.style.display = 'flex';
    turnInfo.textContent = `Turn ${state.turn_number} \u2014 ${isMyTurn ? 'Your Turn' : "Opponent's Turn"}`;

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

    const nextStepBtn = document.getElementById('next_step_btn');
    if(isMyTurn && step === 'cheer'){
      nextStepBtn.style.display = '';
      nextStepBtn.textContent = 'Skip Cheer \u2192';
      nextStepBtn.onclick = ()=> sendAction({type:'skip_cheer'});
    } else if(isMyTurn && step === 'main'){
      nextStepBtn.style.display = '';
      nextStepBtn.textContent = 'End Main \u2192';
      nextStepBtn.onclick = ()=> sendAction({type:'end_main'});
    } else if(isMyTurn && step === 'performance'){
      nextStepBtn.style.display = '';
      nextStepBtn.textContent = 'End Performance \u2192';
      nextStepBtn.onclick = ()=> sendAction({type:'end_performance'});
    } else {
      nextStepBtn.style.display = 'none';
    }
  } else {
    stepBar.style.display = 'none';
  }

  /* Pending banner */
  if(state.pending_life_deduction === playerId){
    pendingBanner.textContent = '\u26a1 KNOCKOUT \u2014 Right-click Life zone to deduct. Click "End Deduct Life" when done.';
    pendingBanner.style.display = 'block';
    pendingBanner.style.background = '#8b1313';
  } else if(state.pending_centre_fill === playerId){
    pendingBanner.textContent = '\ud83c\udfaf Centre is empty! Select a back holomen to move to Centre';
    pendingBanner.style.display = 'block';
    pendingBanner.style.background = '#8b4513';
    showCentreFillPicker();
  } else if(state.step_state && state.step_state.pending_support){
    const ps = state.step_state.pending_support;
    const remaining = ps.picks ? ps.picks.length : 0;
    pendingBanner.textContent = `\u26a1 ${ps.card_name} \u2014 ${remaining} pick${remaining!==1?'s':''} remaining`;
    pendingBanner.style.display = 'block';
    pendingBanner.style.background = '#1a4a6a';
  } else {
    pendingBanner.style.display = 'none';
  }

  updateActionButtons(state, isMyTurn, allowed);

  renderPlaymat('you_playmat', myData.zones, true);
  renderPlaymat('opp_playmat', opData ? opData.zones : null, false);
  renderHandTray(myData.zones.hand || []);

  if(state.game_state === 'playing'){
    checkPendingSupportPicks(state);
    /* Auto-show centre fill picker during reset/end when need_centre */
    const isMyTurnNow = state.turn_player_id === playerId;
    const needCentre = state.step_state && state.step_state.need_centre;
    if(isMyTurnNow && needCentre){
      showCentreFillPicker();
    } else if(!state.pending_centre_fill || state.pending_centre_fill !== playerId){
      resetCentreFillFlag();
    }
  } else {
    resetCentreFillFlag();
  }
}

/* ── Show/hide action buttons per step ── */
function updateActionButtons(state, isMyTurn, allowed){
  const step = state.step;

  const btns = ['draw','skip_cheer','end_main','end_performance','end_turn',
                'end_deduct_life_btn','hand_to_deck'];
  btns.forEach(id => { const el = document.getElementById(id); if(el) el.style.display = 'none'; });

  if(state.pending_life_deduction === playerId){
    show('end_deduct_life_btn');
    return;
  }
  if(!isMyTurn) return;

  if(step === 'cheer') show('skip_cheer');
  if(step === 'main'){
    show('draw'); show('end_main');
    show('hand_to_deck');
  }
  if(step === 'performance') show('end_performance');
  if(step === 'end') show('end_turn');

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

    if(zd && zd.hidden){
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

          /* Setup phase */
          if(lastState && lastState.game_state === 'setup'){
            const mySetup = lastState.setup_state?.[playerId];
            const remaining = (mySetup?.returning || 0) - (mySetup?.returned || 0);
            if(remaining <= 0 && d.from === 'hand' && d.card_type && d.card_type.includes('\u30db\u30ed\u30e1\u30f3') && d.bloom_level === 'Debut'){
              if(zname === 'centre' || zname === 'back'){
                sendAction({type:'setup_place', zone:zname, card_number:d.card});
              }
            }
            return;
          }

          /* Cheer step */
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

          /* Bloom shortcut */
          const stageHasCard = (SINGLE_ZONES.includes(zname) || MULTI_ZONES.includes(zname))
            && Array.isArray(zd) && zd.length > 0;
          const fromHand = d.from === 'hand';
          const isHolomen = d.card_type && d.card_type.includes('\u30db\u30ed\u30e1\u30f3');
          const droppedOnCard = ev.target.closest('.main-card,.card-in-slot');
          if(stageHasCard && fromHand && isHolomen && droppedOnCard){
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

    /* Life zone right-click */
    if(isOwner && zname === 'life'){
      z.addEventListener('contextmenu', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        const count = (zd && zd.count != null) ? zd.count : (Array.isArray(zd) ? zd.length : 0);
        showZoneContextMenu(ev.clientX, ev.clientY, 'life', new Array(count));
      });
    }

    z.classList.toggle('play-target', isOwner && !!selectedCard && PLAY_ZONES.includes(zname));
    wrap.appendChild(z);
  }
}

/* ═══════ ZONE RENDERERS ═══════ */

function renderHiddenZone(container, count, zw, zh, zname){
  const d = document.createElement('div');
  if(count <= 0){ d.className = 'hidden-display'; container.appendChild(d); return; }

  if(HSTACK_ZONES.includes(zname)){
    d.className = 'hstack-display';
    const pad = 4;
    const visibleFraction = 0.15;
    const maxVisualW = zw - pad*2;
    let ch = maxVisualW;
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
    badge.textContent = `\u00d7${count}`;
    d.appendChild(badge);
  } else {
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
    badge.textContent = `\u00d7${count}`;
    d.appendChild(badge);
  }
  container.appendChild(d);
}

function renderStackZone(container, cards, zname, zw, zh, isOwner){
  const d = document.createElement('div');
  d.className = 'stack-display';
  if(!cards.length){ container.appendChild(d); return; }

  const pad = 4;
  const topCard = cards[cards.length - 1];
  const cardW = Math.min(zw - pad*2, (zh - pad*2 - 14) * 0.717);
  const cardH = cardW / 0.717;
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
  if(isOwner && zname === 'yell_deck'){
    img.draggable = true;
    img.addEventListener('dragstart', ev=>{
      ev.dataTransfer.setData('text/plain', JSON.stringify({card:'yell_top', from:'yell_deck'}));
    });
  }
  if(isOwner && zname === 'archive'){
    img.addEventListener('contextmenu', ev=>{
      ev.preventDefault(); ev.stopPropagation();
      showZoneContextMenu(ev.clientX, ev.clientY, zname, cards);
    });
  }
  if(isOwner && (zname === 'deck' || zname === 'yell_deck')){
    img.addEventListener('contextmenu', ev=>{
      ev.preventDefault(); ev.stopPropagation();
      showZoneContextMenu(ev.clientX, ev.clientY, zname, cards);
    });
  }
  d.appendChild(img);
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
  badge.textContent = `\u00d7${cards.length}`;
  d.appendChild(badge);
  container.appendChild(d);
}

function renderHStackZone(container, cards, zname, zw, zh, isOwner){
  const d = document.createElement('div');
  d.className = 'hstack-display';
  if(!cards.length){ container.appendChild(d); return; }

  const pad = 4;
  const n = cards.length;
  const visibleFraction = 0.15;
  const maxVisualW = zw - pad*2;
  let ch = maxVisualW;
  let cw = ch * 0.717;
  const maxVisualH = zh - pad*2 - 14;
  if(n === 1){
    if(cw > maxVisualH){ cw = maxVisualH; ch = cw / 0.717; if(ch > maxVisualW){ ch = maxVisualW; cw = ch * 0.717; }}
  } else {
    const needed = cw * (1 + (n-1)*visibleFraction);
    if(needed > maxVisualH){ cw = maxVisualH / (1 + (n-1)*visibleFraction); ch = cw / 0.717; if(ch > maxVisualW){ ch = maxVisualW; cw = ch * 0.717; }}
  }
  const visibleStrip = Math.round(cw * visibleFraction);
  const startY = pad + 12;
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
  badge.textContent = `\u00d7${n}`;
  d.appendChild(badge);
  container.appendChild(d);
}

function renderPeekCards(wrapper, card, cw, ch, isResting){
  const bloomArr = Array.isArray(card.stacked_cards) ? card.stacked_cards : [];
  const yellArr  = Array.isArray(card.attached_yells) ? card.attached_yells : [];
  const bloomPeek = 0.13;
  const yellPeek  = 0.10;

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

function renderSingleZone(container, cards, zname, zw, zh, isOwner){
  const d = document.createElement('div');
  d.className = 'single-display';
  if(!cards.length){ container.appendChild(d); return; }

  const card = cards[0];
  const pad = 4;
  const isResting = card.resting;
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

  const wrap = document.createElement('div');
  wrap.style.position = 'relative';
  wrap.style.width = cw + 'px';
  wrap.style.height = ch + 'px';
  wrap.style.zIndex = 10;

  renderPeekCards(wrap, card, cw, ch, isResting);

  const img = document.createElement('img');
  img.className = 'main-card' + (isResting ? ' resting' : '');
  img.src = cardImgSrc(card);
  img.style.width = cw+'px';
  img.style.height = ch+'px';
  img.style.position = 'relative';
  img.style.zIndex = 20;

  img.addEventListener('click', ()=>{
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
  } else {
    img.addEventListener('contextmenu', ev=>{
      ev.preventDefault(); ev.stopPropagation();
      showOppCardContextMenu(ev.clientX, ev.clientY, zname, 0, card);
    });
  }
  wrap.appendChild(img);
  d.appendChild(wrap);

  const nYells = yellArr.length;
  const nStack = bloomArr.length;
  if(nYells) renderYellBadge(yellArr, d, false);
  if(nStack){
    const b = document.createElement('div');
    b.className = 'badge badge-bloom';
    b.textContent = `B\u00d7${nStack}`;
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
  if(card.debut_this_turn){
    const b = document.createElement('div');
    b.className = 'badge badge-new';
    b.textContent = 'NEW';
    d.appendChild(b);
  }
  const nSupps = (card.attached_supports || []).length;
  if(nSupps){
    const sb = document.createElement('div');
    sb.className = 'badge';
    sb.style.background = 'rgba(200,80,180,0.85)';
    sb.textContent = `\ud83d\udd27\u00d7${nSupps}`;
    d.appendChild(sb);
  }
  container.appendChild(d);
}

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
    const yellExW = yellArr.length * (cw * yellPeek);
    const bloomExH = bloomArr.length * (ch * bloomPeek);
    if(cw + yellExW > slotW - pad*2){
      const s = (slotW-pad*2)/(cw+yellExW); cw*=s; ch*=s;
    }
    if(ch + bloomExH > zh - pad*2 - 4){
      const s = (zh-pad*2-4)/(ch+bloomExH); cw*=s; ch*=s;
    }

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
    } else {
      img.addEventListener('contextmenu', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        showOppCardContextMenu(ev.clientX, ev.clientY, zname, i, card);
      });
    }
    wrap.appendChild(img);
    slot.appendChild(wrap);

    const nYells = yellArr.length;
    const nStack = bloomArr.length;
    if(nYells) renderYellBadge(yellArr, slot, true);
    if(nStack){
      const b = document.createElement('div');
      b.className = 'badge badge-bloom';
      b.textContent = `B\u00d7${nStack}`;
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
    if(card.debut_this_turn){
      const b = document.createElement('div');
      b.className = 'badge badge-new';
      b.textContent = 'NEW';
      b.style.position = 'absolute';
      slot.appendChild(b);
    }
    const nSupps = (card.attached_supports || []).length;
    if(nSupps){
      const sb = document.createElement('div');
      sb.className = 'badge';
      sb.style.cssText = 'background:rgba(200,80,180,0.85);position:absolute';
      sb.textContent = `\ud83d\udd27\u00d7${nSupps}`;
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

    img.addEventListener('click', ev=>{
      ev.stopPropagation();
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
        setSelectedCard({card_number:cd.card_number, from_zone:'hand'});
        handTray.querySelectorAll('.card-thumb').forEach(i=>i.classList.remove('selected'));
        img.classList.add('selected');
        playHint.textContent = `Selected ${cd.card_name||cd.card_number} \u2014 click zone to play`;
        if(lastState) renderGame(lastState);
      }
    });

    img.addEventListener('contextmenu', ev=>{
      ev.preventDefault(); ev.stopPropagation();
      showHandContextMenu(ev.clientX, ev.clientY, idx, cd);
    });

    img.addEventListener('dblclick', ev=>{
      ev.stopPropagation();
      showZoom(img.src);
    });

    img.addEventListener('dragstart', ev=>{
      ev.dataTransfer.setData('text/plain', JSON.stringify({card:cd.card_number, from:'hand', card_type:cd.card_type||'', bloom_level:cd.bloom_level||''}));
    });

    handTray.appendChild(img);
  });
}

export function clearSelection(){
  setSelectedCard(null);
  handTray.querySelectorAll('.card-thumb').forEach(i=>i.classList.remove('selected'));
  playHint.textContent = '';
  document.querySelectorAll('.zone.play-target').forEach(z=>z.classList.remove('play-target'));
}
