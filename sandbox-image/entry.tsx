// Fixed entry point. The LLM-written ./harness exports `states`; we render one per page load.
import React from "react";
import { createRoot } from "react-dom/client";
import { states } from "./harness";

type CR = { states: { name: string; viewport: unknown }[]; errors: string[]; done: boolean };
const cr: CR = ((window as unknown as { __CR: CR }).__CR = {
  states: states.map((s: { name: string; viewport?: unknown }) => ({ name: s.name, viewport: s.viewport ?? null })),
  errors: [],
  done: false,
});

class Boundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    cr.errors.push(String((error as Error)?.stack ?? error));
    cr.done = true;
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function Done() {
  React.useEffect(() => {
    cr.done = true;
  }, []);
  return null;
}

const params = new URLSearchParams(location.search);
const index = Number(params.get("state") ?? -1);
if (params.get("inspect") === "1") import("./inspector").then((m) => m.startInspector());
if (index >= 0 && states[index]) {
  createRoot(document.getElementById("cr-root")!).render(
    <Boundary>
      {states[index].render()}
      <Done />
    </Boundary>,
  );
} else {
  cr.done = true;
}
