"""
Reddit Fact Guard - Multi-Signal AI Credibility Analysis Backend
================================================================
Combines:
  1. Groq LLM text analysis (AI credibility scoring)
  2. Groq Vision image analysis (AI-generated detection)
  3. Bot Network Analyzer (heuristic comment pattern detection)
  4. Community Debunking Analyzer (keyword-based skepticism detection)
  5. Author History Fetcher (PullPush-based account credibility)
"""

import os
import sys
import json
import base64
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from CommentAnalyzer import Comment, CommentList, MainOrchestrator
from history_fetcher import fetch_user_history

load_dotenv()

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

TEXT_MODEL = "llama-3.1-8b-instant"
VISION_MODEL = "llama-3.2-90b-vision-preview"

# ============================================================================
# PROMPTS
# ============================================================================

ANALYSIS_PROMPT = """You are a balanced credibility analyst for Reddit posts. Your job is to assess whether a post contains misinformation or deceptive content.

IMPORTANT CONTEXT: Most Reddit posts are normal, everyday content — questions, opinions, discussions, memes, personal stories. These should score HIGH (70-85) because they are not trying to deceive anyone. Only score LOW if there are clear signs of actual misinformation, deception, or manipulation.

Scoring guidelines:
- 85-100: Factual content with sources, news from credible outlets, expert discussion
- 70-84: Normal posts — opinions, questions, personal stories, discussions, humor. This is the DEFAULT for regular content.
- 50-69: Unverifiable claims presented as fact, missing important context
- 30-49: Likely misleading — emotional manipulation, debunked claims, clear bias presented as neutral
- 0-29: Clear misinformation, fabricated content, deliberate deception

A post asking a question is NOT misleading. A personal opinion is NOT misinformation. A meme is NOT deception. Casual/informal language is NOT a red flag.

ADDITIONAL CONTEXT:
- Author history: {author_context}
- Community signals: {community_context}

POST DATA:
- Title: {title}
- Subreddit: {subreddit}
- Author: {author}
- Post Content: {body}
- Sample Comments: {comments_text}

IMPORTANT: You MUST respond with ONLY valid JSON in this exact format, no other text:
{{
  "credibility_score": <number 0-100>,
  "verdict": "<one of: Highly Credible, Likely Credible, Normal Post, Uncertain, Likely Misleading, Highly Misleading>",
  "reasoning": "<2-3 sentence explanation>",
  "flags": ["<flag1>", "<flag2>"]
}}

If the post is just a normal question, discussion, or opinion with no deceptive intent, score it 70-80 and use verdict "Normal Post" with minimal flags."""

IMAGE_ANALYSIS_PROMPT = """You are an image credibility analyst. Analyze this image that was posted on Reddit along with the post context.

Post title: {title}
Subreddit: {subreddit}

Analyze the image for:
1. Does it appear to be AI-generated? (look for artifacts, unnatural lighting, distorted hands/text, inconsistent shadows, too-perfect skin)
2. Does it appear to be manipulated or doctored?
3. Is it misleading in context?
4. Does it contain text overlays that make unsourced claims?
5. Is it a screenshot that could be fabricated?

IMPORTANT: You MUST respond with ONLY valid JSON in this exact format, no other text:
{{
  "ai_generated_likelihood": "<one of: Very Likely AI, Possibly AI, Unlikely AI, Not AI>",
  "manipulation_detected": <true or false>,
  "image_concerns": ["<concern1>", "<concern2>"],
  "image_credibility_score": <number 0-100 where 100 means fully authentic>,
  "image_reasoning": "<1-2 sentence explanation>"
}}"""


# ============================================================================
# COMMENT ANALYZER PIPELINE
# ============================================================================

def run_comment_analysis(comments_data: list) -> dict:
    """Run the CommentAnalyzer pipeline on structured comment data."""
    if not comments_data or len(comments_data) < 3:
        return {
            "suspicion_score": 0.0,
            "bot_network_score": 0.0,
            "community_debunking_score": 0.0,
            "flags": [],
            "debunking_keywords": [],
        }

    comment_objects = []
    for c in comments_data:
        try:
            comment_objects.append(Comment(
                id=c.get("id", ""),
                parent_id=c.get("parent_id", ""),
                text=c.get("text", ""),
                author=c.get("author", ""),
                created_utc=c.get("created_utc", time.time()),
            ))
        except Exception:
            continue

    if len(comment_objects) < 3:
        return {
            "suspicion_score": 0.0,
            "bot_network_score": 0.0,
            "community_debunking_score": 0.0,
            "flags": [],
            "debunking_keywords": [],
        }

    comment_list = CommentList(comment_objects)
    orchestrator = MainOrchestrator(
        comment_list=comment_list,
        author_profiles={},
        post_created_utc=time.time(),
    )
    return orchestrator.analyze()


