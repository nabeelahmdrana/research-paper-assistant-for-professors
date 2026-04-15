"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, FileText, ExternalLink, Calendar, User, Download } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { Paper } from "@/lib/types";
import { getPaper, getPaperPdfUrl } from "@/lib/api";

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function PaperDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [paper, setPaper] = useState<Paper | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    getPaper(id).then((r) => {
      if (r.data) setPaper(r.data);
      else setNotFound(true);
      setIsLoading(false);
    });
  }, [id]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (notFound || !paper) {
    return (
      <div className="py-16 text-center">
        <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-3">
          Paper not found
        </h2>
        <p className="text-sm text-gray-500 mb-6">
          The paper with ID &ldquo;{id}&rdquo; does not exist or the backend is not
          connected.
        </p>
        <Button variant="outline" asChild>
          <Link href="/library">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Library
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div>
      <Button variant="ghost" size="sm" asChild className="mb-6 -ml-2">
        <Link href="/library">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Library
        </Link>
      </Button>

      {/* Title */}
      <div className="flex items-start gap-4 mb-6">
        <FileText className="w-8 h-8 text-blue-600 shrink-0 mt-1" />
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold text-gray-900 leading-snug mb-2">
            {paper.title}
          </h1>
          <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <User className="w-3.5 h-3.5" />
              {paper.authors.join(", ")}
            </span>
            <span>&middot;</span>
            <span>{paper.year}</span>
            <StatusBadge variant={paper.source} />
          </div>
        </div>
      </div>

      <Separator className="mb-6" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Abstract */}
        <div className="md:col-span-2">
          <Card>
            <CardContent className="p-6">
              <h2 className="text-base font-semibold text-gray-700 mb-3">Abstract</h2>
              <p className="text-sm text-gray-700 leading-relaxed">{paper.abstract}</p>
            </CardContent>
          </Card>
        </div>

        {/* Metadata Sidebar */}
        <aside>
          <Card>
            <CardContent className="p-4 space-y-4 text-sm">
              {paper.hasPdf && (
                <div className="flex flex-col gap-2">
                  <a
                    href={getPaperPdfUrl(paper.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-2 w-full rounded-md bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 px-3 transition-colors"
                  >
                    <FileText className="w-4 h-4" />
                    View PDF
                  </a>
                  <a
                    href={getPaperPdfUrl(paper.id)}
                    download
                    className="flex items-center justify-center gap-2 w-full rounded-md border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-medium py-2 px-3 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Download PDF
                  </a>
                </div>
              )}

              <div>
                <p className="text-xs text-gray-500 mb-1">Source</p>
                <StatusBadge variant={paper.source} />
              </div>

              <div>
                <p className="text-xs text-gray-500 mb-1">Publication Year</p>
                <p className="font-medium text-gray-900">{paper.year}</p>
              </div>

              <div>
                <p className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                  <Calendar className="w-3 h-3" /> Date Added
                </p>
                <p className="font-medium text-gray-900">{formatDate(paper.dateAdded)}</p>
              </div>

              {paper.authors.length > 1 && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">All Authors</p>
                  <div className="flex flex-wrap gap-1">
                    {paper.authors.map((author) => (
                      <Badge
                        key={author}
                        variant="secondary"
                        className="text-xs font-normal"
                      >
                        {author}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {paper.doi && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">DOI</p>
                  <a
                    href={`https://doi.org/${paper.doi}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline flex items-center gap-1 text-xs break-all"
                  >
                    {paper.doi}
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>
                </div>
              )}

              {paper.url && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">URL</p>
                  <a
                    href={paper.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline flex items-center gap-1 text-xs break-all"
                  >
                    {paper.url}
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
