import Link from "next/link";
import type { Metadata } from "next";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { CrmSync } from "@/lib/types";
import { Badge, EmptyState, PageHeader, td, th } from "@/components/ui";

export const metadata: Metadata = { title: "CRM sync" };

export default async function CrmPage() {
  const rows = await apiFetch<CrmSync[]>("/crm/failed-syncs?limit=100");

  return (
    <>
      <PageHeader
        title="CRM sync"
        description="Calls that did not reach your CRM. Failed syncs retry automatically; dead ones gave up and need a look."
      />
      {rows.length === 0 ? (
        <EmptyState
          title="Everything is synced"
          hint="Contacts, call notes and deals reach your CRM after each call. Anything that fails shows up here with the reason."
        />
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[40rem]">
            <thead className="border-b border-zinc-200">
              <tr>
                <th className={th}>Provider</th>
                <th className={th}>Status</th>
                <th className={th}>Attempts</th>
                <th className={th}>First failed</th>
                <th className={th}>Error</th>
                <th className={th}>Call</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className={td}>{r.provider}</td>
                  <td className={td}>
                    <Badge value={r.status} />
                  </td>
                  <td className={`${td} font-mono`}>{r.attempts}</td>
                  <td className={`${td} whitespace-nowrap text-zinc-600`}>{formatDateTime(r.created_at)}</td>
                  <td className={`${td} max-w-[36ch] break-words font-mono text-xs text-zinc-700`}>
                    {r.last_error ?? "--"}
                  </td>
                  <td className={td}>
                    {r.call_id ? (
                      <Link href={`/calls/${r.call_id}`} className="text-accent-700 hover:underline">
                        View
                      </Link>
                    ) : (
                      "--"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
