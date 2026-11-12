/* Manual schedules share character data, but use the full released roster. */
const SchedulePlanner=(()=>{
 function current(configuration){return configuration.schedules.plans.find(p=>p.id===configuration.schedules.active_id)}
 const fixed=(plan,row)=>plan.row_fixed?.[row]??(Object.hasOwn(plan.row_heads||{},row)?(plan.row_heads[row]?[plan.row_heads[row]]:[]):[row]);
 const head=(plan,row)=>fixed(plan,row)[0]||null;
 const form=(plan,row)=>plan.row_attributes?.[row]||'衍射';
 function compact(plan){
  const ordered=plan.rows.map(row=>plan.cells.filter(c=>c.row===row).sort((a,b)=>plan.columns.findIndex(col=>col.id===a.column)-plan.columns.findIndex(col=>col.id===b.column)));
  const length=Math.max(1,...ordered.map(cells=>cells.length));
  while(plan.columns.length<length)plan.columns.push({id:crypto.randomUUID(),name:'列'+(plan.columns.length+1)});
  plan.columns=plan.columns.slice(0,length);
  ordered.forEach(cells=>cells.forEach((cell,index)=>cell.column=plan.columns[index].id));
 }
 function migrate(plan){
  plan.row_heads??={};plan.row_attributes??={};plan.row_fixed??={};
  if(plan.layout_version!==2){compact(plan);plan.layout_version=2}
 }
 function analyse(plan,characters){
  const budget=Object.fromEntries(characters.map(c=>[c.name,c.released?(c.weekly??c.base):0]));
  const usage=Object.fromEntries(characters.map(c=>[c.name,0]));
  for(const cell of plan.cells)for(const name of [...fixed(plan,cell.row),...cell.members])usage[name]=(usage[name]||0)+1;
  const exceeded=characters.filter(c=>usage[c.name]>budget[c.name]).map(c=>({name:c.name,used:usage[c.name],limit:budget[c.name]}));
  return {usage,budget,exceeded,incomplete:plan.cells.filter(c=>c.members.length+fixed(plan,c.row).length<3).length};
 }
 function move(plan,from,to){
  const source=plan.cells.find(c=>c.row===from.row&&c.column===from.column);
  if(!source)return false;
  const target=plan.cells.find(c=>c.row===to.row&&c.column===to.column);
  if(!plan.rows.includes(to.row)||!plan.columns.some(c=>c.id===to.column))throw Error('目标位置不存在');
  if(source.members.some(n=>fixed(plan,to.row).includes(n))||target?.members.some(n=>fixed(plan,from.row).includes(n)))throw Error('固定角色与队员重复，请先移动队员');
  if(source.members.length+fixed(plan,to.row).length>3||target&&target.members.length+fixed(plan,from.row).length>3)throw Error('目标行固定位数量不同，队伍会超过三人');
  Object.assign(source,to);
  if(target&&target!==source)Object.assign(target,from);
  return true;
 }
 function setFixed(plan,row,names,attribute='衍射'){
  if(!plan.rows.includes(row))throw Error('目标行不存在');
  if(names.length>2||new Set(names).size!==names.length)throw Error('固定位最多两人，且不能重复');
  const cells=plan.cells.filter(c=>c.row===row);
  if(cells.some(cell=>cell.members.filter(n=>!names.includes(n)).length+names.length>3))throw Error('固定后队伍会超过三人，请先移出多余卡牌，或拖到已有固定角色上替换');
  plan.row_fixed[row]=names;
  plan.row_heads[row]=names[0]||null;
  if(names.includes('漂泊者'))plan.row_attributes[row]=attribute;else delete plan.row_attributes[row];
  for(const cell of plan.cells.filter(c=>c.row===row)){
   if(cell.members.some(n=>names.includes(n))){cell.members=cell.members.filter(n=>!names.includes(n));cell.label='';if(names.includes('漂泊者'))cell.rover_attribute=''}
  }
 }
 function swapRows(plan,from,to){
  const a=plan.rows.indexOf(from),b=plan.rows.indexOf(to);
  if(a<0||b<0)throw Error('行不存在');
  [plan.rows[a],plan.rows[b]]=[plan.rows[b],plan.rows[a]];
 }
 function swapColumns(plan,from,to){
  const a=plan.columns.findIndex(c=>c.id===from),b=plan.columns.findIndex(c=>c.id===to);
  if(a<0||b<0)throw Error('列不存在');
  [plan.columns[a],plan.columns[b]]=[plan.columns[b],plan.columns[a]];
 }
 function blank(configuration,name){
  return {id:crypto.randomUUID(),name,rows:configuration.characters.filter(c=>c.released&&c.roles.includes('奶妈')).map(c=>c.name),row_heads:{},row_fixed:{},row_attributes:{},columns:[{id:'c1',name:'列1'}],cells:[],layout_version:2};
 }
 return {current,head,fixed,form,compact,migrate,analyse,move,setFixed,swapRows,swapColumns,blank};
})();
