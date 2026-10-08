import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  ChevronRight,
  Copy,
  Cpu,
  Plug,
  RefreshCw,
  Terminal,
  Wrench,
} from "lucide-react";
import { useConnection } from "../connection";
import { formatDate, shortId } from "../format";
import {
  Dialog,
  Disconnected,
  Empty,
  ErrorNotice,
  JsonBlock,
  Loading,
  Metrics,
  PageHeading,
  Pagination,
} from "../components/ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ObservationFlow } from "@/components/ObservationFlow";
import {
  eventLabels as labels,
  type ObservationEvent,
} from "@/lib/observation-flow";
import { Input } from "@/components/ui/input";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldDescription,
} from "@/components/ui/field";

type Source = {
  id: string;
  name: string;
  revoked: boolean;
  last_seen_at: string | null;
};
type MetricsData = {
  events?: number;
  turns?: number;
  model_calls?: number;
  tool_calls?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  usage_responses?: number;
  unknown_usage?: number;
  started_at?: string;
  ended_at?: string;
  dropped?: number;
  truncated?: number;
};
type ObservedRun = {
  id: string;
  source_id: string;
  external_id: string;
  session_id: string;
  agent: string;
  model: string;
  capture_body: boolean;
  status: string;
  prompt: string | null;
  created_at: string;
  last_seen_at: string;
  evidence_status: string;
  sequence_gaps: number;
  metrics: MetricsData;
};
type EventContent = ObservationEvent["content"];
type EventRecord = ObservationEvent;
type RunDetail = ObservedRun & { events: EventRecord[]; has_more: boolean };

function Status({ value }: { value: string }) {
  const names: Record<string, string> = {
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    limited: "达到限制",
    cancelled: "已取消",
    disconnected: "观测中断",
    complete: "链路已收齐",
    partial: "链路不完整",
    collecting: "采集中",
  };
  const variant =
    value === "running" || value === "collecting"
      ? "active"
      : value === "completed" || value === "complete"
        ? "success"
        : value === "failed"
          ? "destructive"
          : "warning";
  return <Badge variant={variant}>{names[value] || value}</Badge>;
}

