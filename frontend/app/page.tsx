"use client";

import { useState, useCallback } from "react";

import {
  FileText,
  Sparkles,
  Loader2,
  AlertCircle,
  ClipboardList,
  Download,
} from "lucide-react";

interface GenerateReportResponse {
  report: string;
}

const API_URL = "http://127.0.0.1:8000/api/generate-report";

const PLACEHOLDER = `Paste your raw notes here…

Example:
- Q3 planning call with product & engineering leads
- Discussed new AI feature set: autocomplete, summarization, report gen
- Budget approved: $120k for tooling, $80k for headcount
- Hiring plan: 2 senior engineers, 1 PM by end of Q3
- Risks: vendor dependency on SuperDocs API, timeline slippage on ML infra
- Next steps: finalize PRD by July 15, kick off sprint on July 22`;

function LoadingSkeleton() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 text-muted-foreground select-none">
      <div className="relative flex items-center justify-center w-16 h-16">
        <span className="absolute inline-flex h-full w-full rounded-full bg-primary/15 animate-ping" />
        <span className="relative inline-flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </span>
      </div>
      <div className="flex flex-col items-center gap-1.5">
        <p className="text-sm font-medium text-foreground">
          Generating report…
        </p>
        <p className="text-xs text-muted-foreground">
          SuperDocs is transforming your notes
        </p>
      </div>
      <div className="w-72 flex flex-col gap-2.5 mt-2">
        {[100, 85, 92, 70, 88].map((w, i) => (
          <div
            key={i}
            className="h-2.5 rounded-full bg-muted animate-pulse"
            style={{ width: `${w}%`, animationDelay: `${i * 120}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-muted-foreground select-none">
      <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-muted border border-border">
        <ClipboardList className="h-6 w-6" />
      </div>
      <div className="flex flex-col items-center gap-1">
        <p className="text-sm font-medium text-foreground">No report yet</p>
        <p className="text-xs text-center max-w-[200px] leading-relaxed">
          Paste your notes on the left and click{" "}
          <span className="font-semibold text-foreground">Generate Report</span>
        </p>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-8 text-center select-none">
      <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-destructive/10 border border-destructive/20">
        <AlertCircle className="h-6 w-6 text-destructive" />
      </div>
      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-foreground">Request failed</p>
        <p className="text-xs text-muted-foreground leading-relaxed max-w-xs">
          {message}
        </p>
      </div>
    </div>
  );
}

function ReportViewer({ content }: { content: string }) {
  return (
    <div className="h-full overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
      <div className="p-8" dangerouslySetInnerHTML={{ __html: content }} />
    </div>
  );
}

const EXPORT_PDF_URL = "http://127.0.0.1:8000/api/export-pdf";

export default function Page() {
  const [rawText, setRawText] = useState<string>("");
  const [report, setReport] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const generateReport = useCallback(async () => {
    if (!rawText.trim()) return;

    setIsLoading(true);
    setError("");
    setReport("");

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: rawText }),
      });

      if (!response.ok) {
        let detail = `Server responded with status ${response.status}.`;
        try {
          const errorData = await response.json();
          if (errorData?.detail) detail = errorData.detail;
        } catch {
          // response body is not JSON — keep the fallback message
        }
        throw new Error(detail);
      }

      const data: GenerateReportResponse = await response.json();
      setReport(data.report ?? "");
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "An unexpected error occurred. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [rawText]);

  const handleDownloadPdf = useCallback(async () => {
    if (!report) return;

    setIsDownloading(true);
    try {
      const res = await fetch(EXPORT_PDF_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ html: report }),
      });

      if (!res.ok) {
        let detail = `Export failed with status ${res.status}.`;
        try {
          const errData = await res.json();
          if (errData?.detail) detail = errData.detail;
        } catch {
          // response body is not JSON — keep the fallback message
        }
        throw new Error(detail);
      }

      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = "SuperDocs_Report.pdf";
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "PDF download failed. Please try again.";
      setError(message);
    } finally {
      setIsDownloading(false);
    }
  }, [report]);

  // Determine what to render in the output panel
  const renderOutput = () => {
    if (isLoading) return <LoadingSkeleton />;
    if (error) return <ErrorState message={error} />;
    if (report) return <ReportViewer content={report} />;
    return <EmptyState />;
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background font-sans antialiased">
      <header className="h-14 shrink-0 flex items-center justify-between px-5 border-b border-border bg-background z-10">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary">
            <FileText className="w-3.5 h-3.5 text-primary-foreground" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-foreground">
            SuperDocs Report Agent
          </span>
        </div>

        <div className="hidden md:flex items-center gap-1 text-xs text-muted-foreground absolute left-1/2 -translate-x-1/2">
          <span>Raw Notes</span>
          <span className="mx-2 text-border">→</span>
          <span>Structured Report</span>
        </div>

        <div className="flex items-center gap-2">
          {report && (
            <button
              id="download-pdf-btn"
              onClick={handleDownloadPdf}
              disabled={isDownloading}
              className="inline-flex items-center gap-2 h-8 px-3.5 rounded-md text-xs font-medium
                         bg-secondary text-secondary-foreground border border-border
                         hover:bg-secondary/80 active:scale-[0.97]
                         disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100
                         transition-all duration-150 select-none"
            >
              {isDownloading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              {isDownloading ? "Downloading…" : "Download PDF"}
            </button>
          )}
          <button
            id="generate-report-btn"
            onClick={generateReport}
            disabled={isLoading || !rawText.trim()}
            className="inline-flex items-center gap-2 h-8 px-3.5 rounded-md text-xs font-medium
                       bg-primary text-primary-foreground
                       hover:bg-primary/90 active:scale-[0.97]
                       disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100
                       transition-all duration-150 select-none"
          >
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            {isLoading ? "Generating…" : "Generate Report"}
          </button>
        </div>
      </header>

      <main className="flex-1 grid grid-cols-2 overflow-hidden">
        <section className="flex flex-col border-r border-border overflow-hidden">
          <div className="shrink-0 flex items-center gap-2 px-5 h-9 border-b border-border bg-muted/40">
            <span className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
              Input
            </span>
            {rawText.trim() && (
              <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                {rawText.length.toLocaleString()} chars
              </span>
            )}
          </div>
          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            placeholder={PLACEHOLDER}
            spellCheck={false}
            className="flex-1 w-full resize-none border-0 rounded-none outline-none ring-0
                       focus:ring-0 focus:outline-none
                       bg-background text-sm text-foreground
                       placeholder:text-muted-foreground/50
                       px-5 py-4 leading-relaxed font-mono"
          />
        </section>

        <section className="flex flex-col overflow-hidden">
          <div className="shrink-0 flex items-center gap-2 px-5 h-9 border-b border-border bg-muted/40">
            <span className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
              Report
            </span>
            {report && !isLoading && (
              <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                {report.length.toLocaleString()} chars
              </span>
            )}
          </div>
          <div className="flex-1 overflow-hidden [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
            {renderOutput()}
          </div>
        </section>
      </main>
    </div>
  );
}
