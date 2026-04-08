const HISTORY_API = "/api/history";

document.addEventListener("DOMContentLoaded", () => {
  setupActiveNav();
  setupScrollReveal();
  setupReorderForm();
  setupCopyButtons();
  setupReorderFlowGraph();
  void saveRunPayloadToHistory();
  void setupHistoryPage();
});

function setupActiveNav() {
  const path = window.location.pathname;
  const links = Array.from(document.querySelectorAll(".tube-link"));
  const nav = document.querySelector("[data-expandable-tabs]");
  if (!links.length) return;

  let activeIndex = -1;
  links.forEach((link, index) => {
    const route = link.getAttribute("data-route");
    if (route && (path === route || path.startsWith(route + "/"))) {
      link.classList.add("active");
      activeIndex = index;
    }
  });

  const setExpanded = (index) => {
    links.forEach((link, i) => {
      link.classList.toggle("expanded", i === index);
    });
  };

  if (activeIndex >= 0) setExpanded(activeIndex);

  links.forEach((link, index) => {
    link.addEventListener("click", () => {
      setExpanded(index);
    });
  });

  if (nav) {
    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (!nav.contains(target) && activeIndex >= 0) {
        setExpanded(activeIndex);
      }
    });
  }
}

function setupScrollReveal() {
  const targets = document.querySelectorAll(".reveal");
  if (!targets.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  targets.forEach((target) => observer.observe(target));
}

function setupReorderForm() {
  const form = document.getElementById("reorder-form");
  if (!form) return;

  const textarea = document.getElementById("input-text");
  const loading = document.getElementById("loading-indicator");
  const validation = document.getElementById("validation-message");
  const loadSampleBtn = document.getElementById("load-sample");
  const clearBtn = document.getElementById("clear-input");

  if (loadSampleBtn && textarea) {
    loadSampleBtn.addEventListener("click", async () => {
      const original = loadSampleBtn.textContent;
      loadSampleBtn.textContent = "Loading...";
      loadSampleBtn.disabled = true;
      if (loading) loading.classList.add("active");

      try {
        const response = await fetch("/api/sample", {
          method: "GET",
          headers: { Accept: "application/json" },
        });
        const payload = await readJsonResponse(response);
        if (payload && typeof payload.text === "string" && payload.text.trim()) {
          textarea.value = payload.text;
          if (validation) validation.textContent = "Loaded Reuters dataset sample.";
        } else {
          if (validation) validation.textContent = "Dataset sample is unavailable right now.";
        }
      } catch (error) {
        if (validation) validation.textContent = `Could not load Reuters dataset sample: ${error.message}`;
      } finally {
        loadSampleBtn.textContent = original;
        loadSampleBtn.disabled = false;
        if (loading) loading.classList.remove("active");
      }

      textarea.focus();
    });
  }


  if (clearBtn && textarea) {
    clearBtn.addEventListener("click", () => {
      textarea.value = "";
      textarea.focus();
      if (validation) validation.textContent = "";
    });
  }

  form.addEventListener("submit", (event) => {
    if (!textarea) return;
    const raw = textarea.value.trim();
    const lines = raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    const approxSentenceCount =
      lines.length >= 3
        ? lines.length
        : raw
            .split(/[.!?]+(?=\s|$)/)
            .map((s) => s.trim())
            .filter(Boolean).length;

    if (approxSentenceCount < 3) {
      event.preventDefault();
      if (validation) validation.textContent = "Please enter at least 3 sentences.";
      return;
    }

    if (validation) validation.textContent = "";
    if (loading) loading.classList.add("active");
  });
}

async function readJsonResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const rawText = await response.text();
  const cleanText = rawText.replace(/^\uFEFF/, "").trim();

  if (!response.ok) {
    let msg = `Request failed with status ${response.status}`;
    try {
      const parsed = cleanText ? JSON.parse(cleanText) : null;
      if (parsed && parsed.error) msg = parsed.error;
    } catch (_error) {
      // Keep default error.
    }
    throw new Error(msg);
  }

  if (!contentType.includes("application/json")) {
    throw new Error("API did not return JSON.");
  }

  if (!cleanText) {
    throw new Error("Empty API response.");
  }

  try {
    return JSON.parse(cleanText);
  } catch (_error) {
    throw new Error("Invalid JSON in API response.");
  }
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  return readJsonResponse(response);
}

