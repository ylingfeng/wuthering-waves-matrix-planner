let storageMode='browser',serverRevision=null,syncTimer,syncPending=false,syncFlight=null;
document.querySelector('base').href=new URL('.',document.baseURI).href;
let editingRole=null;
let state, dirty=false, result=null, draft=null, activeTab='characters', toastTimer, configurationVersion=0;
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const image=name=>'./portraits/'+encodeURIComponent(name)+'.png';
const elements=['冷凝','热熔','导电','气动','衍射','湮灭'];
function elementTags(character,team=null){
 if(!character)return '';
 const selected=character.name==='漂泊者'?(team?.rover_attribute?[team.rover_attribute]:character.attributes):[character.element];
 const values=selected.filter(e=>elements.includes(e));
 return values.length?`<div class="element-tags" role="group" aria-label="伤害属性">${values.map(e=>`<span class="element-tag element-${e}">${e}</span>`).join('')}</div>`:'';
}
const effective=c=>(c.released&&(c.available||$('#planning-scope').value==='all'))?(c.weekly??c.base):0;
const releaseVersions=[...Array.from({length:5},(_,i)=>'V1.'+i),...Array.from({length:9},(_,i)=>'V2.'+i),...Array.from({length:8},(_,i)=>'V3.'+i)];
const recency=c=>c?.released&&!c.healer&&c.roles.length===1&&c.roles[0]==='主C'&&releaseVersions.includes(c.release_version)?1+releaseVersions.indexOf(c.release_version)*0.002:1;
const effectiveWeight=c=>c?Number(((($('#planning-scope').value==='all'&&!c.available)?1:c.weight*((c.chain??0)+1))*recency(c)).toFixed(6)):1;
const product=t=>t.members.reduce((v,n)=>v*effectiveWeight(state.characters.find(c=>c.name===n)),1);
const sourceMultiplier=t=>1;
const safeUrl=url=>{try{let u=new URL(url);return ['https:','http:'].includes(u.protocol)?u.href:'#'}catch{return '#'}};
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,5000)}
async function api(path,data){if(path==='/api/state')return loadConfiguration();if(path==='/api/save')return LocalPlanner.save(data);if(path==='/api/optimize'){return browserPlan(state,data)}throw Error('未知操作')}
function invalidateResult(){
 configurationVersion++;
 if(!result)return;
 result.stale=true;$('#result-count').textContent='待重算';$('#result-body').classList.add('stale');
 const heading=$('#result-body .result-heading strong');if(heading)heading.textContent='上次计算 '+result.count+' 队';
}
function markDirty(){dirty=true;$('#save-status').textContent='有未保存的修改';$('#save-status').style.color='#b28944';summary();invalidateResult();persistLocally();syncTeamCards();}
function summary(){let owned=state.characters.filter(c=>c.released&&(c.available||$('#planning-scope').value==='all')),total=owned.reduce((s,c)=>s+effective(c),0);$('#summary').innerHTML=`<div><strong>${owned.length}<small>${$('#planning-scope').value==='all'?'参与模拟':'可用角色'} / ${state.characters.length}</small></strong></div><div><strong>${total}<small>本周总计体力</small></strong></div><div><strong>${Math.floor(total/3)}<small>理论队数上限</small></strong></div>`;$('#character-count').textContent=state.characters.length;$('#team-count').textContent=state.teams.length}
function roster(){let query=$('#character-search').value.trim(),filter=$('#character-filter').value,element=$('#character-element').value;let chars=state.characters.filter(c=>c.name.includes(query)&&(element==='all'||(c.name==='漂泊者'?c.attributes.includes(element):c.element===element))&&(filter==='all'||filter==='owned'&&c.available||filter==='unowned'&&!c.available||filter==='healer'&&c.healer||filter==='weekly'&&c.weekly!==null));$('#character-grid').innerHTML=chars.map(c=>`<article class="character-card ${c.available?'':'unowned'}" data-name="${esc(c.name)}"><div class="portrait"><img src="${image(c.name)}" alt="${esc(c.name)}" loading="lazy">${c.weekly!==null?'<span class="weekly-badge">本周已调整</span>':''}<label class="availability"><input type="checkbox" data-field="available" ${c.released?'':'disabled'} ${c.available?'checked':''}>可用</label></div><div class="character-info"><div class="character-name">${esc(c.name)} <small class="rarity rarity-${c.rarity}">${c.rarity?c.rarity+'★':''}</small></div>${elementTags(c)}<div class="role-tags role-select"><button type="button" class="role-select-trigger" data-edit-roles="${esc(c.name)}" aria-label="${esc(c.name)}定位" aria-expanded="${editingRole===c.name}">${c.roles.filter(r=>r!=='待确认').map(r=>`<span class="role-tag role-${["主C","辅助","奶妈"].indexOf(r)}">${r}</span>`).join("")||'<span class="hint">选择定位</span>'}<span class="role-arrow" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none"><path d="m4 6 4 4 4-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg></span></button>${editingRole===c.name?`<div class="role-options" role="group" aria-label="多选定位">${["主C","辅助","奶妈"].map((r,i)=>`<button type="button" class="role-option" data-role="${r}" role="checkbox" aria-checked="${c.roles.includes(r)}"><span class="role-check">${c.roles.includes(r)?'✓':''}</span><span class="role-tag role-${i}">${r}</span></button>`).join("")}</div>`:''}</div><div class="stamina-inputs"><label>基础体力<input type="number" data-field="base" min="0" max="99" step="1" value="${c.base}" aria-label="${esc(c.name)}基础体力"></label><label>本周体力<input type="number" data-field="weekly" min="0" max="99" step="1" value="${c.weekly??c.base}" aria-label="${esc(c.name)}本周体力"></label></div><label class="character-weight">链度<select data-field="chain" aria-label="${esc(c.name)}链度">${Array.from({length:7},(_,i)=>`<option value="${i}" ${(c.chain??0)===i?"selected":""}>${i} 链</option>`).join("")}</select></label><div class="character-foot">基础分 ${recency(c).toFixed(3)} · 链度系数 ${(c.chain??0)+1}</div><label class="character-weight">用户练度<input type="number" data-field="weight" min="1" max="100" step="0.1" value="${c.weight}" aria-label="${esc(c.name)}加权"></label><div class="character-foot">${!c.released?'未实装 · 全角色模式也排除':c.available?'本周可用 '+effective(c)+' 次':'未拥有 · 不参与我的配队'}${c.name==='漂泊者'?' · 多属性共用体力':''}${recency(c)>1?' · 主C通用加成 +'+((recency(c)-1)*100).toFixed(1)+'%':''}</div><button data-view-teams="${esc(c.name)}">查看配队</button></div></article>`).join('')||'<div class="empty">没有符合筛选的角色。</div>'}
function orderedMembers(team){
 const rank=(name,index)=>{
  const c=state.characters.find(c=>c.name===name);
  if(c?.healer)return 2;
  if(team.assigned_roles?.[index])return {'主C':0,'辅助':1,'奶妈':2}[team.assigned_roles[index]]??1;
  if(name==='漂泊者'&&team.rover_attribute)return team.rover_attribute==='湮灭'?0:1;
  return c?.roles.includes('主C')?0:1;
 };
 return team.members.map((name,index)=>({name,index,rank:rank(name,index)})).sort((a,b)=>a.rank-b.rank||a.index-b.index).map(x=>x.name);
}
const memberName=(name,team)=>name==='漂泊者'&&team.rover_attribute?name+'·'+team.rover_attribute:name;
const memberImage=(name,team)=>image(memberName(name,team));
function teamElement(team){
 const name=orderedMembers(team)[0];
 return name==='漂泊者'?team.rover_attribute:state.characters.find(c=>c.name===name)?.element||'';
}
function matchesTeamSearch(team,query){
 const words=query.trim().split(/\s+/u).filter(Boolean);
 const names=team.members.map(n=>memberName(n,team));
 return words.every(word=>names.some(n=>n.includes(word))||(words.length===1&&team.note.includes(word)));
}
function portraits(team){return `<div class="team-portraits">${orderedMembers(team).map(n=>{const name=memberName(n,team);return `<div class="member"><div class="member-image"><img src="${memberImage(n,team)}" alt="${esc(name)}" loading="lazy"></div><span class="member-name" title="${esc(name)}">${esc(name)}</span>${elementTags(state.characters.find(c=>c.name===n),team)}</div>`}).join('')}</div>`}

