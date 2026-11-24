const SLOT_STATES = {
  available: "the slot exists and nobody holds it",
  held: "one agent is resolving conflicts; the others wait",
  absent: "no slot bead in this project, so nothing serialises conflict resolution",
};

function makeFleet(host) {
  function draw(data) {
    host.innerHTML = "";
    if (!data) {
      host.appendChild(tag("p", "empty", "asking bd for the coordination state ..."));
      return { sections: 0 };
    }
    host.append(slotCard(data.slot), gatesCard(data.gates), swarmCard(data.swarms));
    return { sections: 3 };
  }

  return { draw };
}

function card(title, sub) {
  const box = document.createElement("section");
  box.className = "scard";
  const head = document.createElement("header");
  head.className = "shead";
  head.append(tag("span","stitle", title), tag("span","ssub", sub));
  box.appendChild(head);
  return box;
}

function failed(section) {
  return section && typeof section === "object" && typeof section.unavailable === "string";
}

function slotCard(slot) {
  const box = card("merge slot", "bd merge-slot check");
  if (failed(slot)) {
    box.appendChild(tag("span","snote", `could not be read: ${slot.unavailable}`));
    return box;
  }
  const missing = Boolean(slot && slot.error);
  const state = missing ? "absent" : slot && slot.available ? "available" : "held";
  const badge = tag("span","fstate", state);
  badge.dataset.state = state;
  box.appendChild(badge);
  box.appendChild(tag("span","snote", SLOT_STATES[state]));
  const facts = [["bead", (slot && slot.id) || "unknown"]];
  if (slot && slot.holder) facts.push(["held by", String(slot.holder)]);
  if (slot && slot.waiters && slot.waiters.length) {
    facts.push(["waiting", String(slot.waiters.length)]);
  }
  box.appendChild(factList(facts));
  if (missing) {
    box.appendChild(tag("span","snote", "Create one with: bd merge-slot create"));
  }
  return box;
}

function gatesCard(gates) {
  const box = card("gates", "bd gate list");
  if (failed(gates)) {
    box.appendChild(tag("span","snote", `could not be read: ${gates.unavailable}`));
    return box;
  }
  const open = (gates && gates.open) || [];
  if (!open.length) {
    box.appendChild(tag("span","snote", "nothing is waiting on a gate"));
    return box;
  }
  const list = document.createElement("div");
  list.className = "frows";
  open.forEach((gate) => {
    const row = document.createElement("div");
    row.className = "frow";
    row.append(
      tag("span","fid", String(gate.id || gate.issue_id || "?")),
      tag("span","ftx", String(gate.title || gate.await_id || "")),
      tag("span","ftag", String(gate.gate_type || gate.type || "gate")),
    );
    list.appendChild(row);
  });
  box.appendChild(list);
  return box;
}

function swarmCard(swarms) {
  const box = card("swarms", "bd swarm list");
  if (failed(swarms)) {
    box.appendChild(tag("span","snote", `could not be read: ${swarms.unavailable}`));
    return box;
  }
  const active = (swarms && swarms.active) || [];
  if (!active.length) {
    box.appendChild(tag("span","snote",
      "no swarm molecules; work is being taken one ticket at a time"));
    return box;
  }
  active.forEach((swarm) => box.appendChild(swarmRow(swarm)));
  return box;
}

function swarmRow(swarm) {
  const block = document.createElement("div");
  block.className = "fswarm";
  const head = document.createElement("div");
  head.className = "frow";
  head.append(
    tag("span","fid", String(swarm.id || "?")),
    tag("span","ftx", String(swarm.title || swarm.epic_id || "")),
    tag("span","ftag", String(swarm.status || "")),
  );
  block.appendChild(head);

  const done = Number(swarm.completed_issues || 0);
  const total = Number(swarm.total_issues || 0);
  const percent = Math.round(Number(swarm.progress_percent || 0));
  block.appendChild(meter(percent));
  block.appendChild(tag("span","fmeta", `${percent}% complete, ${done} of ${total} closed`));

  const progress = swarm.progress;
  if (failed(progress)) {
    block.appendChild(tag("span","fmeta", `breakdown unavailable: ${progress.unavailable}`));
    return block;
  }
  if (progress && typeof progress === "object") {
    const parts = [
      ["ready", (progress.ready || []).length],
      ["active", (progress.active || []).length],
      ["blocked", (progress.blocked || []).length],
      ["done", (progress.completed || []).length],
    ];
    block.appendChild(tag("span","fmeta",
      parts.map(([name, count]) => `${count} ${name}`).join(", ")));
    (progress.active || []).forEach((issue) => {
      block.appendChild(issueRow(issue, issue.assignee
        ? String(issue.assignee)
        : "claimed, no actor recorded"));
    });
    (progress.blocked || []).forEach((issue) => {
      block.appendChild(issueRow(issue, `blocked by ${(issue.blocked_by || []).length}`));
    });
  }
  return block;
}

function issueRow(issue, tag) {
  const row = document.createElement("div");
  row.className = "frow";
  row.append(
    tag("span","fid", String(issue.id || "?")),
    tag("span","ftx", String(issue.title || "")),
    tag("span","ftag", tag),
  );
  return row;
}

function meter(percent) {
  const track = document.createElement("div");
  track.className = "fmeter";
  const fill = document.createElement("div");
  fill.className = "fmeterfill";
  fill.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  track.appendChild(fill);
  return track;
}

function factList(facts) {
  const list = document.createElement("dl");
  list.className = "sfacts";
  facts.forEach(([term, value]) => {
    const key = document.createElement("dt");
    key.textContent = term;
    const val = document.createElement("dd");
    val.textContent = value;
    list.append(key, val);
  });
  return list;
}
