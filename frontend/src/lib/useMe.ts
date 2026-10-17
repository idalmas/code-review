"use client";

import { useEffect, useState } from "react";

import { api } from "./api";
import type { Me } from "./types";

/** Current viewer; `undefined` while loading. */
export function useMe(): Me | undefined {
  const [me, setMe] = useState<Me>();
  useEffect(() => {
    api.me().then(setMe, () => setMe({ login_enabled: false, user: null }));
  }, []);
  return me;
}
