import Link from "next/link";

import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function LoginPage() {
  const [statusRes, initRes] = await Promise.all([
    fetchApiResult("/api/system/status", { status: "不可达" }),
    fetchApiResult("/api/init/status", { steps: [] as string[], done: [] as string[], finished: false })
  ]);
  const status = statusRes.data;
  const initStatus = initRes.data;
  const pageState = resolvePageState([statusRes, initRes], status.status !== "不可达");

  return (
    <main className="container">
      <h1>登录入口</h1>
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} />
      <div className="grid">
        <div className="card">
          <h2>本地模式说明</h2>
          <p>当前阶段未启用真实账号认证，可直接进入总览与业务流程页面。</p>
          <p>
            <Link href="/dashboard">进入总览看板</Link>
          </p>
        </div>
        <div className="card">
          <h2>环境检查</h2>
          <p>接口状态：{status.status}</p>
          <p>初始化完成：{initStatus.finished ? "是" : "否"}</p>
        </div>
      </div>
    </main>
  );
}
