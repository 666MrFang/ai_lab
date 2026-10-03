# QWEN.md

本文件为 Qwen Code 在本仓库中工作时的指导上下文。若本文件与代码/配置不一致，**以实际文件为准**。

## 项目概览

- **名称**：`ai-lab`（`pyproject.toml` 中 `version = "0.1.0"`）
- **性质**：个人 AI Engineering 学习实验项目
- **目标**（据 `README.md`）：
  1. 学习 AI Coding
  2. 学习 Skill
  3. 学习 MCP
  4. 学习 Agent
  5. 最终制作 **A 股复盘工具**
- **当前状态**：早期骨架阶段。除 `03-coding/hello_ai.py` 外，各主题目录尚为空；依赖、测试、版本控制均未建立。

## 技术栈与运行环境

- **语言**：Python，`requires-python = ">=3.12"`；`.venv` 实际为 CPython 3.12。
- **环境/包管理**：**uv**（`.venv/pyvenv.cfg` 记录 `uv = 0.12.21`，`include-system-site-packages = false`）。
- **IDE**：PyCharm（`.idea/`），Python SDK 指向 `D:\ai_lab\.venv`。
- **依赖**：`pyproject.toml` 中 `dependencies = []`，目前**未声明任何第三方依赖**，`.venv` 内也未安装任何第三方包。

### 计划中的依赖（来自 `.idea/inspectionProfiles/Project_Default.xml`，**尚未落地**）

| 包 | 预期用途 |
| --- | --- |
| `litellm` | 统一调用各家大模型 API（LLM 抽象层） |
| `fastapi` / `uvicorn` | 将能力暴露为 HTTP 服务 |
| `pydantic` | 数据模型与参数校验 |
| `python-dotenv` | 管理 API Key 等密钥 |
| `google-search-results` (SerpAPI) | 联网搜索工具 |
| `exchange-calendars` | 交易日历（金融场景） |
| `json-repair` | 容错解析大模型返回的 JSON |

> 该列表是"意图中的技术栈"的证据，不代表已安装；实际以 `pyproject.toml` 与 `uv.lock` 为准（当前均无）。

## 目录结构

```
D:\ai_lab\
├── pyproject.toml              # 项目声明（最小化：name/version/requires-python，无依赖、无 build-system）
├── README.md                   # 项目目标说明（唯一的目标文档）
├── QWEN.md                     # 本文件
├── .idea\                      # PyCharm 工程配置（含 inspectionProfiles/）
├── .venv\                      # uv 创建的虚拟环境（无第三方包）
├── 01-llm\                     # 空：大模型基础
├── 02-context\                 # 空：上下文工程
├── 03-coding\                  # 含 hello_ai.py：AI Coding 练习
├── 04-skills\                  # 空：Skill
├── 05-mcp\                     # 空：MCP
├── 06-agent\                   # 空：Agent
├── 07-rag\                     # 空：RAG 检索增强
├── 08-eval\                    # 空：评估
└── astock-review\              # 空：最终目标——A 股复盘工具
```

目录命名是 `01`→`08` 的**递进式学习路线**，编号即建议的学习顺序。

## 构建与运行（Building and Running）

- **创建/同步环境**：
  ```
  uv sync
  ```
- **运行脚本**：
  ```
  uv run python 03-coding/hello_ai.py
  ```
  或直接使用虚拟环境解释器：
  ```
  .venv\Scripts\python.exe 03-coding\hello_ai.py
  ```
- **新增依赖**：
  ```
  uv add <package>
  ```
- **测试**：TODO —— 仓库尚无测试框架与用例。
- **Lint / 格式化**：TODO —— 尚未配置（建议 ruff）。
- **构建/打包**：TODO —— `pyproject.toml` 无 `[build-system]`，当前不是可安装包。

## 开发约定

- 代码按**主题目录**组织；每个主题目录存放该主题的练习/示例，`astock-review` 为最终落地应用。
- 尚未建立正式约定（代码风格、测试、提交流程）。如需确立，建议：`ruff`（风格/静态检查）+ `pytest`（测试）+ `.env`（密钥）。
- **版本控制注意**：仓库当前**没有 Git**，也**没有根级 `.gitignore`**。若初始化 Git，请先忽略 `.venv/`、`__pycache__/`、`.idea/`、`.env`、`*.pyc`。
- **密钥安全**：`astock-review` 预期会用到 LLM/搜索 API Key，一律通过 `.env` 管理，**禁止提交密钥**。

## 现状与已知问题

- `03-coding/hello_ai.py`：仅含一个 `calculate_checksum()`（普通累加后 `& 0xffff`，即 16 位截断和），无 docstring、无类型注解、无 `if __name__` 入口，且内容与文件名中的 "ai" 无关；疑似未完成的练习代码。
- `01-llm`、`02-context`、`04-skills`、`05-mcp`、`06-agent`、`07-rag`、`08-eval`、`astock-review`：均为**空目录**。
- 空目录若纳入 Git 不会被跟踪，需要时用 `.gitkeep` 或该目录下的 `README.md` 占位。
- 无测试、无 CI、无 `uv.lock`、无依赖声明。

## 给未来交互的提示

- 用户以**中文**交流；回复使用中文。
- 动手前先确认要操作的主题目录，避免混淆不同阶段的代码。
- 未经明确要求，不要改动 `01`→`08` 的目录结构与主题划分，也不要擅自新增依赖。
- `astock-review` 是项目最终目标，涉及金融数据与外部 API，注意合规与密钥管理。
