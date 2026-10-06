# market-mcp

A 股行情数据的 MCP server，是 `a-share-review` 的第一个模块。

## 目录结构

```text
market-mcp/
├── server.py              # MCP server 入口，暴露行情工具
├── data/
│   └── mock_market.json   # 第一版的 mock 行情数据（无需外部 API）
├── requirements.txt       # 依赖
└── README.md
```

## 提供的工具

| 工具 | 说明 | 参数 |
| --- | --- | --- |
| `get_index_performance` | 返回指定交易日的 A 股主要指数行情（开收盘、涨跌幅、成交额） | `date`：交易日期 `YYYY-MM-DD` |
| `get_sector_ranking` | 返回指定交易日板块按涨跌幅从高到低的排名 | `date`：交易日期；`limit`：返回数量，正整数，默认 10 |
| `get_sector_detail` | 返回指定交易日某个板块的详细表现及领涨个股 | `date`：交易日期；`sector_name`：板块名称 |
| `get_stock_detail` | 返回指定交易日某只个股的行情与交易数据 | `date`：交易日期；`stock_code`：股票代码，如 `600519.SH` |
| `get_stock_news` | 返回指定交易日某只个股的相关新闻与公开事件 | `date`：交易日期；`stock_code`：股票代码；`limit`：返回数量上限，正整数，默认 10 |

所有工具只返回事实数据，不做市场评价或投资判断。日期不存在、板块不存在或 `limit` 非法时，返回 `success=false` 及 `error` 字段。

## 安装与运行

```bash
pip install -r requirements.txt
python server.py
```

默认以 **stdio** 方式运行，供支持 MCP 的客户端（如 Qwen Code、opencode）连接。

## 说明

- 第一版数据来自 `data/mock_market.json`，**不依赖任何外部接口或 API Key**。
- 后续接入真实数据源时，再引入 `.env` 管理密钥（已预留 `python-dotenv` 依赖）。
