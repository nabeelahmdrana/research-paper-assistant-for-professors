"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, CheckCircle, Circle, ExternalLink, BookPlus, ArrowLeft, Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Separator } from "@/components/ui/separator";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { ExternalPaperCard } from "@/components/ExternalPaperCard";
import { SkeletonRow } from "@/components/SkeletonRow";
import type { QueryResult, ExternalPaper } from "@/lib/types";
import { runQuery, confirmExternalPapers, listQueryResults } from "@/lib/api";

type LoadingStep = "idle" | "active" | "done" | "error";

interface StepState {
  local: LoadingStep;
  external: LoadingStep;
  generating: LoadingStep;
}

export default function QueryPage() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepState>({
    local: "idle",
    external: "idle",
    generating: "idle",
  });

  const [step, setStep] = useState<"query" | "select">("query");
  const [pendingResultId, setPendingResultId] = useState<string>("");
  const [externalCandidates, setExternalCandidates] = useState<ExternalPaper[]>([]);
  const [selectedPaperIds, setSelectedPaperIds] = useState<Set<string>>(new Set());
  const [isConfirming, setIsConfirming] = useState(false);

  const [pastQueries, setPastQueries] = useState<QueryResult[]>([]);
  const [pastQueriesLoading, setPastQueriesLoading] = useState(true);

  const loadPastQueries = () => {
    listQueryResults().then((r) => {
      if (r.data) setPastQueries(r.data.results);
      setPastQueriesLoading(false);
    });
  };

  useEffect(() => {
    loadPastQueries();
  }, []);

  const handleSearch = async () => {
    if (!question.trim()) return;
    setIsLoading(true);
    setResult(null);
    setError(null);
    setStep("query");
    setExternalCandidates([]);
    setSelectedPaperIds(new Set());
    setPendingResultId("");
    setSteps({ local: "active", external: "idle", generating: "idle" });

    try {
      const response = await runQuery(question);

      if (response.status === "needs_external_selection") {
        setSteps({ local: "done", external: "done", generating: "idle" });
        setPendingResultId(response.result_id);
        setExternalCandidates(response.external_papers);
        setStep("select");
      } else {
        setSteps({ local: "done", external: "done", generating: "done" });
        setResult(response.data);
        loadPastQueries();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to the research pipeline.");
      setSteps({ local: "error", external: "idle", generating: "idle" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmSelection = async () => {
    if (!pendingResultId) return;
    setIsConfirming(true);
    setError(null);
    setSteps({ local: "done", external: "done", generating: "active" });

    try {
      const finalResult = await confirmExternalPapers(
        pendingResultId,
        Array.from(selectedPaperIds)
      );
      setSteps({ local: "done", external: "done", generating: "done" });
      setResult(finalResult);
      setStep("query");
      setExternalCandidates([]);
      loadPastQueries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to process selected papers.");
      setSteps({ local: "done", external: "done", generating: "error" });
    } finally {
      setIsConfirming(false);
    }
  };

  const handleSkipExternal = () => {
    if (pendingResultId) {
      router.push(`/results/${pendingResultId}`);
    } else {
      setError("No local results available.");
    }
  };

  const handleTogglePaper = (paperId: string) => {
    setSelectedPaperIds((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) {
        next.delete(paperId);
      } else {
        next.add(paperId);
      }
      return next;
    });
  };

  const handleRetry = () => {
    setError(null);
    setStep("query");
    setExternalCandidates([]);
    setSelectedPaperIds(new Set());
    setPendingResultId("");
    setSteps({ local: "idle", external: "idle", generating: "idle" });
  };

  const handleBackToQuery = () => {
    setStep("query");
    setExternalCandidates([]);
    setSelectedPaperIds(new Set());
    setPendingResultId("");
    setSteps({ local: "idle", external: "idle", generating: "idle" });
  };

  return (
    <div>
      <PageHeader
        title="Research Query"
        subtitle="Ask a question across your paper library"
      />

      {/* Search Form */}
      {step === "query" && (
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
      )}

      {/* Loading Steps */}
      {(isLoading || isConfirming) && (
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
                  label="Fetching additional papers from external sources..."
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

      {/* External Paper Selection Step */}
      {step === "select" && !isConfirming && externalCandidates.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <button
              type="button"
              onClick={handleBackToQuery}
              className="text-gray-500 hover:text-gray-700"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                External papers found — select papers to include
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Your local library didn&apos;t have enough coverage. We found {externalCandidates.length} relevant
                paper{externalCandidates.length !== 1 ? "s" : ""} from external sources.
                Select the ones you&apos;d like to include in your analysis.
              </p>
            </div>
          </div>

          <div className="space-y-3 mb-4">
            {externalCandidates.map((paper) => (
              <ExternalPaperCard
                key={paper.paper_id}
                paper={paper}
                selected={selectedPaperIds.has(paper.paper_id)}
                onToggle={handleTogglePaper}
              />
            ))}
          </div>

          <div className="flex items-center justify-between gap-3 flex-wrap">
            <p className="text-xs text-gray-500">
              {selectedPaperIds.size} of {externalCandidates.length} paper{externalCandidates.length !== 1 ? "s" : ""} selected
            </p>
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                onClick={handleSkipExternal}
              >
                Skip — use local results only
              </Button>
              <Button
                onClick={handleConfirmSelection}
                disabled={selectedPaperIds.size === 0 || isConfirming}
              >
                {isConfirming ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    Processing...
                  </>
                ) : (
                  `Confirm Selection (${selectedPaperIds.size})`
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* External Papers Notification */}
      {result && !isLoading && !isConfirming && result.externalPapersFetched && (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <BookPlus className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
          <p className="text-sm text-blue-700">
            <span className="font-semibold">{result.newPapersCount} new paper{result.newPapersCount !== 1 ? "s" : ""}</span>
            {" "}were fetched from external sources and saved to your library.
          </p>
        </div>
      )}

      {/* Results Panel */}
      {result && !isLoading && !isConfirming && (
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
              <Button variant="outline" size="sm" onClick={() => router.push(`/results/${result.id}`)}>
                View Full Review &rarr;
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty State — only when no past queries either */}
      {!result && !isLoading && !error && step === "query" && pastQueries.length === 0 && !pastQueriesLoading && (
        <EmptyState
          icon={<Search className="w-16 h-16" />}
          title="Ask a research question"
          description="Type your question above and click Search Papers. Your results will appear here."
        />
      )}

      {/* Past Queries List */}
      {step === "query" && !isLoading && !isConfirming && (
        <Card>
          <CardContent className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Past Queries
            </h2>
            {pastQueriesLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <SkeletonRow key={i} />
                ))}
              </div>
            ) : pastQueries.length === 0 ? (
              <p className="text-sm text-gray-500 py-3">
                No queries yet. Ask your first research question above.
              </p>
            ) : (
              <div className="space-y-0">
                {pastQueries.map((q, idx) => (
                  <div key={q.id}>
                    <div className="flex items-start justify-between py-3 group">
                      <div className="flex-1 min-w-0 pr-4">
                        <p className="text-sm font-medium text-gray-800">
                          {q.question}
                        </p>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(q.createdAt).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                              hour: "numeric",
                              minute: "2-digit",
                            })}
                          </span>
                          {q.citations.length > 0 && (
                            <span className="text-xs text-gray-500">
                              {q.citations.length} citation{q.citations.length !== 1 ? "s" : ""}
                            </span>
                          )}
                          {q.externalPapersFetched && (
                            <span className="text-xs text-blue-600 font-medium">
                              + external
                            </span>
                          )}
                        </div>
                      </div>
                      <Link
                        href={`/results/${q.id}`}
                        className="text-xs text-blue-600 hover:underline whitespace-nowrap shrink-0 mt-1"
                      >
                        View &rarr;
                      </Link>
                    </div>
                    {idx < pastQueries.length - 1 && <Separator />}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
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
