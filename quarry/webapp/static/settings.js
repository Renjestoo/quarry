const MODE_CONSEQUENCE = {
  interactive: "You are asked at every decision point. Nothing is decided on your behalf.",
  yolo: "The answer agent decides at question points, surfacing only NEEDS HUMAN. "
    + "Destructive, outward-facing and credential-bearing actions stay human gates in both modes.",
};

function makeSettings(host, profiles, onProfile, onToast) {
  let current = null;
  let profile = "";

  async function draw(activeProfile) {
    if (activeProfile) profile = activeProfile;
    host.innerHTML = "";
    let data;
    try {
      const answer = await fetch("/api/settings");
      if (!answer.ok) throw new Error(String(answer.status));
      data = await answer.json();
    } catch (error) {
      host.appendChild(note("settings unavailable", `GET /api/settings failed: ${error.message}`));
      return null;
    }
    current = data;
    host.appendChild(modeCard(data));
    host.appendChild(profileCard(profiles, profile));
    host.appendChild(connectionCard(data));
    return data;
  }

  function modeCard(data) {
    const card = document.createElement("section");
    card.className = "scard";
    card.append(
      heading("interaction mode", `read from and written to ${data.mode_file}`),
    );
    if (!data.configured) {
      card.appendChild(note(
        "this project is unconfigured",
        `${data.mode_file} has no usable 'Interaction mode:' line. Run /quarry:setup; `
        + "the dashboard will not create the file, because inventing one would hide that it is missing.",
      ));
      return card;
    }
    const row = document.createElement("div");
    row.className = "srow";
    data.modes.forEach((mode) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "smode";
      button.dataset.mode = mode;
      if (mode === data.mode) button.dataset.active = "1";
      button.append(tag("span","smodename", mode), tag("span","smodewhy", data.meaning[mode] || ""));
      button.addEventListener("click", () => flip(mode));
      row.appendChild(button);
    });
    card.appendChild(row);
    card.appendChild(tag("span","snote", MODE_CONSEQUENCE[data.mode] || ""));
    return card;
  }

  async function flip(mode) {
    if (!current || mode === current.mode) return;
    try {
      const answer = await fetch("/api/settings/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      const body = await answer.json();
      if (!answer.ok) throw new Error(body.error || String(answer.status));
      onToast(`mode is now ${body.mode}, and /quarry:mode reads the same file`);
      draw();
    } catch (error) {
      onToast(`mode unchanged: ${error.message}`);
    }
  }

  function profileCard(names, active) {
    const card = document.createElement("section");
    card.className = "scard";
    card.append(heading("colour profile", "kept in this browser, never sent to the server"));
    const row = document.createElement("div");
    row.className = "srow";
    names.forEach((name) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "sprofile";
      button.dataset.profile = name;
      if (name === active) button.dataset.active = "1";
      button.textContent = name;
      button.addEventListener("click", () => {
        onProfile(name);
        draw(name);
      });
      row.appendChild(button);
    });
    card.appendChild(row);
    return card;
  }

  function connectionCard(data) {
    const card = document.createElement("section");
    card.className = "scard";
    card.append(heading("connection", "server configuration, and how this board is running"));
    const list = document.createElement("dl");
    list.className = "sfacts";
    const health = data.health || {};
    const facts = [
      ["address", `${data.host}:${data.port}`],
      ["poll interval", `${data.poll_ms} ms`],
      ["project", data.project],
    ];
    if (Object.keys(health).length) {
      const served = health.served || 0;
      facts.push(
        ["uptime", spell(health.uptime_seconds || 0)],
        ["requests served", String(served)],
        ["failed", `${health.failed || 0}${served ? ` (${rate(health.failed, served)})` : ""}`],
        ["request time", served ? `${health.mean_ms} ms mean, ${health.slowest_ms} ms slowest`
                                : "nothing served yet"],
      );
    }
    facts.forEach(([term, value]) => {
      const key = document.createElement("dt");
      key.textContent = term;
      const val = document.createElement("dd");
      val.textContent = value;
      list.append(key, val);
    });
    card.appendChild(list);
    return card;
  }

  return { draw };
}

function rate(failed, served) {
  return `${((failed / served) * 100).toFixed(1)}% of requests`;
}

function heading(title, sub) {
  const box = document.createElement("header");
  box.className = "shead";
  box.append(tag("span","stitle", title), tag("span","ssub", sub));
  return box;
}

function note(title, body) {
  const box = document.createElement("section");
  box.className = "scard warn";
  box.append(tag("span","stitle", title), tag("span","snote", body));
  return box;
}

