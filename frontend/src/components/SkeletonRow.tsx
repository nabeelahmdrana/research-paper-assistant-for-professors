import React from "react";
import { cn } from "@/lib/utils";

interface SkeletonRowProps {
  className?: string;
}

export function SkeletonRow({ className }: SkeletonRowProps) {
  return (
    <div
      className={cn("h-12 bg-gray-200 rounded animate-pulse mb-2", className)}
    />
  );
}
