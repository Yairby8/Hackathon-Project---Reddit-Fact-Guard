// Reddit Trust & Safety - Content Script

(function () {
  "use strict";

  const BACKEND_URL = "http://localhost:8000/analyze";

  /**
   * Scrape basic post data from the current Reddit page.
   * Supports both old and new Reddit layouts.
   */
  function scrapePostData() {
    let title = "";
    let author = "";
    let subreddit = "";

    // Try new Reddit (sh- prefixed elements or data attributes)
    const titleEl =
      document.querySelector("h1") ||
      document.querySelector('[data-testid="post-title"]') ||
      document.querySelector(".Post h3");

    if (titleEl) {
      title = titleEl.textContent.trim();
    }

    // Extract subreddit from URL
    const urlMatch = window.location.pathname.match(/\/r\/([^/]+)/);
    if (urlMatch) {
      subreddit = urlMatch[1];
    }

    // Extract author - try multiple selectors
    const authorEl =
      document.querySelector('[data-testid="post_author_link"]') ||
      document.querySelector('a[href*="/user/"]') ||
      document.querySelector(".author");

    if (authorEl) {
      author = authorEl.textContent.trim().replace(/^u\//, "");
    }

    return { title, author, subreddit };
  }

  /**
   * Create and inject the trust widget into the page.
   */
  function injectWidget(postData) {
    // Remove existing widget if present
    const existing = document.getElementById("reddit-trust-widget");
    if (existing) existing.remove();

    const widget = document.createElement("div");
    widget.id = "reddit-trust-widget";
    widget.innerHTML = `
      <h3>🛡️ Trust & Safety</h3>
      <div class="widget-row">
        <span class="widget-label">Author</span>
        <span class="widget-value">${postData.author || "Unknown"}</span>
      </div>
      <div class="widget-row">
        <span class="widget-label">Subreddit</span>
        <span class="widget-value">r/${postData.subreddit || "Unknown"}</span>
      </div>
      <div class="score-container">
        <div class="score-value" id="trust-score">--</div>
        <div class="score-label">Credibility Score</div>
      </div>
      <div class="status loading" id="trust-status">Analyzing...</div>
    `;

    document.body.appendChild(widget);
  }

  /**
   * Send scraped data to the backend for analysis.
   */
  async function analyzePost(postData) {
    try {
      const response = await fetch(BACKEND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(postData),
      });

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`);
      }

      const result = await response.json();
      updateWidget(result);
    } catch (error) {
      console.error("[Reddit Trust & Safety] Analysis failed:", error);
      const statusEl = document.getElementById("trust-status");
      if (statusEl) {
        statusEl.textContent = "Backend unavailable - is the server running?";
        statusEl.className = "status error";
      }
    }
  }

  /**
   * Update the widget with the backend response.
   */
  function updateWidget(result) {
    const scoreEl = document.getElementById("trust-score");
    const statusEl = document.getElementById("trust-status");

    if (scoreEl) {
      scoreEl.textContent = result.credibility_score;

      // Color code the score
      const score = result.credibility_score;
      if (score >= 70) scoreEl.style.color = "#4caf50";
      else if (score >= 40) scoreEl.style.color = "#ffc107";
      else scoreEl.style.color = "#f44336";
    }

    if (statusEl) {
      statusEl.textContent = `Status: ${result.status}`;
      statusEl.className = "status";
    }
  }

  // --- Main Execution ---

  // Wait a moment for Reddit's dynamic content to load
  setTimeout(() => {
    const postData = scrapePostData();

    // Only inject if we're on a post page (has title or subreddit)
    if (postData.title || postData.subreddit) {
      injectWidget(postData);
      analyzePost(postData);
    }
  }, 1500);
})();
