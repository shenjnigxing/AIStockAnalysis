from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategySignalResult:
    symbol: str
    strategy_key: str
    hit: bool
    score: float
    confidence: float
    reasons: list[str]
    risk_tags: list[str]
    feature_snapshot: dict
    market_fit_score: float
    conflict_tags: list[str]


class StrategyBase:
    strategy_key: str = "base"
    strategy_name: str = "Base Strategy"
    category: str = "generic"
    risk_level: str = "medium"

    def evaluate(self, symbol: str, context: dict) -> StrategySignalResult:
        raise NotImplementedError


class RuleTemplateStrategy(StrategyBase):
    def __init__(self, strategy_key: str, strategy_name: str, category: str, bias: float = 0.5) -> None:
        self.strategy_key = strategy_key
        self.strategy_name = strategy_name
        self.category = category
        self.bias = bias

    def evaluate(self, symbol: str, context: dict) -> StrategySignalResult:
        quote = context.get("quote", {})
        change_pct = float(quote.get("change_pct", 0))
        volume = float(quote.get("volume", 0))
        market_state = context.get("market_state", "neutral")
        state_factor = {"bullish": 1.1, "neutral": 1.0, "weak": 0.8, "panic": 0.6}.get(market_state, 1.0)
        raw = max(0.0, min(100.0, change_pct * 10 + (volume / 5000) * self.bias * 10))
        score = round(raw * state_factor, 2)
        hit = score >= 60
        confidence = round(min(1.0, 0.4 + score / 200), 2)
        reasons = [f"{self.strategy_name} evaluated score={score}"]
        risk_tags = ["high_volatility"] if change_pct > 6 else []
        return StrategySignalResult(
            symbol=symbol,
            strategy_key=self.strategy_key,
            hit=hit,
            score=score,
            confidence=confidence,
            reasons=reasons,
            risk_tags=risk_tags,
            feature_snapshot={"change_pct": change_pct, "volume": volume},
            market_fit_score=round(score / 100, 2),
            conflict_tags=[],
        )


class PlaceholderStrategy(StrategyBase):
    def __init__(self, strategy_key: str, strategy_name: str, category: str) -> None:
        self.strategy_key = strategy_key
        self.strategy_name = strategy_name
        self.category = category

    def evaluate(self, symbol: str, context: dict) -> StrategySignalResult:
        return StrategySignalResult(
            symbol=symbol,
            strategy_key=self.strategy_key,
            hit=False,
            score=20.0,
            confidence=0.3,
            reasons=[f"{self.strategy_name} placeholder rule is not fully calibrated yet"],
            risk_tags=["placeholder_rule"],
            feature_snapshot={},
            market_fit_score=0.2,
            conflict_tags=[],
        )


REAL_STRATEGIES = [
    ("first_board_breakout", "首板打板", "emotion", 0.65),
    ("second_board_follow", "二板接力", "emotion", 0.7),
    ("broken_board_recover", "炸板回封", "emotion", 0.6),
    ("platform_breakout", "平台突破", "trend", 0.55),
    ("volume_breakout", "放量突破", "trend", 0.7),
    ("n_shape_breakout", "N 字突破", "trend", 0.52),
    ("macd_second_cross", "MACD 二次金叉", "volume_price", 0.5),
    ("vwap_reversion", "VWAP 回归", "volume_price", 0.45),
    ("main_fund_inflow", "主力净流入增强", "fund", 0.75),
    ("event_catalyst", "公告催化", "event", 0.58),
]

PLACEHOLDER_STRATEGIES = [
    ("reverse_wrap_board", "反包板", "emotion"),
    ("dragon_return", "龙回头", "emotion"),
    ("golden_phoenix_limitup", "金凤凰涨停", "emotion"),
    ("low_volume_pullback", "缩量回踩", "trend"),
    ("ma_bullish_align", "均线多头排列", "trend"),
    ("ma_expand", "均线粘合发散", "trend"),
    ("amount_expand", "成交额放大", "volume_price"),
    ("lhb_resonance", "龙虎榜游资共振", "fund"),
    ("large_order_netbuy", "大单净买入", "fund"),
    ("buyback_support", "回购增持", "event"),
]


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, StrategyBase] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        for key, name, category, bias in REAL_STRATEGIES:
            self._strategies[key] = RuleTemplateStrategy(
                strategy_key=key,
                strategy_name=name,
                category=category,
                bias=bias,
            )
        for key, name, category in PLACEHOLDER_STRATEGIES:
            self._strategies[key] = PlaceholderStrategy(
                strategy_key=key,
                strategy_name=name,
                category=category,
            )

    def list_strategies(self) -> list[StrategyBase]:
        return list(self._strategies.values())

    def get(self, strategy_key: str) -> StrategyBase | None:
        return self._strategies.get(strategy_key)

    def evaluate(self, symbol: str, strategy_keys: list[str] | None, context: dict) -> list[StrategySignalResult]:
        targets = (
            [self._strategies[k] for k in strategy_keys if k in self._strategies]
            if strategy_keys
            else self.list_strategies()
        )
        return [strategy.evaluate(symbol=symbol, context=context) for strategy in targets]

