import { cn } from "@/lib/utils";

/** Strata mark: layered knowledge with the grounding layer in the signal colour. */
export function BrandMark({
  className,
  size = 28,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground",
        className
      )}
      style={{ height: size, width: size }}
    >
      <svg
        aria-hidden="true"
        fill="none"
        height={size * 0.56}
        viewBox="0 0 16 16"
        width={size * 0.56}
      >
        <rect fill="currentColor" height="2" opacity="0.45" rx="1" width="8" x="4" y="2.5" />
        <rect fill="currentColor" height="2" opacity="0.7" rx="1" width="11" x="2.5" y="7" />
        <rect fill="var(--signal)" height="2.5" rx="1.25" width="14" x="1" y="11.5" />
      </svg>
    </span>
  );
}

export const BRAND_NAME = "Groundwork";
