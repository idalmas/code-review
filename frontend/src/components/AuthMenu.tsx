"use client";

import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";

import { SignInButton } from "./SignInButton";

export function AuthMenu() {
  const me = useMe();
  if (!me) return <span className="h-8" />;
  if (!me.user) return me.login_enabled ? <SignInButton /> : null;

  return (
    <div className="flex items-center gap-3 text-sm">
      {me.user.avatar_url && (
        // eslint-disable-next-line @next/next/no-img-element -- tiny avatar from GitHub's CDN
        <img
          src={me.user.avatar_url}
          alt=""
          width={24}
          height={24}
          className="rounded-full"
        />
      )}
      <span>{me.user.login}</span>
      <button
        onClick={async () => {
          await api.logout();
          window.location.reload();
        }}
        className="text-muted hover:text-fg"
      >
        Sign out
      </button>
    </div>
  );
}