# ============================================================================
# GROQ AI ANALYSIS
# ============================================================================

def analyze_text_with_groq(post_data: dict, author_context: str, community_context: str) -> dict | None:
    """Send post data to Groq for AI text credibility analysis."""
    comments_text = ""
    if post_data.get("comments"):
        comment_texts = []
        for c in post_data["comments"][:15]:
            author = c.get("author", "anon")
            text = c.get("text", "")
            if text:
                comment_texts.append(f"[{author}]: {text[:200]}")
        comments_text = "\n".join(comment_texts)

    prompt = ANALYSIS_PROMPT.format(
        title=post_data.get("title", ""),
        subreddit=post_data.get("subreddit", ""),
        author=post_data.get("author", ""),
        body=post_data.get("body", "No body content"),
        comments_text=comments_text or "No comments available",
        author_context=author_context,
        community_context=community_context,
    )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": "You are a credibility analysis AI. Always respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }

    text = ""
    try:
        print(f"[Groq Text] Sending request...")
        response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"[Groq Text] HTTP {response.status_code}: {response.text[:300]}")
            return None

        data = response.json()
        text = data["choices"][0]["message"]["content"]

        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        return json.loads(text)

    except requests.exceptions.RequestException as e:
        print(f"[Groq Text] API error: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"[Groq Text] Parse error: {e}")
        print(f"[Groq Text] Raw: {text[:300] if text else 'empty'}")
        return None


def analyze_image_with_groq(image_url: str, post_data: dict) -> dict | None:
    """Send image to Groq Vision model for analysis."""
    image_b64, media_type = download_image_as_base64(image_url)
    if not image_b64:
        return None

    prompt = IMAGE_ANALYSIS_PROMPT.format(
        title=post_data.get("title", ""),
        subreddit=post_data.get("subreddit", ""),
    )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:{media_type};base64,{image_b64}"
                }},
            ]},
        ],
        "temperature": 0.3,
        "max_tokens": 400,
    }

    text = ""
    try:
        print(f"[Groq Vision] Sending image for analysis...")
        response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=45)

        if response.status_code != 200:
            print(f"[Groq Vision] HTTP {response.status_code}: {response.text[:300]}")
            return None

        data = response.json()
        text = data["choices"][0]["message"]["content"]

        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        return json.loads(text)

    except requests.exceptions.RequestException as e:
        print(f"[Groq Vision] API error: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"[Groq Vision] Parse error: {e}")
        print(f"[Groq Vision] Raw: {text[:300] if text else 'empty'}")
        return None


def download_image_as_base64(image_url: str):
    """Download an image and convert to base64."""
    try:
        response = requests.get(image_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        response.raise_for_status()

        content_type = response.headers.get("content-type", "image/jpeg")
        if "image" not in content_type:
            return None, None

        image_b64 = base64.b64encode(response.content).decode("utf-8")
        if "png" in content_type:
            media_type = "image/png"
        elif "webp" in content_type:
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"

        print(f"[Image] Downloaded: {len(response.content)} bytes, {media_type}")
        return image_b64, media_type

    except Exception as e:
        print(f"[Image] Download error: {e}")
        return None, None


# ============================================================================
# SCORE COMBINATION
# ============================================================================

def combine_all_results(ai_result, image_result, comment_analysis, author_history):
    """
    Combine all analysis signals into a final credibility result.
    The AI score is the primary signal. Heuristics only apply penalties
    when signals are STRONG.
    """
    if ai_result:
        base_score = ai_result.get("credibility_score", 70)
        verdict = ai_result.get("verdict", "Normal Post")
        reasoning = ai_result.get("reasoning", "")
        flags = ai_result.get("flags", [])
    else:
        base_score = 70
        verdict = "Normal Post"
        reasoning = "AI text analysis unavailable."
        flags = []

    # --- Comment analysis (only penalize on STRONG signals) ---
    bot_score = comment_analysis.get("bot_network_score", 0)
    debunk_score = comment_analysis.get("community_debunking_score", 0)

    comment_penalty = 0
    if bot_score > 0.6:
        comment_penalty = int((bot_score - 0.6) * 25)
        flags.append("Bot-like coordination detected")
    elif bot_score > 0.4:
        flags.append("Minor bot-like patterns")

    debunk_penalty = 0
    if debunk_score > 0.5:
        debunk_penalty = int((debunk_score - 0.5) * 20)
        flags.append("Community actively debunking this post")
    elif debunk_score > 0.3:
        flags.append("Some skepticism in comments")

    if comment_analysis.get("debunking_keywords"):
        keywords = comment_analysis["debunking_keywords"][:3]
        flags.append(f"Keywords: {', '.join(keywords)}")

    # --- Author history ---
    history_modifier = 0
    age_indicator = author_history.get("account_age_indicator", "unknown")
    total_items = author_history.get("total_items", 0)

    if age_indicator == "very_new":
        history_modifier = -8
        flags.append("Very new account (< 7 days)")
    elif age_indicator == "new":
        history_modifier = -4
        flags.append("New account (< 30 days)")
    elif age_indicator == "veteran" and total_items > 30:
        history_modifier = +3

    # --- Image analysis ---
    image_modifier = 0
    if image_result:
        ai_likelihood = image_result.get("ai_generated_likelihood", "")

        if "Very Likely" in ai_likelihood:
            image_modifier = -15
            flags.append(f"Image: {ai_likelihood}")
        elif "Possibly" in ai_likelihood:
            image_modifier = -6
            flags.append(f"Image: {ai_likelihood}")

        if image_result.get("manipulation_detected"):
            image_modifier -= 5
            flags.append("Image manipulation detected")

        image_concerns = image_result.get("image_concerns", [])
        for concern in image_concerns[:2]:
            if concern:
                flags.append(f"Image: {concern}")

        if image_result.get("image_reasoning"):
            reasoning += f" Image: {image_result['image_reasoning']}"

    # --- Final score ---
    final_score = base_score - comment_penalty - debunk_penalty + history_modifier + image_modifier
    final_score = max(0, min(100, final_score))

    if final_score >= 75:
        verdict = "Highly Credible"
    elif final_score >= 55:
        verdict = "Likely Credible"
    elif final_score >= 35:
        verdict = "Uncertain"
    elif final_score >= 20:
        verdict = "Likely Misleading"
    else:
        verdict = "Highly Misleading"

    # Deduplicate flags
    seen = set()
    unique_flags = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            unique_flags.append(f)

    return {
        "credibility_score": final_score,
        "verdict": verdict,
        "reasoning": reasoning,
        "flags": unique_flags[:8],
    }


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route("/analyze", methods=["POST"])
def analyze_post():
    """Full multi-signal analysis of a Reddit post."""
    post_data = request.get_json(force=True)

    image_url = post_data.get("imageUrl", "")
    author = post_data.get("author", "")
    comments_data = post_data.get("comments", [])

    print(f"\n{'='*60}")
    print(f"[Analyze] Author: {author} | Subreddit: {post_data.get('subreddit')}")
    print(f"          Title: {post_data.get('title', '')[:80]}")
    print(f"          Body: {len(post_data.get('body', ''))} chars")
    print(f"          Comments: {len(comments_data)} structured")
    print(f"          Image: {'Yes' if image_url else 'No'}")

    # 1. Comment analysis
    print(f"[Pipeline] Running comment analysis...")
    comment_analysis = run_comment_analysis(comments_data)
    print(f"[Pipeline] Bot: {comment_analysis['bot_network_score']:.3f} | "
          f"Debunk: {comment_analysis['community_debunking_score']:.3f}")

    # 2. Author history
    print(f"[Pipeline] Fetching author history for u/{author}...")
    author_history = fetch_user_history(author, limit=30)
    print(f"[Pipeline] History: {author_history['total_items']} items, "
          f"age: {author_history['account_age_indicator']}")

    # Context for AI prompt
    author_context = f"Account age: {author_history['account_age_indicator']}, " \
                     f"History items: {author_history['total_items']}"
    community_context = f"Bot suspicion: {comment_analysis['bot_network_score']:.2f}, " \
                        f"Community debunking: {comment_analysis['community_debunking_score']:.2f}"
    if comment_analysis.get("debunking_keywords"):
        community_context += f", Keywords: {', '.join(comment_analysis['debunking_keywords'][:5])}"

    # 3. Groq AI text analysis
    ai_result = analyze_text_with_groq(post_data, author_context, community_context)

    # 4. Image analysis (if present)
    image_result = None
    if image_url:
        image_result = analyze_image_with_groq(image_url, post_data)

    # 5. Combine all signals
    final_result = combine_all_results(ai_result, image_result, comment_analysis, author_history)

    print(f"[Result]  Score: {final_result['credibility_score']} | "
          f"Verdict: {final_result['verdict']}")
    print(f"[Result]  Flags: {final_result['flags']}")

    return jsonify(final_result)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "groq_configured": bool(GROQ_API_KEY),
        "pipeline": ["groq_text", "groq_vision", "bot_network", "community_debunking", "author_history"],
    })


if __name__ == "__main__":
    print("\n  Reddit Fact Guard - Multi-Signal Analysis Backend")
    print(f"   Groq API: {'configured' if GROQ_API_KEY else 'missing key'}")
    print(f"   Text model: {TEXT_MODEL}")
    print(f"   Vision model: {VISION_MODEL}")
    print(f"   Pipeline: AI Text + Vision + Bot Detection + Debunking + History")
    print(f"   Server: http://localhost:8000")
    print()
    app.run(host="0.0.0.0", port=8000, debug=True)
