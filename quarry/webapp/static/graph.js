const SVG_NS = "http://www.w3.org/2000/svg";
const REPULSION = 2300;
const SPRING = 0.0030;
const KIN_SPRING = 0.0009;
const CENTER_PULL = 0.0002;
const CLUSTER_PULL = 0.020;
const LOOSE_PULL = 0.055;
const STAGE_PULL = 0.08;
const NODES_PER_VIEW = 8;
const STAGE_LEFT = 0.14;
const STAGE_RIGHT = 0.86;
const DAMPING = 0.94;
const JITTER = 0.11;
const MAX_SPEED = 2.2;
const LOOSE_Y = 0.50;
const CLUSTER_Y = 0.50;
const CLUSTER_SPREAD_Y = 0.28;
const COLUMN_STEP_Y = 0.09;
const COLUMN_SPREAD_Y = 0.40;
const DIM = "0.3";
const RADIUS_BASE = 7;
const RADIUS_STEP = 2.5;
const RADIUS_CAP = 6;
const PARTICLE_SPEED = 0.0042;
const EDGE_BOW = 0.22;
const MARGIN = 58;
const LABEL_ROOM = 14;
const SETTLE_STEPS = 420;
const HEAT_DECAY = 0.982;
const HEAT_FLOOR = 0.03;
const COLLIDE_PAD = 26;
const RESIZE_SLOP = 8;
const FRAME_MS = 16.7;
const MAX_TICK_MS = 120;

