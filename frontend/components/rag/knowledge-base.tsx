"use client";

import { FileTextIcon, Trash2Icon, UploadIcon } from "lucide-react";
import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Textarea } from "@/components/ui/textarea";
import {
  type KnowledgeDocument,
  useBackendHealth,
  useKnowledge,
} from "@/hooks/use-knowledge";
import { cn } from "@/lib/utils";

const CATEGORIES = ["general", "support", "billing", "technical"] as const;
type Category = (typeof CATEGORIES)[number];

const MAX_FILE_BYTES = 1_000_000;
const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border/70 bg-card px-4 py-3 shadow-[var(--shadow-card)]">
      <span className="font-label text-muted-foreground">{label}</span>
      <span className="font-medium text-[22px] text-foreground tabular-nums">
        {value}
      </span>
    </div>
  );
}

function AddDocumentForm({ onAdded }: { onAdded: () => void }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState<Category>("general");
  const [submitting, setSubmitting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file) {
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        toast.error("Files are limited to 1 MB of text.");
        return;
      }
      const text = await file.text();
      setContent(text);
      if (!title.trim()) {
        setTitle(file.name.replace(/\.[^.]+$/, ""));
      }
    },
    [title]
  );

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      if (!title.trim() || !content.trim()) {
        toast.error("A title and some content are required.");
        return;
      }
      setSubmitting(true);
      try {
        const res = await fetch(`${base}/api/knowledge`, {
          body: JSON.stringify({
            category: category === "general" ? undefined : category,
            content,
            title,
          }),
          headers: { "Content-Type": "application/json" },
          method: "POST",
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(body.error ?? `Request failed (${res.status})`);
        }
        toast.success(
          `Indexed "${title.trim()}" into ${body.chunks_indexed} passage${body.chunks_indexed === 1 ? "" : "s"}.`
        );
        setTitle("");
        setContent("");
        setCategory("general");
        onAdded();
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : "Could not add document."
        );
      } finally {
        setSubmitting(false);
      }
    },
    [category, content, onAdded, title]
  );

  return (
    <form
      className="flex flex-col gap-4 rounded-md border border-border/70 bg-card p-4 shadow-[var(--shadow-card)]"
      onSubmit={handleSubmit}
    >
      <div className="flex flex-col gap-4 sm:flex-row">
        <div className="flex flex-1 flex-col gap-1.5">
          <Label htmlFor="kb-title">Title</Label>
          <Input
            id="kb-title"
            maxLength={512}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Refund policy"
            value={title}
          />
        </div>
        <div className="flex flex-col gap-1.5 sm:w-44">
          <Label htmlFor="kb-category">Category</Label>
          <Select
            onValueChange={(v) => setCategory(v as Category)}
            value={category}
          >
            <SelectTrigger className="w-full" id="kb-category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c[0].toUpperCase() + c.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="kb-content">Content</Label>
          <button
            className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground"
            onClick={() => fileRef.current?.click()}
            type="button"
          >
            <UploadIcon className="size-3" />
            Load from .txt / .md
          </button>
          <input
            accept=".txt,.md,.markdown,text/plain,text/markdown"
            className="hidden"
            onChange={handleFile}
            ref={fileRef}
            type="file"
          />
        </div>
        <Textarea
          className="min-h-48 text-[13px] leading-relaxed"
          id="kb-content"
          onChange={(e) => setContent(e.target.value)}
          placeholder="Paste the article, policy, or FAQ text here…"
          value={content}
        />
      </div>

      <div className="flex items-center justify-between gap-3">
        <span className="text-[12px] text-muted-foreground">
          Category helps retrieval filter billing, support, and technical
          questions.
        </span>
        <Button disabled={submitting} type="submit">
          {submitting ? "Indexing…" : "Add document"}
        </Button>
      </div>
    </form>
  );
}

