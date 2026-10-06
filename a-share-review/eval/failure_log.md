# Failure Log

本文件记录 A-Share Review Agent 在开发、评测和回归过程中发现的重要 Failure。

Failure 的目的不是记录所有错误日志，而是记录能够推动：
- Skill 改进
- Tool 改进
- RAG 改进
- Schema 改进
- Eval Case 增加

的系统性问题。

---

## RAG-F001 - TF-IDF 对语义改写检索能力不足

### Status

OPEN

### Component

RAG / Retrieval

### Observed In

Retrieval Eval Q4

### Query

市场从混乱轮动逐渐走向一致的迹象有哪些？

### Expected

应该能够检索到市场状态演化相关的历史复盘：

- 2026-09-28-review::市场判断
- 2026-09-29-review::市场判断
- 2026-09-30-review::市场判断
- 2026-09-30-review::板块

### Actual

TF-IDF Recall@5 = 0.25。

Embedding Recall@5 = 0.50。

### Root Cause

Query 与历史复盘使用了不同的词面表达。

TF-IDF 更依赖 lexical overlap，无法充分识别：

“混乱轮动逐渐走向一致”

与：

“ROTATION 向 MAIN_UPTREND 候选状态演化”

之间的语义关系。

### Improvement Candidate

引入 Semantic Retrieval，并进一步评估 Hybrid Retrieval。

### Regression

Q4 必须长期保留在 Retrieval Eval 中。

---

## RAG-F002 - Embedding 出现语义过度泛化

### Status

OPEN

### Component

RAG / Retrieval

### Observed In

Retrieval Eval Q3

### Query

最近市场接力赚钱效应发生了什么变化？

### Expected

重点检索：

- 2026-09-28-review::短线生态
- 2026-09-29-review::短线生态
- 2026-09-30-review::短线生态
- market-rules::赚钱效应

### Actual

TF-IDF Recall@5 = 0.50。

Embedding Recall@5 = 0.25。

Embedding 检索出多个“市场状态”和“市场判断” Chunk，
但遗漏三个关键“短线生态” Chunk。

### Root Cause

Embedding 能识别“市场、赚钱效应、状态变化”等整体语义，
但对本 Query 所要求的“接力生态变化”粒度不够精确。

属于：

Semantic Relevance != Task Relevance

### Improvement Candidate

Hybrid Retrieval / Metadata / Query Decomposition。

### Regression

Q3 必须长期保留。

---

## RAG-F003 - Binary Ground Truth 可能过于严格

### Status

OPEN

### Component

RAG / Eval

### Observed In

Retrieval Eval Q5

### Query

市场风险偏好是不是正在修复？

### Actual

Embedding Hit@5 = 0。

但返回的：

- 市场判断
- 市场状态
- 赚钱效应

部分 Chunk 实际具有辅助相关性。

### Root Cause

当前 Eval 只有：

Relevant / Irrelevant

二值判断。

现实中的 Retrieval Relevance 可能存在：

- Highly Relevant
- Relevant
- Weakly Relevant
- Irrelevant

### Improvement Candidate

当前阶段暂不修改。

未来如果 Retrieval Eval 精度要求提高，
可引入 graded relevance / NDCG。

### Regression

保留 Q5。

---

## RAG-F004 - Temporal Query 无法仅靠普通 Top-K Similarity 满足

### Status

OPEN

### Component

RAG / Context Construction

### Observed In

Retrieval Eval Q3

### Query

最近市场接力赚钱效应发生了什么变化？

### Expected Context

需要形成时间序列：

2026-09-28
→ 2026-09-29
→ 2026-09-30

### Problem

即使 Retriever 返回一个高度相关的 2026-09-30 Chunk，
也不足以回答“发生了什么变化”。

### Root Cause

Retrieval Relevance != Answer Sufficiency。

Temporal Query 不仅要求相关性，
还要求跨时间 Evidence Coverage。

### Improvement Candidate

未来增加：

- metadata date
- temporal query detection
- multi-date context construction

当前 Mini RAG 阶段暂不实现。

### Regression

Q3 同时作为 Retrieval 和 Temporal Coverage Case 保留。

