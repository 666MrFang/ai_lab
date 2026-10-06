---
name: a-share-daily-review
version: 0.1.0
description: >
  A股每日盘后复盘 Skill。
  基于结构化市场行情、板块、个股、新闻事件和历史数据，
  分析市场状态、赚钱/亏钱效应、主线板块、核心个股及事件驱动，
  并生成 Evidence-based 的结构化复盘结果。
---

# A-Share Daily Review Skill

## 1. Goal

对指定交易日的 A 股市场进行盘后复盘。

目标不是解释所有涨跌，也不是预测股价，
而是回答以下问题：

1. 今天市场整体强弱如何？
2. 当前市场处于什么状态？
3. 赚钱效应在哪里？
4. 亏钱效应在哪里？
5. 哪些板块是当天最重要的主线或弱势方向？
6. 主线中的核心个股是谁？
7. 核心个股上涨/下跌有哪些可验证的相关事件？
8. 哪些判断有充分 Evidence？
9. 哪些判断仍存在 Evidence Gap？
10. 下一交易日应该观察哪些验证条件？

所有分析必须遵循：

Fact
→ Evidence
→ Inference
→ Confidence
→ Claim

禁止：

Fact
→ Guess
→ Strong Claim


# 2. Core Principles

## RULE-001: Fact / Inference Separation

所有输出必须区分：

- FACT
- INFERENCE
- EVIDENCE_GAP

FACT 必须来自：

- MCP Tool
- Structured Market Data
- Historical Data
- 可追溯新闻/公告
- 其他明确数据源

模型自身知识不得伪装成 FACT。


## RULE-002: Evidence Before Claim

任何关于以下内容的判断：

- 市场阶段
- 主线
- 龙头
- 赚钱效应
- 亏钱效应
- 上涨原因
- 下跌原因
- 股性
- 次日倾向

必须提供 Evidence。

Evidence 无法支持 Claim 时：

降低 Claim 强度，

或者：

输出 EVIDENCE_GAP。


## RULE-003: Correlation Is Not Causation

禁止仅因为：

新闻出现
+
股票上涨

就输出：

“该新闻导致股票上涨”。

允许：

“该事件与股价上涨在时间上相关。”

“该事件可能是候选影响因素。”

“现有 Evidence 支持相关性，但不足以建立因果关系。”


## RULE-004: Temporal Consistency

事件用于解释价格行为时必须检查发布时间。

例如：

08:30 Event
→ 可以作为开盘行为的候选 Evidence。

10:15 Event
→ 不得解释 09:30 已经发生的高开。

14:05 Event
→ 不得解释上午已经完成的主要涨幅。

时间顺序冲突时必须降低 Evidence 强度。


## RULE-005: Source Reliability

新闻和事件必须保留：

- source
- published_at
- title
- news_id / url（如果存在）

来源无法确认时：

source_reliability = low

不得形成 Strong Claim。


## RULE-006: Historical Claims Require Historical Evidence

包含以下语义的 Claim：

- 历史上
- 通常
- 经常
- 大概率
- 股性
- 惯性
- 涨停后一般
- 次日容易
- 高开高走概率
- 容易坑人
- 容易反包

必须使用 Historical Evidence。

没有历史样本：

禁止形成统计性 Claim。


## RULE-007: Evidence Completeness Gate

任何需要历史 / 持续性（persistence）支撑的判断，
在形成 Claim 之前必须检查 Evidence 的完整性。

必须读取并检查：

- window
- sample_count
- complete
- missing_dates
- evidence_status

当 Evidence 来自 baseline / 历史统计，且：

`complete != true`
或
`evidence_status == INSUFFICIENT_HISTORY`

则视为 incomplete Evidence。

incomplete Evidence：

- 只能支持 Fact 陈述；
- 不能支持 confirmed 判断；
- 不能通过“承认证据不足，但仍然给出 confirmed 结论”的方式绕过。

当 persistence Evidence incomplete 时：

- 禁止输出 confirmed market_regime；
- 默认 market_regime.state = UNCERTAIN；
- 在 evidence_gaps 中记录：insufficient persistence evidence。

候选判断只能以 candidate / tentative 形式出现在 narrative / inference 中，
不得写入结构化 confirmed state。


## RULE-008: Numeric Semantic Calibration

任何 Numeric Fact 升级为语义标签之前，必须先存在 Calibration。

Numeric Fact 例如：

