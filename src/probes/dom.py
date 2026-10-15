"""
DOM & UI Probe: blank page heuristics, stuck spinner detection, iframe verification, and DOM leak inspection.
"""

from typing import List
import uuid
import asyncio
from datetime import datetime, timezone
from playwright.async_api import Page
from ..models import AuditIssue, IssueCategory, IssueSeverity
from ..config import HeuristicRulesConfig, RouteConfig


class DomProbe:
    def __init__(self, rules: HeuristicRulesConfig):
        self.rules = rules
        self.issues: List[AuditIssue] = []

    async def inspect(self, page: Page, route_config: RouteConfig):
        """Runs heuristic audits on the current page DOM."""
        await self._check_dev_leaks_in_dom(page, route_config)
        await self._check_blank_page(page)
        await self._check_stuck_spinner(page)
        if route_config.check_iframes and self.rules.detect_iframe_issues:
            await self._check_iframes(page)
        await self._check_custom_selectors(page, route_config)

    async def _check_dev_leaks_in_dom(self, page: Page, route_config: RouteConfig):
        """Scans DOM attributes (src, href, style) for localhost or development machine addresses."""
        if not self.rules.detect_dev_leaks:
            return

        patterns = list(set(self.rules.dev_leak_patterns + route_config.forbidden_patterns))
        
        leak_check_script = """
        (patterns) => {
            const found = [];
            const checkVal = (tag, attr, val) => {
                if (!val) return;
                for (const pat of patterns) {
                    const cleanPat = pat.replace(/\\*/g, '');
                    if (val.toLowerCase().includes(cleanPat.toLowerCase())) {
                        found.push({ tag, attr, val, pattern: pat });
                    }
                }
            };

            // Check elements with src or href
            document.querySelectorAll('[src]').forEach(el => {
                checkVal(el.tagName.toLowerCase(), 'src', el.getAttribute('src'));
            });
            document.querySelectorAll('[href]').forEach(el => {
                checkVal(el.tagName.toLowerCase(), 'href', el.getAttribute('href'));
            });
            // Check images explicitly
            document.querySelectorAll('img').forEach(el => {
                checkVal('img', 'src', el.src);
            });
            // Check iframes
            document.querySelectorAll('iframe').forEach(el => {
                checkVal('iframe', 'src', el.src);
            });
            return found;
        }
        """
        try:
            leaks = await page.evaluate(leak_check_script, patterns)
            for leak in leaks:
                self.issues.append(
                    AuditIssue(
                        id=f"domleak-{uuid.uuid4().hex[:8]}",
                        category=IssueCategory.DEV_URL_LEAK,
                        severity=IssueSeverity.CRITICAL,
                        title=f"DOM 標籤引用開發機網址 (<{leak['tag']} {leak['attr']}>)",
                        message=f"標籤 <{leak['tag']}> 的 {leak['attr']} 屬性包含本地開發位址: {leak['val']}",
                        details=leak,
                        element_selector=f"{leak['tag']}[{leak['attr']}*='{leak['pattern'].replace('*', '')}']",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
        except Exception:
            pass

    async def _check_blank_page(self, page: Page):
        """Evaluates whether the page rendered as completely or virtually blank."""
        if not self.rules.detect_blank_page:
            return

        metrics_script = """
        () => {
            const body = document.body;
            if (!body) return { nodeCount: 0, textLength: 0, title: document.title, isBlank: true };
            const nodeCount = document.querySelectorAll('*').length;
            const text = (body.innerText || '').trim();
            const interactiveCount = document.querySelectorAll('button, a, input, select, textarea').length;
            return {
                nodeCount,
                textLength: text.length,
                textSample: text.substring(0, 100),
                interactiveCount,
                title: document.title
            };
        }
        """
        try:
            m = await page.evaluate(metrics_script)
            # Blank threshold evaluation
            is_empty_text = m["textLength"] < self.rules.blank_page_min_text_length
            is_empty_nodes = m["nodeCount"] < self.rules.blank_page_min_dom_nodes
            
            if is_empty_text and is_empty_nodes:
                self.issues.append(
                    AuditIssue(
                        id=f"blank-{uuid.uuid4().hex[:8]}",
                        category=IssueCategory.BLANK_PAGE,
                        severity=IssueSeverity.CRITICAL,
                        title="頁面呈現空白 (Blank Page Detected)",
                        message=f"頁面載入後 DOM 節點過少 ({m['nodeCount']}) 且可視文字極短 ({m['textLength']} 字)，未成功渲染內容",
                        details=m,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
        except Exception:
            pass

    async def _check_stuck_spinner(self, page: Page):
        """Checks if a loading spinner remains visible after the page has finished loading."""
        if not self.rules.detect_stuck_spinner:
            return

        selectors_json = self.rules.spinner_selectors
        spinner_script = """
        (selectors) => {
            for (const sel of selectors) {
                try {
                    const elements = document.querySelectorAll(sel);
                    for (const el of elements) {
                        const style = window.getComputedStyle(el);
                        if (style && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                return {
                                    selector: sel,
                                    tagName: el.tagName.toLowerCase(),
                                    className: el.className,
                                    id: el.id
                                };
                            }
                        }
                    }
                } catch(e) {}
            }
            return null;
        }
        """
        try:
            spinner = await page.evaluate(spinner_script, selectors_json)
            if spinner:
                # Wait briefly to confirm it's stuck, not just naturally finishing
                await asyncio.sleep(self.rules.spinner_timeout_seconds)
                spinner_after = await page.evaluate(spinner_script, [spinner["selector"]])
                if spinner_after:
                    self.issues.append(
                        AuditIssue(
                            id=f"spinner-{uuid.uuid4().hex[:8]}",
                            category=IssueCategory.STUCK_SPINNER,
                            severity=IssueSeverity.CRITICAL,
                            title="UI 陷入無窮載入/轉圈 (Stuck Loading Spinner)",
                            message=f"載入指示器在超過 {self.rules.spinner_timeout_seconds} 秒後仍未消除，使用者介面處於卡死狀態",
                            details=spinner_after,
                            element_selector=spinner["selector"],
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )
        except Exception:
            pass

    async def _check_iframes(self, page: Page):
        """Inspects iframes on the page for broken sources or 404 embeds."""
        iframe_script = """
        () => {
            const iframes = Array.from(document.querySelectorAll('iframe'));
            return iframes.map(f => ({
                id: f.id,
                name: f.name,
                src: f.src || f.getAttribute('src') || '',
                title: f.title || '',
                className: f.className || ''
            }));
        }
        """
        try:
            frames = await page.evaluate(iframe_script)
            for f in frames:
                src = f.get("src", "").strip()
                if not src or src == "about:blank":
                    continue
                
                # Check if this frame src has returned a 404 in network requests or failed
                # Note: Frame network response is also captured by NetworkProbe.
                # Here we also check frame content if accessible
                for frame in page.frames:
                    if frame.url == src:
                        try:
                            title = await frame.title()
                            if "404" in title or "Not Found" in title:
                                self.issues.append(
                                    AuditIssue(
                                        id=f"iframe-{uuid.uuid4().hex[:8]}",
                                        category=IssueCategory.IFRAME_BROKEN,
                                        severity=IssueSeverity.CRITICAL,
                                        title=f"嵌入式 iframe 回傳 404/錯誤: {src}",
                                        message=f"頁面中嵌入的 iframe 標題包含 404/Not Found: {title}",
                                        details={"src": src, "title": title, "frame_info": f},
                                        timestamp=datetime.now(timezone.utc).isoformat(),
                                    )
                                )
                        except Exception:
                            pass
        except Exception:
            pass

    async def _check_custom_selectors(self, page: Page, route_config: RouteConfig):
        """Checks user-configured required and forbidden selectors."""
        for sel in route_config.required_selectors:
            try:
                count = await page.locator(sel).count()
                if count == 0:
                    self.issues.append(
                        AuditIssue(
                            id=f"selreq-{uuid.uuid4().hex[:8]}",
                            category=IssueCategory.BLANK_PAGE,
                            severity=IssueSeverity.CRITICAL,
                            title=f"缺少必要 DOM 元素: {sel}",
                            message=f"頁面未渲染指定的關鍵元素選擇器: {sel}",
                            details={"selector": sel},
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )
            except Exception:
                pass

        for sel in route_config.forbidden_selectors:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    self.issues.append(
                        AuditIssue(
                            id=f"selforbid-{uuid.uuid4().hex[:8]}",
                            category=IssueCategory.RUNTIME_ERROR,
                            severity=IssueSeverity.WARNING,
                            title=f"出現禁止存在的 DOM 元素: {sel}",
                            message=f"頁面上偵測到不應存在的元素 (例如報錯框或 fallback 提示): {sel}",
                            details={"selector": sel, "count": count},
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )
            except Exception:
                pass
