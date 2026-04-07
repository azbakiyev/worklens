"""
Suggestion Engine -- analyzes collected activity data and generates
actionable automation suggestions using GPT-4o.

Flow:
  1. Collect stats from SQLite (apps, time, patterns, intents)
  2. Build a structured summary (no personal content)
  3. Send to GPT-4o → get JSON suggestions
  4. Save suggestions to DB
  5. Return ranked list with ROI estimates
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

WORKLENS_API_URL = "https://web-production-3c1ef.up.railway.app"
WORKLENS_TOKEN   = "wl_9060ee04-9506-4641-b461-d6c5d8713589"

ANALYSIS_PROMPT = """You are a business process automation expert.

Analyze this employee work activity data and identify TOP automation opportunities.

Return a JSON array of suggestions (max 6), sorted by impact (highest first):
[
  {
    "title": "Short title (max 8 words)",
    "description": "What the employee does manually and why it should be automated (2-3 sentences)",
    "evidence": "Specific data that proves this pattern exists",
    "time_per_week_hours": 3.5,
    "automation_tool": "Specific tool/method to automate (e.g. Zapier, Python script, Make.com, API integration)",
    "implementation_hours": 8,
    "priority": "high|medium|low",
    "category": "data_transfer|reporting|communication|file_processing|approval"
  }
]

