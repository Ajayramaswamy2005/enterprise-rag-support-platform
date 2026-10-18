import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  BackendError,
  backendFetch,
  readBackendError,
} from "@/lib/rag/backend";

const createDocumentSchema = z.object({
  category: z.enum(["support", "billing", "technical", "general"]).optional(),
  content: z.string().trim().min(1).max(200_000),
  title: z.string().trim().min(1).max(512),
});

function errorResponse(error: unknown) {
  if (error instanceof BackendError) {
    return Response.json({ error: error.message }, { status: error.status });
  }
  return Response.json({ error: "Unexpected error" }, { status: 500 });
}

async function requireUser() {
  const session = await auth();
  return session?.user && session.user.type !== "guest" ? session.user : null;
}

export async function GET(request: Request) {
  if (!(await requireUser())) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const limit = Math.min(Number(searchParams.get("limit") ?? 100) || 100, 200);

  try {
    const [docsRes, statsRes] = await Promise.all([
      backendFetch(`/knowledge/documents?limit=${limit}`),
      backendFetch("/knowledge/stats"),
    ]);
    if (!docsRes.ok) {
      throw new BackendError(await readBackendError(docsRes), docsRes.status);
    }
    const docs = await docsRes.json();
    const stats = statsRes.ok ? await statsRes.json() : null;
    return Response.json({ ...docs, stats });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request: Request) {
  if (!(await requireUser())) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const parsed = createDocumentSchema.safeParse(
    await request.json().catch(() => null)
  );
  if (!parsed.success) {
    return Response.json(
      { error: "A title and some content are required." },
      { status: 400 }
    );
  }

  const { title, content, category } = parsed.data;

  try {
    // Embedding + indexing a long document can take a while on a CPU backend
    const res = await backendFetch("/knowledge/documents", {
      body: JSON.stringify({
        content,
        metadata: category ? { category } : {},
        title,
      }),
      method: "POST",
      timeoutMs: 120_000,
    });
    if (!res.ok) {
      throw new BackendError(await readBackendError(res), res.status);
    }
    return Response.json(await res.json(), { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}