## RAG-F005 - RRF 可能抑制仅由单路 Retriever 召回的相关 Chunk

### Status

OPEN

### Component

RAG / Hybrid Retrieval

### Observed In

Retrieval Eval Q5

### Query

市场风险偏好是不是正在修复？

### Expected

至少应该保留与短线生态相关的历史 Chunk。

### Actual

TF-IDF 能够命中一个 Relevant Chunk。

Embedding 未命中 Relevant Chunk。

经过 RRF Fusion 后，
TF-IDF 单路召回的 Relevant Chunk 被挤出最终 Top-5。

结果：

TF-IDF Hit@5 = 1

Embedding Hit@5 = 0

Hybrid Hit@5 = 0

Hybrid Mean Recall@5 = 0.510，
仍低于 TF-IDF 的 0.527。

### Root Cause

RRF 根据多个 Retriever 的排名进行融合。

同时被多个 Retriever 排名靠前的 Chunk
会获得更高的累计 RRF score。

因此，一个只被单个 Retriever 高度认可、
但未被另一个 Retriever 召回或排名较低的 Relevant Chunk，
可能被两个 Retriever 都“部分认可”的非 Ground Truth Chunk 挤出 Top-K。

因此：

Retriever Fusion
!=
Relevant Result Union

### Improvement Candidate

未来可评估：

- larger candidate pool
- weighted RRF
- result diversification
- query routing
- reranking
- relevance-aware fusion

当前 Mini RAG 阶段不继续优化。

### Regression

Q5 必须长期保留，
用于检测 Hybrid Retrieval 对 single-retriever unique hit 的抑制。

RAG-F007
Metadata Classification Failure Is Silent

现象：
无法识别的 Knowledge Document 被归类 UNKNOWN，
随后被 temporal filter fail-closed 排除，
但系统没有 warning / rejected-document 信息。

影响：
合法知识可能因为命名错误或新增文档类型而静默消失，
Agent 无法区分：
“知识库里没有相关知识”
和
“知识存在，但 metadata classification 失败”。

典型场景：
- market-rules-v2.md
- 新增规则文档
- 2026-9-30-review.md 命名错误

当前策略：
UNKNOWN 继续 fail-closed，不允许参与 Retrieval。

未来改进：
显式 metadata / manifest / directory convention；
同时增加 rejected/unknown document observability。

Regression：
构造 UNKNOWN document，
验证：
1. 不进入 eligible chunks
2. 系统能够观察到它被拒绝及原因

## AGENT-F001 — Forced Regime Classification Under Insufficient Persistence Evidence

### Category

Agent / Skill Compliance / Evidence Discipline / Schema Design

### Status

OPEN

### Scenario

在 2026-10-08 A股复盘中，Agent 需要判断当前市场阶段：

- MAIN_UPTREND
- ROTATION
- LOSS_EFFECT
- ICE_POINT
- UNCERTAIN

Agent 最终输出：

state = MAIN_UPTREND
confidence = MEDIUM

### Observed Behavior

Agent 使用以下 Evidence 支持 MAIN_UPTREND：

- 三大指数上涨
- 上涨家数明显多于下跌家数
- 成交额高于前一日、5 日均值和 20 日均值
- 涨停数量多于跌停数量
- 科技方向当日领涨

但 Agent 同时已经识别出：

- 缺少 2026-10-08 当周多日市场数据
- 缺少板块多日持续性数据
- 缺少核心个股持续性 Evidence
- 缺少高位核心股分歧后修复 Evidence
- Historical Review 最新仅到 2026-09-30
- 2026-09-30 → 2026-10-08 存在时间缺口
- 无法证明期间市场状态连续

在这些关键 Evidence 缺失的情况下，
Agent 仍然选择 MAIN_UPTREND，而不是 UNCERTAIN。

### Expected Behavior

MAIN_UPTREND 不应仅由单日市场强势推导。

如果 MAIN_UPTREND 定义所要求的关键 Evidence，例如：

- 主线持续性
- 核心个股持续性
- 赚钱效应持续性
- 高位核心股分歧后的修复能力
- 多日市场结构

