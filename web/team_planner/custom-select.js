/* Native selects retain form values; accessible custom listboxes provide the UI. */
(() => {
 let opened=null,serial=0;
 const widgets=new WeakMap();
 function close(focus=false){
  if(!opened)return;
  const w=opened;opened=null;w.menu.remove();w.button.setAttribute('aria-expanded','false');
  if(focus&&w.button.isConnected)w.button.focus();
 }
 function sync(w){
  const text=w.select.selectedOptions[0]?.textContent||'请选择';
  if(w.label.textContent!==text)w.label.textContent=text;
  w.button.disabled=w.select.disabled;
 }
 function open(w){
  if(opened===w){close();return}close();sync(w);opened=w;
  w.menu=document.createElement('div');w.menu.className='select-menu';w.menu.id=w.id;w.menu.setAttribute('role','listbox');
  w.menu.setAttribute('aria-label',w.button.getAttribute('aria-label'));
  const buttons=[...w.select.options].map((option,index)=>{
   const button=document.createElement('button');button.type='button';button.className='select-option';button.textContent=option.textContent;
   button.setAttribute('role','option');button.setAttribute('aria-selected',String(option.selected));button.disabled=option.disabled;
   button.onclick=e=>{e.preventDefault();e.stopPropagation();w.select.selectedIndex=index;sync(w);close(true);w.select.dispatchEvent(new Event('change',{bubbles:true}));
    // Some views replace the edited card after change.
    queueMicrotask(()=>{if(!w.button.isConnected){const field=w.select.dataset.field,name=w.select.closest('[data-name]')?.dataset.name;const next=[...document.querySelectorAll('select')].find(s=>s.dataset.field===field&&s.closest('[data-name]')?.dataset.name===name);if(next)widgets.get(next)?.button.focus()}});
   };w.menu.append(button);return button;
  });
  (w.button.closest('dialog')||document.body).append(w.menu);w.button.setAttribute('aria-expanded','true');
  const rect=w.button.getBoundingClientRect(),width=Math.min(Math.max(rect.width,180),innerWidth-24);
  w.menu.style.width=width+'px';w.menu.style.left=Math.max(12,Math.min(rect.left,innerWidth-width-12))+'px';
  const height=Math.min(w.menu.scrollHeight,280),below=innerHeight-rect.bottom-12;
  w.menu.style.top=(below>=height?rect.bottom+6:Math.max(12,rect.top-height-6))+'px';
  w.menu.style.maxHeight=Math.min(280,innerHeight-24)+'px';
  const selected=buttons.find(b=>b.getAttribute('aria-selected')==='true'&&!b.disabled)||buttons.find(b=>!b.disabled);
  selected?.focus({preventScroll:true});if(selected)w.menu.scrollTop=Math.max(0,selected.offsetTop-w.menu.clientHeight/2);
  w.menu.onkeydown=e=>{
   const items=buttons.filter(b=>!b.disabled),i=items.indexOf(document.activeElement);
   if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();items[e.key==='Home'?0:e.key==='End'?items.length-1:(i+(e.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus()}
   else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close(true)}
   else if(e.key==='Tab')close();
   else if(e.key.length===1){const found=items.find(b=>b.textContent.toLowerCase().startsWith(e.key.toLowerCase()));found?.focus()}
  };
 }
 function enhance(){
  if(opened&&!opened.button.isConnected)close();
  document.querySelectorAll('select').forEach(select=>{
   let w=widgets.get(select);
   if(w){sync(w);return}
   const wrapper=document.createElement('span');wrapper.className='custom-select';select.before(wrapper);wrapper.append(select);
   select.classList.add('custom-select-native');select.tabIndex=-1;select.setAttribute('aria-hidden','true');
   const button=document.createElement('button');button.type='button';button.className='select-trigger';button.setAttribute('role','combobox');button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-expanded','false');
   button.setAttribute('aria-label',select.getAttribute('aria-label')||select.closest('label')?.firstChild?.textContent?.trim()||'选择选项');
   const label=document.createElement('span');label.className='select-value';button.append(label);
   const arrow=document.createElement('span');arrow.className='select-chevron';arrow.innerHTML='<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m4 6 4 4 4-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';arrow.setAttribute('aria-hidden','true');button.append(arrow);wrapper.append(button);
   w={select,button,label,id:'custom-listbox-'+(++serial)};widgets.set(select,w);button.setAttribute('aria-controls',w.id);
   button.onclick=e=>{e.preventDefault();open(w)};
   button.onkeydown=e=>{if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();open(w)}};
   select.addEventListener('change',()=>sync(w));sync(w);
  });
 }
 document.addEventListener('pointerdown',e=>{if(opened&&!opened.menu.contains(e.target)&&!opened.button.contains(e.target))close()});
 window.addEventListener('resize',()=>close());
 document.addEventListener('scroll',e=>{if(opened&&!opened.menu.contains(e.target)){const r=opened.button.getBoundingClientRect();opened.menu.style.top=Math.max(12,Math.min(r.bottom+6,innerHeight-opened.menu.offsetHeight-12))+'px'}},true);
 let queued=false;new MutationObserver(()=>{if(!queued){queued=true;queueMicrotask(()=>{queued=false;enhance()})}}).observe(document.body,{childList:true,subtree:true});
 enhance();
})();