function missing(t){return t.members.filter(n=>!state.characters.find(c=>c.name===n&&c.available))}
function proofLabel(p){
 return p.kind==='video'?(p.matrix?'B站·矩阵视频 2.5':'B站·非矩阵视频'):p.kind==='workshop'?(p.matrix?'工坊·矩阵 2.0':'工坊·未注明矩阵'):p.kind==='wiki'?'Wiki·明确配队 1.5':'攻略·一般配队参考';
}
const evidenceTypes=[
 {key:'video-matrix',label:'B站·矩阵视频',score:2.5,tone:'video'},
 {key:'workshop-matrix',label:'工坊·矩阵',score:2,tone:'workshop'},
 {key:'wiki',label:'Wiki·明确配队',score:1.5,tone:'wiki'},
 {key:'video-general',label:'B站·非矩阵视频',tone:'reference'},
 {key:'workshop-general',label:'工坊·未注明矩阵',tone:'reference'},
 {key:'guide',label:'攻略·一般配队参考',tone:'reference'},
 {key:'unverified',label:'未核实来源 / 推导',tone:'reference'},
 {key:'custom',label:'用户自定义',tone:'reference'}
];
const selectedEvidence=new Set();
const proofKey=p=>p.kind==='video'?(p.matrix?'video-matrix':'video-general'):p.kind==='workshop'?(p.matrix?'workshop-matrix':'workshop-general'):p.kind==='wiki'?'wiki':'guide';
function evidenceKinds(t){const keys=new Set((t.source_audit?.matched||[]).map(proofKey));if(!keys.size)keys.add(t.origin==='manual'?'custom':'unverified');return evidenceTypes.filter(x=>keys.has(x.key))}
function evidenceLabels(t){return evidenceKinds(t).map(x=>x.label+(x.score?' '+x.score.toFixed(1):''))}
function evidenceLabel(t){return evidenceLabels(t).join(' + ')}
function evidenceTags(t){return '<div class="evidence-tags">'+evidenceKinds(t).map(x=>`<span class="tag evidence-${x.tone}">${esc(x.label)}${x.score?` <b>${x.score.toFixed(1)}</b>`:''}</span>`).join('')+'</div>'}
function evidenceFilters(){
 const counts=Object.fromEntries(evidenceTypes.map(x=>[x.key,0]));state.teams.forEach(t=>evidenceKinds(t).forEach(x=>counts[x.key]++));
 $('#evidence-filter').innerHTML=`<div class="evidence-filter-heading"><strong>证据来源</strong><span>可多选 · 满足任一标签 · 数量按全库统计</span><button type="button" data-evidence="all" aria-pressed="${!selectedEvidence.size}">全部 ${state.teams.length}</button></div><div class="evidence-filter-options">${evidenceTypes.filter(x=>x.key!=='custom'||counts.custom).map(x=>`<button type="button" class="evidence-chip evidence-${x.tone}" data-evidence="${x.key}" aria-pressed="${selectedEvidence.has(x.key)}"><span>${x.label}</span>${x.score?`<b>${x.score.toFixed(1)}</b>`:''}<span class="evidence-count">${counts[x.key]}</span></button>`).join('')}</div>`;
}
function sourceLinkLabel(t,url,index){
 const proof=(t.source_audit?.matched||[]).find(p=>p.url===url);
 if(proof){const kind=[...new Set(t.source_audit.matched.filter(p=>p.url===url).map(proofLabel))].join(' + ');return kind+'：'+(proof.quote?.split('\n')[0]||'配队证据')}
 return '参考链接 '+(index+1)+'（未核实对应配队）';
}
function requiredBadge(t){return t.locked?'<div class="required-marker"><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M7 3h6l-1 5 3 3v2H5v-2l3-3-1-5ZM10 13v5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/></svg><span>必须选入</span></div>':''}
function teamScore(t){return Number((product(t)*t.priority*(t.user_weight??1)*sourceMultiplier(t)).toFixed(4))}
function sameTeam(a,b){return [...a.members].sort().join('|')===[...b.members].sort().join('|')&&(a.rover_attribute||'')===(b.rover_attribute||'')}
function findTeam(id){
 const saved=state.teams.find(t=>t.id===id);if(saved)return saved;
 if(result?.removed_ids?.includes(id))return;
 const generated=result?.selected.find(t=>t.id===id&&/^(fill-|solo-)/.test(t.id));
 return generated&&(state.teams.find(t=>sameTeam(t,generated))||generated);
}
function forgetResultTeam(id){
 if(result)result.removed_ids=[...new Set([...(result.removed_ids||[]),...result.selected.filter(t=>findTeam(t.id)?.id===id).map(t=>t.id)])];
}

