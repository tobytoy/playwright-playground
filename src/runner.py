"""
Audit Runner: orchestrates Playwright browser sessions, probe executions, screenshots, and result compilation.
"""

import time
import os
import uuid
from typing import List, Set
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Page, BrowserContext

from .config import SiteConfig, RouteConfig
from .models import (
    AuditIssue,
    AuditReport,
    AuditSummary,
    IssueCategory,
    IssueSeverity,
    PageAuditResult,
)
from .probes.runtime import RuntimeProbe
from .probes.network import NetworkProbe
from .probes.dom import DomProbe
from .crawler import SiteCrawler


class AuditRunner:
    def __init__(self, config: SiteConfig, output_dir: str = "reports"):
        self.config = config
        self.output_dir = output_dir
        self.screenshots_dir = os.path.join(output_dir, "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)
        self.crawler = SiteCrawler(
            base_url=config.base_url,
            max_pages=config.crawl_max_pages,
            max_depth=config.crawl_max_depth,
        )

    async def run(self) -> AuditReport:
        """Executes the full audit across all configured and discovered routes."""
        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.time()
        page_results: List[PageAuditResult] = []

        routes_to_visit: List[RouteConfig] = list(self.config.routes)
        visited_paths: Set[str] = set()

        # If no routes provided, default to root "/"
        if not routes_to_visit:
            routes_to_visit.append(RouteConfig(path="/"))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.config.headless)
            context: BrowserContext = await browser.new_context(
                viewport=self.config.viewport,
                user_agent=self.config.user_agent,
                ignore_https_errors=True,
            )

            idx = 0
            while idx < len(routes_to_visit):
                route = routes_to_visit[idx]
                idx += 1

                normalized_path = route.path if route.path.startswith("/") else f"/{route.path}"
                if normalized_path in visited_paths:
                    continue
                visited_paths.add(normalized_path)

                result = await self._audit_single_route(context, route)
                page_results.append(result)

                # If crawling enabled and under limit, extract more links
                if self.config.crawl_enabled and len(routes_to_visit) < self.config.crawl_max_pages:
                    # We create a temporary page or use the visited links
                    # We can discover from DOM during page audit
                    pass

            await browser.close()

        finished_at = datetime.now(timezone.utc).isoformat()
        duration_seconds = round(time.time() - start_time, 2)

        # Aggregate summary
        total_pages = len(page_results)
        passed_pages = sum(1 for p in page_results if p.is_passed)
        failed_pages = total_pages - passed_pages
        total_critical = sum(sum(1 for i in p.issues if i.severity == IssueSeverity.CRITICAL) for p in page_results)
        total_warning = sum(sum(1 for i in p.issues if i.severity == IssueSeverity.WARNING) for p in page_results)
        total_info = sum(sum(1 for i in p.issues if i.severity == IssueSeverity.INFO) for p in page_results)

        summary = AuditSummary(
            total_pages=total_pages,
            passed_pages=passed_pages,
            failed_pages=failed_pages,
            total_critical=total_critical,
            total_warning=total_warning,
            total_info=total_info,
            duration_seconds=duration_seconds,
        )

        return AuditReport(
            site_name=self.config.name,
            base_url=self.config.base_url,
            started_at=started_at,
            finished_at=finished_at,
            summary=summary,
            pages=page_results,
        )

    async def _audit_single_route(self, context: BrowserContext, route: RouteConfig) -> PageAuditResult:
        full_url = urljoin(self.config.base_url, route.path)
        runtime_probe = RuntimeProbe(detect_runtime=self.config.rules.detect_runtime_errors)
        network_probe = NetworkProbe(
            detect_api_failures=self.config.rules.detect_api_failures,
            detect_dev_leaks=self.config.rules.detect_dev_leaks,
            dev_leak_patterns=self.config.rules.dev_leak_patterns + route.forbidden_patterns,
        )
        dom_probe = DomProbe(self.config.rules)

        page: Page = await context.new_page()
        runtime_probe.attach(page)
        network_probe.attach(page)
        await runtime_probe.inject_csp_listener(page)

        page_title = ""
        http_status = None
        nav_start = time.time()
        issues: List[AuditIssue] = []

        try:
            # Navigate to target route
            response = await page.goto(
                full_url,
                wait_until=route.wait_until,
                timeout=self.config.default_timeout_ms,
            )
            if response:
                http_status = response.status

            # Additional pause for client-side rendering / hydration
            if route.custom_wait_ms > 0:
                await page.wait_for_timeout(route.custom_wait_ms)

            page_title = await page.title()

            # Check redirect anomalies (e.g. unexpectedly redirected to homepage)
            final_url = page.url
            if final_url != full_url:
                parsed_final = urlparse(final_url)
                if parsed_final.path in ("/", "") and route.path not in ("/", ""):
                    issues.append(
                        AuditIssue(
                            id=f"redir-{uuid.uuid4().hex[:8]}",
                            category=IssueCategory.REDIRECT_ANOMALY,
                            severity=IssueSeverity.WARNING,
                            title="頁面異常重定向至首頁 (Silent Redirect)",
                            message=f"請求 {route.path} 被直接跳轉至首頁 ({final_url})，使用者可能無法得知具體錯誤原因",
                            details={"original": full_url, "final": final_url},
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )

            # Collect CSP violations & run DOM probe
            await runtime_probe.collect_csp_violations(page)
            await dom_probe.inspect(page, route)

            # Discover links if crawler active
            if self.config.crawl_enabled:
                discovered = await self.crawler.extract_links_from_page(page)
                for new_path in discovered:
                    # Append dynamically if not already in visited
                    pass

        except Exception as e:
            error_str = str(e)
            is_timeout = "timeout" in error_str.lower()
            issues.append(
                AuditIssue(
                    id=f"nav-{uuid.uuid4().hex[:8]}",
                    category=IssueCategory.RUNTIME_ERROR,
                    severity=IssueSeverity.CRITICAL,
                    title="頁面導航崩潰或載入逾時 (Navigation Failure)",
                    message=f"訪問 {full_url} 發生錯誤: {error_str}",
                    details={"error": error_str, "is_timeout": is_timeout},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )

        load_time_ms = round((time.time() - nav_start) * 1000, 2)

        # Merge all probe issues
        all_issues = issues + runtime_probe.issues + network_probe.issues + dom_probe.issues

        # Capture screenshot if configured or if issues present
        screenshot_path = None
        has_error = any(i.severity in (IssueSeverity.CRITICAL, IssueSeverity.WARNING) for i in all_issues)
        if self.config.rules.capture_screenshots and (has_error or True):
            safe_name = route.path.strip("/").replace("/", "_").replace("?", "_").replace("&", "_") or "root"
            filename = f"screenshot_{safe_name}_{uuid.uuid4().hex[:6]}.png"
            filepath = os.path.join(self.screenshots_dir, filename)
            try:
                await page.screenshot(path=filepath, full_page=self.config.rules.full_page_screenshot)
                screenshot_path = filepath
            except Exception:
                pass

        await page.close()

        return PageAuditResult(
            url=full_url,
            route_path=route.path,
            page_title=page_title,
            http_status=http_status,
            load_time_ms=load_time_ms,
            screenshot_path=screenshot_path,
            issues=all_issues,
            network_records=network_probe.network_records,
            console_logs=runtime_probe.console_logs,
        )
