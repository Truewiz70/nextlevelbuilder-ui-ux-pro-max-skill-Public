import Link from "next/link";
import type { Metadata } from "next";
import { apiFetch, query } from "@/lib/api";
import { formatDateTime, formatDuration, formatPhone } from "@/lib/format";
import type { CallSummary, Page } from "@/lib/types";
import { Badge, EmptyState, PageHeader, Pagination, td, th } from "@/components/ui";

export const metadata: Metadata = { title: "Calls" };

const LIMIT = 25;
const OUTCOMES = [
  "appointment_booked",
  "lead_qualified",
  "callback_requested",
  "answered_faq",
  "voicemail",
  "abandoned",
  "other",
];

export default async function CallsPage({
  searchParams,
}: {
  searchParams: Promise<{ outcome?: string; offset?: string }>;
}) {
  const sp = await searchParams;
  const offset = Math.max(0, Number(sp.offset) || 0);
  const outcome = OUTCOMES.includes(sp.outcome ?? "") ? sp.outcome : undefined;
  const data = await apiFetch<Page<CallSummary>>(`/calls${query({ outcome, limit: LIMIT, offset })}`);

  return (
    <>
      <PageHeader title="Calls" description="Every inbound call, newest first." />
      <nav aria-label="Filter by outcome" className="flex flex-wrap gap-1.5 text-sm">
        {[undefined, ...OUTCOMES].map((o) => (
          <Link
            key={o ?? "all"}
            href={o ? `/calls?outcome=${o}` : "/calls"}
            aria-current={o === outcome ? "true" : undefined}
            className={`rounded-full border px-3 py-1 transition active:scale-95 ${
              o === outcome
                ? "border-zinc-900 bg-zinc-900 text-white"
                : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100"
            }`}
          >
            {o ? o.replace(/_/g, " ") : "All"}
          </Link>
        ))}
      </nav>

      {data.items.length === 0 ? (
        <EmptyState
          title={outcome ? "No calls with this outcome" : "No calls yet"}
          hint={
            outcome
              ? "Try a different filter, or clear it to see every call."
              : "Calls appear here after they end, with a transcript and a one-line summary."
          }
        />
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[40rem]">
            <thead className="border-b border-zinc-200">
              <tr>
                <th className={th}>Caller</th>
                <th className={th}>When</th>
                <th className={th}>Length</th>
                <th className={th}>Outcome</th>
                <th className={th}>Sentiment</th>
                <th className={th}>Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {data.items.map((c) => (
                <tr key={c.id} className="transition hover:bg-zinc-100/60">
                  <td className={`${td} whitespace-nowrap font-mono`}>
                    <Link href={`/calls/${c.id}`} className="text-accent-700 underline-offset-2 hover:underline">
                      {formatPhone(c.caller_e164)}
                    </Link>
                  </td>
                  <td className={`${td} whitespace-nowrap text-zinc-600`}>{formatDateTime(c.started_at)}</td>
                  <td className={`${td} font-mono text-zinc-600`}>
                    {formatDuration(c.started_at, c.ended_at)}
                  </td>
                  <td className={td}>
                    <Badge value={c.outcome} />
                  </td>
                  <td className={td}>
                    <Badge value={c.sentiment} />
                  </td>
                  <td className={`${td} max-w-[28ch] truncate text-zinc-600`} title={c.summary ?? ""}>
                    {c.summary ?? "--"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination
        basePath="/calls"
        params={{ outcome }}
        offset={offset}
        limit={LIMIT}
        total={data.total}
      />
    </>
  );
}