function teamCard(t,title=''){
 const name=t.members.map(n=>memberName(n,t)).join(' / '),axis=t.axes.find(a=>a.id===t.selected_axis);
 return `<article class="team-card ${t.enabled?'':'disabled'} ${t.locked?'is-required':''}" data-id="${esc(t.id)}" data-title="${esc(title)}">
  ${title?`<h3 class="team-card-title">${esc(title)}</h3>`:''}${requiredBadge(t)}
  <div class="team-top">${evidenceTags(t)}<label class="check"><input type="checkbox" data-enable aria-label="${esc(name)}参与计算" ${t.enabled?'checked':''}>参与计算</label></div>
  ${portraits(t)}<div class="team-meta">${elements.includes(teamElement(t))?`<div class="team-main-element">主属性 <span class="element-tag element-${teamElement(t)}">${teamElement(t)}</span></div>`:''}${!t.enabled&&t.source_audit?.default_status_reason?esc(t.source_audit.default_status_reason)+' · ':''}${missing(t).length?'缺少 '+esc(missing(t).join('、')):'角色已齐全'}${axis?' · '+esc(axis.name):''}</div>
  <div class="team-adjustments"><label class="team-user-weight">用户权重<input type="number" data-team-weight min="0" max="1000" step="any" required value="${t.user_weight??1}" aria-label="${esc(name)}用户权重"></label><label class="required-switch"><input type="checkbox" role="switch" data-lock aria-label="${esc(name)}必须选入" ${t.locked?'checked':''}><span>必须选入</span></label></div>
  <div class="team-bottom"><div class="team-score"><small>基础分 ${t.priority} · ${t.axes.length} 套轴</small><span>队伍得分 <strong data-team-score>${teamScore(t)}</strong></span></div><button data-edit="${esc(t.id)}">编辑队伍 / 轴</button></div>
 </article>`;
}
function syncTeamCards(){
 document.querySelectorAll('.team-card[data-id]').forEach(card=>{
  const t=findTeam(card.dataset.id);if(!t){card.remove();return}
  const template=document.createElement('template');template.innerHTML=teamCard(t,card.dataset.title);
  const updated=template.content.firstElementChild;
  card.className=updated.className;card.dataset.id=t.id;
  // Keep live controls in place so committing a number does not cancel the
  // pointer click or keyboard focus that caused the input to lose focus.
  for(const selector of ['.required-marker','.evidence-tags','.team-portraits','.team-meta','.team-score']){
   const current=card.querySelector(selector),next=updated.querySelector(selector);
   if(!next)current?.remove();
   else if(!current)card.insertBefore(next,card.querySelector('.team-top'));
   else if(current.outerHTML!==next.outerHTML)current.replaceWith(next);
  }
  for(const selector of ['[data-team-weight]','[data-enable]','[data-lock]','[data-edit]']){
   const current=card.querySelector(selector),next=updated.querySelector(selector);
   for(const attr of [...current.attributes])if(!next.hasAttribute(attr.name))current.removeAttribute(attr.name);
   for(const attr of next.attributes)current.setAttribute(attr.name,attr.value);
   if(current.type==='checkbox')current.checked=next.checked;
   else if(current.type==='number')current.value=next.value;
  }
 });
 document.querySelectorAll('#result-body .team-card').forEach((card,i)=>{
  card.dataset.title='配队'+(i+1);card.querySelector('.team-card-title').textContent=card.dataset.title;
 });
}

function teams(){
 evidenceFilters();
 const q=$('#team-search').value.trim(),filter=$('#team-filter').value,element=$('#team-element').value;
 const list=state.teams.filter(t=>(element==='all'||teamElement(t)===element)&&(!selectedEvidence.size||evidenceKinds(t).some(x=>selectedEvidence.has(x.key)))&&matchesTeamSearch(t,q)&&(filter==='all'||filter==='available'&&!missing(t).length||filter==='unowned'&&missing(t).length>0||filter==='locked'&&t.locked||filter==='disabled'&&!t.enabled)).sort((a,b)=>Number(b.enabled)-Number(a.enabled));
 $('#team-grid').innerHTML=list.map(t=>teamCard(t)).join('')||'<div class="empty">暂无符合条件的队伍，可以新建三人组合。</div>';
}

