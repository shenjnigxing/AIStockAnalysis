import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";

type OpsPayload = {
  path?: string;
  method?: string;
  payload?: Record<string, unknown>;
};

function tryParseJson(raw: string): unknown {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export async function POST(request: NextRequest) {
  let body: OpsPayload;
  try {
    body = (await request.json()) as OpsPayload;
  } catch {
    return NextResponse.json({ ok: false, status: 400, error: "invalid_json_body", data: null });
  }

  const path = body.path || "";
  const method = (body.method || "POST").toUpperCase();
  const payload = body.payload || {};

  if (!path.startsWith("/api/")) {
    return NextResponse.json({ ok: false, status: 400, error: "path_must_start_with_/api/", data: null });
  }

  try {
    const init: RequestInit = {
      method,
      headers: { "Content-Type": "application/json" },
      cache: "no-store"
    };
    if (!["GET", "HEAD"].includes(method)) {
      init.body = JSON.stringify(payload);
    }

    const response = await fetch(`${API_BASE_URL}${path}`, init);
    const text = await response.text();
    const data = tryParseJson(text);
    return NextResponse.json({
      ok: response.ok,
      status: response.status,
      error: response.ok ? null : typeof data === "string" ? data : "request_failed",
      data
    });
  } catch (error) {
    return NextResponse.json({
      ok: false,
      status: 502,
      error: error instanceof Error ? error.message : "upstream_unreachable",
      data: null
    });
  }
}
