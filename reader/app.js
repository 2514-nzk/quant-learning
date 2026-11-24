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
  let labBusy = false;
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
    const secondChapters = secondVolume.filter((doc) => /^advanced\/volume-2\/\d{2}_[^/]+\.md$/.test(doc.path));
    const secondDone = secondChapters.filter((doc) => state.completed.includes(doc.path)).length;
    if (els.secondVolumeCopy) els.secondVolumeCopy.textContent =
      `第二卷已读 ${secondDone} / ${secondChapters.length} 章 · 教学版 v1`;
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
    const secondChapters = secondVolume.filter((doc) => /^advanced\/volume-2\/\d{2}_[^/]+\.md$/.test(doc.path));
    const secondDone = secondChapters.filter((doc) => state.completed.includes(doc.path)).length;
    const volumes = [
      {
        number: "01", title: "第一卷 · 量化研究基础",
        description: "四只真实 A 股、100 万元课堂模拟账户，从价格、因子、模型学会量化入门。",
        path: firstVolume[0]?.path, status: `${firstVolume.length} 篇教学材料`, action: "从第一卷继续",
      },
      {
        number: "02", title: "第二卷 · 专业量化研究方法",
        description: "从 REV20 反转因子出发，学会清理数据、检验因子、比较模型，再走向组合与回测。",
        path: secondChapters[0]?.path, status: `${secondDone}/${secondChapters.length} 章已读`, action: "开始研究项目",
        featured: true,
      },
      {
        number: "03", title: "第三卷 · A 股策略与交易系统",
        description: "研究择时、行业、反转、配对交易与订单，再完成多策略配置、纸面故障演练及综合研究报告。",
        path: thirdVolume[0]?.path, status: "12 章教学正文 · 1 章入门案例", action: "查看第三卷",
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
      const sourceBranch = "master";
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
      }).catch(error => { textCache.delete(relative); throw error; }));
    }
    return textCache.get(relative);
  }

  function getPyWorker() {
    if (pyWorker) return pyWorker;
    pyWorker = new Worker(new URL("pyodide-worker.js?v=10", document.baseURI));
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
    if (labPending.size) return Promise.reject(new Error("已有 Python 实验运行，请完成后再试。"));
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
    if (labBusy) { setLabStatus(status, "已有实验正在运行，请完成后再试。"); return; }
    labBusy = true;
    const buttons = [...(button.closest(".lab-panel")?.querySelectorAll("button") || [button])];
    buttons.forEach(b => { b.disabled = true; });
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
      labBusy = false;
      buttons.forEach(b => { b.disabled = false; });
    }
  }

  async function runLabEditor(lab, editor, output, status, button) {
    if (labBusy) { setLabStatus(status, "已有实验正在运行，请完成后再试。"); return; }
    labBusy = true;
    const buttons = [...(button.closest(".lab-panel")?.querySelectorAll("button") || [button])];
    buttons.forEach(b => { b.disabled = true; });
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
      labBusy = false;
      buttons.forEach(b => { b.disabled = false; });
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
    // Line-anchored fences (including longer ones) and inline code are literal.
    // Do not rewrite TeX that is being taught as source code.
    const lines = markdown.match(/[^\n]*\n|[^\n]+$/g) || [];
    let fence = null, plain = "", result = "";
    function renderText(part) {
      return part.replace(/(\x60+)([^\n]*?)\1(?!\x60)|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)/g,
        (whole, ticks, code, display, inline) => {
          if (ticks) return whole;
          const tex = display === undefined ? inline : display;
          const block = display !== undefined;
          const tag = block ? "div" : "span";
          const literal = (block ? "\\[" : "\\(") + tex + (block ? "\\]" : "\\)");
          // Escape pipes in fallback HTML, too, so GFM tables do not split a formula.
          return '<' + tag + ' class="math-' + (block ? "block" : "inline") +
            '" data-math="' + encodeURIComponent(tex) + '">' +
            escapeHTML(literal).replace(/\|/g, "&#124;") + '</' + tag + '>';
        });
    }
    function flush() { result += renderText(plain); plain = ""; }
    for (const line of lines) {
      const marker = line.match(/^ {0,3}(~{3,}|\x60{3,})([^\n]*)/);
      if (fence) {
        result += line;
        if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length && !marker[2].trim()) fence = null;
      } else if (marker) {
        flush(); fence = marker[1]; result += line;
      } else plain += line;
    }
    flush();
    return result;
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

  // Render only fixed classroom calculations; no connection to a trading account.
  function renderRiskDashboard(doc) {
    if (!/^advanced\/volume-2\/(08_|11_|12_|13_|14_)/.test(doc.path)) return;
    const panel = document.createElement("section");
    panel.className = "risk-dashboard";
    panel.innerHTML = '<h2>看图读懂风险与收益</h2><p>同一课堂股票池，人工数据，非实盘业绩。选择账户即可比较实际持仓、净值及归因。</p><div class="risk-content" aria-live="polite">正在读取计算结果…</div>';
    els.article.append(panel);
    const body = panel.querySelector(".risk-content");
    const money = n => n.toLocaleString("zh-CN", {maximumFractionDigits: 2});
    const pct = n => (100*n).toFixed(2) + "%";
    const labels = {fixed:"固定等权",risk:"风险约束",monitored:"IC监控降仓"};
    const palette = {fixed:"#64748b",risk:"#258b82",monitored:"#bd7840"};
    function chart(series, unit, domain) {
      const all = series.flatMap(s => s.values.map(v => v.value).filter(Number.isFinite));
      if (!all.length) return '<p>没有有效数据。</p>';
      let lo = domain ? domain[0] : Math.min(...all), hi = domain ? domain[1] : Math.max(...all);
      if (hi === lo) {lo -= 1; hi += 1;}
      const left=72,right=680,top=14,bottom=178;
      const days = series.flatMap(s=>s.values.map(v=>v.day));
      const d0=Math.min(...days),d1=Math.max(...days);
      const x=d=>left+(d-d0)/Math.max(1,d1-d0)*(right-left);
      const y=v=>bottom-(v-lo)/(hi-lo)*(bottom-top);
      let svg='<svg viewBox="0 0 700 210" role="img" aria-label="课堂数据折线图">';
      for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;const yy=y(v);
        svg+='<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" stroke="currentColor" opacity=".12"/><text x="'+(left-8)+'" y="'+(yy+4)+'" text-anchor="end" fill="currentColor" font-size="11">'+escapeHTML(unit(v))+'</text>';
      }
      for(let i=0;i<=4;i++){const d=Math.round(d0+(d1-d0)*i/4);svg+='<text x="'+x(d)+'" y="199" text-anchor="middle" fill="currentColor" font-size="11">'+d+'</text>';}
      for(const s of series){let segment=[];
        const flush=()=>{if(segment.length){svg+='<polyline points="'+segment.join(" ")+'" fill="none" stroke="'+s.color+'" stroke-width="2.4" stroke-linejoin="round"/>';segment=[];}};
        for(const v of s.values){if(!Number.isFinite(v.value)){flush();continue;}segment.push(x(v.day)+","+y(v.value));}flush();
      }
      return svg+'</svg><div class="risk-legend">'+series.map(s=>'<span><i style="background:'+s.color+'"></i>'+escapeHTML(s.name)+'</span>').join("")+'</div>';
    }
    fetch(new URL("assets/rev20-risk-dashboard.json", document.baseURI)).then(r=>{if(!r.ok)throw Error("数据未加载");return r.json();}).then(data=>{
      if(!panel.isConnected)return;
      if(data.source_kind!=="SYNTHETIC_ONLY")throw Error("数据标识错误");
      const keys=Object.keys(labels);
      body.innerHTML='<label>查看账户 <select class="risk-select">'+keys.map(k=>'<option value="'+k+'">'+labels[k]+'</option>').join("")+'</select></label><h3>净值对照（元）</h3><div class="risk-nav-chart"></div><div class="risk-selected"></div><h3>逐期 RankIC（信号时段）</h3><div class="risk-ic-chart"></div><h3>流动性约束敏感性</h3><div class="risk-capacity"></div>';
      body.querySelector(".risk-nav-chart").innerHTML=chart(keys.map(k=>({name:labels[k],color:palette[k],values:data.nav[k]})),v=>money(v));
      body.querySelector(".risk-ic-chart").innerHTML=chart([{name:"REV20 IC",color:palette.risk,values:data.factor_ic.map(v=>({day:v.signal,value:v.ic}))}],v=>v.toFixed(2),[-1,1]);
      const cap=data.capacity.map(v=>'<tr><td>'+pct(v.rate)+'</td><td>'+money(v.nav)+'</td><td>'+v.unfilled+'</td><td>'+money(v.traded)+'</td></tr>').join("");
      body.querySelector(".risk-capacity").innerHTML='<table><thead><tr><th>参与率代理</th><th>期末净值</th><th>未完全成交单</th><th>成交额</th></tr></thead><tbody>'+cap+'</tbody></table><p>不同假设下的模拟执行结果，不是实际资金容量。</p>';
      function update(){
        const k=body.querySelector("select").value,a=data.summary[k],at=data.attribution[k];
        const ex=data.exposure[k];
        const components={market:"市场参考",industry:"行业偏离",selection:"个股相对表现",fees:"手续费",slippage:"滑点",residual:"对账残差",actual:"实际盈亏"};
        const attr=Object.entries(components).map(([v,label])=>'<tr><td>'+label+'</td><td>'+money(at[v])+'</td></tr>').join("");
        body.querySelector(".risk-selected").innerHTML='<div class="risk-metrics"><div><small>期末净值</small><strong>'+money(a.final_nav)+'</strong></div><div><small>累计收益</small><strong>'+pct(a.total_return)+'</strong></div><div><small>最大回撤</small><strong>'+pct(a.max_drawdown)+'</strong></div><div><small>未完全成交单</small><strong>'+a.unfilled_orders+'</strong></div></div><h3>每日实际持仓比例</h3>'+chart([{name:"股票仓位",color:palette.risk,values:ex.map(v=>({day:v.day,value:v.stock}))},{name:"最大行业权重",color:palette.monitored,values:ex.map(v=>({day:v.day,value:v.max_industry}))}],pct,[0,1])+'<h3>收益来源（元）</h3><table><thead><tr><th>组成</th><th>金额</th></tr></thead><tbody>'+attr+'</tbody></table><p>参考篮子分解，不是回归估计的 Alpha/Beta；金额之和与账户盈亏对账。</p>';
      }
      body.querySelector("select").addEventListener("change",update);update();
    }).catch(()=>{if(panel.isConnected)body.textContent="图表数据加载失败。仍可使用本章 Python 实验重新计算。";});
  }

  function renderRealSensitivity(doc) {
    if (!["教程/真实_08_单因子评价.md","教程/真实_16_综合练习.md",
           "advanced/volume-2/08_factor_validation.md"].includes(doc.path)) return;
    const panel = document.createElement("section");
    panel.className = "risk-dashboard real-sensitivity";
    panel.innerHTML = '<h2>动手试：动量还是反转？买几只股票？</h2><p>使用第一卷原有四只真实股票的 18 期价格观察。可以改变排序方向、选股数量和每期费用代理。所有结果仅为已公开历史的描述性教学，不是独立样本外或真实成交净值。</p><div class="sensitivity-body" aria-live="polite">正在读取课堂数据…</div>';
    els.article.append(panel);
    const body = panel.querySelector(".sensitivity-body");
    fetchText("data/real_a_share/teaching_case.json").then(JSON.parse).then(sample => {
      if (!panel.isConnected) return;
      body.innerHTML = '<div class="sensitivity-controls"><label>排序方向 <select name="direction"><option value="momentum">动量（过去涨得多）</option><option value="reversal">反转（过去跌得多）</option></select></label><label>每期选股数量 <select name="count"><option>1</option><option selected>2</option><option>3</option><option>4</option></select></label><label>每期固定费用代理 <select name="bps"><option>0</option><option>10</option><option>30</option><option>50</option><option>100</option></select> bps</label></div><div class="sensitivity-results"></div>';
      const result = body.querySelector(".sensitivity-results");
      function update() {
        const r = window.QuantRealCase.sensitivity(sample,body.querySelector('[name="direction"]').value,
          Number(body.querySelector('[name="count"]').value),Number(body.querySelector('[name="bps"]').value));
        const pct = n => (n*100).toFixed(2)+"%";
        const f = n => n===null?"未定义":n.toFixed(3);
        const tr = r.blocks.map(b=>'<tr><td>'+escapeHTML(b.name)+'</td><td>'+b.periods+'</td><td>'+f(b.meanIc)+'</td><td>'+pct(b.gross)+'</td><td>'+pct(b.netProxy)+'</td><td>'+pct(b.benchmarkProxy)+'</td></tr>').join("");
        const selected = r.rows[r.rows.length-1];
        result.innerHTML='<div class="risk-metrics"><div><small>18期毛观察复利</small><strong>'+pct(r.gross)+'</strong></div><div><small>费用情景复利</small><strong>'+pct(r.netProxy)+'</strong></div><div><small>平均 RankIC</small><strong>'+f(r.meanIc)+'</strong></div><div><small>四股等权费用情景</small><strong>'+pct(r.benchmarkProxy)+'</strong></div></div><p>最后一期按已知分数选择：'+escapeHTML(selected.selected.join("、"))+'；该期毛收益 '+pct(selected.gross)+'。</p><div class="risk-capacity"><table><thead><tr><th>历史分段</th><th>期数</th><th>平均IC</th><th>毛复利</th><th>扣费代理</th><th>等权扣费代理</th></tr></thead><tbody>'+tr+'</tbody></table></div><p>费用代理 = 每期收益减去固定基点（1 bps = 0.01 个百分点）；两种组合都按相同假设扣费。没有实际整手、分红、成交及换手账本。改变选股数不改变排序 IC；切换方向则反转排序符号。不要从已公开历史中挑表现最好的一组再称为独立检验。</p>';
      }
      body.querySelectorAll("select").forEach(select=>select.addEventListener("change",update));
      update();
    }).catch(error=>{if(panel.isConnected)body.textContent="课堂数据加载失败："+error.message;});
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
    // Teaching calculations use readable Chinese notation, not a code toolbar.
    wrapper.querySelectorAll("pre > code.language-formula").forEach((code) => {
      const panel = document.createElement("div");
      panel.className = "formula-reading";
      panel.textContent = (code.textContent || "").trim();
      code.parentElement.replaceWith(panel);
    });
    wrapper.querySelectorAll("a[href]").forEach((anchor) => normalizeMarkdownLink(anchor, doc));
    wrapper.querySelectorAll("img[src]").forEach((image) => {
      const src = image.getAttribute("src") || "";
      if (!/^(https?:|data:|\/\/)/i.test(src)) {
        const encodedPath = doc.path.split("/").map(encodeURIComponent).join("/");
        try {
          const sourceBranch = "master";
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
    window.QuantMathLab?.mount(els.article);
    renderRealSensitivity(doc);
    renderRiskDashboard(doc);
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

  // Treat a volume boundary as a book transition, never an ordinary chapter jump.
  // The existing first-volume reading order (including its optional references) is intact.
  function volumeOf(doc) {
    if (doc.path.startsWith("advanced/volume-2/")) return "second";
    if (doc.path.startsWith("advanced/volume-3/")) return "third";
    return "first";
  }

  function updatePager(index) {
    const previous = documents[index - 1];
    const next = documents[index + 1];
    const activeVolume = volumeOf(current);
    const previousIsAnotherVolume = previous && volumeOf(previous) !== activeVolume;
    const nextIsAnotherVolume = next && volumeOf(next) !== activeVolume;

    // Cross-volume buttons return to the three-volume bookshelf, where the
    // reader explicitly selects the next book. Never masquerade as "下一篇".
    els.previous.disabled = !previous;
    els.previous.querySelector("span").textContent = previousIsAnotherVolume
      ? "← 本卷起点" : "← 上一篇";
    els.previous.querySelector("strong").textContent = previousIsAnotherVolume
      ? "返回书架选择卷别" : previous?.title || "已是第一篇";
    els.previous.dataset.path = previousIsAnotherVolume ? "__home__" : previous?.path || "";

    els.next.disabled = !next;
    els.next.querySelector("span").textContent = nextIsAnotherVolume
      ? "本卷读完 · 切换下一卷 →"
      : current.group !== "工具与参考" && next?.group === "工具与参考"
        ? "主线读完了 · 按需查阅 →" : "下一篇 →";
    els.next.querySelector("strong").textContent = nextIsAnotherVolume
      ? "返回书架选择卷别" : next?.title || "已到最后一篇";
    els.next.dataset.path = nextIsAnotherVolume ? "__home__" : next?.path || "";
  }

  function updateReadingProgress() {
    if (!current || restoringPosition) return;
    const maximum = Math.max(0, els.reader.scrollHeight - els.reader.clientHeight);
    const percent = maximum ? Math.min(100, Math.round(els.reader.scrollTop / maximum * 100)) : 0;
    const chapter = current.content.match(/^#\s*第\s*(\d+)\s*章/m);
    let position = current.group === "工具与参考" ? "参考资料" : "导读与准备";
    const volumeTwoChapter = current.path.match(/^advanced\/volume-2\/(\d{2})_/);
    if (current.path === "advanced/volume-3/08_stat_arb.md") position = "第三卷 第 8 / 13 章 · 入门案例";
    else if (current.path === "advanced/volume-3/09_l2_auction.md") position = "第三卷 第 9 / 13 章 · L2 教学正文";
    else if (current.path === "advanced/volume-3/10_execution_replay.md") position = "第三卷 第 10 / 13 章 · 执行回放教学正文";
    else if (/^advanced\/volume-3\/0[1-7]_/.test(current.path)) position = `第三卷 第 ${Number(current.path.match(/\/0([1-7])_/)[1])} / 13 章 · 教学正文`;
    else if (/^advanced\/volume-3\/1[1-3]_/.test(current.path)) position = `第三卷 第 ${Number(current.path.match(/\/(1[1-3])_/)[1])} / 13 章 · 教学正文`;
    else if (current.path.startsWith("advanced/volume-3/")) position = "第三卷 · 课程目录";
    else if (volumeTwoChapter) position = `第二卷 第 ${Number(volumeTwoChapter[1])} / 14 章`;
    else if (current.path === "advanced/volume-2/README.md") position = "第二卷 · 课程目录";
    else if (chapter) position = `第 ${chapter[1]} / ${mainChapterCount} 章`;
    els.chapterProgress.textContent = `${position}　·　${percent}%`;
    els.readingProgressBar.style.width = `${percent}%`;
    els.readingProgress.setAttribute("aria-valuenow", String(percent));
    els.backToTop.hidden = els.reader.scrollTop < 380;
    state.positions[current.path] = els.reader.scrollTop;
    if ((!current.path.startsWith("advanced/volume-3/") || /^advanced\/volume-3\/(0[1-7]|08|09|10|1[1-3])_/.test(current.path)) && maximum > 0 && percent >= 92 && !state.completed.includes(current.path)) {
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
      // Preserve reading positions and bookmarks when the pair-trading case
      // moves from the first-volume optional section into volume three.
      const oldPairPath = "教程/真实_专题A_协整与配对交易.md";
      const newPairPath = "advanced/volume-3/08_stat_arb.md";
      const migratePairPath = (path) => path === oldPairPath ? newPairPath : path;
      if (state.lastPath === oldPairPath) state.lastPath = newPairPath;
      state.bookmarks = [...new Set(state.bookmarks.map(migratePairPath))];
      state.completed = [...new Set(state.completed.map(migratePairPath))];
      if (Object.prototype.hasOwnProperty.call(state.positions, oldPairPath)) {
        if (!(newPairPath in state.positions)) state.positions[newPairPath] = state.positions[oldPairPath];
        delete state.positions[oldPairPath];
      }
      state.completed = state.completed.filter((path) => byPath.has(path));
      $("#home-chapter-count").textContent = documents.length;
      renderHome();
      renderNavigation();
      applyAppearance();
      els.loading.hidden = true;
      const queryPath = new URLSearchParams(location.search).get("chapter");
      const resolvedPath = queryPath === oldPairPath ? newPairPath : queryPath;
      if (resolvedPath && byPath.has(resolvedPath)) showChapter(resolvedPath, { route: queryPath === oldPairPath, replace: true, restore: true, section: decodeURIComponent(location.hash.slice(1)) });
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
  function followPager(path) {
    if (path === "__home__") showHome();
    else if (path) showChapter(path);
  }
  els.previous.addEventListener("click", () => followPager(els.previous.dataset.path));
  els.next.addEventListener("click", () => followPager(els.next.dataset.path));
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
