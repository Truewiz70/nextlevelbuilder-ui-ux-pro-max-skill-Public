import { redirect } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { readSession } from "@/lib/session";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await readSession();
  if (!session) redirect("/login");
  return (
    <div className="flex min-h-[100dvh] flex-col md:flex-row">
      <Sidebar tenantName={session.tenantName} userName={session.userName} />
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-6">{children}</div>
      </main>
    </div>
  );
}