无法验证，则 Agent 应降低状态判断强度。

更合理的结果应为：

state = UNCERTAIN

并在解释中记录：

candidate_state = MAIN_UPTREND
alternative_state = ROTATION

以及：

Current evidence leans toward MAIN_UPTREND,
but persistence evidence is insufficient.

### Root Cause

1. Agent 存在“必须完成分类”的倾向。
2. Skill 虽然要求 Evidence Gap，但没有足够强地规定：
   缺失 Market Regime 的必要 Evidence 时必须输出 UNCERTAIN。
3. Schema 当前主要表达单一 state，
   对 candidate state / alternative state 的表达能力有限。
4. 单日强势 Evidence 被过度用于多日市场阶段判断。

### Risk

可能将：

“今天市场表现较强”

错误升级为：

“市场已经进入主升阶段”。

这会导致 Market Regime 的 Claim 强于实际 Evidence。

### Regression Test

构造：

- 单日指数上涨
- Breadth 较强
- 成交额放大
- 涨停数量较多
- 当日存在明显领涨板块

但：

- 无多日板块持续性
- 无核心股持续性
- 无高位修复数据
- Historical Context 存在时间缺口

验证 Agent 不得仅凭单日 Evidence
直接给出 MAIN_UPTREND 的确定性判断。

Expected:

UNCERTAIN

或等价的“MAIN_UPTREND candidate，但证据不足以确认”。

---

## AGENT-F002 — Uncalibrated Metric Semantic Interpretation

### Category

Agent / Evidence Discipline / Metric Calibration

### Status

OPEN

### Scenario

在 2026-10-08 A股复盘中，Market Tool 返回：

- 炸板率 = 25.27%
- 昨日涨停晋级率 = 29.09%

Agent 推断：

“接力环节存在一定分歧与失败。”

### Observed Behavior

25.27% 和 29.09% 是有效的 Numeric Facts。

但当前系统没有提供：

- 炸板率历史均值
- 炸板率历史分位
- 晋级率历史均值
- 晋级率历史分位
- 强/弱阈值
- 不同市场阶段下的参考区间

Agent 自己也记录了：

“炸板率与晋级率缺少历史基准，
无法判断 25.27% / 29.09% 处于何种相对水平。”

但仍然把这些数值解释成：

“存在一定分歧”。

### Expected Behavior

在没有 Baseline / Threshold / Historical Distribution 时：

允许：

“今日炸板率为 25.27%。”
“昨日涨停晋级率为 29.09%。”
“今日存在 23 家炸板。”

不允许直接推出：

- 炸板率较高
- 炸板率适中
- 晋级率较低
- 接力较弱
- 接力较强
- 分歧较大
- 情绪较好/较差

更合理的输出：

“今日炸板率 25.27%，昨日涨停晋级率 29.09%。
由于缺少历史基准或明确阈值，
当前无法判断这些指标处于高位、低位或正常区间，
因此不据此单独判断接力生态强弱。”

### Root Cause

Agent 将：

Numeric Fact

直接映射成：

Semantic Interpretation

但中间缺少：

Reference Frame / Baseline / Threshold。

即：

Numeric Fact
    ↓
[缺失 Calibration]
    ↓
High / Low / Strong / Weak / Divergence

### Risk

该问题不仅影响炸板率。

同类风险包括：

- 换手率 8% → “活跃”
- 成交额 2 万亿 → “高”
- PE 30 → “估值贵”
- 晋级率 30% → “接力差”
- 北向流入 100 亿 → “资金明显流入”
- 振幅 10% → “分歧巨大”

如果缺少 Reference Frame，
这些语义判断都可能形成 Claim > Evidence。

### Regression Test

给 Agent 一个指标：

metric = 25.27%

但不提供：

- historical_average
- percentile
- threshold
- comparison_period

验证 Agent：

PASS:
“指标当前值为 25.27%，缺少历史基准，无法判断相对高低。”

FAIL:
“25.27% 较高。”
“25.27% 说明市场分歧明显。”
“25.27% 说明接力较弱。”

只有在 Tool / Historical Statistics 提供有效基准后，
才允许进一步做强弱语义判断。