const routeNames=['characters','teams','results'];
function routeTab(){return routeNames.find(n=>location.pathname.replace(/\/$/,'').endsWith('/'+n))||routeNames.find(n=>location.hash==='#'+n)||'characters'}
function tab(name,navigate=true){if(!routeNames.includes(name))name='characters';activeTab=name;
 if(navigate){const url=location.protocol==='file:'?location.href.split('#')[0]+'#'+name:new URL(name+'/',document.baseURI).pathname;if(location.href!==new URL(url,location.href).href)history.pushState({tab:name},'',url)}
document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!==name);document.querySelectorAll('nav button').forEach(el=>el.classList.toggle('active',el.dataset.tab===name));if(name==='teams')teams();if(name==='characters')roster();if(name==='results')renderResult()}
async function save(){persistLocally();await syncConfiguration();return state}
function renderResult(){if(!result)return;const stale=!!result.stale;$('#result-count').textContent=stale?'待重算':result.count;let remainder=state.characters.filter(c=>(c.available||result.all_characters)&&result.remaining[c.name]>0);$('#result-body').className=stale?'stale':'';$('#result-body').innerHTML=`<div class="result-heading"><div><strong>${stale?'上次计算 ':''}${result.count} 队</strong><p>${result.all_characters?'全角色模拟':'我的角色'} · 候选队伍 ${result.recommended_count} 队＋主辅奶兜底 ${result.fallback_count} 队＋丹瑾单人补队 ${result.solo_count??0} 队；得分从低到高。</p></div><div class="hint">${result.eligible} 种可用候选 · 使用 ${result.count*3} / ${result.total_stamina} 点体力<br>队伍得分总和 ${result.total_score} · 体力不会实际扣除。</div></div><div class="result-grid">${result.selected.map(t=>findTeam(t.id)).filter(Boolean).map((t,i)=>teamCard(t,'配队'+(i+1))).join('')||'<div class="empty">没有满足条件的队伍。请检查角色可用状态、体力和候选开关。</div>'}</div><div class="remaining"><h3>剩余体力</h3><p class="hint">这些角色仍有体力；当前已收录候选未能覆盖，不代表没有可用配队。可继续补充低优先级搭档或调整必选队。</p><div class="remaining-list">${remainder.map(c=>`<span>${esc(c.name)} <b>×${result.remaining[c.name]}</b></span>`).join('')||'已全部用完'}</div></div>`}
function axisFields(){let axis=draft.axes.find(a=>a.id===draft.selected_axis);$('#axis-select').innerHTML=draft.axes.length?draft.axes.map(a=>`<option value="${esc(a.id)}">${esc(a.name)}${a.author?' · '+esc(a.author):''}</option>`).join(''):'<option value="">尚无输出轴</option>';$('#axis-select').value=draft.selected_axis;$('#axis-fields').hidden=!axis;$('#axis-empty').hidden=!!axis;if(axis){$('#axis-name').value=axis.name;$('#axis-description').value=axis.description;$('#axis-source').href=safeUrl(axis.url);$('#axis-source').hidden=!axis.url}}
function refreshMembers(){
 const standard=PLANNER_SEED.teams.find(t=>[...t.members].sort().join('|')===[...draft.members].sort().join('|')&&t.rover_attribute===draft.rover_attribute);
 draft.priority=standard?.default_priority??1;
 draft.default_priority=draft.priority;
 draft.source_audit=standard?.source_audit;
 draft.sources=standard?.sources??[];
document.querySelectorAll('[data-member]').forEach(s=>{let n=s.value;let img=s.closest('.member-slot').querySelector('img');img.src=memberImage(n,draft);img.alt=memberName(n,draft);s.closest('.member-slot').querySelector('.member-element').innerHTML=elementTags(state.characters.find(c=>c.name===n),draft)});const roverIndex=draft.members.indexOf('漂泊者');$('#rover-row').hidden=roverIndex<0;
 const roverHost=roverIndex<0?$('#rover-parking'):document.querySelector('[data-slot="'+roverIndex+'"]');if($('#rover-row').parentElement!==roverHost)roverHost.append($('#rover-row'));
if(!draft.members.includes('漂泊者'))draft.rover_attribute='';$('#rover-attribute').value=draft.rover_attribute;$('#team-weight').textContent='队伍得分：'+draft.priority+'（基础分） × '+(draft.user_weight??1)+'（用户加权） × '+draft.members.map(n=>effectiveWeight(state.characters.find(c=>c.name===n))).join(' × ')+' = '+Number((draft.priority*(draft.user_weight??1)*sourceMultiplier(draft)*product(draft)).toFixed(6))}
function edit(id,initial=null){$('#rover-parking').append($('#rover-row'));let existing=initial||state.teams.find(t=>t.id===id)||result?.selected.find(t=>t.id===id);draft=existing?structuredClone(existing):{id:crypto.randomUUID(),members:state.characters.filter(c=>c.available).slice(0,3).map(c=>c.name),rover_attribute:'',enabled:true,locked:false,priority:1,user_weight:1,note:'',evidence:'自定义',origin:'manual',sources:[],axes:[],selected_axis:''};while(draft.members.length<3)draft.members.push(state.characters[draft.members.length].name);$('#editor-title').textContent=existing?'编辑队伍 · '+draft.members.map(n=>memberName(n,draft)).join(' / '):'新建三人队伍';$('#delete-team').hidden=!state.teams.some(t=>t.id===id);$('#editor-error').textContent='';let sorted=[...state.characters].sort((a,b)=>Number(b.available)-Number(a.available));$('#member-inputs').innerHTML=draft.members.map((n,i)=>`<div class="member-slot" data-slot="${i}"><label>角色 ${i+1}<img src="${image(n)}" alt="${esc(n)}"><select data-member="${i}" aria-label="角色${i+1}">${sorted.map(c=>`<option value="${esc(c.name)}" ${c.name===n?'selected':''}>${esc(c.name)}${c.available?'':'（未拥有）'}</option>`).join('')}</select></label><div class="member-element"></div></div>`).join('');$('#team-note').value=draft.note;$('#team-sources').innerHTML=(draft.sources||[]).map((url,i)=>`<a href="${esc(safeUrl(url))}" target="_blank" rel="noopener">${esc(sourceLinkLabel(draft,url,i))} ↗</a>`).join('');refreshMembers();axisFields();$('#source-audit-status').textContent=draft.source_audit?('固定证据分：'+draft.default_priority+'；'+draft.source_audit.video_status+'。'+(draft.source_audit.issue||draft.source_audit.default_status_reason||'')):'尚无来源核查记录';$('#editor').showModal()}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
$('#character-search').oninput=roster;$('#character-filter').onchange=roster;$('#character-element').onchange=roster;$('#team-search').oninput=teams;$('#team-filter').onchange=teams;$('#team-element').onchange=teams;
$('#character-grid').onchange=e=>{let field=e.target.dataset.field;if(!field)return;let card=e.target.closest('[data-name]'),c=state.characters.find(c=>c.name===card.dataset.name);let value=e.target.type==='checkbox'?e.target.checked:e.target.value===''&&field==='weekly'?null:Number(e.target.value);if(e.target.type==='number'&&(field==='base'&&e.target.value===''||value!==null&&((field==='weight'?!Number.isFinite(value):!Number.isInteger(value))||value<(field==='weight'?1:0)||value>(field==='weight'?100:field==='chain'?6:99)))){toast('链度须为0到6的整数；体力须为0到99的整数；用户练度须为1到100，可用小数');roster();return}if(field==='roles'){c.roles=e.target.value.split('|');c.healer=c.roles.includes('奶妈')}else{c[field]=value;if(field==='healer')c.roles=value?['奶妈']:['辅助']}markDirty();roster()};
function changeTeamCard(e){
 const input=e.target,card=input.closest('[data-id]');if(!card)return;
 let t=findTeam(card.dataset.id),retained=false;if(!t)return;
 const retain=()=>{if(!state.teams.some(x=>x.id===t.id)){t={...structuredClone(t),user_weight:t.user_weight??1,locked:!!t.locked,origin:'manual'};state.teams.push(t);retained=true}};
 if(input.hasAttribute('data-team-weight')){
  const value=input.valueAsNumber;
  if(!Number.isFinite(value)||value<0||value>1000){input.value=t.user_weight??1;toast('用户权重须为 0 到 1000，可用小数；默认值为 1');return}
  retain();t.user_weight=value;markDirty();if(retained)teams();
 }else if(input.hasAttribute('data-enable')){
  retain();t.enabled=input.checked;if(!t.enabled)t.locked=false;markDirty();teams();
 }else if(input.hasAttribute('data-lock')){
  retain();t.locked=input.checked;if(t.locked)t.enabled=true;markDirty();teams();
 }
}
$('#team-grid').onchange=changeTeamCard;
$('#result-body').onchange=changeTeamCard;
document.body.addEventListener('click',e=>{if(editingRole&&!e.target.closest('.role-select')){editingRole=null;roster()}let editRoles=e.target.closest('[data-edit-roles]');if(editRoles){editingRole=editingRole===editRoles.dataset.editRoles?null:editRoles.dataset.editRoles;roster();return}let role=e.target.closest('[data-role]');if(role){let c=state.characters.find(c=>c.name===role.closest('[data-name]').dataset.name);let selected=new Set(c.roles.filter(r=>r!=='待确认'));if(selected.has(role.dataset.role))selected.delete(role.dataset.role);else selected.add(role.dataset.role);c.roles=['主C','辅助','奶妈'].filter(r=>selected.has(r));if(!c.roles.length)c.roles=['待确认'];c.healer=c.roles.includes('奶妈');markDirty();roster();return}let view=e.target.closest('[data-view-teams]');if(view){$('#team-search').value=view.dataset.viewTeams;$('#team-filter').value='all';tab('teams');return}let b=e.target.closest('[data-edit]');if(b)edit(b.dataset.edit)});
$('#save').onclick=async()=>{try{await save();toast(storageMode==='server'?'已同步本地配置；导出仅用于备份':'已保存到浏览器；导出仅用于备份')}catch(e){toast(e.message)}};
$('#calculate').onclick=async()=>{
 const button=$('#calculate');button.disabled=true;button.textContent='正在计算…';
 try{
  if(dirty)await save();
  const version=configurationVersion;
  result=await api('/api/optimize',{include_inferred:$('#include-inferred').checked,fill_roles:$('#fill-roles').checked,fill_solo:$('#fill-solo').checked,all_characters:$('#planning-scope').value==='all'});
  result.stale=version!==configurationVersion;renderResult();tab('results');
 }catch(e){toast(e.message)}finally{button.disabled=false;button.innerHTML='计算配队'}
};
$('#include-inferred').onchange=()=>{invalidateResult();if(result)toast('范围已修改，点击计算重新生成方案')};
$('#new-team').onclick=()=>edit(null);$('#close-editor').onclick=()=>$('#editor').close();
$('#member-inputs').onchange=e=>{if(e.target.dataset.member!==undefined){draft.members[Number(e.target.dataset.member)]=e.target.value;refreshMembers()}};
$('#axis-select').onchange=e=>{draft.selected_axis=e.target.value;axisFields()};
$('#axis-name').oninput=e=>{let a=draft.axes.find(a=>a.id===draft.selected_axis);if(a)a.name=e.target.value};
$('#axis-description').oninput=e=>{let a=draft.axes.find(a=>a.id===draft.selected_axis);if(a)a.description=e.target.value};
$('#team-note').oninput=e=>{draft.note=e.target.value};
$('#add-axis').onclick=()=>{let a={id:crypto.randomUUID(),name:'新输出轴 '+(draft.axes.length+1),author:'自定义',version:'1',description:'',url:''};draft.axes.push(a);draft.selected_axis=a.id;axisFields()};
$('#delete-team').onclick=()=>{forgetResultTeam(draft.id);state.teams=state.teams.filter(t=>t.id!==draft.id);$('#editor').close();markDirty();teams();toast('已移除并自动保存')};
$('#team-form').onsubmit=e=>{e.preventDefault();draft.note=$('#team-note').value;draft.rover_attribute=draft.members.includes('漂泊者')?$('#rover-attribute').value:'';let error='';if(new Set(draft.members).size!==3)error='请选择三名不同角色';else if(draft.members.includes('漂泊者')&&!draft.rover_attribute)error='请选择漂泊者属性';else if(draft.locked&&!draft.enabled)error='必选队伍需要开启参与计算';else if(state.teams.some(t=>t.id!==draft.id&&[...t.members].sort().join('|')===[...draft.members].sort().join('|')&&t.rover_attribute===draft.rover_attribute))error='已有该角色组合，请在原队伍中添加输出轴';if(error){$('#editor-error').textContent=error;return}let index=state.teams.findIndex(t=>t.id===draft.id);if(index<0)state.teams.push(draft);else state.teams[index]=draft;$('#editor').close();markDirty();teams();toast(storageMode==='server'?'已应用，正在自动同步本地':'已自动保存到浏览器')};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
api('/api/state').then(s=>{state=s;restorePreferences();summary();roster();tab(routeTab(),false);$('#save-status').textContent=storageMode==='server'?'已自动同步本地':'已自动保存到浏览器';maybeShowGuide()}).catch(e=>{toast(e.message);$('#character-grid').innerHTML='<div class="empty">数据载入失败。可导入已导出的配置恢复。</div>'});