function setupCopyButtons() {
  const buttons = document.querySelectorAll(".copy-btn[data-target]");
  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      const targetId = button.getAttribute("data-target");
      if (!targetId) return;
      const target = document.getElementById(targetId);
      if (!target) return;

      const text = "value" in target ? target.value : target.textContent || "";
      if (!text.trim()) return;

      try {
        await navigator.clipboard.writeText(text);
        button.dataset.original = button.dataset.original || button.textContent || "Copy Output";
        button.textContent = "Copied";
        button.style.opacity = "0.7";
        setTimeout(() => {
          button.textContent = button.dataset.original || "Copy Output";
          button.style.opacity = "1";
        }, 1200);
      } catch (_error) {
        const original = button.textContent;
        button.textContent = "Failed";
        setTimeout(() => {
          button.textContent = original;
        }, 1200);
      }
    });
  });
}

function setupReorderFlowGraph() {
  const mount = document.getElementById("reorder-graph-mount");
  if (!mount) return;

  const payloadNode = document.getElementById("run-payload");
  if (!payloadNode) {
    mount.innerHTML = '<div class="graph-empty">Run a method to see sentence movement graph.</div>';
    return;
  }

  let payload = null;
  try {
    payload = JSON.parse(payloadNode.textContent || "{}");
  } catch (_error) {
    mount.innerHTML = '<div class="graph-empty">Could not parse run payload for graph rendering.</div>';
    return;
  }

  const inputSentences = splitSentences(payload.input_text || "");
  const baselineSentences = splitSentences(payload.baseline_text || "");
  const parsingSentences = splitSentences(payload.parsing_text || "");

  if (!inputSentences.length || (!baselineSentences.length && !parsingSentences.length)) {
    mount.innerHTML = '<div class="graph-empty">Graph will appear when output is generated.</div>';
    return;
  }

  renderReorderFlowSvg(mount, inputSentences, baselineSentences, parsingSentences);
}

function splitSentences(rawText) {
  return String(rawText || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function mapInputToOutput(inputSentences, outputSentences) {
  const buckets = new Map();
  outputSentences.forEach((sentence, index) => {
    if (!buckets.has(sentence)) buckets.set(sentence, []);
    buckets.get(sentence).push(index);
  });

  return inputSentences.map((sentence) => {
    const queue = buckets.get(sentence);
    if (!queue || !queue.length) return -1;
    return queue.shift();
  });
}

function renderReorderFlowSvg(mount, inputSentences, baselineSentences, parsingSentences) {
  mount.innerHTML = "";

  const baselineMap = mapInputToOutput(inputSentences, baselineSentences);
  const parsingMap = mapInputToOutput(inputSentences, parsingSentences);

  const svgNS = "http://www.w3.org/2000/svg";
  const rowCount = Math.max(inputSentences.length, baselineSentences.length, parsingSentences.length, 1);
  const svgWidth = 980;
  const rowHeight = 52;
  const nodeHeight = 36;
  const topPadding = 62;
  const bottomPadding = 28;
  const svgHeight = topPadding + rowCount * rowHeight + bottomPadding;

  const inputX = 24;
  const baselineX = 360;
  const parsingX = 696;
  const nodeWidth = 260;

  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${svgWidth} ${svgHeight}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Sentence arrangement flow graph");

  const bg = document.createElementNS(svgNS, "rect");
  bg.setAttribute("x", "0");
  bg.setAttribute("y", "0");
  bg.setAttribute("width", String(svgWidth));
  bg.setAttribute("height", String(svgHeight));
  bg.setAttribute("fill", "rgba(255,255,255,0.01)");
  svg.appendChild(bg);

  drawColumnHeading(svg, svgNS, inputX, 34, "Input Order");
  drawColumnHeading(svg, svgNS, baselineX, 34, "Baseline Output");
  drawColumnHeading(svg, svgNS, parsingX, 34, "Parsing Output");

  const centerY = (index) => topPadding + index * rowHeight + nodeHeight / 2;
  const curveX1 = inputX + nodeWidth + 70;
  const curveX2 = baselineX - 70;
  const curveX3 = parsingX - 70;

  baselineMap.forEach((mappedIndex, inputIndex) => {
    if (mappedIndex < 0) return;
    const path = document.createElementNS(svgNS, "path");
    const y1 = centerY(inputIndex);
    const y2 = centerY(mappedIndex);
    path.setAttribute(
      "d",
      `M ${inputX + nodeWidth} ${y1} C ${curveX1} ${y1}, ${curveX2} ${y2}, ${baselineX} ${y2}`
    );
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "rgba(147, 197, 253, 0.72)");
    path.setAttribute("stroke-width", "2.2");
    path.setAttribute("stroke-linecap", "round");
    svg.appendChild(path);
  });

  parsingMap.forEach((mappedIndex, inputIndex) => {
    if (mappedIndex < 0) return;
    const path = document.createElementNS(svgNS, "path");
    const y1 = centerY(inputIndex);
    const y2 = centerY(mappedIndex);
    path.setAttribute(
      "d",
      `M ${inputX + nodeWidth} ${y1} C ${curveX1} ${y1}, ${curveX3} ${y2}, ${parsingX} ${y2}`
    );
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "rgba(52, 211, 153, 0.72)");
    path.setAttribute("stroke-width", "2.2");
    path.setAttribute("stroke-linecap", "round");
    svg.appendChild(path);
  });

  drawSentenceColumn(
    svg,
    svgNS,
    inputX,
    nodeWidth,
    nodeHeight,
    topPadding,
    rowHeight,
    inputSentences,
    "rgba(147, 197, 253, 0.22)",
    "rgba(147, 197, 253, 0.42)"
  );
  drawSentenceColumn(
    svg,
    svgNS,
    baselineX,
    nodeWidth,
    nodeHeight,
    topPadding,
    rowHeight,
    baselineSentences,
    "rgba(59, 130, 246, 0.18)",
    "rgba(147, 197, 253, 0.34)"
  );
  drawSentenceColumn(
    svg,
    svgNS,
    parsingX,
    nodeWidth,
    nodeHeight,
    topPadding,
    rowHeight,
    parsingSentences,
    "rgba(16, 185, 129, 0.16)",
    "rgba(52, 211, 153, 0.34)"
  );

  if (!baselineSentences.length) {
    drawNoOutputLabel(svg, svgNS, baselineX + nodeWidth / 2, topPadding + 18, "No baseline output");
  }
  if (!parsingSentences.length) {
    drawNoOutputLabel(svg, svgNS, parsingX + nodeWidth / 2, topPadding + 18, "No parsing output");
  }

  mount.appendChild(svg);
}

