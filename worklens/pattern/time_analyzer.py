"""
Time Analyzer — detects recurring time-based patterns.

Finds things like:
  - Every day at 09:00-09:30 employee is in Excel
  - Every Friday afternoon 30+ minutes in email
  - Daily CRM usage spikes at 14:00
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)

# Minimum days a pattern must repeat to count
MIN_DAYS_REPEAT = 3
# Time bucket size in minutes
BUCKET_MINUTES = 30


@dataclass
class TimePattern:
    app_category: str
    hour_bucket: int            # 0-23 (start of 30-min window)
    minute_bucket: int          # 0 or 30
    days_observed: int          # how many different days seen
    avg_duration_minutes: float
    day_of_week: int = -1       # -1=any day, 0=Mon..6=Sun

    @property
    def time_label(self) -> str:
        return f"{self.hour_bucket:02d}:{self.minute_bucket:02d}"

    def __str__(self) -> str:
        dow = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        day_str = dow[self.day_of_week] if self.day_of_week >= 0 else "daily"
        return (
            f"{self.app_category} @ {self.time_label} ({day_str}) — "
            f"{self.days_observed} days, ~{self.avg_duration_minutes:.0f} min"
        )


class TimeAnalyzer:
    """Detects recurring time-of-day patterns from activity events."""

    def __init__(self, db_manager) -> None:
        self.db = db_manager

    def analyze(self, days_back: int = 14, min_repeat: int = MIN_DAYS_REPEAT) -> List[TimePattern]:
        """Return list of recurring time-based patterns."""
        rows = self._load_events(days_back)
        if not rows:
            return []

        # bucket_key → {date → count}
        buckets: Dict[tuple, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for row in rows:
            ts = row["ts"] if isinstance(row["ts"], datetime) else datetime.fromisoformat(str(row["ts"]))
            cat = row["cat"]
            date_str = ts.date().isoformat()
            bucket_minute = 0 if ts.minute < 30 else 30
            key = (cat, ts.hour, bucket_minute)
            buckets[key][date_str] += 1

        patterns = []
        for (cat, hour, minute), day_counts in buckets.items():
            days = len(day_counts)
            if days < min_repeat:
                continue
            total_events = sum(day_counts.values())
            avg_duration = (total_events / days) * 5  # 5 sec per event
            avg_duration_min = avg_duration / 60

            patterns.append(TimePattern(
                app_category=cat,
                hour_bucket=hour,
                minute_bucket=minute,
                days_observed=days,
                avg_duration_minutes=avg_duration_min,
            ))

        patterns.sort(key=lambda p: (p.days_observed, p.avg_duration_minutes), reverse=True)
        logger.info(f"Time analyzer found {len(patterns)} recurring time patterns")
        return patterns

    def _load_events(self, days_back: int) -> List[dict]:
        from sqlalchemy import text
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        sql = text("""
            SELECT timestamp, app_name, window_category
            FROM activity_events
            WHERE timestamp >= :cutoff AND is_privacy_zone = 0
            ORDER BY timestamp ASC
        """)
        try:
            with self.db.get_session() as session:
                result = session.execute(sql, {"cutoff": cutoff})
                return [
                    {"ts": row[0], "app": row[1], "cat": row[2] or "other"}
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error(f"Failed to load events for time analysis: {e}")
            return []
