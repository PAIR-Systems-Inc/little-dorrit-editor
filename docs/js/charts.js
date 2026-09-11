/* Interactive comparisons, using the exact table metrics and a dated price snapshot. */
(function () {
    "use strict";
    const vendors = {
        OpenAI: ["openai", "#436c79", "OA"], Anthropic: ["anthropic", "#ca8b70", "A"],
        Google: ["google-color", "#538bca", "G"], Meta: ["meta-color", "#5079d0", "M"],
        Moonshot: ["moonshot", "#617862", "K"], Alibaba: ["qwen-color", "#8a79bf", "Q"],
        DeepSeek: ["deepseek-color", "#5b83c8", "DS"], Mistral: ["mistral-color", "#d6924f", "Mi"],
        MiniMax: ["minimax-color", "#c16e8c", "MM"], Microsoft: ["microsoft-color", "#6c928a", "MS"],
        xAI: ["xai", "#6d747c", "X"], SpaceXAI: ["xai", "#6d747c", "X"],
        "Zhipu AI": ["zai", "#769697", "Z"], StepFun: ["stepfun-color", "#7293b0", "S"],
    };
    const state = { rows: [], prices: {}, view: "performance", vendor: "", year: "", selected: null, snapshot: null, priceError: false };
    const $ = id => document.getElementById(id);
    const esc = value => String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const money = n => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: n > 0 && n < .01 ? 4 : 2 }).format(n);
    const name = row => row.model.replace(/\s*\(OR\)/g, "");
    const vendor = row => vendors[row.vendor] || [null, "#72909b", row.vendor.slice(0, 2).toUpperCase() || "?"];
    const metric = () => $("chart-metric").value;
    const volume = () => Number($("chart-workload").value);
    const cost = row => row.price.input_per_million + volume() * row.price.output_per_million;
    const priced = price => price && [price.input_per_million, price.output_per_million].every(v => typeof v === "number" && Number.isFinite(v) && v >= 0);
    function niceMax(value) {
        const power = 10 ** Math.floor(Math.log10(Math.max(value, .01)));
        return [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find(n => n * power >= value) * power;
    }

    function logCostScale(costs, left, right, compact) {
        const positive = costs.filter(value => value > 0);
        const hasFree = costs.some(value => value === 0);
        if (!positive.length) return { x: () => (left + right) / 2, ticks: [0], hasFree, logLeft: null };
        const min = Math.min(...positive), max = Math.max(...positive);
        const candidates = [];
        for (let exponent = Math.floor(Math.log10(min)) - 1; exponent <= Math.ceil(Math.log10(max)) + 1; exponent++) {
            for (const multiple of [1, 2, 5]) candidates.push(multiple * 10 ** exponent);
        }
        let lowIndex = candidates.findLastIndex(value => value <= min);
        let highIndex = candidates.findIndex(value => value >= max);
        // Give a single price (including ties) a meaningful, nonzero domain.
        if (lowIndex === highIndex) { lowIndex--; highIndex++; }
        const low = candidates[lowIndex], high = candidates[highIndex];
        // Zero has no logarithm. A separate labeled gutter keeps free models
        // visible and eligible for the frontier without inventing a token price.
        const logLeft = left + (hasFree ? 48 : 0);
        const x = value => value === 0 ? left : logLeft + (Math.log10(value) - Math.log10(low)) / (Math.log10(high) - Math.log10(low)) * (right - logLeft);
        const ticks = hasFree ? [0] : [];
        const minSpacing = compact ? 58 : 62;
        for (const value of candidates.slice(lowIndex, highIndex + 1)) {
            const previous = ticks.at(-1);
            if (previous === undefined || previous === 0 || x(value) - x(previous) >= minSpacing) ticks.push(value);
        }
        // Always label both ends, removing a crowded intermediate tick if needed.
        if (ticks.at(-1) !== high) {
            if (ticks.at(-1) !== low && x(high) - x(ticks.at(-1)) < minSpacing) ticks.pop();
            ticks.push(high);
        }
        return { x, ticks, hasFree, logLeft };
    }

    // Ties at identical coordinates are all efficient. Strictly dominated ties are not.
    function pareto(rows, getCost = row => row.cost, getScore = row => row.f1Score) {
        return rows.filter(a => !rows.some(b => getCost(b) <= getCost(a) && getScore(b) >= getScore(a) && (getCost(b) < getCost(a) || getScore(b) > getScore(a))))
            .sort((a, b) => getCost(a) - getCost(b));
    }
    function mark(row) {
        const [icon, , mono] = vendor(row);
        return `<span class="vendor-mark" aria-hidden="true">${icon ? `<img src="assets/vendors/${icon}.svg" alt="" data-fallback="${esc(mono)}">` : esc(mono)}</span>`;
    }
    function label(row, rank) {
        const route = row.modelId.startsWith("or_") ? '<span class="route-badge">OR</span>' : '';
        return `<button type="button" class="chart-model" data-model="${esc(row.modelId)}" aria-label="Inspect ${esc(name(row))}"><span class="chart-rank">${rank}</span>${mark(row)}<span class="chart-model-name">${esc(name(row))}${esc(row.modelDisplaySuffix || "")}${route}</span></button>`;
    }
    function selection() {
        const row = state.rows.find(r => r.modelId === state.selected);
        $("chart-selection").hidden = !row;
        if (!row) return;
        const price = state.prices[row.modelId];
        let content = `<strong>${esc(name(row))}</strong> · F1 ${row.f1Score.toFixed(4)} · Precision ${row.precision.toFixed(4)} · Recall ${row.recall.toFixed(4)}`;
        if (priced(price)) {
            content += `<br>${esc(price.route)} · ${money(price.input_per_million)} input / ${money(price.output_per_million)} output per million tokens`;
            if (state.view === "value") content += ` · Illustrative workload: <strong>${money(cost({ price }))}</strong>`;
            // Source is a URL in our checked-in snapshot; constrain its scheme.
            if (/^https:\/\//.test(price.source)) content += `<br><a href="${esc(price.source)}" target="_blank" rel="noopener noreferrer">Pricing source ↗</a> · Verified ${esc(price.verified_at)}`;
        } else content += "<br>Verified token pricing is unavailable for this benchmark route.";
        if (row.modelDisplayNote) content += `<br>${esc(row.modelDisplayNote)}`;
        $("chart-selection").innerHTML = content;
    }
    function pickRows() {
        const selectedMetric = state.view === "performance" ? metric() : "f1Score";
        const filtered = state.rows.filter(r => (!state.vendor || r.vendor === state.vendor) && (!state.year || r.releaseYear === state.year))
            .sort((a, b) => b[selectedMetric] - a[selectedMetric]);
        const limit = $("chart-count").value;
        const contenders = limit === "all" ? filtered : filtered.slice(0, Number(limit));
        const missing = contenders.filter(r => !priced(state.prices[r.modelId])).length;
        let rows = contenders.map((r, index) => ({ ...r, chartRank: index + 1, price: state.prices[r.modelId] }));
        if (state.view !== "performance") rows = rows.filter(r => priced(r.price));
        let overBudget = 0;
        const budget = $("chart-budget");
        if (state.view === "value" && budget.value !== "" && budget.validity.valid) {
            const count = rows.length;
            rows = rows.filter(r => cost(r) <= Number(budget.value));
            overBudget = count - rows.length;
        }
        return { rows, missing, total: filtered.length, overBudget };
    }
    function axis(max, isPrice) {
        return `<div class="chart-axis"><span>MODEL</span><span class="chart-axis-ticks">${[0, .25, .5, .75, 1].map(v => `<span>${isPrice ? money(v * max) : (v * max).toFixed(2)}</span>`).join("")}</span><span style="text-align:right">${isPrice ? "USD / 1M" : "SCORE"}</span></div>`;
    }
    function bars(rows) {
        const isPrice = state.view === "price";
        const max = isPrice ? niceMax(Math.max(.01, ...rows.flatMap(r => [r.price.input_per_million, r.price.output_per_million]))) : 1;
        let html = isPrice ? '<div class="chart-legend"><span><i class="legend-key legend-input"></i>Input</span><span><i class="legend-key"></i>Output</span><span>Same scale · lower is cheaper</span></div>' : '';
        html += axis(max, isPrice);
        html += rows.map((row, i) => {
            let body;
            if (isPrice) {
                body = `<div class="chart-price-tracks">${["input", "output"].map(type => `<div class="chart-track" title="${type}: ${money(row.price[`${type}_per_million`])} / million"><div class="chart-bar ${type}-bar" style="width:${100 * row.price[`${type}_per_million`] / max}%"></div></div>`).join("")}</div><div class="chart-number chart-price-numbers">${money(row.price.input_per_million)}<br>${money(row.price.output_per_million)}</div>`;
            } else {
                const bounds = row.confidenceBounds;
                const ci = metric() === "f1Score" && $("chart-ci").checked && bounds ? `<span class="chart-ci" style="left:${bounds.low * 100}%;width:${(bounds.high - bounds.low) * 100}%" title="95% CI: ${bounds.low.toFixed(4)}–${bounds.high.toFixed(4)}"></span>` : '';
                body = `<div class="chart-track"><div class="chart-bar" style="width:${row[metric()] * 100}%"></div>${ci}</div><span class="chart-number">${row[metric()].toFixed(4)}</span>`;
            }
            return `<div class="chart-row" style="--bar-color:${vendor(row)[1]}">${label(row, row.chartRank)}${body}</div>`;
        }).join("");
        return html;
    }
    function scatter(rows) {
        const efficient = pareto(rows, cost);
        const efficientIds = new Set(efficient.map(r => r.modelId));
        const compact = window.matchMedia("(max-width: 700px)").matches;
        const width = compact ? 360 : 700, height = compact ? 350 : 420, left = 45, right = 28, top = 30, bottom = 58;
        const costScale = logCostScale(rows.map(cost), left, width - right, compact);
        const x = costScale.x;
        const y = n => height - bottom - n * (height - top - bottom);
        let svg = `<svg viewBox="0 0 ${width} ${height}" class="value-plot" role="group" aria-label="F1 on a linear axis versus estimated workload price on a logarithmic axis. Lower price is left; higher accuracy is up. Free models, if any, appear separately. Select a model for details.">`;
        const ticks = compact ? 2 : 4;
        for (let i = 0; i <= ticks; i++) {
            const v = i / ticks;
            svg += `<line x1="${left}" x2="${width - right}" y1="${y(v)}" y2="${y(v)}" stroke="#e4eae8" stroke-dasharray="3 5"/><text x="${left - 12}" y="${y(v) + 4}" text-anchor="end">${v.toFixed(2)}</text>`;
        }
        for (const tick of costScale.ticks) {
            svg += `<line x1="${x(tick)}" x2="${x(tick)}" y1="${top}" y2="${height - bottom}" stroke="#eef2f0"/><text class="cost-tick" x="${x(tick)}" y="${height - bottom + 25}" text-anchor="middle">${tick === 0 ? '$0 (free)' : money(tick)}</text>`;
        }
        if (costScale.hasFree && costScale.logLeft !== null) {
            const divider = (left + costScale.logLeft) / 2;
            svg += `<line x1="${divider}" x2="${divider}" y1="${top}" y2="${height - bottom}" stroke="#aebec2" stroke-dasharray="3 5"/>`;
        }
        svg += `<text x="${left}" y="16" class="axis-label">F1 ↑</text><text x="${width / 2}" y="${height - 7}" text-anchor="middle" class="axis-label">${compact ? 'Workload price · log scale (USD) →' : 'Estimated workload price (USD) · logarithmic scale →'}</text>`;
        svg += `<text x="${left + 12}" y="${top + 18}" style="fill:#8aa69a;font-size:10px">BETTER VALUE ↖</text>`;
        // Discrete frontier: each step is an available model, not interpolated performance.
        const unique = efficient.filter((r, i) => cost(r) > 0 && (i === 0 || cost(r) !== cost(efficient[i - 1]) || r.f1Score !== efficient[i - 1].f1Score));
        if (unique.length > 1) {
            const path = unique.map((r, i) => i === 0 ? `M${x(cost(r))},${y(r.f1Score)}` : `H${x(cost(r))} V${y(r.f1Score)}`).join(" ");
            svg += `<path d="${path}" fill="none" stroke="#267768" stroke-width="1.5" stroke-dasharray="4 4"/>`;
        }
        // Draw frontier last so a near-coincident dominated point cannot obscure it.
        const ordered = [...rows].sort((a, b) => Number(efficientIds.has(a.modelId)) - Number(efficientIds.has(b.modelId)));
        svg += ordered.map(row => {
            const [icon, , mono] = vendor(row), px = x(cost(row)), py = y(row.f1Score);
            const text = `${name(row)}, ${row.price.route}, F1 ${row.f1Score.toFixed(4)}, workload ${money(cost(row))}${efficientIds.has(row.modelId) ? ", Pareto frontier" : ""}`;
            return `<g class="value-point ${efficientIds.has(row.modelId) ? "frontier" : ""}" tabindex="0" role="button" data-model="${esc(row.modelId)}" aria-label="${esc(text)}"><title>${esc(text)}</title><circle cx="${px}" cy="${py}" r="12"/>${icon ? `<image href="assets/vendors/${icon}.svg" x="${px - 7}" y="${py - 7}" width="14" height="14"/>` : `<text x="${px}" y="${py + 3}">${esc(mono)}</text>`}</g>`;
        }).join("");
        svg += "</svg>";
        const sidebar = `<aside class="frontier-sidebar"><h3>On the frontier</h3><p>No displayed model is both cheaper and at least as accurate, or more accurate at the same price.</p>${efficient.map(row => `<button type="button" class="frontier-item" data-model="${esc(row.modelId)}"><strong>${esc(name(row))}${row.modelId.startsWith("or_") ? ' <span class="route-badge">OR</span>' : ''}</strong><span>${money(cost(row))} · F1 ${row.f1Score.toFixed(4)}</span></button>`).join("")}</aside>`;
        return `<div class="value-layout">${svg}${sidebar}</div><details class="chart-method"><summary>Inspect all ${rows.length} plotted models</summary>${rows.map((row, i) => `<div class="chart-row">${label(row, i + 1)}<span>F1 ${row.f1Score.toFixed(4)}</span><span class="chart-number">${money(cost(row))}</span></div>`).join("")}</details>`;
    }
    function render() {
        const view = state.view;
        const isTable = view === "table" || view === "details";
        $("chart-panel").hidden = isTable;
        $("table-panel").hidden = view !== "table";
        $("details-panel").hidden = view !== "details";
        if (isTable) return;
        const isPerformance = view === "performance", isValue = view === "value";
        $("metric-control").hidden = !isPerformance;
        $("ci-control").hidden = !isPerformance || metric() !== "f1Score";
        $("workload-control").hidden = !isValue;
        $("budget-control").hidden = !isValue;
        $("chart-scale-note").textContent = isValue ? "Cost: log scale · F1: linear" : "Linear scales · zero baseline";
        $("chart-panel").setAttribute("aria-labelledby", `tab-${view}`);
        $("chart-title").textContent = isPerformance ? "How well do models read the red pen?" : isValue ? "Where accuracy meets affordability" : "What does a million tokens cost?";
        $("chart-subtitle").textContent = isPerformance ? "Editorial accuracy on handwritten corrections. Higher is better." : isValue ? "Explore the tradeoff between F1 and an illustrative token workload." : "Input and output rates for the same contenders. Lower is cheaper.";
        const { rows, missing, total, overBudget } = pickRows();
        const top = rows[0];
        let summary = `${rows.length} of ${total} matching models`;
        if (isPerformance && top) summary += ` · <strong>${esc(name(top))}</strong> leads on ${metric() === "f1Score" ? "F1" : metric()} with <strong>${top[metric()].toFixed(4)}</strong>`;
        if (!isPerformance) summary += `${missing ? ` · ${missing} without verified pricing omitted` : ""}${overBudget ? ` · ${overBudget} above price ceiling` : ""}`;
        if (isValue && rows.length) summary += ` · <strong>${pareto(rows, cost).length} on the frontier</strong>`;
        $("chart-summary").innerHTML = summary;
        $("chart-plot").innerHTML = rows.length ? (isValue ? scatter(rows) : bars(rows)) : `<p class="chart-empty">${state.priceError && !isPerformance ? "Pricing could not be loaded. Reload the page to retry; performance remains available." : "No models match this selection. Try all models, clear the filters, or raise the price ceiling."}</p>`;
        $("chart-footnote").textContent = isPerformance ? "Select a model for details. F1 intervals appear as bootstrap calculations finish. All score bars run from 0 to 1." : `${state.snapshot ? `Pricing snapshot: ${state.snapshot.fetched_at.slice(0, 10)} (UTC). ` : ""}${isValue ? `Workload: 1M input + ${new Intl.NumberFormat("en-US").format(volume() * 1e6)} output tokens. Estimated token charge; excludes image charges and other extras. Frontier is relative to this selection.` : "Standard uncached text rates in USD per million tokens; OpenRouter starting rates. Contenders stay in F1 order. Select a model for source and route."}`;
        $("chart-plot").querySelectorAll("img[data-fallback]").forEach(img => img.addEventListener("error", () => { img.replaceWith(document.createTextNode(img.dataset.fallback)); }, { once: true }));
        selection();
    }
    function activate(view) {
        state.view = view;
        document.querySelectorAll(".chart-tabs [data-view]").forEach(button => {
            const selected = button.dataset.view === view;
            button.setAttribute("aria-selected", String(selected));
            button.tabIndex = selected ? 0 : -1;
        });
        render();
        if (view === "table" || view === "details") document.dispatchEvent(new CustomEvent("dorrit:table-shown", { detail: view }));
    }
    let refreshTimer;
    window.dorritCharts = {
        pareto,
        modelMark: mark,
        async init(rows) {
            state.rows = rows;
            $("model-explorer").hidden = false;
            document.querySelectorAll(".chart-tabs [data-view]").forEach(button => {
                button.addEventListener("click", () => activate(button.dataset.view));
                button.addEventListener("keydown", event => {
                    const order = ["performance", "price", "value", "table", "details"];
                    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
                    event.preventDefault();
                    const index = order.indexOf(state.view);
                    const next = event.key === "Home" ? 0 : event.key === "End" ? order.length - 1 : (index + (event.key === "ArrowRight" ? 1 : order.length - 1)) % order.length;
                    activate(order[next]); $("tab-" + order[next]).focus();
                });
            });
            ["chart-count", "chart-metric", "chart-ci", "chart-workload"].forEach(id => $(id).addEventListener("change", render));
            $("chart-budget").addEventListener("input", render);
            $("chart-plot").addEventListener("click", event => {
                const target = event.target.closest("[data-model]");
                if (target) { state.selected = target.dataset.model; selection(); }
            });
            $("chart-plot").addEventListener("keydown", event => {
                const point = event.target.closest(".value-point");
                if (point && ["Enter", " "].includes(event.key)) { event.preventDefault(); state.selected = point.dataset.model; selection(); }
            });
            window.matchMedia("(max-width: 700px)").addEventListener("change", render);
            const openTableAnchor = () => {
                const view = { "#leaderboard-table": "table", "#detailed": "details", "#model-performance-table": "details" }[location.hash];
                if (view) {
                    activate(view);
                    $("model-explorer").scrollIntoView({ block: "start" });
                }
            };
            window.addEventListener("hashchange", openTableAnchor);
            render();
            $("static-results").hidden = true;
            // A retained table fragment must not override Performance on reload.
            // Fresh deep links and in-page navigation can still open either table.
            const isReload = performance.getEntriesByType("navigation")[0]?.type === "reload";
            if (isReload && ["#leaderboard-table", "#detailed", "#model-performance-table"].includes(location.hash)) {
                history.replaceState(history.state, "", `${location.pathname}${location.search}#leaderboard`);
            } else if (!isReload) {
                openTableAnchor();
            }
            try {
                const response = await fetch("pricing.json");
                if (!response.ok) throw new Error(`Pricing HTTP ${response.status}`);
                state.snapshot = await response.json();
                state.prices = state.snapshot.models || {};
            } catch (error) { state.priceError = true; console.warn("Pricing unavailable", error); }
            render();
        },
        setFilters(vendor, year) { state.vendor = vendor; state.year = year; if (!pickRows().rows.some(r => r.modelId === state.selected)) state.selected = null; render(); },
        refreshIntervals() {
            clearTimeout(refreshTimer);
            refreshTimer = setTimeout(() => { if (state.view === "performance") render(); }, 150);
        },
    };
})();
