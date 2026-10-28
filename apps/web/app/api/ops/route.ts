import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";
const READ_ONLY = [
  /^\/api\/candidates(?:\/latest|\/top100|\/[A-Za-z0-9_.-]+)?$/,
  /^\/api\/recommendation\/(?:latest|top|history(?:\/list)?|[A-Za-z0-9_.-]+)$/,
  /^\/api\/strategy\/(?:registry|config|signals)$/,
  /^\/api\/backtest\/(?:jobs|report\/\d+(?:\/detail)?|trades\/\d+|equity\/\d+)$/,
];
const MUTATIONS = [
  /^\/api\/screener\/run$/,
  /^\/api\/recommendation\/run$/,
  /^\/api\/backtest\/(?:run|compare)$/,
  /^\/api\/paper\/(?:order\/preview|orders(?:\/\d+\/cancel)?)$/,
];
function denied(status: number, error: string) {
  return NextResponse.json({ok:false,status,error,data:null}, {status});
}
export async function POST(request: NextRequest) {
  // No cookie/token authority is inferred from the browser. This route never
  // forwards administrator or ingestion credentials from server environment.
  const origin = request.headers.get("origin");
  if (!origin || origin !== request.nextUrl.origin || request.headers.get("sec-fetch-site") === "cross-site") {
    return denied(403, "same_origin_required");
  }
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    return denied(415, "application_json_required");
  }
  let body: {path?: unknown; method?: unknown; payload?: unknown};
  try { body = await request.json(); } catch { return denied(400,"invalid_json_body"); }
  if (!body || typeof body !== "object" || typeof body.path !== "string") return denied(400,"invalid_operation");
  const path=body.path;
  const method=typeof body.method === "string" ? body.method.toUpperCase() : "POST";
  if (!/^\/api\/[A-Za-z0-9_./?-]+(?:[=&A-Za-z0-9_.%-]*)?$/.test(path) || path.includes("..") || path.includes("%")) return denied(400,"invalid_path");
  const pathname=path.split("?")[0];
  const allowed = method === "GET" ? READ_ONLY.some(rule=>rule.test(pathname)) : method === "POST" && MUTATIONS.some(rule=>rule.test(pathname));
  if (!allowed) return denied(403,"operation_not_available_in_browser_use_authorized_local_admin_client");
  if (body.payload !== undefined && (!body.payload || typeof body.payload !== "object" || Array.isArray(body.payload))) return denied(400,"invalid_payload");
  try {
    const headers: Record<string,string>={"Content-Type":"application/json"};
    const key=request.headers.get("idempotency-key");
    if(key && key.length<=128 && /^[A-Za-z0-9_.:-]+$/.test(key)) headers["Idempotency-Key"]=key;
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,headers,cache:"no-store",signal:AbortSignal.timeout(15000),
      ...(method === "POST" ? {body:JSON.stringify(body.payload || {})} : {})
    });
    const raw=await response.text();
    let data:unknown=raw;try {data=JSON.parse(raw);} catch {}
    return NextResponse.json({ok:response.ok,status:response.status,error:response.ok?null:"request_failed",data});
  } catch {
    // Do not expose internal upstream URLs or environment-dependent errors.
    return denied(502,"upstream_unreachable_or_outcome_unknown");
  }
}
