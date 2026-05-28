"""
Reddit Trust & Safety - Backend Server
Run with: python server.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/analyze", methods=["POST"])
def analyze_post():
    """
    Analyze a Reddit post for credibility.
    Currently returns a dummy score - replace with real AI logic later.
    """
    data = request.get_json()
    title = data.get("title", "")
    author = data.get("author", "")
    subreddit = data.get("subreddit", "")

    print(f"[Analyze] title={title!r}, author={author!r}, subreddit={subreddit!r}")

    # TODO: Replace with actual AI analysis
    return jsonify({"credibility_score": 75, "status": "analyzed"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
