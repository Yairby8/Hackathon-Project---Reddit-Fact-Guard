"""
Community Debunking Analyzer
=============================
Detects whether the community is actively exposing or debunking the
main post as fake, AI-generated, or a disinformation campaign.

Uses a keyword-based approach (no LLM dependency) for speed.
"""

from CommentAnalyzer.models.comment_list import CommentList


# Debunking lexicon — words that indicate the community is calling BS
# Only include strong signals, not casual words
DEBUNKING_LEXICON = {
    "debunked", "photoshopped", "hoax",
    "misleading", "midjourney", "dall-e", "dalle",
    "fabricated", "disinformation", "misinformation", "propaganda", "staged",
    "manipulated", "doctored", "deepfake",
    "astroturf", "scam", "fraudulent", "clickbait",
    "debunk", "fact-check", "factcheck", "fact check",
    "ai-generated", "ai generated", "stable diffusion",
    "not real", "completely fake", "proven false",
}


class CommunityDebunkingAnalyzer:
    """
    Scans comments for debunking keywords and computes a community
    skepticism score.
    """

    def __init__(self, comment_list: CommentList):
        self.comment_list = comment_list

    def _text_matches_lexicon(self, text: str) -> bool:
        """Check if any debunking term appears in the text."""
        for term in DEBUNKING_LEXICON:
            if term in text:
                return True
        return False

    def analyze(self) -> dict:
        """
        Scan all comments against the debunking lexicon.

        Returns a dict with:
          - "score": float [0.0, 1.0] — how much the community is debunking
          - "flagged_count": int
          - "discussion_density": float
          - "unique_author_ratio": float
          - "flagged_keywords": list of matched keywords
        """
        comments = self.comment_list.get_all_comments()
        total = len(comments)

        if total == 0:
            return {
                "score": 0.0,
                "flagged_count": 0,
                "discussion_density": 0.0,
                "unique_author_ratio": 0.0,
                "flagged_keywords": [],
            }

        flagged_authors = set()
        flagged_count = 0
        matched_keywords = set()

        for comment in comments:
            text = comment.cleaned_text if comment.cleaned_text else ""
            if not text:
                continue

            for term in DEBUNKING_LEXICON:
                if term in text:
                    flagged_count += 1
                    flagged_authors.add(comment.author)
                    matched_keywords.add(term)
                    break  # Count each comment only once

        discussion_density = flagged_count / total if total > 0 else 0.0
        unique_authors = self.comment_list.get_all_authors()
        unique_author_count = len(set(unique_authors))
        unique_author_ratio = (
            len(flagged_authors) / unique_author_count
            if unique_author_count > 0
            else 0.0
        )

        # Score: combine density and author diversity of debunking
        # High density + many different authors debunking = strong signal
        score = min(1.0, (discussion_density * 3) * 0.6 + unique_author_ratio * 0.4)

        return {
            "score": score,
            "flagged_count": flagged_count,
            "discussion_density": round(discussion_density, 3),
            "unique_author_ratio": round(unique_author_ratio, 3),
            "flagged_keywords": list(matched_keywords)[:10],
        }
