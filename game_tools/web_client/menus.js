/* ══════════════════════════════════════════════════════════════
   hOCG Web Client — Context Menus
   Right-click menus for hand cards and stage/field cards
   ══════════════════════════════════════════════════════════════ */
import {
  playerId, lastState, ctxMenu,
  sendAction, cardImgSrc,
} from './state.js';
import {
  showBloomPicker, showArtsPicker, showStackPopup,
  showOshiSkillActivation, playSupportCard, showZoom,
  buildSearchModalUI, openPeekModal,
  showAttachYellPicker, showSearchYellModal,
  showDeductLifePicker,
  showAdjustHpModal,
} from './modals.js';

/* ── Show / hide ── */
export function hideContextMenu(){ ctxMenu.style.display = 'none'; }

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
  const rect = ctxMenu.getBoundingClientRect();
  if(rect.right > window.innerWidth) ctxMenu.style.left = (x - rect.width)+'px';
  if(rect.bottom > window.innerHeight) ctxMenu.style.top = (y - rect.height)+'px';
}

/* ── Zone context menu (deck / archive / yell_deck) ── */
export function showZoneContextMenu(x, y, zname, cards){
  const items = [{type:'header', text:`${zname} (${cards.length})`}];

  if(zname === 'deck'){
    items.push({text:'Search Deck', action:()=>{
      buildSearchModalUI('Search Deck', 'deck', cards, [
        {label:'Hand', action:(card)=> sendAction({type:'move', from_zone:'deck', to_zone:'hand', card_number:card.card_number})},
        {label:'Archive', action:(card)=> sendAction({type:'move', from_zone:'deck', to_zone:'archive', card_number:card.card_number})},
      ]);
    }});
    items.push({text:'Shuffle Deck', action:()=> sendAction({type:'shuffle_deck'})});
    items.push({type:'sep'});
    items.push({text:'View Top 3', action:()=> openPeekModal(3)});
    items.push({text:'View Top 5', action:()=> openPeekModal(5)});
  }

  if(zname === 'archive'){
    items.push({text:'Search Archive', action:()=>{
      buildSearchModalUI('Search Archive', 'archive', cards, [
        {label:'Top', action:(card)=> sendAction({type:'move', from_zone:'archive', to_zone:'deck', card_number:card.card_number})},
        {label:'Hand', action:(card)=> sendAction({type:'move', from_zone:'archive', to_zone:'hand', card_number:card.card_number})},
        {label:'Y\u2191', action:(card)=> sendAction({type:'move', from_zone:'archive', to_zone:'yell_deck', card_number:card.card_number})},
      ]);
    }});
  }

  if(zname === 'yell_deck'){
    items.push({text:'Search Yell', action:()=> showSearchYellModal()});
    items.push({text:'Attach Yell', action:()=> showAttachYellPicker()});
    items.push({text:'Shuffle Yell', action:()=> sendAction({type:'shuffle_yell'})});
  }

  if(zname === 'life'){
    items.push({text:'Deduct Life', action:()=> showDeductLifePicker()});
  }

  showContextMenuAt(x, y, items);
}

