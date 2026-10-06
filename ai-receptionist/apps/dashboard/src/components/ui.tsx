import Link from "next/link";
import { WarningCircle, Tray } from "@phosphor-icons/react/dist/ssr";
import type { ReactNode } from "react";

export const btn = {
  base: "inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition active:-translate-y-px active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50",
  primary: "bg-accent-700 text-white hover:bg-accent-800",
  secondary: "border border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-100",
  danger: "border border-red-200 bg-white text-red-700 hover:bg-red-50",
};

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex items-end justify-between gap-4 border-b border-zinc-200 pb-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-[65ch] text-sm text-zinc-600">{description}</p>}
      </div>
      {actions}
    </header>
  );
}

const BADGE_TONES: Record<string, string> = {
  good: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
  warn: "bg-amber-50 text-amber-800 ring-amber-600/20",
  bad: "bg-red-50 text-red-800 ring-red-600/20",
  neutral: "bg-zinc-100 text-zinc-700 ring-zinc-500/20",
};

const STATUS_TONE: Record<string, keyof typeof BADGE_TONES> = {
  appointment_booked: "good",
  confirmed: "good",
  synced: "good",
  connected: "good",
  resolved: "good",
  positive: "good",
  escalated: "warn",
  callback_requested: "warn",
  pending: "warn",
  failed: "warn",
  in_progress: "warn",
  open: "warn",
  negative: "bad",
  dead: "bad",
  cancelled: "bad",
  abandoned: "bad",
};

export function Badge({ value }: { value: string | null }) {
  if (!value) return <span className="text-zinc-400">--</span>;
  const tone = BADGE_TONES[STATUS_TONE[value] ?? "neutral"];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tone}`}
    >
      {value.replace(/_/g, " ")}
    </span>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2 py-16">
      <Tray size={28} weight="regular" className="text-zinc-400" />
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-[55ch] text-sm text-zinc-600">{hint}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800"
    >
      <WarningCircle size={20} weight="regular" className="mt-px shrink-0" />
      <div>
        <p className="font-medium">Could not load this page</p>
        <p className="mt-0.5 text-red-700">{message}</p>
      </div>
    </div>
  );
}

export function Notice({ tone, children }: { tone: "good" | "bad"; children: ReactNode }) {
  const cls =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
      : "border-red-200 bg-red-50 text-red-800";
  return (
    <p role={tone === "bad" ? "alert" : "status"} className={`rounded-md border px-3 py-2 text-sm ${cls}`}>
      {children}
    </p>
  );
}

export function Pagination({
  basePath,
  params,
  offset,
  limit,
  total,
}: {
  basePath: string;
  params: Record<string, string | undefined>;
  offset: number;
  limit: number;
  total: number;
}) {
  if (total <= limit) return null;
  const href = (nextOffset: number) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) q.set(k, v);
    if (nextOffset > 0) q.set("offset", String(nextOffset));
    const s = q.toString();
    return s ? `${basePath}?${s}` : basePath;
  };
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <nav className="flex items-center justify-between border-t border-zinc-200 pt-3 text-sm">
      <span className="font-mono text-zinc-600">
        {from}-{to} of {total}
      </span>
      <div className="flex gap-2">
        {offset > 0 && (
          <Link className={`${btn.base} ${btn.secondary}`} href={href(Math.max(0, offset - limit))}>
            Previous
          </Link>
        )}
        {offset + limit < total && (
          <Link className={`${btn.base} ${btn.secondary}`} href={href(offset + limit)}>
            Next
          </Link>
        )}
      </div>
    </nav>
  );
}

export function SkeletonRows({ rows = 8 }: { rows?: number }) {
  return (
    <div className="divide-y divide-zinc-200" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-6 py-3">
          <div className="skeleton h-4 w-28" />
          <div className="skeleton h-4 w-36" />
          <div className="skeleton h-4 flex-1" />
          <div className="skeleton h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

export const th = "py-2 pr-4 text-left text-xs font-medium uppercase tracking-wide text-zinc-500";
export const td = "py-3 pr-4 align-top text-sm";