- broken_limit_rate
- promotion_rate
- limit_up_count
- limit_down_count
- turnover
- advance / decline 相关数值或比例

语义标签例如：

- 高 / 低
- 强 / 弱
- 放量 / 缩量
- 分歧大
- 修复明显
- 情绪高涨 / 情绪冰点

只有在满足其一时才允许使用语义标签：

A. complete historical baseline；
B. Skill / Eval 中明确冻结的 threshold rule（SemanticCalibrationPolicy）。

否则只能：

- 陈述 current value；
- 或陈述 current 与 avg / median / percentile 的数值关系。

禁止路径：

Numeric Fact
→ 模型直觉
→ Semantic Label。


## RULE-009: Forward Claim Boundary

历史校准不等于未来因果。

即使存在 complete baseline 或高 percentile，
也只允许描述“相对历史的位置”，
不得据此推出未来方向。

禁止：

- broken_limit_rate high → tomorrow market will fall
- promotion_rate high → tomorrow will continue rising
- 任何 deterministic forecast

未来只能写成 verification condition（见 Section 15），
不能写成 prediction。


# 3. Review Workflow

执行顺序：

Market
→ Evidence Completeness Gate
→ Market Regime
→ Sector
→ Core Stock
→ Event
→ Historical Context（需要时）
→ Evidence Review
→ Structured Output


# 4. Market Review

首先分析市场整体状态。

至少获取：

- 主要指数涨跌幅
- 市场成交额

如果数据源支持，还应获取：

- 上涨家数
- 下跌家数
- 涨停家数
- 跌停家数
- 首板数量
- 连板数量
- 最高连板高度
- 炸板率
- 昨日涨停股今日表现
- 昨日涨停晋级率
- 大涨股票数量
- 大跌股票数量


## 4.1 Volume

单独的成交额不能直接判断：

“放量”
“缩量”

需要比较：

- previous_day_turnover
- avg_5d_turnover
- avg_20d_turnover

建议计算：

turnover_vs_prev
turnover_vs_5d
turnover_vs_20d


## 4.2 Market Breadth

使用：

上涨家数
/
下跌家数

判断市场赚钱效应是否广泛。

指数上涨 ≠ 普涨。

如果：

指数上涨
+
下跌家数明显多于上涨家数

应描述为：

“指数上涨但赚钱效应集中”

而不是：

“市场普涨”。


## 4.3 Numeric Semantic Calibration Gate

Section 4 获取的数值（涨停家数、跌停家数、首板 / 连板、
炸板率、晋级率、成交额、涨跌家数等）
在升级为语义描述之前，必须经过 Calibration Gate（RULE-008）。

如果 baseline `complete != true`：

允许：

- “今日炸板率为 18.75%。”
- “昨日涨停晋级率为 21.05%。”

禁止：

- “炸板率较高 / 较低”
- “接力分歧较大”
- “情绪较好 / 较差”
- “放量 / 缩量”（除非成交额存在 complete turnover baseline）

并记录 evidence_gap。

如果 baseline `complete == true`：

允许引用 avg / median / percentile 形成相对描述。

例如允许：

“当前 18.75%，近 5 日均值 21.89%，历史分位 40%。”

禁止扩展为：

“市场风险较低。”
“明天会上涨。”

优先输出数值关系（current / avg / median / percentile），
优先于离散语义标签（高 / 低）。


## 4.4 Market Breadth Evidence Gap

advance_count / decline_count / flat_count 与 limit ecology 属于不同 Evidence。

如果目标历史日期无法获得 advance / decline / flat（例如数据源仅支持 current snapshot）：

- 必须进入 evidence_gaps；
- 禁止用 limit_up_count 替代全市场 breadth；
- 禁止由“涨停很多”推断“上涨家数很多”；
- 禁止使用当前 snapshot 回填历史日期。


## 4.5 Structured MetricClaim Contract

review.json 是 Claim 的 Source of Truth；review.md 只是呈现。

Agent 每产生一个 numeric metric claim
（包括 FACT / RELATIVE_NUMERIC / SEMANTIC / FORWARD），
必须同步写入 root-level `metric_claims`。

禁止：

review.md 中出现 metric semantic claim，
但 review.json.metric_claims 没有对应结构化 Claim。

claim_type：

- FACT：仅陈述数值，例如“炸板率为 18.75%”。
- RELATIVE_NUMERIC：数值与 baseline 的数学关系，
  例如“18.75% 低于近 5 日均值 21.89%”。
  注意：“低于”只是数学关系，不是 semantic_label=low。