function DocumentRow({
  doc,
  onDeleted,
}: {
  doc: KnowledgeDocument;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const category =
    typeof doc.metadata?.category === "string" ? doc.metadata.category : null;

  const handleDelete = useCallback(async () => {
    if (!window.confirm(`Delete "${doc.title}" from the knowledge base?`)) {
      return;
    }
    setDeleting(true);
    try {
      const res = await fetch(`${base}/api/knowledge/${doc.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error ?? `Request failed (${res.status})`);
      }
      toast.success(`Deleted "${doc.title}".`);
      onDeleted();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not delete document."
      );
      setDeleting(false);
    }
  }, [doc.id, doc.title, onDeleted]);

  return (
    <li className="flex flex-col gap-2 rounded-md border border-border/70 bg-card px-4 py-3 shadow-[var(--shadow-card)]">
      <div className="flex items-start gap-3">
        <FileTextIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        <button
          aria-expanded={expanded}
          className="min-w-0 flex-1 text-left"
          onClick={() => setExpanded((v) => !v)}
          type="button"
        >
          <span className="block truncate font-medium text-[13.5px] text-foreground">
            {doc.title}
          </span>
          <span className="font-label mt-0.5 flex flex-wrap gap-x-3 text-muted-foreground/80">
            {category && <span>{category}</span>}
            <span>{doc.content.length.toLocaleString()} chars</span>
            <span>added {formatDate(doc.created_at)}</span>
          </span>
        </button>
        <Button
          aria-label={`Delete ${doc.title}`}
          className="text-muted-foreground hover:text-destructive"
          disabled={deleting}
          onClick={handleDelete}
          size="icon-sm"
          variant="ghost"
        >
          <Trash2Icon className="size-4" />
        </Button>
      </div>
      <p
        className={cn(
          "pl-7 text-[12.5px] text-muted-foreground leading-relaxed",
          expanded ? "whitespace-pre-wrap" : "line-clamp-2"
        )}
      >
        {doc.content}
      </p>
    </li>
  );
}

export function KnowledgeBase() {
  const { data, error, isLoading, mutate } = useKnowledge();
  const { data: health } = useBackendHealth();
  const refresh = useCallback(() => {
    mutate();
  }, [mutate]);

  const items = data?.items ?? [];
  const stats = data?.stats;

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-sidebar">
      <header className="flex h-14 shrink-0 items-center gap-2 px-3">
        <SidebarTrigger className="md:hidden" />
      </header>
      <div className="flex-1 overflow-y-auto bg-background md:rounded-tl-xl md:border-t md:border-l md:border-border/70">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 md:px-6">
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-[36px] text-foreground leading-none">
              Knowledge base
            </h1>
            <p className="text-[14px] text-muted-foreground">
              Every chat answer is retrieved from these documents. Add policies,
              FAQs, and guides; they are chunked, embedded, and indexed for
              hybrid search.
            </p>
          </div>

          {health?.status === "unconfigured" && (
            <p className="rounded-md bg-signal-soft px-3 py-2 text-[13px] text-signal">
              The backend isn't connected. Set BACKEND_API_URL and
              BACKEND_API_KEY on the frontend service.
            </p>
          )}
          {health?.status === "offline" && (
            <p className="rounded-md bg-caution-soft px-3 py-2 text-[13px] text-caution">
              The knowledge backend is offline or waking up. Free-tier services
              can take up to a minute to wake, then press Retry.
            </p>
          )}

          <div className="grid grid-cols-3 gap-3">
            <Stat label="Documents" value={stats?.documents ?? "—"} />
            <Stat label="Passages" value={stats?.sparse_chunks ?? "—"} />
            <Stat label="Vectors" value={stats?.vectors ?? "—"} />
          </div>

          <AddDocumentForm onAdded={refresh} />

          <section className="flex flex-col gap-3">
            <h2 className="font-label text-muted-foreground">
              Documents{data ? ` · ${data.total}` : ""}
            </h2>
            {isLoading && (
              <p className="text-[13px] text-muted-foreground">Loading…</p>
            )}
            {error && (
              <div className="flex items-center gap-3 text-[13px] text-caution">
                {error.message}
                <Button onClick={refresh} size="sm" variant="outline">
                  Retry
                </Button>
              </div>
            )}
            {data && items.length === 0 && (
              <p className="text-[13px] text-muted-foreground">
                No documents yet. Add one above to start answering questions.
              </p>
            )}
            <ul className="flex flex-col gap-2">
              {items.map((doc) => (
                <DocumentRow doc={doc} key={doc.id} onDeleted={refresh} />
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
