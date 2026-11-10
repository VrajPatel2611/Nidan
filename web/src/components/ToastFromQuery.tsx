"use client";

/**
 * Shows a toast named in `?toast=` and removes it from the address bar — how a
 * server redirect says "You've been signed out" (UX_SPEC §6.1.7) without a
 * client-side store. Only known keys: the query string is user-controlled, so
 * it selects a message, it never supplies one.
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useToast } from "@/components/ui";

export const TOASTS: Record<string, { text: string; tone: "success" | "error" }> = {
  "signed-out": { text: "You've been signed out", tone: "success" },
  "signin-cancelled": { text: "Sign-in cancelled", tone: "success" },
  "password-updated": { text: "Password updated", tone: "success" },
  "email-verified": { text: "Email verified", tone: "success" },
};

export function ToastFromQuery() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const show = useToast();
  const key = params.get("toast");

  useEffect(() => {
    if (!key) return;
    const toast = TOASTS[key];
    if (toast) show(toast.text, toast.tone);
    const rest = new URLSearchParams(params);
    rest.delete("toast");
    router.replace(rest.size ? `${pathname}?${rest}` : pathname, { scroll: false });
  }, [key, params, pathname, router, show]);

  return null;
}
