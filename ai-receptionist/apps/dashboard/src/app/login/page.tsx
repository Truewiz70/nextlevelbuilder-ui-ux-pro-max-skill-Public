import type { Metadata } from "next";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="grid min-h-[100dvh] grid-cols-1 md:grid-cols-[3fr_2fr]">
      <section className="flex flex-col justify-end gap-3 bg-zinc-900 px-8 py-12 text-zinc-100 md:px-16">
        <h1 className="max-w-[18ch] text-3xl font-semibold leading-tight tracking-tight">
          Every call answered. Every booking on the calendar.
        </h1>
        <p className="max-w-[48ch] text-sm text-zinc-400">
          Review transcripts, work the callback queue and tune what your receptionist says.
        </p>
      </section>
      <section className="flex items-center px-8 py-12 md:px-14">
        <div className="w-full max-w-sm">
          <h2 className="mb-6 text-lg font-semibold tracking-tight">Sign in</h2>
          <LoginForm />
        </div>
      </section>
    </div>
  );
}
