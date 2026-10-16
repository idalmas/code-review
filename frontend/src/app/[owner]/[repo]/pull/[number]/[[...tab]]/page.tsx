import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ReviewApp } from "@/components/review/ReviewApp";

// Mirrors github.com/<owner>/<repo>/pull/<number>[/files|/commits|...] so swapping the
// host on any PR URL lands here. Every tab opens the same review view.
export default function PullRequestPage({
  params,
}: PageProps<"/[owner]/[repo]/pull/[number]/[[...tab]]">) {
  return (
    <Suspense fallback={<p className="p-6 text-muted">Loading…</p>}>
      <Review params={params} />
    </Suspense>
  );
}

async function Review({
  params,
}: {
  params: PageProps<"/[owner]/[repo]/pull/[number]/[[...tab]]">["params"];
}) {
  const { owner, repo, number } = await params;
  const prNumber = Number(number);
  if (!Number.isInteger(prNumber) || prNumber <= 0) notFound();
  return <ReviewApp owner={owner} repo={repo} number={prNumber} />;
}