function makeGraph(svg, labelHost, onSelect, onClearSelect) {
  const bodies = new Map();
  const nodeEls = new Map();
  const edgeEls = new Map();
  const partEls = new Map();
  const labelEls = new Map();
  let model = { nodes: [], edges: [], focus: null };
  let size = { w: 900, h: 600 };
  let world = { w: 900, h: 600 };
  let lastStage = 0;
  let fitted = false;
  let dragging = null;
  let hovering = null;
  let running = false;
  let background = null;
  let watching = null;
  let heat = 1;
  let ticked = performance.now();
  let homes = new Map();
  let scene = null;
  const camera = makeViewport(svg, onClearSelect, () => paint());
  const { view, toScene } = camera;

  function reheat(amount) {
    heat = Math.max(heat, amount);
  }

  function ensureBackground() {
    if (background) return;
    background = document.createElementNS(SVG_NS, "rect");
    setAttr(background, "width", "100%");
    setAttr(background, "height", "100%");
    setAttr(background, "fill", "transparent");
    svg.appendChild(background);
    scene = document.createElementNS(SVG_NS, "g");
    svg.appendChild(scene);
    camera.attach(background);
  }

  function measure() {
    const box = svg.getBoundingClientRect();
    size = { w: Math.max(box.width, 220), h: Math.max(box.height, 180) };
  }

  function watchSize() {
    if (watching || typeof ResizeObserver !== "function") return;
    watching = new ResizeObserver(([entry]) => {
      const box = entry.contentRect;
      if (box.width < RESIZE_SLOP || box.height < RESIZE_SLOP) return;
      measure();
    });
    watching.observe(svg);
  }

  function seed(node, index, total) {
    return {
      x: columnX(node.stage || 0) * world.w,
      y: world.h * ((index + 0.5) / Math.max(1, total)),
      vx: 0,
      vy: 0,
      r: RADIUS_BASE,
    };
  }

  function assignHomes(nodes, edges) {
    const parent = new Map(nodes.map((node) => [node.id, node.id]));
    const find = (id) => {
      let root = id;
      while (parent.get(root) !== root) root = parent.get(root);
      let walk = id;
      while (parent.get(walk) !== root) {
        const next = parent.get(walk);
        parent.set(walk, root);
        walk = next;
      }
      return root;
    };
    edges.forEach((edge) => {
      const a = find(edge.from);
      const b = find(edge.to);
      if (a !== b) parent.set(a, b);
    });

    const grouped = new Map();
    nodes.forEach((node) => {
      const root = find(node.id);
      if (!grouped.has(root)) grouped.set(root, []);
      grouped.get(root).push(node.id);
    });

    const loose = [];
    const clusters = [];
    grouped.forEach((ids) => (ids.length === 1 ? loose.push(ids[0]) : clusters.push(ids)));
    clusters.sort((a, b) => b.length - a.length);

    const column = stageColumns(nodes);
    homes = new Map();
    loose.forEach((id, index) => {
      const y = LOOSE_Y + ((index + 0.5) / loose.length - 0.5) * 2 * CLUSTER_SPREAD_Y;
      homes.set(id, { x: column.get(id), y, tight: true });
    });
    const stageOf = new Map(nodes.map((node) => [node.id, node.stage || 0]));
    clusters.forEach((ids, index) => {
      const y = clusterY(index, clusters.length);
      const columns = new Map();
      ids.forEach((id) => {
        const stage = stageOf.get(id);
        if (!columns.has(stage)) columns.set(stage, []);
        columns.get(stage).push(id);
      });
      columns.forEach((members) => {
        const span = Math.min(2 * COLUMN_SPREAD_Y, (members.length - 1) * COLUMN_STEP_Y);
        members.forEach((id, place) => {
          const offset = ((place + 0.5) / members.length - 0.5) * span;
          homes.set(id, {
            x: column.get(id),
            y: y + offset,
            tight: members.length > 1,
          });
        });
      });
    });
  }

  function columnX(stage) {
    if (lastStage === 0) return 0.5;
    return STAGE_LEFT + stage * ((STAGE_RIGHT - STAGE_LEFT) / lastStage);
  }

  function stageColumns(nodes) {
    return new Map(nodes.map((node) => [node.id, columnX(node.stage || 0)]));
  }

  function clusterY(index, total) {
    if (total <= 1) return CLUSTER_Y;
    return CLUSTER_Y + ((index + 0.5) / total - 0.5) * 2 * CLUSTER_SPREAD_Y;
  }

  function sync(nodes) {
    const scale = Math.max(1, Math.sqrt(nodes.length / NODES_PER_VIEW));
    world = { w: size.w * scale, h: size.h * scale };
    lastStage = nodes.reduce((top, node) => Math.max(top, node.stage || 0), 0);
    const live = new Set();
    nodes.forEach((node, index) => {
      live.add(node.id);
      let body = bodies.get(node.id);
      if (!body) {
        body = seed(node, index, nodes.length);
        bodies.set(node.id, body);
      }
      body.r = RADIUS_BASE + Math.min(node.blocking || 0, RADIUS_CAP) * RADIUS_STEP;
      body.node = node;
    });
    [...bodies.keys()].forEach((id) => {
      if (!live.has(id)) bodies.delete(id);
    });
  }

  function step() {
    const list = [...bodies.values()];
    for (let i = 0; i < list.length; i += 1) {
      const a = list[i];
      for (let j = i + 1; j < list.length; j += 1) {
        const b = list[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let distance = Math.hypot(dx, dy);
        if (distance < 0.01) {
          dx = (Math.random() - 0.5) * 0.5;
          dy = (Math.random() - 0.5) * 0.5;
          distance = 0.5;
        }
        const push = REPULSION / (distance * distance);
        const ux = (dx / distance) * push;
        const uy = (dy / distance) * push;
        a.vx += ux;
        a.vy += uy;
        b.vx -= ux;
        b.vy -= uy;
      }
    }

    model.edges.forEach((edge) => {
      const a = bodies.get(edge.from);
      const b = bodies.get(edge.to);
      if (!a || !b) return;
      if ((a.node.stage || 0) === (b.node.stage || 0)) return;
      const dy = b.y - a.y;
      const soft = edge.kind === "parent-child";
      const uy = dy * Math.abs(dy) * (soft ? KIN_SPRING : SPRING);
      a.vy += uy;
      b.vy -= uy;
    });

    bodies.forEach((body) => {
      const home = homes.get(body.node.id);
      if (home) {
        const pull = home.tight ? LOOSE_PULL : CLUSTER_PULL;
        body.vx += (home.x * world.w - body.x) * STAGE_PULL;
        body.vy += (home.y * world.h - body.y) * pull;
      }
      body.vx += (world.w / 2 - body.x) * CENTER_PULL;
      body.vy += (world.h / 2 - body.y) * CENTER_PULL;
      body.vx += (Math.random() - 0.5) * JITTER * heat;
      body.vy += (Math.random() - 0.5) * JITTER * heat;
      body.vx *= DAMPING;
      body.vy *= DAMPING;
      const speed = Math.hypot(body.vx, body.vy);
      if (speed > MAX_SPEED) {
        body.vx = (body.vx / speed) * MAX_SPEED;
        body.vy = (body.vy / speed) * MAX_SPEED;
      }
      if (dragging && dragging.id === body.node.id) {
        body.x = dragging.x;
        body.y = dragging.y;
        body.vx = 0;
        body.vy = 0;
      } else if (body.pinned) {
        body.vx = 0;
        body.vy = 0;
      } else {
        body.x += body.vx;
        body.y += body.vy;
      }
      const inset = Math.min(MARGIN, world.h * 0.16, world.w * 0.12);
      const edgeX = body.r + inset;
      const edgeY = body.r + inset + LABEL_ROOM;
      body.x = Math.min(world.w - edgeX, Math.max(edgeX, body.x));
      body.y = Math.min(world.h - edgeY, Math.max(edgeY, body.y));
    });
    separate();
  }

  function separate() {
    const list = [...bodies.values()];
    for (let i = 0; i < list.length; i += 1) {
      for (let j = i + 1; j < list.length; j += 1) {
        const a = list[i];
        const b = list[j];
        const want = a.r + b.r + COLLIDE_PAD;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distance = Math.hypot(dx, dy);
        if (distance >= want) continue;
        if (distance < 0.01) {
          dx = Math.random() - 0.5;
          dy = Math.random() - 0.5;
          distance = 0.5;
        }
        const shift = (want - distance) / 2;
        const ux = (dx / distance) * shift;
        const uy = (dy / distance) * shift;
        if (!held(a)) {
          a.x -= ux;
          a.y -= uy;
        }
        if (!held(b)) {
          b.x += ux;
          b.y += uy;
        }
      }
    }
  }

  function held(body) {
    return body.pinned || (dragging && dragging.id === body.node.id);
  }

  function curve(a, b) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    return { cx: mx - dy * EDGE_BOW, cy: my + dx * EDGE_BOW };
  }

  function pointOn(a, c, b, t) {
    const inv = 1 - t;
    return {
      x: inv * inv * a.x + 2 * inv * t * c.cx + t * t * b.x,
      y: inv * inv * a.y + 2 * inv * t * c.cy + t * t * b.y,
    };
  }

  function neighbours() {
    const near = new Set();
    if (!model.focus) return near;
    near.add(model.focus);
    model.edges.forEach((edge) => {
      if (edge.from === model.focus) near.add(edge.to);
      if (edge.to === model.focus) near.add(edge.from);
    });
    return near;
  }

  function paint() {
    const near = neighbours();
    const dimming = Boolean(model.focus);
    const liveEdges = new Set();
    setAttr(scene, "transform", `translate(${view.x.toFixed(2)} ${view.y.toFixed(2)}) scale(${view.k.toFixed(4)})`);

    model.edges.forEach((edge) => {
      const a = bodies.get(edge.from);
      const b = bodies.get(edge.to);
      if (!a || !b) return;
      const key = `${edge.from}>${edge.to}`;
      liveEdges.add(key);
      let path = edgeEls.get(key);
      if (!path) {
        path = document.createElementNS(SVG_NS, "path");
        setAttr(path, "class", "gedge");
        setAttr(path, "fill", "none");
        scene.insertBefore(path, scene.firstChild);
        edgeEls.set(key, path);
      }
      const c = curve(a, b);
      setAttr(path, "d", `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} Q ${c.cx.toFixed(1)} ${c.cy.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`);
      const lit = dimming && (edge.from === model.focus || edge.to === model.focus);
      setAttr(path, "data-lit", lit ? "1" : "0");
      setAttr(path, "data-kind", edge.kind || "blocks");
      setAttr(path, "opacity", dimming && !lit ? DIM : "1");

      const blocks = (edge.kind || "blocks") === "blocks";
      const flowing = blocks && a.node
        && (a.node.state === "ready" || a.node.state === "claimed");
      let dot = partEls.get(key);
      if (flowing) {
        if (!dot) {
          dot = document.createElementNS(SVG_NS, "circle");
          setAttr(dot, "class", "gflow");
          setAttr(dot, "r", "2.4");
          scene.appendChild(dot);
          partEls.set(key, dot);
          dot.dataset.t = String(Math.random());
        }
        const t = (Number(dot.dataset.t) + PARTICLE_SPEED) % 1;
        dot.dataset.t = String(t);
        const at = pointOn(a, c, b, t);
        setAttr(dot, "cx", at.x.toFixed(1));
        setAttr(dot, "cy", at.y.toFixed(1));
        setAttr(dot, "data-state", a.node.state);
        setAttr(dot, "opacity", dimming && !lit ? DIM : String(0.4 + Math.sin(t * Math.PI) * 0.6));
      } else if (dot) {
        scene.removeChild(dot);
        partEls.delete(key);
      }
    });
    prune(edgeEls, liveEdges, (el) => scene.removeChild(el));
    prune(partEls, liveEdges, (el) => scene.removeChild(el));

    const liveNodes = new Set();
    bodies.forEach((body, id) => {
      liveNodes.add(id);
      const node = body.node;
      let group = nodeEls.get(id);
      if (!group) {
        group = document.createElementNS(SVG_NS, "g");
        setAttr(group, "class", "gnode");
        setAttr(group, "data-id", id);
        const halo = document.createElementNS(SVG_NS, "circle");
        setAttr(halo, "class", "halo");
        const ring = document.createElementNS(SVG_NS, "circle");
        setAttr(ring, "class", "ring");
        const hit = document.createElementNS(SVG_NS, "circle");
        setAttr(hit, "class", "hit");
        setAttr(hit, "fill", "transparent");
        const core = document.createElementNS(SVG_NS, "circle");
        setAttr(core, "class", "core");
        group.append(halo, ring, hit, core);
        wire(group, id);
        scene.appendChild(group);
        nodeEls.set(id, group);
      }
      const [halo, ring, hit, core] = group.children;
      const focused = id === model.focus;
      const hot = id === hovering;
      const grow = hot ? 1.28 : focused ? 1.12 : 1;
      setAttr(group, "data-state", node.state);
      setAttr(group, "opacity", dimming && !near.has(id) ? DIM : "1");
      circle(halo, body.x, body.y, body.r * grow + 11);
      setAttr(halo, "opacity", focused ? "0.5" : hot ? "0.28" : "0");
      circle(ring, body.x, body.y, body.r * grow + 5);
      setAttr(ring, "opacity", focused ? "0.75" : "0");
      circle(hit, body.x, body.y, body.r + 16);
      circle(core, body.x, body.y, body.r * grow);

      let label = labelEls.get(id);
      if (!label) {
        label = document.createElement("div");
        label.className = "nlabel";
        labelHost.appendChild(label);
        labelEls.set(id, label);
      }
      setText(label, node.id.split("-").pop());
      const lx = view.x + body.x * view.k;
      const ly = view.y + (body.y + body.r * grow + 9) * view.k;
      setStyle(label, "transform", `translate(calc(${lx.toFixed(1)}px - 50%), ${ly.toFixed(1)}px)`);
      setStyle(label, "opacity", dimming && !near.has(id) ? DIM : "1");
      setStyle(label, "color", focused || hot ? "var(--ink)" : "var(--ink-2)");
    });
    prune(nodeEls, liveNodes, (el) => scene.removeChild(el));
    prune(labelEls, liveNodes, (el) => labelHost.removeChild(el));
  }

  function wire(group, id) {
    group.addEventListener("click", (event) => {
      event.stopPropagation();
      if (group.dataset.dragged === "1") {
        group.dataset.dragged = "0";
        return;
      }
      onSelect(id);
    });
    group.addEventListener("pointerenter", () => {
      hovering = id;
    });
    group.addEventListener("pointerleave", () => {
      if (hovering === id) hovering = null;
    });
    group.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      const body = bodies.get(id);
      if (!body) return;
      body.pinned = false;
      setAttr(group, "data-pinned", "0");
      reheat(0.55);
    });
    group.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const at = toLocal(event);
      dragging = { id, x: at.x, y: at.y, moved: 0 };
      reheat(0.4);
      group.setPointerCapture(event.pointerId);
    });
    group.addEventListener("pointermove", (event) => {
      if (!dragging || dragging.id !== id) return;
      const at = toLocal(event);
      dragging.moved += Math.hypot(at.x - dragging.x, at.y - dragging.y);
      dragging.x = at.x;
      dragging.y = at.y;
      if (dragging.moved > 4) group.dataset.dragged = "1";
    });
    const release = (event) => {
      if (!dragging || dragging.id !== id) return;
      try {
        group.releasePointerCapture(event.pointerId);
      } catch (error) {
        void error;
      }
      const body = bodies.get(id);
      if (body && dragging.moved > 4) {
        body.pinned = true;
        setAttr(group, "data-pinned", "1");
      }
      dragging = null;
      reheat(0.35);
    };
    group.addEventListener("pointerup", release);
    group.addEventListener("pointercancel", release);
  }

  function toLocal(event) {
    const box = svg.getBoundingClientRect();
    return toScene(event.clientX - box.left, event.clientY - box.top);
  }

  function frame() {
    if (!running) return;
    const now = performance.now();
    const elapsed = Math.min(MAX_TICK_MS, now - ticked);
    ticked = now;
    if (!document.hidden) {
      if (heat > HEAT_FLOOR || dragging) step();
      if (!dragging) heat *= HEAT_DECAY ** (elapsed / FRAME_MS);
      paint();
    }
    requestAnimationFrame(frame);
  }

  function render(nodes, edges, focusId) {
    measure();
    watchSize();
    ensureBackground();
    const shown = nodes.filter((node) => node.state !== "closed");
    const visible = new Set(shown.map((node) => node.id));
    const fresh = shown.some((node) => !bodies.has(node.id));
    const changed = fresh || shown.length !== model.nodes.length || focusId !== model.focus;
    model = {
      nodes: shown,
      edges: edges.filter((edge) => visible.has(edge.from) && visible.has(edge.to)),
      focus: focusId,
    };
    sync(shown);
    assignHomes(shown, model.edges);
    if (fresh) settle();
    if (fresh && !fitted && shown.length) {
      fitted = true;
      camera.fit(bounds());
    }
    if (changed) reheat(fresh ? 1 : 0.3);
    paint();
    if (!running) {
      running = true;
      requestAnimationFrame(frame);
    }
    return { nodes: shown.length, edges: model.edges.length };
  }

  function release() {
    bodies.forEach((body, id) => {
      body.pinned = false;
      const group = nodeEls.get(id);
      if (group) setAttr(group, "data-pinned", "0");
      body.vx += (Math.random() - 0.5) * 2;
      body.vy += (Math.random() - 0.5) * 2;
    });
    reheat(1);
  }

  function settle() {
    for (let i = 0; i < SETTLE_STEPS; i += 1) step();
  }

  function bounds() {
    const list = [...bodies.values()];
    if (!list.length) return { x: 0, y: 0, w: size.w, h: size.h };
    const pad = RADIUS_BASE + RADIUS_CAP * RADIUS_STEP + LABEL_ROOM + MARGIN;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    list.forEach((body) => {
      minX = Math.min(minX, body.x);
      minY = Math.min(minY, body.y);
      maxX = Math.max(maxX, body.x);
      maxY = Math.max(maxY, body.y);
    });
    return { x: minX - pad, y: minY - pad, w: maxX - minX + 2 * pad, h: maxY - minY + 2 * pad };
  }

  return { render, release, resetView: () => camera.fit(bounds()) };
}

function setAttr(el, name, value) {
  if (el.getAttribute(name) !== value) el.setAttribute(name, value);
}

function setText(el, value) {
  const next = value == null ? "" : String(value);
  if (el.textContent !== next) el.textContent = next;
}

function setStyle(el, name, value) {
  if (el.style.getPropertyValue(name) !== value) el.style.setProperty(name, value);
}

function circle(el, x, y, r) {
  setAttr(el, "cx", x.toFixed(1));
  setAttr(el, "cy", y.toFixed(1));
  setAttr(el, "r", r.toFixed(1));
}

function prune(store, live, remove) {
  store.forEach((el, key) => {
    if (live.has(key)) return;
    remove(el);
    store.delete(key);
  });
}
