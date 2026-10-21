import { auth } from "@/app/(auth)/auth";
import {
  BackendError,
  backendFetch,
  readBackendError,
} from "@/lib/rag/backend";

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user || session.user.type === "guest") {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const force = new URL(request.url).searchParams.get("force") === "true";

  try {
    // Embedding every document can take a while on a CPU backend
    const res = await backendFetch(`/knowledge/reindex?force=${force}`, {
      method: "POST",
      timeoutMs: 180_000,
    });
    if (!res.ok) {
      throw new BackendError(await readBackendError(res), res.status);
    }
    return Response.json(await res.json());
  } catch (error) {
    if (error instanceof BackendError) {
      return Response.json({ error: error.message }, { status: error.status });
    }
    return Response.json({ error: "Unexpected error" }, { status: 500 });
  }
}
