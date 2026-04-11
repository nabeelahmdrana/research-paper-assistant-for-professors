"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Copy,
  FileText,
  Download,
  ExternalLink,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { toast } from "@/components/ui/use-toast";
import type { QueryResult } from "@/lib/types";
import { getQueryResult } from "@/lib/api";

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function ResultDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [result, setResult] = useState<QueryResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    getQueryResult(id).then((r) => {
      if (r.data) setResult(r.data);
      else setNotFound(true);
      setIsLoading(false);
    });
  }, [id]);

  const buildFullText = (r: QueryResult): string => {
    return [
      `# Literature Review`,
      `**Question:** ${r.question}`,
      `**Generated:** ${formatDate(r.createdAt)}`,
      "",
      `## Summary`,
      r.summary,
      "",
      `## Key Agreements`,
      ...r.agreements.map((a) => `- ${a}`),
      "",
      `## Contradictions`,
      ...r.contradictions.map((c) => `- ${c}`),
      "",
      `## Research Gaps`,
      ...r.researchGaps.map((g) => `- ${g}`),
      "",
      `## Citations`,
      ...r.citations.map(
        (c) =>
          `[${c.index}] ${c.title} — ${c.authors.join(", ")} (${c.year}) [${c.source}]`
      ),
    ].join("\n");
  };

  const handleCopy = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(buildFullText(result));
    toast({ title: "Copied to clipboard!" });
  };

  const handleExportMarkdown = () => {
    if (!result) return;
    const text = buildFullText(result);
    const blob = new Blob([text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `review-${formatDate(result.createdAt).replace(/\s/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportPdf = () => {
    window.print();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (notFound || !result) {
    return (
      <div className="py-16 text-center">
        <h2 className="text-xl font-semibold text-gray-900 mb-3">
          Review not found
        </h2>
        <p className="text-sm text-gray-500 mb-6">
          The review with ID &ldquo;{id}&rdquo; does not exist or the backend is not connected.
        </p>
        <Button variant="outline" asChild>
          <Link href="/query">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Query
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Button variant="ghost" size="sm" asChild className="mb-4 -ml-2">
          <Link href="/query">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Query
          </Link>
        </Button>

        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          &ldquo;{result.question}&rdquo;
        </h1>
        <p className="text-sm text-gray-500 mb-4">
          Generated on {formatDate(result.createdAt)} &middot;{" "}
          {result.citations.length} papers cited
        </p>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
          >
            <Copy className="w-4 h-4 mr-2" />
            Copy to Clipboard
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportMarkdown}
          >
            <FileText className="w-4 h-4 mr-2" />
            Export Markdown
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportPdf}
          >
            <Download className="w-4 h-4 mr-2" />
            Export PDF
          </Button>
        </div>
      </div>

      <Separator className="mb-8" />

      {/* Two-column layout */}
      <div className="flex flex-col md:flex-row gap-8 items-start">
        {/* Main Content */}
        <div className="flex-1 min-w-0 space-y-8">
          <ResultSection title="Summary">
            <p className="text-base text-gray-700 leading-relaxed">
              {result.summary}
            </p>
          </ResultSection>

          <ResultSection title="Key Agreements">
            <ul className="space-y-2">
              {result.agreements.map((item, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-base text-gray-700"
                >
                  <span className="text-blue-600 font-bold mt-0.5">&bull;</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </ResultSection>

          <ResultSection title="Contradictions">
            <ul className="space-y-2">
              {result.contradictions.map((item, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-base text-gray-700"
                >
                  <span className="text-blue-600 font-bold mt-0.5">&bull;</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </ResultSection>

          <ResultSection title="Research Gaps">
            <ul className="space-y-2">
              {result.researchGaps.map((item, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-base text-gray-700"
                >
                  <span className="text-blue-600 font-bold mt-0.5">&bull;</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </ResultSection>
        </div>

        {/* Sidebar */}
        <aside className="w-full md:w-72 shrink-0 md:sticky md:top-8 md:self-start">
          <Card>
            <CardContent className="p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">
                Cited Papers ({result.citations.length})
              </h3>
              <div
                className="space-y-3 overflow-y-auto"
                style={{ maxHeight: "calc(100vh - 200px)" }}
              >
                {result.citations.map((citation) => (
                  <div key={citation.index} className="flex items-start gap-2">
                    <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center shrink-0">
                      {citation.index}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-gray-800 leading-tight">
                        {citation.title}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {citation.authors[0]} &middot; {citation.year}
                      </p>
                      <div className="flex items-center gap-1 mt-1">
                        <StatusBadge variant={citation.source} />
                        {(citation.doi ?? citation.url) && (
                          <a
                            href={
                              citation.url ?? `https://doi.org/${citation.doi}`
                            }
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:text-blue-700"
                            aria-label="Open paper link"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

interface ResultSectionProps {
  title: string;
  children: React.ReactNode;
}

function ResultSection({ title, children }: ResultSectionProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-4">{title}</h2>
      <Card>
        <CardContent className="p-6">{children}</CardContent>
      </Card>
    </div>
  );
}
