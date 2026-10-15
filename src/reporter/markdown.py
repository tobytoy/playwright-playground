"""
Markdown Reporter: produces GitHub-compatible executive markdown audit summaries.
"""

from pathlib import Path
from ..models import AuditReport, IssueSeverity


class MarkdownReporter:
    @staticmethod
    def export(report: AuditReport, output_path: str | Path):
        s = report.summary
        
        md_lines = [
            f"# 🌐 網站全方位健康檢查報告 (Site Health Audit Report)",
            f"",
            f"- **檢測目標**: [{report.site_name}]({report.base_url})",
            f"- **檢測時間**: `{report.started_at}`",
            f"- **總耗時**: `{s.duration_seconds} 秒`",
            f"",
            f"## 📊 總覽統計 (Overview)",
            f"",
            f"| 總檢查頁面 | 正常通過 (Passed) | 異常頁面 (Failed) | 致命問題 (Critical) | 警告項目 (Warning) |",
            f"| :---: | :---: | :---: | :---: | :---: |",
            f"| **{s.total_pages}** | {s.passed_pages} ✅ | **{s.failed_pages} ❌** | **<font color='#e05252'>{s.total_critical}</font>** 🚨 | {s.total_warning} ⚠️ |",
            f"",
            f"---",
            f"",
            f"## 🔍 異常頁面詳細檢視 (Detailed Findings)",
            f"",
        ]

        # Filter failed pages
        failed_pages = [p for p in report.pages if not p.is_passed or p.issues]
        if not failed_pages:
            md_lines.append("🎉 **所有檢測頁面皆順利通過，未發現重大前端或網路異常！**")
        else:
            for p in failed_pages:
                status_icon = "🚨 異常" if p.has_critical else ("⚠️ 警告" if p.has_warning else "ℹ️ 提示")
                md_lines.extend([
                    f"### {status_icon} `{p.route_path}`",
                    f"- **完整網址**: [{p.url}]({p.url})",
                    f"- **頁面標題**: {p.page_title or '(無標題)'}",
                    f"- **HTTP 狀態碼**: `{p.http_status or 'N/A'}`",
                    f"- **載入耗時**: `{p.load_time_ms} ms`",
                ])

                if p.screenshot_path:
                    md_lines.append(f"- **截圖存檔**: `{p.screenshot_path}`")

                md_lines.append("")
                md_lines.append("#### 發現問題項目：")
                
                for issue in p.issues:
                    badge = "**[CRITICAL]**" if issue.severity == IssueSeverity.CRITICAL else f"**[{issue.severity.value}]**"
                    md_lines.append(f"- {badge} **`{issue.category.value}`** - {issue.title}")
                    md_lines.append(f"  - **說明**: {issue.message}")
                    if issue.element_selector:
                        md_lines.append(f"  - **元素選擇器**: `{issue.element_selector}`")
                    if issue.details:
                        detail_preview = str(issue.details)
                        if len(detail_preview) > 200:
                            detail_preview = detail_preview[:200] + "..."
                        md_lines.append(f"  - **詳細資料**: `{detail_preview}`")

                md_lines.append("")
                md_lines.append("---")
                md_lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
