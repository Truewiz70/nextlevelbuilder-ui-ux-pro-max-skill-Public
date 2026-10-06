import Link from "next/link";
import type { Metadata } from "next";
import { apiFetch, query } from "@/lib/api";
import { formatPhone } from "@/lib/format";
import { readSession } from "@/lib/session";
import type { CallbackRequest, Page } from "@/lib/types";
import { Badge, EmptyState, PageHeader, Pagination, td, th } from "@/components/ui";
import { StatusButtons } from "./status-buttons";

export const metadata: Metadata = { title: "Callbacks" };

const LIMIT = 25;
const STATUSES = ["open", "contacted", "resolved"];

export default async function CallbacksPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; offset?: string }>;
}) {
  const sp = await searchParams;
  const offset = Math.max(0, Number(sp.offset) || 0);
  const status = STATUSES.includes(sp.status ?? "") ? sp.status : undefined;
  const [data, session] = await Promise.all([
    apiFetch<Page<CallbackRequest>>(`/callback-requests${query({ status, limit: LIMIT, offset })}`),
    readSession(),
  ]);
  const canEdit = session?.role !== "viewer";

  return (
    <>
      <PageHeader
        title="Callbacks"
        description="Callers the receptionist could not fully help and promised someone would ring back. Open requests are listed first."
      />
      <nav aria-label="Filter by status" className="flex gap-1.5 text-sm">
        {[undefined, ...STATUSES].map((s) => (
          <Link
            key={s ?? "all"}
            href={s ? `/callbacks?status=${s}` : "/callbacks"}
            aria-current={s === status ? "true" : undefined}
            className={`rounded-full border px-3 py-1 transition active:scale-95 ${
              s === status
                ? "border-zinc-900 bg-zinc-900 text-white"
                : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100"
            }`}
          >
            {s ?? "All"}
          </Link>
        ))}
      </nav>

      {data.items.length === 0 ? (
        <EmptyState
          title={status ? `No ${status} callbacks` : "Nobody is waiting on a callback"}
          hint="When a caller asks for a person or the receptionist hits something it should not answer, the request lands here."
        />
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[40rem]">
            <thead className="border-b border-zinc-200">
              <tr>
                <th className={th}>Caller</th>
                <th className={th}>Reason</th>
                <th className={th}>Best time</th>
                <th className={th}>Status</th>
                {canEdit && <th className={th}>
                  <span className="sr-only">Actions</span>
                </th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {data.items.map((r) => (
                <tr key={r.id}>
                  <td className={`${td} whitespace-nowrap font-mono`}>{formatPhone(r.caller_e164)}</td>
                  <td className={`${td} max-w-[40ch]`}>{r.reason}</td>
                  <td className={`${td} text-zinc-600`}>{r.preferred_window ?? "Any time"}</td>
                  <td className={td}>
                    <Badge value={r.status} />
                  </td>
                  {canEdit && (
                    <td className={`${td} text-right`}>
                      <StatusButtons id={r.id} status={r.status} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination basePath="/callbacks" params={{ status }} offset={offset} limit={LIMIT} total={data.total} />
    </>
  );
}
