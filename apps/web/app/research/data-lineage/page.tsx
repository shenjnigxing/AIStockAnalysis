"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import "./lineage.css";

type Release = {
  id:number; fingerprint:string; source_id:string; asset_class:string;
  product_type:string; symbol:string; venue:string; currency:string;
  adjustment:string; volume_unit:string; date_from:string; date_to:string;
  collected_at_utc:string; row_count:number; raw_sha256:string; rows_sha256:string;
  status:string; quality_state:string; pit_verified:boolean; research_eligible:boolean;
};
type Readiness = {
  recorded_release_count:number; recorded_observation_count:number;
  latest_release:Release|null; historical_pit_verified:boolean;
  can_generate_real_recommendations:boolean; data_state:string; missing:string[];
};
type Detail = {release:Release; integrity:string; observations:Array<{date:string;close:number}>};

export default function DataLineagePage(){
  const [status,setStatus]=useState<Readiness|null>(null);
  const [releases,setReleases]=useState<Release[]>([]);
  const [detail,setDetail]=useState<Detail|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [selected,setSelected]=useState<number|null>(null);
  useEffect(()=>{
    let active=true;
    Promise.all([
      fetch("/api/research/v3/datasets/readiness",{cache:"no-store"}),
      fetch("/api/research/v3/datasets/releases?limit=30",{cache:"no-store"}),
    ]).then(async ([a,b])=>{
      if(!a.ok||!b.ok) throw new Error("数据版本诊断服务暂时不可用");
      return Promise.all([a.json(),b.json()]);
    }).then(([ready,history])=>{
      if(!active)return;
      setStatus(ready as Readiness);setReleases(history.items as Release[]);
    }).catch(e=>{if(active)setError(e instanceof Error?e.message:"无法读取数据血缘");})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[]);
  async function inspect(id:number){
    setSelected(id);setDetail(null);setError("");
    try{
      const response=await fetch(`/api/research/v3/datasets/releases/${id}`,{cache:"no-store"});
      if(!response.ok) throw new Error(response.status===409?"数据哈希校验失败；此版本不可用":"未能读取或验证版本");
      setDetail(await response.json() as Detail);
    }catch(e){setError(e instanceof Error?e.message:"校验失败");}
  }
  return <div className="lineage-page">
    <div className="lineage-crumb"><Link href="/research/assets">← 多资产研究</Link> / 数据血缘 / R1</div>
    <div className="lineage-heading"><div><small>DATASET RELEASES · DATA TRUST</small><h1>数据发布与来源审查</h1>
      <p>区分“这次供应商返回的数据是什么”与“当年交易时点是否已知”。版本被保存并不代表允许真实推荐。</p></div>
      <span>R1 · PROVENANCE</span>
    </div>
    <div className="lineage-warning" role="status"><strong>真实推荐仍被阻断</strong>
      <p>此页面只展示已记录的供应商响应和数据库一致性。尚无历史 PIT / 交易日历 / 复权事件核验，也未通过样本外模型测试。不会从页面发起供应商采集、下单或发送消息。</p>
    </div>
    {loading&&<div className="lineage-empty">正在读取数据版本状态…</div>}
    {error&&<div className="lineage-error" role="alert">{error}</div>}
    {!loading&&status&&<>
      <div className="lineage-stats">
        <div><span>发布版本</span><strong>{status.recorded_release_count}</strong><small>供应商响应记录</small></div>
        <div><span>价格观测点</span><strong>{status.recorded_observation_count}</strong><small>独立版本内留存</small></div>
        <div><span>历史 PIT 验证</span><strong>未通过</strong><small>没有可宣称的历史重演</small></div>
        <div><span>实际候选输出</span><strong>禁止</strong><small>不自动发布市场推荐</small></div>
      </div>
      <section className="lineage-panel">
        <div className="lineage-panel-top"><div><small>01 / RELEASE HISTORY</small><h2>供应商数据版本</h2></div><span>只读 · 最多 30 个版本</span></div>
        {releases.length===0?<div className="lineage-empty"><strong>暂无供应商数据发布记录</strong>
          <p>系统不会使用演示行情或旧数据库填补。正式采集仅允许由服务器管理员通过受保护接口执行。</p>
          </div>:<div className="lineage-scroller"><table><thead><tr><th>版本 / 标的</th><th>来源</th><th>范围</th><th>采集时刻 UTC</th><th>行数</th><th>核查</th></tr></thead>
          <tbody>{releases.map(r=><tr key={r.id}><td><strong>{r.symbol}</strong><small>#{r.id} · {r.asset_class}/{r.product_type}</small></td>
            <td>{r.source_id}</td><td>{r.date_from} → {r.date_to}</td><td>{r.collected_at_utc}</td>
            <td>{r.row_count}</td><td><button type="button" onClick={()=>void inspect(r.id)}>核对指纹 →</button></td>
          </tr>)}</tbody></table></div>}
      </section>
      {selected!==null&&detail&&<section className="lineage-panel">
        <div className="lineage-panel-top"><div><small>02 / INTEGRITY</small><h2>版本 #{selected} 校验结果</h2></div><span>内容哈希匹配，不等于真实 PIT</span></div>
        <div className="lineage-hashes">
          <div><span>release fingerprint</span><code>{detail.release.fingerprint}</code></div>
          <div><span>provider frame SHA256</span><code>{detail.release.raw_sha256}</code></div>
          <div><span>normalized observations SHA256</span><code>{detail.release.rows_sha256}</code></div>
        </div>
        <p>内容一致性：{detail.integrity}。资产：{detail.release.asset_class}，复权：{detail.release.adjustment}，体量单位：{detail.release.volume_unit}。此版本仍标为 <b>{detail.release.status}</b>，不得用于真实荐股。</p>
      </section>}
      <section className="lineage-panel">
        <div className="lineage-panel-top"><div><small>03 / RELEASE GATES</small><h2>仍需补足的验证</h2></div></div>
        <ul className="lineage-missing">{status.missing.map(v=><li key={v}>{v}</li>)}</ul>
      </section>
    </>}
  </div>;
}
