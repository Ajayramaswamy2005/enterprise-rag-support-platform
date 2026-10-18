import { auth } from "@/app/(auth)/auth";
import {
  BackendError,
  backendFetch,
  readBackendError,
} from "@/lib/rag/backend";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function handle(
  id: string,
  init: RequestInit
): Promise<Response> {
  const session = await auth();
  if (!session?.user || session.user.type === "guest") {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (!UUID_PATTERN.test(id)) {
    return Response.json({ error: "Invalid document id" }, { status: 400 });
  }

  try {
    const res = await backendFetch(`/knowledge/documents/${id}`, init);
    if (!res.ok) {
      throw new BackendError(await readBackendError(res), res.status);
    }
    return res.status === 204
      ? new Response(null, { status: 204 })
      : Response.json(await res.json());
  } catch (error) {
    if (error instanceof BackendError) {
      return Response.json({ error: error.message }, { status: error.status });
    }
    return Response.json({ error: "Unexpected error" }, { status: 500 });
  }
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return handle(id, { method: "GET" });
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return handle(id, { method: "DELETE" });
}
