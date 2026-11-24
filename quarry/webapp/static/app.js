const POLL_MS = 30000;
const PROFILES = ["Nebula", "Cobalt", "Amethyst", "Ember"];
const PAGES = [
  { key: "graph", label: "graph", icon: "M6 8a2 2 0 100-4 2 2 0 000 4zM18 20a2 2 0 100-4 2 2 0 000 4zM18 8a2 2 0 100-4 2 2 0 000 4zM8 7l8 9M8 7h8",
    title: "dependency graph", sub: "click a node to trace what it blocks" },
  { key: "ready", label: "ready", icon: "M4 7h16M4 12h11M4 17h6",
    title: "ready", sub: "every blocker closed, claimable now" },
  { key: "board", label: "board", icon: "M4 5h5v14H4zM10 5h5v9h-5zM16 5h4v11h-4z",
    title: "board", sub: "every issue under the status it carries" },
  { key: "paths", label: "paths", icon: "M4 18h4l4-12h4M16 6h4M16 18h4",
    title: "workflow paths", sub: "six journeys through quarry, first command to last" },
  { key: "guide", label: "guide", icon: "M5 4h11l3 3v13H5zM9 9h7M9 13h7M9 17h4",
    title: "every command and skill", sub: "a command is typed, a skill fires on what you say" },
  { key: "strata", label: "strata", icon: "M3 8h18M3 13h18M3 18h18",
    title: "strata", sub: "sealed context windows, thickness by preserved lines" },
  { key: "activity", label: "activity", icon: "M3 12h4l3-7 4 14 3-7h4",
    title: "activity", sub: "tracker events, newest first" },
  { key: "settings", label: "settings", icon: "M12 15a3 3 0 100-6 3 3 0 000 6zM4 12h2M18 12h2M12 4v2M12 18v2",
    title: "settings", sub: "interaction mode, colour profile, connection" },
];

const BOARD_TABS = ["kanban", "roadmap", "fleet"];

const BOARD_HINT = {
  kanban: "GET /api/snapshot returns nodes and bd's status vocabulary",
  roadmap: "order derived from the blocks graph; parent-child edges make the lanes",
  fleet: "GET /api/fleet runs bd merge-slot check, gate list and swarm list",
};

const BOARD_LEDE = {
  fleet:
    "What coordinates several agents on this one tracker, read from bd rather than "
    + "inferred: who holds the merge slot that serialises conflict resolution, what is "
    + "waiting on a gate, and which swarm molecules are open. Fetched when you open this "
    + "tab rather than with every poll, because these commands are slow and most projects "
    + "never run a fleet. Empty here is the normal answer, not a failure.",
  kanban:
    "Every issue bd holds, filed under the status it actually carries. The columns are "
    + "bd's own status vocabulary, so a column stays visible even when nothing is in it: "
    + "an empty column is a fact about the tracker, not a gap in the board. Click a card "
    + "to open it on the graph. Hover a column heading to see what that status means.",
  roadmap:
    "The same work in execution order, grouped by the objective it serves. Objectives and "
    + "non-goals are declared in CHARTER.md; a ticket joins an objective by carrying its "
    + "label. Work no objective claims still appears below, by epic and priority, so it "
    + "reads as unclaimed rather than hidden. Quarry keeps no dates, so the waves are not a "
    + "calendar: wave 1 is everything nothing blocks, and each later wave begins only once "
    + "the wave before it closes. Dashed wires are blocks edges.",
};

const state = {
  snapshot: null,
  etag: "",
  page: remembered("quarry.page", "graph"),
  boardtab: remembered("quarry.boardtab", "kanban"),
  profile: remembered("quarry.profile", "Nebula"),
  collapsed: remembered("quarry.rail", "0") === "1",
  focus: null,
  passages: null,
  guide: null,
  fleet: null,
  fleetPending: false,
  busy: false,
};

const el = {};
let graph = null;
let board = null;
let roadmap = null;
let fleet = null;
let panel = null;
let stream = null;
let toastTimer = 0;

function remembered(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch (error) {
    return fallback;
  }
}

function remember(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    return;
  }
}

function bind(name) {
  return document.querySelector(`[data-bind="${name}"]`);
}