/* ── Hand card context menu ── */
export function showHandContextMenu(x, y, idx, card){
  const isHolo = card.card_type && card.card_type.includes('\u30db\u30ed\u30e1\u30f3');
  const isDebut = card.bloom_level === 'Debut';
  const items = [
    {type:'header', text:`${card.card_name} (${card.bloom_level||card.card_type})`},
  ];

  /* Mulligan phase */
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

  /* Setup (placement) phase */
  if(lastState && lastState.game_state === 'setup'){
    const mySetup = lastState.setup_state?.[playerId];
    const remaining = (mySetup?.returning || 0) - (mySetup?.returned || 0);
    if(remaining > 0){
      items.push({text:`Return to Deck (${remaining} left)`, action:()=>
        sendAction({type:'setup_return_card', card_number:card.card_number})});
    } else {
      if(isHolo && isDebut){
        items.push({text:'\u2192 Centre (Setup)', action:()=>
          sendAction({type:'setup_place', zone:'centre', card_number:card.card_number})});
        items.push({text:'\u2192 Back (Setup)', action:()=>
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

  const isSupport = card.card_type && card.card_type.includes('\u30b5\u30dd\u30fc\u30c8');

  if(isHolo){
    items.push({text:'\u2192 Centre', action:()=> sendAction({type:'move_to_centre', from_zone:'hand', card_number:card.card_number})});
    items.push({text:'\u2192 Back', action:()=> sendAction({type:'play_card', card_number:card.card_number, zone:'back', face_up:true})});
  }
  if(isSupport){
    items.push({text:'\u26a1 Use Support', action:()=> playSupportCard(card.card_number)});
  }
  items.push({type:'sep'});
  items.push({text:'\u2192 Archive', action:()=> sendAction({type:'move', from_zone:'hand', to_zone:'archive', card_number:card.card_number})});
  items.push({text:'\u2192 Deck Top', action:()=> sendAction({type:'move', from_zone:'hand', to_zone:'deck', card_number:card.card_number})});
  items.push({text:'\u2192 Deck Bottom', action:()=> sendAction({type:'move', from_zone:'hand', to_zone:'deck', card_number:card.card_number, position:'bottom'})});
  items.push({text:'\u2192 Holo Power', action:()=> sendAction({type:'move', from_zone:'hand', to_zone:'holo_power', card_number:card.card_number})});
  items.push({type:'sep'});
  items.push({text:'View Card', action:()=> showZoom(cardImgSrc(card))});
  showContextMenuAt(x, y, items);
}

/* ── Stage/field card context menu ── */
export function showCardContextMenu(x, y, zname, idx, card){
  const items = [
    {type:'header', text:`${card.card_name} [${zname}]`},
  ];

  /* Setup phase */
  if(lastState && lastState.game_state === 'setup'){
    if(['centre','back'].includes(zname)){
      items.push({text:'\u2192 Hand (undo)', action:()=>
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
    items.push({text:'Collabo (deck\u2192HP)', action:()=> sendAction({type:'collabo', from_zone:'back', card_index:idx})});
    items.push({text:'Force Collabo', action:()=> sendAction({type:'force_collabo', from_zone:'back', card_index:idx})});
    items.push({text:'\u2192 Centre', action:()=> sendAction({type:'move_to_centre', from_zone:'back', card_number:card.card_number, card_index:idx})});
    items.push({type:'sep'});
  }
  if(zname === 'centre' || zname === 'collabo'){
    items.push({text:'Play Arts', action:()=> showArtsPicker(zname, idx, card)});
    items.push({text:'\u2192 Back', action:()=> sendAction({type:'move', from_zone:zname, to_zone:'back', card_number:card.card_number})});
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
    items.push({text:'\u2192 Archive (all)', action:()=> sendAction({type:'archive_card', zone:zname, card_index:idx, mode:'all'})});
    items.push({text:'\u2192 Archive (card only)', action:()=> sendAction({type:'archive_card', zone:zname, card_index:idx, mode:'card_only'})});
  }

  if(zname === 'archive'){
    items.push({text:'\u2192 Hand', action:()=> sendAction({type:'move', from_zone:'archive', to_zone:'hand', card_number:card.card_number})});
    items.push({text:'\u2192 Deck Top', action:()=> sendAction({type:'move', from_zone:'archive', to_zone:'deck', card_number:card.card_number})});
    items.push({text:'\u2192 Yell Deck Top', action:()=> sendAction({type:'move', from_zone:'archive', to_zone:'yell_deck', card_number:card.card_number})});
  }

  if(zname === 'holo_power'){
    items.push({text:'\u2192 Archive', action:()=> sendAction({type:'move', from_zone:'holo_power', to_zone:'archive', card_number:card.card_number})});
  }

  /* Oshi skill actions */
  if(zname === 'oshi'){
    const allowed = lastState ? (lastState.allowed_actions || []) : [];
    const oshiState = lastState ? (lastState.oshi_skill_state || {}) : {};
    const hpCount = lastState ? (lastState.players[playerId]?.zones?.holo_power || []).length : 0;

    if(allowed.includes('use_oshi_skill')){
      items.push({text:'\u26a1 Use Oshi Skill', action:()=> showOshiSkillActivation('oshi_skill')});
    }
    if(allowed.includes('use_sp_oshi_skill')){
      items.push({text:'\ud83c\udf1f Use SP Oshi Skill', action:()=> showOshiSkillActivation('sp_oshi_skill')});
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

  if(isStage && card.hp > 0){
    items.push({type:'sep'});
    items.push({text:'\u2764 Special Damage/Heal (self)', action:()=> showAdjustHpModal('self', zname, idx, card)});
  }

  items.push({text:'View Card', action:()=> showZoom(cardImgSrc(card))});
  showContextMenuAt(x, y, items);
}

/* ════════════════════ OPPONENT CARD CONTEXT MENU ════════════════════ */
export function showOppCardContextMenu(x, y, zname, idx, card){
  const items = [
    {type:'header', text:`${card.card_name} [opp ${zname}]`},
  ];

  const isStage = ['centre','collabo','back'].includes(zname);

  if(isStage && card.hp > 0){
    items.push({text:'\u2694 Special Damage/Heal (opponent)', action:()=> showAdjustHpModal('opponent', zname, idx, card)});
  }

  items.push({text:'View Card', action:()=> showZoom(cardImgSrc(card))});
  showContextMenuAt(x, y, items);
}
