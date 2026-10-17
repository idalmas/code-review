"use client";

import { useEffect, useState } from "react";

/**
 * Tracks a background job (render, stress test): resumes one started earlier for this file
 * and polls every 2s while its status is in `running`.
 */
export function useJob<J extends { id: string; status: string }>(
  get: (id: string) => Promise<J>,
  running: readonly string[],
  earlierId: string | undefined,
) {
  const [job, setJob] = useState<J | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const id = job?.id ?? earlierId;
    if (!id || (job && !running.includes(job.status))) return;
    let cancelled = false;
    const timer = setTimeout(
      () =>
        get(id).then(
          (j) => !cancelled && setJob(j),
          (err) => !cancelled && setError(err),
        ),
      job ? 2000 : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [job, earlierId, get, running]);

  const isRunning = !!job && running.includes(job.status);
  return { job, setJob, error, setError, isRunning };
}