export function ObservationPage() {
  const { api } = useConnection();
  const [setup, setSetup] = useState(false);
  const [params, setParams] = useSearchParams();
  const pageValue = Number(params.get("page"));
  const page =
    Number.isSafeInteger(pageValue) && pageValue >= 0 ? pageValue : 0;
  const source = params.get("source") || "";
  const session = params.get("session") || "";
  const query = useQuery({
    queryKey: ["observed-runs", source, session, page],
    queryFn: ({ signal }) =>
      api!.request<{ items: ObservedRun[] }>(
        `/v1/observation/runs?limit=51&offset=${page * 50}${source ? `&source_id=${encodeURIComponent(source)}` : ""}${session ? `&session_id=${encodeURIComponent(session)}` : ""}`,
        { signal },
      ),
    enabled: !!api,
    refetchInterval: 2000,
  });
  const sources = useQuery({
    queryKey: ["observation-sources"],
    queryFn: ({ signal }) =>
      api!.request<{ items: Source[] }>("/v1/observation/sources?limit=200", {
        signal,
      }),
    enabled: !!api,
    refetchInterval: 10000,
  });
  const rows = query.data?.items.slice(0, 50) || [];
  return (
    <>
      <PageHeading
        eyebrow="OBSERVATION"
        title="Agent 观测"
        description="在 Agent 中照常对话，在这里查看每一次模型与工具调用。"
        action={
          <Button disabled={!api} onClick={() => setSetup(true)}>
            <Plug data-icon="inline-start" />
            接入 Agent
          </Button>
        }
      />
      {!api ? (
        <section className="panel">
          <Disconnected />
        </section>
      ) : (
        <>
          <div className="observation-toolbar">
            <div className="flex flex-wrap items-center gap-2">
              <Activity size={16} />
              <span>{session ? `会话 ${shortId(session)}` : "最近任务"}</span>
              <span className="muted small-text">每 2 秒更新</span>
              {(session || source) && (
                <Button variant="ghost" size="sm" onClick={() => setParams({})}>
                  查看全部
                </Button>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label="刷新观测记录"
              disabled={query.isFetching}
              onClick={() => void query.refetch()}
            >
              <RefreshCw />
            </Button>
          </div>
          {query.error && (
            <ErrorNotice
              error={query.error}
              retry={() => void query.refetch()}
            />
          )}
          {query.isPending ? (
            <Loading label="正在读取 Agent 运行记录" />
          ) : !rows.length && !query.error ? (
            <section className="panel">
              <Empty
                icon={Terminal}
                title="等待 Agent 发来第一条任务"
                description="配置一次接入信息，然后回到 Deta 输入任务。无需测试集、评分器或 Runner。"
                action={
                  <Button onClick={() => setSetup(true)}>
                    <Plug data-icon="inline-start" />
                    接入 Agent
                  </Button>
                }
              />
            </section>
          ) : (
            rows.length > 0 && (
              <section className="observation-runs" aria-label="Agent 任务记录">
                {rows.map((run) => (
                  <article className="observation-run" key={run.id}>
                    <div className="observation-run-main">
                      <Link
                        className="observation-run-title"
                        to={`/observe/${run.id}`}
                      >
                        {run.prompt ||
                          (run.capture_body ? "继续会话" : "任务正文未采集")}
                        <ChevronRight size={16} />
                      </Link>
                      <div className="observation-run-meta">
                        <span>
                          {sources.data?.items.find(
                            (s) => s.id === run.source_id,
                          )?.name || run.agent}
                        </span>
                        <span>{run.model}</span>
                        <button
                          className="text-button"
                          onClick={() =>
                            setParams({
                              source: run.source_id,
                              session: run.session_id,
                            })
                          }
                        >
                          会话 {shortId(run.session_id)}
                        </button>
                        <time>{formatDate(run.created_at)}</time>
                      </div>
                    </div>
                    <div className="observation-run-stats">
                      <span>{run.metrics.turns ?? 0} 轮</span>
                      <span>{run.metrics.tool_calls ?? 0} 次工具</span>
                      <Status value={run.status} />
                      <Status value={run.evidence_status} />
                    </div>
                  </article>
                ))}
                <Pagination
                  page={page}
                  next={(query.data?.items.length || 0) > 50}
                  onPage={(value) => {
                    const next = new URLSearchParams(params);
                    next.set("page", String(value));
                    setParams(next);
                  }}
                />
              </section>
            )
          )}
          <p className="observation-footnote">
            只展示 Agent 实际上报的边界。观测中断不代表任务已停止。
          </p>
        </>
      )}
      {setup && (
        <SourceSetup
          onClose={() => setSetup(false)}
          sources={sources.data?.items || []}
          error={sources.error}
          loading={sources.isPending}
        />
      )}
    </>
  );
}

function SourceSetup({
  onClose,
  sources,
  error,
  loading,
}: {
  onClose: () => void;
  sources: Source[];
  error: Error | null;
  loading: boolean;
}) {
  const { api } = useConnection();
  const client = useQueryClient();
  const [name, setName] = useState("Deta");
  const [created, setCreated] = useState<(Source & { token: string }) | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);
  const config = created
    ? `EYES_OBSERVATION_URL=${window.location.origin}/api\nEYES_OBSERVATION_TOKEN=${created.token}\nEYES_CAPTURE_BODY=true`
    : "";
  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFailure(null);
    try {
      setCreated(
        await api!.post<Source & { token: string }>("/v1/observation/sources", {
          schema_version: "1.0",
          name: name.trim(),
        }),
      );
      await client.invalidateQueries({ queryKey: ["observation-sources"] });
    } catch (e) {
      setFailure(e);
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id: string) {
    setBusy(true);
    setFailure(null);
    try {
      await api!.post(`/v1/observation/sources/${id}/revoke`);
      await client.invalidateQueries({ queryKey: ["observation-sources"] });
    } catch (e) {
      setFailure(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title="观测接入"
      subtitle="Agent 自己执行，Eyes 接收运行链路。"
      onClose={onClose}
      wide
    >
      <div className="observation-setup">
        {failure != null && <ErrorNotice error={failure} />}
        {created ? (
          <>
            <h3>将这三行添加到 Deta 的 .env</h3>
            <p className="muted">
              令牌只显示一次，仅允许上报这个接入的事件。正文采集包含任务、模型输入输出和工具参数；改为
              false 可只采集运行信息。
            </p>
            <pre
              className="observation-config"
              tabIndex={0}
              aria-label="Deta 观测配置"
            >
              {config}
            </pre>
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(config);
                  setCopied(true);
                } catch (e) {
                  setFailure(e);
                }
              }}
            >
              <Copy data-icon="inline-start" />
              {copied ? "已复制" : "复制配置"}
            </Button>
            <p>
              在 Deta 项目中运行 <code>uv run --env-file .env deta</code>
              ，输入任务后回到这里查看。
            </p>
            <Button onClick={onClose}>完成</Button>
          </>
        ) : (
          <>
            <h3>本机自动接入</h3>
            <p>
              启动本机 Eyes 后，在 Deta
              中照常输入任务。首次上报会自动登记，无需创建接入或填写令牌。
            </p>
            <pre className="observation-config">
              uv run --env-file .env deta -i
            </pre>
            <p className="muted">
              默认连接本机 8000 端口；自定义端口只需设置
              EYES_OBSERVATION_URL。其他 Agent 仍需接入事件上报。
            </p>
            <details>
              <summary>远程 Agent 接入</summary>
              <form onSubmit={(event) => void create(event)}>
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor="source-name">Agent 名称</FieldLabel>
                    <Input
                      id="source-name"
                      value={name}
                      maxLength={200}
                      required
                      data-autofocus
                      onChange={(event) => setName(event.target.value)}
                      disabled={busy}
                    />
                    <FieldDescription>
                      Deta 已支持此接入。其他 Agent
                      需实现事件上报，不能仅凭进程地址观测内部调用。
                    </FieldDescription>
                  </Field>
                </FieldGroup>
                <Button type="submit" disabled={busy || !name.trim()}>
                  <Plug data-icon="inline-start" />
                  {busy ? "处理中…" : "生成接入配置"}
                </Button>
              </form>
            </details>
            {error && <ErrorNotice error={error} />}
            {loading ? (
              <Loading label="读取现有接入" />
            ) : (
              sources.length > 0 && (
                <div>
                  <h3>已有接入</h3>
                  {sources.map((source) => (
                    <div className="observation-source" key={source.id}>
                      <div>
                        <strong>{source.name}</strong>
                        <small className="muted">
                          {source.revoked
                            ? "已停用"
                            : source.last_seen_at
                              ? `最近上报 ${formatDate(source.last_seen_at)}`
                              : "等待首次上报"}
                        </small>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={source.revoked || busy}
                        onClick={() => void revoke(source.id)}
                      >
                        停用上报
                      </Button>
                    </div>
                  ))}
                </div>
              )
            )}
          </>
        )}
      </div>
    </Dialog>
  );
}

