"use client";

import { useCallback, useEffect, useState } from "react";

import type { ReviewFile } from "./types";

// A file stays "viewed" only while its diff stats match what you saw, so new pushes
// that touch it un-view it automatically.
const fingerprint = (f: ReviewFile) => `${f.status}:${f.additions}:${f.deletions}`;

type Viewed = Record<string, string>;

export function useViewedFiles(storageKey: string) {
  const [viewed, setViewed] = useState<Viewed>({});

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from storage after mount
      setViewed(JSON.parse(localStorage.getItem(storageKey) ?? "{}"));
    } catch {
      setViewed({});
    }
  }, [storageKey]);

  const persist = useCallback(
    (next: Viewed) => {
      setViewed(next);
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // Storage can be unavailable (private mode); keep the in-memory state.
      }
    },
    [storageKey],
  );

  const isViewed = useCallback((f: ReviewFile) => viewed[f.path] === fingerprint(f), [viewed]);

  const setFileViewed = useCallback(
    (f: ReviewFile, value: boolean) => {
      const next = { ...viewed };
      if (value) next[f.path] = fingerprint(f);
      else delete next[f.path];
      persist(next);
    },
    [viewed, persist],
  );

  return { isViewed, setFileViewed };
}
