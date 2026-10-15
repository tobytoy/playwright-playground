"""
Same-domain crawler for discovering routes on any target website.
"""

from typing import List, Set
from urllib.parse import urljoin, urlparse, urldefrag
from playwright.async_api import Page


class SiteCrawler:
    def __init__(self, base_url: str, max_pages: int = 15, max_depth: int = 2):
        self.base_url = base_url.rstrip("/")
        self.base_netloc = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.discovered_paths: Set[str] = set()

    def is_valid_internal_url(self, url: str) -> bool:
        """Determines if a URL is an internal HTML route on the target site."""
        if not url:
            return False
        clean_url, _ = urldefrag(url)
        parsed = urlparse(clean_url)
        
        # Must match scheme and domain
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.netloc and parsed.netloc != self.base_netloc:
            return False

        # Exclude binary or downloadable extensions
        lower_path = parsed.path.lower()
        excluded_exts = (
            ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".tar",
            ".gz", ".mp4", ".mp3", ".doc", ".docx", ".xls", ".xlsx", ".csv",
            ".json", ".xml", ".txt"
        )
        if any(lower_path.endswith(ext) for ext in excluded_exts):
            return False

        return True

    async def extract_links_from_page(self, page: Page) -> List[str]:
        """Extracts and normalizes all internal route paths from the current page DOM."""
        links_script = """
        () => {
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            return anchors.map(a => a.href);
        }
        """
        try:
            raw_hrefs = await page.evaluate(links_script)
            valid_paths = []
            for href in raw_hrefs:
                full_url = urljoin(self.base_url, href)
                if self.is_valid_internal_url(full_url):
                    clean_url, _ = urldefrag(full_url)
                    parsed = urlparse(clean_url)
                    path_with_query = parsed.path or "/"
                    if parsed.query:
                        path_with_query += f"?{parsed.query}"
                    
                    if path_with_query not in self.discovered_paths:
                        self.discovered_paths.add(path_with_query)
                        valid_paths.append(path_with_query)
            return valid_paths
        except Exception:
            return []