- SEMANTIC：语义标签（高/低/强/弱），
  必须同时具备 complete baseline + 冻结的 SemanticCalibrationPolicy。
- FORWARD：前瞻判断，必须 forward_claim=true。

约束：

- semantic_label 仅在 claim_type == SEMANTIC 时非 null；
- 每个 MetricClaim 必须引用 evidence_refs；
- RELATIVE_NUMERIC / SEMANTIC 必须引用 baseline_refs；
- SEMANTIC 必须引用 threshold_policy_ref；
- claim_id 在本 review 内唯一。

在没有冻结 SemanticCalibrationPolicy 时：

优先输出 FACT / RELATIVE_NUMERIC，
不要产生 SEMANTIC。

不得因为 current < avg 就自动 semantic_label=low。

同时必须在 review.json 提供最小 `evidence_registry`，
为每个 evidence_refs / baseline_refs 提供对应条目。


# 5. Market Regime

候选状态：

- MAIN_UPTREND
- ROTATION
- LOSS_EFFECT
- ICE_POINT
- UNCERTAIN

中文：

- 主升
- 轮动震荡
- 亏钱效应
- 冰点
- 无法确定


## Important

市场阶段属于 INFERENCE，不是 FACT。

必须给出：

market_regime
confidence
evidence[]
counter_evidence[]
evidence_gaps[]


## 5.0 Evidence Completeness Gate

在给出任何 confirmed market_regime 之前，必须先通过本 Gate（RULE-007）。

必须读取并检查所需 persistence Evidence 的：

- window
- sample_count
- complete
- missing_dates
- evidence_status

判定：

如果所需 persistence baseline `complete != true`
或 `evidence_status == INSUFFICIENT_HISTORY`：

→ persistence Evidence insufficient：

- market_regime.state = UNCERTAIN
- confidence 不得高于证据强度
- evidence_gaps 记录：insufficient persistence evidence
- 禁止输出 confirmed MAIN_UPTREND / ROTATION / LOSS_EFFECT / ICE_POINT
- 候选判断只能写 candidate / tentative（inference / narrative）

如果 `complete == true`：

→ 才允许进入 5.1–5.4 的 regime 规则。

注意：

- 5d baseline complete 不能替代 20d persistence Evidence；
- 不得把 5d 结论伪装成 20d 结论；
- 禁止“承认证据不足，但依然 confirmed”的路径。


## 5.1 MAIN_UPTREND

候选特征：

- 主线持续
- 核心个股持续走强
- 高位核心出现分歧后具有修复能力
- 市场赚钱效应较强
- 主线具有持续性而非单日脉冲

不得仅凭：

“指数上涨”

判断为主升。


## 5.2 ROTATION

候选特征：

- 板块持续性不足
- 热点快速轮动
- 个股冲高回落增加
- 强势方向次日延续性下降
- 市场仍存在赚钱机会，但集中度下降


## 5.3 LOSS_EFFECT

候选特征：

- 高位核心负反馈明显
- 前期强势股次日缺少修复
- 跌停或大跌数量增加
- 市场讨论风险明显增加
- 高位接力成功率下降


## 5.4 ICE_POINT

候选特征：

- 市场风险偏好显著下降
- 极端亏钱效应出现
- 强势股普遍补跌
- 接力意愿明显下降
- 情绪指标处于近期极低水平

“冰点”只能作为状态判断。

禁止直接推导：

“冰点后一定反弹”
“冰点就是买点”。

如果需要讨论历史冰点后的表现，
必须调用 Historical Evidence。


## 5.5 Persistence Evidence Rule

Confirmed market regime
requires sufficient persistence evidence.

单日强度不构成持续性 regime Evidence。

例如：

强势指数
+ 放量
+ 涨停较多

只能证明 current-day strength，
不能自动证明 MAIN_UPTREND。

如果 MAIN_UPTREND 的持久性特征无法验证
（主线持续、核心个股持续、赚钱效应持续、高位分歧后修复、多日结构）：

- state = UNCERTAIN
- candidate_state 写入 candidate_state / narrative
- evidence_gaps 记录缺失的 persistence 维度

如果 20d persistence baseline incomplete：

- market_regime.state = UNCERTAIN
- 即使 5d baseline complete，也不得把 5d Evidence 当作 20d persistence Evidence。


## 5.6 Market Regime Decision Order