function drawColumnHeading(svg, svgNS, x, y, label) {
  const heading = document.createElementNS(svgNS, "text");
  heading.setAttribute("x", String(x + 2));
  heading.setAttribute("y", String(y));
  heading.setAttribute("fill", "rgba(255,255,255,0.82)");
  heading.setAttribute("font-size", "13");
  heading.setAttribute("font-family", "Segoe UI, Arial, sans-serif");
  heading.setAttribute("font-weight", "600");
  heading.textContent = label;
  svg.appendChild(heading);
}

function drawNoOutputLabel(svg, svgNS, x, y, label) {
  const text = document.createElementNS(svgNS, "text");
  text.setAttribute("x", String(x));
  text.setAttribute("y", String(y));
  text.setAttribute("fill", "rgba(255,255,255,0.5)");
  text.setAttribute("font-size", "12");
  text.setAttribute("font-family", "Segoe UI, Arial, sans-serif");
  text.setAttribute("text-anchor", "middle");
  text.textContent = label;
  svg.appendChild(text);
}

function drawSentenceColumn(svg, svgNS, x, width, height, topPadding, rowHeight, sentences, fillColor, strokeColor) {
  sentences.forEach((sentence, index) => {
    const y = topPadding + index * rowHeight;

    const rect = document.createElementNS(svgNS, "rect");
    rect.setAttribute("x", String(x));
    rect.setAttribute("y", String(y));
    rect.setAttribute("rx", "9");
    rect.setAttribute("ry", "9");
    rect.setAttribute("width", String(width));
    rect.setAttribute("height", String(height));
    rect.setAttribute("fill", fillColor);
    rect.setAttribute("stroke", strokeColor);
    rect.setAttribute("stroke-width", "1");
    svg.appendChild(rect);

    const indexText = document.createElementNS(svgNS, "text");
    indexText.setAttribute("x", String(x + 10));
    indexText.setAttribute("y", String(y + 23));
    indexText.setAttribute("fill", "rgba(255,255,255,0.84)");
    indexText.setAttribute("font-size", "12");
    indexText.setAttribute("font-family", "Segoe UI, Arial, sans-serif");
    indexText.setAttribute("font-weight", "600");
    indexText.textContent = `#${index + 1}`;
    svg.appendChild(indexText);

    const sentenceText = document.createElementNS(svgNS, "text");
    sentenceText.setAttribute("x", String(x + 44));
    sentenceText.setAttribute("y", String(y + 23));
    sentenceText.setAttribute("fill", "rgba(255,255,255,0.74)");
    sentenceText.setAttribute("font-size", "12");
    sentenceText.setAttribute("font-family", "Segoe UI, Arial, sans-serif");
    sentenceText.textContent = truncateSentence(sentence, 32);
    svg.appendChild(sentenceText);
  });
}

