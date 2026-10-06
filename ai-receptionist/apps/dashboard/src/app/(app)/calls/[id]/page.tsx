import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "@phosphor-icons/react/dist/ssr";
import { ApiError, apiFetch } from "@/lib/api";
import { formatCents, formatDateTime, formatDuration, formatPhone } from "@/lib/format";
import type { CallDetail } from "@/lib/types";
import { Badge, EmptyState, PageHeader } from "@/components/ui";

export const metadata = { title: "Call" };

export default async function CallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let call: CallDetail;
  try {
    call = await apiFetch<CallDetail>(`/calls/${encodeURIComponent(id)}`);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }

  return (
    <>
      <Link
        href="/calls"
        className="-mb-2 inline-flex items-center gap-1 text-sm text-zinc-600 hover:text-zinc-900"
      >
        <ArrowLeft size={14} /> All calls
      </Link>
      <PageHeader
        title={formatPhone(call.caller_e164)}
        description={call.summary ?? "No summary was generated for this call."}
        actions={
          <div className="flex gap-2">
            <Badge value={call.outcome} />
            <Badge value={call.sentiment} />
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-x-10 gap-y-8 lg:grid-cols-[2fr_1fr]">
        <section aria-label="Transcript">
          <h2 className="mb-3 text-sm font-medium text-zinc-500">Transcript</h2>
          {call.transcript.length === 0 ? (
            <EmptyState
              title="No transcript"
              hint="The call ended before anything was said, or the transcript has not arrived from the voice system yet."
            />
          ) : (
            <ol className="flex flex-col gap-3">
              {call.transcript.map((turn, i) => {
                const caller = turn.role === "user" || turn.role === "caller";
                return (
                  <li key={i} className={`flex flex-col gap-1 ${caller ? "items-start" : "items-end"}`}>
                    <span className="text-xs text-zinc-500">{caller ? "Caller" : "Receptionist"}</span>
                    <p
                      className={`max-w-[65ch] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                        caller ? "bg-white ring-1 ring-zinc-200" : "bg-accent-50 text-accent-800"
                      }`}
                    >
                      {turn.text}
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </section>

        <dl className="divide-y divide-zinc-200 self-start border-y border-zinc-200 text-sm">
          {[
            ["Started", formatDateTime(call.started_at)],
            ["Length", formatDuration(call.started_at, call.ended_at)],
            ["Direction", call.direction],
            ["Voice cost", formatCents(call.vendor_cost_cents)],
            ["AI cost", formatCents(call.llm_cost_cents)],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between py-2.5">
              <dt className="text-zinc-600">{k}</dt>
              <dd className="font-mono">{v}</dd>
            </div>
          ))}
          {call.recording_url && (
            <div className="py-2.5">
              <a
                href={call.recording_url}
                target="_blank"
                rel="noreferrer"
                className="text-accent-700 underline-offset-2 hover:underline"
              >
                Open recording
              </a>
            </div>
          )}
        </dl>
      </div>
    </>
  );
}
