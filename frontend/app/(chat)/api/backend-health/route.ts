import { auth } from "@/app/(auth)/auth";
import { backendFetch, getBackendUrl } from "@/lib/rag/backend";

export type BackendHealth = {
  status: "healthy" | "degraded" | "offline" | "unconfigured";
  components: Record<string, string>;
  version?: string;
};

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!getBackendUrl()) {
    return Response.json({
      components: {},
      status: "unconfigured",
    } satisfies BackendHealth);
  }

  try {
    const res = await backendFetch("/health", { timeoutMs: 8000 });
    if (!res.ok) {
      return Response.json({
        components: {},
        status: "offline",
      } satisfies BackendHealth);
    }
    const body = await res.json();
    return Response.json({
      components: body.components ?? {},
      status: body.status === "healthy" ? "healthy" : "degraded",
      version: body.version,
    } satisfies BackendHealth);
  } catch {
    return Response.json({
      components: {},
      status: "offline",
    } satisfies BackendHealth);
  }
}
