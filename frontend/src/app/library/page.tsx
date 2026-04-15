"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { Search, Eye, Trash2, BookOpen, ChevronLeft, ChevronRight, FileText } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonRow } from "@/components/SkeletonRow";
import { toast } from "@/components/ui/use-toast";
import type { Paper } from "@/lib/types";
import { listPapers, deletePaper, getPaperPdfUrl } from "@/lib/api";
import { useRouter } from "next/navigation";

const PAGE_SIZE = 20;

export default function LibraryPage() {
  const router = useRouter();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [deleteTarget, setDeleteTarget] = useState<Paper | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  useEffect(() => {
    listPapers().then((r) => {
      if (r.data) setPapers(r.data.papers);
      setIsLoading(false);
    });
  }, []);

  const LIBRARY_SOURCES = new Set(["pdf", "local"]);
  const EXTERNAL_SOURCES = new Set(["external", "doi", "arxiv"]);

  const filteredPapers = useMemo(() => {
    return papers.filter((p) => {
      const matchesSearch =
        !searchQuery ||
        p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.authors.some((a) =>
          a.toLowerCase().includes(searchQuery.toLowerCase())
        );
      const matchesSource =
        sourceFilter === "all" ||
        (sourceFilter === "local" && LIBRARY_SOURCES.has(p.source)) ||
        (sourceFilter === "external" && EXTERNAL_SOURCES.has(p.source));
      const matchesYearFrom = !yearFrom || p.year >= parseInt(yearFrom);
      const matchesYearTo = !yearTo || p.year <= parseInt(yearTo);
      return matchesSearch && matchesSource && matchesYearFrom && matchesYearTo;
    });
  }, [papers, searchQuery, sourceFilter, yearFrom, yearTo]);

  const totalPages = Math.max(1, Math.ceil(filteredPapers.length / PAGE_SIZE));
  const paginatedPapers = filteredPapers.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === paginatedPapers.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(paginatedPapers.map((p) => p.id)));
    }
  };

  const confirmDelete = (paper: Paper) => {
    setDeleteTarget(paper);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    const res = await deletePaper(deleteTarget.id);
    if (res.error) {
      toast({ title: "Delete failed", description: res.error });
      setDeleteTarget(null);
      return;
    }
    setPapers((prev) => prev.filter((p) => p.id !== deleteTarget.id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.delete(deleteTarget.id);
      return next;
    });
    setDeleteTarget(null);
    toast({
      title: "Paper deleted",
      description: `"${deleteTarget.title}" was removed. Past query results citing this paper have been cleared.`,
    });
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds);
    await Promise.all(ids.map((id) => deletePaper(id)));
    setPapers((prev) => prev.filter((p) => !selectedIds.has(p.id)));
    const count = ids.length;
    setSelectedIds(new Set());
    setBulkDeleteOpen(false);
    toast({ title: `${count} papers deleted` });
  };

  return (
    <div>
      <PageHeader
        title="Paper Library"
        subtitle="Browse and manage your ingested research papers"
        actions={
          <Badge className="bg-blue-100 text-blue-700 text-sm px-3 py-1">
            {filteredPapers.length} papers
          </Badge>
        }
      />

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Search papers..."
            className="pl-9"
          />
        </div>

        <Select
          value={sourceFilter}
          onValueChange={(v) => {
            setSourceFilter(v);
            setCurrentPage(1);
          }}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Source" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All sources</SelectItem>
            <SelectItem value="local">Library</SelectItem>
            <SelectItem value="external">External</SelectItem>
          </SelectContent>
        </Select>

        {selectedIds.size > 0 && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setBulkDeleteOpen(true)}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete Selected ({selectedIds.size})
          </Button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div>
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonRow key={i} />
          ))}
        </div>
      ) : filteredPapers.length === 0 ? (
        <EmptyState
          icon={<BookOpen className="w-16 h-16" />}
          title="No papers found"
          description={
            papers.length === 0
              ? "Upload papers to build your library."
              : "Try adjusting your filters."
          }
          actionLabel="Upload Papers"
          onAction={() => router.push("/upload")}
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-4 py-3 w-10">
                    <Checkbox
                      checked={
                        paginatedPapers.length > 0 &&
                        selectedIds.size === paginatedPapers.length
                      }
                      onCheckedChange={toggleSelectAll}
                      aria-label="Select all"
                    />
                  </th>
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
                  <th className="px-4 py-3 text-left font-medium text-gray-700 hidden md:table-cell">
                    Abstract
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-gray-700">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {paginatedPapers.map((paper) => (
                  <tr
                    key={paper.id}
                    className="hover:bg-gray-50 group"
                  >
                    <td className="px-4 py-3 w-10">
                      <Checkbox
                        checked={selectedIds.has(paper.id)}
                        onCheckedChange={() => toggleSelect(paper.id)}
                        aria-label={`Select ${paper.title}`}
                      />
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <p className="font-medium text-gray-900 truncate">
                        {paper.title}
                      </p>
                    </td>
                    <td className="px-4 py-3 max-w-[140px]">
                      <p className="text-gray-600 truncate">
                        {paper.authors[0]}
                        {paper.authors.length > 1 &&
                          ` +${paper.authors.length - 1}`}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{paper.year}</td>
                    <td className="px-4 py-3">
                      <StatusBadge variant={paper.source} />
                    </td>
                    <td className="px-4 py-3 max-w-sm hidden md:table-cell">
                      <p className="text-xs text-gray-500 truncate">
                        {paper.abstract.slice(0, 120)}
                        {paper.abstract.length > 120 && "..."}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {paper.hasPdf && (
                          <Button
                            variant="ghost"
                            size="icon"
                            asChild
                            title="View PDF"
                          >
                            <a
                              href={getPaperPdfUrl(paper.id)}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <FileText className="w-4 h-4 text-blue-600" />
                              <span className="sr-only">View PDF</span>
                            </a>
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          asChild
                          title="View"
                        >
                          <Link href={`/library/${paper.id}`}>
                            <Eye className="w-4 h-4" />
                            <span className="sr-only">View paper</span>
                          </Link>
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => confirmDelete(paper)}
                          className="text-red-500 hover:text-red-700 hover:bg-red-50"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                          <span className="sr-only">Delete paper</span>
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Pagination */}
      {filteredPapers.length > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-4 text-sm text-gray-600">
          <p>
            Showing {(currentPage - 1) * PAGE_SIZE + 1}–
            {Math.min(currentPage * PAGE_SIZE, filteredPapers.length)} of{" "}
            {filteredPapers.length}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="w-4 h-4" />
              Prev
            </Button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <Button
                key={page}
                variant={page === currentPage ? "default" : "outline"}
                size="sm"
                onClick={() => setCurrentPage(page)}
              >
                {page}
              </Button>
            ))}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Single Delete Dialog */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this paper?</DialogTitle>
            <DialogDescription>
              This will permanently remove &ldquo;{deleteTarget?.title}&rdquo; from your
              library. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Delete Dialog */}
      <Dialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {selectedIds.size} papers?</DialogTitle>
            <DialogDescription>
              This will permanently remove {selectedIds.size} selected papers
              from your library. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleBulkDelete}>
              Delete {selectedIds.size} Papers
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
