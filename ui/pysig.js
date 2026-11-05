"use strict";

let model = null;
let selectedFile = "";
let runTimer = null;

const pageTitles = {
  dashboard: "Model overview",
  network: "Network view",
  yaml: "YAML editor",
  run: "Run model",
  outputs: "Outputs",
};

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({ error: response.statusText }));
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function formatBytes(value) {
  if (value < 1024) return `${value} B`;
  if (value < 1048576) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1048576).toFixed(1)} MB`;
}

function selectView(viewName) {
  document.querySelectorAll(".nav-button").forEach(button => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
  document.querySelectorAll(".view").forEach(view => {
    view.classList.toggle("active", view.id === viewName);
  });
  document.getElementById("page-title").textContent = pageTitles[viewName];
  if (viewName === "network") drawNetwork();
  if (viewName === "outputs") loadOutputs();
}

async function refreshState() {
  const state = await api("/api/state");
  model = state.model;
  const modelTitle = model.model.name || model.model.id || "Unnamed model";
  document.getElementById("model-name").textContent = `${modelTitle} · ${state.config}`;
  document.getElementById("metric-intersections").textContent = model.intersections.length;
  document.getElementById("metric-movements").textContent = model.movements.length;
  document.getElementById("metric-routes").textContent = model.routes.length;
  document.getElementById("metric-demand").textContent = model.od_total.toLocaleString();
  document.getElementById("model-summary").innerHTML = `
    <table class="data-table">
      <tr><th>Item</th><th>Value</th></tr>
      <tr><td>Run mode</td><td>${escapeHtml(model.run.mode || "network")}</td></tr>
      <tr><td>Controllers</td><td>${model.controllers.length}</td></tr>
      <tr><td>Lanes</td><td>${model.lanes.length}</td></tr>
      <tr><td>Network links</td><td>${model.links.length}</td></tr>
      <tr><td>Horizon</td><td>${escapeHtml(model.network.horizon_s || "default")} s</td></tr>
      <tr><td>Time slice</td><td>${escapeHtml(model.network.time_slice_s || "default")} s</td></tr>
    </table>`;
}

async function loadConfigList() {
  const data = await api("/api/configs");
  document.getElementById("config-select").innerHTML = data.configs.map(name =>
    `<option value="${escapeHtml(name)}" ${name === data.selected ? "selected" : ""}>${escapeHtml(name)}</option>`
  ).join("");
}

async function loadConfig() {
  const name = document.getElementById("config-select").value;
  const data = await api(`/api/config?name=${encodeURIComponent(name)}`);
  document.getElementById("yaml-editor").value = data.text;
  document.getElementById("save-state").textContent = "";
  await refreshState();
}

async function saveConfig() {
  const status = document.getElementById("save-state");
  try {
    const payload = {
      name: document.getElementById("config-select").value,
      text: document.getElementById("yaml-editor").value,
    };
    await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    status.innerHTML = '<span class="ok">Saved</span>';
    await refreshState();
    drawNetwork();
  } catch (error) {
    status.innerHTML = `<span class="error">${escapeHtml(error.message)}</span>`;
    throw error;
  }
}

async function validateYaml() {
  const status = document.getElementById("save-state");
  try {
    const data = await api("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: document.getElementById("yaml-editor").value }),
    });
    status.innerHTML = `<span class="ok">Valid YAML · ${data.intersections} intersection(s)</span>`;
  } catch (error) {
    status.innerHTML = `<span class="error">${escapeHtml(error.message)}</span>`;
  }
}

function svgElement(tag, attributes, text) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes || {}).forEach(([name, value]) => element.setAttribute(name, value));
  if (text) element.textContent = text;
  return element;
}

function drawNetwork() {
  if (!model) return;
  const svg = document.getElementById("network-svg");
  svg.innerHTML = "";

  const definitions = svgElement("defs");
  const marker = svgElement("marker", {
    id: "arrow", viewBox: "0 0 10 10", refX: "9", refY: "5",
    markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse",
  });
  marker.appendChild(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#ff6b6b" }));
  definitions.appendChild(marker);
  svg.appendChild(definitions);

  const intersections = model.intersections.length ? model.intersections : [{ id: "I1" }];
  const positions = {};
  intersections.forEach((intersection, index) => {
    positions[intersection.id] = {
      x: intersections.length === 1 ? 600 : 150 + index * (900 / Math.max(1, intersections.length - 1)),
      y: 280,
    };
  });

  model.links.forEach(link => {
    const start = positions[link.from_intersection_id];
    const end = positions[link.to_intersection_id];
    if (!start || !end) return;
    svg.appendChild(svgElement("line", {
      x1: start.x + 95, y1: start.y, x2: end.x - 95, y2: end.y,
      stroke: "#ff6b6b", "stroke-width": "18", "stroke-linecap": "round",
      opacity: ".78", "marker-end": "url(#arrow)",
    }));
    svg.appendChild(svgElement("text", {
      x: (start.x + end.x) / 2, y: start.y - 18, "text-anchor": "middle",
      fill: "#9b2f39", "font-size": "13", "font-weight": "800",
    }, `${link.id} · ${link.length_m} m · ${link.speed_kmh} km/h`));
  });

  intersections.forEach(intersection => {
    const { x, y } = positions[intersection.id];
    svg.appendChild(svgElement("rect", { x: x - 115, y: y - 115, width: 230, height: 230, rx: 28, fill: "#d8d2c8" }));
    svg.appendChild(svgElement("rect", { x: x - 115, y: y - 37, width: 230, height: 74, fill: "#39464b" }));
    svg.appendChild(svgElement("rect", { x: x - 37, y: y - 115, width: 74, height: 230, fill: "#39464b" }));

    const movements = model.movements.filter(movement => movement.intersection_id === intersection.id);
    movements.forEach((movement, index) => {
      const side = index % 4;
      const rank = Math.floor(index / 4);
      const offset = (rank - 1) * 12;
      let x1 = x, y1 = y, x2 = x, y2 = y;
      if (side === 0) { x1 = x - 105; y1 = y - 18 + offset; x2 = x - 35; y2 = y - 18 + offset; }
      if (side === 1) { x1 = x + 18 + offset; y1 = y - 105; x2 = x + 18 + offset; y2 = y - 35; }
      if (side === 2) { x1 = x + 105; y1 = y + 18 + offset; x2 = x + 35; y2 = y + 18 + offset; }
      if (side === 3) { x1 = x - 18 + offset; y1 = y + 105; x2 = x - 18 + offset; y2 = y + 35; }
      const colours = ["#8bb8ff", "#8de4c1", "#ffb86b", "#c5a3ff"];
      svg.appendChild(svgElement("line", {
        x1, y1, x2, y2, stroke: colours[index % colours.length],
        "stroke-width": "8", "stroke-linecap": "round",
      }));
      svg.appendChild(svgElement("text", {
        x: x1 + (side === 0 ? -5 : side === 2 ? 5 : 0),
        y: y1 + (side === 1 ? -7 : side === 3 ? 16 : 4),
        "text-anchor": side === 0 ? "end" : side === 2 ? "start" : "middle",
        fill: "#263238", "font-size": "11", "font-weight": "800",
      }, movement.id));
    });

    svg.appendChild(svgElement("circle", { cx: x, cy: y, r: 31, fill: "#ffe66d", stroke: "#263238", "stroke-width": "4" }));
    svg.appendChild(svgElement("text", { x, y: y + 5, "text-anchor": "middle", "font-size": "16", "font-weight": "900", fill: "#263238" }, intersection.id));
    const controller = model.controllers.find(item => item.intersection_id === intersection.id);
    if (controller) {
      svg.appendChild(svgElement("text", { x, y: y + 145, "text-anchor": "middle", "font-size": "13", "font-weight": "800", fill: "#59666a" }, `${controller.id} · ${controller.cycle_time_s}s · offset ${controller.offset_s || 0}s`));
    }
  });
}

async function startRun(mode) {
  try {
    await saveConfig();
    await api("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    selectView("run");
    pollRun();
  } catch (error) {
    window.alert(error.message);
  }
}

async function stopRun() {
  try { await api("/api/stop", { method: "POST" }); }
  catch (error) { window.alert(error.message); }
}

async function pollRun() {
  try {
    const state = await api("/api/run");
    const dot = document.getElementById("status-dot");
    dot.className = `status-dot${state.running ? " running" : state.return_code !== null && state.return_code !== 0 ? " failed" : ""}`;
    document.getElementById("status-text").textContent = state.running ? "Running" : state.return_code === 0 ? "Completed" : state.return_code !== null ? "Failed" : "Ready";
    const consoleElement = document.getElementById("console");
    consoleElement.textContent = state.log || "No run started.";
    consoleElement.scrollTop = consoleElement.scrollHeight;
    document.getElementById("start-run").disabled = state.running;
    document.getElementById("run-facts").innerHTML = `<p><strong>Elapsed:</strong> ${state.elapsed_s}s</p><p><strong>Exit code:</strong> ${state.return_code ?? "—"}</p>`;
    if (!state.running && state.return_code !== null) loadOutputs();
  } catch (error) {
    console.error(error);
  }
  clearTimeout(runTimer);
  runTimer = setTimeout(pollRun, 1000);
}

async function loadOutputs() {
  const data = await api("/api/outputs");
  document.getElementById("output-count").textContent = `${data.files.length} file(s)`;
  document.getElementById("file-list").innerHTML = data.files.map(file => `
    <button class="file-button ${selectedFile === file.name ? "active" : ""}" data-file="${escapeHtml(file.name)}">
      <strong>${escapeHtml(file.name)}</strong>
      <small>${formatBytes(file.size)} · ${file.kind.toUpperCase()}</small>
    </button>`).join("") || "<p>No outputs yet.</p>";
  document.querySelectorAll(".file-button").forEach(button => {
    button.addEventListener("click", () => previewFile(button.dataset.file));
  });
}

async function previewFile(name) {
  selectedFile = name;
  await loadOutputs();
  const encoded = encodeURIComponent(name);
  const data = await api(`/api/output?name=${encoded}`);
  const preview = document.getElementById("output-preview");
  const header = `<div class="toolbar"><strong>${escapeHtml(name)}</strong><a class="button ghost" href="/download?name=${encoded}">Download</a></div>`;
  if (data.type === "csv") {
    const table = (data.rows || []).map((row, index) => `<tr>${row.map(value => index === 0 ? `<th>${escapeHtml(value)}</th>` : `<td>${escapeHtml(value)}</td>`).join("")}</tr>`).join("");
    preview.innerHTML = `${header}<div class="table-wrap"><table class="data-table">${table}</table></div>${data.truncated ? "<p>Preview limited to 500 rows.</p>" : ""}`;
  } else if (data.type === "json") {
    preview.innerHTML = `${header}<pre class="json-preview">${escapeHtml(JSON.stringify(data.data, null, 2))}</pre>`;
  } else {
    preview.innerHTML = `${header}<pre class="json-preview">${escapeHtml(data.text || "Binary file")}</pre>`;
  }
}

async function boot() {
  document.querySelectorAll(".nav-button").forEach(button => button.addEventListener("click", () => selectView(button.dataset.view)));
  document.querySelectorAll("[data-run-mode]").forEach(button => button.addEventListener("click", () => startRun(button.dataset.runMode)));
  document.getElementById("redraw-network").addEventListener("click", drawNetwork);
  document.getElementById("load-config").addEventListener("click", loadConfig);
  document.getElementById("save-config").addEventListener("click", saveConfig);
  document.getElementById("validate-yaml").addEventListener("click", validateYaml);
  document.getElementById("start-run").addEventListener("click", () => startRun(document.getElementById("run-mode").value));
  document.getElementById("stop-run").addEventListener("click", stopRun);
  document.getElementById("refresh-outputs").addEventListener("click", loadOutputs);
  await refreshState();
  await loadConfigList();
  await loadConfig();
  await pollRun();
}

boot().catch(error => {
  console.error(error);
  document.getElementById("model-name").textContent = error.message;
});
