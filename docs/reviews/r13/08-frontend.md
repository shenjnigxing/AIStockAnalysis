# R13 独立审查 08：高级前端工程师

- 审查者：独立子代理 `/root/r13_frontend`；没有阅读其他角色报告。
- 基线：`c1802e6fbcaf4dae81d06cdb81babbe82febf38e`。
- 独立分支：`audit/r13-frontend`；工作目录为 `review-frontend`。
- 范围：行情查询控制状态、请求竞态、共用动作表单、旧推荐页字段及错误反馈；只新增本报告，不改产品代码。
- 方法：逐行代码审查；从实际组件源码抽取异步处理函数，以 Node.js 延迟 Promise/失败 fetch 执行。只去除两处 TypeScript 类型注解，不复刻处理逻辑。
- 限制：没有实际挂载 React、没有运行浏览器、没有截图或屏幕阅读器测试；不对视觉美观、对比度和响应式实际效果作通过结论。下面三项运行结果属于真实处理函数测试，第四项属于静态数据流证实。

## 结论

发现 **3 项 P1、1 项 P2**。当前 UI 不能保证“所选市场/标的与最终呈现响应一致”，共用动作表单也不能在网络请求期间阻止重复提交、处理未知结果。此前构建与常规成功路径测试通过不能覆盖这些时序。

| ID | 级别 | 状态 | 问题 |
|---|---|---|---|
| FE-01 | P1 | 处理函数运行证实 | 切换市场/标的后，旧查询响应仍回填报价 |
| FE-02 | P1 | 处理函数运行证实 | 请求期间按钮不进入 pending，连续点击发出重复 mutation |
| FE-03 | P1 | 处理函数运行证实 | 网络/响应解析异常未捕获，旧成功结果保留且没有错误反馈 |
| FE-04 | P2 | 静态数据流证实 | 成功采集/查询后，数据源诊断卡仍停留在首次加载的旧状态 |

## FE-01：行情查询没有响应身份/请求序号检查

**代码位置**：`apps/web/app/research/market-data/page.tsx:47-57`、`:84-89`。

**证据**：`checkQuote` 捕获发起请求时的 `kind/symbol`，收到任何成功响应就执行 `setQuote(await response.json())`。市场下拉框在查询期间仍可修改；它会清空旧报价，但没有 `AbortController`、请求序号或当前标的身份校验。代码输入框甚至只 `setSymbol`，不会清空已有报价。

**复现**：发起 `us_equity/AAPL` 查询，让 fetch 暂不返回；选择 `etf/510300`，再让旧请求返回 AAPL。实际函数执行后：

```json
{"selectedKind":"etf","selectedSymbol":"510300","renderedQuote":{"kind":"us_equity","symbol":"AAPL","value":200},"checking":false}
```

**影响**：用户选择的市场及采集命令已变成国内 ETF，结果区却出现旧美股报价。报价本身仍显示 AAPL，不能夸大为后端把 AAPL 改名为 ETF；问题是响应与当前选择脱节，且切换动作的清空被晚到响应撤销。

**最小修复**：每次查询记录递增 request ID 和规范化 `kind/symbol`；仅接纳仍匹配当前选择的响应；切换市场、修改代码、卸载时取消或失效旧请求，同时清理报价及检查状态。

**验收**：用延迟网络依次测试查询中切市场、改代码、返回旧请求；断言没有旧标的报价回填。再逆序返回两次不同请求，最终只呈现当前请求。

## FE-02：动作表单的 pending 只覆盖刷新，不覆盖写请求

**代码位置**：`apps/web/app/components/api-action-fields-form.tsx:88`、`:106-138`、`:199-200`；另一个组件 `api-action-form.tsx:31`、`:39-60`、`:84-85` 有相同结构。

**证据**：表单 `submit` 先执行并等待 `fetch('/api/ops')`；直到返回 `body.ok` 后才进入 `startTransition(() => router.refresh())`。按钮 `disabled` 仅关联该 transition 的 `isPending`，请求期间没有提交标志或同步请求锁。

**复现**：用两个暂不完成的 fetch，连续调用真实 `submit` 两次。实际输出：

```json
{"outboundMutations":2,"buttonDisabledByIsPending":false}
```

**影响**：网络慢时按钮仍显示可执行，用户连点可产生两个纸面下单/运行推荐/保存配置等写请求。此审查只证实 UI 发出重复 mutation，没有借此声称真实券商下单被绕过；实盘默认后端拒绝门禁仍存在。重复写是否都落库还取决于各后端接口的幂等保护。

