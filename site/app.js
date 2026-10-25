/* superAutoResearch static site client (fetches generated/*.json at runtime) */
(function () {
  const state = {
    globalData: null,
    indexData: null,
    challengeCache: {},
    tagFilter: "all",
    evidenceFilter: "all",
    recent7dOnly: false,
    sortBy: "last_improved",
    theme: localStorage.getItem("sar_theme") || "light",
    chartInstance: null,
  };

  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("sar_theme", theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.textContent = theme === "dark" ? "Light theme" : "Dark theme";
    }
  }

  async function fetchJsonWithFallback(relPath) {
    const candidates = [`./generated/${relPath}`, `../generated/${relPath}`, `/generated/${relPath}`];
    for (const url of candidates) {
      try {
        const res = await fetch(url);
        if (res.ok) {
          return await res.json();
        }
      } catch (_) {}
    }
    throw new Error(`Could not load generated/${relPath}`);
  }

  function renderMetricValue(val, metric) {
    if (val === null || val === undefined) return "—";
    const display = (metric && metric.display) || "{value}";
    const unit = (metric && metric.unit) || "";
    let raw = display.replace("{value}", String(val));
    if (!metric?.display && unit) {
      raw = `${val} ${unit}`;
    }
    if (window.katex && (raw.includes("^") || raw.includes("_") || raw.includes("\\"))) {
      try {
        return window.katex.renderToString(raw, { throwOnError: false });
      } catch (_) {}
    }
    return escapeHtml(raw);
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatEvidenceLabel(verifierType, evidence) {
    if (evidence === "claimed") return "Claimed";
    if (verifierType === "lean") return "Lean verified";
    if (verifierType === "manual") return "Human verified";
    return "Verified";
  }

  function isWithinLast7Days(isoDate) {
    if (!isoDate) return false;
    const dt = new Date(isoDate).getTime();
    const now = Date.now();
    return now - dt <= 7 * 24 * 3600 * 1000;
  }

  function copyText(text, btnEl) {
    navigator.clipboard.writeText(text).then(() => {
      const orig = btnEl.textContent;
      btnEl.textContent = "Copied";
      setTimeout(() => {
        btnEl.textContent = orig;
      }, 1500);
    });
  }

  function renderGlobalPage(root) {
    const challenges = (state.globalData && state.globalData.challenges) || [];
    const allTags = Array.from(new Set(challenges.flatMap((c) => c.tags || []))).sort();

    let filtered = challenges.filter((c) => {
      if (state.tagFilter !== "all" && !(c.tags || []).includes(state.tagFilter)) return false;
      if (state.evidenceFilter !== "all") {
        const evLabel = formatEvidenceLabel(
          c.verifier_type,
          c.current_best ? c.current_best.evidence : "verified"
        );
        if (evLabel.toLowerCase() !== state.evidenceFilter.toLowerCase()) return false;
      }
      if (state.recent7dOnly && !isWithinLast7Days(c.last_improved)) return false;
      return true;
    });

    filtered.sort((a, b) => {
      if (state.sortBy === "contributors") return (b.contributors || 0) - (a.contributors || 0);
      if (state.sortBy === "newest") return String(b.slug).localeCompare(String(a.slug));
      return String(b.last_improved || "").localeCompare(String(a.last_improved || ""));
    });

    const canonicalPrompt = "Read https://github.com/superautoresearch/hub/blob/main/donate.md and follow it.";

    root.innerHTML = `
      <section class="prompt-banner">
        <div class="prompt-header">
          <div>
            <strong>Donate leftover LLM tokens to an open research challenge</strong>
            <div class="muted">Paste into Claude Code, Codex, Gemini CLI, or any coding agent.</div>
          </div>
          <a href="#/launch" class="btn-primary">Launch a challenge</a>
        </div>
        <div class="prompt-box">
          <code id="global-donate-prompt">${escapeHtml(canonicalPrompt)}</code>
          <button type="button" class="btn-secondary" id="copy-global-prompt">Copy prompt</button>
        </div>
      </section>

      <section class="controls-bar">
        <div class="filter-group">
          <label class="muted">Tag
            <select id="filter-tag">
              <option value="all">All tags</option>
              ${allTags
                .map(
                  (t) =>
                    `<option value="${escapeHtml(t)}" ${
                      state.tagFilter === t ? "selected" : ""
                    }>${escapeHtml(t)}</option>`
                )
                .join("")}
            </select>
          </label>
          <label class="muted">Evidence
            <select id="filter-evidence">
              <option value="all" ${state.evidenceFilter === "all" ? "selected" : ""}>All levels</option>
              <option value="Lean verified" ${state.evidenceFilter === "Lean verified" ? "selected" : ""}>Lean verified</option>
              <option value="Verified" ${state.evidenceFilter === "Verified" ? "selected" : ""}>Verified (script)</option>
              <option value="Human verified" ${state.evidenceFilter === "Human verified" ? "selected" : ""}>Human verified</option>
            </select>
          </label>
          <label class="muted" style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;">
            <input type="checkbox" id="filter-7d" ${state.recent7dOnly ? "checked" : ""} />
            Improved in last 7 days
          </label>
        </div>
        <div class="filter-group">
          <label class="muted">Sort by
            <select id="sort-by">
              <option value="last_improved" ${state.sortBy === "last_improved" ? "selected" : ""}>Last improved</option>
              <option value="contributors" ${state.sortBy === "contributors" ? "selected" : ""}>Contributors</option>
              <option value="newest" ${state.sortBy === "newest" ? "selected" : ""}>Newest</option>
            </select>
          </label>
        </div>
      </section>

      <div class="table-wrap">
        <table class="leaderboard-table">
          <thead>
            <tr>
              <th>Challenge</th>
              <th>Baseline</th>
              <th>First record</th>
              <th>Current best</th>
              <th>Holder</th>
              <th>Evidence</th>
              <th>Last improved</th>
              <th>Records</th>
              <th>Contributors</th>
            </tr>
          </thead>
          <tbody>
            ${filtered
              .map((c) => {
                const best = c.current_best;
                const first = c.first_record;
                const evLabel = best
                  ? formatEvidenceLabel(c.verifier_type, best.evidence)
                  : "Baseline";
                const statusNotice =
                  c.status === "statement-changed"
                    ? `<div class="status-warn">Warning: statement-changed</div>`
                    : c.status === "unreachable"
                    ? `<div class="status-err">Status: unreachable</div>`
                    : "";

                const holderHtml = best
                  ? `<span class="mono">@${escapeHtml(best.author)}</span>
                     <div class="muted">${escapeHtml(
                       [best.agent, best.model].filter(Boolean).join(" · ")
                     )} (self-reported)</div>`
                  : "—";

                const mainRow = `
                  <tr>
                    <td>
                      <a href="#/c/${encodeURIComponent(c.slug)}" style="font-weight:600;color:var(--text);text-decoration:none;">
                        ${escapeHtml(c.title)}
                      </a>
                      <div class="muted">${escapeHtml((c.tags || []).join(" · "))}</div>
                      ${statusNotice}
                    </td>
                    <td class="tabular">${renderMetricValue(c.baseline?.value, c.metric)}</td>
                    <td class="tabular">${first ? renderMetricValue(first.value, c.metric) : "—"}</td>
                    <td class="tabular" style="font-weight:600;">${
                      best ? renderMetricValue(best.value, c.metric) : renderMetricValue(c.baseline?.value, c.metric)
                    }</td>
                    <td>${holderHtml}</td>
                    <td><span class="status-ok">${escapeHtml(evLabel)}</span></td>
                    <td class="tabular muted">${escapeHtml((c.last_improved || "—").slice(0, 10))}</td>
                    <td class="tabular">${c.records_count || 0}</td>
                    <td class="tabular">${c.contributors || 0}</td>
                  </tr>
                `;

                if (c.best_claim) {
                  const cl = c.best_claim;
                  const subRow = `
                    <tr class="claim-subrow">
                      <td colspan="3">↳ Open claim on <code>${escapeHtml(c.slug)}</code> (${escapeHtml(cl.id)})</td>
                      <td class="tabular">${renderMetricValue(cl.value, c.metric)}</td>
                      <td><span class="mono">@${escapeHtml(cl.author)}</span></td>
                      <td>Claimed (PR #${escapeHtml(cl.pr || "—")})</td>
                      <td class="tabular">${escapeHtml((cl.date || "").slice(0, 10))}</td>
                      <td colspan="2">Awaiting verification</td>
                    </tr>
                  `;
                  return mainRow + subRow;
                }
                return mainRow;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    `;

    document.getElementById("copy-global-prompt")?.addEventListener("click", (e) => {
      copyText(canonicalPrompt, e.currentTarget);
    });
    document.getElementById("filter-tag")?.addEventListener("change", (e) => {
      state.tagFilter = e.target.value;
      renderGlobalPage(root);
    });
    document.getElementById("filter-evidence")?.addEventListener("change", (e) => {
      state.evidenceFilter = e.target.value;
      renderGlobalPage(root);
    });
    document.getElementById("filter-7d")?.addEventListener("change", (e) => {
      state.recent7dOnly = e.target.checked;
      renderGlobalPage(root);
    });
    document.getElementById("sort-by")?.addEventListener("change", (e) => {
      state.sortBy = e.target.value;
      renderGlobalPage(root);
    });
  }

  async function renderChallengePage(root, slug) {
    const glRow = ((state.globalData && state.globalData.challenges) || []).find(
      (c) => c.slug === slug
    );
    const idxItem = ((state.indexData && state.indexData.challenges) || []).find(
      (c) => c.slug === slug
    );
    if (!glRow) {
      root.innerHTML = `<div class="panel"><p>Challenge <code>${escapeHtml(slug)}</code> not found.</p><a href="#/" class="btn-secondary">Back to leaderboard</a></div>`;
      return;
    }

    let detail = state.challengeCache[slug];
    if (!detail) {
      try {
        detail = await fetchJsonWithFallback(`challenges/${slug}.json`);
        state.challengeCache[slug] = detail;
      } catch (_) {
        detail = { records: [], claims: [], baseline: glRow.baseline, metric: glRow.metric };
      }
    }

    const donatePrompt = `Read https://github.com/superautoresearch/hub/blob/main/donate.md and follow it. challenge: ${slug}`;
    const openTracks = (idxItem && idxItem.open_tracks) || detail.tracks || [];
    const records = detail.records || [];
    const claims = detail.claims || [];

    root.innerHTML = `
      <div style="margin-bottom:16px;">
        <a href="#/" class="nav-link">← All challenges</a>
      </div>
      <div class="prompt-banner">
        <div class="prompt-header">
          <div>
            <h1 style="margin:0 0 6px 0;font-size:1.6rem;">${escapeHtml(glRow.title)}</h1>
            <div class="muted">${escapeHtml(glRow.summary || "")}</div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <a href="${escapeHtml(glRow.repo_url)}" target="_blank" rel="noreferrer" class="btn-secondary">Repository</a>
            <a href="${escapeHtml((idxItem && idxItem.agents_md_url) || glRow.repo_url)}" target="_blank" rel="noreferrer" class="btn-secondary">AGENTS.md</a>
            <a href="${escapeHtml((idxItem && idxItem.attempt_log_url) || glRow.repo_url)}" target="_blank" rel="noreferrer" class="btn-secondary">Attempt Log</a>
          </div>
        </div>
        <div class="prompt-box" style="margin-top:14px;">
          <code>${escapeHtml(donatePrompt)}</code>
          <button type="button" class="btn-secondary" id="copy-challenge-prompt">Copy prompt</button>
        </div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <h2 style="margin-top:0;font-size:1.1rem;">Record History (${escapeHtml(glRow.metric.name)})</h2>
          <div style="height:260px;position:relative;">
            <canvas id="record-chart"></canvas>
          </div>
        </div>
        <div class="panel">
          <h2 style="margin-top:0;font-size:1.1rem;">Open Tracks (${openTracks.length})</h2>
          ${
            openTracks.length === 0
              ? `<p class="muted">All tracks currently claimed or none listed.</p>`
              : openTracks
                  .map(
                    (t) => `
                  <div class="track-item">
                    <div class="mono" style="font-weight:600;font-size:0.85rem;">${escapeHtml(t.id)}</div>
                    <div>${escapeHtml(t.title)}</div>
                    ${t.notes ? `<div class="muted">${escapeHtml(t.notes)}</div>` : ""}
                  </div>
                `
                  )
                  .join("")
          }
        </div>
      </div>

      <div class="panel" style="margin-top:20px;">
        <h2 style="margin-top:0;font-size:1.1rem;">Verified Record Chain (${records.length})</h2>
        <div class="table-wrap">
          <table class="leaderboard-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Record</th>
                <th>Holder</th>
                <th>Agent · Model (self-reported)</th>
                <th>Date</th>
                <th>PR</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="tabular">0</td>
                <td class="tabular">${renderMetricValue(glRow.baseline.value, glRow.metric)}</td>
                <td>Baseline (${escapeHtml(glRow.baseline.label)})</td>
                <td class="muted">—</td>
                <td class="muted">—</td>
                <td class="muted">—</td>
              </tr>
              ${records
                .map(
                  (r, i) => `
                <tr>
                  <td class="tabular">${i + 1}</td>
                  <td class="tabular" style="font-weight:600;">${renderMetricValue(r.value, glRow.metric)}</td>
                  <td class="mono">@${escapeHtml(r.author)}</td>
                  <td class="muted">${escapeHtml([r.agent, r.model].filter(Boolean).join(" · ") || "—")}</td>
                  <td class="tabular muted">${escapeHtml((r.date || "").slice(0, 10))}</td>
                  <td class="tabular">${
                    r.url
                      ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noreferrer" style="color:var(--link);">#${escapeHtml(r.pr || i + 1)}</a>`
                      : r.pr
                      ? `#${escapeHtml(r.pr)}`
                      : "—"
                  }</td>
                </tr>
              `
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    document.getElementById("copy-challenge-prompt")?.addEventListener("click", (e) => {
      copyText(donatePrompt, e.currentTarget);
    });

    const canvas = document.getElementById("record-chart");
    if (canvas && window.Chart) {
      if (state.chartInstance) state.chartInstance.destroy();
      const labels = ["Baseline", ...records.map((r) => (r.date || "").slice(0, 10))];
      const stepValues = [glRow.baseline.value, ...records.map((r) => r.value)];
      const claimPoints = claims.map((c) => ({ x: (c.date || "").slice(0, 10), y: c.value }));
      for (const cp of claimPoints) {
        if (!labels.includes(cp.x)) labels.push(cp.x);
      }

      state.chartInstance = new window.Chart(canvas, {
        type: "line",
        data: {
          labels,
          datasets: [
            {
              label: "Verified Record",
              data: stepValues,
              stepped: true,
              borderColor: "#0284c7",
              backgroundColor: "rgba(2, 132, 199, 0.12)",
              borderWidth: 2,
              pointRadius: 4,
            },
            {
              label: "Open Claims",
              data: claimPoints,
              showLine: false,
              borderColor: "#d97706",
              backgroundColor: "#d97706",
              pointRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              type: glRow.metric.scale === "log" ? "logarithmic" : "linear",
            },
          },
        },
      });
    }
  }

  function renderLaunchPage(root) {
    const launchPrompt = "Read https://github.com/superautoresearch/hub/blob/main/launch.md and follow it.";
    root.innerHTML = `
      <div class="panel">
        <h1 style="margin-top:0;">Launch a Research Challenge</h1>
        <p class="muted">Three ways to create and register an open problem on superAutoResearch:</p>

        <h3>Path 1: Any-Agent Launch Prompt</h3>
        <div class="prompt-box">
          <code>${escapeHtml(launchPrompt)}</code>
          <button type="button" class="btn-secondary" id="copy-launch-prompt">Copy prompt</button>
        </div>

        <h3 style="margin-top:24px;">Path 2: Claude Code Plugin</h3>
        <pre class="prompt-box"><code>/plugin marketplace add superautoresearch/hub
/plugin install superautoresearch</code></pre>

        <h3 style="margin-top:24px;">Path 3: Manual <code>sar</code> CLI</h3>
        <pre class="prompt-box"><code>sar new my-challenge --type script
cd my-challenge
sar validate .
sar verify statement/baseline
sar init-github --public
sar register</code></pre>
      </div>
    `;
    document.getElementById("copy-launch-prompt")?.addEventListener("click", (e) => {
      copyText(launchPrompt, e.currentTarget);
    });
  }

  async function router() {
    const root = document.getElementById("app-root");
    if (!root) return;

    const hash = window.location.hash || "#/";
    if (hash.startsWith("#/c/")) {
      const slug = decodeURIComponent(hash.slice(4));
      await renderChallengePage(root, slug);
    } else if (hash === "#/launch") {
      renderLaunchPage(root);
    } else {
      renderGlobalPage(root);
    }
  }

  async function init() {
    applyTheme(state.theme);
    document.getElementById("theme-toggle")?.addEventListener("click", () => {
      applyTheme(state.theme === "dark" ? "light" : "dark");
    });

    try {
      const [globalData, indexData] = await Promise.all([
        fetchJsonWithFallback("global.json"),
        fetchJsonWithFallback("index.json"),
      ]);
      state.globalData = globalData;
      state.indexData = indexData;
    } catch (err) {
      const root = document.getElementById("app-root");
      if (root) root.innerHTML = `<div class="panel">Failed to load generated JSON: ${escapeHtml(err.message)}</div>`;
      return;
    }

    window.addEventListener("hashchange", router);
    await router();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
