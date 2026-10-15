"""
Network Probe: monitors HTTP responses, API failures (4xx/5xx), failed requests, and dev/localhost URL leaks.
"""

from typing import List, Pattern, Set
import uuid
import fnmatch
from datetime import datetime, timezone
from playwright.async_api import Page, Response, Request
from ..models import AuditIssue, IssueCategory, IssueSeverity, NetworkRecord


class NetworkProbe:
    def __init__(
        self,
        detect_api_failures: bool = True,
        detect_dev_leaks: bool = True,
        dev_leak_patterns: List[str] = None,
    ):
        self.detect_api_failures = detect_api_failures
        self.detect_dev_leaks = detect_dev_leaks
        self.dev_leak_patterns = dev_leak_patterns or ["*localhost*", "*127.0.0.1*", "*::1*", "*:44331*"]
        self.issues: List[AuditIssue] = []
        self.network_records: List[NetworkRecord] = []
        self._seen_urls: Set[str] = set()

    def attach(self, page: Page):
        """Attaches request and response event listeners."""
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)

    def _matches_leak(self, url: str) -> bool:
        return any(fnmatch.fnmatch(url.lower(), pat.lower()) for pat in self.dev_leak_patterns)

    def _on_request_failed(self, request: Request):
        url = request.url
        failure = request.failure
        error_text = failure if isinstance(failure, str) else (failure.get("errorText", "Unknown error") if failure else "Unknown error")
        
        # Check dev leak in failed request
        if self.detect_dev_leaks and self._matches_leak(url):
            self.issues.append(
                AuditIssue(
                    id=f"leak-{uuid.uuid4().hex[:8]}",
                    category=IssueCategory.DEV_URL_LEAK,
                    severity=IssueSeverity.CRITICAL,
                    title="生產環境引用開發機網址 (Localhost / Dev Leak)",
                    message=f"請求發送至開發機/本地網址: {url}，導致載入失敗 ({error_text})",
                    details={"url": url, "error": error_text, "resource_type": request.resource_type},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )
            return

        # Regular resource failure
        if "favicon.ico" not in url:
            self.issues.append(
                AuditIssue(
                    id=f"netfail-{uuid.uuid4().hex[:8]}",
                    category=IssueCategory.RESOURCE_FAILURE,
                    severity=IssueSeverity.WARNING,
                    title=f"網路請求失敗 ({request.resource_type})",
                    message=f"資源請求失敗: {url}，原因: {error_text}",
                    details={"url": url, "error": error_text, "resource_type": request.resource_type},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )

    async def _on_response(self, response: Response):
        url = response.url
        status = response.status
        resource_type = response.request.resource_type

        record = NetworkRecord(
            url=url,
            method=response.request.method,
            status=status,
            resource_type=resource_type,
        )
        self.network_records.append(record)

        # Check dev URL leak
        if self.detect_dev_leaks and self._matches_leak(url):
            self.issues.append(
                AuditIssue(
                    id=f"leak-{uuid.uuid4().hex[:8]}",
                    category=IssueCategory.DEV_URL_LEAK,
                    severity=IssueSeverity.CRITICAL,
                    title="生產環境引用開發機網址 (Localhost / Dev Leak)",
                    message=f"伺服器載入或引用了本地開發環境位址: {url}",
                    details={"url": url, "status": status, "resource_type": resource_type},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )

        if not self.detect_api_failures or status < 400:
            return

        # Avoid duplicates for identical failed url
        if url in self._seen_urls:
            return
        self._seen_urls.add(url)

        is_xhr_or_fetch = resource_type in ("fetch", "xhr")
        is_5xx = status >= 500

        if is_xhr_or_fetch:
            category = IssueCategory.API_FAILURE
            severity = IssueSeverity.CRITICAL if is_5xx else IssueSeverity.WARNING
            title = f"後端 API 異常回傳 HTTP {status}"
        elif resource_type in ("script", "stylesheet", "document"):
            category = IssueCategory.RESOURCE_FAILURE
            severity = IssueSeverity.CRITICAL if is_5xx else IssueSeverity.WARNING
            title = f"核心資源載入失敗 (HTTP {status})"
        else:
            category = IssueCategory.RESOURCE_FAILURE
            severity = IssueSeverity.WARNING
            title = f"靜態資源回傳 HTTP {status}"

        # Try to capture response preview if possible
        resp_snippet = ""
        try:
            body = await response.text()
            resp_snippet = body[:200]
        except Exception:
            resp_snippet = "(無法讀取 response body)"

        self.issues.append(
            AuditIssue(
                id=f"http-{uuid.uuid4().hex[:8]}",
                category=category,
                severity=severity,
                title=title,
                message=f"[{response.request.method}] {url} 回傳 HTTP {status}",
                details={
                    "url": url,
                    "method": response.request.method,
                    "status": status,
                    "status_text": response.status_text,
                    "resource_type": resource_type,
                    "snippet": resp_snippet,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
