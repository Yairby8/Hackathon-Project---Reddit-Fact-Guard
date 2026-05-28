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
      <h3>🛡️ Reddit FactGuard</h3>
      <div class="widget-row">
        <span class="widget-label">Post</span>
        <span class="widget-value" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${postData.title || ""}">${postData.title || "Unknown"}</span>
      </div>
      <div class="widget-row">
        <span class="widget-label">Author</span>
        <span class="widget-value">${postData.author || "Unknown"}</span>
      </div>
      <div class="widget-row">
        <span class="widget-label">Subreddit</span>
        <span class="widget-value">r/${postData.subreddit || "Unknown"}</span>
      </div>
      <div class="score-container">
        <div class="spinner" id="trust-spinner">
          <div class="ring-wrapper">
            <div class="ring outer"></div>
            <div class="ring middle"></div>
            <div class="ring inner"></div>
          </div>
          <div class="thinking-text">Evaluating trustworthiness...</div>
        </div>
        <div class="score-value" id="trust-score" style="display:none;">--</div>
        <div class="score-label" id="trust-score-label" style="display:none;">Credibility Score</div>
      </div>
      <div class="status loading" id="trust-status">Analyzing...</div>
    `;

    document.body.appendChild(widget);
  }

  /**
   * Send scraped data to the backend for analysis.
   */
  async function analyzePost(postData) {
    const startTime = Date.now();
    const MIN_SPINNER_TIME = 2500; // Let the spinner show for at least 2.5 seconds

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

      // Wait remaining time so the spinner is visible long enough
      const elapsed = Date.now() - startTime;
      const remaining = MIN_SPINNER_TIME - elapsed;
      if (remaining > 0) {
        await new Promise((resolve) => setTimeout(resolve, remaining));
      }

      updateWidget(result);
    } catch (error) {
      console.error("[Reddit Trust & Safety] Analysis failed:", error);

      const elapsed = Date.now() - startTime;
      const remaining = MIN_SPINNER_TIME - elapsed;
      if (remaining > 0) {
        await new Promise((resolve) => setTimeout(resolve, remaining));
      }

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
    const spinner = document.getElementById("trust-spinner");
    const scoreEl = document.getElementById("trust-score");
    const labelEl = document.getElementById("trust-score-label");
    const statusEl = document.getElementById("trust-status");

    // Trigger collapse animation on the rings
    if (spinner) spinner.classList.add("collapsing");

    // After rings collapse, reveal the score in their place
    setTimeout(() => {
      if (spinner) spinner.style.display = "none";
      if (scoreEl) scoreEl.style.display = "block";
      if (labelEl) labelEl.style.display = "block";

      if (scoreEl) {
        const target = result.credibility_score;
        let current = 0;
        const duration = 800;
        const steps = 30;
        const increment = target / steps;
        const interval = duration / steps;

        // Pop-in effect
        setTimeout(() => scoreEl.classList.add("revealed"), 50);

        const counter = setInterval(() => {
          current += increment;
          if (current >= target) {
            current = target;
            clearInterval(counter);
          }
          scoreEl.textContent = Math.round(current);
        }, interval);

        // Color code the score
        if (target >= 70) scoreEl.style.color = "#4caf50";
        else if (target >= 40) scoreEl.style.color = "#ffc107";
        else scoreEl.style.color = "#f44336";
      }

      if (statusEl) {
        statusEl.textContent = `Status: ${result.status}`;
        statusEl.className = "status";
      }
    }, 500); // Wait for collapse animation to finish
  }

  // --- Main Execution ---

  let lastUrl = "";

  /**
   * Run the scrape + analyze cycle if the URL has changed.
   */
  function runAnalysis() {
    const currentUrl = window.location.href;
    if (currentUrl === lastUrl) return;
    lastUrl = currentUrl;

    console.log("[Reddit Trust & Safety] Navigated to:", currentUrl);

    // Give Reddit a moment to render the new post content
    setTimeout(() => {
      const postData = scrapePostData();
      console.log("[Reddit Trust & Safety] Scraped data:", postData);

      if (postData.title || postData.subreddit || postData.author) {
        injectWidget(postData);
        analyzePost(postData);
      } else {
        // Remove widget if we navigated away from a post
        const existing = document.getElementById("reddit-trust-widget");
        if (existing) existing.remove();
      }
    }, 1500);
  }

  // Detect SPA navigation by observing URL changes
  // 1. Listen for popstate (back/forward buttons)
  window.addEventListener("popstate", runAnalysis);

  // 2. Patch pushState/replaceState to detect programmatic navigation
  const originalPushState = history.pushState;
  history.pushState = function (...args) {
    originalPushState.apply(this, args);
    runAnalysis();
  };

  const originalReplaceState = history.replaceState;
  history.replaceState = function (...args) {
    originalReplaceState.apply(this, args);
    runAnalysis();
  };

  // 3. Fallback: poll for URL changes (catches edge cases)
  setInterval(runAnalysis, 2000);

  // Initial run
  runAnalysis();
})();
