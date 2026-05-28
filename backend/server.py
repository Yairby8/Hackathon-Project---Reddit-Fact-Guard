"""
Reddit Trust & Safety - Backend Server
Run with: uvicorn server:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Reddit Trust & Safety API")

# Allow requests from the Chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PostData(BaseModel):
    title: str = ""
    author: str = ""
    subreddit: str = ""


class AnalysisResult(BaseModel):
    credibility_score: int
    status: str


@app.post("/analyze", response_model=AnalysisResult)
async def analyze_post(post: PostData):
    """
    Analyze a Reddit post for credibility.
    Currently returns a dummy score - replace with real AI logic later.
    """
    print(f"[Analyze] title={post.title!r}, author={post.author!r}, subreddit={post.subreddit!r}")

    # TODO: Replace with actual AI analysis
    return AnalysisResult(credibility_score=75, status="analyzed")


@app.get("/health")
async def health():
    return {"status": "ok"}
