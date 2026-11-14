"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { toast } from "@/components/ui/toast";

export function CopyButton({ value, label, variant = "secondary" }: { value: string; label?: string; variant?: "secondary" | "ghost" | "primary" }) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast("success", t("common.copied"));
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast("error", "Clipboard unavailable", "Your browser blocked clipboard access.");
    }
  }

  return (
    <Button variant={variant} size="sm" onClick={copy} type="button">
      {copied ? <Check /> : <Copy />}
      {label ?? t("common.copy")}
    </Button>
  );
}
