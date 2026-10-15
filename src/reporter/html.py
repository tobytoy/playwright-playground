"""
HTML Reporter: generates a self-contained, modern, interactive HTML audit report.
"""

import json
from pathlib import Path
from ..models import AuditReport, IssueSeverity


class HTMLReporter:
    @staticmethod
    def export(report: AuditReport, output_path: str | Path):
        s = report.summary
        
        # Pre-process pages data for HTML injection
        pages_data = []
        for p in report.pages:
            pages_data.append({
                "url": p.url,
                "route_path": p.route_path,
                "title": p.page_title,
                "status": p.http_status,
                "load_time_ms": p.load_time_ms,
                "screenshot": p.screenshot_path,
                "is_passed": p.is_passed,
                "has_critical": p.has_critical,
                "has_warning": p.has_warning,
                "issues": [
                    {
                        "category": i.category.value,
                        "severity": i.severity.value,
                        "title": i.title,
                        "message": i.message,
                        "details": i.details,
                        "selector": i.element_selector,
                    }
                    for i in p.issues
                ],
                "network_failures": [
                    {
                        "method": r.method,
                        "url": r.url,
                        "status": r.status,
                        "type": r.resource_type,
                    }
                    for r in p.network_records if r.status >= 400
                ],
                "console_errors": [
                    c for c in p.console_logs if c.get("type") in ("error", "warning")
                ]
            })

        html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>網站健康檢查報告 - {report.site_name}</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text-main: #f8fafc;
      --text-sub: #94a3b8;
      --accent: #38bdf8;
      --critical: #f43f5e;
      --critical-bg: rgba(244, 63, 94, 0.12);
      --warning: #f59e0b;
      --warning-bg: rgba(245, 158, 11, 0.12);
      --success: #10b981;
      --success-bg: rgba(16, 185, 129, 0.12);
      --info: #64748b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text-main);
      line-height: 1.6;
      padding: 30px 20px;
    }}
    .container {{
      max-width: 1280px;
      margin: 0 auto;
    }}
    header {{
      margin-bottom: 30px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 15px;
    }}
    h1 {{ font-size: 26px; font-weight: 700; color: #fff; }}
    .subtitle {{ color: var(--text-sub); font-size: 14px; margin-top: 4px; }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
    }}
    .badge-critical {{ background: var(--critical-bg); color: var(--critical); border: 1px solid var(--critical); }}
    .badge-warning {{ background: var(--warning-bg); color: var(--warning); border: 1px solid var(--warning); }}
    .badge-success {{ background: var(--success-bg); color: var(--success); border: 1px solid var(--success); }}
    .badge-status {{ background: #334155; color: #e2e8f0; }}

    /* KPI Cards */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 30px;
    }}
    .kpi-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 18px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }}
    .kpi-title {{ font-size: 13px; color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.5px; }}
    .kpi-value {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
    .val-critical {{ color: var(--critical); }}
    .val-warning {{ color: var(--warning); }}
    .val-success {{ color: var(--success); }}
    .val-accent {{ color: var(--accent); }}

    /* Filters */
    .filter-bar {{
      display: flex;
      gap: 10px;
      margin-bottom: 20px;
    }}
    .filter-btn {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text-sub);
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
    }}
    .filter-btn.active, .filter-btn:hover {{
      background: var(--accent);
      color: #0f172a;
      border-color: var(--accent);
    }}

    /* Page Accordion Cards */
    .page-list {{ display: flex; flex-direction: column; gap: 16px; }}
    .page-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
      transition: border-color 0.2s;
    }}
    .page-card.has-critical {{ border-left: 5px solid var(--critical); }}
    .page-card.has-warning:not(.has-critical) {{ border-left: 5px solid var(--warning); }}
    .page-card.is-passed {{ border-left: 5px solid var(--success); }}

    .page-header {{
      padding: 16px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      user-select: none;
    }}
    .page-header:hover {{ background: rgba(255, 255, 255, 0.02); }}
    .page-title-group {{ display: flex; align-items: center; gap: 12px; }}
    .page-route {{ font-weight: 600; font-size: 16px; color: #fff; }}
    .page-name {{ font-size: 13px; color: var(--text-sub); }}
    .page-meta {{ display: flex; align-items: center; gap: 12px; }}

    .page-content {{
      padding: 20px;
      border-top: 1px solid var(--card-border);
      display: none;
      background: #162032;
    }}
    .page-card.open .page-content {{ display: block; }}

    .grid-split {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 20px;
    }}
    @media (max-width: 900px) {{
      .grid-split {{ grid-template-columns: 1fr; }}
    }}

    /* Issue Item */
    .issue-item {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 12px;
    }}
    .issue-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }}
    .issue-title {{ font-size: 14px; font-weight: 600; color: #fff; }}
    .issue-msg {{ font-size: 13px; color: #cbd5e1; margin-bottom: 8px; }}
    .issue-code {{
      background: #090d16;
      border: 1px solid #1e293b;
      padding: 8px 12px;
      border-radius: 6px;
      font-family: monospace;
      font-size: 12px;
      color: #38bdf8;
      overflow-x: auto;
      max-height: 180px;
    }}

    /* Screenshot */
    .screenshot-container {{
      border: 1px solid var(--card-border);
      border-radius: 8px;
      overflow: hidden;
      background: #000;
      text-align: center;
    }}
    .screenshot-container img {{
      max-width: 100%;
      height: auto;
      display: block;
      cursor: zoom-in;
    }}
    .screenshot-caption {{
      font-size: 11px;
      color: var(--text-sub);
      padding: 6px;
      background: #090d16;
    }}

    /* Table */
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }}
    th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--card-border); }}
    th {{ color: var(--text-sub); font-weight: 600; background: rgba(255, 255, 255, 0.02); }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>🔍 網站全方位健康巡檢報告</h1>
        <div class="subtitle">目標網站：<strong>{report.site_name}</strong> ({report.base_url}) | 檢測時間：{report.started_at[:19].replace('T', ' ')} UTC</div>
      </div>
      <div>
        <span class="badge { 'badge-critical' if s.total_critical > 0 else 'badge-success' }">
          { '檢測發現異常' if s.total_critical > 0 else '全部通過' }
        </span>
      </div>
    </header>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-title">總檢查頁面</div>
        <div class="kpi-value val-accent">{s.total_pages}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">正常通過</div>
        <div class="kpi-value val-success">{s.passed_pages}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">異常頁面</div>
        <div class="kpi-value val-critical">{s.failed_pages}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">致命缺陷 (Critical)</div>
        <div class="kpi-value val-critical">{s.total_critical}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">警告項目 (Warning)</div>
        <div class="kpi-value val-warning">{s.total_warning}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">總耗時</div>
        <div class="kpi-value">{s.duration_seconds}s</div>
      </div>
    </div>

    <div class="filter-bar">
      <button class="filter-btn active" onclick="filterPages('all')">全部頁面 ({s.total_pages})</button>
      <button class="filter-btn" onclick="filterPages('failed')">僅看異常 ({s.failed_pages})</button>
      <button class="filter-btn" onclick="filterPages('critical')">僅看致命問題</button>
      <button class="filter-btn" onclick="filterPages('passed')">僅看正常 ({s.passed_pages})</button>
    </div>

    <div class="page-list" id="pageList"></div>
  </div>

  <script>
    const pages = {json.dumps(pages_data, ensure_ascii=False)};

    function renderPages(filter = 'all') {{
      const container = document.getElementById('pageList');
      container.innerHTML = '';

      pages.forEach((p, idx) => {{
        if (filter === 'failed' && p.is_passed) return;
        if (filter === 'passed' && !p.is_passed) return;
        if (filter === 'critical' && !p.has_critical) return;

        const card = document.createElement('div');
        const statusClass = p.has_critical ? 'has-critical' : (p.has_warning ? 'has-warning' : 'is-passed');
        card.className = `page-card ${{statusClass}} ${{idx === 0 || !p.is_passed ? 'open' : ''}}`;

        let issuesHtml = '';
        if (p.issues.length === 0) {{
          issuesHtml = '<p style="color: var(--success); font-size: 13px;">✅ 該頁面無發現任何異常或報錯。</p>';
        }} else {{
          p.issues.forEach(i => {{
            const badgeClass = i.severity === 'CRITICAL' ? 'badge-critical' : 'badge-warning';
            let detailsPre = '';
            if (i.details && Object.keys(i.details).length > 0) {{
              detailsPre = `<pre class="issue-code">${{JSON.stringify(i.details, null, 2)}}</pre>`;
            }}
            issuesHtml += `
              <div class="issue-item">
                <div class="issue-header">
                  <span class="issue-title">${{i.title}}</span>
                  <span class="badge ${{badgeClass}}">${{i.severity}}</span>
                </div>
                <div class="issue-msg">${{i.message}}</div>
                ${{i.selector ? `<div style="font-size: 12px; color: var(--accent); margin-bottom: 6px;">選擇器: <code>${{i.selector}}</code></div>` : ''}}
                ${{detailsPre}}
              </div>
            `;
          }});
        }}

        let netFailHtml = '';
        if (p.network_failures && p.network_failures.length > 0) {{
          netFailHtml = `
            <div style="margin-top: 20px;">
              <h4 style="font-size: 13px; color: var(--text-sub); margin-bottom: 8px;">❌ 失敗網路請求 (HTTP 4xx/5xx)</h4>
              <table>
                <thead>
                  <tr><th>方法</th><th>狀態</th><th>類型</th><th>URL</th></tr>
                </thead>
                <tbody>
                  ${{p.network_failures.map(n => `
                    <tr>
                      <td><code>${{n.method}}</code></td>
                      <td><span class="badge badge-critical">${{n.status}}</span></td>
                      <td>${{n.type}}</td>
                      <td style="word-break: break-all;">${{n.url}}</td>
                    </tr>
                  `).join('')}}
                </tbody>
              </table>
            </div>
          `;
        }}

        let screenshotHtml = '';
        if (p.screenshot) {{
          screenshotHtml = `
            <div>
              <h4 style="font-size: 13px; color: var(--text-sub); margin-bottom: 8px;">📷 頁面渲染截圖存檔</h4>
              <div class="screenshot-container">
                <a href="${{p.screenshot}}" target="_blank">
                  <img src="${{p.screenshot}}" alt="Page screenshot" />
                </a>
                <div class="screenshot-caption">${{p.screenshot}} (點擊檢視原圖)</div>
              </div>
            </div>
          `;
        }}

        card.innerHTML = `
          <div class="page-header" onclick="this.parentElement.classList.toggle('open')">
            <div class="page-title-group">
              <span class="badge ${{p.has_critical ? 'badge-critical' : (p.has_warning ? 'badge-warning' : 'badge-success')}}">
                ${{p.has_critical ? 'CRITICAL' : (p.has_warning ? 'WARNING' : 'PASSED')}}
              </span>
              <span class="page-route">${{p.route_path}}</span>
              <span class="page-name">${{p.title || '(無標題)'}}</span>
            </div>
            <div class="page-meta">
              <span class="badge badge-status">HTTP ${{p.status || 'N/A'}}</span>
              <span style="font-size: 12px; color: var(--text-sub);">${{p.load_time_ms}}ms</span>
              <span style="font-size: 12px; color: ${{p.issues.length ? 'var(--critical)' : 'var(--success)'}}">
                ${{p.issues.length}} 個問題
              </span>
            </div>
          </div>
          <div class="page-content">
            <div class="grid-split">
              <div>
                <h4 style="font-size: 13px; color: var(--text-sub); margin-bottom: 12px;">🚨 檢測問題明細</h4>
                ${{issuesHtml}}
                ${{netFailHtml}}
              </div>
              ${{screenshotHtml}}
            </div>
          </div>
        `;
        container.appendChild(card);
      }});
    }}

    function filterPages(type) {{
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      event.target.classList.add('active');
      renderPages(type);
    }}

    renderPages('all');
  </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
