# Reddit Trust & Safety - Chrome Extension

A Chrome extension + Python backend that analyzes Reddit post credibility.

## Project Structure

```
hakaton/
├── extension/          # Chrome Extension (Manifest V3)
│   ├── manifest.json
│   ├── content.js
│   └── widget.css
├── backend/            # Python Backend (FastAPI)
│   ├── server.py
│   └── requirements.txt
└── README.md
```

## Setup & Running

### 1. Backend (Python)

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload
```

The server will start at `http://localhost:8000`.  
You can verify it's running by visiting `http://localhost:8000/health`.

### 2. Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` folder from this project
5. Navigate to any Reddit post — the trust widget will appear in the top-right corner

## How It Works

1. The content script (`content.js`) runs on Reddit pages
2. It scrapes the post title, author, and subreddit
3. A widget is injected into the page showing the author info
4. The extension sends the data to the backend (`POST /analyze`)
5. The backend returns a credibility score (currently a dummy value of 75)
6. The widget updates with the score

## Next Steps

- [ ] Implement real AI credibility analysis in `server.py`
- [ ] Add account age / karma checks via Reddit API
- [ ] Analyze post history patterns
- [ ] Add sentiment analysis on post content
- [ ] Improve scraping for different Reddit layouts
