"""
Runtime & Console Probe: captures uncaught JS errors, console errors/warnings, and CSP violations.
"""

from typing import Dict, List
import uuid
from datetime import datetime, timezone
from playwright.async_api import Page, ConsoleMessage, Error as PlaywrightError
from ..models import AuditIssue, IssueCategory, IssueSeverity


class RuntimeProbe:
    def __init__(self, detect_runtime: bool = True):
        self.detect_runtime = detect_runtime
        self.issues: List[AuditIssue] = []
        self.console_logs: List[Dict[str, str]] = []

    def attach(self, page: Page):
        """Attaches event listeners to the Playwright page."""
        page.on("pageerror", self._on_page_error)
        page.on("console", self._on_console)

    async def inject_csp_listener(self, page: Page):
        """Injects securitypolicyviolation listener into page before navigation."""
        await page.add_init_script("""
            window.__csp_violations = [];
            document.addEventListener('securitypolicyviolation', (e) => {
                window.__csp_violations.push({
                    blockedURI: e.blockedURI,
                    violatedDirective: e.violatedDirective,
                    originalPolicy: e.originalPolicy,
                    disposition: e.disposition
                });
            });
        """)

    async def collect_csp_violations(self, page: Page):
        """Retrieves accumulated CSP violations from client side."""
        try:
            violations = await page.evaluate("() => window.__csp_violations || []")
            for v in violations:
                self.issues.append(
                    AuditIssue(
                        id=f"csp-{uuid.uuid4().hex[:8]}",
                        category=IssueCategory.CSP_VIOLATION,
                        severity=IssueSeverity.WARNING,
                        title=f"CSP 違規: {v.get('violatedDirective', 'Directive')}",
                        message=f"資源受到 Content Security Policy 阻擋: {v.get('blockedURI', '')}",
                        details=v,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
        except Exception:
            pass

    def _on_page_error(self, error: PlaywrightError):
        if not self.detect_runtime:
            return
        
        error_str = str(error)
        self.issues.append(
            AuditIssue(
                id=f"runtime-{uuid.uuid4().hex[:8]}",
                category=IssueCategory.RUNTIME_ERROR,
                severity=IssueSeverity.CRITICAL,
                title="前端未捕獲例外 (Uncaught JavaScript Error)",
                message=error_str,
                details={
                    "name": error.name if hasattr(error, "name") else "Error",
                    "stack": error.stack if hasattr(error, "stack") else str(error),
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    def _on_console(self, msg: ConsoleMessage):
        text = msg.text
        msg_type = msg.type
        self.console_logs.append({
            "type": msg_type,
            "text": text,
            "location": f"{msg.location.get('url', '')}:{msg.location.get('lineNumber', '')}" if msg.location else ""
        })

        if not self.detect_runtime:
            return

        # Check for severe console errors
        if msg_type == "error":
            # Ignore standard 404 favicon noise
            if "favicon.ico" in text and "404" in text:
                return

            severity = IssueSeverity.CRITICAL if ("Uncaught" in text or "TypeError" in text or "SyntaxError" in text) else IssueSeverity.WARNING
            category = IssueCategory.RUNTIME_ERROR if severity == IssueSeverity.CRITICAL else IssueCategory.CONSOLE_ERROR

            self.issues.append(
                AuditIssue(
                    id=f"console-{uuid.uuid4().hex[:8]}",
                    category=category,
                    severity=severity,
                    title=f"主控台報錯 ({msg_type})",
                    message=text,
                    details={
                        "location": msg.location,
                        "args_count": len(msg.args),
                    },
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )
