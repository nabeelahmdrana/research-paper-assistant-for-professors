"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Upload, Search, FileText, Clock, BarChart3, Zap, Globe } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { SkeletonCard } from "@/components/SkeletonCard";
import type { Paper, QueryResult, DbStats, CacheStats } from "@/lib/types";
import { getDbStats, listQueryResults, listPapers, getCacheStats } from "@/lib/api";

function formatRelativeTime(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffHours < 1) return "Just now";
  if (diffHours < 24) return `${diffHours} hrs ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return `${Math.floor(diffDays / 7)}w ago`;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DbStats | null>(null);
  const [recentQueries, setRecentQueries] = useState<QueryResult[]>([]);
  const [totalQueries, setTotalQueries] = useState(0);
  const [recentPapers, setRecentPapers] = useState<Paper[]>([]);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [cacheStatsLoading, setCacheStatsLoading] = useState(true);

  useEffect(() => {
    getDbStats().then((r) => r.data && setStats(r.data));
    listQueryResults().then((r) => {
      if (r.data) {
        setRecentQueries(r.data.results.slice(0, 5));
        setTotalQueries(r.data.total);
      }
    });
    listPapers().then((r) => {
      if (r.data) {
        const sorted = [...r.data.papers].sort(
          (a, b) => new Date(b.dateAdded).getTime() - new Date(a.dateAdded).getTime()
        );
        setRecentPapers(sorted.slice(0, 5));
      }
    });
    getCacheStats()
      .then((data) => setCacheStats(data))
      .catch(() => { /* silent — don't crash dashboard */ })
      .finally(() => setCacheStatsLoading(false));
  }, []);

  const lastActivity: string = (() => {
    const latest = [
      ...recentPapers.map((p) => p.dateAdded),
      ...recentQueries.map((q) => q.createdAt),
    ].sort().at(-1);
    return latest ? formatRelativeTime(latest) : "—";
  })();

  return (
    <div>
      <PageHeader
        title="Research Paper Assistant"
        subtitle="Your local-first academic research tool"
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
        <Card>
          <CardContent className="p-6">
            <p className="text-3xl font-bold text-blue-600">
              {stats?.paperCount ?? 0}
            </p>
            <p className="text-sm text-gray-500 mt-1 flex items-center gap-1">
              <FileText className="w-3 h-3" /> Total Papers
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-3xl font-bold text-blue-600">
              {totalQueries}
            </p>
            <p className="text-sm text-gray-500 mt-1 flex items-center gap-1">
              <Search className="w-3 h-3" /> Queries Run
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-3xl font-bold text-blue-600">
              {stats?.dbSizeMB ?? 0} MB
            </p>
            <p className="text-sm text-gray-500 mt-1">DB Size</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-2xl font-bold text-blue-600">{lastActivity}</p>
            <p className="text-sm text-gray-500 mt-1 flex items-center gap-1">
              <Clock className="w-3 h-3" /> Last Activity
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Recent Queries */}
        <Card>
          <CardContent className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Recent Queries
            </h2>
            <div className="space-y-0">
              {recentQueries.map((query, idx) => (
                <div key={query.id}>
                  <div className="flex items-start justify-between py-3">
                    <div className="flex-1 min-w-0 pr-4">
                      <p className="text-sm text-gray-700 truncate">
                        {query.question.length > 60
                          ? `${query.question.slice(0, 60)}...`
                          : query.question}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {formatRelativeTime(query.createdAt)}
                      </p>
                    </div>
                    <Link
                      href={`/results/${query.id}`}
                      className="text-xs text-blue-600 hover:underline whitespace-nowrap shrink-0"
                    >
                      View &rarr;
                    </Link>
                  </div>
                  {idx < recentQueries.length - 1 && <Separator />}
                </div>
              ))}
              {recentQueries.length === 0 && (
                <p className="text-sm text-gray-500 py-3">No recent queries.</p>
              )}
            </div>
            <div className="mt-3 pt-3 border-t border-gray-100">
              <Link
                href="/query"
                className="text-xs text-blue-600 hover:underline"
              >
                View all queries &rarr;
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Recently Added Papers */}
        <Card>
          <CardContent className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Recently Added Papers
            </h2>
            <div className="space-y-0">
              {recentPapers.map((paper, idx) => (
                <div key={paper.id}>
                  <div className="flex items-start justify-between py-3">
                    <div className="flex-1 min-w-0 pr-4">
                      <div className="flex items-center gap-2 mb-1">
                        <StatusBadge variant={paper.source} />
                        <p className="text-sm font-medium text-gray-700 truncate">
                          {paper.title.length > 40
                            ? `${paper.title.slice(0, 40)}...`
                            : paper.title}
                        </p>
                      </div>
                      <p className="text-xs text-gray-500">
                        {paper.authors[0]} et al. {paper.year} &nbsp;&middot;&nbsp;{" "}
                        {formatRelativeTime(paper.dateAdded)}
                      </p>
                    </div>
                  </div>
                  {idx < recentPapers.length - 1 && <Separator />}
                </div>
              ))}
              {recentPapers.length === 0 && (
                <p className="text-sm text-gray-500 py-3">No papers added yet.</p>
              )}
            </div>
            <div className="mt-3 pt-3 border-t border-gray-100">
              <Link
                href="/library"
                className="text-xs text-blue-600 hover:underline"
              >
                View all papers &rarr;
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardContent className="p-6 flex flex-col items-center text-center">
            <Upload className="w-12 h-12 text-blue-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Upload Papers
            </h3>
            <p className="text-sm text-gray-500 mb-6">
              Add PDFs or DOIs to your local library
            </p>
            <Button variant="outline" asChild>
              <Link href="/upload">Go to Upload &rarr;</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6 flex flex-col items-center text-center">
            <Search className="w-12 h-12 text-blue-600 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Start Research
            </h3>
            <p className="text-sm text-gray-500 mb-6">
              Ask a question across your paper library
            </p>
            <Button variant="outline" asChild>
              <Link href="/query">Go to Query &rarr;</Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Cache Statistics */}
      {cacheStatsLoading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}
      {!cacheStatsLoading && cacheStats && cacheStats.total_queries > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Pipeline Statistics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardContent className="p-6">
                <p className="text-3xl font-bold text-blue-600">
                  {Math.round(cacheStats.cache_hit_rate * 100)}%
                </p>
                <p className="text-sm text-gray-500 mt-1 flex items-center gap-1">
                  <Zap className="w-3 h-3" /> Cache Hit Rate
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <p className="text-3xl font-bold text-blue-600">
                  {Math.round(cacheStats.avg_confidence * 100)}%
                </p>
                <p className="text-sm text-gray-500 mt-1 flex items-center gap-1">
                  <BarChart3 className="w-3 h-3" /> Avg Confidence
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <p className="text-3xl font-bold text-blue-600">
                  {Math.round(cacheStats.external_usage_ratio * 100)}%
                </p>
                <p className="text-sm text-gray-500 mt-1 flex items-center gap-1">
                  <Globe className="w-3 h-3" /> External Usage
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
