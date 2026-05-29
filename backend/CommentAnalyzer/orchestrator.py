"""
MainOrchestrator
================
Central orchestration layer that merges outputs of all analyzers
into a single unified result for the extension.
"""

from __future__ import annotations
from typing import Any

from CommentAnalyzer.models.comment_list import CommentList
from CommentAnalyzer.analyzers.account_profiler import AccountProfilerAnalyzer, AuthorProfile
from CommentAnalyzer.analyzers.community_debunking import CommunityDebunkingAnalyzer
from CommentAnalyzer.analyzers.bot_network_analyzer import BotNetworkAnalyzer


# Weights for combining analyzer scores
NETWORK_WEIGHT = 0.45
DEBUNKER_WEIGHT = 0.35
PROFILER_WEIGHT = 0.20


class MainOrchestrator:
    """
    Unified orchestrator that runs all core analyzers and produces
    a single result dict for the browser extension.
    """

    def __init__(
        self,
        comment_list: CommentList,
        author_profiles: dict[str, AuthorProfile] | None = None,
        post_created_utc: float | None = None,
    ) -> None:
        self.comment_list = comment_list
        self.author_profiles = author_profiles or {}
        self.post_created_utc = post_created_utc

        # Instantiate analyzers
        self.network_analyzer = BotNetworkAnalyzer(comment_list=self.comment_list)
        self.debunker = CommunityDebunkingAnalyzer(comment_list=self.comment_list)
        self.profiler = AccountProfilerAnalyzer(
            comment_list=self.comment_list,
            author_profiles=self.author_profiles,
            post_created_utc=self.post_created_utc,
        )

    def analyze(self) -> dict[str, Any]:
        """
        Run all analyzers and return combined results.

        Returns:
            {
                "suspicion_score": float [0.0, 1.0],
                "bot_network_score": float,
                "community_debunking_score": float,
                "account_profiler_score": float,
                "debunking_keywords": list[str],
                "flags": list[str],
            }
        """
        # Run each analyzer
        bot_score = self.network_analyzer.analyze()
        debunk_result = self.debunker.analyze()
        debunk_score = debunk_result["score"]
        account_score = self.profiler.analyze()

        # Weighted combination
        combined = (
            bot_score * NETWORK_WEIGHT +
            debunk_score * DEBUNKER_WEIGHT +
            account_score * PROFILER_WEIGHT
        )

        # Generate flags
        flags = []
        if bot_score > 0.4:
            flags.append("Bot-like patterns detected")
        if bot_score > 0.7:
            flags.append("High bot network suspicion")
        if debunk_score > 0.3:
            flags.append("Community is debunking this post")
        if debunk_score > 0.6:
            flags.append("Strong community pushback")
        if account_score > 0.4:
            flags.append("Suspicious account patterns")
        if debunk_result["flagged_count"] > 5:
            flags.append(f"{debunk_result['flagged_count']} comments flagging misinformation")

        return {
            "suspicion_score": round(combined, 3),
            "bot_network_score": round(bot_score, 3),
            "community_debunking_score": round(debunk_score, 3),
            "account_profiler_score": round(account_score, 3),
            "debunking_keywords": debunk_result.get("flagged_keywords", []),
            "flags": flags,
        }
