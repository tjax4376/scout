/**
 * Scout graph visualization UI.
 * Metadata: v0.1.1 | Scout Contributors | 2026-06-15
 */

(function () {
  "use strict";

  const API_BASE = "/v1";
  const STORAGE_KEY = "scout-graph-space";
  const KIND_COLORS = {
    file: "#6bcb77",
    directory: "#868e96",
    function: "#4dabf7",
    method: "#74c0fc",
    class: "#ffd43b",
    module: "#da77f2",
    default: "#adb5bd",
  };

  const spaceSelect = document.getElementById("space-select");
  const symbolQuery = document.getElementById("symbol-query");
  const symbolSearchBtn = document.getElementById("symbol-search-btn");
  const filePath = document.getElementById("file-path");
  const fileLoadBtn = document.getElementById("file-load-btn");
  const hitList = document.getElementById("hit-list");
  const nodeDetail = document.getElementById("node-detail");
  const previewBtn = document.getElementById("preview-btn");
  const sourcePreview = document.getElementById("source-preview");
  const statusBar = document.getElementById("status-bar");

  let cy = null;
  let selectedNode = null;
  let lastStale = false;

  function currentSpace() {
    return spaceSelect.value || "";
  }

  function setStatus(message, stale) {
    statusBar.textContent = message;
    statusBar.classList.toggle("stale", Boolean(stale));
    lastStale = Boolean(stale);
  }

  function applyStalenessHeader(response) {
    const staleHeader = response.headers.get("X-Scout-Stale");
    const stale = staleHeader === "true";
    const version = response.headers.get("X-Scout-Index-Version") || "";
    const suffix = stale ? " (index stale)" : "";
    setStatus(`Space: ${currentSpace()}${version ? ` · v${version}` : ""}${suffix}`, stale);
    return stale;
  }

  function updateUrl(params) {
    const url = new URL(window.location.href);
    for (const [key, value] of Object.entries(params)) {
      if (value) {
        url.searchParams.set(key, value);
      } else {
        url.searchParams.delete(key);
      }
    }
    window.history.replaceState({}, "", url);
  }

  async function apiFetch(path, options) {
    const response = await fetch(`${API_BASE}${path}`, options);
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = body.detail || JSON.stringify(body);
      } catch (_err) {
        /* ignore */
      }
      throw new Error(String(detail));
    }
    applyStalenessHeader(response);
    return response.json();
  }

  function nodeLabel(node) {
    const data = node.data || node;
    return data.symbol || data.rel_path || data.node_id || "?";
  }

  function kindColor(kind) {
    const key = String(kind || "").toLowerCase();
    return KIND_COLORS[key] || KIND_COLORS.default;
  }

  function nodeStyle(kind) {
    const k = String(kind || "").toLowerCase();
    if (k === "file" || k === "directory") {
      return { shape: "round-rectangle" };
    }
    if (k === "class" || k === "module") {
      return { shape: "diamond" };
    }
    return { shape: "ellipse" };
  }

  function ensureCy() {
    if (cy) {
      return cy;
    }
    cy = cytoscape({
      container: document.getElementById("cy"),
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 10,
            color: "#e6edf3",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "background-color": "data(color)",
            width: 28,
            height: 28,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#495057",
            "target-arrow-color": "#495057",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(edge)",
            "font-size": 8,
            color: "#868e96",
          },
        },
        {
          selector: "node.highlight",
          style: {
            "border-width": 3,
            "border-color": "#fff",
          },
        },
      ],
      layout: { name: "cose", animate: false },
    });

    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      showNodeDetail(node.data());
      highlightNode(node.id());
      expandNode(node.id());
    });

    return cy;
  }

  function cytoscapeNodeId(id) {
    return String(id).replace(/[^a-zA-Z0-9_-]/g, "_");
  }

  function addNodeRecord(record) {
    const graph = ensureCy();
    const id = cytoscapeNodeId(record.node_id);
    if (graph.getElementById(id).length) {
      return id;
    }
    const style = nodeStyle(record.kind);
    graph.add({
      group: "nodes",
      data: {
        id,
        node_id: record.node_id,
        label: nodeLabel(record),
        kind: record.kind,
        symbol: record.symbol,
        rel_path: record.rel_path,
        location_ref: record.location_ref,
        start_line: record.start_line,
        end_line: record.end_line,
        color: kindColor(record.kind),
      },
      ...style,
    });
    return id;
  }

  function addEdgeRecord(edge) {
    const graph = ensureCy();
    const source = cytoscapeNodeId(edge.source);
    const target = cytoscapeNodeId(edge.target);
    if (!graph.getElementById(source).length || !graph.getElementById(target).length) {
      return;
    }
    const edgeId = `${source}->${target}:${edge.edge || ""}`;
    if (graph.getElementById(edgeId).length) {
      return;
    }
    graph.add({
      group: "edges",
      data: {
        id: edgeId,
        source,
        target,
        edge: edge.edge || "",
      },
    });
  }

  function relayout() {
    const graph = ensureCy();
    if (graph.nodes().length === 0) {
      return;
    }
    graph.layout({ name: "cose", animate: true, animationDuration: 250 }).run();
  }

  function clearGraph() {
    if (cy) {
      cy.elements().remove();
    }
    selectedNode = null;
    nodeDetail.textContent = "Select a node";
    previewBtn.disabled = true;
    sourcePreview.textContent = "";
  }

  function highlightNode(cyId) {
    const graph = ensureCy();
    graph.nodes().removeClass("highlight");
    graph.getElementById(cyId).addClass("highlight");
    graph.center(graph.getElementById(cyId));
  }

  function showNodeDetail(data) {
    selectedNode = data;
    const lines = [
      `<strong>${escapeHtml(data.symbol || data.label || data.node_id)}</strong>`,
      `Kind: ${escapeHtml(data.kind || "?")}`,
      `Path: ${escapeHtml(data.rel_path || "—")}`,
    ];
    if (data.location_ref) {
      lines.push(`Ref: ${escapeHtml(data.location_ref)}`);
    }
    if (data.start_line) {
      lines.push(`Lines: ${data.start_line}–${data.end_line || data.start_line}`);
    }
    nodeDetail.innerHTML = lines.join("<br>");
    previewBtn.disabled = !data.rel_path;
    sourcePreview.textContent = "";
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderHits(hits) {
    hitList.innerHTML = "";
    if (!hits.length) {
      hitList.innerHTML = "<li>No matches</li>";
      return;
    }
    for (const hit of hits) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = `${hit.symbol || hit.rel_path} · ${hit.rel_path}`;
      btn.addEventListener("click", () => {
        hitList.querySelectorAll("button").forEach((el) => el.classList.remove("active"));
        btn.classList.add("active");
        focusHit(hit);
      });
      li.appendChild(btn);
      hitList.appendChild(li);
    }
  }

  function focusHit(hit) {
    clearGraph();
    const cyId = addNodeRecord(hit);
    relayout();
    highlightNode(cyId);
    showNodeDetail({
      node_id: hit.node_id,
      symbol: hit.symbol,
      kind: hit.kind,
      rel_path: hit.rel_path,
      location_ref: hit.location_ref,
      start_line: hit.start_line,
      end_line: hit.end_line,
      label: hit.symbol,
    });
    expandNode(hit.node_id);
    if (hit.rel_path) {
      filePath.value = hit.rel_path;
    }
    updateUrl({ space: currentSpace(), q: symbolQuery.value.trim(), file: hit.rel_path || "" });
  }

  async function loadSpaces() {
    const data = await apiFetch("/spaces/list");
    spaceSelect.innerHTML = "";
    const spaces = data.spaces || [];
    if (!spaces.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(no spaces — run scout setup)";
      spaceSelect.appendChild(opt);
      setStatus("No spaces configured", false);
      return;
    }
    for (const space of spaces) {
      const opt = document.createElement("option");
      opt.value = space.name;
      opt.textContent = space.name;
      spaceSelect.appendChild(opt);
    }
    const params = new URLSearchParams(window.location.search);
    const saved = localStorage.getItem(STORAGE_KEY);
    const preferred = params.get("space") || saved || spaces[0].name;
    if ([...spaceSelect.options].some((o) => o.value === preferred)) {
      spaceSelect.value = preferred;
    }
  }

  async function runSymbolSearch() {
    const q = symbolQuery.value.trim();
    if (!q || !currentSpace()) {
      return;
    }
    updateUrl({ space: currentSpace(), q, file: filePath.value.trim() });
    const data = await apiFetch(
      `/spaces/${encodeURIComponent(currentSpace())}/graph/search?q=${encodeURIComponent(q)}`
    );
    renderHits(data.hits || []);
    if (data.hits && data.hits.length) {
      focusHit(data.hits[0]);
    }
  }

  async function loadFileGraph() {
    const rel = filePath.value.trim();
    if (!rel || !currentSpace()) {
      return;
    }
    updateUrl({ space: currentSpace(), file: rel, q: symbolQuery.value.trim() });
    clearGraph();
    const data = await apiFetch(
      `/spaces/${encodeURIComponent(currentSpace())}/graph/file?rel_path=${encodeURIComponent(rel)}`
    );
    for (const sym of data.symbols || []) {
      addNodeRecord(sym);
    }
    for (const nb of data.neighbors || []) {
      addNodeRecord(nb);
    }
    for (const edge of data.edges || []) {
      addEdgeRecord(edge);
    }
    relayout();
    if (data.truncated) {
      setStatus(`Loaded ${rel} (truncated — expand nodes for more)`, lastStale);
    } else {
      setStatus(`Loaded ${rel}`, lastStale);
    }
    hitList.innerHTML = `<li>${(data.symbols || []).length} symbols, ${(data.neighbors || []).length} neighbors</li>`;
  }

  async function expandNode(nodeId) {
    if (!nodeId || !currentSpace()) {
      return;
    }
    const data = await apiFetch(
      `/spaces/${encodeURIComponent(currentSpace())}/node/${encodeURIComponent(nodeId)}/neighbors?depth=1&max_nodes=50`
    );
    const pivotCyId = cytoscapeNodeId(nodeId);
    for (const nb of data.neighbors || []) {
      const targetCyId = addNodeRecord(nb);
      addEdgeRecord({
        source: nodeId,
        target: nb.node_id,
        edge: nb.edge || "",
      });
      if (!document.getElementById("cy").querySelector(`[id="${pivotCyId}"]`)) {
        /* cytoscape internal */
      }
      void targetCyId;
    }
    relayout();
  }

  async function previewSource() {
    if (!selectedNode || !selectedNode.rel_path || !currentSpace()) {
      return;
    }
    const params = new URLSearchParams({ rel_path: selectedNode.rel_path });
    if (selectedNode.start_line) {
      params.set("start_line", String(selectedNode.start_line));
      params.set("end_line", String(selectedNode.end_line || selectedNode.start_line));
    }
    const data = await apiFetch(
      `/spaces/${encodeURIComponent(currentSpace())}/file?${params.toString()}`
    );
    sourcePreview.textContent = data.text || "";
  }

  async function bootstrap() {
    try {
      await loadSpaces();
      const params = new URLSearchParams(window.location.search);
      if (params.get("file")) {
        filePath.value = params.get("file");
        await loadFileGraph();
      }
      if (params.get("q")) {
        symbolQuery.value = params.get("q");
        await runSymbolSearch();
      }
      if (!params.get("file") && !params.get("q")) {
        setStatus(`Space: ${currentSpace()}`, false);
      }
    } catch (err) {
      setStatus(`Error: ${err.message}`, false);
    }
  }

  spaceSelect.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEY, currentSpace());
    clearGraph();
    hitList.innerHTML = "";
    updateUrl({ space: currentSpace(), file: "", q: "" });
    setStatus(`Space: ${currentSpace()}`, false);
  });

  symbolSearchBtn.addEventListener("click", () => {
    runSymbolSearch().catch((err) => setStatus(`Search failed: ${err.message}`, false));
  });

  symbolQuery.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter") {
      runSymbolSearch().catch((err) => setStatus(`Search failed: ${err.message}`, false));
    }
  });

  fileLoadBtn.addEventListener("click", () => {
    loadFileGraph().catch((err) => setStatus(`Load failed: ${err.message}`, false));
  });

  filePath.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter") {
      loadFileGraph().catch((err) => setStatus(`Load failed: ${err.message}`, false));
    }
  });

  previewBtn.addEventListener("click", () => {
    previewSource().catch((err) => setStatus(`Preview failed: ${err.message}`, false));
  });

  bootstrap();
})();
