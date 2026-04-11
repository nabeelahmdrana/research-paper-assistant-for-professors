"use client";

import React, { useCallback, useRef, useState } from "react";
import { UploadCloud, FileText, CheckCircle, XCircle, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { toast } from "@/components/ui/use-toast";
import { MOCK_PAPERS, MOCK_DB_STATS } from "@/lib/mockData";
import type { Paper } from "@/lib/types";
import { cn } from "@/lib/utils";

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

function formatRelativeTime(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date("2026-04-11T12:00:00Z");
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);
  if (diffHours < 24) return `${diffHours} hrs ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return `${Math.floor(diffDays / 7)}w ago`;
}

export default function UploadPage() {
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [doiInput, setDoiInput] = useState("");
  const [isFetchingDoi, setIsFetchingDoi] = useState(false);
  const [doiError, setDoiError] = useState<string | null>(null);
  const [papers] = useState<Paper[]>(MOCK_PAPERS);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const simulateUpload = useCallback((uploadId: string) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.floor(Math.random() * 15) + 5;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        setUploadFiles((prev) =>
          prev.map((f) =>
            f.id === uploadId ? { ...f, progress: 100, status: "success" } : f
          )
        );
        toast({ title: "Upload complete", description: "Paper stored successfully." });
      } else {
        setUploadFiles((prev) =>
          prev.map((f) =>
            f.id === uploadId ? { ...f, progress, status: "uploading" } : f
          )
        );
      }
    }, 200);
  }, []);

  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const fileArray = Array.from(files);
      fileArray.forEach((file) => {
        const isPdf = file.type === "application/pdf" || file.name.endsWith(".pdf");
        const uploadId = `${Date.now()}-${Math.random()}`;
        const newFile: UploadFile = {
          id: uploadId,
          file,
          progress: 0,
          status: isPdf ? "idle" : "error",
          errorMessage: isPdf ? undefined : "Only PDF files are supported",
        };
        setUploadFiles((prev) => [...prev, newFile]);
        if (isPdf) {
          setTimeout(() => simulateUpload(uploadId), 300);
        }
      });
    },
    [simulateUpload]
  );

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

  const handleFetchDoi = async () => {
    if (!doiInput.trim()) return;
    setIsFetchingDoi(true);
    setDoiError(null);
    // Simulate fetch
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsFetchingDoi(false);
    setDoiInput("");
    toast({
      title: "Papers fetched",
      description: "2 papers fetched and stored successfully.",
    });
  };

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
                      {uf.status === "success" && (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      )}
                      {uf.status === "error" && (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}
                      <button
                        onClick={() => removeFile(uf.id)}
                        className="text-gray-400 hover:text-gray-600 rounded-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                        aria-label="Remove file"
                      >
                        <X className="w-4 h-4" />
                      </button>
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
                  {uf.status === "success" && (
                    <p className="text-xs text-green-600">Stored successfully</p>
                  )}
                  {uf.status === "error" && uf.errorMessage && (
                    <p className="text-xs text-red-500">{uf.errorMessage}</p>
                  )}
                </div>
              ))}
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

      {/* Status Bar */}
      <div className="flex items-center gap-4 text-sm text-gray-600 mb-6">
        <span>{MOCK_DB_STATS.paperCount} papers stored</span>
        <span>&middot;</span>
        <span>{MOCK_DB_STATS.dbSizeMB} MB used</span>
        <span>&middot;</span>
        <span className="flex items-center gap-1.5">
          ChromaDB:
          <span
            className={cn(
              "w-2 h-2 rounded-full inline-block",
              MOCK_DB_STATS.isConnected ? "bg-green-500" : "bg-red-500"
            )}
          />
          {MOCK_DB_STATS.isConnected ? "Connected" : "Disconnected"}
        </span>
      </div>

      {/* Papers Table */}
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Papers in Your Library
      </h2>
      {papers.length === 0 ? (
        <EmptyState
          icon={<FileText className="w-16 h-16" />}
          title="No papers yet"
          description="Upload a PDF or enter a DOI above to get started."
        />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-4 py-3 text-left font-medium text-gray-700">
                    Title
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">
                    Authors
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">
                    Year
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">
                    Source
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">
                    Added
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {papers.map((paper) => (
                  <tr key={paper.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 max-w-xs">
                      <p className="font-medium text-gray-900 truncate">
                        {paper.title}
                      </p>
                    </td>
                    <td className="px-4 py-3 max-w-[160px]">
                      <p className="text-gray-600 truncate">
                        {paper.authors.slice(0, 2).join(", ")}
                        {paper.authors.length > 2 &&
                          ` +${paper.authors.length - 2}`}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{paper.year}</td>
                    <td className="px-4 py-3">
                      <StatusBadge variant={paper.source} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {formatRelativeTime(paper.dateAdded)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
