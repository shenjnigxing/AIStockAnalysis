// Execute the actual route after TS transpilation, with an isolated upstream.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const ts=require(require.resolve('typescript',{paths:[process.cwd()+'/apps/web']}));
const input=fs.readFileSync('apps/web/app/api/ops/route.ts','utf8');
const compiled=ts.transpileModule(input,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const exportsObject={};const calls=[];
vm.runInNewContext(compiled,{
  exports:exportsObject,
  require(name){assert.equal(name,'next/server');return {NextResponse:{json:(body,init)=>({body,status:init?.status??200})}};},
  process:{env:{API_BASE_URL:'http://127.0.0.1:8000',AISTOCK_ADMIN_TOKEN:'never-forward-this-secret'}},
  AbortSignal,
  async fetch(url,init){calls.push({url,init});return {ok:true,status:200,text:async()=>'{"items":[]}'}}
});
function request(origin,contentType,body){
  const headers=new Headers();if(origin)headers.set('origin',origin);if(contentType)headers.set('content-type',contentType);
  return {headers,nextUrl:{origin:'http://localhost:3000'},json:async()=>body};
}
(async()=>{
  const safe={path:'/api/candidates/latest',method:'GET'};
  assert.equal((await exportsObject.POST(request(null,'application/json',safe))).status,403);
  assert.equal((await exportsObject.POST(request('https://evil.example','application/json',safe))).status,403);
  assert.equal((await exportsObject.POST(request('http://localhost:3000','text/plain',safe))).status,415);
  for(const path of ['/api/risk/kill-switch/disable','/api/settings/update','/api/admin/restore','/api/live/order']){
    assert.equal((await exportsObject.POST(request('http://localhost:3000','application/json',{path}))).status,403);
  }
  assert.equal(calls.length,0);
  assert.equal((await exportsObject.POST(request('http://localhost:3000','application/json',safe))).status,200);
  assert.equal(calls.length,1);
  assert.deepEqual(Object.keys(calls[0].init.headers),['Content-Type']);
  console.log('PASS actual ops handler: origin, JSON, operation whitelist, no privileged credential forwarding');
})().catch(error=>{console.error(error);process.exitCode=1});
