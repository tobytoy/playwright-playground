"""
Data models for Website Health & Quality Inspector.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IssueSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class IssueCategory(str, Enum):
    RUNTIME_ERROR = "RUNTIME_ERROR"         # pageerror / uncaught exceptions
    CONSOLE_ERROR = "CONSOLE_ERROR"         # console.error
    API_FAILURE = "API_FAILURE"             # XHR/fetch returning 4xx/5xx
    RESOURCE_FAILURE = "RESOURCE_FAILURE"   # images, scripts, fonts 404/ERR
    BLANK_PAGE = "BLANK_PAGE"               # empty DOM, no content
    STUCK_SPINNER = "STUCK_SPINNER"         # infinite loading state
    DEV_URL_LEAK = "DEV_URL_LEAK"           # localhost, 127.0.0.1, internal IPs
    IFRAME_BROKEN = "IFRAME_BROKEN"         # 404, blocked or empty iframe
    CSP_VIOLATION = "CSP_VIOLATION"         # security policy violations
    REDIRECT_ANOMALY = "REDIRECT_ANOMALY"   # unexpected redirects without error hints


class AuditIssue(BaseModel):
    id: str
    category: IssueCategory
    severity: IssueSeverity
    title: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    element_selector: Optional[str] = None
    timestamp: str


class NetworkRecord(BaseModel):
    url: str
    method: str
    status: int
    resource_type: str
    duration_ms: Optional[float] = None
    failure_text: Optional[str] = None


class PageAuditResult(BaseModel):
    url: str
    route_path: str
    page_title: str = ""
    http_status: Optional[int] = None
    load_time_ms: float = 0.0
    screenshot_path: Optional[str] = None
    issues: List[AuditIssue] = Field(default_factory=list)
    network_records: List[NetworkRecord] = Field(default_factory=list)
    console_logs: List[Dict[str, str]] = Field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    @property
    def has_warning(self) -> bool:
        return any(i.severity == IssueSeverity.WARNING for i in self.issues)

    @property
    def is_passed(self) -> bool:
        return not self.has_critical


class AuditSummary(BaseModel):
    total_pages: int = 0
    passed_pages: int = 0
    failed_pages: int = 0
    total_critical: int = 0
    total_warning: int = 0
    total_info: int = 0
    duration_seconds: float = 0.0


class AuditReport(BaseModel):
    site_name: str
    base_url: str
    started_at: str
    finished_at: str
    summary: AuditSummary
    pages: List[PageAuditResult]
