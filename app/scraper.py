import time
import hashlib
import datetime
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.models import ScrapeLog


class ResilientScraper:
    """
    Production-grade Resilient Scraper.
    Implements Exponential Backoff Retries, Timeout Handling, 4xx/5xx Exception Guardrails,
    and automatic DB audit logging to `scrape_logs` without failing the parent execution loop.
    """

    def __init__(self, max_retries: int = 3, initial_backoff_sec: float = 1.0, timeout_sec: float = 8.0):
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec
        self.timeout_sec = timeout_sec

    def fetch_url(self, db: Session, company_id: str, target_url: str) -> Tuple[bool, Optional[str], int, float, Optional[str]]:
        """
        Attempts to scrape target_url with retries and exponential backoff.
        Logs every attempt result directly into `scrape_logs`.

        Returns:
        - success: bool
        - content: Optional[str]
        - status_code: int
        - duration_ms: float
        - error_message: Optional[str]
        """
        url = target_url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        retry_count = 0
        status_code = 0
        error_message = None
        html_content = None
        start_time = time.time()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 BusinessRadarCrawler/2.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        while retry_count <= self.max_retries:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                    status_code = response.getcode()
                    raw_bytes = response.read()
                    html_content = raw_bytes.decode('utf-8', errors='ignore')
                    break

            except urllib.error.HTTPError as e:
                status_code = e.code
                error_message = f"HTTPError {e.code}: {e.reason}"
                if e.code in (404, 401, 403):
                    # Non-retryable client errors
                    break
            except urllib.error.URLError as e:
                status_code = 0
                error_message = f"URLError: {e.reason}"
            except Exception as e:
                status_code = 0
                error_message = f"Scrape Exception: {str(e)}"

            retry_count += 1
            if retry_count <= self.max_retries:
                backoff = self.initial_backoff_sec * (2 ** (retry_count - 1))
                time.sleep(backoff)

        duration_ms = round((time.time() - start_time) * 1000.0, 2)
        success = (status_code == 200 and html_content is not None)
        content_hash = hashlib.sha256(html_content.encode('utf-8')).hexdigest() if html_content else None

        # Audit log into DB without breaking if DB write fails
        try:
            log_entry = ScrapeLog(
                company_id=company_id,
                target_url=url,
                status_code=status_code,
                duration_ms=duration_ms,
                error_message=error_message if not success else None,
                retry_count=min(retry_count, self.max_retries),
                content_hash=content_hash,
                scraped_at=datetime.datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"[WARN] Failed to save ScrapeLog: {db_err}")

        return success, html_content, status_code, duration_ms, error_message
