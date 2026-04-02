import {
  ApiHealth,
  BacktestJob,
  BacktestReportDetail,
  BrokerCapabilities,
  BacktestReport,
  DataJob,
  DataQualityIssue,
  DrReadiness,
  InitStatus,
  LiveGrayConfig,
  LiveAssetItem,
  LiveOrderItem,
  LivePositionItem,
  NotificationItem,
  PaperAsset,
  PaperOrderItem,
  PaperPositionItem,
  RecommendationItem,
  RuntimeHealth,
  ScreenerCandidate,
  SettingItem,
  StrategyItem
} from "./types";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";
const FETCH_TIMEOUT_MS = 2500;

async function fetchWithTimeout(path: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    return await fetch(`${API_BASE_URL}${path}`, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

export type FetchResult<T> = {
  data: T;
  ok: boolean;
  error: string | null;
};

async function safeFetch<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetchWithTimeout(path, { cache: "no-store" });
    if (!res.ok) return fallback;
    return (await res.json()) as T;
  } catch {
    return fallback;
  }
}

export async function fetchApiResult<T>(path: string, fallback: T): Promise<FetchResult<T>> {
  try {
    const res = await fetchWithTimeout(path, { cache: "no-store" });
    if (!res.ok) {
      return { data: fallback, ok: false, error: `http_${res.status}` };
    }
    const data = (await res.json()) as T;
    return { data, ok: true, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown_error";
    return { data: fallback, ok: false, error: message };
  }
}

export async function fetchSystemStatus(): Promise<ApiHealth> {
  return safeFetch<ApiHealth>("/api/system/status", { status: "unreachable" });
}

export async function fetchCandidates(): Promise<ScreenerCandidate[]> {
  const data = await safeFetch<{ items: ScreenerCandidate[] }>("/api/candidates/top100", { items: [] });
  return data.items;
}

export async function fetchRecommendations(): Promise<RecommendationItem[]> {
  const data = await safeFetch<{ items: RecommendationItem[] }>("/api/recommendation/top?limit=20", { items: [] });
  return data.items;
}

export async function fetchRecommendationBySymbol(symbol: string): Promise<RecommendationItem | null> {
  return safeFetch<RecommendationItem | null>(`/api/recommendation/${symbol}`, null);
}

export async function fetchStrategies(): Promise<StrategyItem[]> {
  const data = await safeFetch<{ items: StrategyItem[] }>("/api/strategy/list", { items: [] });
  return data.items;
}

export async function fetchNotifications(): Promise<NotificationItem[]> {
  const data = await safeFetch<{ items: NotificationItem[] }>("/api/notifications", { items: [] });
  return data.items;
}

export async function fetchSettings(): Promise<SettingItem[]> {
  const data = await safeFetch<{ items: SettingItem[] }>("/api/settings", { items: [] });
  return data.items;
}

export async function fetchInitStatus(): Promise<InitStatus> {
  return safeFetch<InitStatus>("/api/init/status", { steps: [], done: [], finished: false });
}

export async function fetchPaperOrders(): Promise<PaperOrderItem[]> {
  const data = await safeFetch<{ items: PaperOrderItem[] }>("/api/paper/orders", { items: [] });
  return data.items;
}

export async function fetchPaperPositions(): Promise<PaperPositionItem[]> {
  const data = await safeFetch<{ items: PaperPositionItem[] }>("/api/paper/positions", { items: [] });
  return data.items;
}

export async function fetchPaperAsset(): Promise<PaperAsset> {
  return safeFetch<PaperAsset>("/api/paper/assets", {
    account_id: 0,
    cash: 0,
    frozen_cash: 0,
    market_value: 0,
    total_assets: 0,
    daily_pnl: 0,
    total_pnl: 0
  });
}

export async function fetchLiveOrders(): Promise<LiveOrderItem[]> {
  const data = await safeFetch<{ items: LiveOrderItem[] }>("/api/live/orders", { items: [] });
  return data.items;
}

export async function fetchLivePositions(): Promise<LivePositionItem[]> {
  const data = await safeFetch<{ items: LivePositionItem[] }>("/api/live/positions", { items: [] });
  return data.items;
}

export async function fetchLiveAssets(): Promise<LiveAssetItem[]> {
  const data = await safeFetch<{ items: LiveAssetItem[] }>("/api/live/assets", { items: [] });
  return data.items;
}

export async function fetchLiveBrokerStatus(): Promise<Record<string, unknown>> {
  return safeFetch<Record<string, unknown>>("/api/live/broker/status", {});
}

export async function fetchReplayDays(): Promise<string[]> {
  const data = await safeFetch<{ items: string[] }>("/api/replay/days", { items: [] });
  return data.items;
}

export async function fetchReplayByDay(day: string): Promise<Array<Record<string, unknown>>> {
  const data = await safeFetch<{ items: Array<Record<string, unknown>> }>(`/api/replay/day/${day}`, { items: [] });
  return data.items;
}

export async function fetchDataJobs(): Promise<DataJob[]> {
  const data = await safeFetch<{ items: DataJob[] }>("/api/data/jobs", { items: [] });
  return data.items;
}

export async function fetchDataQualityIssues(): Promise<DataQualityIssue[]> {
  const data = await safeFetch<{ items: DataQualityIssue[] }>("/api/data/quality/issues", { items: [] });
  return data.items;
}

export async function fetchBacktestJobs(): Promise<BacktestJob[]> {
  const data = await safeFetch<{ items: BacktestJob[] }>("/api/backtest/jobs", { items: [] });
  return data.items;
}

export async function fetchBacktestReport(jobId: number): Promise<BacktestReport | null> {
  return safeFetch<BacktestReport | null>(`/api/backtest/report/${jobId}`, null);
}

export async function fetchBacktestReportDetail(jobId: number): Promise<BacktestReportDetail | null> {
  return safeFetch<BacktestReportDetail | null>(`/api/backtest/report/${jobId}/detail`, null);
}

export async function fetchRuntimeHealth(): Promise<RuntimeHealth> {
  return safeFetch<RuntimeHealth>("/api/admin/runtime-health", {
    status: "degraded",
    degraded_reasons: ["unreachable"],
    services: {},
    resilience: { latest_backup_at: "", fresh_backup_within_24h: false, backup_count: 0 },
    timestamp: ""
  });
}

export async function fetchDrReadiness(): Promise<DrReadiness> {
  return safeFetch<DrReadiness>("/api/admin/dr/readiness", {
    score: 0,
    status: "partial",
    checklist: {},
    latest_backup_marker: "",
    timestamp: ""
  });
}

export async function fetchLiveGrayConfig(): Promise<LiveGrayConfig> {
  const data = await safeFetch<{ config: LiveGrayConfig }>("/api/risk/live-gray/config", {
    config: {
      live_gray_mode_enabled: true,
      live_gray_max_notional: 50000,
      live_gray_whitelist: [],
      live_gray_blocklist: [],
      live_auto_submit: false
    }
  });
  return data.config;
}

export async function fetchLiveBrokerCapabilities(provider?: string): Promise<BrokerCapabilities> {
  const query = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  return safeFetch<BrokerCapabilities>(`/api/live/broker/capabilities${query}`, {
    provider: provider || "unknown",
    ready: false,
    supports: {}
  });
}
