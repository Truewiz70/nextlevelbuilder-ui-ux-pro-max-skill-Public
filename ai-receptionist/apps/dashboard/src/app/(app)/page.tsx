import Link from "next/link";
import type { Metadata } from "next";
import { apiFetch, query } from "@/lib/api";
import { formatPercent, humanize } from "@/lib/format";
import type { AnalyticsSummary } from "@/lib/types";
import { EmptyState, PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Overview" };

const WINDOWS = [7, 30, 90];

function Breakdown({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <section>
      <h2 className="mb-3 text-sm font-medium text-zinc-500">{title}</h2>
      {entries.length === 0 ? (
        <p className="text-sm text-zinc-500">Nothing classified yet.</p>
      ) : (
        <ul className="divide-y divide-zinc-200">
          {entries.map(([key, n]) => (
            <li key={key} className="grid grid-cols-[10rem_1fr_3rem] items-center gap-3 py-2 text-sm">
              <span className="truncate">{humanize(key)}</span>
              <span className="h-1.5 rounded-full bg-zinc-200">
                <span
                  className="block h-full origin-left rounded-full bg-accent-600"
                  style={{ width: `${(n / max) * 100}%` }}
                />
              </span>
              <span className="text-right font-mono tabular-nums">{n}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const { days: daysParam } = await searchParams;
  const days = WINDOWS.includes(Number(daysParam)) ? Number(daysParam) : 30;
  const s = await apiFetch<AnalyticsSummary>(`/analytics/summary${query({ days })}`);
  const peak = Math.max(1, ...s.daily_call_volume.map((d) => d.count));

  return (
    <>
      <PageHeader
        title="Overview"
        description={`Last ${s.window_days} days of call activity.`}
        actions={
          <div className="flex gap-1 rounded-md border border-zinc-200 bg-white p-0.5 text-sm">
            {WINDOWS.map((w) => (
              <Link
                key={w}
                href={`/?days=${w}`}
                aria-current={w === days ? "true" : undefined}
                className={`rounded px-2.5 py-1 transition active:scale-95 ${
                  w === days ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
                }`}
              >
                {w}d
              </Link>
            ))}
          </div>
        }
      />

      {s.total_calls === 0 ? (
        <EmptyState
          title="No calls in this window"
          hint="Once your phone number is connected to the voice system, calls appear here within seconds of hanging up. See the voice-system runbook for setup."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-x-10 gap-y-8 lg:grid-cols-[2fr_1fr]">
            <section aria-label="Daily call volume">
              <h2 className="mb-3 text-sm font-medium text-zinc-500">Calls per day</h2>
              <div
                className="grid h-44 items-end gap-px border-b border-zinc-200"
                style={{ gridTemplateColumns: `repeat(${s.daily_call_volume.length}, minmax(0, 1fr))` }}
              >
                {s.daily_call_volume.map((d) => (
                  <div
                    key={d.date}
                    title={`${d.date}: ${d.count} call${d.count === 1 ? "" : "s"}`}
                    className="flex h-full items-end"
                  >
                    <div
                      className="w-full rounded-t-sm bg-accent-600/80 transition hover:bg-accent-700"
                      style={{ height: d.count === 0 ? "2px" : `${(d.count / peak) * 100}%` }}
                    />
                  </div>
                ))}
              </div>
              <div className="mt-1 flex justify-between font-mono text-xs text-zinc-500">
                <span>{s.daily_call_volume[0]?.date}</span>
                <span>{s.daily_call_volume.at(-1)?.date}</span>
              </div>
            </section>

            <dl className="divide-y divide-zinc-200 self-start border-y border-zinc-200">
              {[
                ["Total calls", String(s.total_calls)],
                ["Booking rate", formatPercent(s.booking_rate)],
                ["Escalation rate", formatPercent(s.escalation_rate)],
                ["Classified", `${s.classified_calls} of ${s.total_calls}`],
              ].map(([label, value]) => (
                <div key={label} className="flex items-baseline justify-between py-3">
                  <dt className="text-sm text-zinc-600">{label}</dt>
                  <dd className="font-mono text-lg font-medium tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="grid grid-cols-1 gap-x-10 gap-y-8 lg:grid-cols-2">
            <Breakdown title="Outcomes" data={s.calls_by_outcome} />
            <Breakdown title="Caller sentiment" data={s.calls_by_sentiment} />
          </div>
        </>
      )}
    </>
  );
}
