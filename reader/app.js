(() => {
  "use strict";

  const STORAGE_KEY = "quant-learning-reader-v1";
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  const $ = (selector) => document.querySelector(selector);
  const els = {
    nav: $("#chapter-nav"),
    search: $("#search-input"),
    searchClear: $("#search-clear"),
    readingProgress: $("#reading-progress-track"),
    readingProgressBar: $("#reading-progress-bar"),
    backToTop: $("#back-to-top"),
    menuButton: $("#menu-button"),
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
    secondVolumeCopy: $("#second-volume-progress-copy"),
    manageProgress: $("#manage-progress-button"),
    resetDialog: $("#reset-progress-dialog"),
    resetBookmarks: $("#reset-bookmarks-checkbox"),
    resetCancel: $("#cancel-progress-reset"),
    resetConfirm: $("#confirm-progress-reset"),
    resetNotice: $("#reset-notice"),
    bookmark: $("#bookmark-button"),
    complete: $("#complete-button"),
    previous: $("#previous-button"),
    next: $("#next-button"),
    pathGrid: $("#path-grid"),
    mobileBackdrop: $("#mobile-backdrop"),
    sidebar: $("#sidebar"),
  };

  let documents = [];
  let readingRoute = [];
  let firstVolume = [];
  let secondVolume = [];
  let thirdVolume = [];
  let byPath = new Map();
  let current = null;
  let saveTimer = 0;
  let navigationId = 0;
  let restoringPosition = false;
  let searchTerm = "";
  let mainChapterCount = 0;
  let labs = {};
  let pyWorker = null;
  let labRequestId = 0;
  const labPending = new Map();
  const textCache = new Map();

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

  function renderOverallProgress() {
    const completed = readingRoute.filter((doc) => state.completed.includes(doc.path)).length;
    const percent = readingRoute.length ? Math.round(completed / readingRoute.length * 100) : 0;
    els.overallLabel.textContent = `${percent}%`;
    els.overallBar.style.width = `${percent}%`;
    els.overallCopy.textContent = completed
      ? `第一卷已读 ${completed} / ${readingRoute.length} 篇 · 参考材料按需查阅`
      : "第一卷阅读记录保存在当前设备";
    const secondChapters = secondVolume.filter((doc) => !doc.path.endsWith("/README.md"));
    const secondDone = secondChapters.filter((doc) => state.completed.includes(doc.path)).length;
    if (els.secondVolumeCopy) els.secondVolumeCopy.textContent =
      `第二卷已读 ${secondDone} / ${secondChapters.length} 章 · 初稿试读`;
  }

  function chapterButton(doc) {
    const isActive = current?.path === doc.path;
    const isBookmarked = state.bookmarks.includes(doc.path);
    const isComplete = state.completed.includes(doc.path);
    return `<button class="chapter-link${isActive ? " is-active" : ""}" data-path="${escapeHTML(doc.path)}" aria-current="${isActive ? "page" : "false"}">
      <span class="chapter-label">${escapeHTML(doc.title)}</span>
      <span class="chapter-state" aria-label="${isComplete ? "已读" : isBookmarked ? "已加入书签" : ""}">${isComplete ? "✓" : isBookmarked ? "☆" : ""}</span>
    </button>`;
  }

  function searchExcerpt(doc, query) {
    const text = doc.content.replace(/[#*`>|_~]/g, " ").replace(/\s+/g, " ").trim();
    const index = text.toLocaleLowerCase().indexOf(query);
    if (index < 0) return "";
    const start = Math.max(0, index - 32);
    const end = Math.min(text.length, index + query.length + 55);
    return (start ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : "");
  }

  function renderNavigation() {
    els.searchClear.hidden = !els.search.value;
    const query = searchTerm.trim().toLocaleLowerCase();
    const matches = documents.filter((doc) => {
      if (!query) return true;
      return doc.title.toLocaleLowerCase().includes(query)
        || doc.content.toLocaleLowerCase().includes(query)
        || doc.group.toLocaleLowerCase().includes(query);
    });
    let html = "";

    if (!query && state.bookmarks.length) {
      const saved = state.bookmarks.map((path) => byPath.get(path)).filter(Boolean);
      if (saved.length) {
        html += `<div class="nav-group bookmark-group"><div class="nav-heading"><span>我的书签</span><span class="nav-count">${saved.length}</span></div>${saved.map((doc) => chapterButton(doc)).join("")}</div>`;
      }
    }

    const groups = [...new Set(documents.map((doc) => doc.group))];
    for (const group of groups) {
      const items = matches.filter((doc) => doc.group === group);
      if (!items.length) continue;
      html += `<div class="nav-group"><div class="nav-heading"><span>${escapeHTML(group)}</span><span class="nav-count">${items.length}</span></div>${items.map((doc) => {
        const excerpt = query ? searchExcerpt(doc, query) : "";
        return chapterButton(doc) + (excerpt ? `<p class="search-excerpt">${escapeHTML(excerpt)}</p>` : "");
      }).join("")}</div>`;
    }

    els.nav.innerHTML = html || `<div class="empty-search"><span>⌕</span><strong>没有找到匹配内容</strong><small>试试更短的关键词</small></div>`;
    els.itemCount.textContent = query ? `${matches.length}/${documents.length}` : documents.length;
    els.searchStatus.textContent = query ? `在 ${documents.length} 篇材料中找到 ${matches.length} 篇` : "";
    renderOverallProgress();
  }

  function renderHome() {
    const secondChapters = secondVolume.filter((doc) => !doc.path.endsWith("/README.md"));
    const secondDone = secondChapters.filter((doc) => state.completed.includes(doc.path)).length;
    const volumes = [
      {
        number: "01", title: "第一卷 · 量化研究基础",
        description: "四只真实 A 股、100 万元课堂模拟账户，从价格、因子、模型学会量化入门。",
        path: firstVolume[0]?.path, status: `${firstVolume.length} 篇教学材料`, action: "从第一卷继续",
      },
      {
        number: "02", title: "第二卷 · 专业量化研究方法",
        description: "14 章正文初稿：PIT 数据、统计推断、因子、机器学习、样本外、组合与执行。",
        path: secondChapters[0]?.path, status: `${secondDone}/${secondChapters.length} 章已读`, action: "打开新增正文",
        featured: true,
      },
      {
        number: "03", title: "第三卷 · A 股策略与交易系统",
        description: "行业轮动、反转、微盘、L2 和交易系统，共 13 章，目前只有目录骨架。",
        path: thirdVolume[0]?.path, status: "13 章待写", action: "查看规划",
      },
    ];
    els.pathGrid.innerHTML = volumes.filter((volume) => volume.path).map((volume) =>
      `<button class="path-card volume-card${volume.featured ? " is-featured" : ""}" data-path="${escapeHTML(volume.path)}">` +
      `<span class="path-card-top"><span class="path-index">VOL. ${volume.number}</span><span class="path-arrow" aria-hidden="true">↗</span></span>` +
      `<strong>${escapeHTML(volume.title)}</strong>` +
      `<span class="path-description">${escapeHTML(volume.description)}</span>` +
      `<span class="path-card-foot"><span>${escapeHTML(volume.status)}</span><span>${escapeHTML(volume.action)} →</span></span>` +
      `</button>`
    ).join("");
    const totalMinutes = readingRoute.reduce((sum, doc) => sum + Number(doc.minutes || 1), 0);
    $("#home-chapter-count").textContent = documents.length;
    $("#home-reading-time").textContent = totalMinutes;
    $("#resume-button").textContent = state.lastPath && byPath.has(state.lastPath)
      ? "从上次位置继续　→" : "从第一篇开始阅读　→";
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
      const sourceBranch = doc.path.startsWith("advanced/") ? "docs/three-volume-research-framework" : "master";
      const source = new URL(`https://github.com/2514-nzk/quant-learning/blob/${sourceBranch}/${encodedPath}`);
      const target = new URL(href, source);
      const prefix = `/2514-nzk/quant-learning/blob/${sourceBranch}/`;
      if (target.hostname !== "github.com" || !target.pathname.startsWith(prefix)) return;
      const path = decodeURIComponent(target.pathname.slice(prefix.length));
      if (byPath.has(path)) {
        anchor.href = `?chapter=${encodeURIComponent(path)}${target.hash || ""}`;
        anchor.classList.add("reader-internal-link");
        return;
      }
      anchor.href = `https://github.com/2514-nzk/quant-learning/blob/${sourceBranch}/${path.split("/").map(encodeURIComponent).join("/")}`;
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
    } catch { /* Keep unparseable links as supplied. */ }
  }

  function highlightCodeBlocks(container) {
    const aliases = { py: "python", ps: "powershell", ps1: "powershell", pwsh: "powershell", yml: "yaml", sh: "bash", txt: "plaintext", text: "plaintext" };
    const labels = { python: "Python", powershell: "PowerShell", sql: "SQL", yaml: "YAML", json: "JSON", bash: "Bash", plaintext: "纯文本" };
    container.querySelectorAll("pre").forEach((pre) => {
      const code = pre.querySelector("code");
      if (!code) return;
      const languageClass = [...code.classList].find((name) => name.startsWith("language-"));
      let language = languageClass ? languageClass.slice("language-".length).toLowerCase() : "";
      language = aliases[language] || language;
      if (window.hljs) {
        if (language && language !== "plaintext" && window.hljs.getLanguage(language)) {
          code.className = `language-${language}`;
          window.hljs.highlightElement(code);
        } else if (!language) {
          const result = window.hljs.highlightAuto(code.textContent || "");
          if (result.relevance >= 4) {
            language = result.language || "";
            code.innerHTML = result.value;
            code.className = language ? `language-${language} hljs` : "hljs";
          } else {
            language = "plaintext";
            code.className = "language-plaintext";
          }
        } else {
          code.className = "language-plaintext";
        }
      }
      language ||= "plaintext";
      pre.classList.add("code-block");
      pre.dataset.language = language;
      const toolbar = document.createElement("div");
      toolbar.className = "code-toolbar";
      toolbar.innerHTML = `<span class="code-language">${escapeHTML(labels[language] || language)}</span><button class="code-copy" type="button" aria-label="复制代码">复制代码</button>`;
      pre.prepend(toolbar);
    });
  }

  function fetchText(relative) {
    if (!textCache.has(relative)) {
      textCache.set(relative, fetch(new URL(relative, document.baseURI)).then((response) => {
        if (!response.ok) throw new Error(`无法读取 ${relative}（${response.status}）`);
        return response.text();
      }));
    }
    return textCache.get(relative);
  }

  function getPyWorker() {
    if (pyWorker) return pyWorker;
    pyWorker = new Worker(new URL("pyodide-worker.js?v=9", document.baseURI));
    pyWorker.onmessage = (event) => {
      const { id, status, ok, output } = event.data || {};
      const pending = labPending.get(id);
      if (!pending) return;
      if (status) {
        pending.onStatus?.(status);
        return;
      }
      labPending.delete(id);
      clearTimeout(pending.timer);
      pending.resolve({ ok, output: output || "" });
    };
    pyWorker.onerror = (event) => {
      for (const [id, pending] of labPending) {
        clearTimeout(pending.timer);
        pending.reject(new Error(event.message || "浏览器运行环境出错"));
        labPending.delete(id);
      }
      pyWorker.terminate();
      pyWorker = null;
    };
    return pyWorker;
  }

  function runInBrowser({ code, filename, files, argv, onStatus }) {
    const worker = getPyWorker();
    const id = ++labRequestId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        labPending.delete(id);
        worker.terminate();
        pyWorker = null;
        reject(new Error("运行超过 120 秒，已停止。"));
      }, 120000);
      labPending.set(id, { resolve, reject, timer, onStatus });
      worker.postMessage({ id, code, filename, files, argv });
    });
  }

  async function labFiles(lab) {
    const files = [];
    for (const relative of lab.files || []) {
      files.push({ path: `/project/${relative}`, content: await fetchText(relative) });
    }
    return files;
  }

  function setLabStatus(status, value) {
    if (status.isConnected) status.textContent = value;
  }

  function labStatusMessage(value) {
    return value === "booting"
      ? "正在准备 Python 运行时（首次约十几 MB）…"
      : "正在运行…";
  }

  async function runLabScript(lab, config, output, status, button) {
    button.disabled = true;
    output.textContent = "";
    setLabStatus(status, "正在准备…");
    try {
      // For this book's fixed historical-data exercises, compute from the saved
      // four-stock JSON directly. No CDN, WASM, Python worker or extra download.
      if (lab.kind === "real-data") {
        setLabStatus(status, "正在读取课堂历史数据…");
        const source = lab.files?.[0];
        if (!source) throw new Error("课堂数据配置缺失，请刷新页面后重试。");
        const sample = JSON.parse(await fetchText(source));
        if (!window.QuantRealCase?.run) throw new Error("计算模块尚未加载，请刷新页面后重试。");
        const result = window.QuantRealCase.run(sample);
        if (output.isConnected) output.textContent = result;
        setLabStatus(status, "已完成历史行情计算");
        return;
      }
      const text = await fetchText(config.script);
      const files = await labFiles(lab);
      const filename = `/project/${config.script}`;
      files.push({ path: filename, content: text });
      const argv = [config.script.split("/").pop(), ...(config.args || [])];
      const result = await runInBrowser({
        code: text,
        filename,
        files,
        argv,
        onStatus: (value) => setLabStatus(status, labStatusMessage(value)),
      });
      if (output.isConnected) output.textContent = result.output || "（没有输出）";
      setLabStatus(status, result.ok ? "运行完成" : "运行出错");
    } catch (error) {
      if (output.isConnected) output.textContent = error.message || String(error);
      setLabStatus(status, "运行失败");
    } finally {
      button.disabled = false;
    }
  }

  async function runLabEditor(lab, editor, output, status, button) {
    button.disabled = true;
    output.textContent = "";
    setLabStatus(status, "正在准备…");
    try {
      const files = await labFiles(lab);
      const filename = `/project/${lab.script}`;
      files.push({ path: filename, content: editor.value });
      const result = await runInBrowser({
        code: editor.value,
        filename,
        files,
        argv: [lab.script.split("/").pop()],
        onStatus: (value) => setLabStatus(status, labStatusMessage(value)),
      });
      if (output.isConnected) output.textContent = result.output || "（没有输出）";
      setLabStatus(status, result.ok ? "运行完成" : "运行出错");
    } catch (error) {
      if (output.isConnected) output.textContent = error.message || String(error);
      setLabStatus(status, "运行失败");
    } finally {
      button.disabled = false;
    }
  }

  function renderLabFor(doc) {
    const lab = labs[doc.path];
    if (!lab) return;
    const panel = document.createElement("section");
    panel.className = "lab-panel";
    panel.innerHTML = `<div class="lab-head">
      <span class="lab-kicker">${lab.kind === "real-data" ? "真实数据 · 浏览器计算" : "代码实验室 · PYODIDE"}</span>
      <h2>${escapeHTML(lab.title)}</h2>
      <p>${escapeHTML(lab.description)}</p>
    </div>
    <div class="lab-body"></div>`;
    const body = panel.querySelector(".lab-body");
    const status = document.createElement("span");
    status.className = "lab-status";
    status.setAttribute("aria-live", "polite");
    status.textContent = lab.kind === "real-data" ? "使用已保存的真实历史行情，点击即可计算" : "首次运行需下载约十几 MB 的 Python 运行时";
    const output = document.createElement("pre");
    output.className = "lab-output";
    output.textContent = "运行结果会显示在这里。";

    if (lab.kind === "editor") {
      const editor = document.createElement("textarea");
      editor.className = "lab-editor";
      editor.spellcheck = false;
      editor.setAttribute("aria-label", "可编辑的 Python 代码");
      editor.value = "正在载入代码…";
      const actions = document.createElement("div");
      actions.className = "lab-actions";
      const run = document.createElement("button");
      run.className = "lab-run";
      run.type = "button";
      run.textContent = "运行代码";
      const reset = document.createElement("button");
      reset.className = "lab-reset";
      reset.type = "button";
      reset.textContent = "恢复原代码";
      actions.append(run, reset, status);
      body.append(editor, actions, output);
      fetchText(lab.script).then((text) => {
        if (editor.isConnected && editor.value === "正在载入代码…") editor.value = text;
      }).catch((error) => { editor.value = error.message || String(error); });
      run.addEventListener("click", () => runLabEditor(lab, editor, output, status, run));
      reset.addEventListener("click", () => {
        fetchText(lab.script).then((text) => {
          editor.value = text;
          output.textContent = "已恢复原始代码。";
          setLabStatus(status, "");
        });
      });
      editor.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
          event.preventDefault();
          run.click();
        }
      });
    } else {
      const actions = document.createElement("div");
      actions.className = "lab-actions";
      for (const config of lab.scripts || []) {
        const run = document.createElement("button");
        run.className = "lab-run";
        run.type = "button";
        run.textContent = config.label;
        run.addEventListener("click", () => runLabScript(lab, config, output, status, run));
        actions.append(run);
      }
      actions.append(status);
      body.append(actions, output);
    }
    els.article.append(panel);
  }

  // Keep TeX delimiters intact through Markdown parsing, without converting code fences.
  function prepareMath(markdown) {
    const parts = markdown.split(/(~{3}[\s\S]*?~{3}|\x60{3}[\s\S]*?\x60{3})/g);
    return parts.map((part, index) => {
      if (index % 2) return part;
      return part
        .replace(/\\\[([\s\S]*?)\\\]/g, (_, tex) =>
          '<div class="math-block" data-math="' + encodeURIComponent(tex) +
          '">' + escapeHTML('\\[' + tex + '\\]') + '</div>')
        .replace(/\\\(([\s\S]*?)\\\)/g, (_, tex) =>
          '<span class="math-inline" data-math="' + encodeURIComponent(tex) +
          '">' + escapeHTML('\\(' + tex + '\\)') + '</span>');
    }).join("");
  }

  function typesetMath(container) {
    if (!window.katex) return; // Leave readable source if CDN fails.
    container.querySelectorAll("[data-math]").forEach((element) => {
      try {
        window.katex.render(decodeURIComponent(element.dataset.math),
          element, { displayMode: element.classList.contains("math-block"),
                     throwOnError: false, strict: "warn" });
      } catch { /* Keep source text rather than losing a formula. */ }
    });
  }

  function renderArticle(doc) {
    if (!window.marked || !window.DOMPurify) {
      els.article.innerHTML = `<p class="reader-error">正文解析组件没有加载成功。请刷新页面，或检查当前网络是否可以访问 jsDelivr。</p><pre>${escapeHTML(doc.content)}</pre>`;
      els.sectionIndex.hidden = true;
      return;
    }
    const raw = window.marked.parse(prepareMath(doc.content), { gfm: true, breaks: false });
    const wrapper = document.createElement("div");
    wrapper.innerHTML = window.DOMPurify.sanitize(raw);
    typesetMath(wrapper);
    wrapper.querySelectorAll("a[href]").forEach((anchor) => normalizeMarkdownLink(anchor, doc));
    wrapper.querySelectorAll("img[src]").forEach((image) => {
      const src = image.getAttribute("src") || "";
      if (!/^(https?:|data:|\/\/)/i.test(src)) {
        const encodedPath = doc.path.split("/").map(encodeURIComponent).join("/");
        try {
          const sourceBranch = doc.path.startsWith("advanced/") ? "docs/three-volume-research-framework" : "master";
          const target = new URL(src, `https://raw.githubusercontent.com/2514-nzk/quant-learning/${sourceBranch}/${encodedPath}`);
          const assetPrefix = "https://raw.githubusercontent.com/2514-nzk/quant-learning/master/reader/assets/";
          image.src = target.href.startsWith(assetPrefix)
            ? new URL(`assets/${target.href.slice(assetPrefix.length)}`, document.baseURI).href
            : target.href;
        } catch { /* Keep the original source on malformed paths. */ }
      }
      image.loading = "lazy";
    });
    highlightCodeBlocks(wrapper);

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
    renderLabFor(doc);
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
    els.next.querySelector("span").textContent = current.group !== "工具与参考" && next?.group === "工具与参考"
      ? "主线读完了 · 按需查阅 →" : "下一篇 →";
    els.previous.dataset.path = previous?.path || "";
    els.next.dataset.path = next?.path || "";
  }

  function updateReadingProgress() {
    if (!current || restoringPosition) return;
    const maximum = Math.max(0, els.reader.scrollHeight - els.reader.clientHeight);
    const percent = maximum ? Math.min(100, Math.round(els.reader.scrollTop / maximum * 100)) : 0;
    const chapter = current.content.match(/^#\s*第\s*(\d+)\s*章/m);
    let position = current.group === "工具与参考" ? "参考资料" : "导读与准备";
    const volumeTwoChapter = current.path.match(/^advanced\/volume-2\/(\d{2})_/);
    if (current.path.startsWith("advanced/volume-3/")) position = "第三卷 · 目录框架待写";
    else if (volumeTwoChapter) position = `第二卷 第 ${Number(volumeTwoChapter[1])} / 14 章`;
    else if (current.path === "advanced/volume-2/README.md") position = "第二卷 · 课程目录";
    else if (chapter) position = `第 ${chapter[1]} / ${mainChapterCount} 章`;
    els.chapterProgress.textContent = `${position}　·　${percent}%`;
    els.readingProgressBar.style.width = `${percent}%`;
    els.readingProgress.setAttribute("aria-valuenow", String(percent));
    els.backToTop.hidden = els.reader.scrollTop < 380;
    state.positions[current.path] = els.reader.scrollTop;
    if (!current.path.startsWith("advanced/volume-3/") && maximum > 0 && percent >= 92 && !state.completed.includes(current.path)) {
      state.completed.push(current.path);
      updateChapterActions();
      renderNavigation();
    }
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveState, 400);
  }

  function saveReadingPosition() {
    if (current && !restoringPosition) {
      state.positions[current.path] = els.reader.scrollTop;
    }
    clearTimeout(saveTimer);
    saveState();
  }

  function showChapter(path, { route = true, replace = false, restore = true, section = "" } = {}) {
    const doc = byPath.get(path);
    if (!doc) return showHome({ route: false });

    // Save the chapter being left before DOM changes alter its scroll height.
    saveReadingPosition();
    const storedPosition = Number(state.positions[doc.path] ?? 0);
    const targetPosition = restore && Number.isFinite(storedPosition) ? Math.max(0, storedPosition) : 0;
    const version = ++navigationId;
    restoringPosition = true;
    current = doc;
    const index = documents.indexOf(doc);
    els.home.hidden = true;
    els.resetNotice.hidden = true;
    els.chapter.hidden = false;
    els.readingProgress.hidden = false;
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
      if (version !== navigationId) return;
      const sectionTarget = section ? document.getElementById(section) : null;
      if (sectionTarget) sectionTarget.scrollIntoView({ block: "start", behavior: "instant" });
      else els.reader.scrollTo({ top: targetPosition, behavior: "instant" });
      restoringPosition = false;
      updateReadingProgress();
    });
  }

  function showHome({ route = true, savePrevious = true } = {}) {
    if (savePrevious) saveReadingPosition();
    else clearTimeout(saveTimer);
    ++navigationId;
    restoringPosition = false;
    current = null;
    els.chapter.hidden = true;
    els.home.hidden = false;
    els.readingProgress.hidden = true;
    els.readingProgressBar.style.width = "0%";
    els.backToTop.hidden = true;
    els.breadcrumb.textContent = "量化入门";
    els.chapterProgress.textContent = "";
    els.reader.scrollTo({ top: 0, behavior: "instant" });
    renderHome();
    renderNavigation();
    if (route) setRoute("");
    closeMobileMenu();
  }

  function resetReadingHistory() {
    // Do not let a pending scroll-save repopulate data during reset.
    clearTimeout(saveTimer);
    const clearBookmarks = els.resetBookmarks.checked;
    state.positions = {};
    state.completed = [];
    state.lastPath = "";
    if (clearBookmarks) state.bookmarks = [];

    els.resetDialog.close();
    // Navigating home must not save the now-discarded chapter position.
    showHome({ savePrevious: false });
    saveState();
    els.resetNotice.textContent = clearBookmarks
      ? "阅读进度与书签已清空，可以重新开始阅读。"
      : "阅读进度已清空，书签、主题和字号均已保留。";
    els.resetNotice.hidden = false;
    $("#start-button").focus();
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
    els.menuButton.setAttribute("aria-expanded", "true");
    els.menuButton.setAttribute("aria-label", "关闭目录");
  }

  function closeMobileMenu() {
    els.sidebar.classList.remove("is-open");
    els.mobileBackdrop.classList.remove("is-visible");
    document.body.classList.remove("menu-open");
    els.menuButton.setAttribute("aria-expanded", "false");
    els.menuButton.setAttribute("aria-label", "打开目录");
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
      firstVolume = payload.documents || [];
      secondVolume = (payload.framework || []).filter((doc) => doc.path.startsWith("advanced/volume-2/"));
      thirdVolume = (payload.framework || []).filter((doc) => doc.path.startsWith("advanced/volume-3/"));
      documents = [...firstVolume, ...secondVolume, ...thirdVolume];
      labs = payload.labs || {};
      // Planned volumes are navigable, but must not alter the completed first-volume progress.
      readingRoute = firstVolume.filter((doc) => doc.group !== "工具与参考");
      byPath = new Map(documents.map((doc) => [doc.path, doc]));
      mainChapterCount = firstVolume.filter((doc) => /^#\s*第\s*\d+\s*章/m.test(doc.content)).length;
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
    if (button) showChapter(button.dataset.path);
  });
  els.search.addEventListener("input", () => {
    searchTerm = els.search.value;
    renderNavigation();
  });
  els.searchClear.addEventListener("click", () => {
    els.search.value = "";
    searchTerm = "";
    renderNavigation();
    els.search.focus();
  });
  els.manageProgress.addEventListener("click", () => {
    els.resetBookmarks.checked = false;
    els.resetDialog.showModal();
  });
  els.resetCancel.addEventListener("click", () => els.resetDialog.close());
  els.resetConfirm.addEventListener("click", resetReadingHistory);
  els.backToTop.addEventListener("click", () => {
    // An explicit jump must persist zero, not an intermediate smooth-scroll frame.
    els.reader.scrollTo({ top: 0, behavior: "instant" });
    if (current) {
      state.positions[current.path] = 0;
      updateReadingProgress();
      saveState();
    }
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
  els.previous.addEventListener("click", () => { if (els.previous.dataset.path) showChapter(els.previous.dataset.path); });
  els.next.addEventListener("click", () => { if (els.next.dataset.path) showChapter(els.next.dataset.path); });
  $("#font-down").addEventListener("click", () => { state.font = Math.max(0.88, +(state.font - 0.06).toFixed(2)); applyAppearance(); saveState(); });
  $("#font-up").addEventListener("click", () => { state.font = Math.min(1.3, +(state.font + 0.06).toFixed(2)); applyAppearance(); saveState(); });
  $("#theme-button").addEventListener("click", () => { state.theme = state.theme === "dark" ? "light" : "dark"; applyAppearance(); saveState(); });
  els.menuButton.addEventListener("click", () => {
    if (els.sidebar.classList.contains("is-open")) closeMobileMenu();
    else { openMobileMenu(); els.search.focus(); }
  });
  els.mobileBackdrop.addEventListener("click", closeMobileMenu);
  els.reader.addEventListener("scroll", updateReadingProgress, { passive: true });
  window.addEventListener("pagehide", saveReadingPosition);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") saveReadingPosition();
  });
  els.article.addEventListener("click", (event) => {
    const copyButton = event.target.closest(".code-copy");
    if (copyButton) {
      const code = copyButton.closest("pre")?.querySelector("code");
      if (!code) return;
      if (!navigator.clipboard?.writeText) {
        copyButton.textContent = "无法复制";
        return;
      }
      const originalLabel = "复制代码";
      navigator.clipboard.writeText(code.innerText).then(() => {
        copyButton.textContent = "已复制";
        setTimeout(() => { if (copyButton.isConnected) copyButton.textContent = originalLabel; }, 1400);
      }).catch(() => { copyButton.textContent = "复制失败"; });
      return;
    }
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
      const wasOpen = els.sidebar.classList.contains("is-open");
      closeMobileMenu();
      if (wasOpen) els.menuButton.focus();
    }
  });

  init();
})();
