"""
Pattern Engine — orchestrates sequence mining, time analysis, and scoring.

Usage:
    engine = PatternEngine(db_manager)
    report = engine.run()
    for item in report.top_suggestions:
        print(item)
"""
import logging
from dataclasses import dataclass, field
from typing import List

from worklens.pattern.sequence_miner import AppSequencePattern, SequenceMiner
from worklens.pattern.time_analyzer import TimeAnalyzer, TimePattern
from worklens.pattern.scorer import PatternScorer

logger = logging.getLogger(__name__)


@dataclass
class PatternReport:
    sequence_patterns: List[AppSequencePattern] = field(default_factory=list)
    time_patterns: List[TimePattern] = field(default_factory=list)

    @property
    def top_sequences(self) -> List[AppSequencePattern]:
        return self.sequence_patterns[:10]

    @property
    def top_time_patterns(self) -> List[TimePattern]:
        return self.time_patterns[:10]

    def summary(self) -> str:
        lines = ["=== WorkLens Pattern Report ==="]
        lines.append(f"Sequence patterns found: {len(self.sequence_patterns)}")
        lines.append(f"Time patterns found:     {len(self.time_patterns)}")

        if self.top_sequences:
            lines.append("\n--- Top App Sequences (automation candidates) ---")
            for i, p in enumerate(self.top_sequences, 1):
                score_bar = '█' * int(p.automation_score * 10)
                lines.append(
                    f"  {i:2}. [{score_bar:<10}] {p}  apps={p.apps_involved}"
                )

        if self.top_time_patterns:
            lines.append("\n--- Top Time Patterns (recurring routines) ---")
            for i, p in enumerate(self.top_time_patterns, 1):
                lines.append(f"  {i:2}. {p}")

        return "\n".join(lines)


class PatternEngine:
    """Runs all pattern analysis and returns a unified PatternReport."""

    def __init__(self, db_manager) -> None:
        self.db = db_manager
        self.miner = SequenceMiner(db_manager)
        self.time_analyzer = TimeAnalyzer(db_manager)
        self.scorer = PatternScorer()

    def run(self, days_back: int = 14, min_frequency: int = 3) -> PatternReport:
        """Run full pattern analysis pipeline."""
        logger.info(f"Starting pattern analysis (days_back={days_back})")

        # 1. Mine sequences
        sequences = self.miner.mine(days_back=days_back, min_frequency=min_frequency)
        sequences = self.scorer.score_sequences(sequences)

        # 2. Time patterns
        time_patterns = self.time_analyzer.analyze(days_back=days_back)
        time_patterns = self.scorer.score_time_patterns(time_patterns)

        report = PatternReport(
            sequence_patterns=sequences,
            time_patterns=time_patterns,
        )
        logger.info(f"Pattern analysis complete: {len(sequences)} sequences, {len(time_patterns)} time patterns")
        return report
