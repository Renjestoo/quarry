const ZOOM_SENSITIVITY = 0.0016;
const ZOOM_MIN = 0.02;
const ZOOM_MAX = 4;
const TAP_SLOP = 4;

function makeViewport(svg, onTap, onChange) {
  const view = { k: 1, x: 0, y: 0 };
  let panning = null;

  function toScene(x, y) {
    return { x: (x - view.x) / view.k, y: (y - view.y) / view.k };
  }

  function fit(bounds) {
    const box = svg.getBoundingClientRect();
    const k = Math.min(
      ZOOM_MAX,
      Math.max(ZOOM_MIN, Math.min(box.width / bounds.w, box.height / bounds.h, 1)),
    );
    view.k = k;
    view.x = (box.width - bounds.w * k) / 2 - bounds.x * k;
    view.y = (box.height - bounds.h * k) / 2 - bounds.y * k;
    onChange();
  }

  function onWheel(event) {
    event.preventDefault();
    const box = svg.getBoundingClientRect();
    const px = event.clientX - box.left;
    const py = event.clientY - box.top;
    const factor = Math.exp(-event.deltaY * ZOOM_SENSITIVITY);
    const next = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, view.k * factor));
    const applied = next / view.k;
    view.x = px - (px - view.x) * applied;
    view.y = py - (py - view.y) * applied;
    view.k = next;
    onChange();
  }

  function onDown(event) {
    if (event.button !== 0) return;
    panning = { x: event.clientX, y: event.clientY, moved: 0 };
    svg.dataset.panning = "1";
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onMove(event) {
    if (!panning) return;
    const dx = event.clientX - panning.x;
    const dy = event.clientY - panning.y;
    panning.moved += Math.hypot(dx, dy);
    panning.x = event.clientX;
    panning.y = event.clientY;
    view.x += dx;
    view.y += dy;
    onChange();
  }

  function onUp(event) {
    if (!panning) return;
    const travelled = panning.moved;
    panning = null;
    delete svg.dataset.panning;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (travelled <= TAP_SLOP) onTap();
  }

  function attach(background) {
    svg.addEventListener("wheel", onWheel, { passive: false });
    background.addEventListener("pointerdown", onDown);
    background.addEventListener("pointermove", onMove);
    background.addEventListener("pointerup", onUp);
    background.addEventListener("pointercancel", onUp);
  }

  return { view, toScene, fit, attach };
}
