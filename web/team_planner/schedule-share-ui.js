/* Import always adds an independent plan. Existing plans are never replaced. */
function scheduleShareSummary(plan){return `${plan.name} · ${plan.rows.length} 行 × ${plan.columns.length} 列 · ${plan.cells.length} 支队伍`}
function scheduleShareTab(importing){
 for(const mode of ['export','import']){
  const selected=(mode==='import')===importing,tab=$('#schedule-share-'+mode+'-tab');
  tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;$('#schedule-share-'+mode).hidden=!selected;
 }
 if(importing){scheduleCheckImport();$('#schedule-import-code').focus()}
}
function scheduleReadImport(){
 if(state.schedules.plans.length>=30)throw Error('已达 30 张排表上限，请先删除不用的排表');
 const plan=ScheduleShare.decode($('#schedule-import-code').value),snapshot=structuredClone(state);
 snapshot.schedules.plans.push(plan);snapshot.schedules.active_id=plan.id;
 LocalPlanner.validate(snapshot);
 return plan;
}
function scheduleCheckImport(){
 const status=$('#schedule-import-status'),input=$('#schedule-import-code');
 status.classList.remove('share-code-error');input.removeAttribute('aria-invalid');$('#schedule-import-submit').disabled=true;
 if(!input.value.trim()){status.textContent='导入会新建一张表，保留所有已有排表。';return}
 try{const plan=scheduleReadImport();status.textContent=scheduleShareSummary(plan)+' · 将新建排表';$('#schedule-import-submit').disabled=false}
 catch(e){status.textContent=e.message;status.classList.add('share-code-error');input.setAttribute('aria-invalid','true')}
}
$('#schedule-share').onclick=()=>{
 try{
  scheduleCard=null;scheduleMoving=null;scheduleCloseGridMenu();renderSchedule();
  $('#schedule-export-code').value=ScheduleShare.encode(schedulePlan());
  $('#schedule-export-summary').textContent=scheduleShareSummary(schedulePlan());$('#schedule-copy-status').textContent='';
  $('#schedule-import-code').value='';scheduleCheckImport();scheduleShareTab(false);
  $('#schedule-share-dialog').showModal();
 }catch(e){toast(e.message)}
};
$('#schedule-share-close').onclick=()=>$('#schedule-share-dialog').close();
$('#schedule-share-export-tab').onclick=()=>scheduleShareTab(false);
$('#schedule-share-import-tab').onclick=()=>scheduleShareTab(true);
$('.schedule-share-tabs').addEventListener('keydown',e=>{
 if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
 e.preventDefault();const importing=e.key==='End'||(e.key!=='Home'&&$('#schedule-share-import-tab').getAttribute('aria-selected')!=='true');
 scheduleShareTab(importing);$('#schedule-share-'+(importing?'import':'export')+'-tab').focus();
});
$('#schedule-import-code').addEventListener('input',scheduleCheckImport);
$('#schedule-copy-code').onclick=async()=>{
 const input=$('#schedule-export-code'),code=input.value;
 try{if(!navigator.clipboard?.writeText)throw Error('clipboard unavailable');await navigator.clipboard.writeText(code);$('#schedule-copy-status').textContent='已复制，可以直接分享'}
 catch{input.focus();input.select();$('#schedule-copy-status').textContent='代码已全选，请按 Ctrl+C（Mac：⌘C）复制'}
};
$('#schedule-import-submit').onclick=()=>{
 try{
  const plan=scheduleReadImport(),base=plan.name;
  for(let index=2;state.schedules.plans.some(p=>p.name===plan.name);index++){
   const suffix='（'+index+'）';plan.name=base.slice(0,60-suffix.length)+suffix;
  }
  if(scheduleAct(()=>{state.schedules.plans.push(plan);state.schedules.active_id=plan.id})){
   $('#schedule-share-dialog').close();toast('已新建排表：'+plan.name);
  }
 }catch(e){$('#schedule-import-status').textContent=e.message;$('#schedule-import-status').classList.add('share-code-error');$('#schedule-import-submit').disabled=true}
};
