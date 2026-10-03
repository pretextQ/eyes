import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertCircle,
  ArrowUpRight,
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
import { Link } from "react-router-dom";
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
  eyebrow,
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
        <div className="eyebrow">{eyebrow}</div>
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
    <span
      className={`badge ${good ? "good" : bad ? "bad" : warning ? "warning" : active ? "active" : ""}`}
    >
      <span className="status-dot" />
      {labels[status] || status}
    </span>
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
    <div className="notice error" role="alert">
      <AlertCircle size={17} />
      <div>
        <strong>
          {error instanceof Error ? error.message : "数据读取失败"}
        </strong>
        {error instanceof ApiError && error.details != null && (
          <details>
            <summary>查看校验详情</summary>
            <pre>{JSON.stringify(error.details, null, 2)}</pre>
          </details>
        )}
      </div>
      {retry && (
        <button className="button small" onClick={retry}>
          <RefreshCw size={14} />
          重试
        </button>
      )}
    </div>
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
export function Empty({
  title,
  description,
  action,
  compact = false,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={`empty ${compact ? "compact" : ""}`}>
      <div className="empty-glyph">
        <Database size={24} strokeWidth={1.3} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function Disconnected() {
  const { openConnection } = useConnection();
  return (
    <Empty
      title="连接你的实验空间"
      description="使用项目令牌连接控制 API，读取真实实验与执行证据。"
      action={
        <button className="button primary" onClick={openConnection}>
          <Plug size={16} />
          连接后端
          <ArrowUpRight size={16} />
        </button>
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
  const titleId = useId();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog?.showModal();
    return () => {
      dialog?.close();
      document.body.style.overflow = overflow;
    };
  }, []);
  return (
    <dialog
      aria-labelledby={titleId}
      ref={ref}
      className={`dialog ${wide ? "wide" : ""}`}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="dialog-heading">
        <div>
          <div className="eyebrow">EYES / WORKSPACE</div>
          <h2 id={titleId}>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="关闭对话框"
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
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
        <button
          className="icon-button"
          disabled={page === 0}
          aria-label="上一页"
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft size={16} />
        </button>
        <button
          className="icon-button"
          disabled={!next}
          aria-label="下一页"
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
export function SetupSteps() {
  return (
    <div className="setup-steps">
      <div className="section-label">从接入到结果</div>
      {[
        {
          n: "01",
          title: "接入目标 Agent",
          text: "声明接入方式与观测范围",
          url: "/targets",
        },
        {
          n: "02",
          title: "准备测试与评分",
          text: "发布不可变的用例和口径",
          url: "/datasets",
        },
        {
          n: "03",
          title: "运行并审阅证据",
          text: "从用例结果追溯执行过程",
          url: "/experiments",
        },
      ].map((s) => (
        <Link key={s.n} to={s.url}>
          <span className="step-number">{s.n}</span>
          <div>
            <strong>{s.title}</strong>
            <small>{s.text}</small>
          </div>
          <ArrowUpRight size={16} />
        </Link>
      ))}
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
