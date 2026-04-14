"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import type { ExternalPaper } from "@/lib/types";

interface ExternalPaperCardProps {
  paper: ExternalPaper;
  selected: boolean;
  onToggle: (paper_id: string) => void;
}

export function ExternalPaperCard({ paper, selected, onToggle }: ExternalPaperCardProps) {
  const [expanded, setExpanded] = useState(false);

  const authorsText = paper.authors.length > 0
    ? paper.authors.join(", ")
    : "Unknown authors";

  const abstractText = paper.abstract || "No abstract available.";
  const isLongAbstract = abstractText.length > 250;
  const displayAbstract = expanded || !isLongAbstract
    ? abstractText
    : `${abstractText.slice(0, 250)}...`;

  return (
    <Card
      className={`transition-colors cursor-pointer ${
        selected ? "border-blue-400 bg-blue-50/50" : "hover:border-gray-300"
      }`}
      onClick={() => onToggle(paper.paper_id)}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="pt-0.5 shrink-0">
            <Checkbox
              checked={selected}
              onCheckedChange={() => onToggle(paper.paper_id)}
              onClick={(e) => e.stopPropagation()}
              aria-label={`Select ${paper.title}`}
            />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 mb-1">
              <h3 className="text-sm font-semibold text-gray-900 leading-snug">
                {paper.title}
              </h3>
              {paper.relevance_score != null && (
                <Badge className="shrink-0">
                  {Math.round(paper.relevance_score * 100)}% match
                </Badge>
              )}
            </div>

            <p className="text-xs text-gray-500 mb-2">
              {authorsText} &middot; {paper.year}
            </p>

            <p className="text-sm text-gray-600 leading-relaxed">
              {displayAbstract}
            </p>
            {isLongAbstract && (
              <button
                type="button"
                className="text-xs text-blue-600 hover:underline mt-1"
                onClick={(e) => {
                  e.stopPropagation();
                  setExpanded((prev) => !prev);
                }}
              >
                {expanded ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
