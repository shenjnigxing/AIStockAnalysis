from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from app.core.config import settings


@dataclass
class LLMExplainResult:
    provider: str
    adjustment: float
    explanation: str
    counter_arguments: list[str]
    degraded: bool = False
    error: str = ""


class LLMExplainerBase:
    provider_name: str = "base"

    def explain(
        self,
        *,
        symbol: str,
        market_state: str,
        quant_score: float,
        risk_score: float,
        hit_strategies: list[str],
        risk_tags: list[str],
    ) -> LLMExplainResult:
        raise NotImplementedError


class MockLLMExplainer(LLMExplainerBase):
    provider_name = "mock"

    def explain(
        self,
        *,
        symbol: str,
        market_state: str,
        quant_score: float,
        risk_score: float,
        hit_strategies: list[str],
        risk_tags: list[str],
    ) -> LLMExplainResult:
        resonance = min(6, len(hit_strategies))
        base = (quant_score - risk_score) / 100.0
        market_penalty = -0.8 if market_state == "panic" else -0.35 if market_state == "weak" else 0.0
        adjustment = round(max(-4.0, min(4.0, base * 2.0 + resonance * 0.25 + market_penalty)), 2)

        risk_desc = "、".join(risk_tags[:3]) if risk_tags else "暂无显著风险标签"
        strategies_desc = "、".join(hit_strategies[:4]) if hit_strategies else "无明确命中战法"
        explanation = (
            f"LLM({self.provider_name})评估 {symbol}：市场状态={market_state}，"
            f"命中战法={strategies_desc}，风险={risk_desc}，给出修正 {adjustment:+.2f}。"
        )
        counters = []
        if market_state in {"weak", "panic"}:
            counters.append("市场环境偏弱，建议缩小仓位并延后确认。")
        if "low_liquidity" in risk_tags:
            counters.append("流动性偏低，冲击成本可能扩大。")
        if "high_volatility" in risk_tags:
            counters.append("波动较大，止损阈值需更保守。")
        return LLMExplainResult(
            provider=self.provider_name,
            adjustment=adjustment,
            explanation=explanation,
            counter_arguments=counters[:3],
            degraded=False,
        )


class OpenAICompatExplainer(LLMExplainerBase):
    provider_name = "openai_compat"

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.fallback = MockLLMExplainer()

    def _fallback_result(
        self,
        *,
        symbol: str,
        market_state: str,
        quant_score: float,
        risk_score: float,
        hit_strategies: list[str],
        risk_tags: list[str],
        reason: str,
    ) -> LLMExplainResult:
        base = self.fallback.explain(
            symbol=symbol,
            market_state=market_state,
            quant_score=quant_score,
            risk_score=risk_score,
            hit_strategies=hit_strategies,
            risk_tags=risk_tags,
        )
        base.provider = f"{self.provider_name}_fallback"
        base.degraded = True
        base.error = reason
        return base

    def _parse_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        choices = payload.get("choices", [])
        if not choices:
            return {}
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            text_parts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
            content = "".join(text_parts)
        if not isinstance(content, str):
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    def explain(
        self,
        *,
        symbol: str,
        market_state: str,
        quant_score: float,
        risk_score: float,
        hit_strategies: list[str],
        risk_tags: list[str],
    ) -> LLMExplainResult:
        if not self.api_key:
            return self._fallback_result(
                symbol=symbol,
                market_state=market_state,
                quant_score=quant_score,
                risk_score=risk_score,
                hit_strategies=hit_strategies,
                risk_tags=risk_tags,
                reason="missing_api_key",
            )

        prompt = (
            "你是股票推荐解释助手。请只返回 JSON 对象，字段："
            "adjustment(-4到4浮点数)、explanation(字符串)、counter_arguments(字符串数组)。\n"
            f"symbol={symbol}, market_state={market_state}, quant_score={quant_score}, risk_score={risk_score}, "
            f"hit_strategies={hit_strategies}, risk_tags={risk_tags}"
        )
        req_body = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "你输出的内容必须是 JSON。"},
                {"role": "user", "content": prompt},
            ],
        }
        data = json.dumps(req_body, ensure_ascii=True).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=8) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self._fallback_result(
                symbol=symbol,
                market_state=market_state,
                quant_score=quant_score,
                risk_score=risk_score,
                hit_strategies=hit_strategies,
                risk_tags=risk_tags,
                reason=f"request_failed:{exc}",
            )

        parsed = self._parse_content(body)
        if not parsed:
            return self._fallback_result(
                symbol=symbol,
                market_state=market_state,
                quant_score=quant_score,
                risk_score=risk_score,
                hit_strategies=hit_strategies,
                risk_tags=risk_tags,
                reason="empty_or_invalid_model_payload",
            )
        try:
            adjustment = float(parsed.get("adjustment", 0.0))
        except (TypeError, ValueError):
            adjustment = 0.0
        explanation = str(parsed.get("explanation", ""))[:600]
        counters_raw = parsed.get("counter_arguments", [])
        counters = [str(item) for item in counters_raw][:4] if isinstance(counters_raw, list) else []
        return LLMExplainResult(
            provider=self.provider_name,
            adjustment=max(-4.0, min(4.0, round(adjustment, 2))),
            explanation=explanation or f"LLM({self.provider_name}) 未返回有效解释。",
            counter_arguments=counters,
            degraded=False,
        )


def get_llm_explainer(provider: str | None = None) -> LLMExplainerBase:
    target = (provider or settings.llm_provider).strip().lower()
    if target in {"openai", "openai_compat"}:
        return OpenAICompatExplainer(
            base_url=settings.llm_openai_base_url,
            model=settings.llm_openai_model,
            api_key=settings.llm_openai_api_key,
        )
    return MockLLMExplainer()

