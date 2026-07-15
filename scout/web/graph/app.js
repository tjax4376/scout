/**
 * Scout graph visualization UI.
 * Metadata: v0.3.1 | Scout Contributors | 2026-07-14
 * Change rationale: graph-webui-api-key — Bearer from localStorage for api.auth
 */

(function () {
  "use strict";

  const API_BASE = "/v1";
  const STORAGE_KEY = "scout-graph-space";
  const API_KEY_STORAGE = "scout-graph-api-key";
  const PANE_WIDTH_KEY = "scout-graph-pane-width";
  const LAZY_THRESHOLD = 5000;
  const PANE_MIN_WIDTH = 200;
  const PANE_MAX_RATIO = 0.5;
  const SKIP_TREE_KINDS = new Set(["directory", "file"]);
  const BODY_PREVIEW_CHARS = 480;
  const FILE_LIKE_KINDS = new Set(["file", "module", "directory", "class", "function", "method"]);

  const KIND_COLORS = {
    file: "#6bcb77",
    directory: "#868e96",
    function: "#4dabf7",
    method: "#74c0fc",
    class: "#ffd43b",
    module: "#da77f2",
    memory: "#e599f7",
    default: "#adb5bd",
  };

  const spaceSelect = document.getElementById("space-select");
  const apiKeyInput = document.getElementById("api-key");
  const symbolQuery = document.getElementById("symbol-query");
  const symbolSearchBtn = document.getElementById("symbol-search-btn");
  const filePath = document.getElementById("file-path");
  const fileLoadBtn = document.getElementById("file-load-btn");
  const hitList = document.getElementById("hit-list");
  const nodeDetail = document.getElementById("node-detail");
  const previewBtn = document.getElementById("preview-btn");
  const sourcePreview = document.getElementById("source-preview");
  const statusBar = document.getElementById("status-bar");
  const treePane = document.getElementById("tree-pane");
  const functionTree = document.getElementById("function-tree");
  const functionTreeStatus = document.getElementById("function-tree-status");
  const resizeHandle = document.getElementById("resize-handle");
  const tabGraph = document.getElementById("tab-graph");
  const tabCavern = document.getElementById("tab-cavern");
  const graphControls = document.getElementById("graph-controls");
  const graphPanePanels = document.getElementById("graph-pane-panels");
  const cavernPane = document.getElementById("cavern-pane");
  const memoryIndex = document.getElementById("memory-index");
  const cavernIndexStatus = document.getElementById("cavern-index-status");
  const linkedFilesIndex = document.getElementById("linked-files-index");
  const memoryDetail = document.getElementById("memory-detail");
  const memoryBodyToggle = document.getElementById("memory-body-toggle");

  let cy = null;
  let selectedNode = null;
  let lastStale = false;
  let treeRoot = null;
  let treeLazyMode = false;
  let treeLoading = false;
  let selectedTreeKey = null;
  let currentTab = "graph";
  let memoriesCache = [];
  let selectedMemoryId = null;
  let selectedMemory = null;
  let memoryBodyExpanded = false;
  let pendingMemoryId = null;

  function currentSpace() {
    return spaceSelect.value || "";
  }

  function currentApiKey() {
    return (apiKeyInput && apiKeyInput.value.trim()) || "";
  }

  function restoreApiKey() {
    if (!apiKeyInput) {
      return;
    }
    const saved = localStorage.getItem(API_KEY_STORAGE);
    if (saved) {
      apiKeyInput.value = saved;
    }
  }

  function persistApiKey() {
    if (!apiKeyInput) {
      return;
    }
    const key = apiKeyInput.value.trim();
    if (key) {
      localStorage.setItem(API_KEY_STORAGE, key);
    } else {
      localStorage.removeItem(API_KEY_STORAGE);
    }
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

  function syncUrlState(extra) {
    const params = {
      space: currentSpace(),
      tab: currentTab === "cavern" ? "cavern" : "graph",
      memory: currentTab === "cavern" ? selectedMemoryId || "" : "",
      q: currentTab === "graph" ? symbolQuery.value.trim() : "",
      file: currentTab === "graph" ? filePath.value.trim() : "",
    };
    if (extra) {
      Object.assign(params, extra);
    }
    updateUrl(params);
  }

  async function apiFetch(path, options) {
    const opts = options ? { ...options } : {};
    const headers = new Headers(opts.headers || {});
    const key = currentApiKey();
    if (key && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${key}`);
    }
    opts.headers = headers;
    const response = await fetch(`${API_BASE}${path}`, opts);
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = body.detail || JSON.stringify(body);
      } catch (_err) {
        /* ignore */
      }
      if (response.status === 401) {
        detail =
          "unauthorized — paste SCOUT_API_KEY (api.auth.key) in the API key field";
      }
      const err = new Error(String(detail));
      err.status = response.status;
      throw err;
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
    if (k === "memory") {
      return { shape: "star" };
    }
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
          selector: 'node[kind = "memory"]',
          style: {
            shape: "star",
            width: 36,
            height: 36,
            "background-color": KIND_COLORS.memory,
            "border-width": 2,
            "border-color": "#f3d9fa",
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
      const data = node.data();
      selectNode(data.node_id, data);
      if (currentTab === "graph") {
        expandNode(data.node_id).catch((err) =>
          setStatus(`Expand failed: ${err.message}`, lastStale)
        );
      }
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
    const el = graph.getElementById(cyId);
    if (el.length) {
      el.addClass("highlight");
      graph.center(el);
    }
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
        selectSymbol(hit);
      });
      li.appendChild(btn);
      hitList.appendChild(li);
    }
  }

  function selectNode(nodeId, data) {
    if (!nodeId || !data) {
      return;
    }
    const cyId = cytoscapeNodeId(nodeId);
    highlightNode(cyId);
    showNodeDetail(data);
    if (currentTab === "graph") {
      highlightTreeNode(nodeId, data.rel_path);
    }
  }

  function selectSymbol(hit) {
    clearGraph();
    const cyId = addNodeRecord(hit);
    relayout();
    selectNode(hit.node_id, {
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
    syncUrlState({ q: symbolQuery.value.trim(), file: hit.rel_path || "" });
  }

  function focusHit(hit) {
    selectSymbol(hit);
  }

  /* --- Mode tabs (Graph | Cavern) --- */

  function applyTabVisibility() {
    const isCavern = currentTab === "cavern";
    tabGraph.classList.toggle("active", !isCavern);
    tabCavern.classList.toggle("active", isCavern);
    tabGraph.setAttribute("aria-selected", String(!isCavern));
    tabCavern.setAttribute("aria-selected", String(isCavern));

    graphControls.classList.toggle("hidden", isCavern);
    graphPanePanels.classList.toggle("hidden", isCavern);
    graphPanePanels.hidden = isCavern;

    cavernPane.classList.toggle("hidden", !isCavern);
    cavernPane.hidden = !isCavern;

    const canvas = document.getElementById("cy");
    if (canvas) {
      canvas.setAttribute("aria-label", isCavern ? "Memory cavern graph" : "Code graph");
    }
  }

  async function setTab(tab, options) {
    const opts = options || {};
    const next = tab === "cavern" ? "cavern" : "graph";
    const changed = currentTab !== next;
    currentTab = next;
    applyTabVisibility();

    if (next === "cavern") {
      if (changed || opts.forceReload) {
        clearGraph();
        resetCavernDetail();
        await loadMemoriesIndex();
      }
      const memId = opts.memoryId || pendingMemoryId || selectedMemoryId;
      pendingMemoryId = null;
      if (memId) {
        await selectMemory(memId);
      }
    } else if (changed) {
      clearGraph();
      selectedMemoryId = null;
      selectedMemory = null;
      syncUrlState();
      if (!treeRoot && currentSpace()) {
        await refreshFunctionTree();
      }
    } else {
      syncUrlState();
    }
  }

  function resetCavernDetail() {
    selectedMemoryId = null;
    selectedMemory = null;
    memoryBodyExpanded = false;
    memoryDetail.textContent = "Select a memory";
    memoryBodyToggle.classList.add("hidden");
    memoryBodyToggle.hidden = true;
    linkedFilesIndex.innerHTML = '<li class="tree-empty">Select a memory</li>';
    memoryIndex.querySelectorAll("button").forEach((el) => el.classList.remove("active"));
  }

  function setCavernStatus(message, warn) {
    cavernIndexStatus.textContent = message || "";
    cavernIndexStatus.classList.toggle("warn", Boolean(warn));
  }

  async function loadMemoriesIndex() {
    if (!currentSpace()) {
      memoryIndex.innerHTML = '<li class="tree-empty">No space selected</li>';
      setCavernStatus("");
      return;
    }
    memoryIndex.innerHTML = '<li class="tree-empty">Loading memories…</li>';
    setCavernStatus("Loading…");
    try {
      const data = await apiFetch(`/memories`);
      memoriesCache = data.memories || [];
      renderMemoryIndex(memoriesCache);
      if (!memoriesCache.length) {
        setCavernStatus("Cavern empty — no memories yet");
      } else {
        setCavernStatus(`${memoriesCache.length} memor${memoriesCache.length === 1 ? "y" : "ies"}`);
      }
      syncUrlState();
    } catch (err) {
      memoriesCache = [];
      memoryIndex.innerHTML = '<li class="tree-empty">Failed to load memories</li>';
      setCavernStatus(`Load failed: ${err.message}`, true);
      setStatus(`Cavern error: ${err.message}`, lastStale);
    }
  }

  function renderMemoryIndex(memories) {
    memoryIndex.innerHTML = "";
    if (!memories.length) {
      memoryIndex.innerHTML =
        '<li class="tree-empty">No memories yet. Add via the add-memory skill (global store).</li>';
      return;
    }
    for (const mem of memories) {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.memoryId = mem.id;
      btn.setAttribute("role", "option");
      btn.setAttribute("aria-selected", String(mem.id === selectedMemoryId));
      if (mem.id === selectedMemoryId) {
        btn.classList.add("active");
      }
      const title = document.createElement("span");
      title.textContent = mem.title || mem.id;
      const meta = document.createElement("span");
      meta.className = "memory-meta";
      const bits = [];
      if (mem.category) {
        bits.push(mem.category);
      }
      if (mem.created_at) {
        bits.push(mem.created_at);
      }
      meta.textContent = bits.join(" · ") || mem.id;
      btn.appendChild(title);
      btn.appendChild(meta);
      btn.addEventListener("click", () => {
        selectMemory(mem.id).catch((err) => setStatus(`Memory select failed: ${err.message}`, lastStale));
      });
      btn.addEventListener("keydown", (evt) => {
        if (evt.key === "Enter" || evt.key === " ") {
          evt.preventDefault();
          selectMemory(mem.id).catch((err) =>
            setStatus(`Memory select failed: ${err.message}`, lastStale)
          );
        }
      });
      li.appendChild(btn);
      memoryIndex.appendChild(li);
    }
  }

  function markMemorySelected(memoryId) {
    selectedMemoryId = memoryId;
    memoryIndex.querySelectorAll("button").forEach((el) => {
      const active = el.dataset.memoryId === memoryId;
      el.classList.toggle("active", active);
      el.setAttribute("aria-selected", String(active));
    });
  }

  async function selectMemory(memoryId) {
    if (!memoryId || !currentSpace()) {
      return;
    }
    markMemorySelected(memoryId);
    memoryBodyExpanded = false;
    memoryDetail.textContent = "Loading memory…";
    linkedFilesIndex.innerHTML = '<li class="tree-empty">Loading…</li>';

    let detail = memoriesCache.find((m) => m.id === memoryId) || null;
    try {
      if (!detail || detail.body == null) {
        detail = await apiFetch(
          `/memory/${encodeURIComponent(memoryId)}`
        );
      }
    } catch (err) {
      const missing = err.status === 404;
      memoryDetail.innerHTML = missing
        ? `<strong>Memory not found</strong><br>${escapeHtml(memoryId)}`
        : `<strong>Failed to load memory</strong><br>${escapeHtml(err.message)}`;
      memoryBodyToggle.classList.add("hidden");
      memoryBodyToggle.hidden = true;
      linkedFilesIndex.innerHTML = '<li class="tree-empty">—</li>';
      setStatus(
        missing ? `Memory not found: ${memoryId}` : `Memory load failed: ${err.message}`,
        lastStale
      );
      syncUrlState({ memory: memoryId });
      return;
    }

    selectedMemory = detail;
    renderMemoryDetail(detail);
    syncUrlState({ memory: memoryId });
    await loadMemoryGraph(detail);
  }

  function renderMemoryDetail(mem) {
    const tags = Array.isArray(mem.tags) ? mem.tags.join(", ") : "";
    const body = mem.body || "";
    const truncated = !memoryBodyExpanded && body.length > BODY_PREVIEW_CHARS;
    const shown = truncated ? `${body.slice(0, BODY_PREVIEW_CHARS)}…` : body;

    memoryDetail.innerHTML = [
      `<strong>${escapeHtml(mem.title || mem.id)}</strong>`,
      `Id: ${escapeHtml(mem.id)}`,
      `Category: ${escapeHtml(mem.category || "—")}`,
      `Tags: ${escapeHtml(tags || "—")}`,
      `Created: ${escapeHtml(mem.created_at || "—")}`,
      `Path: ${escapeHtml(mem.rel_path || "—")}`,
      `<div class="memory-body">${escapeHtml(shown || "(empty body)")}</div>`,
    ].join("<br>");

    if (body.length > BODY_PREVIEW_CHARS) {
      memoryBodyToggle.classList.remove("hidden");
      memoryBodyToggle.hidden = false;
      memoryBodyToggle.textContent = memoryBodyExpanded ? "Show preview" : "Show full body";
    } else {
      memoryBodyToggle.classList.add("hidden");
      memoryBodyToggle.hidden = true;
    }
  }

  function renderLinkedFiles(neighbors) {
    linkedFilesIndex.innerHTML = "";
    const paths = [];
    const seen = new Set();
    for (const nb of neighbors || []) {
      const kind = String(nb.kind || "").toLowerCase();
      const rel = nb.rel_path || "";
      if (!rel || seen.has(rel)) {
        continue;
      }
      if (!FILE_LIKE_KINDS.has(kind) && kind === "memory") {
        continue;
      }
      if (kind === "memory") {
        continue;
      }
      seen.add(rel);
      paths.push({ rel_path: rel, kind, node_id: nb.node_id, symbol: nb.symbol });
    }
    paths.sort((a, b) => a.rel_path.localeCompare(b.rel_path));

    if (!paths.length) {
      linkedFilesIndex.innerHTML = '<li class="tree-empty">No linked files</li>';
      return;
    }

    for (const item of paths) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = `${item.rel_path}${item.kind ? ` · ${item.kind}` : ""}`;
      btn.addEventListener("click", () => {
        if (item.node_id) {
          const graph = ensureCy();
          const cyId = cytoscapeNodeId(item.node_id);
          highlightNode(cyId);
          const el = graph.getElementById(cyId);
          if (el.length) {
            showNodeDetail(el.data());
          }
        }
      });
      li.appendChild(btn);
      linkedFilesIndex.appendChild(li);
    }
  }

  async function loadMemoryGraph(mem) {
    clearGraph();
    const nodeId = `mem-${mem.id}`;
    addNodeRecord({
      node_id: nodeId,
      kind: "memory",
      symbol: mem.title || mem.id,
      rel_path: mem.rel_path || "",
      location_ref: "",
      start_line: 0,
      end_line: 0,
    });
    highlightNode(cytoscapeNodeId(nodeId));
    selectNode(nodeId, {
      node_id: nodeId,
      kind: "memory",
      symbol: mem.title || mem.id,
      rel_path: mem.rel_path || "",
      label: mem.title || mem.id,
    });

    try {
      const data = await apiFetch(
        `/spaces/${encodeURIComponent(currentSpace())}/node/${encodeURIComponent(nodeId)}/neighbors?depth=1&max_nodes=80`
      );
      const neighbors = data.neighbors || [];
      for (const nb of neighbors) {
        addNodeRecord(nb);
        addEdgeRecord({
          source: nodeId,
          target: nb.node_id,
          edge: nb.edge || "contains",
        });
        // Also try reverse orientation if API returns from_id oriented differently
        if (nb.from_id && nb.to_id) {
          addEdgeRecord({
            source: nb.from_id,
            target: nb.to_id,
            edge: nb.edge || "contains",
          });
        }
      }
      if (Array.isArray(data.edges)) {
        for (const edge of data.edges) {
          addEdgeRecord({
            source: edge.from_id || edge.source,
            target: edge.to_id || edge.target,
            edge: edge.kind || edge.edge || "",
          });
        }
      }
      renderLinkedFiles(neighbors);
      relayout();
      setStatus(
        `Cavern: ${mem.title || mem.id} · ${neighbors.length} neighbor${neighbors.length === 1 ? "" : "s"}`,
        lastStale
      );
    } catch (err) {
      renderLinkedFiles([]);
      relayout();
      const missing = err.status === 404;
      setStatus(
        missing
          ? `Memory not linked in this space's graph — detail still available`
          : `Memory loaded; neighbors failed: ${err.message}`,
        lastStale
      );
      setCavernStatus(
        missing
          ? "Not linked in this space (create via space alias or link_space)"
          : `Neighbors error: ${err.message}`,
        true
      );
    }
  }

  /* --- Function tree --- */

  function treeNodeKey(node) {
    if (node.node_id) {
      return `id:${node.node_id}`;
    }
    return `${node.kind}:${node.path || node.label}`;
  }

  function createTreeNode(kind, label, path, symbol) {
    return {
      kind,
      label,
      path: path || "",
      node_id: symbol && symbol.node_id ? symbol.node_id : null,
      symbol: symbol || null,
      children: [],
      expanded: false,
      loaded: kind !== "directory" || !treeLazyMode,
    };
  }

  function findOrCreateChild(parent, kind, label, path, symbol) {
    let child = parent.children.find((c) => {
      if (symbol && c.node_id) {
        return c.node_id === symbol.node_id;
      }
      return c.kind === kind && (c.path === path || c.label === label);
    });
    if (!child) {
      child = createTreeNode(kind, label, path, symbol);
      child._key = treeNodeKey(child);
      parent.children.push(child);
    }
    return child;
  }

  function sortTreeChildren(node) {
    const kindOrder = { directory: 0, file: 1, module: 2, class: 3, function: 4, method: 5 };
    node.children.sort((a, b) => {
      const ka = kindOrder[a.kind] ?? 9;
      const kb = kindOrder[b.kind] ?? 9;
      if (ka !== kb) {
        return ka - kb;
      }
      return a.label.localeCompare(b.label);
    });
    for (const child of node.children) {
      sortTreeChildren(child);
    }
  }

  function addSymbolsToParent(parent, symbols, parentPath) {
    for (const sym of symbols) {
      const kind = String(sym.kind || "").toLowerCase();
      if (SKIP_TREE_KINDS.has(kind)) {
        continue;
      }
      let relPath = String(sym.rel_path || "").trim();
      if (!relPath) {
        continue;
      }
      if (parentPath) {
        const prefix = `${parentPath}/`;
        if (relPath.startsWith(prefix)) {
          relPath = relPath.slice(prefix.length);
        } else if (relPath === parentPath) {
          continue;
        }
      }

      const parts = relPath.split("/");
      const fileName = parts.pop();
      let current = parent;
      let dirPath = parentPath || "";

      for (const segment of parts) {
        dirPath = dirPath ? `${dirPath}/${segment}` : segment;
        current = findOrCreateChild(current, "directory", segment, dirPath, null);
      }

      const fileRelPath = sym.rel_path;
      const fileNode = findOrCreateChild(current, "file", fileName, fileRelPath, {
        node_id: `file:${fileRelPath}`,
        kind: "file",
        rel_path: fileRelPath,
      });
      const symKind = kind || "function";
      const symLabel = sym.symbol || symKind;
      findOrCreateChild(fileNode, symKind, symLabel, fileRelPath, sym);
    }
  }

  function buildSymbolTree(symbols) {
    const root = createTreeNode("directory", ".", "", null);
    root.expanded = true;
    root.loaded = true;
    root._key = "root";
    addSymbolsToParent(root, symbols, "");
    sortTreeChildren(root);
    return root;
  }

  function buildLazyRootTree(symbols) {
    const root = createTreeNode("directory", ".", "", null);
    root.expanded = true;
    root.loaded = true;
    root._key = "root";
    const seen = new Set();

    for (const sym of symbols) {
      const relPath = String(sym.rel_path || "").trim();
      if (!relPath) {
        continue;
      }
      const top = relPath.split("/")[0];
      if (!top || seen.has(top)) {
        continue;
      }
      seen.add(top);
      const dirNode = createTreeNode("directory", top, top, null);
      dirNode._key = `dir:${top}`;
      dirNode.loaded = false;
      dirNode.expanded = false;
      root.children.push(dirNode);
    }

    root.children.sort((a, b) => a.label.localeCompare(b.label));
    return root;
  }

  async function fetchSymbolsForTree(space, pathPrefix) {
    const prefix = pathPrefix || "";
    const params = new URLSearchParams();
    if (prefix) {
      params.set("path_prefix", prefix);
    }
    const qs = params.toString();
    const path = `/spaces/${encodeURIComponent(space)}/symbols${qs ? `?${qs}` : ""}`;
    const data = await apiFetch(path);
    return data.symbols || [];
  }

  function setTreeStatus(message, warn) {
    functionTreeStatus.textContent = message || "";
    functionTreeStatus.classList.toggle("warn", Boolean(warn));
  }

  async function loadDirectoryChildren(dirNode) {
    if (!dirNode || dirNode.loaded || !currentSpace()) {
      return;
    }
    setTreeStatus(`Loading ${dirNode.path || dirNode.label}…`);
    try {
      const prefix = dirNode.path ? `${dirNode.path}/` : "";
      const symbols = await fetchSymbolsForTree(currentSpace(), prefix);
      addSymbolsToParent(dirNode, symbols, dirNode.path || "");
      dirNode.loaded = true;
      sortTreeChildren(dirNode);
      renderFunctionTree(treeRoot, functionTree);
      setTreeStatus(
        treeLazyMode ? "Large workspace — expand directories to load symbols" : "",
        treeLazyMode
      );
    } catch (err) {
      setTreeStatus(`Tree load failed: ${err.message}`, true);
    }
  }

  async function toggleTreeNode(dirNode, liEl) {
    if (dirNode.kind !== "directory" && dirNode.kind !== "file") {
      return;
    }
    if (!dirNode.loaded && treeLazyMode && dirNode.kind === "directory") {
      await loadDirectoryChildren(dirNode);
    }
    dirNode.expanded = !dirNode.expanded;
    const childList = liEl.querySelector(":scope > .tree-children");
    const toggle = liEl.querySelector(":scope > .tree-row > .tree-toggle");
    if (childList) {
      childList.classList.toggle("expanded", dirNode.expanded);
    }
    if (toggle) {
      toggle.textContent = dirNode.expanded ? "▼" : "▶";
      toggle.setAttribute("aria-expanded", String(dirNode.expanded));
    }
  }

  function markTreeSelected(key) {
    selectedTreeKey = key;
    functionTree.querySelectorAll(".tree-label.selected").forEach((el) => {
      el.classList.remove("selected");
    });
    if (!key) {
      return;
    }
    const btn = functionTree.querySelector(`[data-tree-key="${CSS.escape(key)}"]`);
    if (btn) {
      btn.classList.add("selected");
      btn.scrollIntoView({ block: "nearest" });
    }
  }

  function highlightTreeNode(nodeId, relPath) {
    if (!treeRoot) {
      return;
    }
    let key = null;
    if (nodeId) {
      key = `id:${nodeId}`;
      if (!functionTree.querySelector(`[data-tree-key="${CSS.escape(key)}"]`)) {
        key = `id:file:${relPath || ""}`;
      }
    }
    if (key) {
      markTreeSelected(key);
    }
  }

  async function onTreeLabelClick(node) {
    markTreeSelected(node._key);

    if (node.kind === "file") {
      filePath.value = node.path;
      await loadFileGraph();
      return;
    }

    if (node.kind === "directory") {
      return;
    }

    if (node.symbol) {
      selectSymbol(node.symbol);
    }
  }

  function renderTreeNode(node) {
    const li = document.createElement("li");
    li.className = "tree-item";
    li.setAttribute("role", "treeitem");

    const row = document.createElement("div");
    row.className = "tree-row";

    const hasChildren =
      node.children.length > 0 || (treeLazyMode && node.kind === "directory" && !node.loaded);
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = `tree-toggle${hasChildren ? "" : " hidden"}`;
    toggle.textContent = node.expanded ? "▼" : "▶";
    toggle.setAttribute("aria-expanded", String(node.expanded));
    toggle.setAttribute("aria-label", node.expanded ? "Collapse" : "Expand");
    toggle.addEventListener("click", (evt) => {
      evt.stopPropagation();
      toggleTreeNode(node, li).catch((err) => setTreeStatus(`Expand failed: ${err.message}`, true));
    });

    const label = document.createElement("button");
    label.type = "button";
    label.className = `tree-label kind-${node.kind}${selectedTreeKey === node._key ? " selected" : ""}`;
    label.textContent = node.label;
    label.dataset.treeKey = node._key;
    if (node.node_id) {
      label.dataset.nodeId = node.node_id;
    }
    label.addEventListener("click", () => {
      onTreeLabelClick(node).catch((err) => setStatus(`Navigation failed: ${err.message}`, false));
    });

    row.appendChild(toggle);
    row.appendChild(label);
    li.appendChild(row);

    if (hasChildren) {
      const childList = document.createElement("ul");
      childList.className = `tree-children${node.expanded ? " expanded" : ""}`;
      childList.setAttribute("role", "group");
      for (const child of node.children) {
        childList.appendChild(renderTreeNode(child));
      }
      li.appendChild(childList);
    }

    return li;
  }

  function renderFunctionTree(root, container) {
    container.innerHTML = "";
    if (!root || !root.children.length) {
      container.innerHTML = '<li class="tree-empty">No symbols indexed</li>';
      return;
    }
    for (const child of root.children) {
      container.appendChild(renderTreeNode(child));
    }
  }

  async function refreshFunctionTree() {
    if (!currentSpace() || treeLoading) {
      return;
    }
    treeLoading = true;
    treeRoot = null;
    treeLazyMode = false;
    selectedTreeKey = null;
    functionTree.innerHTML = '<li class="tree-empty">Loading tree…</li>';
    setTreeStatus("Loading symbols…");

    try {
      const symbols = await fetchSymbolsForTree(currentSpace(), "");
      if (!symbols.length) {
        functionTree.innerHTML = '<li class="tree-empty">No symbols indexed</li>';
        setTreeStatus("");
        return;
      }

      if (symbols.length > LAZY_THRESHOLD) {
        treeLazyMode = true;
        treeRoot = buildLazyRootTree(symbols);
        setTreeStatus(
          `${symbols.length} symbols — expand directories to load (large workspace)`,
          true
        );
      } else {
        treeRoot = buildSymbolTree(symbols);
        setTreeStatus(`${symbols.length} symbols`);
      }
      renderFunctionTree(treeRoot, functionTree);
    } catch (err) {
      functionTree.innerHTML = `<li class="tree-empty">Failed to load tree</li>`;
      setTreeStatus(`Tree error: ${err.message}`, true);
    } finally {
      treeLoading = false;
    }
  }

  /* --- Pane resize --- */

  function paneMaxWidth() {
    return Math.floor(window.innerWidth * PANE_MAX_RATIO);
  }

  function setPaneWidth(px) {
    const clamped = Math.max(PANE_MIN_WIDTH, Math.min(px, paneMaxWidth()));
    document.documentElement.style.setProperty("--pane-width", `${clamped}px`);
    return clamped;
  }

  function restorePaneWidth() {
    const saved = localStorage.getItem(PANE_WIDTH_KEY);
    if (saved) {
      const px = parseInt(saved, 10);
      if (!Number.isNaN(px)) {
        setPaneWidth(px);
      }
    }
  }

  function initResizeHandle() {
    if (!resizeHandle || window.matchMedia("(max-width: 800px)").matches) {
      return;
    }

    let dragging = false;
    let startX = 0;
    let startWidth = 0;

    function onMouseMove(evt) {
      if (!dragging) {
        return;
      }
      const delta = evt.clientX - startX;
      setPaneWidth(startWidth + delta);
    }

    function onMouseUp() {
      if (!dragging) {
        return;
      }
      dragging = false;
      document.body.classList.remove("resizing");
      resizeHandle.classList.remove("active");
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      const width = parseInt(
        getComputedStyle(document.documentElement).getPropertyValue("--pane-width"),
        10
      );
      if (!Number.isNaN(width)) {
        localStorage.setItem(PANE_WIDTH_KEY, String(width));
      }
    }

    resizeHandle.addEventListener("mousedown", (evt) => {
      if (window.matchMedia("(max-width: 800px)").matches) {
        return;
      }
      evt.preventDefault();
      dragging = true;
      startX = evt.clientX;
      startWidth = treePane.getBoundingClientRect().width;
      document.body.classList.add("resizing");
      resizeHandle.classList.add("active");
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    });
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
    syncUrlState({ q, file: filePath.value.trim() });
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
    syncUrlState({ file: rel, q: symbolQuery.value.trim() });
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
    markTreeSelected(`id:file:${rel}`);
  }

  async function expandNode(nodeId) {
    if (!nodeId || !currentSpace()) {
      return;
    }
    const data = await apiFetch(
      `/spaces/${encodeURIComponent(currentSpace())}/node/${encodeURIComponent(nodeId)}/neighbors?depth=1&max_nodes=50`
    );
    for (const nb of data.neighbors || []) {
      addNodeRecord(nb);
      addEdgeRecord({
        source: nodeId,
        target: nb.node_id,
        edge: nb.edge || "",
      });
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
    restorePaneWidth();
    initResizeHandle();
    applyTabVisibility();
    restoreApiKey();
    try {
      await loadSpaces();
      const params = new URLSearchParams(window.location.search);
      const tab = (params.get("tab") || "graph").toLowerCase();
      pendingMemoryId = params.get("memory") || null;

      if (tab === "cavern") {
        await setTab("cavern", { memoryId: pendingMemoryId, forceReload: true });
      } else {
        await setTab("graph");
        await refreshFunctionTree();
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
      }
    } catch (err) {
      setStatus(`Error: ${err.message}`, false);
    }
  }

  async function reloadAfterApiKeyChange() {
    persistApiKey();
    clearGraph();
    hitList.innerHTML = "";
    try {
      await loadSpaces();
      if (currentTab === "cavern") {
        resetCavernDetail();
        await loadMemoriesIndex();
      } else {
        await refreshFunctionTree();
      }
      setStatus(`Space: ${currentSpace()}`, false);
    } catch (err) {
      setStatus(`Error: ${err.message}`, false);
    }
  }

  spaceSelect.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEY, currentSpace());
    clearGraph();
    hitList.innerHTML = "";
    if (currentTab === "cavern") {
      resetCavernDetail();
      syncUrlState({ memory: "" });
      loadMemoriesIndex().catch((err) => setStatus(`Cavern error: ${err.message}`, lastStale));
    } else {
      syncUrlState({ file: "", q: "", memory: "" });
      setStatus(`Space: ${currentSpace()}`, false);
      refreshFunctionTree().catch((err) => setTreeStatus(`Tree error: ${err.message}`, true));
    }
  });

  if (apiKeyInput) {
    apiKeyInput.addEventListener("change", () => {
      reloadAfterApiKeyChange().catch((err) => setStatus(`Error: ${err.message}`, false));
    });
    apiKeyInput.addEventListener("keydown", (evt) => {
      if (evt.key === "Enter") {
        evt.preventDefault();
        reloadAfterApiKeyChange().catch((err) => setStatus(`Error: ${err.message}`, false));
      }
    });
  }
  tabGraph.addEventListener("click", () => {
    setTab("graph").catch((err) => setStatus(`Tab switch failed: ${err.message}`, lastStale));
  });

  tabCavern.addEventListener("click", () => {
    setTab("cavern", { forceReload: true }).catch((err) =>
      setStatus(`Tab switch failed: ${err.message}`, lastStale)
    );
  });

  memoryBodyToggle.addEventListener("click", () => {
    if (!selectedMemory) {
      return;
    }
    memoryBodyExpanded = !memoryBodyExpanded;
    renderMemoryDetail(selectedMemory);
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
