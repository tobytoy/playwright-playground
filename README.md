# 🌐 Universal Website Health & Quality Inspector (Playwright-based)

全方位網站健康與品質自動巡檢工具。專為現代 Web 應用程式設計，透過 Playwright 無頭瀏覽器模擬真實使用者行為，全面監控並捕獲前端執行階段異常、後端 API 崩潰、UI 假死轉圈、白畫面渲染缺陷、開發機網址洩漏及 iframe 異常。

---

## 🚀 核心功能特色

- **多維度啟發式探針 (Heuristic Probes)**：
  - 🚨 **執行階段異常 (Runtime & Console)**：捕獲 `window.onerror`、未處理的 JavaScript 例外、CSP 安全策略阻擋、`console.error`。
  - 🔌 **後端 API 健全度 (Network & API)**：即時監聽 XHR / Fetch 請求，記錄 HTTP 4xx / 5xx 與失敗原因。
  - 🔄 **UI 死鎖與轉圈檢測 (Stuck Spinner)**：自動識別常見 Loading / Spinner 元件，在逾時後仍未消除時判定為卡死。
  - 📄 **白畫面檢測 (Blank Page Detection)**：依據 DOM 節點密度與可視文字長度進行綜合評估。
  - 🔒 **開發機位址洩漏檢測 (Localhost Leak)**：全 DOM 標籤屬性（`src`, `href`）與 Network 請求檢查，杜絕 `localhost:44331` 或內部 IP 流入生產環境。
  - 🖼️ **外嵌與 iframe 檢查 (Iframe Brokenness)**：追蹤外嵌服務（如監控看板）之 HTTP 響應與 404 狀態。
- **全通用設計 (Universal Site Support)**：
  - 既能針對特定站點（如 TDX）依據 YAML 設定檔深度檢測關鍵業務頁面。
  - 亦可直接輸入任意網址 (`--url <https://...>`)，甚至開啟 `--crawl` 進行全站同源自動爬取巡檢。
- **三重格式報告輸出 (Multi-format Reporting)**：
  - **HTML 儀表板 (`reports/report.html`)**：現代感深色主題、KPI 指標、問題嚴重度分級過濾、頁面渲染截圖存檔、網路失敗明細與堆疊追蹤。
  - **Markdown 摘要 (`reports/report.md`)**：適合貼附於 GitHub Issue、Pull Request 評論或維運會議提報單。
  - **JSON 結構化資料 (`reports/report.json`)**：適合整合至 CI/CD Pipeline（當發現致命 Critical 問題時 exit code 為 1）。

---

## 🛠️ 環境需求與安裝

使用 Python 3.10+（推薦使用 Conda `toby` 環境）：

```bash
# 啟用 conda 環境
conda activate toby

# 安裝依賴 (若尚未安裝)
pip install -r requirements.txt

# 安裝 Playwright 瀏覽器
playwright install chromium
```

---

## 💻 使用方式

### 1. 啟動 Streamlit 視覺化操作介面（推薦 🌟）
透過現代化網頁介面自由切換設定檔、即時調整路徑、一鍵開始巡檢並即時檢視報告與截圖：

```bash
conda run -n toby streamlit run app.py
```

### 2. CLI 命令列巡檢（適合 CI/CD 與自動化排程）
針對在 `configs/tdx.yaml` 中定義的關鍵路徑進行全方位檢測：

```bash
conda run -n toby python main.py audit --config configs/tdx.yaml
```

### 2. 對「任何網站」快速一鍵巡檢
不需撰寫任何設定檔，直接傳入目標網址：

```bash
# 檢查特定頁面
conda run -n toby python main.py audit --url https://example.com

# 檢查該站並自動爬取最多 15 個站內頁面
conda run -n toby python main.py audit --url https://example.com --crawl --max-pages 15
```

### 3. 進階選項與參數

| 參數 | 簡寫 | 說明 | 預設值 |
| :--- | :---: | :--- | :--- |
| `--config` | `-c` | 指定 YAML 設定檔路徑 | 無 |
| `--url` | `-u` | 直接指定測試網址 | 無 |
| `--crawl` | | 啟用同源超連結自動爬取探勘 | `False` |
| `--max-pages` | | 爬網模式下最多巡檢的頁面數 | `10` |
| `--output-dir` | `-o` | 報告與截圖存放目錄 | `reports` |
| `--headed` | | 以可視化視窗模式啟動瀏覽器（除錯用） | `False` (Headless) |

---

## 📁 專案架構說明

```text
playwright-playground/
├── configs/
│   ├── tdx.yaml               # TDX 運輸資料流通服務專屬配置 (依據 info.md)
│   └── default.yaml           # 通用網站檢測範本
├── src/
│   ├── models.py              # 資料模型 (AuditIssue, PageAuditResult, AuditReport)
│   ├── config.py              # YAML / URL 配置載入器
│   ├── crawler.py             # 同源自動連結探勘器
│   ├── runner.py              # Playwright 執行調度核心與截圖器
│   ├── probes/                # 啟發式探針群
│   │   ├── runtime.py         # JS 執行階段錯誤、主控台、CSP 違規監控
│   │   ├── network.py         # API 4xx/5xx、Localhost 洩漏、連線失敗
│   │   └── dom.py             # 白畫面判定、卡死轉圈、iframe 檢查
│   ├── reporter/              # 多格式報告生成器
│   │   ├── html.py            # 現代化互動式 HTML 儀表板
│   │   ├── markdown.py        # GitHub 格式 Markdown 摘要
│   │   └── json_rep.py        # 結構化 JSON 輸出
│   └── cli.py                 # Click + Rich 終端介面
├── reports/                   # 產出的報告與截圖
├── main.py                    # 快速啟動入口
├── requirements.txt           # 依賴清單
└── README.md
```
