"use client";

import { useCallback, useEffect, useState } from "react";

import type { Tier } from "./types";

const KEY = "llm-tier";
const TIERS: Tier[] = ["cheap", "balanced", "best"];

/** The AI tier this reviewer last picked, remembered in their browser. */
export function useTier(fallback: Tier = "cheap") {
  const [tier, setTierState] = useState<Tier>(fallback);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY) as Tier | null;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from storage after mount
      if (saved && TIERS.includes(saved)) setTierState(saved);
    } catch {
      // Storage unavailable: keep the default.
    }
  }, []);

  const setTier = useCallback((next: Tier) => {
    setTierState(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // Ignore: the choice still applies for this page view.
    }
  }, []);

  return [tier, setTier] as const;
}