严格按顺序执行。
不得先选 regime，再为它寻找 Evidence。

Step 1
Collect current-day facts
（指数、成交额、breadth、limit ecology）

Step 2
Check historical / persistence evidence
（多日 baseline、历史统计）

Step 3
Run Evidence Completeness Gate（5.0）

Step 4
If insufficient：
    market_regime.state = UNCERTAIN
    在 evidence_gaps 记录 insufficient persistence evidence
    STOP confirmed regime classification

Step 5
If sufficient：
    才应用 regime 规则（5.1–5.4）

Step 6
Separate Fact / Evidence / Inference
标注 confidence 与 evidence_gaps


# 6. Sector Selection

每日必须分析：

- 涨幅 Top 10 板块
- 跌幅 Top 10 板块

板块分析至少包含：

- sector_name
- change_pct
- turnover

如果数据可用：

- 5日涨幅
- 20日涨幅
- 板块成交额变化
- 涨停数量
- 跌停数量
- 板块上涨/下跌家数


# 7. Main Theme Identification

“涨幅第一”不自动等于“市场主线”。

主线判断应综合：

- 当日涨幅
- 多日持续性
- 成交额 / 流动性
- 涨停数量
- 核心个股表现
- 市场关注度
- 新闻 / 产业 / 政策 Evidence

输出：

main_theme_candidates[]

每个 Candidate：

- sector_name
- evidence[]
- confidence
- evidence_gaps[]


# 8. Stock Selection

重点分析三类股票：

1. strong_stock
2. capacity_core
3. popularity_stock


## 8.1 Strong Stock

V0.1 定义：

板块内 5 日涨幅排名 Top 3。

注意：

该定义只代表：

“5日强势股”

不得自动称为：

“龙头”。

龙头身份需要更多 Evidence。


## 8.2 Capacity Core

容量候选：

market_cap >= 50,000,000,000 CNY

即：

市值 >= 500亿元。

容量中军最终判断还需要：

- 当日表现
- 成交额
- 板块影响力
- 持续性

V0.1 不强制唯一选择容量中军。

证据不足：

标记为 capacity_core_candidate。


## 8.3 Popularity Stock

满足以下任一条件：

- 同花顺热榜 Top10
- 东方财富热榜 Top10

进入重点 Drill-down。


# 9. Drill-down Rules

满足任意条件时继续 Drill-down：

DRILL-001

个股进入：

同花顺 / 东方财富热榜 Top10。


DRILL-002

板块或个股出现显著涨跌，

但当前 Evidence 无法解释可能相关因素。


DRILL-003

已有事件 Evidence，

但来源可信度不足。


DRILL-004

事件发布时间与价格行为时间关系不清楚。


DRILL-005

当前判断依赖：

“历史规律”
“股性”
“次日表现”

但尚未获取历史数据。


# 10. Stop Rules

Skill 不是无限搜索。

满足以下条件之一停止 Drill-down：


## STOP-001: Sufficient Evidence

已有多个相互独立、可信且时间一致的 Evidence，

足以形成限定强度的 Claim。


## STOP-002: Evidence Exhausted

已经查询当前允许的数据源，

仍无法找到可信 Evidence。

输出：

EVIDENCE_GAP

禁止继续猜测。


## STOP-003: Source Unreliable

关键 Claim 仅依赖：

- 无法确认来源的信息
- 市场传闻
- 无时间戳信息

不得形成 Strong Claim。


## STOP-004: Historical Data Missing

需要历史统计才能回答，

但当前不存在 Historical Data。

输出：

HISTORICAL_DATA_REQUIRED


# 11. Event Analysis

每个事件必须输出：

event
source
published_at
event_type

以及：

evidence_strength

允许：

HIGH
MEDIUM
LOW


## Evidence Strength

HIGH：

- 官方公告
- 交易所信息
- 公司正式披露
- 高可信来源
- 时间关系明确

MEDIUM：

- 可信财经媒体
- 行业报告
- 有明确来源但不是第一手信息

LOW：

- 来源无法确认
- 市场传闻
- 二手转载
- 时间关系不清晰


# 12. Price Reason Analysis

禁止输出：

“股票上涨原因就是 XXX”

除非 Evidence 极强。

默认使用：

- possible_driver
- related_event
- candidate_factor

每个原因必须包含：

- inference
- evidence[]
- confidence
- counter_evidence[]
- evidence_gaps[]


