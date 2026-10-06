# Sector Data Capability Probe (Round 5A)

- **Date probed:** 2026-10-06 (last completed session 2026-09-30)
- **AkShare:** 1.19.1
- **Script:** `scripts/probe_sector_sources.py`
- **Raw dump:** `output/sector-probe/probe.json`
- **Status:** read-only probe. No production code / Skill / Schema / Eval changed.

Environment reminder: **Eastmoney `push2*` clist endpoints are unreachable here**
(NETWORK_ERROR / 502), so all `stock_board_*_em` capabilities are effectively
unavailable. THS (同花顺 / 10jqka), Sina, SW (申万) are reachable.

---

## 1. Candidate endpoints

| capability | library | source | endpoint | availability | taxonomy | date semantics | historical | units |
|---|---|---|---|---|---|---|---|---|
| industry taxonomy | akshare | ths | `stock_board_industry_name_ths` | AVAILABLE (90) | industry | current | taxonomy static | name,code |
| concept taxonomy | akshare | ths | `stock_board_concept_name_ths` | AVAILABLE (375) | concept | current | taxonomy static | name,code |
| industry ranking+snapshot | akshare | ths | `stock_board_industry_summary_ths` | AVAILABLE (90) | industry | **CURRENT_ONLY** | no | 涨跌幅 %, 总成交额 亿元, 家数 count |
| concept "summary" | akshare | ths | `stock_board_concept_summary_ths` | AVAILABLE (50) | concept | current | partially (event list) | NOT a ranking |
| industry history | akshare | ths | `stock_board_industry_index_ths` | AVAILABLE | industry | HISTORICAL (date range) | **yes** | OHLC points, 成交量 股, 成交额 元 |
| concept history | akshare | ths | `stock_board_concept_index_ths` | AVAILABLE | concept | HISTORICAL | **yes** | same |
| industry fund-flow rank | akshare | ths | `stock_fund_flow_industry` | AVAILABLE (90) | industry | **CURRENT_ONLY** | no | 涨跌幅 %, 净额 元?, 家数 count |
| concept fund-flow rank | akshare | ths | `stock_fund_flow_concept` | AVAILABLE (387) | concept | **CURRENT_ONLY** | no | same |
| industry spot+rank | akshare | sina | `stock_sector_spot(indicator="新浪行业")` | AVAILABLE (49) | industry | **CURRENT_ONLY** | no | 涨跌幅 %, 总成交额 元, 公司家数 |
| concept spot+rank | akshare | sina | `stock_sector_spot(indicator="概念")` | AVAILABLE (175) | concept | **CURRENT_ONLY** | no | same |
| industry constituents | akshare | sina | `stock_sector_detail(sector=<label>)` | AVAILABLE | industry | **CURRENT_MEMBERSHIP_ONLY** | no | changepercent %, amount 元, turnoverratio %, mktcap/nmc 万元 |
| concept constituents | akshare | sina | `stock_sector_detail(sector=<label>)` | AVAILABLE | concept | **CURRENT_MEMBERSHIP_ONLY** | no | same |
| SW L1/L2 taxonomy | akshare | sw | `sw_index_first_info` / `sw_index_second_info` | AVAILABLE (31/131) | industry | snapshot | no | 成份个数, PE, PB |
| SW constituents | akshare | sw | `sw_index_third_cons` | AVAILABLE | industry | **CURRENT snapshot (as-of latest)** | no | 市值, 近1日/近5日涨幅 (embedded) |
| index constituents | akshare | csindex/sina | `index_stock_cons` | AVAILABLE (e.g. 300) | index | current membership | no | code,name,纳入日期 |
| industry rank+cons | akshare | em | `stock_board_industry_name_em` / `_cons_em` / `_hist_em` | **UNAVAILABLE (network)** | unknown | — | — | — |
| concept rank+cons | akshare | em | `stock_board_concept_*_em` | **UNAVAILABLE (network/502)** | unknown | — | — | — |
| THS constituents | akshare | ths | `stock_board_industry_info_ths` / `stock_board_concept_info_ths` | BROKEN (empty HTML → IndexError) | — | — | — | — |

---

## 2. Ranking capability

- **Industry ranking (current):** `stock_board_industry_summary_ths` — 90 rows with
  `板块, 涨跌幅, 总成交量, 总成交额, 净流入, 上涨家数, 下跌家数, 均价, 领涨股, 领涨股-最新价, 领涨股-涨跌幅`.
  Gives ranking + **breadth (up/down)** directly. CURRENT_ONLY.
- **Industry ranking (alt):** `stock_fund_flow_industry("即时")` — `行业, 行业指数, 行业-涨跌幅, 流入资金, 流出资金, 净额, 公司家数, 领涨股`.
- **Concept ranking (current):** `stock_fund_flow_concept("即时")` (387) or Sina `stock_sector_spot("概念")` (175).
  THS `stock_board_concept_summary_ths` is **not** a ranking (event list).
