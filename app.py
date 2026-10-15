"""
Streamlit Web UI for Universal Website Health & Quality Inspector.
"""

import os
import asyncio
from pathlib import Path
from typing import List, Optional
import streamlit as st
import streamlit.components.v1 as components
import yaml

from src.config import SiteConfig, RouteConfig
from src.runner import AuditRunner
from src.models import AuditReport, IssueSeverity
from src.reporter.html import HTMLReporter
from src.reporter.json_rep import JSONReporter
from src.reporter.markdown import MarkdownReporter

# Page configuration
st.set_page_config(
    page_title="網站全方位健康檢查工具 | Playwright Site Auditor",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #1e293b;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #334155;
        text-align: center;
    }
    .badge-critical {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 12px;
    }
    .badge-warning {
        background-color: #fef3c7;
        color: #92400e;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 12px;
    }
    .badge-pass {
        background-color: #d1fae5;
        color: #065f46;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def run_audit_sync(config: SiteConfig, output_dir: str = "reports") -> AuditReport:
    """Runs Playwright async runner in a freshly isolated event loop."""
    runner = AuditRunner(config=config, output_dir=output_dir)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        report = loop.run_until_complete(runner.run())
        return report
    finally:
        loop.close()


def load_cached_report(output_dir: str = "reports") -> Optional[AuditReport]:
    json_path = Path(output_dir) / "report.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = f.read()
            return AuditReport.model_validate_json(data)
        except Exception:
            return None
    return None


# ====================
# Sidebar Configurations
# ====================
st.sidebar.title("🌐 網站巡檢控制台")
st.sidebar.markdown("透過 Playwright 全面檢測前端崩潰、後端 500、轉圈假死與開發機位址洩漏。")

mode = st.sidebar.radio("巡檢模式選擇", ["📁 既有設定檔巡檢 (YAML Config)", "🚀 即時自訂網址巡檢 (Direct URL)"])

config_to_run: Optional[SiteConfig] = None

if mode == "📁 既有設定檔巡檢 (YAML Config)":
    configs_dir = Path("configs")
    yaml_files = list(configs_dir.glob("*.yaml")) + list(configs_dir.glob("*.yml"))
    yaml_names = [f.name for f in yaml_files]

    # Default to tdx.yaml if available
    default_idx = yaml_names.index("tdx.yaml") if "tdx.yaml" in yaml_names else 0
    selected_yaml = st.sidebar.selectbox("選擇設定檔", yaml_names, index=default_idx)

    if selected_yaml:
        yaml_path = configs_dir / selected_yaml
        config_to_run = SiteConfig.from_yaml(yaml_path)

        st.sidebar.info(f"目標網站：**{config_to_run.name}**\n\n網址：`{config_to_run.base_url}`\n\n預定巡檢路由：`{len(config_to_run.routes)}` 頁")

        with st.sidebar.expander("檢視/修改設定檔內容"):
            with open(yaml_path, "r", encoding="utf-8") as f:
                yaml_text = f.read()
            edited_yaml = st.text_area("YAML 內容", yaml_text, height=250)
            if edited_yaml != yaml_text:
                try:
                    parsed = yaml.safe_load(edited_yaml)
                    config_to_run = SiteConfig(**parsed)
                    st.success("YAML 設定已即時更新！")
                except Exception as e:
                    st.error(f"YAML 語法錯誤: {e}")

else:
    # Direct URL mode
    target_url = st.sidebar.text_input("目標網站首頁網址 (Base URL)", "https://tdx.transportdata.tw")
    site_name = st.sidebar.text_input("專案/網站名稱", "即時檢測目標")

    routes_input = st.sidebar.text_area(
        "欲檢查之指定路徑 (一行一個路徑)",
        "/api-service/inquire\n/api-service/ticpApplyTable\n/api-service/mainData\n/about/tdx\n/api-service/monitor",
        height=120,
    )

    crawl_enabled = st.sidebar.checkbox("啟用自動站內連結爬取 (Crawler)", value=False)
    max_crawl_pages = 10
    if crawl_enabled:
        max_crawl_pages = st.sidebar.slider("最多爬取頁面數", 3, 30, 10)

    routes_list = [RouteConfig(path=p.strip()) for p in routes_input.strip().splitlines() if p.strip()]
    if not routes_list:
        routes_list = [RouteConfig(path="/")]

    config_to_run = SiteConfig(
        name=site_name,
        base_url=target_url.rstrip("/"),
        routes=routes_list,
        crawl_enabled=crawl_enabled,
        crawl_max_pages=max_crawl_pages,
    )

# Common Advanced Options
with st.sidebar.expander("⚙️ 進階檢測規則與選項"):
    config_to_run.headless = st.checkbox("無頭模式 (Headless)", value=config_to_run.headless)
    config_to_run.rules.detect_blank_page = st.checkbox("白畫面檢測 (Blank Page)", value=config_to_run.rules.detect_blank_page)
    config_to_run.rules.detect_stuck_spinner = st.checkbox("無窮轉圈死鎖檢測 (Stuck Spinner)", value=config_to_run.rules.detect_stuck_spinner)
    config_to_run.rules.detect_dev_leaks = st.checkbox("開發機 Localhost 洩漏檢測", value=config_to_run.rules.detect_dev_leaks)
    config_to_run.rules.detect_api_failures = st.checkbox("後端 API 5xx/4xx 崩潰監控", value=config_to_run.rules.detect_api_failures)
    config_to_run.rules.detect_iframe_issues = st.checkbox("嵌入式 iframe 404 檢查", value=config_to_run.rules.detect_iframe_issues)
    config_to_run.rules.capture_screenshots = st.checkbox("儲存頁面渲染截圖", value=config_to_run.rules.capture_screenshots)

output_dir = "reports"
Path(output_dir).mkdir(parents=True, exist_ok=True)

start_button = st.sidebar.button("🚀 開始執行全方位巡檢", type="primary", use_container_width=True)

# Initialize Session State
if "report" not in st.session_state:
    st.session_state["report"] = load_cached_report(output_dir)

if start_button and config_to_run:
    with st.spinner(f"Playwright 正在巡檢 [{config_to_run.name}] 各頁面，請稍候..."):
        report = run_audit_sync(config_to_run, output_dir=output_dir)
        # Export all formats
        HTMLReporter.export(report, Path(output_dir) / "report.html")
        JSONReporter.export(report, Path(output_dir) / "report.json")
        MarkdownReporter.export(report, Path(output_dir) / "report.md")
        st.session_state["report"] = report
    st.success("🎉 巡檢執行完成！已即時更新檢查報告。")


# ====================
# Main Dashboard View
# ====================
st.title("🌐 網站全方位健康檢查儀表板")

report: Optional[AuditReport] = st.session_state.get("report")

if not report:
    st.info("👈 請在左側側邊欄設定目標網站或選擇設定檔，點擊「開始執行全方位巡檢」！")
else:
    s = report.summary

    # Header info
    st.markdown(
        f"**目標網站**：`{report.site_name}` ({report.base_url}) &nbsp;|&nbsp; "
        f"**檢測時間**：`{report.started_at[:19].replace('T', ' ')} UTC` &nbsp;|&nbsp; "
        f"**總耗時**：`{s.duration_seconds} 秒`"
    )

    # Top KPI Metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("總檢查頁面", s.total_pages)
    c2.metric("正常通過 (Passed)", s.passed_pages)
    c3.metric("異常頁面 (Failed)", s.failed_pages, delta=None if s.failed_pages == 0 else f"-{s.failed_pages}", delta_color="inverse")
    c4.metric("致命問題 (Critical)", s.total_critical, delta=None if s.total_critical == 0 else f"{s.total_critical} 項", delta_color="inverse")
    c5.metric("警告項目 (Warning)", s.total_warning)

    # Action buttons: Download & Links
    st.write("")
    btn_col1, btn_col2, btn_col3, _ = st.columns([1.5, 1.5, 1.5, 3])

    html_file = Path(output_dir) / "report.html"
    md_file = Path(output_dir) / "report.md"
    json_file = Path(output_dir) / "report.json"

    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            btn_col1.download_button("📥 下載 HTML 報告", f.read(), file_name="report.html", mime="text/html", use_container_width=True)

    if md_file.exists():
        with open(md_file, "r", encoding="utf-8") as f:
            btn_col2.download_button("📥 下載 Markdown 報告", f.read(), file_name="report.md", mime="text/markdown", use_container_width=True)

    if json_file.exists():
        with open(json_file, "r", encoding="utf-8") as f:
            btn_col3.download_button("📥 下載 JSON 數據", f.read(), file_name="report.json", mime="application/json", use_container_width=True)

    st.divider()

    # Tab views
    tab_list, tab_html, tab_md = st.tabs(["📋 頁面檢驗明細與截圖", "🖥️ 完整 HTML 報告檢視", "📝 Markdown 提報檢視"])

    # --- TAB 1: Detailed List ---
    with tab_list:
        filter_col, _ = st.columns([2, 4])
        view_filter = filter_col.selectbox(
            "頁面篩選",
            [f"全部頁面 ({s.total_pages})", f"僅看異常頁面 ({s.failed_pages})", "僅看含 Critical 頁面", f"僅看正常頁面 ({s.passed_pages})"],
        )

        for p in report.pages:
            # Filter condition
            if "僅看異常" in view_filter and p.is_passed:
                continue
            if "僅看正常" in view_filter and not p.is_passed:
                continue
            if "僅看含 Critical" in view_filter and not p.has_critical:
                continue

            status_badge = "🚨 FAIL" if p.has_critical else ("⚠️ WARN" if p.has_warning else "✅ PASS")
            expander_title = f"{status_badge} | {p.route_path} — {p.page_title or '(無標題)'} (HTTP {p.http_status or 'N/A'}, {p.load_time_ms}ms, {len(p.issues)} 個問題)"

            with st.expander(expander_title, expanded=not p.is_passed):
                col_left, col_right = st.columns([1.3, 1.0])

                with col_left:
                    st.markdown(f"**完整網址**：[{p.url}]({p.url})")

                    if not p.issues:
                        st.success("✅ 此頁面未檢測出任何前端例外、後端 500、或轉圈假死問題。")
                    else:
                        st.markdown("#### 🚨 發現問題清單")
                        for i, issue in enumerate(p.issues, 1):
                            sev_badge = "badge-critical" if issue.severity == IssueSeverity.CRITICAL else "badge-warning"
                            st.markdown(
                                f"""
                                <div style="border-left: 4px solid {'#ef4444' if issue.severity == IssueSeverity.CRITICAL else '#f59e0b'}; padding-left: 10px; margin-bottom: 12px;">
                                    <strong>{i}. {issue.title}</strong> &nbsp;
                                    <span class="{sev_badge}">{issue.severity.value}</span> &nbsp;
                                    <code>{issue.category.value}</code><br>
                                    <span style="font-size: 13px; color: #475569;">{issue.message}</span>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            if issue.element_selector:
                                st.caption(f"🎯 元素選擇器：`{issue.element_selector}`")
                            if issue.details:
                                with st.expander(f"查看詳細資料 / Stack Trace (#{i})", expanded=False):
                                    st.json(issue.details)

                    # Network failures list
                    failed_net = [r for r in p.network_records if r.status >= 400]
                    if failed_net:
                        st.markdown("#### ❌ 異常網路請求 (HTTP 4xx/5xx)")
                        net_table = [
                            {"方法": r.method, "狀態碼": r.status, "類型": r.resource_type, "網址": r.url}
                            for r in failed_net
                        ]
                        st.dataframe(net_table, use_container_width=True)

                    # Console logs
                    error_logs = [c for c in p.console_logs if c.get("type") in ("error", "warning")]
                    if error_logs:
                        with st.expander(f"主控台報錯日誌 ({len(error_logs)} 則)", expanded=False):
                            for log in error_logs:
                                st.text(f"[{log.get('type')}] {log.get('text')}\n  at {log.get('location')}")

                with col_right:
                    st.markdown("#### 📷 頁面渲染截圖")
                    if p.screenshot_path and os.path.exists(p.screenshot_path):
                        st.image(p.screenshot_path, caption=f"截圖存檔：{os.path.basename(p.screenshot_path)}", use_container_width=True)
                    else:
                        st.caption("（未擷取或無截圖存檔）")

    # --- TAB 2: Embedded HTML ---
    with tab_html:
        if html_file.exists():
            with open(html_file, "r", encoding="utf-8") as f:
                raw_html = f.read()
            components.html(raw_html, height=850, scrolling=True)
        else:
            st.info("尚未產出 HTML 報告。")

    # --- TAB 3: Markdown View ---
    with tab_md:
        if md_file.exists():
            with open(md_file, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.info("尚未產出 Markdown 報告。")