**最小修复**：增加覆盖完整 `fetch + response.json` 生命周期的 `isSubmitting`，并以同步 ref/锁防止同一事件周期内重入；`finally` 释放；必要时生成并复用幂等键，后端也需独立去重。`useTransition` 仅负责刷新体验。

**验收**：延迟响应时双击、键盘重复激活只发一个请求；失败后可以重试；操作状态在发起请求瞬间变更。对真实 mutation 另做幂等重放验收。

## FE-03：写操作失败没有可见错误，旧成功结果仍保留

**代码位置**：`apps/web/app/components/api-action-fields-form.tsx:106-139`、`:198-206`；`api-action-form.tsx:39-61`、`:83-90`。

**证据**：输入验证只处理空字段/JSON语法；网络 `fetch` 和 `response.json()` 都没有 `try/catch/finally`。重新提交仅清 `inputError`，不清除旧 `result`。失败发生时不会调用 `setResult` 或设置输入外的错误状态，旧响应仍能在“返回结果”中展开。

**复现**：已有一次成功返回；下一次 fetch 抛 `NetworkError`。实际结果：

```json
{"promiseRejected":true,"inputError":null,"previousSuccessRemains":true}
```

**影响**：用户看不到“网络失败/提交结果未知”，仍能看到上一次成功数据，容易把旧响应当成本次结果并重试。不能把网络错误直接声明为“后端操作没有发生”，因为请求可能已经被后端执行但响应丢失。

**最小修复**：提交开始清理或明确归档旧结果；捕获网络和解析错误，显示与本次 request ID 绑定的错误；mutation 响应丢失显示“结果未知，请查询状态”，避免直接提示再次提交。反馈使用 `role="alert"`/状态区，成功数据也绑定对应请求。

**验收**：依次覆盖断网、超时、HTML错误页、无效JSON、后端已完成但响应丢失；不得残留未标旧的新成功显示，错误须可见且可被辅助技术宣布。

## FE-04：行情诊断卡不会随采集或查询更新

**代码位置**：`apps/web/app/research/market-data/page.tsx:33-46`、`:55`、`:71-75`。

**证据**：数据源/账户能力只在空依赖 `useEffect(..., [])` 中加载一次。查询成功只写 `quote`；页面没有重新读取 `sources`、没有刷新诊断按钮、也没有定时轮询。

**触发路径**：首次打开全空缓存页 → 按页面指引在终端采集 → 回到页面点“查看本地快照”。结果区可以显示新报价，但数据源卡的 `has_cached_snapshot` 和 `last_attempt_state` 仍是首次打开时的“暂无缓存/尚未采集”。反方向，首次加载成功后外部采集失败，卡也可能继续显示旧“最近采集成功”。此项根据明确数据流证实，未浏览器实跑。

**影响**：同页报价与诊断状态矛盾；源失败信息和新缓存状态需要用户自行刷新整个页面才能同步，降低故障诊断可信度。

**最小修复**：独立的可重用 `loadSources()`，查询完成后重新加载，提供显式“刷新诊断”及最后诊断时间；若轮询需限制频率、清理卸载，仍只读本地API。

**验收**：首次返回无缓存，后续本地采集产生快照；不刷新整页即可在报价查询后看到卡片更新；失败记录同样同步，接口部分失败不可清空另一块已成功数据。

## 可执行复现

在基线仓库根目录保存下列脚本为临时 `.mjs` 并执行 `node /tmp/r13-fe-harness.mjs`。脚本读取实际处理函数，不请求网络，不访问账户，不向API提交任何写入。

```javascript
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
```

执行结果：三项 `assert` 全部通过，输出见各问题。状态：**缺陷已复现，不代表产品通过**。

## 其余范围说明

- 对 `recommendations/page.tsx` 的静态检查显示旧页面仍叫“推荐榜单”，且 `llm_enabled` 标签仍写“启用大模型修正”（行38），与已修后的后端“LLM不改数值”语义不一致；建议更名为“生成解释”。本项是附带文案建议，未计入上述四项缺陷，避免把旧链路整体门禁问题重复计数。
- 没有对行情值、第三方源单位、收益模型、私有账户权限作专业结论；这些需对应角色和端到端门禁验证。
- 没有把之前的 194 项后端或 13 项云浏览器测试冒充本角色新跑的测试；本角色只执行本文 Node 处理函数 harness。
