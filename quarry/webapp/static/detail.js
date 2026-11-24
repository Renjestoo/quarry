function drawDetail() {
  const node = (state.snapshot.nodes || []).find((entry) => entry.id === state.focus);
  drawFlow(node);
  if (!node) {
    el.detail.hidden = true;
    return;
  }
  el.detail.hidden = false;
  el.detail.innerHTML = "";
  el.detail.append(
    tag("div", "dkey", node.id),
    tag("div", "dttl", node.title),
    row("drow", [
      tag("span", "tag", node.state),
      tag("span", "tag", `P${node.priority}`),
      tag("span", "tag", node.type),
      tag("span", "tag", `blocks ${node.blocking}`),
    ]),
  );
  const move = commandFor(node);
  const cmd = document.createElement("div");
  cmd.className = "dcmd";
  cmd.append(tag("code", "dcmdtext", move.text), copyButton(move.text));
  el.detail.append(cmd, tag("div", "dwhy", move.why));

  if (node.state !== "closed") el.detail.appendChild(priorityPicker(node));

  const acts = document.createElement("div");
  acts.className = "dacts";
  if (node.state !== "closed") {
    if (node.state !== "claimed") {
      acts.appendChild(action("Claim", () => act(`/api/issues/${node.id}/claim`), "", HELP.claim));
    }
    acts.appendChild(action("Close", () => closeWithReason(node.id), "", HELP.close));
  } else {
    acts.appendChild(
      action("Reopen", () => act(`/api/issues/${node.id}/reopen`), "", HELP.reopen),
    );
  }
  acts.appendChild(action("Delete", () => removeIssue(node.id), "danger", HELP.remove));
  el.detail.appendChild(acts);
}

function priorityPicker(node) {
  const row = document.createElement("div");
  row.className = "dpri";
  row.append(tag("span", "dprilabel", "priority"));
  const pick = document.createElement("select");
  pick.className = "field pick";
  pick.dataset.help = HELP.priority;
  [0, 1, 2, 3, 4].forEach((level) => {
    const option = document.createElement("option");
    option.value = String(level);
    option.textContent = `P${level}`;
    option.selected = level === node.priority;
    pick.appendChild(option);
  });
  pick.addEventListener("change", () => {
    act(`/api/issues/${node.id}/priority`, { priority: Number(pick.value) });
  });
  row.appendChild(pick);
  return row;
}

function commandFor(node) {
  if (node.state === "ready") {
    return { text: `/quarry:implement ${node.id}`, why: "nothing blocks it, this starts the work" };
  }
  if (node.state === "claimed") {
    return { text: `/quarry:implement ${node.id}`, why: "already claimed, this resumes it from its notes" };
  }
  if (node.state === "deferred") {
    return { text: `bd undefer ${node.id}`, why: "deferred, so bd hides it from the ready queue until this restores it" };
  }
  if (node.state === "blocked") {
    const open = node.blocked_by || [];
    if (open.length === 1) {
      return { text: `/quarry:implement ${open[0]}`, why: `blocked, so this clears its one blocker ${open[0]}` };
    }
    return { text: `/quarry:show ${node.id}`, why: `${open.length} blockers open, read it before choosing one` };
  }
  return { text: `/quarry:show ${node.id}`, why: "closed, this shows the reason it was closed with" };
}

function copyButton(text) {
  const button = action("Copy", async () => {
    const ok = await toClipboard(text);
    if (!ok) selectCommandText();
    button.textContent = ok ? "Copied" : "Selected, ctrl-c";
    setTimeout(() => {
      button.textContent = "Copy";
    }, 1800);
  });
  button.classList.add("copy");
  button.dataset.help = HELP.copy;
  return button;
}

async function toClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    const carrier = document.createElement("textarea");
    carrier.value = text;
    carrier.setAttribute("readonly", "");
    carrier.style.position = "fixed";
    carrier.style.opacity = "0";
    document.body.appendChild(carrier);
    carrier.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (failure) {
      copied = false;
    }
    carrier.remove();
    return copied;
  }
}

function selectCommandText() {
  const target = el.detail.querySelector(".dcmdtext");
  if (!target) return;
  const range = document.createRange();
  range.selectNodeContents(target);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}