export function ObservationRunPage() {
  const { id } = useParams();
  const { api } = useConnection();
  const [limit, setLimit] = useState(200);
  const query = useQuery<RunDetail>({
    queryKey: ["observed-run", id, limit],
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === id ? previous : undefined,
    queryFn: async ({ signal }) => {
      let first: RunDetail | undefined;
      const events: EventRecord[] = [];
      for (let offset = 0; offset < limit; offset += 200) {
        const value = await api!.request<RunDetail>(
          `/v1/observation/runs/${id}?limit=200&offset=${offset}`,
          { signal },
        );
        first ??= value;
        events.push(...value.events);
        first.has_more = value.has_more;
        if (!value.has_more) break;
      }
      return { ...first!, events };
    },
    enabled: !!api && !!id,
    refetchInterval: 2000,
  });
  if (!api) return <Disconnected />;
  if (query.isPending) return <Loading label="正在读取执行链路" />;
  if (!query.data)
    return (
      <ErrorNotice error={query.error} retry={() => void query.refetch()} />
    );
  const run = query.data;
  const groups = new Map<number, EventRecord[]>();
  for (const event of run.events) {
    const number = event.content.turn || 0;
    groups.set(number, [...(groups.get(number) || []), event]);
  }
  const elapsed =
    run.metrics.started_at && run.metrics.ended_at
      ? (
          (new Date(run.metrics.ended_at).getTime() -
            new Date(run.metrics.started_at).getTime()) /
          1000
        ).toFixed(1) + " s"
      : "—";
  return (
    <>
      <Link className="back-link" to="/observe">
        <ArrowLeft size={15} />
        全部观测任务
      </Link>
      <PageHeading
        eyebrow="RUN"
        title={run.agent}
        description={`${run.model} · 会话 ${shortId(run.session_id)} · 每 2 秒更新`}
        action={
          <Button
            variant="outline"
            nativeButton={false}
            render={
              <Link
                to={`/observe?source=${run.source_id}&session=${encodeURIComponent(run.session_id)}`}
              />
            }
          >
            查看同一会话
          </Button>
        }
      />
      {query.error && (
        <ErrorNotice error={query.error} retry={() => void query.refetch()} />
      )}
      <div className="observation-status">
        <Status value={run.status} />
        <Status value={run.evidence_status} />
        <span className="muted small-text">
          最近上报 {formatDate(run.last_seen_at)}
        </span>
      </div>
      <Metrics
        items={[
          {
            label: "循环轮次",
            value: run.metrics.turns ?? 0,
            note: "已观察到的轮次开始",
          },
          {
            label: "模型调用",
            value: run.metrics.model_calls ?? 0,
            note: "实际请求尝试，包含重试与摘要",
          },
          {
            label: "工具调用",
            value: run.metrics.tool_calls ?? 0,
            note: "实际进入工具执行的次数",
          },
          {
            label: "任务耗时",
            value: elapsed,
            note: "Agent 开始到结束，不含上传",
          },
        ]}
      />
      {run.evidence_status === "partial" && (
        <div className="notice" role="status">
          <p>
            链路不完整：序号缺口 {run.sequence_gaps}，报告丢失{" "}
            {run.metrics.dropped ?? 0}，截断 {run.metrics.truncated ?? 0}。
            {run.status === "disconnected" &&
              "超过 30 秒未收到活动心跳，无法据此判断 Agent 是否仍在运行。"}
          </p>
        </div>
      )}
      <section className="observation-task" aria-label="本次任务">
        <span className="section-label">用户任务</span>
        <p>
          {run.prompt ||
            (run.capture_body
              ? "继续既有会话，查看下方输入事件。"
              : "未启用正文采集。可在 Deta 设置 EYES_CAPTURE_BODY=true 后开始新任务。")}
        </p>
        <div className="observation-run-meta">
          <span>
            {run.metrics.usage_responses
              ? `${run.metrics.total_tokens?.toLocaleString()} tokens（已报告部分）`
              : "Token 用量未知"}
          </span>
          <span>
            {run.metrics.usage_responses ?? 0} 个响应提供用量 ·{" "}
            {run.metrics.unknown_usage ?? 0} 个请求用量未知
          </span>
        </div>
      </section>
      <div className="observation-chain-heading">
        <h2>执行链路</h2>
        <span className="muted small-text">
          按 Agent 事件序号排列 · {run.metrics.events ?? 0} 条事件
        </span>
      </div>
      {!run.events.length ? (
        <Empty
          title="等待执行事件"
          description="Agent 上报后会自动显示在这里。"
        />
      ) : (
        <ObservationFlow
          key={run.id}
          events={run.events}
          status={run.status}
          evidenceStatus={run.evidence_status}
          hasMore={run.has_more}
          captureBody={run.capture_body}
        >
          <div className="observation-chain">
            {[...groups.entries()].map(([turn, events]) => (
              <section key={turn} className="observation-turn">
                <h3>{turn ? `第 ${turn} 轮` : "任务开始"}</h3>
                <ol>
                  {events.map(({ id: eventId, content: event }) => (
                    <TraceEvent key={eventId} event={event} />
                  ))}
                </ol>
              </section>
            ))}
          </div>
        </ObservationFlow>
      )}
      {run.has_more && (
        <Button
          variant="outline"
          disabled={query.isFetching}
          onClick={() => setLimit(limit + 200)}
        >
          {query.isFetching ? "正在读取事件…" : "加载后续 200 条事件"}
        </Button>
      )}
      <p className="observation-footnote">
        完整性仅针对本接入声明的事件。事件来自 Deta
        埋点；不代表未埋点的外部服务内部过程。
      </p>
    </>
  );
}