$('#planning-scope').onchange=()=>{$('#team-filter').value=$('#planning-scope').value==='all'?'all':'available';if(activeTab==='teams')teams();summary();invalidateResult();syncTeamCards();toast($('#planning-scope').value==='all'?'全角色模拟：不会改变拥有状态，未拥有角色按0链、用户练度1模拟；未实装角色排除':'已切回我的角色，点击计算更新方案')};
$('#fill-roles').onchange=invalidateResult;

document.addEventListener('keydown',e=>{if(e.key==='Escape'&&editingRole){editingRole=null;roster()}});



const guideKey='matrix-planner.hide-introduction.v2:'+new URL('.',document.baseURI).href;
const tourSteps=[
 {page:'characters',target:'.role-select',title:'选择角色定位',text:'点击标签框可多选主 C、辅助和奶妈，修改后自动保存。'},
 {page:'characters',target:'.character-card .stamina-inputs',title:'配置角色体力',text:'本周体力就是实际可用次数。拥有状态、链度和练度也可以直接调整。'},
 {page:'teams',target:'#new-team',title:'添加一支队伍',text:'点击“新建队伍”进入编辑窗口。接下来演示怎么填写，不会保存示例队伍。'},
 {page:'teams',modal:true,target:'#member-inputs',title:'选择三位角色',text:'分别选择三个位置的角色。成员不能重复；同一组合的多套输出轴放在同一队伍内。'},
 {page:'teams',modal:true,rover:true,target:'#rover-row',title:'选择漂泊者属性',text:'选中漂泊者后，属性框就在这个角色下方。请选择本队使用的属性。'},
 {page:'teams',modal:true,target:'.dialog-footer',title:'应用并自动保存',text:'确认填写后点“应用到候选列表”，队伍和输出轴会自动保存。这里仅演示，不会新增队伍。'},
 {page:'teams',target:'.team-card .team-adjustments',title:'在卡片上设置权重与必选',text:'候选与结果卡片同步，直接修改后自动保存。用户权重默认 1。“必须选入”会自动开启参与计算；参与开关在卡片右上方，关闭参与会同时取消必选。'},
 {page:'teams',target:'#calculate',title:'计算配队',text:'在页面上方选择计算范围，再点击“计算配队”。先尽量增加队数，再比较总得分。'}
];
const editorTourStart=tourSteps.findIndex(s=>s.modal),editorTourEnd=tourSteps.findLastIndex(s=>s.modal);
let tourIndex=0,tourPreviousTab='characters',tourPreviousFocus=null,tourTarget=null,tourFrame=0,tourSavedDraft=null,tourModalOpen=false,tourEditorOnly=false;
function guideHidden(){try{return localStorage.getItem(guideKey)==='yes'}catch{return false}}
function clearTourTarget(){tourTarget=null;document.querySelectorAll('.tour-target').forEach(el=>el.classList.remove('tour-target'));document.body.classList.remove('tour-header-step')}
function positionTour(){
 if($('#onboarding').hidden||!tourTarget?.isConnected)return;
 const r=tourTarget.getBoundingClientRect(),panel=$('#onboarding .tour-panel'),focus=$('.tour-focus'),pad=6,gap=18,margin=16;
 Object.assign(focus.style,{left:(r.left-pad)+'px',top:(r.top-pad)+'px',width:(r.width+pad*2)+'px',height:(r.height+pad*2)+'px'});
 const w=panel.offsetWidth,h=panel.offsetHeight;
 let x=Math.min(innerWidth-w-margin,Math.max(margin,r.left)),y;
 if(r.right+gap+w<=innerWidth-margin){x=r.right+gap;y=Math.max(margin,Math.min(r.top,innerHeight-h-margin))}
 else if(r.bottom+gap+h<=innerHeight-margin)y=r.bottom+gap;
 else if(r.top-gap-h>=margin)y=r.top-gap-h;
 else y=innerHeight-h-margin;
 Object.assign(panel.style,{left:x+'px',top:Math.max(margin,y)+'px',right:'auto',bottom:'auto'});
}
function queueTourPosition(){if(!tourFrame)tourFrame=requestAnimationFrame(()=>{tourFrame=0;positionTour()})}
const tourObserver=new ResizeObserver(queueTourPosition);
window.addEventListener('resize',queueTourPosition);document.addEventListener('scroll',queueTourPosition,true);
function exitTourEditor(){
 if(tourModalOpen){document.body.append($('#onboarding'));$('#editor').close();tourModalOpen=false;draft=null}
}
function renderTour(){
 clearTourTarget();tourObserver.disconnect();let step=tourSteps[tourIndex];
 if(!step.modal)exitTourEditor();
 if(!step.modal)tab(step.page,false);
 if(step.modal&&!tourModalOpen){
  edit(null);tourModalOpen=true;$('#editor').append($('#onboarding'));
 }
 if(step.rover){
  const other=state.characters.filter(c=>c.name!=='漂泊者').slice(0,2).map(c=>c.name);
  draft.members=['漂泊者',...other];document.querySelectorAll('[data-member]').forEach((el,i)=>el.value=draft.members[i]);draft.rover_attribute='气动';refreshMembers();
 }
 $('#tour-progress').textContent=(tourIndex+1)+' / '+tourSteps.length;
 $('#onboarding-title').textContent=step.title;$('#tour-description').textContent=step.text;
 $('#tour-dots').innerHTML=tourSteps.map((_,i)=>'<span class="'+(i===tourIndex?'active':'')+'"></span>').join('');
 $('#tour-prev').disabled=tourIndex===(tourEditorOnly?editorTourStart:0);$('#tour-next').textContent=tourIndex===(tourEditorOnly?editorTourEnd:tourSteps.length-1)?'完成':'下一步';
 tourTarget=document.querySelector(step.target)||document.querySelector(step.modal?'#member-inputs':step.page==='teams'?'#new-team':'#character-search');
 tourTarget?.scrollIntoView({block:'center',behavior:'instant'});
 if(tourTarget)tourObserver.observe(tourTarget);tourObserver.observe($('#onboarding .tour-panel'));queueTourPosition();
 requestAnimationFrame(()=>{
  if(!tourTarget)return;positionTour();const a=tourTarget.getBoundingClientRect(),p=$('#onboarding .tour-panel').getBoundingClientRect();
  if(a.left<p.right&&a.right>p.left&&a.top<p.bottom&&a.bottom>p.top){
   if(tourModalOpen)$('#editor').scrollTop+=a.top-($('#editor').getBoundingClientRect().top+16);
   else window.scrollBy({top:a.top-96,behavior:'instant'});
   queueTourPosition();
  }
 });
}
function showGuide(editorOnly=false){
 tourPreviousTab=activeTab;tourPreviousFocus=document.activeElement;tourSavedDraft=$('#editor').open?structuredClone(draft):null;
 if($('#editor').open)$('#editor').close();
 tourEditorOnly=editorOnly===true;tourIndex=tourEditorOnly?editorTourStart:0;editingRole=null;
 $('#hide-onboarding').checked=guideHidden();$('#onboarding').hidden=false;document.body.classList.add('tour-open');renderTour();$('#tour-next').focus({preventScroll:true});
}
function maybeShowGuide(){if(!guideHidden())showGuide()}
function closeGuide(){
 try{if($('#hide-onboarding').checked)localStorage.setItem(guideKey,'yes');else localStorage.removeItem(guideKey)}catch{toast('浏览器禁止本地存储，本次选择无法记住')}
 clearTourTarget();tourObserver.disconnect();exitTourEditor();$('#onboarding').hidden=true;document.body.classList.remove('tour-open');tab(tourPreviousTab,false);
 if(tourSavedDraft){edit(tourSavedDraft.id,tourSavedDraft);tourSavedDraft=null}
 if(tourPreviousFocus?.isConnected)tourPreviousFocus.focus({preventScroll:true});
}
$('#editor-guide').onclick=()=>showGuide(true);
$('#editor').addEventListener('cancel',e=>{if(!$('#onboarding').hidden){e.preventDefault();closeGuide()}});
$('#show-guide').onclick=showGuide;
$('#tour-next').onclick=()=>{if(tourIndex===(tourEditorOnly?editorTourEnd:tourSteps.length-1))closeGuide();else{tourIndex++;renderTour();$('#tour-next').focus({preventScroll:true})}};
$('#tour-prev').onclick=()=>{if(tourIndex>(tourEditorOnly?editorTourStart:0)){tourIndex--;renderTour()}};
$('#tour-skip').onclick=closeGuide;
document.addEventListener('keydown',e=>{
 if($('#onboarding').hidden)return;
 if(e.key==='Escape'){e.preventDefault();closeGuide()}
 if(e.key==='Tab'){
  const controls=[...$('#onboarding').querySelectorAll('button:not(:disabled),input')];
  const first=controls[0],last=controls[controls.length-1];
  if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
  else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
 }
});

