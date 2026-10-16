import { LinkForm } from "@/components/LinkForm";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-4 py-16">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Code Review</h1>
        <p className="text-muted">
          Paste a GitHub pull request link. Lockfiles and generated code get tucked away, and
          your progress through the diff is saved as you go.
        </p>
      </div>
      <LinkForm />
      <p className="text-sm text-muted">
        Tip: on any PR, replace <code className="font-mono">github.com</code> in the address bar
        with this site&apos;s host — the paths are the same.
      </p>
    </main>
  );
}
