"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";

export function LinkForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const resolved = await api.resolveLink(url);
      router.push(resolved.app_path);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Couldn't reach the server.",
      );
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="flex gap-2">
        <input
          autoFocus
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo/pull/123"
          aria-label="GitHub pull request link"
          className="flex-1 rounded-md border border-border bg-bg px-3 py-2 font-mono text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={pending || !url.trim()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {pending ? "Opening…" : "Review"}
        </button>
      </div>
      {error && <p className="text-sm text-del-fg">{error}</p>}
    </form>
  );
}