function TraceEvent({ event }: { event: EventContent }) {
  const data = event.data;
  const Icon = event.type.startsWith("tool")
    ? Wrench
    : event.type.startsWith("model") || event.type === "message_end"
      ? Cpu
      : Activity;
  const title = labels[event.type] || event.type;
  return (
    <li className="observation-event">
      <Icon size={16} className="observation-event-icon" />
      <details>
        <summary>
          <span className="observation-event-name">
            {title}
            {typeof data.name === "string" && event.type.startsWith("tool")
              ? ` · ${data.name}`
              : ""}
          </span>
          <span className="observation-event-meta">
            {typeof data.duration_ms === "number" && (
              <span>{data.duration_ms.toFixed(0)} ms</span>
            )}
            {typeof data.status === "string" && (
              <span>
                {data.status === "success" || data.status === "UNSET"
                  ? "完成"
                  : data.status}
              </span>
            )}
            {event.truncated && <Badge variant="warning">已截断</Badge>}
            <span>#{event.sequence}</span>
            <ChevronRight size={14} />
          </span>
        </summary>
        <div className="observation-event-body">
          {typeof data.text === "string" && <pre>{data.text}</pre>}
          {typeof data.answer === "string" && data.answer && (
            <pre>{data.answer}</pre>
          )}
          <JsonBlock title="事件数据" value={data} />
          <details className="observation-identifiers">
            <summary>关联标识与发生时间</summary>
            <JsonBlock
              value={{
                occurred_at: event.occurred_at,
                tool_call_id: event.tool_call_id,
                trace_id: event.trace_id,
                span_id: event.span_id,
                parent_span_id: event.parent_span_id,
              }}
            />
          </details>
        </div>
      </details>
    </li>
  );
}
