# AIStock V3 外部开源调研与求证（截至 2026-10-21）

## 一级资料/可复核入口
| 项目 | 确认事实 | 适配决定 | 限制 |
|---|---|---|---|
| Microsoft Qlib | https://github.com/microsoft/qlib；包含 data handler、workflow、PIT collector、模型与回测（官方 README/docs） | 借数据血缘、PIT 与实验注册，未来可嵌入 ML 训练 | 开源示例 PIT 数据明确提醒可能不完美；不可直接作为可交易级别数据 |
| VeighNa / vnpy | https://github.com/vnpy/vnpy；官方 README 描述 CTA、组合、国内连接器和 alpha 研究 | 未来国内期货交易与仿真执行研究可评估 | 现有交易链必须先审计，不现在接入实盘 |
| QuantConnect LEAN | https://github.com/QuantConnect/Lean；Apache-2.0、含 futures settlement/futures chain、多资产案例 | 参考事件驱动回测与期货契约建模 | 重量级、对中国数据和交易规则需大量适配 |
| NautilusTrader | https://github.com/nautechsystems/nautilus_trader/releases，2026-10-04 有 2.0.0rc6 | 关注跨资产事件模型、可复现模拟 | rc 为预发布，不盲目生产依赖 |
| OpenBB | https://github.com/OpenBB-finance/OpenBB/blob/develop/openbb_platform/providers/README.md 官方说明 provider 独立 model/util/tests | 模仿 provider adapter 的边界 | 不保证数据授权、区域覆盖或免费 |
| AKShare | https://github.com/akfamily/akshare，支持行情基金、期货、宏观债券接口，官方说明接口可能移除 | 中国资产数据接入的候选适配器 | 不能视为商用服务 SLA / 数据品质保证 |
| vectorbt | https://github.com/polakowo/vectorbt/blob/master/LICENSE.md，Apache 2.0 with Commons Clause | 仅借鉴矢量研究思路 | **不是**无条件 Apache 2.0：商业产品分发前需合规评估 |
| CFFEX | https://www.e-cffex.com.cn/web/fljfg/，国债期货合约、风控制度和期货交割规则独立 | 交易时点版本化规则 | 不硬编码保证金、涨跌停、手续费 |
| SGE | https://www.sge.com.cn/cpfw/Au%28T%2BD%29 与 https://www.sge.com.cn/cpfw/Product_service_details?cplx=7&parent_cplx=0&pro_id=793730879941324800 | 黄金实物与延期保证金交易必须独立建模 | 不能把纸黄金报价等价为交易所 Au99.99 |
| ChinaBond | https://indices.chinabond.com.cn/cbweb-mn/yield_main?locale=zh_CN | 国债收益率曲线、估值/久期研究 | 页面注明衍生产品/基准许可需另行确认 |
| Python SMTP | https://docs.python.org/3/library/smtplib.html；SMTP_SSL / STARTTLS / default SSL context | 后续安全邮件推送 | 此阶段不发送、不开邮件凭据入口 |

## 结论
“成熟产品”核心是可核验的多资产研究、PIT 数据版本、每资产独立成本与回测、统一报告和受控分发。短期 3–20 交易观测，中长期 20–120 观测；不因为显示统一分数就跨资产直接推荐。
外部资料适用于架构和算法风险设计；不证明任何模型在 2026 年真实市场具有预测优势。
