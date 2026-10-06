"use client";

import { useActionState } from "react";
import { login, type LoginState } from "./actions";
import { btn, Notice } from "@/components/ui";

const initial: LoginState = { error: null, tenant_slug: "", email: "" };

function Field({
  label,
  name,
  type = "text",
  autoComplete,
  hint,
  defaultValue,
}: {
  label: string;
  name: string;
  type?: string;
  autoComplete?: string;
  hint?: string;
  defaultValue?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={name} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        autoComplete={autoComplete}
        defaultValue={defaultValue}
        required
        className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
      />
      {hint && <p className="text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}

export function LoginForm() {
  const [state, action, pending] = useActionState(login, initial);
  return (
    <form action={action} className="flex flex-col gap-5">
      {state.error && <Notice tone="bad">{state.error}</Notice>}
      <Field
        label="Business ID"
        name="tenant_slug"
        defaultValue={state.tenant_slug}
        autoComplete="organization"
        hint="The short ID your onboarding contact gave you."
      />
      <Field
        label="Email"
        name="email"
        type="email"
        defaultValue={state.email}
        autoComplete="username"
      />
      <Field label="Password" name="password" type="password" autoComplete="current-password" />
      <button type="submit" disabled={pending} className={`${btn.base} ${btn.primary} py-2`}>
        {pending ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}