# 13. Profit / Loss Effect

复盘必须回答：

赚钱效应在哪里？

亏钱效应在哪里？

候选观察维度：

- 题材
- 接力
- 赛道
- 大票
- 小票
- 高位股
- 低位股
- 首板
- 连板
- 趋势股

如果数据不足：

不得强行分类。


# 14. Historical Behavior

当分析：

“这个股票大涨后第二天一般怎么走？”

必须查询历史行情。

建议事件定义明确化，例如：

event = daily_return >= threshold

统计：

sample_size
next_day_open_return
next_day_close_return
next_day_positive_rate
next_day_high_open_rate
3d_return
5d_return
max_drawdown

必须输出 sample_size。

样本量不足时：

confidence = low

禁止使用：

“一般”
“大概率”
“通常”。


# 15. Tomorrow Watchlist

盘后可以生成：

tomorrow_watch_conditions

但它必须是：

“验证条件”

而不是：

“预测结果”。

例如允许：

如果半导体核心个股继续保持强势，
且板块成交活跃度维持，
则主线持续性的 Evidence 增强。

禁止：

明天半导体一定继续上涨。


## 15.1 Forward Claim Boundary

历史校准不等于未来因果（RULE-009）。

即使存在 complete baseline 与高 percentile，
也只能描述相对历史位置，不得推出未来方向。

禁止：

- broken_limit_rate high → tomorrow market will fall
- promotion_rate high → tomorrow will continue rising
- 任何用历史分位 / 阈值包装的确定性预测

未来只能写成 verification condition，
即“若观察到 X，则 Y 的 Evidence 增强 / 减弱”，
不能写成 deterministic prediction。


# 16. Forbidden Behavior

禁止：

- 无 Evidence 猜测涨跌原因
- 把相关新闻自动等价为上涨原因
- 把相关性写成因果
- 使用来源不明消息形成 Strong Claim
- 没有历史数据却谈“股性”
- 没有统计样本却谈“大概率”
- 把涨幅第一自动称为主线
- 把5日涨幅第一自动称为龙头
- 把市场阶段直接转化为买卖建议
- 输出确定性收益预测
- 使用 incomplete baseline 做语义判断
- 把单日强度当成持续性 Evidence
- 在 persistence Evidence 不足时输出 confirmed regime
- 用 limit_up_count 替代全市场 breadth
- 把历史校准结论升级为未来因果或确定性预测


# 17. Output

必须同时生成：

1. Structured JSON
2. Human-readable Markdown Report

JSON 必须符合：

schemas/review_schema.json

review.json 必须包含 root-level：

- metric_claims（结构化 numeric metric claims）
- evidence_registry（metric_claims 引用的最小证据集）

Markdown 必须根据结构化结论表达，
不得在 Markdown 中偷偷增加更强的 Claim。


# 18. Final Self Check

输出前检查：

[ ] Fact 是否都有来源？
[ ] Fact 与 Inference 是否分离？
[ ] 每个关键 Claim 是否有 Evidence？
[ ] 是否存在时间因果倒置？
[ ] 是否把相关新闻误写成上涨原因？
[ ] 是否存在来源不明 Evidence？
[ ] 是否在无历史数据时谈股性？
[ ] 是否把板块涨幅第一直接等价为主线？
[ ] 是否把强势股直接称为龙头？
[ ] Evidence Gap 是否明确输出？
[ ] 是否存在无依据预测？
[ ] 是否在 baseline complete != true 时输出了高/低/强/弱等语义标签？
[ ] 是否把单日强度当作 persistence Evidence？
[ ] 是否在 persistence Evidence 不足时仍输出 confirmed market_regime？
[ ] 是否把历史校准结论写成未来因果 / 确定性预测？
[ ] 在无 advance / decline 时是否用 limit_up_count 替代 breadth？
[ ] 每个 numeric metric claim 是否已结构化写入 metric_claims？
[ ] 是否在无 frozen policy 时避免了 SEMANTIC？
[ ] MetricClaim 的 evidence_refs / baseline_refs 是否都在 evidence_registry 中？
[ ] Structured Output 是否符合 Schema？


## Self Check != Independent Eval

Self Check 是 Agent 输出前的自检；
Independent Eval 是外部、独立、deterministic 的判定。

两者不互相替代：
Self Check 通过不代表 Independent Eval 通过。

Self Check 失败时：

- 降低 Claim 强度；或
- 转为 Evidence Gap。