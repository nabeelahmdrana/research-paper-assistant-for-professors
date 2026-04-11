import React from "react";
import { cn } from "@/lib/utils";

interface SkeletonCardProps {
  className?: string;
}

export function SkeletonCard({ className }: SkeletonCardProps) {
  return (
    <div
      className={cn("h-24 bg-gray-200 rounded-lg animate-pulse", className)}
    />
  );
}
