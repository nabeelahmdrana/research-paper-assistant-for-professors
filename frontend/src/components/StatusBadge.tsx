import React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type BadgeVariant = "pdf" | "doi" | "arxiv" | "local" | "external";

const variantStyles: Record<BadgeVariant, string> = {
  pdf: "bg-blue-100 text-blue-700",
  doi: "bg-green-100 text-green-700",
  arxiv: "bg-green-100 text-green-700",
  local: "bg-blue-100 text-blue-700",
  external: "bg-green-100 text-green-700",
};

const variantLabels: Record<BadgeVariant, string> = {
  pdf: "Library",
  doi: "External",
  arxiv: "External",
  local: "Library",
  external: "External",
};

interface StatusBadgeProps {
  variant: BadgeVariant;
  className?: string;
}

export function StatusBadge({ variant, className }: StatusBadgeProps) {
  return (
    <Badge
      className={cn(
        "uppercase text-xs font-semibold border-0",
        variantStyles[variant],
        className
      )}
    >
      {variantLabels[variant]}
    </Badge>
  );
}
