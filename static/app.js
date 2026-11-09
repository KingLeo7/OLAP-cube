"use strict";

const DEFAULT_LEVEL = { time: "quarter", location: "city", product: "category" };
const state = {
  rows: { dim: "location", level: "city" },
  cols: { dim: "time", level: "quarter" },
  filters: {},
};
let meta = null, last = null, facts = null, tab = "pandas";
const history = [];
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const levelsOf = (dim) => ["all", ...meta.dims[dim].levels];
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const fmt = (n) => (Math.round(n * 10) / 10).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 1 });

async function init() {
  meta = await (await fetch("/api/meta")).json();
  const opts = Object.entries(meta.dims).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join("");
  $("rowsDim").innerHTML = opts;
  $("colsDim").innerHTML = opts;
  document.addEventListener("click", onClick);
  document.addEventListener("change", onChange);
  apply("Base view: City × Quarter");
}

function log(text) {
  history.unshift(text);
  if (history.length > 30) history.pop();
}

async function apply(label) {
  if (label) log(label);
  renderControls();
  const res = await fetch("/api/query", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state),
  });
  const data = await res.json();
  if (!res.ok) { $("tableBox").innerHTML = `<p class="err">${esc(data.error)}</p>`; return; }
  last = data;
  renderResult();
  renderCode();
}

function onChange(e) {
  const sel = e.target.closest("select[data-axis]");
  if (!sel) return;
  const axis = sel.dataset.axis, other = axis === "rows" ? "cols" : "rows";
  const dim = sel.value;
  if (state[other].dim === dim) {
    const free = Object.keys(meta.dims).find((d) => d !== dim && d !== state[axis].dim) || state[axis].dim;
    state[other] = { dim: state[axis].dim, level: DEFAULT_LEVEL[state[axis].dim] };
    if (state[other].dim === dim) state[other] = { dim: free, level: DEFAULT_LEVEL[free] };
  }
  state[axis] = { dim, level: DEFAULT_LEVEL[dim] };
  apply(`Pivot: ${axis === "rows" ? "Rows" : "Columns"} = ${meta.dims[dim].label}`);
}

function onClick(e) {
  const b = e.target.closest("[data-act]");
  if (!b) return;
  const act = b.dataset.act;
  if (act === "swap") {
    [state.rows, state.cols] = [state.cols, state.rows];
    apply("Pivot: swapped rows and columns");
  } else if (act === "roll" || act === "drill") {
    const ax = state[b.dataset.axis], lv = levelsOf(ax.dim);
    const i = lv.indexOf(ax.level), j = act === "roll" ? i - 1 : i + 1;
    if (j < 0 || j >= lv.length) return;
    const from = ax.level; ax.level = lv[j];
    apply(`${act === "roll" ? "Roll-up" : "Drill-down"}: ${meta.dims[ax.dim].label} ${from} → ${ax.level}`);
  } else if (act === "chip") {
    const col = b.dataset.col, val = b.dataset.val;
    const cur = state.filters[col] || [];
    state.filters[col] = cur.includes(val) ? cur.filter((v) => v !== val) : [...cur, val];
    if (!state.filters[col].length) delete state.filters[col];
    apply(`Filter ${col} ${cur.includes(val) ? "removed" : "added"}: ${val}`);
  } else if (act === "clear") {
    state.filters = {};
    apply("Cleared all filters");
  } else if (act === "preset") {
    preset(b.dataset.p);
  } else if (act === "tab") {
    tab = b.dataset.t;
    document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x === b));
    renderCode();
  }
}

function preset(p) {
  state.filters = {};
  state.rows = { dim: "location", level: "city" };
  state.cols = { dim: "time", level: "quarter" };
  if (p === "rollup") { state.cols.level = "year"; state.rows = { dim: "location", level: "city" }; }
  if (p === "drilldown") { state.rows = { dim: "location", level: "city" }; state.cols.level = "month"; state.filters = { city: ["Bhubaneswar"] }; }
  if (p === "slice") state.filters = { quarter: ["Q4"] };
  if (p === "dice") {
    state.rows = { dim: "product", level: "category" };
    state.filters = { city: ["Bhubaneswar", "Cuttack"], category: ["Electronics", "Clothing"], quarter: ["Q1", "Q2"] };
  }
  if (p === "pivot") { state.rows = { dim: "time", level: "quarter" }; state.cols = { dim: "location", level: "city" }; }
  const names = { base: "Base view", rollup: "Roll-up: Quarter → Year", drilldown: "Drill-down: Bhubaneswar, Quarter → Month",
    slice: "Slice: Time = Q4", dice: "Dice: 2 cities × 2 categories × Q1–Q2", pivot: "Pivot: Time on rows, Location on columns" };
  apply(names[p]);
}

