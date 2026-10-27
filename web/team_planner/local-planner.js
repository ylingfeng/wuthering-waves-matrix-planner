/* Browser-only storage and integer optimization. No network API. */
function createLocalPlanner(){
 const key='matrix-planner.configuration.v1';
 const clone=x=>structuredClone(x);
 const identity=t=>[...t.members].sort().join('|');
 const retiredDanjin=t=>t.origin==='user_recommendation'&&identity(t)===['丹瑾','秋水','灯灯'].sort().join('|');
 function validate(s){
  if(!s||!Array.isArray(s.characters)||!Array.isArray(s.teams)||s.teams.length>2000)throw Error('配置格式无效');
  const names=new Set(PLANNER_SEED.characters.map(c=>c.name));
  if(s.characters.length!==names.size||new Set(s.characters.map(c=>c.name)).size!==names.size)throw Error('角色名单不完整');
  for(const c of s.characters){
   if(!names.has(c.name)||!Number.isInteger(c.chain)||c.chain<0||c.chain>6||!Number.isFinite(c.weight)||c.weight<1||c.weight>100)throw Error('角色链度或练度无效');
   for(const v of [c.base,c.weekly])if(v!==null&&(!Number.isInteger(v)||v<0||v>99))throw Error('体力无效');
   if(!Array.isArray(c.roles)||!c.roles.length||c.roles.some(r=>!['主C','辅助','奶妈','待确认'].includes(r)))throw Error('角色定位无效');
   if(typeof c.available!=='boolean'||typeof c.healer!=='boolean')throw Error('角色开关无效');
   c.healer=c.roles.includes('奶妈');
   const original=PLANNER_SEED.characters.find(x=>x.name===c.name);
   for(const f of ['released','attributes','rarity','release_version','release_date'])c[f]=clone(original[f]);
  }
  // Correct the old built-in recommendation, including previously saved browser data.
  s.teams=s.teams.filter(t=>!retiredDanjin(t));
  const correction='2026-10-26-calcharo-yangyang';
  if(!(s.catalogue_updates||[]).includes(correction)){
   s.teams=s.teams.filter(t=>identity(t)!==['卡卡罗','莫特斐','鉴心'].sort().join('|'));
   for(const t of PLANNER_SEED.teams.filter(t=>t.origin==='user_recommendation'&&t.members.includes('卡卡罗')&&t.members.includes('秧秧'))){
    if(!s.teams.some(old=>identity(old)===identity(t)&&old.rover_attribute===t.rover_attribute))s.teams.push(clone(t));
   }
   s.catalogue_updates=[...(s.catalogue_updates||[]),correction];
  }
  const videoUpdate='2026-10-26-iuno-jianxin-verina';
  if(!(s.catalogue_updates||[]).includes(videoUpdate)){
   const added=PLANNER_SEED.teams.find(t=>t.id==='82038de48844ce8a');
   if(added){
    const existing=s.teams.find(t=>identity(t)===identity(added));
    if(!existing)s.teams.push(clone(added));
    else existing.sources=[...new Set([...(existing.sources||[]),...added.sources])];
   }
   s.catalogue_updates=[...(s.catalogue_updates||[]),videoUpdate];
  }
  const secondVideoUpdate='2026-10-26-iuno-lynae-jianxin';
  if(!(s.catalogue_updates||[]).includes(secondVideoUpdate)){
   const added=PLANNER_SEED.teams.find(t=>t.id==='ecf9256f117a5ca8');
   if(added){
    const existing=s.teams.find(t=>identity(t)===identity(added));
    if(!existing)s.teams.push(clone(added));
    else existing.sources=[...new Set([...(existing.sources||[]),...added.sources])];
   }
   s.catalogue_updates=[...(s.catalogue_updates||[]),secondVideoUpdate];
  }
  const collectionUpdate='2026-10-26-bili-sigrika-verina-shorekeeper';
  if(!(s.catalogue_updates||[]).includes(collectionUpdate)){
   const added=PLANNER_SEED.teams.find(t=>t.members.includes('西格莉卡')&&t.members.includes('维里奈')&&t.members.includes('守岸人'));
   if(added){
    const old=s.teams.find(t=>identity(t)===identity(added));
    if(!old)s.teams.push(clone(added));
    else{old.sources=[...new Set([...old.sources,...added.sources])];}
   }
   s.catalogue_updates=[...(s.catalogue_updates||[]),collectionUpdate];
  }
  // Separate legacy effective team scores into fixed base and personal multiplier.
  for(const t of s.teams){
   const standard=PLANNER_SEED.teams.find(x=>identity(x)===identity(t)&&x.rover_attribute===t.rover_attribute);
   const previousBase=t.default_priority??standard?.default_priority??1;
   if(t.user_weight===undefined){
    t.legacy_priority=t.priority;
    t.user_weight=Number(((t.priority??previousBase)/(previousBase||1)).toFixed(8));
   }
   t.priority=standard?.default_priority??1;
  }
  // Source review updates metadata only. Existing user scores and toggles are authoritative.
  for(const t of s.teams){
   const standard=PLANNER_SEED.teams.find(x=>identity(x)===identity(t)&&x.rover_attribute===t.rover_attribute);
   if(standard){
    t.default_priority=standard.default_priority??standard.priority;
    t.default_enabled=standard.default_enabled??standard.enabled;
    if(standard.source_audit)t.source_audit=clone(standard.source_audit);
    t.sources=[...new Set([...(t.sources||[]),...standard.sources])];
   }
  }
  const reviewedUpdate='2026-10-26-reviewed-video-additions-v2';
  if(!(s.catalogue_updates||[]).includes(reviewedUpdate)){
   for(const t of PLANNER_SEED.teams.filter(x=>x.origin==='bilibili_research')){
    if(!s.teams.some(x=>identity(x)===identity(t)&&x.rover_attribute===t.rover_attribute))s.teams.push(clone(t));
   }
   s.catalogue_updates=[...(s.catalogue_updates||[]),reviewedUpdate];
  }
  const workshopOffUpdate='2026-10-26-workshop-without-matrix-off';
  if(!(s.catalogue_updates||[]).includes(workshopOffUpdate)){
   for(const t of s.teams){
    const proof=t.source_audit?.matched||[];
    if(proof.some(p=>p.kind==='workshop')&&!proof.some(p=>(p.kind==='workshop'||p.kind==='video')&&p.matrix)){
     t.enabled=false;t.locked=false;
    }
   }
   s.catalogue_updates=[...(s.catalogue_updates||[]),workshopOffUpdate];
  }
  const videoOnlyUpdate='2026-10-26-three-source-tiers-final';
  if(!(s.catalogue_updates||[]).includes(videoOnlyUpdate)){
   for(const t of s.teams){
    const standard=PLANNER_SEED.teams.find(x=>identity(x)===identity(t)&&x.rover_attribute===t.rover_attribute);
    if(standard){
     t.enabled=standard.default_enabled;
     if(!t.enabled)t.locked=false;
    }
   }
   s.catalogue_updates=[...(s.catalogue_updates||[]),videoOnlyUpdate];
  }
  const recheckUpdate='2026-10-26-disabled-evidence-recheck-v1';
  if(!(s.catalogue_updates||[]).includes(recheckUpdate)){
   for(const t of s.teams){
    const standard=PLANNER_SEED.teams.find(x=>identity(x)===identity(t)&&x.rover_attribute===t.rover_attribute);
    if(standard?.source_audit?.recheck_confirmed)t.enabled=true;
   }
   s.catalogue_updates=[...(s.catalogue_updates||[]),recheckUpdate];
  }
  const requestedAddition='2026-10-26-aemeath-lupa-denia';
  if(!(s.catalogue_updates||[]).includes(requestedAddition)){
   const added=PLANNER_SEED.teams.find(t=>t.id==='f2628f398681fa62');
   if(added&&!s.teams.some(t=>identity(t)===identity(added)&&t.rover_attribute===added.rover_attribute))s.teams.push(clone(added));
   s.catalogue_updates=[...(s.catalogue_updates||[]),requestedAddition];
  }
  const seen=new Set(),ids=new Set();
  for(const t of s.teams){
   if(typeof t.id!=='string'||ids.has(t.id)||t.members?.length!==3||new Set(t.members).size!==3||t.members.some(n=>!names.has(n)))throw Error('队伍成员或编号无效');
   ids.add(t.id);const signature=identity(t)+'|'+t.rover_attribute;
   if(seen.has(signature))throw Error('存在重复队伍');seen.add(signature);
   if(t.members.includes('漂泊者')&&!['衍射','湮灭','气动','导电'].includes(t.rover_attribute))throw Error('请选择漂泊者属性');
   if(!Number.isFinite(t.user_weight??1)||(t.user_weight??1)<0||(t.user_weight??1)>1000||typeof t.enabled!=='boolean')throw Error('队伍权重或开关无效');
   if(!Array.isArray(t.axes)||!Array.isArray(t.sources)||typeof t.note!=='string'||typeof t.evidence!=='string')throw Error('队伍资料无效');
   if(t.axes.some(a=>typeof a.id!=='string'||typeof a.name!=='string'||typeof a.description!=='string')||new Set(t.axes.map(a=>a.id)).size!==t.axes.length)throw Error('输出轴无效');
   if(t.selected_axis&&!t.axes.some(a=>a.id===t.selected_axis))throw Error('输出轴选择无效');
  }
  return s;
 }
 function read(){
  const raw=localStorage.getItem(key);
  if(raw&&!localStorage.getItem(key+'.before-update'))localStorage.setItem(key+'.before-update',raw);
  return validate(raw?JSON.parse(raw):clone(PLANNER_SEED));
 }
 function save(s){
  const next=validate(clone(s)),old=localStorage.getItem(key);
  if(old&&JSON.parse(old).revision!==s.revision)throw Error('其他页面已修改配置，请刷新后重试');
  next.revision=crypto.randomUUID();
  if(old)localStorage.setItem(key+'.previous',old);
  localStorage.setItem(key,JSON.stringify(next));return next;
 }
 function restorePrevious(){
  const raw=localStorage.getItem(key+'.previous')||localStorage.getItem(key+'.before-update');
  if(!raw)throw Error('没有可恢复的历史配置');
  const previous=validate(JSON.parse(raw));previous.revision=read().revision;
  return save(previous);
 }
 function optimize(budget,candidates,score){
  const best=new Map();for(const t of candidates){const k=identity(t);if(!best.has(k)||score(t)>score(best.get(k)))best.set(k,t)}
  const teams=[...best.values()];if(!teams.length)return [];
  const constraints={},variables={},ints={};
  Object.entries(budget).forEach(([n,v])=>constraints['c:'+n]={max:v});
  teams.forEach((t,i)=>{const k='x'+i;variables[k]={count:1,score:score(t),['u'+i]:1};t.members.forEach(n=>variables[k]['c:'+n]=1);constraints['u'+i]={max:1};ints[k]=1});
  const model={optimize:'count',opType:'max',constraints,variables,ints};
  let result=solver.Solve(model);if(!result.feasible||!result.bounded)throw Error('配队求解失败');
  constraints.count={equal:Math.round(result.result)};model.optimize='score';
  result=solver.Solve(model);if(!result.feasible||!result.bounded)throw Error('配队得分求解失败');
  return teams.filter((_,i)=>result['x'+i]>.5);
 }
 function plan(s,options){
  const all=options.all_characters,budget={},weights={},chars=Object.fromEntries(s.characters.map(c=>[c.name,c]));
  for(const c of s.characters){budget[c.name]=c.released&&(c.available||all)?c.weekly??c.base:0;weights[c.name]=Number((recency(c)*(all&&!c.available?1:(c.chain+1)*c.weight)).toFixed(6))}
  const score=t=>t.priority*(t.user_weight??1)*sourceMultiplier(t)*t.members.reduce((v,n)=>v*weights[n],1);
  const remaining={...budget},fixed=s.teams.filter(t=>t.locked),fixedSets=new Set();
  for(const t of fixed){if(!t.enabled||fixedSets.has(identity(t)))throw Error('必选队伍禁用或重复');fixedSets.add(identity(t));for(const n of t.members)if(--remaining[n]<0)throw Error('必选队伍体力不足：'+n)}
  const candidates=s.teams.filter(t=>t.enabled&&!t.locked&&!fixedSets.has(identity(t))&&t.members.every(n=>remaining[n]>0)&&(options.include_inferred||t.evidence!=='机制推导·待验证'||t.source_audit?.matched.some(p=>p.kind==='wiki'||(['video','workshop'].includes(p.kind)&&p.matrix))));
  const selected=[...fixed,...optimize(remaining,candidates,score)].map(clone);
  for(const t of selected.filter(t=>!t.locked))for(const n of t.members)remaining[n]--;
  const recommended_count=selected.length;
  if(options.fill_roles===true){
   const slots=['主C','辅助','奶妈'].map(r=>s.characters.filter(c=>remaining[c.name]>0&&c.roles.includes(r)).map(c=>c.name));
   const excluded=new Set([...selected,...s.teams.filter(t=>!t.enabled)].map(identity)),fill=new Map();
   for(const a of slots[0])for(const b of slots[1])for(const c of slots[2]){
    const members=[a,b,c],k=[...members].sort().join('|');if(new Set(members).size!==3||excluded.has(k)||fill.has(k))continue;
    fill.set(k,{id:'fill-'+k,members,rover_attribute:members.includes('漂泊者')?(a==='漂泊者'?'湮灭':'导电'):'',enabled:true,priority:1,note:'按剩余体力和角色定位补充，尚未验证配合。',evidence:'主辅奶·兜底',sources:[],axes:[],selected_axis:'',assigned_roles:['主C','辅助','奶妈']});
   }
   const extra=optimize(remaining,[...fill.values()],score);selected.push(...extra);for(const t of extra)for(const n of t.members)remaining[n]--;
  }
  const role_count=selected.length-recommended_count;
  if(options.fill_solo===true&&remaining['丹瑾']>0){
   const unused=Object.keys(remaining).filter(n=>n!=='丹瑾'&&remaining[n]>0);
   const excluded=new Set([...selected,...s.teams.filter(t=>!t.enabled)].map(identity)),fill=[];
   for(let i=0;i<unused.length;i++)for(let j=i+1;j<unused.length;j++){
    const members=['丹瑾',unused[i],unused[j]],k=[...members].sort().join('|');if(excluded.has(k))continue;
    fill.push({id:'solo-'+k,members,rover_attribute:members.includes('漂泊者')?'衍射':'',enabled:true,priority:1,note:'用户确认丹瑾可单人完成；另两位仅使用其他配队后剩余的体力，不代表输出配合。',evidence:'丹瑾单人·余量补位',sources:[],axes:[],selected_axis:'',assigned_roles:['主C','补位','补位']});
   }
   const extra=optimize(remaining,fill,score);selected.push(...extra);for(const t of extra)for(const n of t.members)remaining[n]--;
  }
  const solo_count=selected.length-recommended_count-role_count;
  for(const t of selected){t.character_weights=t.members.map(n=>weights[n]);t.unowned_members=t.members.filter(n=>!chars[n].available);t.weight_product=t.character_weights.reduce((a,b)=>a*b,1);t.source_multiplier=sourceMultiplier(t);t.team_score=Number(score(t).toFixed(6))}
  selected.sort((a,b)=>a.team_score-b.team_score||a.id.localeCompare(b.id));
  return {selected,count:selected.length,recommended_count,fallback_count:role_count,solo_count,remaining,planning_weights:weights,all_characters:all,eligible:candidates.length+fixed.length,total_stamina:Object.values(budget).reduce((a,b)=>a+b,0),total_score:Number(selected.reduce((v,t)=>v+t.team_score,0).toFixed(6))};
 }
 function exportConfig(s){
  const current=validate(clone(s));
  return {format:'matrix-planner-v2',preferences:clone(current.preferences||{}),characters:current.characters.map(c=>({name:c.name,available:c.available,base:c.base,weekly:c.weekly,roles:c.roles,chain:c.chain,weight:c.weight})),
   teams:current.teams.map(t=>({id:t.id,members:t.members,rover_attribute:t.rover_attribute,user_weight:t.user_weight??1,enabled:t.enabled,locked:!!t.locked,note:t.note,axes:t.axes,selected_axis:t.selected_axis}))};
 }
 function importConfig(data){
  if(data.format==='matrix-planner-v1')return validate(clone(data.state));
  if(data.format!=='matrix-planner-v2'||!Array.isArray(data.characters)||!Array.isArray(data.teams))throw Error('配置文件格式不支持');
  const current=validate(clone(PLANNER_SEED));
  current.characters=data.characters.map(c=>{const base=current.characters.find(x=>x.name===c.name);return {...base,...Object.fromEntries(['name','available','base','weekly','roles','chain','weight'].map(k=>[k,c[k]])),healer:c.roles?.includes('奶妈')}});
  current.preferences=clone(data.preferences||{});
  current.teams=data.teams.map(t=>{
   const base=PLANNER_SEED.teams.find(x=>identity(x)===identity(t)&&x.rover_attribute===t.rover_attribute);
   const personal=Object.fromEntries(['id','members','rover_attribute','user_weight','enabled','locked','note','axes','selected_axis'].map(k=>[k,t[k]]));
   return {...(base?clone(base):{priority:1,default_priority:1,origin:'manual',evidence:'自定义',sources:[]}),...personal};
  });
  return validate(current);
 }
 return {read,save,validate,plan,restorePrevious,exportConfig,importConfig};

}
const LocalPlanner=createLocalPlanner();
