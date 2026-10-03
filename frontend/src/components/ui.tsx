import { useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Badge as StatusBadge } from "@/components/ui/badge";
import {
  Alert,
  AlertTitle,
  AlertDescription,
  AlertAction,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton as SkeletonPrimitive } from "@/components/ui/skeleton";
import {
  Empty as EmptyPrimitive,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
  EmptyMedia,
} from "@/components/ui/empty";
import {
  Dialog as DialogPrimitive,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import {
  AlertCircle,
  Check,
  Copy,
  ChevronLeft,
  ChevronRight,
  Database,
  LoaderCircle,
  Plug,
  RefreshCw,
  X,
} from "lucide-react";
import { ApiError } from "../api";
import { useConnection } from "../connection";

export function Eye({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M5 24c10-16 28-16 38 0-10 16-28 16-38 0Z"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle cx="24" cy="24" r="7" fill="currentColor" />
      <path d="M24 4v5m0 30v5" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
export function PageHeading({
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="heading-action">{action}</div>}
    </header>
  );
}
export function Badge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    queued: "排队中",
    claimed: "已领取",
    preparing: "准备中",
    running: "执行中",
    succeeded: "执行成功",
    failed: "执行失败",
    completed: "已完成",
    completed_with_unresolved: "含未解决项",
    cancelled: "已取消",
    cancel_requested: "等待停止确认",
    timed_out: "已超时",
    unknown: "结果未知",
    pass: "通过",
    fail: "未通过",
    insufficient_evidence: "证据不足",
    error: "评分错误",
    skipped: "已跳过",
    not_applicable: "不适用",
    sealed: "已封存",
    partial: "部分证据",
    collecting: "采集中",
    unavailable: "不可用",
    expired: "已过期",
    pending: "待处理",
    ready: "可读取",
  };
  const good = ["succeeded", "completed", "pass", "sealed", "ready"].includes(
    status,
  );
  const bad = ["failed", "fail", "error"].includes(status);
  const warning = [
    "unknown",
    "completed_with_unresolved",
    "insufficient_evidence",
    "partial",
    "cancel_requested",
    "timed_out",
  ].includes(status);
  const active = ["running", "preparing", "claimed", "collecting"].includes(
    status,
  );
  return (
    <StatusBadge
      variant={
        good
          ? "success"
          : bad
            ? "destructive"
            : warning
              ? "warning"
              : active
                ? "active"
                : "secondary"
      }
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {labels[status] || status}
    </StatusBadge>
  );
}
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <Alert variant="destructive" className="mb-4">
      <AlertCircle />
      <AlertTitle>
        {error instanceof Error ? error.message : "数据读取失败"}
      </AlertTitle>
      {error instanceof ApiError && error.details != null && (
        <AlertDescription>
          <details>
            <summary>查看校验详情</summary>
            <pre
              className="max-h-[260px] overflow-auto"
              tabIndex={0}
              aria-label="校验错误详情"
            >
              {JSON.stringify(error.details, null, 2)}
            </pre>
          </details>
        </AlertDescription>
      )}
      {retry && (
        <AlertAction>
          <Button variant="outline" size="sm" onClick={retry}>
            <RefreshCw data-icon="inline-start" />
            重试
          </Button>
        </AlertAction>
      )}
    </Alert>
  );
}
export function Loading({ label = "正在读取数据" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={20} className="spin" />
      {label}
    </div>
  );
}
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <SkeletonPrimitive
      aria-hidden="true"
      className={className || "h-2.5 w-3/4"}
    />
  );
}
export function TableLoading({ label = "正在读取列表" }: { label?: string }) {
  return (
    <div className="table-loading" role="status" aria-label={label}>
      <span className="sr-only">{label}</span>
      <div aria-hidden="true">
        {Array.from({ length: 5 }, (_, row) => (
          <div className="skeleton-row" key={row}>
            <div>
              <Skeleton className="skeleton-title" />
              <Skeleton className="skeleton-detail" />
            </div>
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </div>
        ))}
      </div>
    </div>
  );
}
export function Empty({
  title,
  description,
  action,
  compact = false,
  icon: Icon = Database,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  compact?: boolean;
  icon?: LucideIcon;
}) {
  return (
    <EmptyPrimitive className={cn("py-14", compact && "py-8")}>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      {action && <EmptyContent>{action}</EmptyContent>}
    </EmptyPrimitive>
  );
}
export function Disconnected() {
  const { openConnection } = useConnection();
  return (
    <Empty
      icon={Plug}
      title="连接项目"
      description="输入项目令牌，查看实验和执行记录。"
      action={
        <Button onClick={openConnection}>
          <Plug data-icon="inline-start" />
          连接项目
        </Button>
      }
    />
  );
}
export function Dialog({
  title,
  subtitle,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const returnFocus = useRef(document.activeElement as HTMLElement | null);
  return (
    <DialogPrimitive
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className={cn(
          "console-dialog max-h-[calc(100dvh-2rem)] overflow-y-auto p-0 sm:max-w-[480px]",
          wide && "sm:max-w-[760px]",
        )}
        showCloseButton={false}
        finalFocus={returnFocus}
        initialFocus={() =>
          document.querySelector<HTMLElement>(
            '[data-slot="dialog-content"] [data-autofocus]',
          ) || true
        }
      >
        <div className="console-dialog-header flex items-start justify-between gap-4 border-b px-6 py-5">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {subtitle && <DialogDescription>{subtitle}</DialogDescription>}
          </DialogHeader>
          <DialogClose
            render={
              <Button variant="ghost" size="icon-sm" aria-label="关闭对话框" />
            }
          >
            <X />
          </DialogClose>
        </div>
        {children}
      </DialogContent>
    </DialogPrimitive>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function JsonBlock({
  value,
  title,
}: {
  value: unknown;
  title?: string;
}) {
  const content = value == null ? "暂无记录" : JSON.stringify(value, null, 2);
  const [expanded, setExpanded] = useState(false);
  const [search, setSearch] = useState("");
  const [feedback, setFeedback] = useState("");
  const long = content.length > 900;
  const lines = content.split("\n");
  const matches = search
    ? lines.filter((line) => line.toLowerCase().includes(search.toLowerCase()))
    : lines;
  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setFeedback("已复制完整内容");
    } catch {
      setFeedback("复制失败，请选择内容手动复制");
    }
  }
  return (
    <div
      className={`json-block ${long && !expanded && !search ? "collapsed" : ""}`}
    >
      <div className="json-toolbar">
        <span className="section-label">{title || "JSON 内容"}</span>
        <button
          className="icon-button"
          aria-label={`复制${title || "JSON 内容"}`}
          onClick={() => void copy()}
        >
          <Copy size={14} />
        </button>
      </div>
      {long && (
        <div className="json-search">
          <input
            aria-label={`搜索${title || "JSON 内容"}`}
            type="search"
            placeholder="查找内容，显示匹配行…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && <span>{matches.length} 行匹配</span>}
        </div>
      )}
      <pre tabIndex={0} aria-label={title || "JSON 内容"}>
        {matches.length ? matches.join("\n") : "没有匹配的内容"}
      </pre>
      {long && !search && (
        <button
          className="json-expand"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "收起内容" : `展开完整内容 · ${lines.length} 行`}
        </button>
      )}
      {feedback && (
        <div className="json-feedback" role="status">
          {feedback}
        </div>
      )}
    </div>
  );
}
export function Metrics({
  items,
}: {
  items: { label: string; value: ReactNode; note: string; accent?: boolean }[];
}) {
  return (
    <div className="metrics">
      {items.map((item) => (
        <div
          className={`metric ${item.accent ? "accent" : ""}`}
          key={item.label}
        >
          <span>{item.label}</span>
          <strong>{item.value}</strong>
          <small>{item.note}</small>
        </div>
      ))}
    </div>
  );
}
export function Pagination({
  page,
  next,
  onPage,
}: {
  page: number;
  next: boolean;
  onPage: (page: number) => void;
}) {
  return (
    <div className="pagination">
      <span>第 {page + 1} 页 · 每页 50 条</span>
      <div>
        <Button
          variant="ghost"
          size="icon"
          disabled={page === 0}
          aria-label="上一页"
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          disabled={!next}
          aria-label="下一页"
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight />
        </Button>
      </div>
    </div>
  );
}
export function CheckItem({
  children,
  checked,
  onChange,
}: {
  children: ReactNode;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="check-item">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="check-visual">{checked && <Check size={12} />}</span>
      {children}
    </label>
  );
}
