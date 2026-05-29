// Reddit Fact Guard - Content Script (Full Pipeline)

(function () {
  "use strict";

  const BACKEND_URL = "http://localhost:8000/analyze";

  // --- Scraping ---

  function scrapePostData() {
    let title = "";
    let author = "";
    let subreddit = "";
    let body = "";
    let imageUrl = "";

    const shredditPost = document.querySelector("shreddit-post");
    if (shredditPost) {
      title = shredditPost.getAttribute("post-title") || "";
      author = shredditPost.getAttribute("author") || "";
      subreddit = shredditPost.getAttribute("subreddit-prefixed-name") || "";
    }

    if (!title) {
      const titleEl = document.querySelector("h1") ||
        document.querySelector('[data-testid="post-title"]');
      if (titleEl) title = titleEl.textContent.trim();
    }

    if (!subreddit) {
      const match = window.location.pathname.match(/\/r\/([^/]+)/);
      if (match) subreddit = `r/${match[1]}`;
    }

    if (!author) {
      const authorEl = document.querySelector('[data-testid="post_author_link"]') ||
        document.querySelector(".top-matter .author") ||
        document.querySelector('a[href*="/user/"]');
      if (authorEl) author = authorEl.textContent.trim().replace(/^u\//, "");
    }

    body = scrapePostBody();
    imageUrl = scrapePostImage();
    const comments = scrapeStructuredComments();

    return { title, author, subreddit, body, imageUrl, comments, url: window.location.href };
  }

  function scrapePostBody() {
    const selectors = [
      '[slot="text-body"]',
      '[data-click-id="text"] .md',
      ".Post .RichTextJSON-root",
      ".expando .md",
      'div[data-test-id="post-content"]',
    ];

    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.textContent.trim()) {
        return el.textContent.trim().slice(0, 3000);
      }
    }
    return "";
  }

  function scrapeStructuredComments() {
    const results = [];

    // New Reddit
    const shredditComments = document.querySelectorAll("shreddit-comment");
    if (shredditComments.length > 0) {
      shredditComments.forEach((el, i) => {
        if (i >= 30) return;
        const author = el.getAttribute("author") || "";
        const thingId = el.getAttribute("thingid") || `c_${i}`;
        const parentId = el.getAttribute("parentid") || "";

        let text = "";
        const contentEl = el.querySelector('[slot="comment"]');
        if (contentEl) {
          text = contentEl.textContent.trim();
        } else {
          const pEls = el.querySelectorAll("p");
          if (pEls.length > 0) {
            text = Array.from(pEls).map(p => p.textContent.trim()).join(" ");
          }
        }

        if (text && text.length > 3) {
          results.push({ id: thingId, parent_id: parentId, author, text: text.slice(0, 500) });
        }
      });
    }

    // Old Reddit fallback
    if (results.length === 0) {
      const oldComments = document.querySelectorAll('.comment, [id^="t1_"]');
      oldComments.forEach((el, i) => {
        if (i >= 30) return;
        const authorEl = el.querySelector(".author");
        const bodyEl = el.querySelector(".md, p");
        const author = authorEl ? authorEl.textContent.trim() : "";
        const text = bodyEl ? bodyEl.textContent.trim() : "";
        if (text && text.length > 3) {
          results.push({ id: el.id || `c_${i}`, parent_id: "", author, text: text.slice(0, 500) });
        }
      });
    }

    return results;
  }

  function scrapePostImage() {
    const selectors = [
      'shreddit-post img[src*="i.redd.it"]',
      'shreddit-post img[src*="preview.redd.it"]',
      'shreddit-post img[src*="external-preview"]',
      '[data-click-id="body"] img',
      '.Post img[src*="i.redd.it"]',
      'img[alt="Post image"]',
      'div[slot="post-media-container"] img',
    ];

    for (const sel of selectors) {
      const img = document.querySelector(sel);
      if (img && img.src && !img.src.includes("avatar") && !img.src.includes("icon")) {
        return img.src;
      }
    }

    const ogImage = document.querySelector('meta[property="og:image"]');
    if (ogImage && ogImage.content && !ogImage.content.includes("default")) {
      return ogImage.content;
    }
    return "";
  }

  // --- Backend Communication ---

  async function analyzePost(postData) {
    try {
      const response = await fetch(BACKEND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(postData),
      });
      if (!response.ok) throw new Error(`Server responded with ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error("[FactGuard] Backend error:", error);
      return null;
    }
  }

  // --- UI Widget ---

  function createWidget(postData) {
    const existing = document.getElementById("reddit-trust-widget");
    if (existing) existing.remove();

    const widget = document.createElement("div");
    widget.id = "reddit-trust-widget";

    const imageIndicator = postData.imageUrl
      ? '<span style="color:#4ade80;font-size:11px;">📷 Image detected</span>'
      : '<span style="color:#666;font-size:11px;">No image</span>';

    const commentCount = postData.comments ? postData.comments.length : 0;

    widget.innerHTML = `
      <h3>🛡️ Reddit Fact Guard</h3>
      <div class="divider"></div>
      <div class="widget-row">
        <span class="widget-label">Post</span>
        <span class="widget-value" title="${escapeHtml(postData.title)}">${escapeHtml(postData.title || "Untitled")}</span>
      </div>
      <div class="widget-row">
        <span class="widget-label">Author</span>
        <span class="widget-value">${escapeHtml(postData.author || "Unknown")}</span>
      </div>
      <div class="widget-row">
        <span class="widget-label">Subreddit</span>
        <span class="widget-value">${escapeHtml(postData.subreddit || "Unknown")}</span>
      </div>
      <div class="widget-row">
        <span class="widget-label">Media</span>
        <span class="widget-value">${imageIndicator}</span>
      </div>
      <div class="widget-row">
        <span class="widget-label">Comments</span>
        <span class="widget-value">${commentCount} analyzed</span>
      </div>
      <div class="loading-container" id="trust-loading">
        <div class="spinner-wrapper">
          <div class="spinner-glow"></div>
          <div class="spinner"></div>
        </div>
        <div class="loading-text">AI + heuristic analysis running...</div>
      </div>
      <div id="trust-result" style="display:none;">
        <div class="score-container">
          <div class="score" id="trust-score"></div>
          <div class="verdict" id="trust-verdict"></div>
          <div class="score-label">Credibility Score</div>
        </div>
        <div class="reasoning" id="trust-reasoning"></div>
        <div class="flags-container" id="trust-flags"></div>
      </div>
      <div class="status" id="trust-status" style="display:none;"></div>
    `;

    document.body.appendChild(widget);
  }

  function updateWidget(result) {
    const loadingEl = document.getElementById("trust-loading");
    const resultEl = document.getElementById("trust-result");
    const scoreEl = document.getElementById("trust-score");
    const verdictEl = document.getElementById("trust-verdict");
    const reasoningEl = document.getElementById("trust-reasoning");
    const flagsEl = document.getElementById("trust-flags");
    const statusEl = document.getElementById("trust-status");

    if (!loadingEl || !resultEl || !scoreEl) return;

    loadingEl.style.display = "none";
    resultEl.style.display = "block";
    statusEl.style.display = "block";

    if (result) {
      const score = result.credibility_score;
      scoreEl.textContent = `${score}/100`;

      if (score >= 70) scoreEl.className = "score high";
      else if (score >= 40) scoreEl.className = "score medium";
      else scoreEl.className = "score low";

      if (verdictEl && result.verdict) {
        verdictEl.textContent = result.verdict;
        verdictEl.className = `verdict ${score >= 70 ? "high" : score >= 40 ? "medium" : "low"}`;
      }

      if (reasoningEl) {
        reasoningEl.textContent = result.reasoning || "No additional details.";
        reasoningEl.style.display = "block";
      }

      if (flagsEl && result.flags && result.flags.length > 0) {
        flagsEl.innerHTML = result.flags
          .map((flag) => `<span class="flag">${escapeHtml(flag)}</span>`)
          .join("");
      }

      statusEl.textContent = "✓ Multi-signal analysis complete";
    } else {
      scoreEl.textContent = "—";
      scoreEl.className = "score";
      statusEl.textContent = "⚠ Backend unavailable";
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // --- Main ---

  async function main() {
    if (!window.location.pathname.match(/\/r\/[^/]+\/comments\//)) {
      const existing = document.getElementById("reddit-trust-widget");
      if (existing) existing.remove();
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 1200));

    const postData = scrapePostData();
    if (!postData.title && !postData.author) return;

    createWidget(postData);

    const result = await analyzePost(postData);
    updateWidget(result);
  }

  main();

  // SPA navigation support
  let lastUrl = location.href;
  const observer = new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      const existing = document.getElementById("reddit-trust-widget");
      if (existing) existing.remove();
      setTimeout(main, 800);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  window.addEventListener("popstate", () => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      const existing = document.getElementById("reddit-trust-widget");
      if (existing) existing.remove();
      setTimeout(main, 800);
    }
  });

  document.addEventListener("click", (e) => {
    const link = e.target.closest('a[href*="/comments/"]');
    if (link) {
      setTimeout(() => {
        if (location.href !== lastUrl) {
          lastUrl = location.href;
          const existing = document.getElementById("reddit-trust-widget");
          if (existing) existing.remove();
          setTimeout(main, 800);
        }
      }, 300);
    }
  }, true);
})();
