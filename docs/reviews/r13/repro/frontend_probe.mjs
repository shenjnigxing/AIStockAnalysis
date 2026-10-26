import fs from 'node:fs';
import assert from 'node:assert/strict';
const root=process.cwd();
const market=fs.readFileSync(root+'/apps/web/app/research/market-data/page.tsx','utf8');
const qbody=market.slice(market.indexOf('  async function checkQuote(){'),market.indexOf('\n  return <main')).replace(' as Quote','');
let quote=null,error='',checking=false,selectedKind='us_equity',selectedSymbol='AAPL';
let resolveQuote;
const fetchQuote=()=>new Promise(resolve=>{resolveQuote=resolve;});
const makeQuote=new Function('kind','symbol','fetch','setQuote','setError','setChecking',qbody+';return checkQuote;');
const checkQuote=makeQuote(selectedKind,selectedSymbol,fetchQuote,x=>quote=x,x=>error=x,x=>checking=x);
const pending=checkQuote();
// The actual select onChange resets controls/quote but does not invalidate the old request.
selectedKind='etf';selectedSymbol='510300';quote=null;error='';
resolveQuote({status:200,ok:true,json:async()=>({kind:'us_equity',symbol:'AAPL',value:200})});
await pending;
assert.equal(quote.symbol,'AAPL');assert.equal(selectedSymbol,'510300');
console.log('FE-01 reproduced:',JSON.stringify({selectedKind,selectedSymbol,renderedQuote:quote,checking}));
const form=fs.readFileSync(root+'/apps/web/app/components/api-action-fields-form.tsx','utf8');
let submitBody=form.slice(form.indexOf('  const submit = async () => {'),form.indexOf('\n\n  return (',form.indexOf('  const submit = async () => {')));
submitBody=submitBody.replace('const payload: Record<string, unknown> = {}','const payload = {}').replace(' as OpsResponse','');
let calls=0,pendingTransition=false,inputError='not relevant',result={ok:true,data:'previous operation succeeded'};
const resolvers=[];
const fetchSlow=()=>{calls++;return new Promise(resolve=>resolvers.push(resolve));};
const makeSubmit=new Function('setInputError','fields','values','normalizeValue','setByPath','fetch','requestPath','method','setResult','refreshAfterSuccess','startTransition','router',submitBody+';return submit;');
function bind(fetcher){return makeSubmit(x=>inputError=x,[],{},()=>{},()=>{},fetcher,'/api/paper/orders','POST',x=>result=x,true,callback=>{pendingTransition=true;callback();},{refresh(){}});}
const submit=bind(fetchSlow);
const p1=submit(),p2=submit();
assert.equal(calls,2);assert.equal(pendingTransition,false);
console.log('FE-02 reproduced:',JSON.stringify({outboundMutations:calls,buttonDisabledByIsPending:pendingTransition}));
for(const resolve of resolvers)resolve({json:async()=>({ok:true,status:200,error:null,data:{order_id:1}})});
await Promise.all([p1,p2]);
const before=JSON.stringify(result);
const submitFail=bind(async()=>{throw new Error('NetworkError')});
let rejected=false;try{await submitFail();}catch(e){rejected=e.message==='NetworkError';}
assert.equal(rejected,true);assert.equal(inputError,null);assert.equal(JSON.stringify(result),before);
console.log('FE-03 reproduced:',JSON.stringify({promiseRejected:rejected,inputError,previousSuccessRemains:JSON.stringify(result)===before}));