function boot() {
  ["rail", "railtoggle", "nav", "swatches", "graph", "labels", "graphwrap", "detail",
   "readyrows", "feedrows", "seams", "passages", "create", "newtitle", "newtype",
   "newpri", "askform", "askbox", "beacon", "toast", "lanes", "guidebody", "drift",
   "flowstrip", "release", "resetview", "board", "roadmap", "fleet", "boardtabs",
   "boardlede", "boardhint", "settings"].forEach((id) => {
    el[id] = document.getElementById(id);
  });

  graph = makeGraph(el.graph, el.labels, selectNode, clearNode);
  board = makeBoard(el.board, openFromBoard);
  roadmap = makeRoadmap(el.roadmap, openFromBoard);
  fleet = makeFleet(el.fleet);
  panel = makeSettings(el.settings, PROFILES, applyProfile, toast);
  [...el.boardtabs.children].forEach((tab) => {
    tab.addEventListener("click", () => showBoardTab(tab.dataset.tab));
  });
  mountTooltips();
  buildNav();
  buildSwatches();
  applyProfile(state.profile);
  applyRail(state.collapsed);
  showPage(state.page);

  el.railtoggle.addEventListener("click", () => {
    state.collapsed = !state.collapsed;
    remember("quarry.rail", state.collapsed ? "1" : "0");
    applyRail(state.collapsed);
    if (state.page === "graph") drawGraph();
    if (state.page === "board") drawBoard();
  });

  el.create.querySelector(".btn").dataset.help = HELP.create;
  el.askbox.dataset.help = HELP.ask;
  el.release.dataset.help = HELP.release;
  el.release.addEventListener("click", () => {
    graph.release();
    toast("all nodes released");
  });
  el.resetview.dataset.help = HELP.resetview;
  el.resetview.addEventListener("click", () => {
    graph.resetView();
    toast("view reset");
  });
  el.create.addEventListener("submit", createIssue);
  el.askform.addEventListener("submit", askHistory);
  window.addEventListener("resize", () => {
    if (state.page === "graph") drawGraph();
    if (state.page === "board" && state.boardtab === "roadmap") drawBoard();
  });

  poll();
  loadGuide();
  listen();
  setInterval(poll, POLL_MS);
}

function buildNav() {
  PAGES.forEach((page) => {
    const button = document.createElement("button");
    button.className = "nvi";
    button.type = "button";
    button.title = page.label;
    button.innerHTML =
      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"` +
      ` stroke-linecap="round" stroke-linejoin="round"><path d="${page.icon}"></path></svg>` +
      `<span>${page.label}</span><span class="count" data-count="${page.key}"></span>`;
    button.addEventListener("click", () => showPage(page.key));
    el.nav.appendChild(button);
  });
}

function buildSwatches() {
  PROFILES.forEach((name) => {
    const swatch = document.createElement("button");
    swatch.className = "sw";
    swatch.type = "button";
    swatch.title = name;
    swatch.setAttribute("aria-label", `${name} colour profile`);
    swatch.dataset.profile = name;
    el.swatches.appendChild(swatch);
    swatch.addEventListener("click", () => applyProfile(name));
  });
  paintSwatches();
}

function paintSwatches() {
  el.swatches.querySelectorAll(".sw").forEach((swatch) => {
    setStyle(swatch, "background", profileBlue(swatch.dataset.profile));
    setAttr(swatch, "aria-pressed", String(swatch.dataset.profile === state.profile));
  });
}

function profileBlue(name) {
  const hues = { Nebula: 262, Cobalt: 244, Amethyst: 300, Ember: 66 };
  const chroma = name === "Ember" ? 0.105 : name === "Cobalt" ? 0.125 : 0.115;
  const light = name === "Ember" ? 0.75 : 0.72;
  return `oklch(${light} ${chroma} ${hues[name]})`;
}

function applyProfile(name) {
  state.profile = name;
  remember("quarry.profile", name);
  document.documentElement.setAttribute("data-profile", name);
  paintSwatches();
}

function applyRail(collapsed) {
  el.rail.classList.toggle("collapsed", collapsed);
  el.railtoggle.title = collapsed ? "Expand the rail" : "Collapse the rail";
}

