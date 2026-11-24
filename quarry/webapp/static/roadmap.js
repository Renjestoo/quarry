const LANE_LABEL_PX = 186;
const WAVE_MIN_PX = 168;
const WIRE_BOW = 26;
const LANE_HUES = [262, 158, 22, 300, 72, 190, 340, 232, 120];
const LOOSE_LANE = { id: "", title: "unparented work", loose: true };
const COORDINATION_LABEL = "gt:slot";
const COORDINATION_TYPE = "molecule";
const LOCK_LANE = { id: "", title: "coordination, not work", coordination: true };

function makeRoadmap(host, onSelect) {
  function draw(nodes, edges, focus, charter) {
    const byId = new Map(nodes.map((node) => [node.id, node]));
    const kin = edges.filter((edge) => edge.kind === "parent-child");
    const blocks = edges.filter((edge) => edge.kind === "blocks");
    const claimed = objectiveLanes(nodes, charter);
    const rest = nodes.filter((node) => !claimed.taken.has(node.id));
    const lanes = claimed.lanes.concat(buildLanes(rest, byId, kin));
    const waves = 1 + nodes.reduce((top, node) => Math.max(top, node.stage || 0), 0);
    const spans = spanBy(nodes, blocks, byId);

    const heldLeft = host.scrollLeft;
    host.innerHTML = "";
    const grid = document.createElement("div");
    grid.className = "rmgrid";
    grid.style.setProperty("--rm-label", `${LANE_LABEL_PX}px`);
    grid.style.setProperty("--rm-waves", String(waves));
    grid.style.setProperty("--rm-wave-min", `${WAVE_MIN_PX}px`);
    grid.appendChild(header(waves, currentWave(nodes)));
    lanes.forEach((lane, index) => {
      grid.appendChild(laneBlock(lane, index, spans, waves, focus, onSelect));
    });
    host.appendChild(grid);
    const wires = drawWires(grid, blocks, byId);
    host.appendChild(nonGoals(charter));
    host.scrollLeft = heldLeft;
    return {
      lanes: lanes.length,
      waves,
      items: nodes.length,
      wires,
      objectives: claimed.lanes.length,
      unclaimed: rest.length,
    };
  }

  return { draw };
}

function nonGoals(charter) {
  const items = (charter && charter.non_goals) || [];
  const box = document.createElement("section");
  box.className = "rmexcluded";
  if (!items.length) {
    box.append(tag("span","rmxhead", "no non-goals declared"));
    box.append(tag("span","rmxnote", `Record exclusions in ${(charter && charter.path) || "CHARTER.md"} so a later session learns an absence was a choice.`));
    return box;
  }
  box.append(tag("span","rmxhead", `deliberately not building (${items.length})`));
  const list = document.createElement("ul");
  list.className = "rmxlist";
  items.forEach((text) => {
    const row = document.createElement("li");
    row.className = "rmxitem";
    row.textContent = stripMarks(text);
    list.appendChild(row);
  });
  box.appendChild(list);
  return box;
}