IMPORTANT:
- Base suggestions ONLY on the data provided
- Be specific about what to automate and how
- time_per_week_hours must be realistic based on event counts
- implementation_hours should be realistic (2-40 hours)
- If data is insufficient for a category, skip it
- Return ONLY valid JSON array, no markdown
"""


class SuggestionEngine:
    """Analyzes activity data and generates automation suggestions via LLM."""

    def __init__(self, db_manager, config_manager=None):
        self.db = db_manager
        self.config = config_manager

    def run(self, days_back: int = 14, hourly_rate: float = 1500.0) -> List[Dict]:
        """
        Full analysis pipeline.
        Returns list of automation suggestions with ROI.
        """
        logger.info(f"Starting suggestion analysis (days_back={days_back})")

        # 1. Collect stats
        stats = self._collect_stats(days_back)
        if not stats or stats.get("total_events", 0) < 100:
            logger.info("Not enough data for analysis (need 100+ events)")
            return []

        # 2. Build prompt data
        prompt_data = self._build_prompt_data(stats)

        # 3. Call LLM
        suggestions = self._analyze_with_llm(prompt_data)
        if not suggestions:
            return []

        # 4. Enrich with ROI
        enriched = self._enrich_with_roi(suggestions, hourly_rate)

        # 5. Save to DB
        self._save_suggestions(enriched)

        logger.info(f"Generated {len(enriched)} suggestions")
        return enriched

    def _collect_stats(self, days_back: int) -> dict:
        """Collect structured stats from SQLite."""
        from sqlalchemy import text
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

        try:
            with self.db.get_session() as s:
                total = s.execute(text(
                    "SELECT COUNT(*) FROM activity_events WHERE timestamp >= :c"
                ), {"c": cutoff}).scalar() or 0

                days_active = s.execute(text(
                    "SELECT COUNT(DISTINCT date(timestamp)) FROM activity_events WHERE timestamp >= :c"
                ), {"c": cutoff}).scalar() or 1

                # App usage
                apps = s.execute(text("""
                    SELECT app_name, window_category, COUNT(*) c
                    FROM activity_events
                    WHERE timestamp >= :c AND is_privacy_zone = 0
                    GROUP BY app_name ORDER BY c DESC LIMIT 12
                """), {"c": cutoff}).fetchall()

                # Category totals
                cats = s.execute(text("""
                    SELECT window_category, COUNT(*) c
                    FROM activity_events
                    WHERE timestamp >= :c AND is_privacy_zone = 0
                    GROUP BY window_category ORDER BY c DESC
                """), {"c": cutoff}).fetchall()

                # Clipboard patterns
                clips = s.execute(text("""
                    SELECT clipboard_type, COUNT(*) c
                    FROM activity_events
                    WHERE timestamp >= :c AND clipboard_type NOT IN ('empty','unknown')
                    GROUP BY clipboard_type ORDER BY c DESC
                """), {"c": cutoff}).fetchall()

                # Messenger intents
                intents = s.execute(text("""
                    SELECT intent_type, urgency, COUNT(*) c
                    FROM messenger_intents
                    WHERE timestamp >= :c
                    GROUP BY intent_type, urgency
                """), {"c": cutoff}).fetchall()

                # Files received
                files = s.execute(text("""
                    SELECT file_type, document_category, COUNT(*) c
                    FROM received_files
                    WHERE timestamp >= :c
                    GROUP BY file_type, document_category
                """), {"c": cutoff}).fetchall()

                # Time patterns (hour of day)
                hourly = s.execute(text("""
                    SELECT strftime('%H', timestamp) h, app_name, COUNT(*) c
                    FROM activity_events
                    WHERE timestamp >= :c
                    GROUP BY h, app_name
                    HAVING c > 10
                    ORDER BY c DESC LIMIT 20
                """), {"c": cutoff}).fetchall()

            return {
                "total_events": total,
                "days_active": days_active,
                "events_per_day": round(total / max(days_active, 1)),
                "apps": [{"name": r[0], "category": r[1], "events": r[2]} for r in apps],
                "categories": [{"cat": r[0], "events": r[1]} for r in cats],
                "clipboard_types": [{"type": r[0], "count": r[1]} for r in clips],
                "messenger_intents": [{"type": r[0], "urgency": r[1], "count": r[2]} for r in intents],
                "files_received": [{"type": r[0], "category": r[1], "count": r[2]} for r in files],
                "hourly_patterns": [{"hour": r[0], "app": r[1], "count": r[2]} for r in hourly],
            }
        except Exception as e:
            logger.error(f"Stats collection error: {e}")
            return {}

    def _build_prompt_data(self, stats: dict) -> str:
        """Format stats as readable text for LLM."""
        secs_per_event = 5
        total_hours = round(stats["total_events"] * secs_per_event / 3600, 1)
        hrs_per_day = round(stats["events_per_day"] * secs_per_event / 3600, 1)

        lines = [
            f"EMPLOYEE ACTIVITY ANALYSIS",
            f"Period: {stats['days_active']} working days",
            f"Total tracked time: {total_hours}h (~{hrs_per_day}h/day)",
            f"",
            f"APP USAGE (time spent):",
        ]

        for a in stats["apps"][:10]:
            hrs = round(a["events"] * secs_per_event / 3600, 1)
            pct = round(a["events"] / stats["total_events"] * 100)
            lines.append(f"  {a['name']:<28} {a['category']:<15} {hrs}h ({pct}%)")

        lines.append("")
        lines.append("CLIPBOARD ACTIVITY (copy-paste patterns):")
        for c in stats["clipboard_types"]:
            lines.append(f"  {c['type']:<20} {c['count']} times")

        if stats["messenger_intents"]:
            lines.append("")
            lines.append("TELEGRAM MESSAGES ANALYZED:")
            for i in stats["messenger_intents"]:
                lines.append(f"  {i['type']:<20} urgency={i['urgency']:<8} count={i['count']}")

        if stats["files_received"]:
            lines.append("")
            lines.append("FILES RECEIVED VIA TELEGRAM:")
            for f in stats["files_received"]:
                lines.append(f"  {f['type']:<15} {f['category']:<20} count={f['count']}")

        if stats["hourly_patterns"]:
            lines.append("")
            lines.append("RECURRING TIME PATTERNS (same app used at same hour repeatedly):")
            for h in stats["hourly_patterns"][:8]:
                lines.append(f"  {h['app']:<28} at {h['hour']}:00  ({h['count']} times)")

        return "\n".join(lines)

    def _analyze_with_llm(self, prompt_data: str) -> List[Dict]:
        """Send to WorkLens API → GPT-4o → get suggestions."""
        import requests
        try:
            resp = requests.post(
                f"{WORKLENS_API_URL}/analyze_patterns",
                json={
                    "data": prompt_data,
                    "token": WORKLENS_TOKEN,
                },
                timeout=60
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                return resp.json().get("suggestions", [])
            logger.error(f"LLM analysis failed: {resp.status_code} {resp.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            return []

    def _enrich_with_roi(self, suggestions: List[Dict], hourly_rate: float) -> List[Dict]:
        """Add ROI calculations to each suggestion."""
        for s in suggestions:
            hrs_week = float(s.get("time_per_week_hours", 0))
            impl_hrs = float(s.get("implementation_hours", 8))

            annual_hrs = hrs_week * 52
            annual_cost = round(annual_hrs * hourly_rate)
            impl_cost = round(impl_hrs * hourly_rate * 2)  # dev rate = 2x
            roi_pct = round((annual_cost - impl_cost) / max(impl_cost, 1) * 100)
            payback_weeks = round(impl_hrs / max(hrs_week, 0.1))

            s["roi"] = {
                "annual_hours_saved": round(annual_hrs, 1),
                "annual_cost_saved": annual_cost,
                "implementation_cost": impl_cost,
                "roi_percent": roi_pct,
                "payback_weeks": payback_weeks,
                "hourly_rate": hourly_rate,
            }
        return suggestions

    def _save_suggestions(self, suggestions: List[Dict]) -> None:
        """Save suggestions to DB."""
        from sqlalchemy import text
        try:
            with self.db.get_session() as s:
                s.execute(text("DELETE FROM automation_suggestions WHERE status='pending'"))
                for i, sg in enumerate(suggestions):
                    s.execute(text("""
                        INSERT INTO automation_suggestions
                            (title, description, time_save_minutes_per_week,
                             roi_annual, implementation_tools, extella_task_json,
                             status, created_at, updated_at)
                        VALUES (:title, :desc, :time_min, :roi, :tools, :etask,
                                'pending', datetime('now'), datetime('now'))
                    """), {
                        "title": sg.get("title", ""),
                        "desc": sg.get("description", "") + "\n\nEvidence: " + sg.get("evidence", ""),
                        "time_min": round(sg.get("time_per_week_hours", 0) * 60),
                        "roi": sg.get("roi", {}).get("annual_cost_saved", 0),
                        "tools": sg.get("automation_tool", ""),
                        "etask": json.dumps(sg),
                    })
        except Exception as e:
            logger.error(f"Save suggestions error: {e}")