function showPage(key) {
  state.page = key;
  remember("quarry.page", key);
  const page = PAGES.find((entry) => entry.key === key) || PAGES[0];
  setText(bind("pagetitle"), page.title);
  setText(bind("pagesub"), page.sub);
  PAGES.forEach((entry) => {
    document.getElementById(`page-${entry.key}`).hidden = entry.key !== key;
  });
  [...el.nav.children].forEach((button, index) => {
    if (PAGES[index].key === key) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (state.snapshot) render();
  if (key === "settings") panel.draw(state.profile);
}

function listen() {
  stream = new EventSource("/api/events");
  stream.addEventListener("changed", () => poll());
  stream.addEventListener("error", () => live(false));
  stream.addEventListener("open", () => live(true));
}

async function poll() {
  try {
    const headers = state.etag ? { "If-None-Match": state.etag } : {};
    const response = await fetch("/api/snapshot", { headers });
    if (response.status === 304) {
      live(true);
      return;
    }
    if (!response.ok) throw new Error(`snapshot failed: ${response.status}`);
    state.etag = response.headers.get("ETag") || "";
    state.snapshot = await response.json();
    live(true);
    render();
  } catch (error) {
    live(false);
  }
}

function live(up) {
  el.beacon.classList.toggle("live", up);
  el.beacon.classList.toggle("down", !up);
  setText(bind("wiretext"), up ? "live" : "reconnecting");
}

function render() {
  const snap = state.snapshot;
  if (!snap) return;
  const counts = snap.counts || {};
  const lines = (snap.mesh && snap.mesh.total_lines) || 0;

  setText(bind("project"), snap.project || "quarry");
  setText(bind("c-ready"), `${counts.ready || 0} ready`);
  setText(bind("c-claimed"), `${counts.claimed || 0} claimed`);
  setText(bind("c-blocked"), `${counts.blocked || 0} blocked`);
  setText(bind("c-lines"), `${count(lines)} preserved lines`);

  setText(el.nav.querySelector('[data-count="graph"]'), counts.total || 0);
  setText(el.nav.querySelector('[data-count="ready"]'), counts.ready || 0);
  setText(el.nav.querySelector('[data-count="board"]'), counts.total || 0);
  setText(el.nav.querySelector('[data-count="strata"]'), (snap.mesh.units || []).length);
  setText(el.nav.querySelector('[data-count="activity"]'), (snap.activity || []).length);

  if (state.page === "graph") drawGraph();
  if (state.page === "board") drawBoard();
  if (state.page === "ready") drawReady();
  if (state.page === "strata") drawStrata();
  if (state.page === "activity") drawActivity();
  if (state.page === "paths" || state.page === "guide") loadGuide();
}

function drawGraph() {
  const snap = state.snapshot;
  if (!snap) return;
  const drawn = graph.render(snap.nodes, snap.edges, state.focus);
  setText(
    bind("pagesub"),
    `${drawn.nodes} open issues, ${drawn.edges} edges between them, `
    + "click a node to trace what it blocks",
  );
  drawDetail();
}

function drawBoard() {
  const active = BOARD_TABS.includes(state.boardtab) ? state.boardtab : "kanban";
  el.board.hidden = active !== "kanban";
  el.roadmap.hidden = active !== "roadmap";
  el.fleet.hidden = active !== "fleet";
  [...el.boardtabs.children].forEach((tab) => {
    setAttr(tab, "aria-selected", String(tab.dataset.tab === active));
  });
  setText(el.boardlede, BOARD_LEDE[active]);
  setText(el.boardhint, BOARD_HINT[active]);

  if (active === "fleet") {
    loadFleet();
    return;
  }
  const snap = state.snapshot;
  if (!snap) return;
  if (active === "kanban") {
    const drawn = board.draw(snap.nodes || [], snap.statuses || [], state.focus);
    setText(bind("pagesub"), `${drawn.cards} issues across ${drawn.columns} bd statuses`);
    return;
  }
  const drawn = roadmap.draw(snap.nodes || [], snap.edges || [], state.focus, snap.charter);
  setText(
    bind("pagesub"),
    `${drawn.objectives} objectives, ${drawn.unclaimed} issues no objective claims, `
    + `${drawn.waves} waves, ${drawn.wires} dependencies`,
  );
}

async function loadFleet() {
  fleet.draw(state.fleet);
  if (state.fleet || state.fleetPending) return;
  state.fleetPending = true;
  setText(bind("pagesub"), "asking bd for slot, gates and swarms");
  try {
    const response = await fetch("/api/fleet");
    if (!response.ok) throw new Error(`fleet failed: ${response.status}`);
    state.fleet = await response.json();
    fleet.draw(state.fleet);
    setText(bind("pagesub"), "merge slot, open gates and swarm molecules");
  } catch (error) {
    toast(String(error), true);
    setText(bind("pagesub"), "coordination could not be read");
  } finally {
    state.fleetPending = false;
  }
}

function showBoardTab(tab) {
  state.boardtab = tab;
  remember("quarry.boardtab", tab);
  drawBoard();
}

function openFromBoard(id) {
  state.focus = id;
  showPage("graph");
}

function selectNode(id) {
  state.focus = state.focus === id ? null : id;
  drawGraph();
}

function clearNode() {
  state.focus = null;
  drawGraph();
}

function drawReady() {
  const nodes = (state.snapshot.nodes || []).filter((node) => node.state === "ready" || node.state === "claimed");
  syncList(el.readyrows, nodes, (node) => node.id, buildRow, (host, node) => {
    setText(host.querySelector(".rid"), node.id);
    setText(host.querySelector(".rtx"), node.title);
    const pri = host.querySelector(".rpri");
    setText(pri, `p${node.priority}`);
    pri.className = `rpri p${node.priority}`;
    const claim = host.querySelector('[data-act="claim"]');
    const taken = node.state === "claimed";
    setText(claim, taken ? "Claimed" : "Claim");
    setAttr(claim, "aria-disabled", String(taken));
    claim.classList.toggle("off", taken);
    claim.dataset.help = taken ? HELP.claimed : HELP.claim;
  });
  if (!nodes.length) empty(el.readyrows, "nothing ready: every open issue is waiting on a blocker");
}

function buildRow(node) {
  const host = document.createElement("div");
  host.className = "row";
  host.append(tag("span", "rid", ""), tag("span", "rtx", ""), tag("span", "rpri", ""));
  const acts = document.createElement("div");
  acts.className = "racts";
  const claim = action("Claim", () => {
    if (claim.getAttribute("aria-disabled") === "true") return;
    act(`/api/issues/${node.id}/claim`);
  }, "", HELP.claim);
  claim.dataset.act = "claim";
  acts.append(claim, action("Close", () => closeWithReason(node.id), "", HELP.close));
  host.appendChild(acts);
  return host;
}

function drawStrata() {
  const units = (state.snapshot.mesh && state.snapshot.mesh.units) || [];
  const total = Math.max(1, (state.snapshot.mesh && state.snapshot.mesh.total_lines) || 1);
  syncList(el.seams, units, (unit) => unit.id, () => {
    const host = document.createElement("div");
    host.className = "seam";
    host.append(tag("span", "rid", ""), tag("span", "rtx", ""), tag("span", "lines", ""));
    return host;
  }, (host, unit, index) => {
    setText(host.querySelector(".rid"), unit.id);
    setText(host.querySelector(".rtx"), unit.opening);
    setText(host.querySelector(".lines"), `${count(unit.lines)} lines`);
    setStyle(host, "height", `${Math.max(34, Math.round((unit.lines / total) * 380))}px`);
    setStyle(host, "background", `oklch(${0.238 - index * 0.021} ${0.020 - index * 0.002} ${268 + index * 17})`);
  });
  if (!units.length) empty(el.seams, "no sealed units yet: the mesh starts at the first seal");
  drawPassages();
}

function drawPassages() {
  const found = state.passages;
  el.passages.innerHTML = "";
  if (!found) return;
  if (!found.found) {
    empty(el.passages, found.terms.length
      ? `nothing preserved contains: ${found.terms.join(", ")}`
      : "that question carried no words worth searching for");
    return;
  }
  found.passages.forEach((passage) => {
    const card = document.createElement("div");
    card.className = "passage";
    card.append(tag("div", "paddr", passage.address), tag("pre", "ptext", passage.text));
    el.passages.appendChild(card);
  });
}

function drawActivity() {
  const events = state.snapshot.activity || [];
  const timing = state.snapshot.timing || {};
  setText(bind("pagesub"), timing.closed
    ? `tracker events, newest first. ${timing.closed} closed, median lead time `
      + `${spell(timing.lead_seconds)} from filed to closed`
      + (timing.cycle_counted
        ? `, median cycle time ${spell(timing.cycle_seconds)} from claimed to closed `
          + `over the ${timing.cycle_counted} that were claimed`
        : ", none of them were ever claimed, so there is no cycle time")
      + (timing.bugs_closed ? `, ${spell(timing.bug_lead_seconds)} for ${timing.bugs_closed} bugs` : "")
    : "tracker events, newest first. Nothing has closed yet, so there is no lead time to report");
  syncList(el.feedrows, events, (event, index) => `${event.id}:${event.kind}:${index}`, () => {
    const host = document.createElement("div");
    host.className = "row";
    host.append(tag("span", "rid", ""), tag("span", "rtx", ""), tag("span", "rpri", ""));
    return host;
  }, (host, event) => {
    setText(host.querySelector(".rid"), since(event.at));
    setText(host.querySelector(".rtx"), `${event.id} ${event.kind}: ${event.text}`);
    setText(host.querySelector(".rpri"),
      event.kind === "closed" && event.after != null ? `in ${spell(event.after)}`
        : event.kind === "closed" ? "done" : "");
  });
  if (!events.length) empty(el.feedrows, "no tracker events recorded yet");
}

async function createIssue(event) {
  event.preventDefault();
  const title = el.newtitle.value.trim();
  if (!title) return;
  const done = await send("/api/issues", "POST", {
    title,
    type: el.newtype.value,
    priority: Number(el.newpri.value),
  });
  if (done) {
    el.newtitle.value = "";
    toast(`created ${done.id}`);
    refresh();
  }
}

async function askHistory(event) {
  event.preventDefault();
  const question = el.askbox.value.trim();
  if (!question) return;
  const found = await send("/api/recall", "POST", { question });
  if (found) {
    state.passages = found;
    drawPassages();
  }
}

async function closeWithReason(id) {
  const reason = window.prompt(`Close ${id}. What was done, and how was it verified?`, "");
  if (reason === null) return;
  await act(`/api/issues/${id}/close`, { reason });
}

async function removeIssue(id) {
  if (!window.confirm(`Delete ${id} permanently? This cannot be undone.`)) return;
  const done = await send(`/api/issues/${id}`, "DELETE", null);
  if (done) {
    if (state.focus === id) state.focus = null;
    toast(`deleted ${id}`);
    refresh();
  }
}

async function act(path, body) {
  const done = await send(path, "POST", body || {});
  if (done) {
    toast("done");
    refresh();
  }
}

async function send(path, method, body) {
  if (state.busy) {
    toast("still finishing the last change, try that again", true);
    return null;
  }
  state.busy = true;
  try {
    const options = { method, headers: {} };
    if (body !== null) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body || {});
    }
    const response = await fetch(path, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      toast(payload.error || `request failed: ${response.status}`, true);
      return null;
    }
    return payload;
  } catch (error) {
    toast(String(error), true);
    return null;
  } finally {
    state.busy = false;
  }
}

