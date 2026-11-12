/* Manual schedules: reusable templates, fixed row members and direct card editing. */
let scheduleDragging=null,scheduleUndo=null,scheduleCard=null,scheduleMoving=null;
function scheduleSetSplit(value,save=false){
 const split=Number.isFinite(Number(value))?Math.max(30,Math.min(60,Number(value))):40;
 const workspace=$('.schedule-workspace'),separator=$('#schedule-resizer');
 workspace.style.setProperty('--schedule-deck-share',split+'fr');
 workspace.style.setProperty('--schedule-board-share',(100-split)+'fr');
 separator.setAttribute('aria-valuenow',String(split));
 separator.setAttribute('aria-valuetext',`角色模板 ${split}%，排表 ${100-split}%`);
 if(save){state.preferences={...state.preferences,'schedule-deck-width':split};persistLocally()}
}
let scheduleResize=null;
$('#schedule-resizer').addEventListener('pointerdown',e=>{
 if(e.button!==0)return;
 e.preventDefault();scheduleResize={id:e.pointerId,start:Number(e.currentTarget.getAttribute('aria-valuenow'))};
 e.currentTarget.setPointerCapture(e.pointerId);document.body.classList.add('schedule-resizing');
});
$('#schedule-resizer').addEventListener('pointermove',e=>{
 if(scheduleResize?.id!==e.pointerId)return;
 const box=$('.schedule-workspace').getBoundingClientRect();
 scheduleSetSplit(Math.round((e.clientX-box.left-11)/(box.width-22)*100));
});
function scheduleEndResize(e){
 if(scheduleResize?.id!==e.pointerId)return;
 const split=e.type==='pointerup'?Number($('#schedule-resizer').getAttribute('aria-valuenow')):scheduleResize.start;
 scheduleResize=null;document.body.classList.remove('schedule-resizing');
 scheduleSetSplit(split,e.type==='pointerup');
}
for(const type of ['pointerup','pointercancel','lostpointercapture'])$('#schedule-resizer').addEventListener(type,scheduleEndResize);
$('#schedule-resizer').addEventListener('keydown',e=>{
 const current=Number(e.currentTarget.getAttribute('aria-valuenow'));
 const split={ArrowLeft:current-(e.shiftKey?5:1),ArrowRight:current+(e.shiftKey?5:1),Home:30,End:60}[e.key];
 if(split===undefined)return;e.preventDefault();scheduleSetSplit(split,true);
});
$('#schedule-resizer').addEventListener('dblclick',()=>scheduleSetSplit(40,true));
const schedulePlan=()=>SchedulePlanner.current(state);
const scheduleHead=row=>SchedulePlanner.head(schedulePlan(),row);
const scheduleFixed=row=>SchedulePlanner.fixed(schedulePlan(),row);
const scheduleCell=(row,column)=>schedulePlan().cells.find(c=>c.row===row&&c.column===column);
const schedulePlus='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10"/></svg>';
const scheduleDots='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h.1M8 8h.1M13 8h.1" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>';
const scheduleGrip='<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M5 3h1m4 0h1M5 8h1m4 0h1M5 13h1m4 0h1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
const scheduleCross='<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="m4 4 8 8m0-8-8 8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
const scheduleOrder=cell=>orderedMembers({members:[...cell.members,...scheduleFixed(cell.row)]}).filter(n=>!scheduleFixed(cell.row).includes(n));
function scheduleSnapshot(){scheduleUndo=structuredClone(state.schedules)}
let scheduleGridMenu=null;
function scheduleCloseGridMenu(restoreFocus=false){
 const trigger=scheduleGridMenu?.trigger;
 if(trigger?.isConnected)trigger.setAttribute('aria-expanded','false');
 $('#schedule-grid-menu').hidden=true;scheduleGridMenu=null;
 if(restoreFocus&&trigger?.isConnected)trigger.focus();
}
function scheduleInsertGridItem(kind,reference=null,after=true){
 const plan=schedulePlan(),items=kind==='row'?plan.rows:plan.columns,limit=kind==='row'?100:50;
 if(items.length>=limit)return;
 scheduleAct(()=>{
  const index=reference===null?items.length:items.findIndex(item=>(kind==='row'?item:item.id)===reference);
  if(index<0)throw Error('目标位置不存在');
  const at=reference===null?index:index+(after?1:0);
  if(kind==='row'){
   const row='row-'+crypto.randomUUID();items.splice(at,0,row);plan.row_heads[row]=null;plan.row_fixed[row]=[];
  }else items.splice(at,0,{id:crypto.randomUUID(),name:'列'+(items.length+1)});
 });
}
function scheduleDeleteGridItem(kind,id){
 const plan=schedulePlan(),row=kind==='row',items=row?plan.rows:plan.columns;
 if(items.length===1)return;
 const affected=plan.cells.some(c=>c[row?'row':'column']===id);
 if(affected&&!confirm('删除此'+(row?'行':'列')+'及其中队伍？可撤销恢复。'))return;
 scheduleAct(()=>{
  if(row){plan.rows=plan.rows.filter(r=>r!==id);delete plan.row_heads[id];delete plan.row_attributes[id];delete plan.row_fixed[id]}
  else plan.columns=plan.columns.filter(c=>c.id!==id);
  plan.cells=plan.cells.filter(c=>c[row?'row':'column']!==id);
 });
}
function scheduleOpenGridMenu(kind,id,trigger,point=null){
 if(!point&&scheduleGridMenu?.trigger===trigger){scheduleCloseGridMenu(true);return}
 scheduleCloseGridMenu();
 const plan=schedulePlan(),row=kind==='row',items=row?plan.rows:plan.columns,index=items.findIndex(item=>(row?item:item.id)===id);
 if(index<0)return;
 scheduleGridMenu={kind,id,trigger};trigger.setAttribute('aria-expanded','true');
 const actions=[
  ['before',row?'在上方插入行':'在左侧插入列',items.length>=(row?100:50)],
  ['after',row?'在下方插入行':'在右侧插入列',items.length>=(row?100:50)],
  ['previous',row?'上移此行':'左移此列',index===0],
  ['next',row?'下移此行':'右移此列',index===items.length-1],
  ['delete',row?'删除此行':'删除此列',items.length===1]
 ];
 const menu=$('#schedule-grid-menu');
 menu.innerHTML=actions.map(([action,label,disabled])=>`<button type="button" role="menuitem" data-grid-action="${action}" ${disabled?'disabled':''} class="${action==='delete'?'grid-menu-danger':''}">${label}</button>`).join('');
 menu.setAttribute('aria-label',row?'第'+(index+1)+'行操作':items[index].name+'列操作');
 menu.hidden=false;
 const anchor=trigger.getBoundingClientRect(),box=menu.getBoundingClientRect();
 menu.style.left=Math.max(8,Math.min(point?.x??anchor.left,innerWidth-box.width-8))+'px';
 menu.style.top=Math.max(8,Math.min(point?.y??anchor.bottom+4,innerHeight-box.height-8))+'px';
 menu.querySelector('button:not(:disabled)')?.focus();
}
$('#schedule-grid-menu').addEventListener('click',e=>{
 const action=e.target.closest('[data-grid-action]')?.dataset.gridAction;if(!action||!scheduleGridMenu)return;
 const {kind,id}=scheduleGridMenu; scheduleCloseGridMenu();
 if(action==='before'||action==='after')scheduleInsertGridItem(kind,id,action==='after');
 else if(action==='delete')scheduleDeleteGridItem(kind,id);
 else if(action==='previous'||action==='next'){
  const plan=schedulePlan(),items=kind==='row'?plan.rows:plan.columns,index=items.findIndex(item=>(kind==='row'?item:item.id)===id),target=items[index+(action==='previous'?-1:1)];
  if(target)scheduleAct(()=>kind==='row'?SchedulePlanner.swapRows(plan,id,target):SchedulePlanner.swapColumns(plan,id,target.id));
 }
 const selector=kind==='row'?'[data-grid-menu-row]':'[data-grid-menu-column]';
 const trigger=[...document.querySelectorAll(selector)].find(el=>(kind==='row'?el.dataset.gridMenuRow:el.dataset.gridMenuColumn)===id);
 (trigger||$('#schedule-add-'+kind)).focus();
});
$('#schedule-grid-menu').addEventListener('keydown',e=>{
 if(e.key==='Escape'){e.preventDefault();e.stopPropagation();scheduleCloseGridMenu(true);return}
 if(e.key==='Tab'){scheduleCloseGridMenu(true);return}
 if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;
 e.preventDefault();const items=[...e.currentTarget.querySelectorAll('button:not(:disabled)')],index=items.indexOf(document.activeElement);
 const next=e.key==='Home'?0:e.key==='End'?items.length-1:(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;
 items[next]?.focus();
});
document.addEventListener('click',e=>{if(!e.target.closest('#schedule-grid-menu,[data-grid-menu-row],[data-grid-menu-column]'))scheduleCloseGridMenu()});
window.addEventListener('resize',()=>scheduleCloseGridMenu());
document.addEventListener('scroll',()=>scheduleCloseGridMenu(),true);
$('#schedule-table').addEventListener('contextmenu',e=>{
 if(e.target.closest('input,select,.custom-select'))return;
 const row=e.target.closest('[data-row-header]'),column=e.target.closest('[data-column-header]');
 if(!row&&!column)return;e.preventDefault();
 const kind=row?'row':'column',id=row?.dataset.rowHeader||column.dataset.columnHeader,trigger=(row||column).querySelector('[data-grid-menu-'+kind+']');
 scheduleOpenGridMenu(kind,id,trigger,{x:e.clientX,y:e.clientY});
});
$('#schedule-table').addEventListener('keydown',e=>{
 const trigger=e.target.closest('[data-grid-menu-row],[data-grid-menu-column]');
 if(trigger&&e.key==='ArrowDown'){e.preventDefault();scheduleOpenGridMenu(trigger.dataset.gridMenuRow?'row':'column',trigger.dataset.gridMenuRow||trigger.dataset.gridMenuColumn,trigger)}
});
function scheduleCommit(){persistLocally();renderSchedule()}
function scheduleAct(action){const before=structuredClone(state.schedules);try{action();scheduleUndo=before;scheduleCard=null;scheduleMoving=null;scheduleCommit();return true}catch(e){state.schedules=before;toast(e.message);return false}}
function scheduleTone(name,report){
 if(!name||report.usage[name]<=report.budget[name])return '';
 const hue=Math.round((characterDisplayOrder.get(name)||0)*137.508)%360;
 return ` style="--schedule-error-bg:hsl(${hue} 66% 93%);--schedule-error-ink:hsl(${hue} 48% 26%);--schedule-error-line:hsl(${hue} 40% 65%)"`;
}
function scheduleCardContent(name,{cell={},status=''}={}){
 const c=state.characters.find(c=>c.name===name);
 return `<img src="${memberImage(name,cell)}" alt="" draggable="false" loading="lazy" width="36" height="46"><span class="schedule-card-info"><strong>${esc(memberName(name,cell))}</strong><small>${esc(c.roles.join(' / '))}</small><span>${esc(status)}</span></span>`;
}
function scheduleForm(name,value,dataset,label){
 if(name!=='漂泊者')return '';
 return `<label class="schedule-inline-form"><select ${dataset} aria-label="${esc(label)}">${state.characters.find(c=>c.name===name).attributes.map(a=>`<option data-element="${esc(a)}" ${a===value?'selected':''}>${esc(a)}</option>`).join('')}</select></label>`;
}
function renderScheduleCards(report){
 const characters=state.characters.filter(c=>c.released).sort((a,b)=>characterDisplayOrder.get(a.name)-characterDisplayOrder.get(b.name));
 const group=c=>c.roles.includes('奶妈')?'奶妈':c.roles.includes('主C')?'主 C':'辅助';
 const versionOf=c=>c.release_version?.match(/\d+/)?.[0]||'其他';
 const versions=[...new Set(characters.map(versionOf))];
 $('#schedule-deck-title').textContent='角色模板 · '+characters.length+' 位';
 $('#schedule-card-bank').style.setProperty('--template-versions',versions.length);
 $('#schedule-card-bank').innerHTML=`<div class="schedule-template-corner">定位 / 版本</div>${versions.map(version=>`<div class="schedule-version-heading">${esc(version==='其他'?version:version+'.x')}</div>`).join('')}`+['主 C','辅助','奶妈'].map(role=>{
  const members=characters.filter(c=>group(c)===role);
  return `<div class="schedule-role-heading">${role}<small>${members.length}</small></div>${versions.map(version=>`<section class="schedule-version-group" aria-label="${esc(role+' '+version+'.x 模板')}"><div class="schedule-template-grid">${members.filter(c=>versionOf(c)===version).map(c=>{
   const over=report.usage[c.name]>report.budget[c.name],exhausted=report.usage[c.name]===report.budget[c.name],selected=scheduleCard?.name===c.name&&!scheduleCard.from;
   return `<button type="button" draggable="true" data-bank-name="${esc(c.name)}" class="schedule-character-card${over?' card-over':exhausted?' card-exhausted':''}${selected?' card-selected':''}"${scheduleTone(c.name,report)} aria-pressed="${selected}" aria-label="${esc(c.name+'模板'+(exhausted?'，次数用完':''))}" title="${esc(c.release_version+' · '+c.release_date+' · '+c.roles.join(' / ')+' · 已用 '+report.usage[c.name]+' / '+report.budget[c.name]+(exhausted?' · 次数用完，可继续安排':over?' · 超额':''))}">${scheduleCardContent(c.name,{status:report.usage[c.name]+'/'+report.budget[c.name]})}</button>`;
  }).join('')}</div></section>`).join('')}`;
 }).join('');
 $('#schedule-cancel-card').hidden=!scheduleCard&&!scheduleMoving;
 $('#schedule-card-status').textContent=scheduleCard?'已选 '+scheduleCard.name+' · 拖入或点击目标位置':scheduleMoving?'选择目标行、列或队伍进行交换':'模板可重复拖入 · 灰色表示次数用完';
}
function renderSchedule(){
 if(!state?.schedules)return;
 scheduleCloseGridMenu();
 const plan=schedulePlan(),report=SchedulePlanner.analyse(plan,state.characters);
 scheduleSetSplit(state.preferences?.['schedule-deck-width']??40);
 $('#schedule-select').innerHTML=state.schedules.plans.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
 $('#schedule-select').value=plan.id;$('#schedule-name').value=plan.name;
 $('#schedule-delete').disabled=state.schedules.plans.length===1;$('#schedule-undo').disabled=!scheduleUndo;
 $('#schedule-add-column').disabled=plan.columns.length>=50;
 $('#schedule-add-row').disabled=plan.rows.length>=100;
 $('#schedule-help').textContent='行头可空或固定最多两人，每队自动加入；拖角色卡只移动角色，拖行列把手连同队伍调整顺序。';
 $('#schedule-status').innerHTML=`<strong>${plan.cells.length} 支队伍</strong><span>${report.incomplete?report.incomplete+' 支待补成员':'成员已补齐'}</span><span class="${report.exceeded.length?'schedule-error-text':''}">${report.exceeded.length?report.exceeded.length+' 名角色超额':'体力未超额'}</span>`;
 renderScheduleCards(report);
 $('#schedule-table').innerHTML=`<thead><tr><th class="schedule-corner" scope="col">固定位<small>可空，最多两人</small></th>${plan.columns.map(c=>`<th scope="col" data-column-header="${esc(c.id)}"><div class="schedule-column-controls"><button type="button" draggable="true" data-move-column="${esc(c.id)}" aria-label="${esc('移动'+c.name)}">${scheduleGrip}</button><input data-column-name="${esc(c.id)}" value="${esc(c.name)}" maxlength="30" aria-label="${esc(c.name)}列名"><button type="button" class="schedule-grid-menu-trigger" data-grid-menu-column="${esc(c.id)}" aria-label="${esc(c.name+'列操作')}" aria-haspopup="menu" aria-expanded="false" title="列操作（也可右键列标题）">${scheduleDots}</button></div><button type="button" class="schedule-insert-handle schedule-insert-column" data-grid-insert-column="${esc(c.id)}" aria-label="${esc('在'+c.name+'右侧添加列')}" title="在右侧添加列" ${plan.columns.length>=50?'disabled':''}>${schedulePlus}</button></th>`).join('')}</tr></thead><tbody>${plan.rows.map((row,rowIndex)=>{
  const names=scheduleFixed(row),rowForm=SchedulePlanner.form(plan,row);
  return `<tr data-healer="${esc(row)}" class="${scheduleMoving?.kind==='row'&&scheduleMoving.row===row?'row-moving':''}"><th scope="row" data-row-header="${esc(row)}"><div class="schedule-row-controls"><button type="button" draggable="true" data-move-row="${esc(row)}" aria-label="拖动整行">${scheduleGrip}</button><button type="button" class="schedule-grid-menu-trigger" data-grid-menu-row="${esc(row)}" aria-label="${esc('第'+(rowIndex+1)+'行操作')}" aria-haspopup="menu" aria-expanded="false" title="行操作（也可右键行头）">${scheduleDots}</button></div><div class="schedule-fixed-cards">${names.map(name=>{
   const over=report.usage[name]>report.budget[name];
   return `<article draggable="true" data-fixed-card="${esc(name)}" class="schedule-character-card schedule-member schedule-healer${over?' card-over schedule-healer-over':''}${scheduleCard?.fixedRow===row&&scheduleCard.name===name?' card-selected':''}"${scheduleTone(name,report)}><button type="button" class="schedule-card-pick" data-pick-fixed="${esc(name)}" aria-label="${esc('移动固定角色'+name)}">${scheduleCardContent(name,{cell:{rover_attribute:rowForm},status:report.usage[name]+' / '+report.budget[name]})}</button><button type="button" class="schedule-card-remove" data-remove-fixed="${esc(name)}" aria-label="${esc('移除固定角色'+name)}">${scheduleCross}</button>${scheduleForm(name,rowForm,'data-row-rover="'+esc(row)+'"','行头漂泊者属性 '+row)}</article>`;
  }).join('')}${names.length<2?'<button type="button" class="schedule-cell-target schedule-fixed-target" data-fixed-place aria-label="添加固定角色" title="拖入添加固定角色，拖到已有卡片上可替换">添加角色</button>':''}</div><button type="button" class="schedule-insert-handle schedule-insert-row" data-grid-insert-row="${esc(row)}" aria-label="${esc('在第'+(rowIndex+1)+'行下方添加行')}" title="在下方添加行" ${plan.rows.length>=100?'disabled':''}>${schedulePlus}</button></th>${plan.columns.map(column=>{
   const cell=scheduleCell(row,column.id),members=cell?scheduleOrder(cell):[];
   return `<td><div class="schedule-slot${cell?' filled':''}" data-schedule-row="${esc(row)}" data-schedule-column="${esc(column.id)}" role="group" aria-label="${esc((names.join('、')||'空白行')+'，'+column.name)}">${cell?`<button type="button" class="schedule-team-handle" data-move-team draggable="true" aria-label="移动此队伍">${scheduleGrip}<span>${esc(cell.label||'移动队伍')}</span></button><div class="schedule-members">${members.map(n=>{
    const exceeded=report.usage[n]>report.budget[n],selected=scheduleCard?.from?.row===row&&scheduleCard.from.column===column.id&&scheduleCard.name===n;
    return `<article draggable="true" data-member-card="${esc(n)}" class="schedule-character-card schedule-member${exceeded?' card-over':''}${selected?' card-selected':''}"${scheduleTone(n,report)}><button type="button" data-pick-member="${esc(n)}" class="schedule-card-pick" aria-label="${esc('移动'+n)}">${scheduleCardContent(n,{cell,status:report.usage[n]+' / '+report.budget[n]})}</button><button type="button" data-remove-member="${esc(n)}" class="schedule-card-remove" aria-label="${esc('移除'+n)}">${scheduleCross}</button>${scheduleForm(n,cell.rover_attribute,'data-cell-rover','格内漂泊者属性 '+row+' '+column.id)}</article>`;
   }).join('')}${members.length+names.length<3?'<button type="button" class="schedule-cell-target" data-cell-place>拖入角色卡 · 待补 '+(3-members.length-names.length)+' 人</button>':''}</div>`:'<button type="button" class="schedule-cell-target" data-cell-place>拖入角色卡</button>'}</div></td>`;
  }).join('')}</tr>`;
 }).join('')}</tbody>`;
}
function schedulePlaceCard(card,position,replaceName=null){
 const plan=schedulePlan(),source=card.from&&scheduleCell(card.from.row,card.from.column),target=position&&scheduleCell(position.row,position.column);
 if(card.from&&(!source||!source.members.includes(card.name))){toast('卡牌位置已变化，请重新选择');return}
 const targetFixed=position?scheduleFixed(position.row).filter(n=>!(card.fixedRow===position.row&&n===card.name)):[];
 if(position&&targetFixed.includes(card.name)){toast('该角色已是全行固定角色，不能重复加入');return}
 if(position&&target?.members.includes(card.name)){if(source===target){scheduleCard=null;renderSchedule();return}toast('同一队伍不能重复加入角色');return}
 if(position&&(target?.members.length||0)>=3-targetFixed.length&&!target?.members.includes(replaceName)){toast('格子已满，请拖到要替换的卡牌上');return}
 const replaced=target?.members.includes(replaceName)?replaceName:null;
 if(source&&replaced&&(scheduleFixed(source.row).includes(replaced)||source.members.includes(replaced))){toast('交换后角色会重复');return}
 if(!position&&!source&&!card.fixedRow)return;
 scheduleAct(()=>{
  const fixedForm=card.fixedRow?SchedulePlanner.form(plan,card.fixedRow):'';
  if(card.fixedRow){const fixed=scheduleFixed(card.fixedRow).filter(n=>n!==card.name);SchedulePlanner.setFixed(plan,card.fixedRow,fixed,SchedulePlanner.form(plan,card.fixedRow))}
  const rover=source?.rover_attribute||fixedForm||state.characters.find(c=>c.name===card.name)?.attributes?.[0]||'',replacedRover=target?.rover_attribute||'';
  if(source){source.members=source.members.filter(n=>n!==card.name);if(replaced)source.members.push(replaced);source.label='';if(card.name==='漂泊者')source.rover_attribute='';if(replaced==='漂泊者')source.rover_attribute=replacedRover;source.members=scheduleOrder(source);if(!source.members.length)plan.cells=plan.cells.filter(c=>c!==source)}
  if(position){const cell=target||{...position,label:'',members:[],rover_attribute:''};if(replaced)cell.members=cell.members.filter(n=>n!==replaced);cell.members.push(card.name);cell.label='';if(replaced==='漂泊者')cell.rover_attribute='';if(card.name==='漂泊者')cell.rover_attribute=rover;cell.members=scheduleOrder(cell);if(!target)plan.cells.push(cell)}
 });
}
function scheduleApplyHead(card,row,replaceName=null){
 scheduleAct(()=>{
  const plan=schedulePlan(),source=card.from&&scheduleCell(card.from.row,card.from.column),attribute=card.name==='漂泊者'?(source?.rover_attribute||(card.fixedRow?SchedulePlanner.form(plan,card.fixedRow):'衍射')):SchedulePlanner.form(plan,row);
  const fixed=[...scheduleFixed(row)];
  if(fixed.includes(card.name)){if(card.fixedRow===row)return;throw Error('固定位不能重复')}
  if(replaceName&&fixed.includes(replaceName))fixed.splice(fixed.indexOf(replaceName),1,card.name);else fixed.push(card.name);
  if(card.from&&(!source||!source.members.includes(card.name)))throw Error('卡牌位置已变化');
  if(card.fixedRow)SchedulePlanner.setFixed(plan,card.fixedRow,scheduleFixed(card.fixedRow).filter(n=>n!==card.name),SchedulePlanner.form(plan,card.fixedRow));
  if(source){source.members=source.members.filter(n=>n!==card.name);source.label='';if(card.name==='漂泊者')source.rover_attribute='';if(!source.members.length&&source.row!==row)plan.cells=plan.cells.filter(c=>c!==source)}
  SchedulePlanner.setFixed(plan,row,fixed,attribute);
 });
}
function scheduleRemoveFixed(row,name){scheduleAct(()=>SchedulePlanner.setFixed(schedulePlan(),row,scheduleFixed(row).filter(n=>n!==name),SchedulePlanner.form(schedulePlan(),row)))}
function scheduleFinishMove(to){scheduleAct(()=>SchedulePlanner.move(schedulePlan(),scheduleMoving,to))}
function scheduleHeaderAction(payload,row,column,replaceName=null){
 if(row){if(payload.kind==='card')scheduleApplyHead(payload,row,replaceName);else if(payload.kind==='row')scheduleAct(()=>SchedulePlanner.swapRows(schedulePlan(),payload.row,row))}
 else if(column&&payload.kind==='column')scheduleAct(()=>SchedulePlanner.swapColumns(schedulePlan(),payload.column,column));
}
$('#schedule-table').addEventListener('click',e=>{
 if(e.target.closest('.custom-select,.schedule-inline-form,input'))return;
 const insert=e.target.closest('[data-grid-insert-row],[data-grid-insert-column]');
 if(insert){scheduleInsertGridItem(insert.dataset.gridInsertRow?'row':'column',insert.dataset.gridInsertRow||insert.dataset.gridInsertColumn);return}
 const menu=e.target.closest('[data-grid-menu-row],[data-grid-menu-column]');
 if(menu){scheduleOpenGridMenu(menu.dataset.gridMenuRow?'row':'column',menu.dataset.gridMenuRow||menu.dataset.gridMenuColumn,menu);return}
 const rowHeader=e.target.closest('[data-row-header]'),columnHeader=e.target.closest('[data-column-header]'),slot=e.target.closest('[data-schedule-row]');
 if(rowHeader){const row=rowHeader.dataset.rowHeader,remove=e.target.closest('[data-remove-fixed]'),fixed=e.target.closest('[data-fixed-card]');
  if(remove){scheduleRemoveFixed(row,remove.dataset.removeFixed);return}
  if(e.target.closest('[data-move-row]')){scheduleCard=null;scheduleMoving={kind:'row',row};renderSchedule();return}
  if(scheduleCard)scheduleApplyHead(scheduleCard,row,fixed?.dataset.fixedCard);
  else if(scheduleMoving?.kind==='row')scheduleHeaderAction(scheduleMoving,row);
  else if(fixed){scheduleMoving=null;scheduleCard={kind:'card',name:fixed.dataset.fixedCard,fixedRow:row};renderSchedule()}
  return}
 if(columnHeader){const column=columnHeader.dataset.columnHeader;if(scheduleMoving?.kind==='column')scheduleHeaderAction(scheduleMoving,null,column);else{scheduleMoving={kind:'column',column};renderSchedule()}return}
 if(!slot)return;
 const position={row:slot.dataset.scheduleRow,column:slot.dataset.scheduleColumn},remove=e.target.closest('[data-remove-member]'),member=e.target.closest('[data-member-card]');
 if(remove){schedulePlaceCard({name:remove.dataset.removeMember,from:position},null);return}
 if(e.target.closest('[data-move-team]')){scheduleCard=null;scheduleMoving=position;renderSchedule();return}
 if(scheduleCard)schedulePlaceCard(scheduleCard,position,member?.dataset.memberCard);
 else if(scheduleMoving&&!scheduleMoving.kind)scheduleFinishMove(position);
 else if(member){scheduleMoving=null;scheduleCard={kind:'card',name:member.dataset.memberCard,from:position};renderSchedule()}
});
function scheduleStartDrag(e,payload){scheduleCard=null;scheduleMoving=null;scheduleDragging=payload;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',JSON.stringify(payload));if(payload.kind==='row')e.target.closest('tr').classList.add('row-dragging')}
$('#schedule-table').addEventListener('dragstart',e=>{
 const fixed=e.target.closest('[data-fixed-card]');if(fixed){scheduleStartDrag(e,{kind:'card',name:fixed.dataset.fixedCard,fixedRow:fixed.closest('[data-row-header]').dataset.rowHeader});return}
 const row=e.target.closest('[data-move-row]'),column=e.target.closest('[data-move-column]');
 if(row){scheduleStartDrag(e,{kind:'row',row:row.dataset.moveRow});return}if(column){scheduleStartDrag(e,{kind:'column',column:column.dataset.moveColumn});return}
 const slot=e.target.closest('[data-schedule-row]'),member=e.target.closest('[data-member-card]');if(!slot||(!member&&!e.target.closest('[data-move-team]'))){e.preventDefault();return}
 const from={row:slot.dataset.scheduleRow,column:slot.dataset.scheduleColumn};scheduleStartDrag(e,member?{kind:'card',name:member.dataset.memberCard,from}:from);
});
$('#schedule-table').addEventListener('dragover',e=>{
 if(scheduleDragging?.kind==='row'){
  const row=e.target.closest('tr[data-healer]');if(!row)return;
  e.preventDefault();e.dataTransfer.dropEffect='move';
  document.querySelectorAll('#schedule-table .row-drop-target').forEach(el=>{if(el!==row)el.classList.remove('row-drop-target')});
  if(row.dataset.healer!==scheduleDragging.row)row.classList.add('row-drop-target');return;
 }
 const target=e.target.closest('[data-row-header],[data-column-header],[data-schedule-row]');if(scheduleDragging&&target){e.preventDefault();e.dataTransfer.dropEffect='move';target.classList.add('drop-target')}
});
$('#schedule-table').addEventListener('dragleave',e=>{const target=e.target.closest('.row-drop-target,.drop-target');if(target&&!target.contains(e.relatedTarget))target.classList.remove('drop-target','row-drop-target')});
$('#schedule-table').addEventListener('drop',e=>{
 if(!scheduleDragging)return;e.preventDefault();const payload=scheduleDragging,row=e.target.closest('[data-row-header]'),column=e.target.closest('[data-column-header]'),slot=e.target.closest('[data-schedule-row]');
 if(payload.kind==='row'){const targetRow=e.target.closest('tr[data-healer]');if(targetRow)scheduleHeaderAction(payload,targetRow.dataset.healer)}
 else if(row||column)scheduleHeaderAction(payload,row?.dataset.rowHeader,column?.dataset.columnHeader,e.target.closest('[data-fixed-card]')?.dataset.fixedCard);
 else if(slot){const to={row:slot.dataset.scheduleRow,column:slot.dataset.scheduleColumn};if(payload.kind==='card')schedulePlaceCard(payload,to,e.target.closest('[data-member-card]')?.dataset.memberCard);else if(!payload.kind){scheduleMoving=payload;scheduleFinishMove(to)}}
 scheduleClearDrag();
});
$('#schedule-card-bank').addEventListener('click',e=>{const card=e.target.closest('[data-bank-name]');if(!card)return;scheduleMoving=null;scheduleCard={kind:'card',name:card.dataset.bankName};renderSchedule()});
$('#schedule-card-bank').addEventListener('dragstart',e=>{const card=e.target.closest('[data-bank-name]');if(card)scheduleStartDrag(e,{kind:'card',name:card.dataset.bankName})});
$('#schedule-card-bank').addEventListener('dragover',e=>{if(scheduleDragging?.kind==='card'||scheduleDragging&&!scheduleDragging.kind){e.preventDefault();$('#schedule-card-bank').classList.add('drop-target')}});
$('#schedule-card-bank').addEventListener('drop',e=>{if(!scheduleDragging)return;e.preventDefault();const payload=scheduleDragging;if(payload.fixedRow)scheduleRemoveFixed(payload.fixedRow,payload.name);else if(payload.kind==='card')schedulePlaceCard(payload,null);else if(!payload.kind)scheduleAct(()=>schedulePlan().cells=schedulePlan().cells.filter(c=>c.row!==payload.row||c.column!==payload.column));scheduleDragging=null;$('#schedule-card-bank').classList.remove('drop-target')});
function scheduleClearDrag(){scheduleDragging=null;document.querySelectorAll('#schedule .drop-target,#schedule .row-dragging,#schedule .row-drop-target').forEach(el=>el.classList.remove('drop-target','row-dragging','row-drop-target'))}
document.addEventListener('dragend',scheduleClearDrag);
$('#schedule-table').addEventListener('change',e=>{
 if(e.target.matches('[data-row-rover]')){scheduleAct(()=>schedulePlan().row_attributes[e.target.dataset.rowRover]=e.target.value);return}
 if(e.target.matches('[data-cell-rover]')){const slot=e.target.closest('[data-schedule-row]');scheduleAct(()=>scheduleCell(slot.dataset.scheduleRow,slot.dataset.scheduleColumn).rover_attribute=e.target.value);return}
 const id=e.target.dataset.columnName;if(!id)return;const col=schedulePlan().columns.find(c=>c.id===id),name=e.target.value.trim();if(name)scheduleAct(()=>col.name=name);else e.target.value=col.name;
});
$('#schedule-cancel-card').onclick=()=>{scheduleCard=null;scheduleMoving=null;renderSchedule()};
$('#schedule-select').onchange=e=>{scheduleCard=null;scheduleMoving=null;scheduleUndo=null;state.schedules.active_id=e.target.value;scheduleCommit()};
 $('#schedule-name').onchange=e=>{const name=e.target.value.trim();if(name)scheduleAct(()=>schedulePlan().name=name);else e.target.value=schedulePlan().name};
$('#schedule-rename').onclick=()=>{$('#schedule-name').hidden=false;$('#schedule-name').focus();$('#schedule-name').select()};
$('#schedule-name').onblur=()=>$('#schedule-name').hidden=true;
function scheduleCreate(copy){
 if(state.schedules.plans.length>=30){toast('最多保存 30 张排表');return}
 scheduleAct(()=>{const name=(copy?'副本 ':'新排表 ')+(state.schedules.plans.length+1),plan=copy?{...structuredClone(schedulePlan()),id:crypto.randomUUID(),name}:SchedulePlanner.blank(state,name);state.schedules.plans.push(plan);state.schedules.active_id=plan.id});
}
$('#schedule-new').onclick=()=>scheduleCreate(false);$('#schedule-copy').onclick=()=>scheduleCreate(true);
$('#schedule-delete').onclick=()=>{if(state.schedules.plans.length<=1||!confirm('删除“'+schedulePlan().name+'”？可撤销恢复。'))return;scheduleAct(()=>{state.schedules.plans=state.schedules.plans.filter(p=>p.id!==state.schedules.active_id);state.schedules.active_id=state.schedules.plans[0].id})};
$('#schedule-undo').onclick=()=>{if(!scheduleUndo)return;const previous=structuredClone(state.schedules);state.schedules=scheduleUndo;scheduleUndo=previous;scheduleMoving=null;scheduleCard=null;scheduleCommit()};
$('#schedule-add-row').onclick=()=>scheduleInsertGridItem('row');
$('#schedule-add-column').onclick=()=>scheduleInsertGridItem('column');
$('#schedule-compact').onclick=()=>scheduleAct(()=>SchedulePlanner.compact(schedulePlan()));
document.addEventListener('keydown',e=>{if(activeTab!=='schedule'||$('#schedule-share-dialog').open)return;if(e.key==='Escape'){scheduleCard=null;scheduleMoving=null;renderSchedule()}if(e.key==='Delete'&&(scheduleCard?.from||scheduleCard?.fixedRow)&&!e.target.closest('input,select,textarea,[contenteditable]')){e.preventDefault();if(scheduleCard.fixedRow)scheduleRemoveFixed(scheduleCard.fixedRow,scheduleCard.name);else schedulePlaceCard(scheduleCard,null)}});
