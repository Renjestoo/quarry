const STATUS_MEANS = {
  open: "filed and live, waiting to be picked up",
  in_progress: "claimed by someone and being worked right now",
  blocked: "held by its own status, or by a real open dependency, whichever applies",
  deferred: "put off until a date, hidden from the ready queue until then",
  closed: "finished, its reason recorded",
};

const TYPE_ORDER = [
  "epic", "milestone", "story", "feature", "bug", "spike", "task", "chore", "decision",
];
const CLAIMED_COLUMN = "in_progress";
const QUIET_CLAIMS = 1;
const IN_FLIGHT_HELP =
  "How many issues are claimed right now. One is the single-agent default. More than one "
  + "is what a deliberate fleet looks like, and also what drift looks like when nobody "
  + "meant to start a fleet. Each card names the actor that claimed it, where one was "
  + "passed; a card with no name was claimed without --actor, and those are the claims "
  + "the board cannot tell apart. See the parallel-agents skill.";

function makeBoard(host, onSelect) {
  function draw(nodes, statuses, focus) {
    const columns = statuses && statuses.length ? statuses : [...new Set(nodes.map(byStatus))];
    const grouped = new Map(columns.map((name) => [name, []]));
    const strays = [];
    nodes.forEach((node) => {
      const bucket = grouped.get(byStatus(node));
      if (bucket) bucket.push(node);
      else strays.push(node);
    });
    if (strays.length) {
      grouped.set("unknown", strays);
      columns.push("unknown");
    }
    grouped.forEach((list) => list.sort(order));

    const held = heldScroll(host);
    host.innerHTML = "";
    columns.forEach((name) => host.appendChild(column(name, grouped.get(name) || [], focus)));
    restoreScroll(host, held);
    return { columns: columns.length, cards: nodes.length };
  }

  function column(name, list, focus) {
    const box = document.createElement("section");
    box.className = "kcol";
    box.dataset.status = name;
    const head = document.createElement("header");
    head.className = "khead";
    head.append(
      span("kname", name.replace(/_/g, " ")),
      span("kcount", String(list.length)),
    );
    head.dataset.help = `${name.replace(/_/g, " ")}: ${STATUS_MEANS[name] || "a status bd reported that this board does not describe yet"}`;
    if (name === CLAIMED_COLUMN && list.length > QUIET_CLAIMS) {
      head.appendChild(span("kwip", `${list.length} in flight`));
      head.dataset.help += ` ${IN_FLIGHT_HELP}`;
    }
    box.appendChild(head);
    const stack = document.createElement("div");
    stack.className = "kstack";
    if (!list.length) stack.appendChild(span("kempty", "nothing here"));
    list.forEach((node) => stack.appendChild(card(node, focus)));
    box.appendChild(stack);
    return box;
  }

  function card(node, focus) {
    const box = document.createElement("article");
    box.className = "kcard";
    box.dataset.id = node.id;
    box.dataset.type = node.type;
    box.dataset.pri = `P${node.priority}`;
    box.dataset.state = node.state;
    if (node.id === focus) box.dataset.selected = "1";
    box.tabIndex = 0;
    box.append(
      span("kid", node.id),
      span("kttl", node.title),
    );
    const tags = document.createElement("div");
    tags.className = "ktags";
    tags.append(span("ktag pri", `P${node.priority}`), span("ktag", node.type));
    if (node.blocked_by && node.blocked_by.length) {
      tags.appendChild(span("ktag warn", `blocked by ${node.blocked_by.length}`));
    }
    if (node.blocking) tags.appendChild(span("ktag", `blocks ${node.blocking}`));
    if (node.assignee) tags.appendChild(span("ktag own", node.assignee));
    if (node.holder) tags.appendChild(span("ktag own", `held by ${node.holder}`));
    box.appendChild(tags);
    const act = () => onSelect(node.id);
    box.addEventListener("click", act);
    box.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        act();
      }
    });
    return box;
  }

  return { draw };
}

function heldScroll(host) {
  const stacks = new Map();
  host.querySelectorAll(".kcol").forEach((column) => {
    const stack = column.querySelector(".kstack");
    if (stack) stacks.set(column.dataset.status, stack.scrollTop);
  });
  return { left: host.scrollLeft, stacks };
}

function restoreScroll(host, held) {
  host.scrollLeft = held.left;
  host.querySelectorAll(".kcol").forEach((column) => {
    const stack = column.querySelector(".kstack");
    const top = held.stacks.get(column.dataset.status);
    if (stack && top) stack.scrollTop = top;
  });
}

function byStatus(node) {
  if (node.state === "blocked" || node.state === "claimed_blocked") return "blocked";
  return node.status || "open";
}

function rank(type) {
  const at = TYPE_ORDER.indexOf(type);
  return at === -1 ? TYPE_ORDER.length : at;
}

function order(a, b) {
  const pri = (a.priority ?? 9) - (b.priority ?? 9);
  if (pri) return pri;
  const kind = rank(a.type) - rank(b.type);
  if (kind) return kind;
  return a.id.localeCompare(b.id);
}

function span(className, text) {
  const node = document.createElement("span");
  node.className = className;
  node.textContent = text;
  return node;
}