function truncateSentence(sentence, limit) {
  const text = String(sentence || "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 1)}...`;
}

async function loadHistoryItems(limit = 40) {
  const payload = await requestJson(`${HISTORY_API}?limit=${encodeURIComponent(String(limit))}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  return Array.isArray(payload.items) ? payload.items : [];
}

async function createHistoryItem(record) {
  await requestJson(HISTORY_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(record),
  });
}

async function deleteHistoryItem(id) {
  await requestJson(`${HISTORY_API}/${encodeURIComponent(String(id))}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}

async function clearHistoryItems() {
  await requestJson(HISTORY_API, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
}

async function saveRunPayloadToHistory() {
  const payloadNode = document.getElementById("run-payload");
  if (!payloadNode) return;

  try {
    const payload = JSON.parse(payloadNode.textContent || "{}");
    const methodLabelMap = {
      baseline: "Run Baseline",
      parser: "Run Parsing",
      compare: "Compare Both",
    };

    const record = {
      method: payload.method || "compare",
      method_label: methodLabelMap[payload.method] || "Run",
      input_text: payload.input_text || "",
      baseline_text: payload.baseline_text || "",
      parsing_text: payload.parsing_text || "",
      baseline_score: payload.baseline_score,
      parsing_score: payload.parsing_score,
    };

    if (!record.input_text.trim()) return;

    const latest = await loadHistoryItems(1);
    const last = latest[0];
    const isDuplicate =
      last &&
      last.method === record.method &&
      last.input_text === record.input_text &&
      last.baseline_text === record.baseline_text &&
      last.parsing_text === record.parsing_text;

    if (!isDuplicate) {
      await createHistoryItem(record);
    }
  } catch (_error) {
    // Ignore malformed payload and network failures on non-history pages.
  }
}

async function setupHistoryPage() {
  const historyList = document.getElementById("history-list");
  if (!historyList) return;

  const clearBtn = document.getElementById("clear-history");

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function render() {
    historyList.innerHTML = '<div class="history-empty">Loading history...</div>';

    let items = [];
    try {
      items = await loadHistoryItems();
    } catch (error) {
      historyList.innerHTML = `<div class="history-empty">Could not load history: ${escapeHtml(error.message)}</div>`;
      return;
    }

    if (!items.length) {
      historyList.innerHTML = '<div class="history-empty">No runs yet. Use the Reorder page to generate outputs.</div>';
      return;
    }

    historyList.innerHTML = items
      .map((item) => {
        const when = new Date(item.ts).toLocaleString();
        const baseline = item.baseline_text
          ? `<div class="history-block"><span class="mini-label">Baseline</span><pre>${escapeHtml(item.baseline_text)}</pre></div>`
          : "";
        const parsing = item.parsing_text
          ? `<div class="history-block"><span class="mini-label">Parsing</span><pre>${escapeHtml(item.parsing_text)}</pre></div>`
          : "";
        const scores = [
          item.baseline_score !== null && item.baseline_score !== undefined ? `Baseline: ${Math.round(item.baseline_score * 100)}%` : null,
          item.parsing_score !== null && item.parsing_score !== undefined ? `Parsing: ${Math.round(item.parsing_score * 100)}%` : null,
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="history-item card">
            <div class="history-item-head">
              <strong>${escapeHtml(item.method_label || "Run")}</strong>
              <span class="history-time">${escapeHtml(when)}</span>
            </div>
            <div class="history-block">
              <span class="mini-label">Input</span>
              <pre>${escapeHtml(item.input_text)}</pre>
            </div>
            ${baseline}
            ${parsing}
            ${scores ? `<p class="score">${escapeHtml(scores)}</p>` : ""}
            <button class="copy-btn history-remove" type="button" data-id="${escapeHtml(item.id)}">Remove</button>
          </article>
        `;
      })
      .join("");

    historyList.querySelectorAll(".history-remove").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        if (!id) return;

        try {
          await deleteHistoryItem(id);
          await render();
        } catch (error) {
          alert(`Could not remove item: ${error.message}`);
        }
      });
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      try {
        await clearHistoryItems();
        await render();
      } catch (error) {
        alert(`Could not clear history: ${error.message}`);
      }
    });
  }

  await render();
}
