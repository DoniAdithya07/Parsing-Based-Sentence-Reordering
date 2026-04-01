const HISTORY_KEY = "reorder_run_history_v1";

const EXAMPLE_TEXTS = {
  story: [
    "Finally, the villagers celebrated in the square.",
    "First, a heavy storm blocked the main road.",
    "Then, volunteers cleared fallen trees overnight.",
  ].join("\n"),
  process: [
    "Finally, the model predictions are displayed to the user.",
    "First, the input text is cleaned and split into sentences.",
    "Then, each sentence is parsed for syntax-aware features.",
  ].join("\n"),
  technical: [
    "Finally, the API returns JSON with ordered outputs.",
    "First, the request payload is validated by the backend.",
    "Then, baseline and parser methods compute ranking scores.",
  ].join("\n"),
};

document.addEventListener("DOMContentLoaded", () => {
  setupActiveNav();
  setupScrollReveal();
  setupReorderForm();
  setupCopyButtons();
  saveRunPayloadToHistory();
  setupHistoryPage();
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
  const storyBtn = document.getElementById("load-story");
  const processBtn = document.getElementById("load-process");
  const technicalBtn = document.getElementById("load-technical");

  const fallbackSample = [
    "said . The deal is on track , officials",
    "after the update . markets reacted quickly",
    "investors welcomed the decision , analysts said",
  ].join("\n");

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
          if (validation) validation.textContent = "";
        } else {
          textarea.value = fallbackSample;
          if (validation) validation.textContent = "Sample API returned empty data, fallback loaded.";
        }
      } catch (error) {
        textarea.value = fallbackSample;
        if (validation) validation.textContent = `Could not load sample: ${error.message}`;
      } finally {
        loadSampleBtn.textContent = original;
        loadSampleBtn.disabled = false;
        if (loading) loading.classList.remove("active");
      }

      textarea.focus();
    });
  }

  bindExampleButton(storyBtn, textarea, validation, EXAMPLE_TEXTS.story);
  bindExampleButton(processBtn, textarea, validation, EXAMPLE_TEXTS.process);
  bindExampleButton(technicalBtn, textarea, validation, EXAMPLE_TEXTS.technical);

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

function bindExampleButton(button, textarea, validation, sampleText) {
  if (!button || !textarea) return;
  button.addEventListener("click", () => {
    textarea.value = sampleText;
    textarea.focus();
    if (validation) validation.textContent = "Example loaded.";
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

function readHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function writeHistory(items) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 40)));
}

function saveRunPayloadToHistory() {
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
      ts: Date.now(),
      method: payload.method || "compare",
      method_label: methodLabelMap[payload.method] || "Run",
      input_text: payload.input_text || "",
      baseline_text: payload.baseline_text || "",
      parsing_text: payload.parsing_text || "",
      baseline_score: payload.baseline_score,
      parsing_score: payload.parsing_score,
    };

    if (!record.input_text.trim()) return;

    const items = readHistory();
    const last = items[0];
    const isDuplicate =
      last &&
      last.method === record.method &&
      last.input_text === record.input_text &&
      last.baseline_text === record.baseline_text &&
      last.parsing_text === record.parsing_text;

    if (!isDuplicate) {
      items.unshift(record);
      writeHistory(items);
    }
  } catch (_error) {
    // Ignore malformed payload.
  }
}

function setupHistoryPage() {
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

  function render() {
    const items = readHistory();
    if (!items.length) {
      historyList.innerHTML = '<div class="history-empty">No runs yet. Use Reorder page buttons to generate outputs.</div>';
      return;
    }

    historyList.innerHTML = items
      .map((item, index) => {
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
              <strong>${escapeHtml(item.method_label)}</strong>
              <span class="history-time">${escapeHtml(when)}</span>
            </div>
            <div class="history-block">
              <span class="mini-label">Input</span>
              <pre>${escapeHtml(item.input_text)}</pre>
            </div>
            ${baseline}
            ${parsing}
            ${scores ? `<p class="score">${escapeHtml(scores)}</p>` : ""}
            <button class="copy-btn history-remove" type="button" data-index="${index}">Remove</button>
          </article>
        `;
      })
      .join("");

    historyList.querySelectorAll(".history-remove").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.getAttribute("data-index"));
        if (Number.isNaN(idx)) return;
        const items = readHistory();
        items.splice(idx, 1);
        writeHistory(items);
        render();
      });
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      localStorage.removeItem(HISTORY_KEY);
      render();
    });
  }

  render();
}