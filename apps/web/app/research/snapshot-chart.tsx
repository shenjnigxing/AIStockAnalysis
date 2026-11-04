'use client';
import {useEffect,useState} from 'react';
export type SnapshotPoint={id?:number;kind:string;symbol:string;value:number;unit:string;freshness:string;source_id:string;source_display_time:string;collected_at_utc:string;cache_age_seconds:number};
export function displayTime(value:string){const d=new Date(value);return Number.isNaN(d.getTime())?'时间未知':d.toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});}
export function SnapshotChart({points,symbol,loading,error}:{points:SnapshotPoint[];symbol:string;loading:boolean;error:string}){
 const [active,setActive]=useState(0),[showTable,setShowTable]=useState(false);
 useEffect(()=>{setActive(Math.max(0,points.length-1));},[points]);
 const selectedIndex=Math.max(0,Math.min(active,points.length-1));
 const current=points[selectedIndex];
 const min=points.length?Math.min(...points.map(p=>p.value)):0,max=points.length?Math.max(...points.map(p=>p.value)):0;
 const span=max-min||Math.max(Math.abs(max)*.01,1),floor=min-(span*.15),ceiling=max+(span*.15);
 const x=(i:number)=>48+i*640/Math.max(points.length-1,1),y=(value:number)=>174-(value-floor)/(ceiling-floor)*142;
 const path=points.map((p,i)=>`${i?'L':'M'}${x(i)},${y(p.value)}`).join(' ');
 return <section className="rt-panel rt-chart-panel"><div className="rt-panel-head"><div><span className="rt-index">02</span><h2>{symbol||'标的'} · 采集快照轨迹</h2></div><span className="rt-badge">非日 K · 非收益曲线</span></div>
 <div className="rt-chart-description">按采集先后等距展示公开报价。采集间隔不固定，点间连线仅帮助阅读，不补齐缺失行情。</div>
 {loading?<div className="rt-chart-empty" role="status">正在读取已保存的快照…</div>:error?<div className="rt-error" role="alert">轨迹读取失败：{error}</div>:points.length<2?<div className="rt-chart-empty"><span>⌁</span><strong>{points.length===1?'已保存 1 个快照，尚不足以观察变化':'选择标的，查看真实采集记录'}</strong><p>{points.length===1?`${points[0].value.toLocaleString('zh-CN')} ${points[0].unit} · ${displayTime(points[0].collected_at_utc)}`:'尚无历史记录时保持留白，不绘制模拟走势。'}</p></div>:<>
 <div className="rt-chart-inspection" aria-live="polite"><div><small>采集时间</small><strong>{current?displayTime(current.collected_at_utc):'—'}</strong></div><div><small>快照值 / {current?.unit}</small><strong>{current?.value.toLocaleString('zh-CN',{maximumFractionDigits:6})}</strong></div><div><small>观测范围</small><strong>{min.toLocaleString('zh-CN')} — {max.toLocaleString('zh-CN')}</strong></div></div>
 <svg className="rt-chart" viewBox="0 0 720 210" role="img" aria-label={`${symbol} 的 ${points.length} 个采集快照，使用下方滑块逐点查看`} onPointerMove={e=>{const rect=e.currentTarget.getBoundingClientRect();setActive(Math.max(0,Math.min(points.length-1,Math.round(((e.clientX-rect.left)/rect.width*720-48)/640*(points.length-1)))));}}>
 {[0,.5,1].map(t=><g key={t}><line x1="48" x2="688" y1={32+142*t} y2={32+142*t} stroke="#2b3d52" strokeDasharray="3 5"/><text x="5" y={36+142*t} fill="#96a9bf" fontSize="9">{(ceiling-(ceiling-floor)*t).toLocaleString('zh-CN',{maximumFractionDigits:2})}</text></g>)}
 <path d={path} fill="none" stroke="#57d7b3" strokeWidth="2.5" strokeLinejoin="round"/>{current&&<><line x1={x(selectedIndex)} x2={x(selectedIndex)} y1="25" y2="180" stroke="#6d8b9e" strokeDasharray="4 4"/><circle cx={x(selectedIndex)} cy={y(current.value)} r="5" fill="#a1f6db" stroke="#152132" strokeWidth="2"/></>}
 <text x="48" y="201" fill="#96a9bf" fontSize="10">{displayTime(points[0].collected_at_utc)}</text><text x="688" y="201" textAnchor="end" fill="#96a9bf" fontSize="10">{displayTime(points[points.length-1].collected_at_utc)}</text></svg>
 <label className="rt-chart-slider">逐点查看 <input aria-label="查看采集快照" type="range" min="0" max={points.length-1} value={selectedIndex} onChange={e=>setActive(Number(e.target.value))}/><span>{selectedIndex+1} / {points.length}</span></label>
 <p className="rt-chart-source">当前点：{current?.source_id} · 源时间 {current?.source_display_time||'未提供'} · {current?.freshness}</p>
 </>}
 {points.length>0&&<><button className="rt-data-toggle" aria-expanded={showTable} onClick={()=>setShowTable(!showTable)}>{showTable?'收起':'展开'}快照数据表 ({points.length})</button>{showTable&&<div className="rt-table-scroll"><table aria-label="采集快照数据"><thead><tr><th>采集时间</th><th>值 / 单位</th><th>源时间</th><th>来源</th></tr></thead><tbody>{points.map((p,i)=><tr key={p.id??i}><td>{displayTime(p.collected_at_utc)}</td><td>{p.value.toLocaleString('zh-CN')} {p.unit}</td><td>{p.source_display_time||'未提供'}</td><td>{p.source_id}</td></tr>)}</tbody></table></div>}</>}
 </section>;
}
