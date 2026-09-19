import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AnalyticsEventRequest(BaseModel):
    event_type: str = Field(..., description="e.g. 'page_view', 'export_csv_click', 'add_to_watchlist_click', 'upgrade_click'")
    page: Optional[str] = None
    user_id: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsService:
    """
    Privacy-Friendly Product Analytics & Event Tracker (Feature 22).
    Tracks non-PII conversion metrics (e.g. CSV exports, watchlist adds, upgrade clicks).
    """

    EVENTS_LOG = []

    @classmethod
    def log_event(cls, event: AnalyticsEventRequest, ip_address: Optional[str] = None) -> Dict[str, Any]:
        entry = {
            "event_type": event.event_type,
            "page": event.page or "/app",
            "user_id": event.user_id or "anonymous",
            "properties": event.properties,
            "ip_anonymized": ip_address[:7] + ".xxx.xxx" if ip_address else "0.0.0.0",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        cls.EVENTS_LOG.append(entry)
        # Keep buffer bounded to 5000 recent events
        if len(cls.EVENTS_LOG) > 5000:
            cls.EVENTS_LOG.pop(0)

        print(f"[ANALYTICS EVENT] '{event.event_type}' logged from user '{entry['user_id']}' on '{entry['page']}'")
        return {"status": "recorded", "event_type": event.event_type, "recorded_at": entry["timestamp"]}

    @classmethod
    def get_summary_metrics(cls) -> Dict[str, Any]:
        counts = {}
        for ev in cls.EVENTS_LOG:
            t = ev["event_type"]
            counts[t] = counts.get(t, 0) + 1
        return {
            "total_events": len(cls.EVENTS_LOG),
            "event_counts": counts
        }