function renderControls() {
  $("rowsDim").value = state.rows.dim;
  $("colsDim").value = state.cols.dim;
  $("levelBox").innerHTML = ["rows", "cols"].map((axis) => {
    const ax = state[axis], lv = levelsOf(ax.dim), i = lv.indexOf(ax.level);
    return `<div class="lvl">
      <div class="name">${meta.dims[ax.dim].label}<div class="path">${axis === "rows" ? "rows" : "columns"}</div></div>
      <button class="up" data-act="roll" data-axis="${axis}" ${i === 0 ? "disabled" : ""} title="Roll-up">▲ Roll</button>
      <div class="cur">${cap(ax.level)}<div class="path">${lv.map((l) => (l === ax.level ? `<b>${l}</b>` : l)).join(" › ")}</div></div>
      <button class="down" data-act="drill" data-axis="${axis}" ${i === lv.length - 1 ? "disabled" : ""} title="Drill-down">▼ Drill</button>
    </div>`;
  }).join("");
  $("filterBox").innerHTML = Object.keys(meta.dims).map((dim) => {
    const cols = meta.dims[dim].levels.map((col) => {
      const chips = meta.values[col].map((v) => {
        const on = (state.filters[col] || []).includes(v);
        return `<button class="chip ${on ? "on" : ""}" data-act="chip" data-col="${col}" data-val="${esc(v)}">${esc(v)}</button>`;
      }).join("");
      return `<div class="chips-label"><div class="t">${col}</div><div class="chips">${chips}</div></div>`;
    }).join("");
    return `<div class="fgroup"><div class="t">${meta.dims[dim].label}</div>${cols}</div>`;
  }).join("");
}

function renderResult() {
  const d = last;
  $("badges").innerHTML = d.ops.map((o) => `<span class="badge ${o.type}">${esc(o.text)}</span>`).join("");
  if (!d.rows.length) {
    $("tableBox").innerHTML = `<p class="hint">No data matches these filters.</p>`;
    $("foot").textContent = "";
    return;
  }
  const max = Math.max(...d.matrix.flat(), 1), maxRow = Math.max(...d.row_totals, 1);
  let h = `<table><thead><tr><th>${esc(cap(d.row_label))} \\ ${esc(cap(d.col_label))}</th>` +
    d.cols.map((c) => `<th>${esc(c)}</th>`).join("") + `<th>Total</th></tr></thead><tbody>`;
  d.rows.forEach((r, i) => {
    h += `<tr><td class="rh">${esc(r)}</td>` + d.matrix[i].map((v) =>
      `<td style="background:rgba(42,157,143,${(0.08 + 0.5 * v / max).toFixed(2)})">${fmt(v)}</td>`).join("") +
      `<td class="tot">${fmt(d.row_totals[i])}<span class="bar" style="width:${(100 * d.row_totals[i] / maxRow).toFixed(0)}%"></span></td></tr>`;
  });
  h += `<tr class="tot"><td>Total</td>` + d.col_totals.map((v) => `<td>${fmt(v)}</td>`).join("") + `<td>${fmt(d.grand)}</td></tr></tbody></table>`;
  $("tableBox").innerHTML = h;
  $("foot").textContent = `Sales in ₹ lakh · ${d.cells_used} of ${meta.facts} fact rows used`;
}

async function renderCode() {
  const box = $("codeBox"), fb = $("factsBox");
  fb.hidden = tab !== "facts";
  box.hidden = tab === "facts";
  if (tab === "pandas") box.textContent = last ? last.pandas : "";
  if (tab === "sql") box.textContent = last ? last.sql : "";
  if (tab === "log") box.textContent = history.map((t, i) => `${String(history.length - i).padStart(2, "0")}. ${t}`).join("\n");
  if (tab === "facts") {
    if (!facts) facts = await (await fetch("/api/data")).json();
    const keys = Object.keys(facts[0]);
    fb.innerHTML = `<table><thead><tr>${keys.map((k) => `<th>${k}</th>`).join("")}</tr></thead><tbody>` +
      facts.map((r) => `<tr>${keys.map((k) => `<td>${esc(r[k])}</td>`).join("")}</tr>`).join("") + `</tbody></table>`;
  }
}

init();
