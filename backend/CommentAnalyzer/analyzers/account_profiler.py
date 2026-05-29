"""
Account Age & Karma Profiler Analyzer
=====================================
Detects coordinated inauthentic behavior by analyzing account metadata:
- Account age clustering (many new accounts = suspicious)
- Karma-to-activity mismatch
- Fresh account ratio

Requires author profile data (account age, karma) from external source.
"""

from __future__ import annotations
from typing import Any

import numpy as np

from CommentAnalyzer.models.comment_list import CommentList

# Type alias for author profile data
AuthorProfile = dict[str, Any]

# Age bands (in days)
AGE_BAND_FRESH = 7
AGE_BAND_NEW = 30
AGE_BAND_ESTABLISHED = 365

LOW_KARMA_THRESHOLD = 100
MIN_AUTHORS_FOR_ANALYSIS = 3


class AccountProfilerAnalyzer:
    """
    Analyzes commenter identity signals to detect bot farms and astroturfing.
    """

    def __init__(
        self,
        comment_list: CommentList,
        author_profiles: dict[str, AuthorProfile],
        post_created_utc: float | None = None,
    ) -> None:
        self.comment_list = comment_list
        self.author_profiles = author_profiles
        self.post_created_utc = post_created_utc

    def analyze(self) -> float:
        """
        Run account-level analysis and return suspicion score [0.0, 1.0].
        """
        unique_authors = list(set(self.comment_list.get_all_authors()))
        if len(unique_authors) < MIN_AUTHORS_FOR_ANALYSIS:
            return 0.0

        # Resolve profiles we have data for
        resolved = {}
        for author in unique_authors:
            if author in self.author_profiles:
                resolved[author] = self.author_profiles[author]

        if not resolved:
            return 0.0

        coverage = len(resolved) / len(unique_authors)

        # Sub-metric 1: Fresh/new account ratio
        fresh_ratio = self._compute_fresh_ratio(resolved)

        # Sub-metric 2: Low karma ratio
        low_karma_ratio = self._compute_low_karma_ratio(resolved)

        # Combine
        score = (fresh_ratio * 0.6 + low_karma_ratio * 0.4)

        # Penalize if low coverage
        if coverage < 0.4:
            score *= coverage / 0.4

        return min(1.0, score)

    def _compute_fresh_ratio(self, profiles: dict[str, AuthorProfile]) -> float:
        """Ratio of accounts younger than 30 days."""
        import time
        ref_time = self.post_created_utc or time.time()
        fresh_count = 0

        for author, profile in profiles.items():
            created = profile.get("account_created_utc", 0)
            if created:
                age_days = (ref_time - created) / 86400
                if age_days < AGE_BAND_NEW:
                    fresh_count += 1

        return fresh_count / len(profiles) if profiles else 0.0

    def _compute_low_karma_ratio(self, profiles: dict[str, AuthorProfile]) -> float:
        """Ratio of accounts with very low karma."""
        low_count = 0
        for author, profile in profiles.items():
            total_karma = profile.get("comment_karma", 0) + profile.get("link_karma", 0)
            if total_karma < LOW_KARMA_THRESHOLD:
                low_count += 1

        return low_count / len(profiles) if profiles else 0.0
