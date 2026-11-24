const HELP = {
  create:
    "Runs bd create. Files a new issue at this type and priority. With no blockers on "
    + "it, it lands straight in this queue as ready to claim.",
  claim:
    "Runs bd update --claim. Marks it in progress and assigns it to you, so a parallel "
    + "session does not start the same ticket. Do this before you begin, not after.",
  claimed:
    "Already claimed, so there is nothing to take. Its notes carry the state, which is "
    + "what lets /quarry:implement resume it instead of starting over.",
  close:
    "Runs bd close. Asks you for a reason first, then closes it and promotes whatever "
    + "it was blocking into this ready queue. Only close what is demonstrably done.",
  reopen:
    "Runs bd reopen. Returns a closed issue to open, so it comes back to this queue "
    + "once nothing blocks it again.",
  remove:
    "Runs bd delete. Removes the issue and its dependency edges permanently, with no "
    + "history kept. Closing preserves the record, so prefer that unless this issue "
    + "should never have existed.",
  priority:
    "Runs bd priority. Moves this issue between P0 critical and P4 backlog, which is how "
    + "the backlog gets reprioritized without leaving the board. Order of work still comes "
    + "from the dependency graph; priority breaks ties within what is already ready.",
  copy:
    "Copies the command above so you can paste it straight to the agent.",
  ask:
    "Searches every sealed context window at once and returns the preserved lines at "
    + "their addresses. It never hands back a whole unit.",
  release:
    "Unpins every node you have dragged and stirs the layout, so the graph drifts, "
    + "clusters and pushes apart on its own again. Nothing in the tracker changes.",
  resetview:
    "Returns the zoom to where it started. Scroll the wheel over the graph to zoom "
    + "in on whatever the pointer is over.",
};

const SHOW_DELAY_MS = 170;
const HIDE_DELAY_MS = 450;
const FADE_MS = 340;
const EDGE_GAP = 10;

function flushStyles(node) {
  return node.offsetWidth;
}

function mountTooltips() {
  const bubble = document.createElement("div");
  bubble.className = "tip";
  bubble.setAttribute("role", "tooltip");
  bubble.hidden = true;
  document.body.appendChild(bubble);

  let showTimer = 0;
  let hideTimer = 0;
  let clearTimer = 0;
  let anchor = null;

  function place(target) {
    const box = target.getBoundingClientRect();
    bubble.style.left = "0px";
    bubble.style.top = "0px";
    const own = bubble.getBoundingClientRect();
    let left = box.left + box.width / 2 - own.width / 2;
    left = Math.min(window.innerWidth - own.width - EDGE_GAP, Math.max(EDGE_GAP, left));
    let top = box.top - own.height - EDGE_GAP;
    if (top < EDGE_GAP) top = box.bottom + EDGE_GAP;
    bubble.style.left = `${Math.round(left)}px`;
    bubble.style.top = `${Math.round(top)}px`;
  }

  function show(target) {
    anchor = target;
    bubble.textContent = target.dataset.help;
    bubble.hidden = false;
    place(target);
    flushStyles(bubble);
    bubble.classList.add("on");
  }

  function open(target) {
    window.clearTimeout(hideTimer);
    window.clearTimeout(clearTimer);
    if (anchor === target && !bubble.hidden) return;
    window.clearTimeout(showTimer);
    showTimer = window.setTimeout(() => show(target), SHOW_DELAY_MS);
  }

  function close() {
    window.clearTimeout(showTimer);
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => {
      bubble.classList.remove("on");
      clearTimer = window.setTimeout(() => {
        bubble.hidden = true;
        anchor = null;
      }, FADE_MS);
    }, HIDE_DELAY_MS);
  }

  function helpTarget(node) {
    return node && node.closest ? node.closest("[data-help]") : null;
  }

  document.addEventListener("pointerover", (event) => {
    const target = helpTarget(event.target);
    if (target) open(target);
  });
  document.addEventListener("pointerout", (event) => {
    if (helpTarget(event.target) && !helpTarget(event.relatedTarget)) close();
  });
  document.addEventListener("focusin", (event) => {
    const target = helpTarget(event.target);
    if (target) open(target);
  });
  document.addEventListener("focusout", () => close());
  document.addEventListener("pointerdown", () => close());
  window.addEventListener("scroll", () => close(), true);
}
