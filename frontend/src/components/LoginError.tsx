"use client";

import { useEffect, useState } from "react";

/** Shows `?login_error=...` set by the OAuth callback, then cleans it from the URL. */
export function LoginError() {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const error = params.get("login_error");
    if (!error) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- read once from the URL after mount
    setMessage(error);
    params.delete("login_error");
    const rest = params.toString();
    history.replaceState(
      null,
      "",
      location.pathname + (rest ? `?${rest}` : "") + location.hash,
    );
  }, []);
  if (!message) return null;
  return (
    <p className="rounded-md border border-del-fg px-3 py-2 text-sm text-del-fg">
      {message}
    </p>
  );
}
