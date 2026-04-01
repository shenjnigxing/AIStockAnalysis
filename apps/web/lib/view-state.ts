import { FetchResult } from "./api";

export type PageState = "loading" | "empty" | "error" | "partial_error" | "ready";

export function resolvePageState(results: Array<FetchResult<unknown>>, hasData: boolean): PageState {
  if (results.length === 0) return hasData ? "ready" : "empty";
  const failed = results.filter((item) => !item.ok).length;
  if (failed === results.length) return "error";
  if (failed > 0) return hasData ? "partial_error" : "error";
  return hasData ? "ready" : "empty";
}
