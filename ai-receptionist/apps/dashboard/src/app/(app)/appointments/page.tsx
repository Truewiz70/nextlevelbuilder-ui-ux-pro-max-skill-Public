import Link from "next/link";
import type { Metadata } from "next";
import { apiFetch, query } from "@/lib/api";
import { formatDateTime, formatPhone } from "@/lib/format";
import { readSession } from "@/lib/session";
import type { Appointment, Page } from "@/lib/types";
import { Badge, EmptyState, PageHeader, Pagination, td, th } from "@/components/ui";
import { CancelButton } from "./cancel-button";

export const metadata: Metadata = { title: "Appointments" };

const LIMIT = 25;
const STATUSES = ["confirmed", "cancelled"];

export default async function AppointmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; offset?: string }>;
}) {
  const sp = await searchParams;
  const offset = Math.max(0, Number(sp.offset) || 0);
  const status = STATUSES.includes(sp.status ?? "") ? sp.status : undefined;
  const [data, session] = await Promise.all([
    apiFetch<Page<Appointment>>(`/appointments${query({ status, limit: LIMIT, offset })}`),
    readSession(),
  ]);
  const canCancel = session?.role !== "viewer";

  return (
    <>
      <PageHeader title="Appointments" description="Bookings the receptionist made on calls." />
      <nav aria-label="Filter by status" className="flex gap-1.5 text-sm">
        {[undefined, ...STATUSES].map((s) => (
          <Link
            key={s ?? "all"}
            href={s ? `/appointments?status=${s}` : "/appointments"}
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
          title="No appointments"
          hint="When a caller books through the receptionist, the appointment shows up here and on the connected calendar."
        />
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[40rem]">
            <thead className="border-b border-zinc-200">
              <tr>
                <th className={th}>Customer</th>
                <th className={th}>Service</th>
                <th className={th}>Starts</th>
                <th className={th}>Status</th>
                {canCancel && <th className={th}>
                  <span className="sr-only">Actions</span>
                </th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {data.items.map((a) => (
                <tr key={a.id}>
                  <td className={td}>
                    <p className="font-medium">{a.customer_name}</p>
                    <p className="font-mono text-xs text-zinc-500">{formatPhone(a.customer_phone)}</p>
                  </td>
                  <td className={td}>{a.service}</td>
                  <td className={`${td} whitespace-nowrap`}>
                    <span className="font-mono">{formatDateTime(a.starts_at, a.timezone)}</span>
                    <span className="ml-1 text-xs text-zinc-500">{a.timezone.split("/").pop()?.replace(/_/g, " ")}</span>
                  </td>
                  <td className={td}>
                    <Badge value={a.status} />
                  </td>
                  {canCancel && (
                    <td className={`${td} text-right`}>
                      {a.status === "confirmed" && <CancelButton id={a.id} name={a.customer_name} />}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination basePath="/appointments" params={{ status }} offset={offset} limit={LIMIT} total={data.total} />
    </>
  );
}