function refresh() {
  state.etag = "";
  poll();
}

function syncList(host, items, keyOf, create, update) {
  const live = new Set();
  items.forEach((item, index) => {
    const key = keyOf(item, index);
    live.add(key);
    let node = host.querySelector(`[data-key="${cssEscape(key)}"]`);
    if (!node) {
      node = create(item);
      node.dataset.key = key;
      host.appendChild(node);
    }
    update(node, item, index);
    if (host.children[index] !== node) host.insertBefore(node, host.children[index] || null);
  });
  [...host.children].forEach((child) => {
    if (child.dataset.key !== undefined && !live.has(child.dataset.key)) child.remove();
    if (child.dataset.key === undefined) child.remove();
  });
}

function cssEscape(value) {
  return String(value).replace(/["\\]/g, "\\$&");
}

function tag(name, className, text) {
  const node = document.createElement(name);
  node.className = className;
  node.textContent = text;
  return node;
}

function row(className, children) {
  const node = document.createElement("div");
  node.className = className;
  node.append(...children);
  return node;
}

function action(label, onClick, extra, help) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = extra ? `btn ${extra}` : "btn";
  button.textContent = label;
  if (help) button.dataset.help = help;
  button.addEventListener("click", onClick);
  return button;
}

function empty(host, message) {
  host.innerHTML = "";
  host.appendChild(tag("p", "empty", message));
}

function count(value) {
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

function spell(seconds) {
  if (seconds == null) return "";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

function since(stamp) {
  const then = Date.parse(stamp);
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

function toast(message, bad) {
  el.toast.textContent = message;
  el.toast.classList.toggle("bad", Boolean(bad));
  el.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.toast.hidden = true;
  }, bad ? 6000 : 2600);
}

document.addEventListener("DOMContentLoaded", boot);
