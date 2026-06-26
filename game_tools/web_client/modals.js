/* ══════════════════════════════════════════════════════════════
   hOCG Web Client — Modal Dialogs & Pickers
   Bloom picker, arts picker, stack popup, search, peek,
   support picker, oshi skill, deduct life, zoom, toast
   ══════════════════════════════════════════════════════════════ */
import {
  ws, playerId, lastState, modalContainer,
  sendAction, cardImgSrc, YELL_COLORS, renderYellBadge,
  CARD_BACK, YELL_LIFE_BACK,
} from './state.js';

/* ════════════════════ STAGE HOLOMEN PICKER GRID ════════════════════ */
/**
 * Build a 2-row stage layout grid for holomen selection.
 * Top row: collabo (left), centre (right)
 * Bottom row: back positions left→right
 * @param {object} zones - the player's zones data
 * @param {function} onSelect - callback({zone, idx, card})
 * @returns {HTMLElement} the stage-pick-grid element
 */
function buildStagePickerGrid(zones, onSelect, labelFn){
  const grid = document.createElement('div');
  grid.className = 'stage-pick-grid';

  /* Top row: collabo + centre */
  const topRow = document.createElement('div');
  topRow.className = 'stage-pick-row';
  const collabo = Array.isArray(zones.collabo) ? zones.collabo : [];
  const centre  = Array.isArray(zones.centre)  ? zones.centre  : [];
  collabo.forEach((c, idx) => topRow.appendChild(makePickCard(c, 'collabo', idx, onSelect, labelFn)));
  centre.forEach((c, idx)  => topRow.appendChild(makePickCard(c, 'centre', idx, onSelect, labelFn)));
  if(topRow.children.length) grid.appendChild(topRow);

  /* Bottom row: back */
  const back = Array.isArray(zones.back) ? zones.back : [];
  if(back.length){
    const botRow = document.createElement('div');
    botRow.className = 'stage-pick-row';
    back.forEach((c, idx) => botRow.appendChild(makePickCard(c, 'back', idx, onSelect, labelFn)));
    grid.appendChild(botRow);
  }
  return grid;
}

function makePickCard(card, zone, idx, onSelect, labelFn){
  const mc = document.createElement('div');
  mc.className = 'modal-card';
  const img = document.createElement('img');
  img.src = cardImgSrc(card);
  mc.appendChild(img);
  const name = document.createElement('div');
  name.className = 'mc-name';
  name.textContent = labelFn ? labelFn(card, zone) : `${card.card_name} [${zone}]`;
  mc.appendChild(name);
  mc.addEventListener('click', ()=> onSelect({zone, idx, card}));
  return mc;
}

/* ════════════════════ ZOOM ════════════════════ */
export function showZoom(src){
  const m = document.createElement('div');
  m.className = 'zoom-modal';
  const big = document.createElement('img');
  big.src = src;
  m.appendChild(big);
  m.addEventListener('click', ()=>m.remove());
  document.getElementById('zoom_container').appendChild(m);
}

