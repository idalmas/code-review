// Click-to-comment inspector, active only when the page is opened with ?inspect=1 inside
// Orbiter's sandboxed iframe. Hover outlines the element; click sends its source chain to the
// parent window. Nothing here can reach Orbiter's cookies or API (opaque origin, no network).
export function startInspector() {
  const box = document.createElement("div");
  Object.assign(box.style, {
    position: "fixed", pointerEvents: "none", zIndex: "2147483647", display: "none",
    outline: "2px solid #0969da", background: "rgba(9,105,218,0.08)", borderRadius: "2px",
  });
  document.body.appendChild(box);

  const tagged = (el: EventTarget | null) =>
    el instanceof Element ? el.closest<HTMLElement>("[data-orbiter-src]") : null;

  document.addEventListener("mouseover", (e) => {
    const el = tagged(e.target);
    if (!el) return void (box.style.display = "none");
    const r = el.getBoundingClientRect();
    Object.assign(box.style, {
      display: "block", left: `${r.left}px`, top: `${r.top}px`,
      width: `${r.width}px`, height: `${r.height}px`,
    });
  });

  document.addEventListener(
    "click",
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      const chain: string[] = [];
      for (let el = tagged(e.target); el; el = tagged(el.parentElement)) {
        chain.push(el.dataset.orbiterSrc!);
      }
      const first = tagged(e.target);
      const text = (first?.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 60);
      parent.postMessage({ type: "orbiter:pick", chain, tag: first?.tagName.toLowerCase(), text }, "*");
    },
    true,
  );
}
