# Product Spec

## 1. Product Name

Crypto Trading Data Miner

## 2. Product Vision

建立一套面向 crypto 量化交易的資料與交易系統，支援從研究、回測、paper trade 到 live trade 的完整閉環，並以統一資料模型管理市場資料、策略訊號、訂單成交、部位、績效與風控事件。

本產品的核心目標不是只做資料收集，而是提供一個可持續擴充的交易基礎設施，讓使用者可以：

- 收集與管理多交易所市場資料
- 建立標準化資料庫供研究與回測使用
- 產生策略訊號並追蹤版本
- 執行 paper trade 與 live trade
- 做績效分析、風控檢查與審計追蹤

## 3. Product Goals

### 3.1 Primary Goals

1. 建立可共用於 backtest / paper / live 的統一資料模型
2. 支援 crypto spot 與 perpetual futures 商品
3. 建立可靠的市場資料收集與儲存流程
4. 建立可重現的回測系統
5. 建立可觀測的 execution 與風控流程

### 3.2 Secondary Goals

1. 支援多策略並行運行
2. 支援多帳戶與多交易所
3. 支援策略版本管理與回測版本追蹤
4. 支援績效歸因與報表分析

### 3.3 Non-Goals for V1

1. 不在 V1 處理 options 定價與 Greeks
2. 不在 V1 建立高頻撮合模擬器
3. 不在 V1 提供完整前端 UI
4. 不在 V1 支援鏈上交易與 DeFi execution

## 4. Target Users

### 4.1 Primary Users

- 個人量化交易開發者
- 小型量化團隊
- 需要自建交易資料基礎設施的研究者

### 4.2 User Needs

- 能快速收集乾淨且一致的市場資料
- 能清楚定義交易商品與交易規則
- 能建立策略並進行可重現回測
- 能無縫切換到 paper trade 與 live trade
- 能在出問題時追查訊號、訂單、成交與風控紀錄

## 5. Problem Statement

多數 crypto 量化系統在早期只重視 K 線與策略回測，忽略了商品主檔、funding、mark price、交易費率、execution log、風控事件與審計資料。結果是：

- 回測結果與實盤表現落差大
- paper trade 與 live trade 流程不一致
- 發生異常時難以追查原因
- 無法明確知道某次績效來自策略、滑價還是手續費

本產品要解決的是：把研究、執行、對帳、績效分析與風控追蹤放在同一套資料基礎之上。

## 6. Core User Flows

### 6.1 Market Data Flow

1. 系統從交易所抓取 market data
2. 將原始資料轉成統一格式
3. 寫入資料庫
4. 供研究、特徵計算與回測使用

### 6.2 Strategy Research Flow

1. 使用者選定商品池與時間區間
2. 讀取 bars / trades / funding / open interest
3. 產生特徵與訊號
4. 執行回測
5. 寫入 backtest run 與 performance summary

### 6.3 Paper Trading Flow

1. 策略版本啟動
2. 即時市場資料更新
3. 產生 signal 與 target position
4. 產生 paper order / simulated fill
5. 更新 position / balance / PnL

### 6.4 Live Trading Flow

1. 策略版本啟動
2. 根據 signal 產生 order
3. 送單到交易所
4. 收到 ack / reject / fill
5. 更新 orders / fills / positions / balances
6. 風控系統同步監控風險狀態

## 7. Product Scope

## 7.1 V1 Functional Scope

### A. Reference Data
- exchange master
- asset master
- instrument master
- fee schedule

### B. Market Data
- 1m OHLCV bars
- trades
- funding rates
- open interest

### C. Strategy Layer
- strategy registry
- strategy versioning
- signals
- target positions

### D. Execution Layer
- accounts
- orders
- fills
- positions
- balances

### E. Backtest Layer
- backtest runs
- simulated orders
- simulated fills
- performance summary
- performance timeseries

### F. Risk and Ops
- risk limits
- risk events
- system logs

## 7.2 Future Scope

- order book snapshot / delta storage
- feature store
- portfolio optimizer
- execution router abstraction
- web dashboard
- alerting and notification
- strategy deployment workflow

## 8. Functional Requirements

### 8.1 Reference Data Requirements

The system shall:

1. 支援新增與維護交易所主檔
2. 支援新增與維護資產主檔
3. 支援不同交易所商品映射到統一商品代碼
4. 支援紀錄 tick size、lot size、min qty、min notional、contract size
5. 支援商品狀態，如 trading / paused / delisted

### 8.2 Market Data Requirements

The system shall:

1. 支援按交易所與商品收集 1m bars
2. 支援收集 trade-level 成交資料
3. 支援收集 funding rate
4. 支援收集 open interest
5. 支援同時記錄 event time 與 ingest time
6. 支援資料缺口檢查與補資料流程

### 8.3 Strategy Requirements

The system shall:

1. 支援策略註冊
2. 支援策略版本管理
3. 支援將參數存成 JSON
4. 支援紀錄 signal time、signal type、direction、score
5. 支援紀錄 target qty / target notional

