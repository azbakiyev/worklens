"""
Sequence Miner — finds frequent app switch sequences in activity data.

Algorithm: sliding window over activity_events, groups into sessions,
then counts N-grams of app categories to find recurring patterns.

Example output:
  (browser -> spreadsheet -> erp)  frequency=24  avg_duration=8.5min
  (email -> spreadsheet)           frequency=31  avg_duration=3.2min
"""
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Gap between events that signals a new work session
SESSION_GAP_MINUTES = 15
# Minimum times a sequence must appear to be considered a pattern
MIN_FREQUENCY = 3
# N-gram sizes to mine (pairs and triples)
NGRAM_SIZES = [2, 3]


@dataclass
class AppSequencePattern:
    sequence: Tuple[str, ...]       # e.g. ('email', 'spreadsheet', 'crm')
    frequency: int                  # how many times seen
    apps_involved: List[str]        # actual app names (not categories)
    automation_score: float = 0.0   # computed by scorer

    def __str__(self) -> str:
        return f"{'→'.join(self.sequence)} (x{self.frequency})"


class SequenceMiner:
    """Mines frequent app-category sequences from the local activity database."""

    def __init__(self, db_manager) -> None:
        self.db = db_manager

    def mine(self, days_back: int = 14, min_frequency: int = MIN_FREQUENCY) -> List[AppSequencePattern]:
        """Run the full mining pipeline and return discovered patterns."""
        rows = self._load_events(days_back)
        if not rows:
            logger.info("No events found for sequence mining")
            return []

        sessions = self._split_into_sessions(rows)
        logger.info(f"Loaded {len(rows)} events → {len(sessions)} sessions")

        patterns = self._mine_ngrams(sessions, min_frequency)
        logger.info(f"Found {len(patterns)} frequent sequences (min_freq={min_frequency})")
        return patterns

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_events(self, days_back: int) -> List[dict]:
        """Fetch activity events from the local DB."""
        from sqlalchemy import text
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        sql = text("""
            SELECT timestamp, app_name, window_category
            FROM activity_events
            WHERE timestamp >= :cutoff
              AND is_privacy_zone = 0
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
            logger.error(f"Failed to load events: {e}")
            return []

    def _split_into_sessions(self, rows: List[dict]) -> List[List[dict]]:
        """Split flat event list into work sessions based on time gaps."""
        if not rows:
            return []

        sessions: List[List[dict]] = []
        current: List[dict] = [rows[0]]
        gap = timedelta(minutes=SESSION_GAP_MINUTES)

        for prev, curr in zip(rows, rows[1:]):
            # Handle both string timestamps and datetime objects
            prev_ts = prev["ts"] if isinstance(prev["ts"], datetime) else datetime.fromisoformat(str(prev["ts"]))
            curr_ts = curr["ts"] if isinstance(curr["ts"], datetime) else datetime.fromisoformat(str(curr["ts"]))
            if curr_ts - prev_ts > gap:
                sessions.append(current)
                current = []
            current.append(curr)

        if current:
            sessions.append(current)
        return sessions

    def _mine_ngrams(
        self, sessions: List[List[dict]], min_frequency: int
    ) -> List[AppSequencePattern]:
        """Count N-grams of app categories across all sessions."""
        ngram_counter: Counter = Counter()
        # Map ngram → set of app names seen in that context
        ngram_apps: dict = {}

        for session in sessions:
            # Deduplicate consecutive identical categories
            cats = []
            for event in session:
                cat = event["cat"]
                if not cats or cats[-1][0] != cat:
                    cats.append((cat, event["app"]))

            for n in NGRAM_SIZES:
                for i in range(len(cats) - n + 1):
                    window = cats[i:i + n]
                    seq = tuple(c for c, _ in window)
                    apps = [a for _, a in window]
                    ngram_counter[seq] += 1
                    if seq not in ngram_apps:
                        ngram_apps[seq] = set()
                    ngram_apps[seq].update(apps)

        patterns = []
        for seq, freq in ngram_counter.items():
            if freq >= min_frequency:
                patterns.append(AppSequencePattern(
                    sequence=seq,
                    frequency=freq,
                    apps_involved=sorted(ngram_apps[seq]),
                ))

        # Sort by frequency descending
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        return patterns