/* ════════════════════ SUPPORT TOAST ════════════════════ */
export function showSupportToast(text, color, duration){
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

/* ════════════════════ BLOOM PICKER ════════════════════ */
export function showBloomPicker(zname, idx, targetCard){
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const hand = myData.zones.hand || [];

  const BLOOM_VALID = {'Debut':['1st'], '1st':['1st','2nd'], '2nd':['2nd']};
  const allowed = BLOOM_VALID[targetCard.bloom_level] || [];
  if(!allowed.length){
    alert(`${targetCard.card_name} (${targetCard.bloom_level}) cannot be bloomed further.`);
    return;
  }

  const eligible = hand.filter(c =>
    c.card_type && c.card_type.includes('\u30db\u30ed\u30e1\u30f3') && allowed.includes(c.bloom_level)
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

export function canPayYells(artReq, attachedYells){
  const required = artReq || [];
  if(!required.length) return true;
  const used = new Array(attachedYells.length).fill(false);
  for(const reqColor of required){
    let matched = false;
    for(let i = 0; i < attachedYells.length; i++){
      if(used[i]) continue;
      const yellColors = Array.isArray(attachedYells[i].color) ? attachedYells[i].color : [];
      if(reqColor === '\u7121' || yellColors.includes(reqColor)){
        used[i] = true;
        matched = true;
        break;
      }
    }
    if(!matched) return false;
  }
  return true;
}

function renderArtYellReq(reqColors){
  const span = document.createElement('span');
  span.className = 'art-yell-req';
  for(const c of (reqColors||[])){
    const dot = document.createElement('span');
    dot.className = 'yell-dot';
    if(c === '\u7121'){
      dot.style.background = '#999';
      dot.style.border = '1px dashed #666';
    } else {
      dot.style.background = YELL_COLORS[c] || '#e0c020';
    }
    span.appendChild(dot);
  }
  return span;
}

export function showArtsPicker(zname, idx, card){
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
  h.textContent = `Arts \u2014 ${card.card_name}`;
  h.style.marginBottom = '4px';
  overlay.appendChild(h);

  const hpInfo = document.createElement('div');
  hpInfo.style.cssText = 'color:#aaa;font-size:13px;margin-bottom:12px;text-align:center;';
  let hpText = `HP: ${card.hp || '?'}  |  Damage: ${card.damage || 0}  |  Yells: ${yells.length}`;
  const mod = card.arts_modifier || 0;
  if(mod > 0) hpText += `  |  \ud83d\udd27 Arts +${mod}`;
  hpInfo.textContent = hpText;
  overlay.appendChild(hpInfo);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';
  grid.style.flexDirection = 'column';
  grid.style.alignItems = 'center';
  grid.style.gap = '8px';

  artsList.forEach((art, artIdx) => {
    const canUse = canPayYells(art['\u30a8\u30fc\u30eb'], yells);
    const row = document.createElement('div');
    row.className = 'arts-row' + (canUse ? ' arts-usable' : ' arts-disabled');
    row.style.cssText = `display:flex;align-items:center;gap:10px;padding:10px 16px;
      border-radius:8px;cursor:${canUse?'pointer':'not-allowed'};width:90%;max-width:420px;
      background:${canUse?'rgba(50,180,80,0.15)':'rgba(80,80,80,0.2)'};
      border:1px solid ${canUse?'#4a4':'#555'};opacity:${canUse?1:0.5};`;

    const nameEl = document.createElement('div');
    nameEl.style.cssText = 'flex:1;font-weight:bold;font-size:14px;color:#eee;';
    nameEl.textContent = art.name || `Art ${artIdx+1}`;
    row.appendChild(nameEl);

    row.appendChild(renderArtYellReq(art['\u30a8\u30fc\u30eb']));

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

function showArtsTargetPicker(atkZone, atkIdx, artsIdx, art){
  if(!lastState) return;
  const oppId = Object.keys(lastState.players).find(k=>k!==playerId);
  if(!oppId){ alert('No opponent found.'); return; }
  const oppData = lastState.players[oppId];
  if(!oppData || !oppData.zones) return;

  const hasTargets = ['centre','back','collabo'].some(z => Array.isArray(oppData.zones[z]) && oppData.zones[z].length);
  if(!hasTargets){ alert('Opponent has no holomen on stage.'); return; }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = `${art.name || 'Arts'} (${art.damage} dmg) \u2014 Select target`;
  overlay.appendChild(h);

  const grid = buildStagePickerGrid(oppData.zones, ({zone, idx})=>{
    overlay.remove();
    sendAction({
      type:'play_arts', zone:atkZone, card_index:atkIdx,
      arts_index:artsIdx, target_player_id:oppId,
      target_zone:zone, target_card_index:idx,
    });
  }, (card, zone)=> `${card.card_name} [${zone}] HP:${card.hp||'?'} Dmg:${card.damage||0}`);
  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Cancel';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  modalContainer.appendChild(overlay);
}

/* ════════════════════ STACK / YELL POPUP ════════════════════ */
export function showStackPopup(zname, idx, card){
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = `${card.card_name} \u2013 Stack & Yells`;
  overlay.appendChild(h);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';

  /* Active card */
  const activeLabel = document.createElement('h3');
  activeLabel.textContent = 'Active Card';
  activeLabel.style.cssText = 'width:100%;text-align:center;color:#8f8';
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
    stackLabel.style.cssText = 'width:100%;text-align:center;color:#7af';
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
    yellLabel.style.cssText = 'width:100%;text-align:center;color:#ffa';
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

  /* Attached support cards */
  const supps = Array.isArray(card.attached_supports) ? card.attached_supports : [];
  if(supps.length){
    const suppLabel = document.createElement('h3');
    suppLabel.textContent = `Attached Supports (${supps.length})`;
    suppLabel.style.cssText = 'width:100%;text-align:center;color:#f9a';
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
export function buildSearchModalUI(title, zoneKey, cards, actions){
  if(!cards.length){ alert(`${title}: empty`); return; }

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
    const ordered = zoneKey === 'deck' ? [...filtered].reverse() : filtered;
    ordered.forEach((card) => {
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
  overlay.addEventListener('click', ev=>{ if(ev.target === overlay) overlay.remove(); });
  modalContainer.appendChild(overlay);
}

/* ════════════════════ SUPPORT CARD PLAY ════════════════════ */
export function playSupportCard(cardNumber){
  sendAction({type:'play_support', card_number: cardNumber});

  const handler = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch{ return; }
    if(data.type !== 'action_result') return;
    ws.removeEventListener('message', handler);
    const res = data.result;
    if(!res || !res.success){
      showSupportToast(`\u274c ${res?.reason || 'Failed'}`, '#c33');
      return;
    }
    const acts = res.actions_taken || [];
    const cardName = res.card_name || cardNumber;
    if(acts.length){
      showSupportToast(`\u26a1 ${cardName}: ${acts.join(', ')}`, '#2a6');
    } else {
      showSupportToast(`\u26a1 ${cardName} played`, '#2a6');
    }
    if(res.turn_modifiers && res.turn_modifiers.length){
      const mods = res.turn_modifiers.map(m =>
        `${m.target}: ${m.amount >= 0 ? '+' : ''}${m.amount} (${m.type})`
      ).join(', ');
      showSupportToast(`\ud83d\udcca ${mods}`, '#26a', 4000);
    }
  };
  ws.addEventListener('message', handler);
}

/* ═══════════════════ OSHI SKILL ACTIVATION ═══════════════════ */
export function showOshiSkillActivation(skillType){
  sendAction({type:'get_oshi_skill_info'});

  const handler = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch{ return; }
    if(data.type !== 'action_result') return;
    ws.removeEventListener('message', handler);
    const res = data.result;
    if(!res || !res.success){
      showSupportToast(`\u274c ${res?.reason || 'Failed to get skill info'}`, '#c33');
      return;
    }
    const skill = skillType === 'sp_oshi_skill' ? res.sp_oshi_skill : res.oshi_skill;
    if(!skill){ showSupportToast('\u274c Skill not found', '#c33'); return; }
    if(!skill.available){ showSupportToast(`\u274c ${skill.name}: ${skill.reason}`, '#c33'); return; }
    _showOshiSkillModal(skillType, skill, res.holo_power_count);
  };
  ws.addEventListener('message', handler);
}

function _showOshiSkillModal(skillType, skill, hpCount){
  const isX = (String(skill.cost) === 'X');
  const isSP = skillType === 'sp_oshi_skill';
  const actionType = isSP ? 'use_sp_oshi_skill' : 'use_oshi_skill';

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.style.zIndex = '800';

  const title = document.createElement('h3');
  title.style.cssText = 'margin:0 0 8px; color:#fff;';
  title.textContent = isSP ? `\ud83c\udf1f SP Oshi Skill: ${skill.name}` : `\u26a1 Oshi Skill: ${skill.name}`;
  overlay.appendChild(title);

  const effectEl = document.createElement('p');
  effectEl.style.cssText = 'margin:0 0 12px; color:#ccc; font-size:13px; max-width:400px; line-height:1.5;';
  effectEl.textContent = skill.effect;
  overlay.appendChild(effectEl);

  const costInfo = document.createElement('div');
  costInfo.style.cssText = 'margin:0 0 12px; color:#ffd700; font-size:14px; font-weight:600;';
  costInfo.textContent = isX
    ? `Holo Power Cost: X (you choose) \u2014 Available: ${hpCount}`
    : `Holo Power Cost: ${skill.cost} \u2014 Available: ${hpCount}`;
  overlay.appendChild(costInfo);

  const timingEl = document.createElement('div');
  timingEl.style.cssText = 'margin:0 0 16px; font-size:12px;';
  if(isSP){
    timingEl.innerHTML = '<span style="background:#8b1313;color:#fff;padding:2px 8px;border-radius:4px;">Once per Game</span>';
    if(skill.used_this_game) timingEl.innerHTML += ' <span style="color:#f66;">\u2014 Already Used!</span>';
  } else {
    timingEl.innerHTML = '<span style="background:#1a4a6a;color:#fff;padding:2px 8px;border-radius:4px;">Once per Turn</span>';
    if(skill.used_this_turn) timingEl.innerHTML += ' <span style="color:#f66;">\u2014 Already Used!</span>';
  }
  overlay.appendChild(timingEl);

  let xInput = null;
  if(isX){
    const inputWrap = document.createElement('div');
    inputWrap.style.cssText = 'margin:0 0 16px; display:flex; align-items:center; gap:8px;';
    const label = document.createElement('label');
    label.style.cssText = 'color:#fff; font-size:13px;';
    label.textContent = 'Holo Power to pay (X):';
    inputWrap.appendChild(label);
    xInput = document.createElement('input');
    xInput.type = 'number'; xInput.min = '0'; xInput.max = String(hpCount); xInput.value = '0';
    xInput.style.cssText = 'width:60px; padding:4px 8px; border-radius:4px; border:1px solid #555; background:#222; color:#fff; font-size:14px; text-align:center;';
    inputWrap.appendChild(xInput);
    const maxLabel = document.createElement('span');
    maxLabel.style.cssText = 'color:#888; font-size:12px;';
    maxLabel.textContent = `(max: ${hpCount})`;
    inputWrap.appendChild(maxLabel);
    overlay.appendChild(inputWrap);
  }

  const btnWrap = document.createElement('div');
  btnWrap.style.cssText = 'display:flex; gap:12px; justify-content:center;';

  const confirmBtn = document.createElement('button');
  confirmBtn.style.cssText = 'padding:8px 24px; border:none; border-radius:6px; font-size:14px; font-weight:600; cursor:pointer; ' +
    (isSP ? 'background:#c8a000; color:#000;' : 'background:#2a8; color:#fff;');
  confirmBtn.textContent = isSP ? '\ud83c\udf1f Activate SP Skill' : '\u26a1 Activate Skill';
  confirmBtn.onclick = () => {
    const action = {type: actionType};
    if(isX && xInput) action.x_cost = parseInt(xInput.value) || 0;
    overlay.remove();
    sendAction(action);

    const resHandler = (ev2) => {
      let d2;
      try { d2 = JSON.parse(ev2.data); } catch{ return; }
      if(d2.type !== 'action_result') return;
      ws.removeEventListener('message', resHandler);
      const r = d2.result;
      if(!r || !r.success){ showSupportToast(`\u274c ${r?.reason || 'Failed'}`, '#c33'); return; }
      const paid = r.cost_paid || 0;
      const remaining = r.holo_power_remaining != null ? r.holo_power_remaining : '?';
      showSupportToast(
        `${isSP ? '\ud83c\udf1f' : '\u26a1'} ${r.skill_name} activated! (Cost: ${paid} HP, Remaining: ${remaining})`,
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

  overlay.addEventListener('click', ev => { if(ev.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}

/* ════════════════════ SUPPORT PICKER (pending picks) ════════════════════ */
let _supportPickerShown = null;

export function checkPendingSupportPicks(state){
  const ss = state.step_state || {};
  const pending = ss.pending_support;
  if(!pending || !pending.picks || !pending.picks.length){
    _supportPickerShown = null;
    return;
  }
  const firstPick = pending.picks[0];
  if(_supportPickerShown === firstPick.pick_id) return;
  _supportPickerShown = firstPick.pick_id;
  showSupportPickerModal(pending.card_name, firstPick);
}

function showSupportPickerModal(cardName, pick){
  document.querySelectorAll('.support-picker-overlay').forEach(e => e.remove());

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay support-picker-overlay';

  const h = document.createElement('h3');
  h.textContent = `\u26a1 ${cardName}`;
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

  // ─── REORDER MODE ───
  if(pickType === 'reorder'){
    const info = document.createElement('div');
    info.style.cssText = 'font-size:12px;color:#adf;margin-bottom:8px;text-align:center';
    info.textContent = 'Drag cards to set the order (top \u2192 bottom). First card = top.';
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

      row.addEventListener('dragstart', e => {
        e.dataTransfer.effectAllowed = 'move';
        row.style.opacity = '0.5';
        row._dragIdx = Array.from(list.children).indexOf(row);
      });
      row.addEventListener('dragend', () => { row.style.opacity = '1'; });
      row.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; });
      row.addEventListener('drop', e => {
        e.preventDefault();
        const dragged = list.querySelector('[style*="opacity: 0.5"]') || list.querySelector('[style*="opacity:0.5"]');
        if(dragged && dragged !== row){
          const rect = row.getBoundingClientRect();
          const mid = rect.top + rect.height / 2;
          if(e.clientY < mid) list.insertBefore(dragged, row);
          else list.insertBefore(dragged, row.nextSibling);
          Array.from(list.children).forEach((r, i) => {
            const n = r.querySelector('.reorder-num');
            if(n) n.textContent = `${i+1}.`;
          });
        }
      });
      row.addEventListener('contextmenu', ev => { ev.preventDefault(); showZoom(cardImgSrc(card)); });
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
      const finalOrder = [];
      Array.from(list.children).forEach(row => {
        const img = row.querySelector('img');
        if(img){
          const cn = (pick.cards || []).find(c => cardImgSrc(c) === img.src);
          if(cn) finalOrder.push(cn.card_number);
        }
      });
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

  // ─── STANDARD SELECTION MODE ───
  const counter = document.createElement('div');
  counter.style.cssText = 'font-size:12px;color:#aaa;margin-bottom:8px;text-align:center';
  overlay.appendChild(counter);

  const selected = new Set();

  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'modal-close';
  confirmBtn.style.background = '#2d5bff';

  function updateCounter(){
    const label = pickType === 'select_cheer' ? 'Yells' :
                  (pickType === 'holomen' || pickType === 'attach_support') ? 'Holomen' : 'Cards';
    counter.textContent = `Selected ${label}: ${selected.size} / ${maxPick}${minPick > 0 ? ` (min ${minPick})` : ''}`;
    confirmBtn.disabled = selected.size < minPick;
  }

  // ─── Build card element helper ───
  const allCards = pick.cards || [];
  const cardEls = [];   // parallel array of DOM elements for deselect-all

  function _buildCardEl(card, cardIdx){
    const cn = card.card_number;
    const isSelectable = !selectableSet || selectableSet.has(cn);

    const mc = document.createElement('div');
    mc.className = 'modal-card';
    mc.style.transition = 'border-color 0.15s, box-shadow 0.15s';
    if(!isSelectable){ mc.style.opacity = '0.4'; mc.style.pointerEvents = 'none'; }

    const img = document.createElement('img');
    img.src = cardImgSrc(card);
    img.style.cursor = isSelectable ? 'pointer' : 'default';
    mc.appendChild(img);

    const name = document.createElement('div');
    name.className = 'mc-name';
    let label = card.card_name || card.card_number;
    if(pickType === 'select_cheer' && card.color){
      label += ` [${Array.isArray(card.color) ? card.color.join('/') : card.color}]`;
    }
    if((pickType === 'holomen' || pickType === 'attach_support') && card.hp){
      label += ` (HP:${card.hp})`;
    }
    name.textContent = label;
    mc.appendChild(name);

    if(selectableSet && isSelectable){
      const marker = document.createElement('div');
      marker.style.cssText = 'position:absolute;top:2px;right:2px;background:#5f5;color:#000;font-size:9px;padding:1px 4px;border-radius:3px;font-weight:bold';
      marker.textContent = '\u2713 match';
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
              cardEls.forEach(c => {
                c.style.borderColor = '#333';
                c.style.boxShadow = 'none';
              });
            } else { return; }
          }
          selected.add(cardIdx);
          mc.style.borderColor = '#5f5';
          mc.style.boxShadow = '0 0 8px rgba(80,255,80,0.4)';
        }
        updateCounter();
      });
    }

    mc.addEventListener('contextmenu', ev=>{ ev.preventDefault(); showZoom(cardImgSrc(card)); });
    cardEls[cardIdx] = mc;
    return mc;
  }

  // ─── Stage-layout mode for holomen / attach_support ───
  const useStageLayout = (pickType === 'holomen' || pickType === 'attach_support')
                         && allCards.some(c => c.zone);

  if(useStageLayout){
    const stageWrap = document.createElement('div');
    stageWrap.className = 'stage-pick-grid';

    const collaboCards = [];
    const centreCards  = [];
    const backCards    = [];
    allCards.forEach((card, i) => {
      if(card.zone === 'collabo') collaboCards.push(i);
      else if(card.zone === 'centre') centreCards.push(i);
      else backCards.push(i); // back or unknown
    });

    // Top row: collabo (left) + centre (right)
    if(collaboCards.length || centreCards.length){
      const topRow = document.createElement('div');
      topRow.className = 'stage-pick-row';

      const makeSlot = (indices, zoneLabel) => {
        if(!indices.length){
          // empty slot placeholder
          const ph = document.createElement('div');
          ph.className = 'modal-card';
          ph.style.cssText = 'opacity:0.25;pointer-events:none';
          const lbl = document.createElement('div');
          lbl.className = 'mc-name';
          lbl.textContent = `(${zoneLabel} - empty)`;
          ph.appendChild(lbl);
          return ph;
        }
        // single card per slot (centre/collabo are single)
        const frag = document.createDocumentFragment();
        indices.forEach(ci => frag.appendChild(_buildCardEl(allCards[ci], ci)));
        return frag;
      };
      topRow.appendChild(makeSlot(collaboCards, 'Collabo'));
      topRow.appendChild(makeSlot(centreCards, 'Centre'));
      stageWrap.appendChild(topRow);
    }

    // Zone label row
    if(collaboCards.length || centreCards.length){
      const labelRow = document.createElement('div');
      labelRow.style.cssText = 'display:flex;justify-content:center;gap:60px;margin:-4px 0 6px;font-size:11px;color:#888';
      const l1 = document.createElement('span'); l1.textContent = 'Collabo';
      const l2 = document.createElement('span'); l2.textContent = 'Centre';
      labelRow.appendChild(l1);
      labelRow.appendChild(l2);
      stageWrap.appendChild(labelRow);
    }

    // Bottom row: back
    if(backCards.length){
      const botRow = document.createElement('div');
      botRow.className = 'stage-pick-row';
      backCards.forEach(ci => botRow.appendChild(_buildCardEl(allCards[ci], ci)));
      stageWrap.appendChild(botRow);

      const backLabel = document.createElement('div');
      backLabel.style.cssText = 'text-align:center;font-size:11px;color:#888;margin:-4px 0 2px';
      backLabel.textContent = 'Back';
      stageWrap.appendChild(backLabel);
    }

    overlay.appendChild(stageWrap);
  } else {
    // ─── Flat grid for non-stage picks ───
    const grid = document.createElement('div');
    grid.className = 'modal-grid';
    allCards.forEach((card, cardIdx) => grid.appendChild(_buildCardEl(card, cardIdx)));
    overlay.appendChild(grid);
  }

  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex;gap:10px;margin-top:12px';

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
      sendAction({ type: 'pick_support_cards', pick_id: pick.pick_id, card_numbers: [] });
    });
    btnRow.appendChild(skipBtn);
  }

  overlay.appendChild(btnRow);
  updateCounter();
  modalContainer.appendChild(overlay);
}

/* ════════════════════ ATTACH YELL PICKER ════════════════════ */
/** Pick a stage holomen to attach top yell card to (main step). */
export function showAttachYellPicker(){
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const yellDeck = myData.zones.yell_deck;
  if(!yellDeck || !yellDeck.length){ alert('Yell deck is empty!'); return; }

  const hasHolomen = ['centre','back','collabo'].some(z => Array.isArray(myData.zones[z]) && myData.zones[z].length);
  if(!hasHolomen){ alert('No holomen on stage to attach yell to.'); return; }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = 'Attach Yell \u2014 Select holomen';
  overlay.appendChild(h);

  const grid = buildStagePickerGrid(myData.zones, ({zone, idx})=>{
    overlay.remove();
    sendAction({type:'attach_yell', zone:zone, card_index:idx});
  });
  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Cancel';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  overlay.addEventListener('click', ev=>{ if(ev.target === overlay) overlay.remove(); });
  modalContainer.appendChild(overlay);
}

/* ════════════════════ SEARCH YELL MODAL ════════════════════ */
/** Browse yell deck — attach chosen yell to a holomen or archive it. */
export function showSearchYellModal(){
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const yellDeck = myData.zones.yell_deck;
  if(!yellDeck || !yellDeck.length){ alert('Yell deck is empty!'); return; }

  /* Sub-picker: choose holomen target for a specific yell card */
  function openHolomenSubPicker(yellCard, parentOverlay){
    const hasHolomen = ['centre','back','collabo'].some(z => Array.isArray(myData.zones[z]) && myData.zones[z].length);
    if(!hasHolomen){ alert('No holomen on stage!'); return; }

    const sub = document.createElement('div');
    sub.className = 'modal-overlay';
    const sh = document.createElement('h3');
    sh.textContent = 'Attach to which holomen?';
    sub.appendChild(sh);

    const sgrid = buildStagePickerGrid(myData.zones, ({zone, idx})=>{
      sub.remove();
      parentOverlay.remove();
      sendAction({type:'search_yell', card_number:yellCard.card_number,
                  destination:'attach', zone:zone, card_index:idx});
    });
    sub.appendChild(sgrid);
    const close = document.createElement('button');
    close.className = 'modal-close';
    close.textContent = 'Back';
    close.addEventListener('click', ()=> sub.remove());
    sub.appendChild(close);
    modalContainer.appendChild(sub);
  }

  /* Main search overlay */
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = `Search Yell Deck (${yellDeck.length} cards)`;
  overlay.appendChild(h);

  const filter = document.createElement('input');
  filter.className = 'modal-filter';
  filter.placeholder = 'Filter by name/number...';
  overlay.appendChild(filter);

  const grid = document.createElement('div');
  grid.className = 'modal-grid';

  function populate(ft){
    grid.innerHTML = '';
    const filtered = ft ? yellDeck.filter(c =>
      `${c.card_number} ${c.card_name} ${c.card_type}`.toLowerCase().includes(ft.toLowerCase())
    ) : yellDeck;
    filtered.forEach((card) => {
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

      const attachBtn = document.createElement('button');
      attachBtn.textContent = 'Attach';
      attachBtn.addEventListener('click', ev => {
        ev.stopPropagation();
        openHolomenSubPicker(card, overlay);
      });
      btns.appendChild(attachBtn);

      const archiveBtn = document.createElement('button');
      archiveBtn.textContent = 'Archive';
      archiveBtn.addEventListener('click', ev => {
        ev.stopPropagation();
        overlay.remove();
        sendAction({type:'search_yell', card_number:card.card_number, destination:'archive'});
      });
      btns.appendChild(archiveBtn);

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
  overlay.addEventListener('click', ev=>{ if(ev.target === overlay) overlay.remove(); });
  modalContainer.appendChild(overlay);
}

/* ════════════════════ DEDUCT LIFE PICKER ════════════════════ */
export function showDeductLifePicker(){
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const lifeCount = Array.isArray(myData.zones.life) ? myData.zones.life.length :
                    (myData.zones.life?.count || 0);
  if(!lifeCount){ alert('No life cards remaining!'); return; }

  const hasHolomen = ['centre','back','collabo'].some(z => Array.isArray(myData.zones[z]) && myData.zones[z].length);
  if(!hasHolomen){ alert('No holomen on stage to attach life card to.'); return; }

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = 'Deduct Life \u2014 Select holomen to attach';
  overlay.appendChild(h);

  const grid = buildStagePickerGrid(myData.zones, ({zone, idx})=>{
    overlay.remove();
    sendAction({type:'deduct_life', zone:zone, card_index:idx});
  });
  overlay.appendChild(grid);
  const close = document.createElement('button');
  close.className = 'modal-close';
  close.textContent = 'Cancel';
  close.addEventListener('click', ()=> overlay.remove());
  overlay.appendChild(close);
  modalContainer.appendChild(overlay);
}

/* ════════════════════ CENTRE FILL PICKER ════════════════════ */
let _centreFillOpen = false;
export function showCentreFillPicker(){
  if(_centreFillOpen) return;  // prevent duplicate popups
  if(!lastState) return;
  const myData = lastState.players[playerId];
  const back = Array.isArray(myData.zones.back) ? myData.zones.back : [];
  if(!back.length) return;  // nothing to pick from

  _centreFillOpen = true;
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const h = document.createElement('h3');
  h.textContent = 'Centre is empty \u2014 Select a back holomen to move';
  overlay.appendChild(h);

  const grid = document.createElement('div');
  grid.className = 'stage-pick-grid';
  const row = document.createElement('div');
  row.className = 'stage-pick-row';
  back.forEach((card, idx) => {
    const mc = document.createElement('div');
    mc.className = 'modal-card';
    const img = document.createElement('img');
    img.src = cardImgSrc(card);
    mc.appendChild(img);
    const name = document.createElement('div');
    name.className = 'mc-name';
    name.textContent = `${card.card_name}`;
    mc.appendChild(name);
    mc.addEventListener('click', ()=>{
      overlay.remove();
      _centreFillOpen = false;
      sendAction({type:'move_to_centre', from_zone:'back', card_number:card.card_number, card_index:idx});
    });
    row.appendChild(mc);
  });
  grid.appendChild(row);
  overlay.appendChild(grid);

  overlay.addEventListener('click', ev=>{
    if(ev.target === overlay){ overlay.remove(); _centreFillOpen = false; }
  });
  modalContainer.appendChild(overlay);
}
export function resetCentreFillFlag(){ _centreFillOpen = false; }

/* ════════════════════ PEEK MODAL ════════════════════ */
export function openPeekModal(count){
  sendAction({type:'peek_deck', count});
  const handler = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch{ return; }
    if(data.type !== 'action_result') return;
    ws.removeEventListener('message', handler);
    const res = data.result;
    if(!res.success){ alert(res.reason || 'Peek failed'); return; }
    showPeekModal(count, res.cards);
  };
  ws.addEventListener('message', handler);
}

function showPeekModal(count, cards){
  if(!cards || !cards.length){ alert('No cards to show'); return; }
  let orderedCards = cards.slice();

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';

  function rebuildGrid(){
    overlay.innerHTML = '';

    const h = document.createElement('h3');
    h.textContent = `Top ${count} Cards \u2014 drag to reorder (left = top of deck)`;
    overlay.appendChild(h);

    const grid = document.createElement('div');
    grid.className = 'modal-grid';

    orderedCards.forEach((card, displayIdx) => {
      const mc = document.createElement('div');
      mc.className = 'modal-card';
      mc.draggable = true;
      mc.dataset.idx = displayIdx;

      const handle = document.createElement('div');
      handle.className = 'drag-handle';
      handle.textContent = '\u2630';
      mc.appendChild(handle);

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

      const btns = document.createElement('div');
      btns.className = 'mc-actions';
      const deckIdx = card.deck_index;

      const mkBtn = (label, subType) => {
        const btn = document.createElement('button');
        btn.textContent = label;
        btn.addEventListener('click', ev => {
          ev.stopPropagation();
          sendAction({type:'peek_deck', count, sub_action:{type:subType, card_index:deckIdx}});
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
    bulk.appendChild(mkBulk('\u2b06 All to Top (in order)', 'all_to_top'));
    bulk.appendChild(mkBulk('\u2b07 All to Bottom (in order)', 'all_to_bottom'));
    bulk.appendChild(mkBulk('\ud83d\uddd1 Archive All', 'all_to_archive'));
    overlay.appendChild(bulk);

    const close = document.createElement('button');
    close.className = 'modal-close';
    close.textContent = 'Close';
    close.addEventListener('click', ()=> overlay.remove());
    overlay.appendChild(close);
  }

  rebuildGrid();
  overlay.addEventListener('click', ev=>{ if(ev.target === overlay) overlay.remove(); });
  modalContainer.appendChild(overlay);
}

/* ════════════════════ SPECIAL DAMAGE / HEAL MODAL ════════════════════ */
/**
 * Show a modal to deal special damage or heal a holomen.
 * @param {string} targetPlayer - 'self' or 'opponent'
 * @param {string} zone - 'centre', 'collabo', or 'back'
 * @param {number} cardIndex - index in the zone
 * @param {object} card - card data with card_name, hp, damage
 */
export function showAdjustHpModal(targetPlayer, zone, cardIndex, card){
  document.querySelectorAll('.adjust-hp-overlay').forEach(e => e.remove());

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay adjust-hp-overlay';

  const h = document.createElement('h3');
  h.style.color = '#f88';
  h.textContent = `⚔ Special Damage/Heal: ${card.card_name}`;
  overlay.appendChild(h);

  const info = document.createElement('div');
  info.style.cssText = 'font-size:13px;color:#ccc;margin-bottom:8px;text-align:center';
  const curHp = (card.hp || 0) - (card.damage || 0);
  info.textContent = `Current: ${curHp} / ${card.hp}  (damage: ${card.damage || 0})  [${zone}]`;
  overlay.appendChild(info);

  const preview = document.createElement('div');
  preview.style.cssText = 'font-size:14px;color:#fff;margin-bottom:12px;text-align:center;font-weight:bold';
  overlay.appendChild(preview);

  let pendingDelta = 0;

  function updatePreview(){
    const newDmg = Math.max(0, (card.damage || 0) + pendingDelta);
    const newHp = (card.hp || 0) - newDmg;
    if(pendingDelta > 0){
      preview.textContent = `Deal ${pendingDelta} damage → HP becomes ${newHp}/${card.hp}`;
      preview.style.color = '#f66';
    } else if(pendingDelta < 0){
      preview.textContent = `Heal ${Math.abs(pendingDelta)} → HP becomes ${newHp}/${card.hp}`;
      preview.style.color = '#6f6';
    } else {
      preview.textContent = '';
    }
  }

  // Damage buttons
  const dmgLabel = document.createElement('div');
  dmgLabel.style.cssText = 'font-size:11px;color:#f88;margin-bottom:4px;text-align:center';
  dmgLabel.textContent = '— Deal Damage —';
  overlay.appendChild(dmgLabel);

  const dmgRow = document.createElement('div');
  dmgRow.style.cssText = 'display:flex;gap:6px;justify-content:center;margin-bottom:10px;flex-wrap:wrap';
  [10, 20, 30, 40, 50, 60].forEach(v => {
    const btn = document.createElement('button');
    btn.className = 'modal-close';
    btn.style.cssText = 'background:#8b2020;padding:6px 14px;font-size:13px;min-width:50px';
    btn.textContent = `+${v}`;
    btn.addEventListener('click', () => { pendingDelta = v; updatePreview(); });
    dmgRow.appendChild(btn);
  });
  overlay.appendChild(dmgRow);

  // Heal buttons
  const healLabel = document.createElement('div');
  healLabel.style.cssText = 'font-size:11px;color:#6f6;margin-bottom:4px;text-align:center';
  healLabel.textContent = '— Heal —';
  overlay.appendChild(healLabel);

  const healRow = document.createElement('div');
  healRow.style.cssText = 'display:flex;gap:6px;justify-content:center;margin-bottom:10px;flex-wrap:wrap';
  [10, 20, 30, 40, 50, 60].forEach(v => {
    const btn = document.createElement('button');
    btn.className = 'modal-close';
    btn.style.cssText = 'background:#1a6b1a;padding:6px 14px;font-size:13px;min-width:50px';
    btn.textContent = `-${v}`;
    btn.addEventListener('click', () => { pendingDelta = -v; updatePreview(); });
    healRow.appendChild(btn);
  });
  overlay.appendChild(healRow);

  // Custom input
  const customRow = document.createElement('div');
  customRow.style.cssText = 'display:flex;gap:6px;justify-content:center;align-items:center;margin-bottom:14px';
  const customLabel = document.createElement('span');
  customLabel.style.cssText = 'color:#aaa;font-size:12px';
  customLabel.textContent = 'Custom:';
  customRow.appendChild(customLabel);
  const customInput = document.createElement('input');
  customInput.type = 'number';
  customInput.style.cssText = 'width:70px;padding:4px 8px;border-radius:4px;border:1px solid #555;background:#1a1a2e;color:#fff;font-size:13px;text-align:center';
  customInput.placeholder = '±N';
  customInput.addEventListener('input', () => {
    const v = parseInt(customInput.value);
    if(!isNaN(v)){ pendingDelta = v; updatePreview(); }
  });
  customRow.appendChild(customInput);
  overlay.appendChild(customRow);

  // Action buttons
  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex;gap:10px;justify-content:center';

  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'modal-close';
  confirmBtn.style.background = '#2d5bff';
  confirmBtn.textContent = 'Apply';
  confirmBtn.addEventListener('click', () => {
    if(pendingDelta === 0) return;
    overlay.remove();
    sendAction({
      type: 'adjust_hp',
      target_player: targetPlayer,
      zone: zone,
      card_index: cardIndex,
      delta: pendingDelta,
    });
  });
  btnRow.appendChild(confirmBtn);

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'modal-close';
  cancelBtn.textContent = 'Cancel';
  cancelBtn.addEventListener('click', () => overlay.remove());
  btnRow.appendChild(cancelBtn);

  overlay.appendChild(btnRow);
  overlay.addEventListener('click', ev => { if(ev.target === overlay) overlay.remove(); });
  modalContainer.appendChild(overlay);
}
