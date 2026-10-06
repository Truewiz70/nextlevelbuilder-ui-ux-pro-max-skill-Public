"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChartBar,
  PhoneCall,
  CalendarCheck,
  PhoneIncoming,
  ArrowsClockwise,
  GearSix,
  SignOut,
} from "@phosphor-icons/react";

const NAV = [
  { href: "/", label: "Overview", icon: ChartBar },
  { href: "/calls", label: "Calls", icon: PhoneCall },
  { href: "/appointments", label: "Appointments", icon: CalendarCheck },
  { href: "/callbacks", label: "Callbacks", icon: PhoneIncoming },
  { href: "/crm", label: "CRM sync", icon: ArrowsClockwise },
  { href: "/settings", label: "Settings", icon: GearSix },
];

export function Sidebar({ tenantName, userName }: { tenantName: string; userName: string }) {
  const pathname = usePathname();
  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-zinc-200 bg-white md:min-h-[100dvh] md:w-56 md:border-b-0 md:border-r">
      <div className="px-4 py-4">
        <p className="truncate text-sm font-semibold tracking-tight">{tenantName}</p>
        <p className="text-xs text-zinc-500">AI receptionist</p>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-1 md:flex-col md:overflow-visible">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm transition active:scale-[0.98] ${
                active
                  ? "bg-accent-50 font-medium text-accent-800"
                  : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
              }`}
            >
              <Icon size={18} weight={active ? "fill" : "regular"} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center justify-between border-t border-zinc-200 px-4 py-3">
        <span className="truncate text-xs text-zinc-600">{userName}</span>
        <form action="/api/auth/logout" method="post">
          <button
            type="submit"
            aria-label="Sign out"
            className="rounded p-1 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 active:scale-95"
          >
            <SignOut size={18} />
          </button>
        </form>
      </div>
    </aside>
  );
}