### 8.4 Execution Requirements

The system shall:

1. 支援同一 execution schema 用於 backtest / paper / live
2. 支援紀錄 order lifecycle：new / submitted / partial / filled / canceled / rejected
3. 支援紀錄 client order id 與 exchange order id
4. 支援紀錄 fill、fee、liquidity flag
5. 支援更新 current positions 與 balance snapshots

### 8.5 Backtest Requirements

The system shall:

1. 支援建立 backtest run metadata
2. 支援紀錄使用的 strategy version
3. 支援紀錄 market data / fee model / slippage model version
4. 支援輸出 simulated orders 與 simulated fills
5. 支援輸出 performance summary 與 equity curve

### 8.6 Risk Requirements

The system shall:

1. 支援每個 account 設定 risk limits
2. 支援 max position / max notional / max leverage / max daily loss
3. 支援記錄 risk events
4. 支援 kill switch 類型事件在後續版本擴充

### 8.7 Ops Requirements

The system shall:

1. 支援記錄 system logs
2. 支援區分 service name / log level / context
3. 支援追蹤資料收集或交易流程異常

## 9. Non-Functional Requirements

### 9.1 Reliability
- 市場資料寫入需具備冪等性
- 重複事件不可造成主資料重複污染
- order / fill 寫入需可追蹤來源與狀態

### 9.2 Scalability
- 高交易量資料需能在後續拆分到 ClickHouse 或 object storage
- transactional data 與 high-volume market data 設計上需可分層

### 9.3 Reproducibility
- 回測需可重現
- 策略版本、參數、資料版本、fee/slippage 假設需可追溯

### 9.4 Observability
- 所有核心流程需保留 event log
- 市場資料收集、signal 產生、送單與成交需可追查

## 10. Data Model Principles

1. Raw data 與 normalized data 分開管理
2. 所有時間資料優先使用 UTC
3. 所有市場事件至少保留 event_time 與 ingest_time
4. 所有 execution records 保留 internal id 與 external id
5. 所有會影響結果的邏輯都需要 version 化

## 11. V1 System Components

### 11.1 Database
- PostgreSQL for reference data, execution data, backtest metadata

### 11.2 Cache / Realtime State
- Redis for short-lived state and latest snapshots

### 11.3 Data Ingestion
- exchange REST / websocket collectors

### 11.4 Backtest Engine
- historical replay with configurable fee / slippage assumptions

### 11.5 Execution Engine
- paper executor
- live exchange adapter

### 11.6 Risk Engine
- pre-trade risk checks
- post-trade risk monitoring

## 12. Success Metrics

### 12.1 Product Metrics
- 能成功收集至少 2 個交易所的主要商品資料
- 可對至少 1 個策略完成可重現回測
- 可成功跑通 1 個 paper strategy 的完整 signal-to-fill 流程
- 可成功寫入 live trading 的 order / fill / position 紀錄

### 12.2 Data Quality Metrics
- bars 缺口率低於預設門檻
- funding / open interest 更新延遲可監控
- 重複 trade 寫入率接近 0

### 12.3 Execution Metrics
- order lifecycle 完整率
- fill 對帳成功率
- fee 與 PnL 計算一致性

## 13. Risks and Constraints

### 13.1 Risks
- 各交易所 API 格式不一致
- funding / mark price / open interest 可用性不同
- live trading 需要處理延遲與斷線問題
- 只用 K 線回測會低估 execution friction

### 13.2 Constraints
- V1 以基礎設施優先，不做完整 GUI
- V1 先支援少量交易所與少量商品
- V1 先以集中式交易所為主

## 14. Milestones

### Milestone 1: Data Foundation
- 完成 reference data schema
- 完成 bars / trades / funding / OI schema
- 完成基礎資料匯入流程

### Milestone 2: Research and Backtest
- 完成 strategy / signal schema
- 完成 backtest runs 與 performance summary
- 完成最小可用回測流程

### Milestone 3: Paper Trading
- 完成 paper order / fill 模型
- 完成 position / balance 更新流程
- 完成基本風控檢查

### Milestone 4: Live Trading
- 完成第一個交易所 adapter
- 完成 live orders / fills / positions 寫入
- 完成 system logs 與風控事件追蹤

## 15. Open Questions

1. V1 優先支援哪些交易所？
2. V1 主要做 spot、perp，還是兩者都支援？
3. 回測最小粒度是 1m bars 還是要支援 trades replay？
4. 是否需要一開始就支援多帳戶資金管理？
5. 是否需要在 V1 就加入 feature store？

## 16. Recommended Immediate Next Steps

1. 補 `002_seed.sql`，初始化 exchanges / assets / instruments
2. 建立 `src/ingestion/` 模組，先從單一交易所收 1m bars 與 funding
3. 建立 `src/backtest/` 模組，先支援 bars-based 回測
4. 建立 `src/execution/` 模組，先實作 paper trading executor
5. 建立 `docs/api-contracts.md`，定義 signal、order、fill 的欄位契約
