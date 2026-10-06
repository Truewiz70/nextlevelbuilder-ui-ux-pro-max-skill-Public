import type { Metadata } from "next";
import { apiFetch } from "@/lib/api";
import { readSession } from "@/lib/session";
import type { AgentConfig, Integration, Tenant } from "@/lib/types";
import { Badge, btn, Notice, PageHeader } from "@/components/ui";
import { AgentForm, TenantForm } from "./forms";

export const metadata: Metadata = { title: "Settings" };

const ERRORS: Record<string, string> = {
  oauth_denied: "Access was declined, so nothing was connected. Approve the request to connect.",
  oauth_callback_invalid: "The connection response looked wrong. Start the connection again.",
  forbidden: "Only admins can connect integrations.",
  integration_error:
    "This integration is not set up on the server yet. Ask your administrator to add its credentials.",
  connect_failed: "Could not start the connection. Try again in a minute.",
};

const PROVIDER_LABEL: Record<string, string> = {
  google_calendar: "Google Calendar",
  hubspot: "HubSpot",
};

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<{ connected?: string; error?: string }>;
}) {
  const sp = await searchParams;
  const [tenant, agent, integrations, session] = await Promise.all([
    apiFetch<Tenant>("/tenants/me"),
    apiFetch<AgentConfig>("/tenants/me/agent-config"),
    apiFetch<Integration[]>("/integrations"),
    readSession(),
  ]);
  const readOnly = session?.role === "viewer";

  return (
    <>
      <PageHeader title="Settings" description={`${tenant.name}, ${tenant.vertical} practice.`} />
      {sp.connected && (
        <Notice tone="good">{PROVIDER_LABEL[sp.connected] ?? sp.connected} is connected.</Notice>
      )}
      {sp.error && <Notice tone="bad">{ERRORS[sp.error] ?? "Something went wrong while connecting."}</Notice>}
      {readOnly && <Notice tone="good">You have view-only access. Ask an admin to change settings.</Notice>}

      <section className="flex flex-col gap-4">
        <h2 className="border-b border-zinc-200 pb-2 text-sm font-semibold">Integrations</h2>
        <ul className="divide-y divide-zinc-200">
          {integrations.map((i) => (
            <li key={i.provider} className="flex items-center justify-between gap-4 py-3">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">{PROVIDER_LABEL[i.provider] ?? i.provider}</span>
                <Badge value={i.status} />
              </div>
              {!readOnly && (
                <a
                  href={`/api/integrations/${i.provider}/connect`}
                  className={`${btn.base} ${i.connected ? btn.secondary : btn.primary}`}
                >
                  {i.connected ? "Reconnect" : "Connect"}
                </a>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="border-b border-zinc-200 pb-2 text-sm font-semibold">Business</h2>
        <TenantForm timezone={tenant.timezone} readOnly={readOnly} />
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="border-b border-zinc-200 pb-2 text-sm font-semibold">
          Receptionist <span className="font-mono text-xs font-normal text-zinc-500">v{agent.version}</span>
        </h2>
        <AgentForm agent={agent} readOnly={readOnly} />
      </section>
    </>
  );
}