- **No historical cross-sectional ranking** in any working source.
- Verdict: **AVAILABLE for current day only; historical ranking UNSUPPORTED.**

## 3. Constituents capability

- **Sina** `stock_sector_detail(sector=<label>)`: constituents with
  `code, name, changepercent, amount, turnoverratio, mktcap, nmc, per, pb`. Works for
  Sina industry (`new_blhy`, 19 stocks) and concept labels. **CURRENT_MEMBERSHIP_ONLY.**
- **SW** `sw_index_third_cons(symbol="801016.SI")`: 20 rows with `股票代码, 股票简称, 市值,
  市盈率, 市净率, ROE, 股息率, 近1日涨幅(2026-09-30), 近5日涨幅(2026-09-30)`. Snapshot as-of latest.
- **EM** constituents unavailable (network). **THS** constituents unavailable (broken).
- Verdict: **AVAILABLE (current membership) via Sina and SW; historical membership UNAVAILABLE.**

## 4. History capability

- **Sector history:** THS `stock_board_{industry,concept}_index_ths(symbol, start_date, end_date)`
  returns daily `日期, 开盘价, 最高价, 最低价, 收盘价, 成交量, 成交额`. HISTORICAL.
  → supports `sector_change_pct_5d/20d` and `sector_turnover vs history`.
- **Constituent history:** use existing `stock_zh_a_daily` (Sina) per stock → `stock_change_pct_5d/20d`.
  SW third_cons embeds 1d/5d but **not 20d**.
- Verdict: **sector index history AVAILABLE (THS); constituent history AVAILABLE via stock history.**

## 5. Breadth capability

- **Industry breadth:** `stock_board_industry_summary_ths` gives `上涨家数, 下跌家数` (no 平盘).
  `up_count`/`down_count` = AVAILABLE; `flat_count` = **UNAVAILABLE**.
- **Concept breadth:** NOT provided by any working ranking endpoint. `stock_sector_spot`
  gives `公司家数` (constituent count) but no up/down. → **UNAVAILABLE for concept.**
- Deriving breadth from constituents (Sina detail) is possible only if the constituent
  list is complete; Sina industry detail matched `公司家数` (19=19) → complete. Otherwise
  `breadth = unavailable` (never partial→full).

## 6. market_cap capability

- **Sina** `stock_sector_detail`: `mktcap` / `nmc` — verified unit **万元**
  (中国巨石 mktcap 1.577636e7 万元 ≈ 1577.6亿, consistent with price×shares).
- **SW** `sw_index_third_cons`: `市值` column present (unit not yet verified — treat as UNVERIFIED).
- **EM** `总市值/流通市值` unavailable (network).
- Verdict: **AVAILABLE (Sina, 万元)**; supports `market_cap >= 50B CNY` candidate filter.

## 7. 2026-09-30 replay capability

| capability | 2026-09-30 replay | reason |
|---|---|---|
| sector index momentum (5d/20d) | **YES** | THS index history by date range |
| cross-sectional sector ranking | **NO** | only CURRENT snapshots |
| sector constituents | **NO** | current membership only |
| sector breadth (up/down) | **NO** | current snapshot only |
| constituent 5d/20d | (partial) | via stock history, but membership is current |

→ Historical replay only if that date's ranking/constituents were **collected into the
Evidence Store on the day** (fits the frozen Replay design). Direct upstream replay of
2026-09-30 ranking/constituents is **NOT possible**.

## 8. Current-only endpoints

`stock_board_industry_summary_ths`, `stock_fund_flow_industry`, `stock_fund_flow_concept`,
`stock_sector_spot` (industry & concept), `stock_sector_detail`, `sw_index_third_cons`
(as-of latest), `stock_board_concept_summary_ths` (event list).
Historical: only `stock_board_{industry,concept}_index_ths`.

## 9. Cross-source universe mismatch

| taxonomy | industry count | concept count |
|---|---|---|
| THS | 90 | 375 (name list) / 387 (fund-flow) |
| Sina | 49 | 175 |
| SW | L1 31 / L2 131 | — |

- "半导体" differs across THS (`881121`) / Sina / SW: different names, members, 涨跌幅, classification.
- Even within THS, concept **name list (375)** ≠ concept **fund-flow list (387)** → UNIVERSE_MISMATCH.
- **Rule:** do not compose ranking from one source and constituents from another unless
  sector identity + universe are proven equivalent. Default = same Evidence Family = same source.

## 10. Units (verified from payloads)

