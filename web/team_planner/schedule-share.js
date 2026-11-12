/* A versioned, self-contained code for one schedule. No account settings. */
const ScheduleShare=(()=>{
 const prefix='WWMP1:',limit=2_000_000;
 function encode(plan){
  const rows=plan.rows.map(row=>[SchedulePlanner.fixed(plan,row),SchedulePlanner.form(plan,row)]);
  const cells=plan.cells.map(c=>[plan.rows.indexOf(c.row),plan.columns.findIndex(col=>col.id===c.column),c.members,c.label,c.rover_attribute||'']);
  const data={v:1,name:plan.name,rows,columns:plan.columns.map(c=>c.name),cells};
  const bytes=new TextEncoder().encode(JSON.stringify(data));
  let binary='';for(let start=0;start<bytes.length;start+=8192)binary+=String.fromCharCode(...bytes.subarray(start,start+8192));
  return prefix+btoa(binary).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
 }
 function decode(code){
  if(typeof code!=='string'||code.length>limit)throw Error('排表代码过长');
  const compact=code.replace(/\s/g,'');
  if(!compact.startsWith(prefix))throw Error('请粘贴以 WWMP1: 开头的排表代码');
  const body=compact.slice(prefix.length);
  if(!body||!/^[A-Za-z0-9_-]+$/.test(body))throw Error('排表代码不完整或格式有误');
  let data;
  try{
   const binary=atob(body.replace(/-/g,'+').replace(/_/g,'/'));
   data=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(binary,c=>c.charCodeAt(0))));
  }catch{throw Error('排表代码不完整或已损坏，请重新复制')}
  const invalid=()=>{throw Error('排表代码中的行列或成员数据无效')};
  if(!data||data.v!==1||typeof data.name!=='string'||!data.name.trim()||data.name.length>60)invalid();
  if(!Array.isArray(data.rows)||!data.rows.length||data.rows.length>100||!Array.isArray(data.columns)||!data.columns.length||data.columns.length>50)invalid();
  if(!Array.isArray(data.cells)||data.cells.length>data.rows.length*data.columns.length)invalid();
  const plan={id:crypto.randomUUID(),name:data.name,rows:[],row_heads:{},row_fixed:{},row_attributes:{},columns:[],cells:[],layout_version:2};
  for(const entry of data.rows){
   if(!Array.isArray(entry)||entry.length!==2||!Array.isArray(entry[0])||entry[0].length>2||entry[0].some(n=>typeof n!=='string')||typeof entry[1]!=='string')invalid();
   const row='row-'+crypto.randomUUID();plan.rows.push(row);plan.row_fixed[row]=[...entry[0]];plan.row_heads[row]=entry[0][0]||null;
   if(entry[0].includes('漂泊者'))plan.row_attributes[row]=entry[1];
  }
  for(const name of data.columns){
   if(typeof name!=='string'||!name.trim()||name.length>30)invalid();
   plan.columns.push({id:crypto.randomUUID(),name});
  }
  for(const cell of data.cells){
   if(!Array.isArray(cell)||cell.length!==5)invalid();
   const [row,column,members,label,rover_attribute]=cell;
   if(!Number.isInteger(row)||row<0||row>=plan.rows.length||!Number.isInteger(column)||column<0||column>=plan.columns.length)invalid();
   if(!Array.isArray(members)||members.length>3||members.some(n=>typeof n!=='string')||typeof label!=='string'||label.length>24||typeof rover_attribute!=='string')invalid();
   plan.cells.push({row:plan.rows[row],column:plan.columns[column].id,members:[...members],label,rover_attribute});
  }
  return plan;
 }
 return {encode,decode};
})();