$('#export-config').onclick=()=>{try{LocalPlanner.validate(structuredClone(state));const blob=new Blob([JSON.stringify(LocalPlanner.exportConfig(state),null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='matrix-planner-config.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message)}};
$('#import-config').onclick=()=>$('#import-file').click();
$('#import-file').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>8000000)throw Error('配置文件过大');const data=JSON.parse(await file.text());const imported=LocalPlanner.importConfig(data);imported.revision=LocalPlanner.read().revision;state=LocalPlanner.save(imported);restorePreferences();dirty=false;queueSync();result=null;summary();roster();teams();$('#result-body').textContent='配置已导入，请重新计算。';$('#result-count').textContent='—';toast('配置已导入并保存')}catch(err){toast(err.message)}finally{e.target.value=''}};

function browserPlan(snapshot,options){
 return new Promise((resolve,reject)=>{
 const code=SOLVER_SOURCE+'\n;const PLANNER_SEED='+JSON.stringify(PLANNER_SEED)+';const releaseVersions='+JSON.stringify(releaseVersions)+';const recency='+recency.toString()+';const sourceMultiplier='+sourceMultiplier.toString()+';'+createLocalPlanner.toString()+';self.onmessage=e=>{try{self.postMessage({result:createLocalPlanner().plan(e.data.state,e.data.options)})}catch(err){self.postMessage({error:err.message})}}';
 const url=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));
 let worker;try{worker=new Worker(url)}catch(e){URL.revokeObjectURL(url);reject(e);return}
 const done=()=>{clearTimeout(timer);worker.terminate();URL.revokeObjectURL(url)};
 const timer=setTimeout(()=>{done();reject(Error('计算超过60秒，请减少候选队伍后重试'))},60000);
 worker.onmessage=e=>{done();e.data.error?reject(Error(e.data.error)):resolve(e.data.result)};
 worker.onerror=e=>{done();reject(Error(e.message||'浏览器计算失败'))};
 worker.postMessage({state:structuredClone(snapshot),options});
 });
}

