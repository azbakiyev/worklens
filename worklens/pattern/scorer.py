"""
Scorer — assigns automation potential score to discovered patterns.

Score formula (0.0 → 1.0):
  score = 0.40 * frequency_score
        + 0.40 * time_cost_score
        + 0.20 * automation_ease_score

High score = high priority for automation suggestion.
"""
import logging
from typing import List

from worklens.pattern.sequence_miner import AppSequencePattern
from worklens.pattern.time_analyzer import TimePattern

logger = logging.getLogger(__name__)

# Categories that are easy to automate (data transfer tools exist)
EASY_AUTOMATION = {"spreadsheet", "crm", "erp", "browser", "email"}
# Categories that are harder to automate
HARD_AUTOMATION = {"video_call", "other", "terminal", "ide"}


class PatternScorer:
    """Scores patterns by their automation potential."""

    def score_sequences(
        self,
        patterns: List[AppSequencePattern],
        max_frequency: int = 1
    ) -> List[AppSequencePattern]:
        """Add automation_score to each sequence pattern."""
        if not patterns:
            return patterns

        actual_max = max(p.frequency for p in patterns) if patterns else 1
        max_freq = max(max_frequency, actual_max)

        for p in patterns:
            freq_score = min(p.frequency / max_freq, 1.0)
            time_score = self._time_cost_score_for_sequence(p)
            ease_score = self._ease_score(p.sequence)
            p.automation_score = (
                0.40 * freq_score +
                0.40 * time_score +
                0.20 * ease_score
            )

        patterns.sort(key=lambda p: p.automation_score, reverse=True)
        return patterns

    def score_time_patterns(
        self,
        patterns: List[TimePattern],
        max_duration: float = 1.0
    ) -> List[TimePattern]:
        """Sort time patterns by days_observed × avg_duration."""
        if not patterns:
            return patterns
        actual_max = max(p.avg_duration_minutes for p in patterns) if patterns else 1.0
        for p in patterns:
            p.avg_duration_minutes = round(p.avg_duration_minutes, 1)
        patterns.sort(
            key=lambda p: p.days_observed * p.avg_duration_minutes,
            reverse=True
        )
        return patterns

    def _ease_score(self, sequence: tuple) -> float:
        easy = sum(1 for cat in sequence if cat in EASY_AUTOMATION)
        hard = sum(1 for cat in sequence if cat in HARD_AUTOMATION)
        total = len(sequence)
        if total == 0:
            return 0.5
        return (easy - hard * 0.5) / total

    def _time_cost_score_for_sequence(self, p: AppSequencePattern) -> float:
        # Estimate: each occurrence takes ~2 min of manual work on average
        estimated_minutes_per_week = p.frequency * 2
        # Cap at 60 min/week = score of 1.0
        return min(estimated_minutes_per_week / 60, 1.0)
