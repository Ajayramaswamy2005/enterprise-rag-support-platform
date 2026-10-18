import { BRAND_NAME, BrandMark } from "@/components/rag/brand-mark";

const FEATURES = [
  {
    detail: "BM25 keyword search and dense vectors, fused and re-ranked.",
    title: "Hybrid retrieval",
  },
  {
    detail: "Every answer links back to the passages it came from.",
    title: "Cited answers",
  },
  {
    detail: "Unclear or unsupported questions get a follow-up, not a guess.",
    title: "No made-up policies",
  },
];

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-dvh w-screen bg-sidebar">
      <div className="flex w-full flex-col bg-background p-8 md:p-16 xl:w-[600px] xl:shrink-0 xl:rounded-r-2xl xl:border-border/40 xl:border-r">
        <div className="flex items-center gap-2 font-medium text-[14px] text-foreground">
          <BrandMark size={26} />
          {BRAND_NAME}
        </div>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-10">
          <div className="flex flex-col gap-2">{children}</div>
        </div>
      </div>

      <div className="hidden flex-1 flex-col justify-center gap-10 px-16 xl:flex">
        <div className="flex max-w-lg flex-col gap-4">
          <span className="font-label flex items-center gap-2 text-muted-foreground">
            <span className="size-1.5 rounded-full bg-signal" />
            Support desk
          </span>
          <h2 className="font-display text-[48px] text-foreground leading-[1.02]">
            Answers grounded in <em className="text-signal">your</em>{" "}
            knowledge base.
          </h2>
        </div>
        <ul className="flex max-w-md flex-col gap-5">
          {FEATURES.map((f) => (
            <li className="flex flex-col gap-1" key={f.title}>
              <span className="font-medium text-[14px] text-foreground">
                {f.title}
              </span>
              <span className="text-[13.5px] text-muted-foreground leading-relaxed">
                {f.detail}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