function stripMarks(text) {
  return text.replace(/\*\*/g, "").replace(/`/g, "");
}

function objectiveLanes(nodes, charter) {
  const objectives = (charter && charter.objectives) || [];
  const taken = new Set();
  const lanes = [];
  objectives.forEach((objective) => {
    const items = nodes.filter((node) => (node.labels || []).includes(objective.label));
    items.forEach((node) => taken.add(node.id));
    lanes.push({
      id: objective.id,
      title: objective.title,
      objective,
      items,
    });
  });
  return { lanes, taken };
}

function buildLanes(nodes, byId, kin) {
  const childrenOf = new Map();
  const parentOf = new Map();
  kin.forEach((edge) => {
    if (!byId.has(edge.from) || !byId.has(edge.to)) return;
    if (!childrenOf.has(edge.from)) childrenOf.set(edge.from, []);
    childrenOf.get(edge.from).push(edge.to);
    parentOf.set(edge.to, edge.from);
  });

  const lanes = [];
  [...childrenOf.keys()]
    .map((id) => byId.get(id))
    .sort((a, b) => (a.stage - b.stage) || a.priority - b.priority || a.id.localeCompare(b.id))
    .forEach((epic) => {
      const kids = childrenOf.get(epic.id).map((id) => byId.get(id)).filter(Boolean);
      lanes.push({ id: epic.id, title: epic.title, epic, items: kids });
    });

  const unowned = nodes.filter((node) => !parentOf.has(node.id) && !childrenOf.has(node.id));
  const locks = unowned.filter(isCoordination);
  const byPriority = new Map();
  unowned.filter((node) => !isCoordination(node)).forEach((node) => {
    if (!byPriority.has(node.priority)) byPriority.set(node.priority, []);
    byPriority.get(node.priority).push(node);
  });
  [...byPriority.keys()].sort((a, b) => a - b).forEach((priority) => {
    lanes.push({
      ...LOOSE_LANE,
      title: `${LOOSE_LANE.title}, P${priority}`,
      items: byPriority.get(priority),
    });
  });
  if (locks.length) lanes.push({ ...LOCK_LANE, items: locks });
  return lanes;
}

function isCoordination(node) {
  return (node.labels || []).includes(COORDINATION_LABEL) || node.type === COORDINATION_TYPE;
}

function spanBy(nodes, blocks, byId) {
  const soonest = new Map();
  blocks.forEach((edge) => {
    const dependent = byId.get(edge.to);
    if (!dependent) return;
    const at = soonest.get(edge.from);
    soonest.set(edge.from, at === undefined ? dependent.stage : Math.min(at, dependent.stage));
  });
  const spans = new Map();
  nodes.forEach((node) => {
    const next = soonest.get(node.id);
    spans.set(node.id, Math.max(1, next === undefined ? 1 : next - node.stage));
  });
  return spans;
}

function currentWave(nodes) {
  const live = nodes.filter((node) => node.state !== "closed");
  if (!live.length) return -1;
  return live.reduce((first, node) => Math.min(first, node.stage || 0), Infinity);
}

function header(waves, now) {
  const strip = document.createElement("div");
  strip.className = "rmrow rmhead";
  strip.appendChild(cell("rmcorner", "order of execution"));
  for (let wave = 0; wave < waves; wave += 1) {
    const head = cell("rmwave", wave === now ? `wave ${wave + 1} · here` : `wave ${wave + 1}`);
    head.style.gridColumn = `${wave + 2} / span 1`;
    if (wave === now) head.dataset.now = "1";
    head.dataset.help = wave === 0
      ? "Wave 1: nothing blocks these, so they can start immediately."
      : `Wave ${wave + 1}: starts once every wave-${wave} blocker it depends on is closed.`;
    if (wave === now) {
      head.dataset.help += " This is where execution sits: the earliest wave still holding open work.";
    }
    strip.appendChild(head);
  }
  return strip;
}

function laneBlock(lane, index, spans, waves, focus, onSelect) {
  const block = document.createElement("section");
  block.className = "rmlane";
  block.style.setProperty("--lane-hue", String(LANE_HUES[index % LANE_HUES.length]));
  if (lane.loose) block.dataset.loose = "1";
  if (lane.coordination) block.dataset.coordination = "1";

  if (lane.objective) block.dataset.objective = "1";
  block.appendChild(laneLabel(lane));

  const track = document.createElement("div");
  track.className = "rmtrack";
  if (lane.epic) track.appendChild(milestoneRow(lane, waves, focus, onSelect));
  if (lane.objective && !lane.items.length) {
    track.appendChild(tag("span","rmnone", "no work serves this objective yet"));
  }
  pack(lane.items, spans).forEach((line) => {
    track.appendChild(itemRow(line, spans, waves, focus, onSelect));
  });
  block.appendChild(track);
  return block;
}

const STATE_WORDS = {
  met: "measure holds",
  "at-risk": "measure at risk",
  "not-met": "measure does not hold",
  unassessed: "measure unassessed",
};

function objectiveHelp(lane, state) {
  const measure = lane.objective.measure || "no measure recorded";
  if (!lane.items.length) {
    return `${lane.id} has no work yet. Link a ticket with: bd label add <id> ${lane.objective.label}`;
  }
  const assessment = lane.objective.assessment ? ` ${lane.objective.assessment}` : "";
  if (state === "unassessed") {
    return `${lane.id}. Measured by: ${measure}. Nobody has recorded whether that holds, so the `
      + "count beside it is work closed, not the objective met.";
  }
  return `${lane.id}. Measured by: ${measure}. Last recorded as ${STATE_WORDS[state] || state}.${assessment}`;
}

function laneLabel(lane) {
  const label = document.createElement("div");
  label.className = "rmlabel";
  const done = lane.items.filter((item) => item.state === "closed").length;
  label.append(tag("span","rmlname", lane.title));

  if (lane.objective) {
    const state = lane.objective.state || "unassessed";
    label.append(tag("span","rmlmeta", `${lane.id}  ${done}/${lane.items.length} done`));
    const badge = tag("span","rmlstate", STATE_WORDS[state] || state);
    badge.dataset.state = state;
    label.append(badge);
    label.dataset.help = objectiveHelp(lane, state);
    return label;
  }
  if (lane.epic) {
    label.append(tag("span","rmlmeta", `${lane.id}  ${done}/${lane.items.length} done`));
    label.dataset.help =
      `Epic ${lane.id}. Its children are laid out by the wave they can start in, and the `
      + "marker sits at the wave the last of them completes.";
    return label;
  }
  if (lane.coordination) {
    const held = lane.items.filter((item) => item.state === "claimed").length;
    label.append(tag("span","rmlmeta", `${held} of ${lane.items.length} held`));
    label.dataset.help =
      "bd represents a lock as an issue, so it arrives here looking like work. It is not "
      + "work: the merge slot goes in_progress while one agent resolves conflicts and sits "
      + "open otherwise, and closing it would be wrong. The Fleet tab names who holds it.";
    return label;
  }
  label.append(tag("span","rmlmeta", `${done}/${lane.items.length} done`));
  label.dataset.help =
    "Work no objective claims and no epic owns, grouped by priority so it reads as lanes "
    + "rather than one wall. Link it to an objective with bd label add.";
  return label;
}

function slots(row, waves) {
  for (let wave = 0; wave < waves; wave += 1) {
    const slot = document.createElement("div");
    slot.className = "rmslot";
    slot.style.gridArea = `1 / ${wave + 1} / 2 / span 1`;
    if (wave === waves - 1) slot.dataset.last = "1";
    row.appendChild(slot);
  }
}

function milestoneRow(lane, waves, focus, onSelect) {
  const row = document.createElement("div");
  row.className = "rmrow rmmilerow";
  row.style.setProperty("--rm-waves", String(waves));
  slots(row, waves);
  const at = lane.items.reduce((top, item) => Math.max(top, item.stage || 0), 0);
  const mark = document.createElement("button");
  mark.type = "button";
  mark.className = "rmmile";
  mark.dataset.state = lane.epic.state;
  mark.dataset.id = lane.epic.id;
  if (lane.epic.id === focus) mark.dataset.selected = "1";
  mark.style.gridArea = `1 / ${at + 1} / 2 / span 1`;
  mark.append(tag("span","rmdiamond", ""), tag("span","rmmiletext", lane.epic.title));
  mark.dataset.help =
    `${lane.epic.id} completes here, once every child in this lane is closed.`;
  mark.addEventListener("click", () => onSelect(lane.epic.id));
  row.appendChild(mark);
  return row;
}

function itemRow(line, spans, waves, focus, onSelect) {
  const row = document.createElement("div");
  row.className = "rmrow rmitems";
  row.style.setProperty("--rm-waves", String(waves));
  slots(row, waves);
  line.forEach((item) => {
    const bar = document.createElement("button");
    bar.type = "button";
    bar.className = "rmbar";
    bar.dataset.id = item.id;
    bar.dataset.state = item.state;
    bar.dataset.type = item.type;
    if (item.id === focus) bar.dataset.selected = "1";
    bar.style.gridArea = `1 / ${item.stage + 1} / 2 / span ${spans.get(item.id)}`;
    bar.append(tag("span","rmbtext", item.title));
    if (item.blocked_by && item.blocked_by.length) {
      bar.append(tag("span","rmblock", String(item.blocked_by.length)));
    }
    bar.dataset.help = help(item, spans.get(item.id));
    bar.addEventListener("click", () => onSelect(item.id));
    row.appendChild(bar);
  });
  return row;
}

function help(item, span) {
  const where = `${item.id}, P${item.priority} ${item.type}, starts in wave ${item.stage + 1}`;
  const wait = item.blocked_by && item.blocked_by.length
    ? `. Waiting on ${item.blocked_by.length} open blocker(s): ${item.blocked_by.join(", ")}`
    : "";
  const room = span > 1 ? `. It has ${span} waves before the work it blocks begins` : "";
  return `${where}${wait}${room}.`;
}

function pack(items, spans) {
  const lines = [];
  [...items]
    .sort((a, b) => (a.stage - b.stage) || a.priority - b.priority || a.id.localeCompare(b.id))
    .forEach((item) => {
      const from = item.stage;
      const to = item.stage + spans.get(item.id);
      const line = lines.find((row) => row.every((placed) => {
        const start = placed.stage;
        const end = placed.stage + spans.get(placed.id);
        return to <= start || from >= end;
      }));
      if (line) line.push(item);
      else lines.push([item]);
    });
  return lines;
}

function drawWires(grid, blocks, byId) {
  const bars = new Map();
  grid.querySelectorAll("[data-id]").forEach((node) => bars.set(node.dataset.id, node));
  const frame = grid.getBoundingClientRect();
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "rmwires");
  svg.setAttribute("width", String(grid.scrollWidth));
  svg.setAttribute("height", String(grid.scrollHeight));
  let drawn = 0;
  blocks.forEach((edge) => {
    const source = bars.get(edge.from);
    const target = bars.get(edge.to);
    if (!source || !target || !byId.has(edge.from) || !byId.has(edge.to)) return;
    const a = source.getBoundingClientRect();
    const b = target.getBoundingClientRect();
    const x1 = a.right - frame.left;
    const y1 = a.top - frame.top + a.height / 2;
    const x2 = b.left - frame.left;
    const y2 = b.top - frame.top + b.height / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${x1 + WIRE_BOW} ${y1}, ${x2 - WIRE_BOW} ${y2}, ${x2} ${y2}`);
    path.setAttribute("class", "rmwire");
    path.dataset.state = byId.get(edge.to).state;
    svg.appendChild(path);
    drawn += 1;
  });
  grid.appendChild(svg);
  return drawn;
}

function cell(className, text) {
  const node = document.createElement("div");
  node.className = className;
  node.textContent = text;
  return node;
}

