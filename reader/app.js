(() => {
  "use strict";

  const STORAGE_KEY = "quant-learning-reader-v1";
  const $ = (selector) => document.querySelector(selector);
  const els = {
    nav: $("#chapter-nav"),
    search: $("#search-input"),
    searchStatus: $("#search-status"),
    loading: $("#loading-state"),
    home: $("#home-view"),
    chapter: $("#chapter-view"),
    reader: $("#reader-scroll"),
    article: $("#markdown-body"),
    breadcrumb: $("#breadcrumb-title"),
    group: $("#chapter-group"),
    time: $("#chapter-reading-time"),
    sectionIndex: $("#section-index"),
    itemCount: $("#item-count"),
    chapterProgress: $("#chapter-progress"),
    overallLabel: $("#overall-progress-label"),
    overallBar: $("#overall-progress-bar"),
    overallCopy: $("#overall-progress-copy"),
    bookmark: $("#bookmark-button"),
    complete: $("#complete-button"),
    previous: $("#previous-button"),
    next: $("#next-button"),
    pathGrid: $("#path-grid"),
    mobileBackdrop: $("#mobile-backdrop"),
    sidebar: $("#sidebar"),
  };

  let documents = [];
  let byPath = new Map();
  let current = null;
  let saveTimer = 0;
  let searchTerm = "";

  function freshState() {
    return { lastPath: "", bookmarks: [], completed: [], positions: {}, theme: "light", font: 1 };
  }

  function readState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return { ...freshState(), ...saved };
    } catch {
      return freshState();
    }
  }

  const state = readState();

  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch { /* Private browsing can disable storage. */ }
  }

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  }

  function displayNumber(index) {
    return String(index + 1).padStart(2, "0");
  }

  function renderOverallProgress() {
    const completed = state.completed.filter((path) => byPath.has(path)).length;
    const percent = documents.length ? Math.round(completed / documents.length * 100) : 0;
    els.overallLabel.textContent = `${percent}%`;
    els.overallBar.style.width = `${percent}%`;
    els.overallCopy.textContent = completed
      ? `已读 ${completed} / ${documents.length} 篇 · 进度保存在当前设备`
      : "开始阅读，记录会保存在这台设备上";
  }

  function chapterButton(doc, index) {
    const isActive = current?.path === doc.path;
    const isBookmarked = state.bookmarks.includes(doc.path);
    const isComplete = state.completed.includes(doc.path);
    return `<button class="chapter-link${isActive ? " is-active" : ""}" data-path="${escapeHTML(doc.path)}" aria-current="${isActive ? "page" : "false"}">
      <span class="chapter-number">${displayNumber(index)}</span>
      <span class="chapter-label">${escapeHTML(doc.title)}</span>
      <span class="chapter-state" aria-label="${isComplete ? "已读" : isBookmarked ? "已加入书签" : ""}">${isComplete ? "✓" : isBookmarked ? "☆" : ""}</span>
    </button>`;
  }

  function renderNavigation() {
    const query = searchTerm.trim().toLocaleLowerCase();
    const matches = documents.filter((doc) => {
      if (!query) return true;
      return doc.title.toLocaleLowerCase().includes(query)
        || doc.content.toLocaleLowerCase().includes(query)
        || doc.group.toLocaleLowerCase().includes(query);
    });
    const indexByPath = new Map(documents.map((doc, index) => [doc.path, index]));
    let html = "";

    if (!query && state.bookmarks.length) {
      const saved = state.bookmarks.map((path) => byPath.get(path)).filter(Boolean);
      if (saved.length) {
        html += `<div class="nav-group bookmark-group"><div class="nav-heading"><span>我的书签</span><span class="nav-count">${saved.length}</span></div>${saved.map((doc) => chapterButton(doc, indexByPath.get(doc.path))).join("")}</div>`;
      }
    }

    const groups = [...new Set(documents.map((doc) => doc.group))];
    for (const group of groups) {
      const items = matches.filter((doc) => doc.group === group);
      if (!items.length) continue;
      html += `<div class="nav-group"><div class="nav-heading"><span>${escapeHTML(group)}</span><span class="nav-count">${items.length}</span></div>${items.map((doc) => chapterButton(doc, indexByPath.get(doc.path))).join("")}</div>`;
    }

    els.nav.innerHTML = html || `<div class="empty-search"><span>⌕</span><strong>没有找到匹配内容</strong><small>试试更短的关键词</small></div>`;
    els.itemCount.textContent = query ? `${matches.length}/${documents.length}` : documents.length;
    els.searchStatus.textContent = query ? `在 ${documents.length} 篇材料中找到 ${matches.length} 篇` : "";
    renderOverallProgress();
  }

  function renderHome() {
    const groups = [...new Set(documents.map((doc) => doc.group))];
    const summaries = {
      "起步导览": "补上量化 Python 与数学统计，先把研究语言读顺。",
      "第一阶段 · 传统量化研究": "从研究假设、数据和因子，走到单因子评价与组合。",
      "第二阶段 · 机器学习": "以传统因子为参照，扩展到模型、验证与研究复现。",
      "附录与研究模板": "随读随用的研究卡片、审计清单与规则说明。",
    };
    els.pathGrid.innerHTML = groups.map((group, index) => {
      const items = documents.filter((doc) => doc.group === group);
      const first = items[0];
      return `<button class="path-card" data-path="${escapeHTML(first.path)}">
        <span class="path-card-top"><span class="path-index">0${index + 1}</span><span class="path-arrow" aria-hidden="true">↗</span></span>
        <strong>${escapeHTML(group)}</strong>
        <span class="path-description">${escapeHTML(summaries[group] || "按章节阅读，并随手记录研究问题。")}</span>
        <span class="path-card-foot"><span>${items.length} 篇材料</span><span>${escapeHTML(first.title)} →</span></span>
      </button>`;
    }).join("");

    const totalMinutes = documents.reduce((sum, doc) => sum + Number(doc.minutes || 1), 0);
    $("#home-chapter-count").textContent = documents.length;
    $("#home-reading-time").textContent = totalMinutes;
    $("#resume-button").textContent = state.lastPath && byPath.has(state.lastPath) ? "从上次位置继续　→" : "从第一篇开始阅读　→";
  }

  function setRoute(path, replace = false, section = "") {
    const url = new URL(location.href);
    if (path) url.searchParams.set("chapter", path);
    else url.searchParams.delete("chapter");
    url.hash = section ? `#${encodeURIComponent(section)}` : "";
    if (replace) history.replaceState({ path }, "", url);
    else history.pushState({ path }, "", url);
  }

  function slugify(text, index) {
    const slug = text.toLocaleLowerCase().trim()
      .normalize("NFKC")
      .replace(/[^\p{L}\p{N}_ -]/gu, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 64);
    return slug || `section-${index + 1}`;
  }

  function normalizeMarkdownLink(anchor, doc) {
    const href = anchor.getAttribute("href") || "";
    if (!href || href.startsWith("#") || /^(mailto:|tel:|data:)/i.test(href)) return;
    if (/^https?:\/\//i.test(href) || href.startsWith("//")) {
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
      return;
    }
    try {
      const encodedPath = doc.path.split("/").map(encodeURIComponent).join("/");
      const source = new URL(`https://github.com/2514-nzk/quant-learning/blob/master/${encodedPath}`);
      const target = new URL(href, source);
      const prefix = "/2514-nzk/quant-learning/blob/master/";
      if (target.hostname !== "github.com" || !target.pathname.startsWith(prefix)) return;
      const path = decodeURIComponent(target.pathname.slice(prefix.length));
      if (byPath.has(path)) {
        anchor.href = `?chapter=${encodeURIComponent(path)}${target.hash || ""}`;
        anchor.classList.add("reader-internal-link");
        return;
      }
      anchor.href = `https://github.com/2514-nzk/quant-learning/blob/master/${path.split("/").map(encodeURIComponent).join("/")}`;
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
    } catch { /* Keep unparseable links as supplied. */ }
  }

  function renderArticle(doc) {
    if (!window.marked || !window.DOMPurify) {
      els.article.innerHTML = `<p class="reader-error">正文解析组件没有加载成功。请刷新页面，或检查当前网络是否可以访问 jsDelivr。</p><pre>${escapeHTML(doc.content)}</pre>`;
      els.sectionIndex.hidden = true;
      return;
    }
    const raw = window.marked.parse(doc.content, { gfm: true, breaks: false });
    const wrapper = document.createElement("div");
    wrapper.innerHTML = window.DOMPurify.sanitize(raw);
    wrapper.querySelectorAll("a[href]").forEach((anchor) => normalizeMarkdownLink(anchor, doc));
    wrapper.querySelectorAll("img[src]").forEach((image) => {
      const src = image.getAttribute("src") || "";
      if (!/^(https?:|data:|\/\/)/i.test(src)) {
        const encodedPath = doc.path.split("/").map(encodeURIComponent).join("/");
        try {
          image.src = new URL(src, `https://raw.githubusercontent.com/2514-nzk/quant-learning/master/${encodedPath}`).href;
        } catch { /* Keep the original source on malformed paths. */ }
      }
      image.loading = "lazy";
    });

    const headings = [...wrapper.querySelectorAll("h2, h3")];
    const slugCounts = new Map();
    const sections = headings.map((heading, index) => {
      const baseSlug = slugify(heading.textContent || "", index);
      const duplicate = slugCounts.get(baseSlug) || 0;
      slugCounts.set(baseSlug, duplicate + 1);
      heading.id = duplicate ? `${baseSlug}-${duplicate}` : baseSlug;
      return { id: heading.id, title: heading.textContent || "", level: heading.tagName.toLowerCase() };
    });
    const headingBySlug = new Map(sections.map((section) => [section.id, section.id]));
    headings.forEach((heading, index) => headingBySlug.set(slugify(heading.textContent || "", index), heading.id));
    wrapper.querySelectorAll('a[href^="#"]').forEach((anchor) => {
      let fragment = anchor.getAttribute("href").slice(1);
      try { fragment = decodeURIComponent(fragment); } catch { /* Keep the supplied fragment. */ }
      if (headingBySlug.has(fragment)) anchor.setAttribute("href", `#${headingBySlug.get(fragment)}`);
    });
    els.article.replaceChildren(...wrapper.childNodes);
    if (sections.length) {
      els.sectionIndex.innerHTML = `<div class="section-index-label">本章目录</div><div class="section-index-links">${sections.map((section) => `<a class="${section.level}" href="#${section.id}">${escapeHTML(section.title)}</a>`).join("")}</div>`;
      els.sectionIndex.hidden = false;
    } else {
      els.sectionIndex.hidden = true;
    }
  }

  function updateChapterActions() {
    if (!current) return;
    const bookmarked = state.bookmarks.includes(current.path);
    const completed = state.completed.includes(current.path);
    els.bookmark.classList.toggle("is-selected", bookmarked);
    els.bookmark.innerHTML = `<span aria-hidden="true">${bookmarked ? "★" : "☆"}</span><span>${bookmarked ? "已收藏" : "书签"}</span>`;
    els.complete.classList.toggle("is-selected", completed);
    els.complete.innerHTML = `<span aria-hidden="true">${completed ? "✓" : "○"}</span><span>${completed ? "已读" : "标记已读"}</span>`;
  }

  function updatePager(index) {
    const previous = documents[index - 1];
    const next = documents[index + 1];
    els.previous.disabled = !previous;
    els.previous.querySelector("strong").textContent = previous?.title || "已是第一篇";
    els.next.disabled = !next;
    els.next.querySelector("strong").textContent = next?.title || "已到最后一篇";
    els.previous.dataset.path = previous?.path || "";
    els.next.dataset.path = next?.path || "";
  }

  function updateReadingProgress() {
    if (!current) return;
    const index = documents.findIndex((doc) => doc.path === current.path);
    const maximum = Math.max(0, els.reader.scrollHeight - els.reader.clientHeight);
    const percent = maximum ? Math.min(100, Math.round(els.reader.scrollTop / maximum * 100)) : 0;
    els.chapterProgress.textContent = `${displayNumber(index)} / ${String(documents.length).padStart(2, "0")}　·　${percent}%`;
    state.positions[current.path] = els.reader.scrollTop;
    if (maximum > 0 && percent >= 92 && !state.completed.includes(current.path)) {
      state.completed.push(current.path);
      updateChapterActions();
      renderNavigation();
    }
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveState, 400);
  }

  function showChapter(path, { route = true, replace = false, restore = true, section = "" } = {}) {
    const doc = byPath.get(path);
    if (!doc) return showHome({ route: false });
    current = doc;
    const index = documents.indexOf(doc);
    els.home.hidden = true;
    els.chapter.hidden = false;
    els.breadcrumb.textContent = doc.title;
    els.group.textContent = doc.group;
    els.time.textContent = `${doc.minutes} 分钟阅读`;
    renderArticle(doc);
    updateChapterActions();
    updatePager(index);
    renderNavigation();
    if (route) setRoute(doc.path, replace, section);
    state.lastPath = doc.path;
    saveState();
    closeMobileMenu();
    requestAnimationFrame(() => {
      const sectionTarget = section ? document.getElementById(section) : null;
      if (sectionTarget) sectionTarget.scrollIntoView({ block: "start" });
      else els.reader.scrollTop = restore ? Number(state.positions[doc.path] || 0) : 0;
      updateReadingProgress();
    });
  }

  function showHome({ route = true } = {}) {
    current = null;
    els.chapter.hidden = true;
    els.home.hidden = false;
    els.breadcrumb.textContent = "量化入门";
    els.chapterProgress.textContent = "";
    els.reader.scrollTop = 0;
    renderHome();
    renderNavigation();
    if (route) setRoute("");
    closeMobileMenu();
  }

  function toggleBookmark() {
    if (!current) return;
    if (state.bookmarks.includes(current.path)) state.bookmarks = state.bookmarks.filter((path) => path !== current.path);
    else state.bookmarks.push(current.path);
    saveState();
    updateChapterActions();
    renderNavigation();
  }

  function toggleComplete() {
    if (!current) return;
    if (state.completed.includes(current.path)) state.completed = state.completed.filter((path) => path !== current.path);
    else state.completed.push(current.path);
    saveState();
    updateChapterActions();
    renderNavigation();
  }

  function openMobileMenu() {
    els.sidebar.classList.add("is-open");
    els.mobileBackdrop.classList.add("is-visible");
    document.body.classList.add("menu-open");
  }

  function closeMobileMenu() {
    els.sidebar.classList.remove("is-open");
    els.mobileBackdrop.classList.remove("is-visible");
    document.body.classList.remove("menu-open");
  }

  function applyAppearance() {
    document.documentElement.dataset.theme = state.theme === "dark" ? "dark" : "light";
    document.documentElement.style.setProperty("--reader-scale", String(state.font));
    $("#theme-button").textContent = state.theme === "dark" ? "☼" : "◐";
    $("#theme-button").setAttribute("aria-label", state.theme === "dark" ? "切换到浅色主题" : "切换到深色主题");
  }

  async function init() {
    try {
      const response = await fetch(new URL("content.json", document.baseURI));
      if (!response.ok) throw new Error(`内容读取失败 (${response.status})`);
      const payload = await response.json();
      documents = payload.documents || [];
      byPath = new Map(documents.map((doc) => [doc.path, doc]));
      state.bookmarks = state.bookmarks.filter((path) => byPath.has(path));
      state.completed = state.completed.filter((path) => byPath.has(path));
      $("#home-chapter-count").textContent = documents.length;
      renderHome();
      renderNavigation();
      applyAppearance();
      els.loading.hidden = true;
      const queryPath = new URLSearchParams(location.search).get("chapter");
      if (queryPath && byPath.has(queryPath)) showChapter(queryPath, { route: false, restore: true, section: decodeURIComponent(location.hash.slice(1)) });
      else showHome({ route: false });
    } catch (error) {
      els.loading.innerHTML = `<span class="loading-error">${escapeHTML(error.message || "加载失败")}</span><button class="retry-button" onclick="location.reload()">重新加载</button>`;
    }
  }

  els.nav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-path]");
    if (button) showChapter(button.dataset.path);
  });
  els.pathGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-path]");
    if (button) showChapter(button.dataset.path, { restore: false });
  });
  els.search.addEventListener("input", () => {
    searchTerm = els.search.value;
    renderNavigation();
  });
  $("#resume-button").addEventListener("click", () => {
    const path = state.lastPath && byPath.has(state.lastPath) ? state.lastPath : documents[0]?.path;
    if (path) showChapter(path);
  });
  $("#start-button").addEventListener("click", () => {
    if (documents[0]) showChapter(documents[0].path, { restore: false });
  });
  els.bookmark.addEventListener("click", toggleBookmark);
  els.complete.addEventListener("click", toggleComplete);
  els.previous.addEventListener("click", () => { if (els.previous.dataset.path) showChapter(els.previous.dataset.path, { restore: false }); });
  els.next.addEventListener("click", () => { if (els.next.dataset.path) showChapter(els.next.dataset.path, { restore: false }); });
  $("#font-down").addEventListener("click", () => { state.font = Math.max(0.88, +(state.font - 0.06).toFixed(2)); applyAppearance(); saveState(); });
  $("#font-up").addEventListener("click", () => { state.font = Math.min(1.3, +(state.font + 0.06).toFixed(2)); applyAppearance(); saveState(); });
  $("#theme-button").addEventListener("click", () => { state.theme = state.theme === "dark" ? "light" : "dark"; applyAppearance(); saveState(); });
  $("#menu-button").addEventListener("click", openMobileMenu);
  els.mobileBackdrop.addEventListener("click", closeMobileMenu);
  els.reader.addEventListener("scroll", updateReadingProgress, { passive: true });
  els.article.addEventListener("click", (event) => {
    const anchor = event.target.closest("a.reader-internal-link");
    if (!anchor) return;
    const targetURL = new URL(anchor.href, location.href);
    const path = targetURL.searchParams.get("chapter");
    if (!path || !byPath.has(path)) return;
    event.preventDefault();
    let section = targetURL.hash.slice(1);
    try { section = decodeURIComponent(section); } catch { /* Keep the supplied fragment. */ }
    showChapter(path, { restore: false, section });
  });
  window.addEventListener("popstate", () => {
    const path = new URLSearchParams(location.search).get("chapter");
    if (path && byPath.has(path)) {
      let section = location.hash.slice(1);
      try { section = decodeURIComponent(section); } catch { /* Keep the supplied fragment. */ }
      showChapter(path, { route: false, restore: true, section });
    }
    else showHome({ route: false });
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      els.search.focus();
      els.search.select();
    } else if (event.key === "Escape") {
      els.search.blur();
      closeMobileMenu();
    }
  });

  init();
})();
