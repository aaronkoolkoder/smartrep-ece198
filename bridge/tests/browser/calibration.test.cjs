const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function browser() {
  const nodes = new Map(), events = {}, calls = [], sockets = [];
  function add(id) {
    const node = {textContent:'',dataset:{},disabled:false,hidden:false,
      classList:{add(){},remove(){},toggle(){}},addEventListener(name,fn){events[id+name]=fn},
      close(){this.open=false},showModal(){this.open=true},setAttribute(){}};
    nodes.set(id,node);return node;
  }
  ['#modal','#modal-body','#collapse-nav','#account-button','#staff-nav','#connection-label',
    '.connection-dot','#toast','#cal-progress','#cal-graph-status','[data-action="cal-done"]'].forEach(add);
  class WebSocket {constructor(url){this.url=url;this.readyState=1;sockets.push(this)}close(){}send(){}}
  const context={console,URL,WebSocket,location:{protocol:'https:',host:'phone.example',pathname:'/app',reload(){}},
    localStorage:{getItem(){return null},setItem(){}},navigator:{},
    window:{addEventListener(name,fn){events[name]=fn}},
    document:{querySelector:id=>nodes.get(id)||null,addEventListener(name,fn){events[name]=fn}},
    setTimeout(){return 1},clearTimeout(){},setInterval(){},
    fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>
      url==='/api/calibrations'?{calibration_id:42,target:3}:
      {calibration_id:42,cycles_seen:3,target:3,ready:true,result:null}}}};
  vm.createContext(context);
  const code=fs.readFileSync(path.join(__dirname,'../../static/app.js'),'utf8').replace(/\ninit\(\);/,'\n');
  vm.runInContext(code,context);
  const run=code=>vm.runInContext(code,context);
  run("state.calibrationId=42;state.calibrationStation='db-5lb';state.health={simulate:false};state.stations=[{id:'db-5lb',device_id:'clip-01'}]");
  return {nodes,events,calls,sockets,run,context};
}

test('Save remains disabled until the shared validator captures three full cycles',()=>{
  const b=browser(),button=b.nodes.get('[data-action="cal-done"]');
  b.run('onCalibrationProgress({calibration_id:42,cycles_seen:2,target:3,ready:false})');
  assert.equal(button.disabled,true);
  b.run('onCalibrationProgress({calibration_id:42,cycles_seen:3,target:3,ready:true})');
  assert.equal(button.disabled,false);
  assert.match(b.nodes.get('#cal-progress').textContent,/Three reps captured/);
});

test('calibrating another person subscribes to that person and restores status',async()=>{
  const b=browser();
  b.run("state.calibrationLogin={participant:'204417',pin:'0000'}");
  await b.run("beginCalibration('bent-over-row','db-5lb')");
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(b.sockets.at(-1).url,/participant=204417/);
  assert(b.calls.some(call=>call.url==='/api/calibrations/42'));
  assert.equal(b.nodes.get('[data-action="cal-done"]').disabled,false);
});

test('returning to a completed recording shows retry instead of submitting a null ID',async()=>{
  const b=browser();b.run('state.calibrationId=null');
  const button=b.nodes.get('[data-action="cal-done"]');button.dataset.action='cal-done';
  await b.events.click({target:{closest:()=>button}});
  assert.equal(b.calls.length,0);
  assert.equal(button.dataset.action,'cal-retry');
});

test('cancel closes recording and restores the normal participant subscription',()=>{
  const b=browser();b.run("state.calibrationSocketParticipant='204417';closeModal()");
  assert(b.calls.some(call=>call.url==='/api/calibrations/42/cancel'&&call.options.keepalive));
  assert.match(b.sockets.at(-1).url,/participant=123129/);
  assert.equal(b.run('state.calibrationId'),null);
});

test('disconnected graph shows a fault and does not pretend to have data',()=>{
  const b=browser();
  b.run("calibrationDeviceStatus({device_id:'clip-01',online:true,sensor_ok:false})");
  assert.match(b.nodes.get('#cal-graph-status').textContent,/MPU read failed/);
});


test('closing while Start is pending cancels the late recording instead of reserving it',async()=>{
  const b=browser();let resolve;
  const original=b.context.fetch;
  b.context.fetch=(url,options)=>url==='/api/calibrations'?new Promise(done=>resolve=done):original(url,options);
  b.run("state.calibrationId=null;state.calibrationLogin={participant:'123129',pin:'0000'}");
  const pending=b.run("beginCalibration('bent-over-row','db-5lb')");
  b.run('closeModal()');
  resolve({ok:true,json:async()=>({calibration_id:55,target:3})});
  await pending;
  assert.equal(b.run('state.calibrationId'),null);
  assert(b.calls.some(call=>call.url==='/api/calibrations/55/cancel'));
});

test('a late Save response cannot clear the ID of a newer calibration',async()=>{
  const b=browser();let resolve;
  b.context.fetch=()=>new Promise(done=>resolve=done);
  const button=b.nodes.get('[data-action="cal-done"]');button.dataset.action='cal-done';
  const pending=b.events.click({target:{closest:()=>button}});
  b.run('state.calibrationId=99');
  resolve({ok:true,json:async()=>({ok:true})});
  await pending;
  assert.equal(b.run('state.calibrationId'),99);
});
