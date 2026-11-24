async function loadGuide() {
  if (state.guide) {
    drawGuidePages();
    return;
  }
  try {
    const response = await fetch("/api/guide");
    if (!response.ok) throw new Error(`guide failed: ${response.status}`);
    state.guide = await response.json();
    drawGuidePages();
  } catch (error) {
    toast(String(error), true);
  }
}

function drawGuidePages() {
  if (state.page === "paths") drawPaths();
  if (state.page === "guide") drawGuide();
}

function drawPaths() {
  const lanes = state.guide.paths || [];
  syncList(el.lanes, lanes, (lane) => lane.id, () => {
    const host = document.createElement("section");
    host.className = "lane";
    return host;
  }, (host, lane) => {
    host.innerHTML = "";
    const head = document.createElement("div");
    head.className = "lanehead";
    head.append(tag("span", "lanekey", lane.id), tag("span", "lanename", lane.name),
                tag("span", "lanewhen", lane.when));
    host.appendChild(head);

    const chain = document.createElement("div");
    chain.className = "chain";
    lane.steps.forEach((step, index) => {
      if (index) chain.appendChild(tag("span", "arrow", "→"));
      const pill = document.createElement("div");
      pill.className = step.last ? "pill end" : "pill";
      pill.append(tag("div", "pcmd", step.cmd), tag("div", "psub", step.sub));
      chain.appendChild(pill);
    });
    host.appendChild(chain);

    if (lane.loop) host.appendChild(tag("div", "loopnote", `loops: ${lane.loop.label}`));

    (lane.branches || []).forEach((branch) => {
      const line = document.createElement("div");
      line.className = "branch";
      const pill = document.createElement("div");
      pill.className = branch.ends ? "pill end small" : "pill small";
      pill.append(tag("div", "pcmd", branch.cmd), tag("div", "psub", branch.sub));
      line.append(
        tag("span", "bwhen", branch.when),
        tag("span", "arrow", "→"),
        pill,
        tag("span", "bafter", `after ${branch.after}`),
      );
      host.appendChild(line);
    });
  });
}

function drawGuide() {
  const catalog = state.guide.catalog || { commands: [], groups: [] };
  const groups = [
    { name: "commands you type", kind: "command", items: catalog.commands },
    ...catalog.groups,
  ];
  syncList(el.guidebody, groups, (group) => group.name, () => {
    const host = document.createElement("section");
    host.className = "ggroup";
    return host;
  }, (host, group) => {
    host.innerHTML = "";
    host.appendChild(tag("div", "gname", group.name));
    group.items.forEach((item) => {
      const line = document.createElement("div");
      line.className = "grow";
      line.append(tag("span", `gnm ${group.kind}`, item.name), tag("span", "gds", item.detail));
      host.appendChild(line);
    });
  });
  showDrift();
}

function laneFor(node) {
  const lanes = (state.guide && state.guide.paths) || [];
  const pick = (id) => lanes.find((lane) => lane.id === id) || null;
  const title = (node.title || "").toLowerCase();
  if (node.type === "bug") return pick("C");
  if (node.type === "epic" && title.startsWith("workflow:")) return pick("E");
  if (node.type === "decision") return pick("D");
  return pick("A");
}

function hereIn(lane, node) {
  const find = (needle) => lane.steps.findIndex((step) => step.cmd.includes(needle));
  if (node.state === "closed") {
    const closing = find("bd close");
    return closing >= 0 ? closing : lane.steps.length - 1;
  }
  const building = find("implement");
  if (node.state === "ready" || node.state === "claimed") {
    return building >= 0 ? building : 0;
  }
  return building > 0 ? building - 1 : 0;
}

function drawFlow(node) {
  const strip = el.flowstrip;
  const lane = node && state.guide ? laneFor(node) : null;
  if (!lane) {
    strip.hidden = true;
    return;
  }
  const here = hereIn(lane, node);
  const heldChain = strip.querySelector(".chain");
  const heldLeft = heldChain ? heldChain.scrollLeft : 0;
  strip.hidden = false;
  strip.innerHTML = "";

  const head = document.createElement("div");
  head.className = "lanehead";
  head.append(
    tag("span", "lanekey", lane.id),
    tag("span", "lanename", lane.name),
    tag("span", "lanewhen", `${lane.when}, and this issue sits at step ${here + 1}`),
  );
  strip.appendChild(head);

  const chain = document.createElement("div");
  chain.className = "chain";
  lane.steps.forEach((step, index) => {
    if (index) chain.appendChild(tag("span", "arrow", "→"));
    const pill = document.createElement("div");
    const done = index < here;
    pill.className = `pill small${step.last ? " end" : ""}${index === here ? " here" : ""}${done ? " done" : ""}`;
    pill.append(tag("div", "pcmd", step.cmd), tag("div", "psub", step.sub));
    chain.appendChild(pill);
  });
  strip.appendChild(chain);
  chain.scrollLeft = heldLeft;

  const branches = (lane.branches || []).filter((branch) => branch.after === lane.steps[here].cmd);
  branches.forEach((branch) => {
    strip.appendChild(
      tag("div", "loopnote", `${branch.when}: take ${branch.cmd} (${branch.sub})`),
    );
  });
}

function showDrift() {
  const drift = state.guide.drift || {};
  const problems = Object.entries(drift).filter(([, items]) => items.length);
  el.drift.hidden = !problems.length;
  if (!problems.length) return;
  el.drift.innerHTML = "";
  el.drift.appendChild(tag("div", "gname", "catalog drift against the plugin on disk"));
  problems.forEach(([kind, items]) => {
    el.drift.appendChild(tag("div", "empty", `${kind.replace(/_/g, " ")}: ${items.join(", ")}`));
  });
}
