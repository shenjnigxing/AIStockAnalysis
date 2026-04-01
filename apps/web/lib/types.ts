export type ApiHealth = {
  status: string;
  app_name?: string;
  environment?: string;
};

export type RecommendationItem = {
  symbol: string;
  final_rank: number;
  recommendation_level: "A" | "B" | "C" | "D";
  total_score: number;
  action_suggestion: string;
};

export type ScreenerCandidate = {
  symbol: string;
  base_score: number;
  rank_no: number;
};

export type StrategyItem = {
  strategy_key: string;
  strategy_name: string;
  category: string;
  enabled: boolean;
  version: string;
};

export type NotificationItem = {
  id: number;
  source_type: string;
  level: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
};

export type InitStatus = {
  steps: string[];
  done: string[];
  finished: boolean;
};

export type SettingItem = {
  config_key: string;
  config_value: string;
};

export type PaperOrderItem = {
  order_id: number;
  symbol: string;
  side: string;
  status: string;
  price: number;
  quantity: number;
};

export type PaperPositionItem = {
  symbol: string;
  quantity: number;
  avg_price: number;
};

export type PaperAsset = {
  account_id: number;
  cash: number;
  frozen_cash: number;
  market_value: number;
  total_assets: number;
  daily_pnl: number;
  total_pnl: number;
};

export type LiveOrderItem = {
  order_id: number;
  symbol: string;
  side: string;
  price: number;
  quantity: number;
  status: string;
};

export type LivePositionItem = {
  symbol: string;
  quantity: number;
  avg_price: number;
};

export type LiveAssetItem = {
  snapshot_time: string;
  cash: number;
  market_value: number;
  total_assets: number;
};

export type DataJob = {
  job_id: number;
  job_type: string;
  status: string;
  result: Record<string, unknown>;
  error_message: string | null;
};

export type DataQualityIssue = {
  id: number;
  issue_type: string;
  symbol: string;
  detail: string;
  created_at: string;
};

export type BacktestJob = {
  job_id: number;
  name: string;
  status: string;
  type: string;
};

export type BacktestReport = {
  job_id: number;
  metrics: Record<string, unknown>;
};
