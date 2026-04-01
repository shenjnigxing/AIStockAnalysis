import Link from "next/link";

import { AutoRefresh } from "../components/auto-refresh";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function LoginPage() {
  const [statusRes, initRes] = await Promise.all([
    fetchApiResult("/api/system/status", { status: "unreachable" }),
    fetchApiResult("/api/init/status", { steps: [] as string[], done: [] as string[], finished: false })
  ]);
  const status = statusRes.data;
  const initStatus = initRes.data;
  const pageState = resolvePageState([statusRes, initRes], status.status !== "unreachable");

  return (
    <main className="container">
      <h1>Login</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} />
      <div className="grid">
        <div className="card">
          <h2>Phase 0 Local Mode</h2>
          <p>Authentication is not enabled in this scaffold. Continue directly to dashboard and workflow pages.</p>
          <p>
            <Link href="/dashboard">Enter Dashboard</Link>
          </p>
        </div>
        <div className="card">
          <h2>Environment Check</h2>
          <p>API: {status.status}</p>
          <p>Init Finished: {initStatus.finished ? "yes" : "no"}</p>
        </div>
      </div>
    </main>
  );
}
