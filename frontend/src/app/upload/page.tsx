"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { UploadCloud, FileText, CheckCircle, XCircle, X, Clock, Search, BookPlus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { toast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import { uploadPapers, fetchPapersByDoi, getDbStats, searchExternalPapers, importExternalPapers } from "@/lib/api";
import type { DbStats, ExternalPaper } from "@/lib/types";

type UploadStatus = "idle" | "uploading" | "success" | "error";

interface UploadFile {
  id: string;
  file: File;
  progress: number;
  status: UploadStatus;
  errorMessage?: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [doiInput, setDoiInput] = useState("");
  const [isFetchingDoi, setIsFetchingDoi] = useState(false);
  const [doiError, setDoiError] = useState<string | null>(null);
  const [dbStats, setDbStats] = useState<DbStats | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Discover / external search state
  const [discoverQuery, setDiscoverQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<ExternalPaper[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isImporting, setIsImporting] = useState(false);

  useEffect(() => {
    getDbStats().then((r) => r.data && setDbStats(r.data));
  }, []);

  const addFiles = useCallback((files: FileList | File[]) => {
    Array.from(files).forEach((file) => {
      const isPdf = file.type === "application/pdf" || file.name.endsWith(".pdf");
      const uploadId = `${Date.now()}-${Math.random()}`;
      setUploadFiles((prev) => [
        ...prev,
        {
          id: uploadId,
          file,
          progress: 0,
          status: isPdf ? "idle" : "error",
          errorMessage: isPdf ? undefined : "Only PDF files are supported",
        },
      ]);
    });
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
      e.target.value = "";
    }
  };

  const removeFile = (id: string) => {
    setUploadFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const handleUploadAll = async () => {
    const pending = uploadFiles.filter((f) => f.status === "idle");
    if (pending.length === 0) return;

    setUploadFiles((prev) =>
      prev.map((f) => (f.status === "idle" ? { ...f, status: "uploading" as UploadStatus, progress: 30 } : f))
    );

    const result = await uploadPapers(pending.map((f) => f.file));

    // Build a map from filename → error message using the per-file errors array
    // Backend error strings are formatted as "filename.pdf: reason"
    const fileErrors = new Map<string, string>();
    for (const errStr of result.data?.errors ?? []) {
      const colonIdx = errStr.indexOf(":");
      if (colonIdx !== -1) {
        const fname = errStr.slice(0, colonIdx).trim();
        const reason = errStr.slice(colonIdx + 1).trim();
        fileErrors.set(fname, reason);
      }
    }

    setUploadFiles((prev) =>
      prev.map((f) => {
        if (f.status !== "uploading") return f;
        const errorReason = fileErrors.get(f.file.name);
        const failed = errorReason !== undefined;
        return {
          ...f,
          progress: 100,
          status: failed ? ("error" as UploadStatus) : ("success" as UploadStatus),
          errorMessage: failed ? errorReason : undefined,
        };
      })
    );

    if (result.error) {
      toast({ title: "Upload error", description: result.error });
    } else {
      toast({
        title: `${result.data?.uploaded ?? 0} paper(s) uploaded`,
        description: "Papers have been stored in local database.",
      });
      getDbStats().then((r) => r.data && setDbStats(r.data));
    }
  };

  const handleFetchDoi = async () => {
    if (!doiInput.trim()) return;
    setIsFetchingDoi(true);
    setDoiError(null);

    try {
      const lines = doiInput.split("\n").map((l) => l.trim()).filter(Boolean);
      const result = await fetchPapersByDoi(lines);
      if (result.error) throw new Error(result.error);
      toast({ title: `${result.data?.fetched ?? 0} paper(s) fetched and stored.` });
      setDoiInput("");
      getDbStats().then((r) => r.data && setDbStats(r.data));
    } catch (err) {
      setDoiError(err instanceof Error ? err.message : "Fetch failed");
    } finally {
      setIsFetchingDoi(false);
    }
  };

  const handleDiscover = async () => {
    if (!discoverQuery.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    setSearchResults([]);
    setSelectedIds(new Set());
    try {
      const res = await searchExternalPapers(discoverQuery.trim(), 10);
      if (res.error) throw new Error(res.error);
      setSearchResults(res.data?.papers ?? []);
      if ((res.data?.total ?? 0) === 0) {
        setSearchError("No papers found. Try a different query.");
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  const toggleSelect = (paperId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(paperId) ? next.delete(paperId) : next.add(paperId);
      return next;
    });
  };

  const handleImportSelected = async () => {
    const toImport = searchResults.filter((p) => selectedIds.has(p.paper_id));
    if (toImport.length === 0) return;
    setIsImporting(true);
    try {
      const res = await importExternalPapers(toImport);
      if (res.error) throw new Error(res.error);
      toast({
        title: `${res.data?.imported ?? 0} paper(s) imported`,
        description: `${res.data?.chunks ?? 0} chunks stored in local database.`,
      });
      setSelectedIds(new Set());
      getDbStats().then((r) => r.data && setDbStats(r.data));
    } catch (err) {
      toast({
        title: "Import failed",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setIsImporting(false);
    }
  };

  const pendingCount = uploadFiles.filter((f) => f.status === "idle").length;

  return (
    <div>
      <PageHeader
        title="Upload Papers"
        subtitle="Add research papers to your local ChromaDB library"
      />

      {/* Upload Zone */}
      <Card className="mb-6">
        <CardContent className="p-6">
          <div
            className={cn(
              "border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors",
              isDragOver
                ? "border-blue-400 bg-blue-50"
                : "border-gray-300 bg-gray-50 hover:border-gray-400"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
            aria-label="Upload PDF files"
          >
            <UploadCloud className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-base text-gray-700 font-medium mb-1">
              Drag and drop PDF files here, or click to browse
            </p>
            <p className="text-sm text-gray-500 mb-4">
              PDF files only &middot; Max 50MB per file
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              Browse Files
            </Button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={handleFileInputChange}
            aria-hidden="true"
          />

          {/* File List */}
          {uploadFiles.length > 0 && (
            <div className="mt-4 space-y-3">
              {uploadFiles.map((uf) => (
                <div
                  key={uf.id}
                  className="border border-gray-200 rounded-lg p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="w-5 h-5 text-blue-600 shrink-0" />
                      <span className="text-sm font-medium text-gray-700 truncate">
                        {uf.file.name}
                      </span>
                      <span className="text-xs text-gray-400 shrink-0">
                        {formatFileSize(uf.file.size)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-2">
                      {uf.status === "idle" && (
                        <span title="Pending upload">
                          <Clock className="w-5 h-5 text-gray-400" />
                        </span>
                      )}
                      {uf.status === "success" && (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      )}
                      {uf.status === "error" && (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}

                      {uf.status !== "success" && (
                      <button
                        onClick={() => removeFile(uf.id)}
                        className="text-gray-400 hover:text-gray-600 rounded-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                        aria-label="Remove file"
                        disabled={uf.status === "uploading"}
                      >
                        <X className="w-4 h-4" />
                      </button>
                      )}
                    </div>
                  </div>
                  {uf.status === "uploading" && (
                    <>
                      <Progress value={uf.progress} className="h-1.5 mb-1" />
                      <p className="text-xs text-gray-500">
                        Processing... {uf.progress}%
                      </p>
                    </>
                  )}
                  {uf.status === "idle" && (
                    <p className="text-xs text-gray-400">Pending — ready to upload</p>
                  )}
                  {uf.status === "success" && (
                    <p className="text-xs text-green-600">Stored successfully</p>
                  )}
                  {uf.status === "error" && uf.errorMessage && (
                    <p className="text-xs text-red-500">{uf.errorMessage}</p>
                  )}
                </div>
              ))}

              {pendingCount > 0 && (
                <Button
                  onClick={handleUploadAll}
                  className="w-full sm:w-auto"
                >
                  Upload {pendingCount} File{pendingCount !== 1 ? "s" : ""}
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Separator className="my-6" />

      {/* DOI/URL Section */}
      <Card className="mb-6">
        <CardContent className="p-6">
          <h2 className="text-base font-semibold text-gray-700 mb-3">
            OR FETCH BY DOI / URL
          </h2>
          <Textarea
            value={doiInput}
            onChange={(e) => setDoiInput(e.target.value)}
            rows={5}
            placeholder={`Enter one DOI or URL per line\ne.g. 10.48550/arXiv.1706.03762\n     https://arxiv.org/abs/1810.04805`}
            className="mb-3 font-mono text-sm"
          />
          {doiError && (
            <Alert variant="destructive" className="mb-3">
              <AlertTitle>Fetch failed</AlertTitle>
              <AlertDescription>{doiError}</AlertDescription>
            </Alert>
          )}
          <Button
            onClick={handleFetchDoi}
            disabled={isFetchingDoi || !doiInput.trim()}
            className="w-full sm:w-auto"
          >
            {isFetchingDoi ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                Fetching...
              </>
            ) : (
              "Fetch & Store"
            )}
          </Button>
        </CardContent>
      </Card>

      <Separator className="my-6" />

      {/* Discover / External Search Section */}
      <Card className="mb-6">
        <CardContent className="p-6">
          <h2 className="text-base font-semibold text-gray-700 mb-1">
            SEARCH EXTERNAL DATABASES
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Search Semantic Scholar + arXiv via the MCP server. Preview results and selectively import into your local library.
          </p>

          <div className="flex gap-2 mb-4">
            <Input
              value={discoverQuery}
              onChange={(e) => setDiscoverQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !isSearching && handleDiscover()}
              placeholder="e.g. transformer attention mechanism, BERT language model..."
              className="flex-1"
              disabled={isSearching}
            />
            <Button
              onClick={handleDiscover}
              disabled={isSearching || !discoverQuery.trim()}
            >
              {isSearching ? (
                <LoadingSpinner size="sm" className="mr-2" />
              ) : (
                <Search className="w-4 h-4 mr-2" />
              )}
              {isSearching ? "Searching..." : "Search"}
            </Button>
          </div>

          {searchError && (
            <Alert variant="destructive" className="mb-4">
              <AlertTitle>Search error</AlertTitle>
              <AlertDescription>{searchError}</AlertDescription>
            </Alert>
          )}

          {searchResults.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm text-gray-600">
                  {searchResults.length} result{searchResults.length !== 1 ? "s" : ""} found
                  {selectedIds.size > 0 && (
                    <span className="ml-1 text-blue-600 font-medium">
                      · {selectedIds.size} selected
                    </span>
                  )}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setSelectedIds(new Set(searchResults.map((p) => p.paper_id)))
                    }
                    className="text-xs"
                  >
                    Select all
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedIds(new Set())}
                    className="text-xs"
                    disabled={selectedIds.size === 0}
                  >
                    Clear
                  </Button>
                </div>
              </div>

              <div className="space-y-2 mb-4 max-h-[480px] overflow-y-auto pr-1">
                {searchResults.map((paper) => (
                  <div
                    key={paper.paper_id}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                      selectedIds.has(paper.paper_id)
                        ? "border-blue-300 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300 bg-white"
                    )}
                    onClick={() => toggleSelect(paper.paper_id)}
                  >
                    <Checkbox
                      checked={selectedIds.has(paper.paper_id)}
                      onCheckedChange={() => toggleSelect(paper.paper_id)}
                      onClick={(e) => e.stopPropagation()}
                      className="mt-1 shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start gap-2 mb-0.5">
                        <p className="text-sm font-semibold text-gray-900 leading-snug flex-1">
                          {paper.title}
                        </p>
                        <Badge variant="outline" className="text-xs shrink-0">
                          external
                        </Badge>
                      </div>
                      <p className="text-xs text-gray-500 mb-1">
                        {paper.authors.slice(0, 3).join(", ")}
                        {paper.authors.length > 3 && " et al."}
                        {paper.year ? ` · ${paper.year}` : ""}
                      </p>
                      {paper.abstract && (
                        <p className="text-xs text-gray-600 line-clamp-2">
                          {paper.abstract}
                        </p>
                      )}
                      {!paper.abstract && (
                        <p className="text-xs text-amber-600 italic">
                          No abstract — will be skipped during import
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <Button
                onClick={handleImportSelected}
                disabled={selectedIds.size === 0 || isImporting}
                className="w-full sm:w-auto"
              >
                {isImporting ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    Importing...
                  </>
                ) : (
                  <>
                    <BookPlus className="w-4 h-4 mr-2" />
                    Import Selected ({selectedIds.size})
                  </>
                )}
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      <Separator className="my-6" />

      {/* Status Bar */}
      {/* <div className="flex items-center gap-4 text-sm text-gray-600 mb-6">
        <span>{dbStats?.paperCount ?? "—"} papers stored</span>
        <span>&middot;</span>
        <span>{dbStats?.dbSizeMB ?? "—"} MB used</span>
        <span>&middot;</span>
        <span className="flex items-center gap-1.5">
          ChromaDB:
          <span
            className={`w-2 h-2 rounded-full inline-block ${
              dbStats === null
                ? "bg-gray-300"
                : dbStats.isConnected
                ? "bg-green-500"
                : "bg-red-400"
            }`}
          />
          <span className="text-gray-400">
            {dbStats === null
              ? "Checking..."
              : dbStats.isConnected
              ? "Connected"
              : "Disconnected"}
          </span>
        </span>
      </div> */}

      {/* Papers Table */}
      {/* <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Papers in Your Library
      </h2>
      <EmptyState
        icon={<FileText className="w-16 h-16" />}
        title="No papers yet"
        description="Upload a PDF or enter a DOI above to get started."
      /> */}
    </div>
  );
}
