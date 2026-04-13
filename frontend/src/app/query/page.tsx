"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Search, CheckCircle, Circle, ExternalLink, BookPlus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { QueryResult } from "@/lib/types";
import { runResearchQuery } from "@/lib/api";

type LoadingStep = "idle" | "active" | "done" | "error";

interface StepState {
  local: LoadingStep;
  external: LoadingStep;
  generating: LoadingStep;
}

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepState>({
    local: "idle",
    external: "idle",
    generating: "idle",
  });

  const handleSearch = async () => {
    if (!question.trim()) return;
    setIsLoading(true);
    setResult(null);
    setError(null);
    setSteps({ local: "active", external: "idle", generating: "idle" });

    try {
      setSteps({ local: "active", external: "idle", generating: "idle" });
      const res = await runResearchQuery(question);
      if (res.error) throw new Error(res.error);
      setSteps({ local: "done", external: "done", generating: "done" });
      setResult(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to the research pipeline.");
      setSteps({ local: "error", external: "idle", generating: "idle" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleRetry = () => {
    setError(null);
    setSteps({ local: "idle", external: "idle", generating: "idle" });
  };

  return (
    <div>
      <PageHeader
        title="Research Query"
        subtitle="Ask a question across your paper library"
      />

      {/* Search Form */}
      <Card className="mb-6">
        <CardContent className="p-6">
          <label
            htmlFor="research-question"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            What would you like to research?
          </label>
          <Textarea
            id="research-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            placeholder="e.g. What are the key differences between transformer-based and RNN-based language models?"
            className="mb-3"
            disabled={isLoading}
          />
          <div className="flex items-center justify-between flex-wrap gap-3">
            <p className="text-xs text-gray-500">
              Your query will first search local papers, then fetch externally if needed.
            </p>
            <Button
              onClick={handleSearch}
              disabled={isLoading || !question.trim()}
            >
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4 mr-2" />
                  Search Papers
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Loading Steps */}
      {isLoading && (
        <Card className="mb-6">
          <CardContent className="p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">
              Processing your query...
            </h3>
            <div className="space-y-4">
              <LoadingStepRow
                label="Searching local database..."
                status={steps.local}
              />
              {steps.external !== "idle" && (
                <LoadingStepRow
                  label="Fetching additional papers from Semantic Scholar..."
                  status={steps.external}
                />
              )}
              {steps.generating !== "idle" && (
                <LoadingStepRow
                  label="Generating literature review..."
                  status={steps.generating}
                />
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error State */}
      {error && (
        <div className="mb-6">
          <ErrorAlert
            title="Search failed"
            message={error}
            onRetry={handleRetry}
          />
        </div>
      )}

      {/* External Papers Notification */}
      {result && !isLoading && result.externalPapersFetched && (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <BookPlus className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
          <p className="text-sm text-blue-700">
            <span className="font-semibold">{result.newPapersCount} new paper{result.newPapersCount !== 1 ? "s" : ""}</span>
            {" "}were fetched from external sources and saved to your library.
          </p>
        </div>
      )}

      {/* Results Panel */}
      {result && !isLoading && (
        <Card className="mb-6">
          <CardContent className="p-6">
            <Tabs defaultValue="summary">
              <TabsList className="flex flex-wrap h-auto gap-1 mb-4">
                <TabsTrigger value="summary">Summary</TabsTrigger>
                <TabsTrigger value="agreements">
                  Agreements ({result.agreements.length})
                </TabsTrigger>
                <TabsTrigger value="contradictions">
                  Contradictions ({result.contradictions.length})
                </TabsTrigger>
                <TabsTrigger value="gaps">
                  Research Gaps ({result.researchGaps.length})
                </TabsTrigger>
                <TabsTrigger value="citations">
                  Citations ({result.citations.length})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="summary">
                <p className="text-base text-gray-700 leading-relaxed">
                  {result.summary}
                </p>
              </TabsContent>

              <TabsContent value="agreements">
                <ul className="space-y-2">
                  {result.agreements.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-blue-600 font-bold mt-0.5">&bull;</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </TabsContent>

              <TabsContent value="contradictions">
                <ul className="space-y-2">
                  {result.contradictions.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-blue-600 font-bold mt-0.5">&bull;</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </TabsContent>

              <TabsContent value="gaps">
                <ul className="space-y-2">
                  {result.researchGaps.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-blue-600 font-bold mt-0.5">&bull;</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </TabsContent>

              <TabsContent value="citations">
                <div className="space-y-3">
                  {result.citations.map((citation) => (
                    <div
                      key={citation.index}
                      className="flex items-start gap-3 p-3 rounded-lg border border-gray-200"
                    >
                      <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center shrink-0">
                        {citation.index}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-gray-900 truncate">
                          {citation.title}
                        </p>
                        <p className="text-xs text-gray-500">
                          {citation.authors.join(", ")} &middot; {citation.year}
                        </p>
                        {(citation.doi ?? citation.url) && (
                          <a
                            href={citation.url ?? `https://doi.org/${citation.doi}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-500 hover:underline flex items-center gap-1 mt-0.5"
                          >
                            {citation.doi ?? citation.url}
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                      <StatusBadge variant={citation.source} />
                    </div>
                  ))}
                </div>
              </TabsContent>
            </Tabs>

            <div className="mt-4 pt-4 border-t border-gray-200">
              <Button variant="outline" size="sm" asChild>
                <Link href={`/results/${result.id}`}>
                  View Full Review &rarr;
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!result && !isLoading && !error && (
        <EmptyState
          icon={<Search className="w-16 h-16" />}
          title="Ask a research question"
          description="Type your question above and click Search Papers. Your results will appear here."
        />
      )}
    </div>
  );
}

interface LoadingStepRowProps {
  label: string;
  subtext?: string;
  status: LoadingStep;
}

function LoadingStepRow({ label, subtext, status }: LoadingStepRowProps) {
  return (
    <div className="flex items-start gap-3">
      <div className="shrink-0 mt-0.5">
        {status === "done" && (
          <CheckCircle className="w-5 h-5 text-green-500" />
        )}
        {status === "active" && <LoadingSpinner size="sm" />}
        {status === "idle" && (
          <Circle className="w-5 h-5 text-gray-300" />
        )}
        {status === "error" && (
          <Circle className="w-5 h-5 text-red-500" />
        )}
      </div>
      <div>
        <p className="text-sm text-gray-700">{label}</p>
        {subtext && (
          <p className="text-xs text-gray-500 mt-0.5">{subtext}</p>
        )}
      </div>
    </div>
  );
}