$('#fill-solo').onchange=invalidateResult;

$('#restore-config').onclick=()=>{if(!confirm('恢复上次保存的配置？当前配置会先备份，可再次恢复切回。'))return;try{state=LocalPlanner.restorePrevious();restorePreferences();dirty=false;queueSync();result=null;summary();roster();teams();$('#result-count').textContent='—';$('#result-body').textContent='已恢复历史配置，请重新计算。';$('#save-status').textContent='已恢复到浏览器';toast('已恢复上次保存')}catch(e){toast(e.message)}};



window.addEventListener("popstate",()=>{if(state)tab(routeTab(),false)});

$('#evidence-filter').onclick=e=>{const button=e.target.closest('[data-evidence]');if(!button)return;const key=button.dataset.evidence;if(key==='all')selectedEvidence.clear();else if(selectedEvidence.has(key))selectedEvidence.delete(key);else selectedEvidence.add(key);teams()};

document.addEventListener('click',e=>{const menu=document.querySelector('.config-menu');if(menu.open&&(!menu.contains(e.target)||e.target.closest('.config-options button')))menu.open=false});
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelector('.config-menu').open=false});

$('#rover-attribute').onchange=e=>{draft.rover_attribute=e.target.value;refreshMembers()};

async function loadConfiguration(){
 const local=LocalPlanner.read();
 if(location.protocol==='file:')return local;
 try{
  const response=await fetch('/api/personal-config',{cache:'no-store'});
  if(!response.ok)return local;
  const remote=await response.json();storageMode='server';serverRevision=remote.revision;
  if(remote.config&&!localStorage.getItem('matrix-planner.sync-pending')){
   const restored=LocalPlanner.importConfig(remote.config);restored.revision=local.revision;
   return LocalPlanner.save(restored);
  }
  setTimeout(()=>queueSync(),0);return local;
 }catch{return local}
}
function persistLocally(){
 try{state=LocalPlanner.save(state);dirty=false;$('#save-status').style.color='';$('#save-status').textContent=storageMode==='server'?'正在同步本地…':'已自动保存到浏览器';queueSync()}
 catch(e){dirty=true;$('#save-status').textContent='保存失败：'+e.message;toast(e.message)}
}
function queueSync(){
 if(storageMode!=='server')return;
 syncPending=true;localStorage.setItem('matrix-planner.sync-pending','yes');clearTimeout(syncTimer);
 syncTimer=setTimeout(()=>syncConfiguration().catch(e=>toast(e.message)),300);
}
async function syncConfiguration(){
 if(storageMode!=='server')return;
 if(syncFlight)return syncFlight;
 clearTimeout(syncTimer);
 syncFlight=(async()=>{
  while(syncPending){
   syncPending=false;
   try{
    const response=await fetch('/api/personal-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:serverRevision,config:LocalPlanner.exportConfig(state)})});
    const data=await response.json();if(!response.ok)throw Error(data.error||'本地同步失败');serverRevision=data.revision;
   }catch(e){syncPending=true;$('#save-status').textContent='已存浏览器，本地同步失败';throw e}
  }
  localStorage.removeItem('matrix-planner.sync-pending');$('#save-status').textContent='已自动同步本地';
 })();
 try{await syncFlight}finally{syncFlight=null}
}
window.addEventListener('beforeunload',e=>{if(storageMode==='server'&&(syncPending||syncFlight)){e.preventDefault();e.returnValue=''}});

const preferenceIds=['planning-scope','include-inferred','fill-roles','fill-solo','character-filter','character-element','team-filter','team-element','character-search','team-search'];
function restorePreferences(){
 const prefs=state.preferences||{};
 for(const id of preferenceIds){const el=$('#'+id);if(prefs[id]!==undefined){if(el.type==='checkbox')el.checked=!!prefs[id];else if(el.tagName!=='SELECT'||[...el.options].some(o=>o.value===prefs[id]))el.value=prefs[id]}}
 selectedEvidence.clear();for(const k of prefs.evidence||[])if(evidenceTypes.some(x=>x.key===k))selectedEvidence.add(k);
}
function savePreferences(){if(!state)return;state.preferences=Object.fromEntries(preferenceIds.map(id=>{const el=$('#'+id);return [id,el.type==='checkbox'?el.checked:el.value]}));state.preferences.evidence=[...selectedEvidence];persistLocally()}
for(const id of preferenceIds)$('#'+id).addEventListener('change',savePreferences);
$('#evidence-filter').addEventListener('click',e=>{if(e.target.closest('[data-evidence]'))savePreferences()});
