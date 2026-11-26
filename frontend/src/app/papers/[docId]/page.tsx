import { Suspense } from "react";

import { PaperWorkspace } from "@/components/papers/PaperWorkspace";

// The paper id is only known per request, so this part renders on demand, not at build time.
export default function PaperPage({ params }: PageProps<"/papers/[docId]">) {
  return (
    <Suspense fallback={<p className="p-4 text-sm text-muted">Loading paper…</p>}>
      <Workspace params={params} />
    </Suspense>
  );
}

async function Workspace({ params }: Pick<PageProps<"/papers/[docId]">, "params">) {
  const { docId } = await params;
  return <PaperWorkspace docId={docId} />;
}
