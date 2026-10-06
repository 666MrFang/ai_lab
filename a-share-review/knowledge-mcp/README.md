# knowledge-mcp

A 股复盘历史知识库的 MCP server，是 `a-share-review` 的第二个模块。

## 职责

- `market-mcp` 回答：**今天发生了什么？**（结构化行情事实）
- `knowledge-mcp` 回答：**截至某个日期，历史知识库中有哪些相关资料？**（检索到的历史文本上下文）
- Review Skill / Agent 回答：**这些 Evidence 意味着什么？**

`knowledge-mcp` 只返回 Retrieved Historical Context，
不生成 market_regime / 主线 / 因果 / 看多看空 / 预测 / 交易建议。

## 目录结构

```text
knowledge-mcp/
├── server.py              # MCP server 入口，暴露检索工具
├── test_future_leakage.py # Future Leakage 防护测试（临时目录，不污染正式数据）
├── requirements.txt       # 依赖
└── README.md
```

## 提供的工具

| 工具 | 说明 | 参数 |
| --- | --- | --- |
| `search_review_knowledge` | 检索历史复盘与市场规则，返回截至 `as_of_date` 可用的历史文本上下文 | `query`；`as_of_date`（`YYYY-MM-DD`）；`top_k`（正整数，默认 5）；`retriever`（默认 `tfidf`） |

### Retriever 选择

- 当前固定 Eval Set 的真实结果：TF-IDF Mean Recall@5 = 0.527，
  Embedding = 0.460，Hybrid = 0.510。
- 因此 **V0.1 默认 `tfidf`**：它是当前最佳 baseline，且没有 embedding runtime dependency。
- 代码保留 `retriever="embedding"` / `"hybrid"`，采用惰性 import；
  使用它们需要在同一 Python 环境安装 `numpy` 与 `sentence-transformers`。

## Metadata 与时间安全

Document / Chunk metadata：

```text
document_id     文件名 stem
document_type   HISTORICAL_REVIEW | RULE | UNKNOWN
document_date   YYYY-MM-DD 或 null
source
heading
content
```

仅依据文件名解析（不依赖正文自然语言日期）：

- `YYYY-MM-DD-review.md` → `HISTORICAL_REVIEW` + 该日期
- `market-rules.md` → `RULE` + `null`

`as_of_date` 过滤（**在 retrieval ranking 之前**执行）：

- `HISTORICAL_REVIEW`：仅当 `document_date < as_of_date`（**严格小于**）
- `RULE`：不受日期限制
- `UNKNOWN`：过滤模式下 fail-closed，排除
- `as_of_date` 非法 → 返回 `success=false` 与明确 `error`

严格小于的原因：复盘 2026-10-08 时，`2026-10-08-review.md`
通常是当天复盘生成的结果，不能作为生成当天复盘的输入。

## 安装与运行

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe server.py
```

默认以 **stdio** 方式运行，供支持 MCP 的客户端（如 opencode）连接。
`server.py` 直接复用 `../rag` 中的 Mini RAG 代码，不复制 RAG 实现。

## 测试

```bash
.venv\Scripts\python.exe test_future_leakage.py
```
