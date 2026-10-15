"""
Configuration loader and models for Website Health & Quality Inspector.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import yaml
from pathlib import Path


class RouteConfig(BaseModel):
    path: str
    name: Optional[str] = None
    expected_status: int = 200
    wait_until: str = "load"  # "load", "domcontentloaded", "networkidle"
    custom_wait_ms: int = 2500
    check_iframes: bool = True
    forbidden_patterns: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "::1", "44331"])
    required_selectors: List[str] = Field(default_factory=list)
    forbidden_selectors: List[str] = Field(default_factory=list)


class HeuristicRulesConfig(BaseModel):
    detect_blank_page: bool = True
    blank_page_min_text_length: int = 40
    blank_page_min_dom_nodes: int = 20
    detect_stuck_spinner: bool = True
    spinner_selectors: List[str] = Field(
        default_factory=lambda: [
            ".loading",
            ".spinner",
            ".loading-spinner",
            "[class*='spinner']",
            "[class*='loading']",
            "mat-spinner",
            "ant-spin",
            "div.v-spinner",
            ".el-loading-mask",
            ".ngx-spinner-overlay",
        ]
    )
    spinner_timeout_seconds: float = 3.5
    detect_dev_leaks: bool = True
    dev_leak_patterns: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "::1", "44331"])
    detect_api_failures: bool = True
    api_failure_threshold: int = 400
    detect_runtime_errors: bool = True
    detect_iframe_issues: bool = True
    capture_screenshots: bool = True
    full_page_screenshot: bool = False


class SiteConfig(BaseModel):
    name: str = "Website Health Audit"
    base_url: str
    headless: bool = True
    viewport: Dict[str, int] = Field(default_factory=lambda: {"width": 1440, "height": 900})
    default_timeout_ms: int = 15000
    user_agent: Optional[str] = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    routes: List[RouteConfig] = Field(default_factory=list)
    crawl_enabled: bool = False
    crawl_max_pages: int = 15
    crawl_max_depth: int = 2
    rules: HeuristicRulesConfig = Field(default_factory=HeuristicRulesConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SiteConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_url(cls, url: str, name: Optional[str] = None, crawl: bool = False, max_pages: int = 10) -> "SiteConfig":
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
            
        routes = [RouteConfig(path=path)]
        return cls(
            name=name or f"Audit of {parsed.netloc}",
            base_url=base_url,
            routes=routes,
            crawl_enabled=crawl,
            crawl_max_pages=max_pages,
        )