| field | source | raw | normalized target |
|---|---|---|---|
| 涨跌幅 / changepercent / 行业-涨跌幅 | ths / sina | percent | percent |
| 总成交额 (summary_ths) | ths | 亿元 | ×1e8 → CNY |
| 成交额 (index_ths) | ths | 元 | CNY |
| 总成交额 (sina spot) | sina | 元 | CNY |
| amount (sina detail) | sina | 元 | CNY |
| turnoverratio | sina | percent | percent |
| mktcap / nmc | sina | 万元 | ×1e4 → CNY |
| 市值 (sw) | sw | UNVERIFIED | verify before use |
| 上涨家数/下跌家数/公司家数 | ths/sina | count | count |
| 成交量 (index_ths) | ths | 股 (approx) | shares |

Internal model normalization: `change_pct` percent, `turnover_cny` CNY,
`market_cap_cny` CNY, `turnover_rate_pct` percent.

## 11. Failure modes observed

| mode | observed example |
|---|---|
| NETWORK_ERROR | `stock_board_industry_cons_em`, `stock_board_industry_hist_em` (push2) |
| HTTP 502 | `stock_board_concept_name_em` |
| CURRENT_ONLY | all ranking/constituent snapshots |
| OUT_OF_RETENTION / UNSUPPORTED_HISTORY | no historical ranking/constituents |
| EMPTY_UPSTREAM_RESPONSE / broken parse | `stock_board_*_info_ths` (IndexError) |
| UNIVERSE_MISMATCH | THS concept 375 vs 387 |
| UNKNOWN (JSON decode) | `stock_sector_fund_flow_rank` |

Invariants: **Empty != Zero; Missing != Zero; Current != Historical.**

## 12. Recommended V0.1 source architecture

Keep **one Evidence Family per taxonomy** (no cross-source stitching):

- **Industry (THS family)**
  - taxonomy: `stock_board_industry_name_ths`
  - ranking/breadth (current): `stock_board_industry_summary_ths`
  - history: `stock_board_industry_index_ths` → 5d/20d momentum + turnover history
  - constituents: **Sina `stock_sector_detail`** OR **SW `sw_index_third_cons`** as a
    separate, explicitly-labelled membership family (current-only)
- **Concept (THS family for history, current ranking separately labelled)**
  - taxonomy: `stock_board_concept_name_ths`
  - history: `stock_board_concept_index_ths`
  - current ranking: `stock_fund_flow_concept` (label universe mismatch vs name list)
- **market_cap:** Sina `stock_sector_detail` (万元) for the membership family.
- All rankings marked `CURRENT_ONLY`; historical replay of ranking/constituents only via
  Evidence Store collected on the day.

## 13. P0 available fields

- `sector_id`, `sector_name`, `taxonomy` (industry via THS/SW; concept via THS/Sina)
- `date` = snapshot date (current)
- `change_pct` (percent) — THS industry summary / Sina spot / THS fund-flow
- `turnover_cny` — THS summary (亿元→元) / Sina spot (元) / THS index (元)
- `up_count`, `down_count` (industry, THS summary)
- `constituent_count` (公司家数 / 成份个数)
- **constituents:** `stock_code, stock_name, change_pct, turnover_cny, turnover_rate_pct,
  market_cap_cny` (Sina detail)
- **history:** `sector_change_pct_5d/20d`, `sector_turnover vs history` (THS index)
- **constituent history:** `stock_change_pct_5d/20d` via `stock_zh_a_daily`

## 14. P0 unavailable fields

- historical cross-sectional **ranking** (any date ≠ current)
- historical **constituent membership** (all sources current-only)
- `flat_count` (all sources)
- **concept breadth** `up_count/down_count` (no working source)
- direct 20d constituent return (must compute from stock history)
- SW `市值` unit unverified

## 15. Evidence Gaps

- Historical sector ranking + constituents → **CURRENT_ONLY**; 2026-09-30 sector replay
  impossible unless collected that day.
- Constituent membership drift / survivorship (current membership used for past dates).
- Concept breadth missing.
- Cross-source taxonomy not mappable → no THS-ranking + EM-constituents composition.
- Eastmoney family entirely unavailable in this environment.
- THS constituents endpoint broken.

## 16. 是否足够进入 Sector Provider Implementation

**PARTIAL**

- Enough to implement a **current-day Sector Provider V0.1**:
  industry ranking + breadth + turnover (THS), sector 5d/20d history (THS),
  current constituents + market cap (Sina/SW), constituent 5d/20d via stock history.
- **Not** enough for full historical sector replay; ranking/constituents must be
  collected daily into the Evidence Store and explicitly marked `CURRENT_ONLY` /
  `CURRENT_MEMBERSHIP_ONLY` with Evidence Gaps.
- Recommend proceeding to Sector Provider implementation **only** with these boundaries
  frozen as first-class evidence semantics (per-taxonomy single-source families).

> Not starting implementation. No Sector Tool / News / LLM Agent added.
