import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { ArrowLeft, ArrowUpRight, Plus, Square, Trash2 } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Badge,
  CheckItem,
  Dialog,
  Disconnected,
  Empty,
  ErrorNotice,
  Loading,
  Metrics,
  PageHeading,
  Pagination,
} from "../components/ui";
import { useConnection } from "../connection";
import { formatDate, shortId } from "../format";
import type { Experiment, ExperimentRequest, TargetContent } from "../types";

type BatchItem = {
  id: string;
  name: string;
  created_at: string;
  status: string;
  agent_count: number;
  requested_concurrency: number;
};
type Batch = Omit<BatchItem, "agent_count" | "requested_concurrency"> & {
  members: (Experiment & {
    dataset_name: string;
    progress: {
      planned: number;
      states: Record<string, number>;
      reserved: number;
    };
  })[];
};
const terminal = (status: string) =>
  ["completed", "completed_with_unresolved"].includes(status);

export function BatchesPage() {
  const { api } = useConnection();
  const [createOpen, setCreateOpen] = useState(false);
  const [params, setParams] = useSearchParams();
  const pageValue = Number(params.get("page"));
  const page =
    Number.isSafeInteger(pageValue) && pageValue >= 0 ? pageValue : 0;
  const query = useQuery({
    queryKey: ["batches", page],
    queryFn: ({ signal }) =>
      api!.request<{ items: BatchItem[] }>(
        `/v1/experiment-batches?limit=51&offset=${page * 50}`,
        { signal },
      ),
    enabled: !!api,
    refetchInterval: 10000,
  });
  const items = query.data?.items.slice(0, 50) || [];
  return (
    <>
      <PageHeading
        eyebrow=""
        title="多 Agent 批次"
        description="一次安排多个 Agent，各自执行测试集，集中跟踪任务进度。"
        action={
          api && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus data-icon="inline-start" />
              创建批次
            </Button>
          )
        }
      />
      {!api ? (
        <Disconnected />
      ) : query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorNotice error={query.error} retry={() => void query.refetch()} />
      ) : !items.length ? (
        <Empty
          title="还没有多 Agent 批次"
          description="为每个 Agent 选择测试集、评分口径和任务并发数，一次提交所有任务。"
          action={<Button onClick={() => setCreateOpen(true)}>创建批次</Button>}
        />
      ) : (
        <>
          <Table
            containerProps={{
              tabIndex: 0,
              "aria-label": "批次列表，可横向滚动",
            }}
          >
            <TableHeader>
              <TableRow>
                <TableHead>批次</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>Agent 数</TableHead>
                <TableHead>申请任务并发</TableHead>
                <TableHead>创建时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <Link className="batch-link" to={`/batches/${item.id}`}>
                      {item.name}
                      <ArrowUpRight size={14} />
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge status={item.status} />
                  </TableCell>
                  <TableCell>{item.agent_count}</TableCell>
                  <TableCell>{item.requested_concurrency}</TableCell>
                  <TableCell>{formatDate(item.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={page}
            next={(query.data?.items.length || 0) > 50}
            onPage={(value) => setParams(value ? { page: String(value) } : {})}
          />
        </>
      )}
      {createOpen && <CreateBatch onClose={() => setCreateOpen(false)} />}
    </>
  );
}

export function BatchPage() {
  const { id } = useParams();
  return <BatchView key={id} id={id!} />;
}
function BatchView({ id }: { id: string }) {
  const { api } = useConnection();
  const client = useQueryClient();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const query = useQuery({
    queryKey: ["batch", id],
    queryFn: ({ signal }) =>
      api!.request<Batch>(`/v1/experiment-batches/${id}`, { signal }),
    enabled: !!api,
    refetchInterval: 5000,
  });
  const data = query.data;
  async function cancel() {
    if (!api) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<Batch>(
        `/v1/experiment-batches/${id}/cancel`,
      );
      client.setQueryData(["batch", id], result);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["batches"] }),
        client.invalidateQueries({ queryKey: ["experiments"] }),
        client.invalidateQueries({ queryKey: ["operations"] }),
      ]);
      setCancelOpen(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back-link" to="/batches">
        <ArrowLeft size={15} />
        全部批次
      </Link>
      <PageHeading
        eyebrow=""
        title={data?.name || "批次详情"}
        description={
          data
            ? `${shortId(id)} · ${formatDate(data.created_at)} · 每 5 秒更新`
            : "查看各 Agent 的任务执行和证据。"
        }
        action={
          data &&
          !terminal(data.status) && (
            <Button
              variant="outline"
              disabled={data.status === "cancel_requested"}
              onClick={() => setCancelOpen(true)}
            >
              <Square data-icon="inline-start" />
              {data.status === "cancel_requested"
                ? "等待停止确认"
                : "取消整个批次"}
            </Button>
          )
        }
      />
      {!api ? (
        <Disconnected />
      ) : query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorNotice error={query.error} retry={() => void query.refetch()} />
      ) : (
        data && (
          <>
            <div className="flex flex-wrap items-center gap-3 pb-5">
              <Badge status={data.status} />
              <p className="text-sm text-muted-foreground">
                各 Agent 独立调度；申请并发受目标、项目、全局额度及 Runner
                可用槽位约束。
              </p>
            </div>
            <Metrics
              items={[
                {
                  label: "Agent 数",
                  value: data.members.length,
                  note: "每个成员保留独立实验",
                },
                {
                  label: "计划任务",
                  value: data.members.reduce(
                    (n, m) => n + m.progress.planned,
                    0,
                  ),
                  note: "用例数 × 各自重复次数",
                },
                {
                  label: "执行成功",
                  value: data.members.reduce(
                    (n, m) => n + (m.progress.states.succeeded || 0),
                    0,
                  ),
                  note: "质量结论请查看成员评分",
                },
                {
                  label: "已预留 / 申请并发",
                  value: `${data.members.reduce((n, m) => n + m.progress.reserved, 0)} / ${data.members.reduce((n, m) => n + m.snapshot.request.concurrency, 0)}`,
                  note: "未知执行仍可能占用额度",
                },
              ]}
            />
            <Table
              containerProps={{
                tabIndex: 0,
                "aria-label": "Agent 任务进度，可横向滚动",
              }}
            >
              <TableHeader>
                <TableRow>
                  <TableHead>Agent / 测试集</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>执行成功 / 计划</TableHead>
                  <TableHead>排队 / 运行 / 未知</TableHead>
                  <TableHead>任务并发</TableHead>
                  <TableHead>证据与评分</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.members.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell>
                      <strong>{member.snapshot.target.content.name}</strong>
                      <div className="text-xs text-muted-foreground">
                        {member.snapshot.target.content.external_version ||
                          "外部版本未知"}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {member.dataset_name} ·{" "}
                        {member.snapshot.request.repetitions} 次重复
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge status={member.status} />
                    </TableCell>
                    <TableCell>
                      {member.progress.states.succeeded || 0} /{" "}
                      {member.progress.planned}
                      <div className="text-xs text-muted-foreground">
                        失败 / 超时{" "}
                        {(member.progress.states.failed || 0) +
                          (member.progress.states.timed_out || 0)}{" "}
                        · 取消 {member.progress.states.cancelled || 0}
                      </div>
                    </TableCell>
                    <TableCell>
                      {member.progress.states.queued || 0} /{" "}
                      {member.progress.states.running || 0} /{" "}
                      {member.progress.states.unknown || 0}
                    </TableCell>
                    <TableCell>{member.snapshot.request.concurrency}</TableCell>
                    <TableCell>
                      <Link
                        className={buttonVariants({
                          variant: "outline",
                          size: "sm",
                        })}
                        to={`/experiments/${member.id}`}
                      >
                        查看任务
                        <ArrowUpRight data-icon="inline-end" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-4 text-sm text-muted-foreground">
              已完成表示调度结束，不代表任务成功或评分通过。不同测试集或评分口径的结果分别展示。进入成员实验可查看评分结果和每次执行证据，也可单独取消该
              Agent。
            </p>
          </>
        )
      )}
      {cancelOpen && (
        <Dialog
          title="取消整个批次"
          subtitle="停止派发未开始的任务，并向执行中的 Agent 请求停止。未确认停止的任务仍保留额度。"
          onClose={() => {
            if (!busy) setCancelOpen(false);
          }}
        >
          <div className="form">
            {error != null && <ErrorNotice error={error} />}
            <div className="form-actions">
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => setCancelOpen(false)}
              >
                返回
              </Button>
              <Button
                variant="destructive"
                disabled={busy}
                onClick={() => void cancel()}
              >
                {busy ? "正在请求…" : "确认请求取消"}
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </>
  );
}

type Draft = ExperimentRequest & { key: string };
const newDraft = (): Draft => ({
  key: crypto.randomUUID(),
  target_version_id: "",
  dataset_version_id: "",
  scorer_version_ids: [],
  concurrency: 1,
  timeout_seconds: 300,
  repetitions: 1,
  attempt_selection: "first_success",
});
function CreateBatch({ onClose }: { onClose: () => void }) {
  const { api } = useConnection();
  const navigate = useNavigate();
  const client = useQueryClient();
  const targets = useQuery({
    queryKey: ["catalog", "targets"],
    queryFn: ({ signal }) => api!.catalog("targets", signal),
    enabled: !!api,
  });
  const datasets = useQuery({
    queryKey: ["catalog", "datasets"],
    queryFn: ({ signal }) => api!.catalog("datasets", signal),
    enabled: !!api,
  });
  const scorers = useQuery({
    queryKey: ["catalog", "scorers"],
    queryFn: ({ signal }) => api!.catalog("scorers", signal),
    enabled: !!api,
  });
  const [name, setName] = useState("");
  const [members, setMembers] = useState<Draft[]>(() => [
    newDraft(),
    newDraft(),
  ]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [requestKey, setRequestKey] = useState<{
    body: string;
    key: string;
  } | null>(null);
  function update(key: string, patch: Partial<Draft>) {
    setMembers((values) =>
      values.map((member) =>
        member.key === key ? { ...member, ...patch } : member,
      ),
    );
  }
  const valid =
    !!name.trim() &&
    members.every(
      (member) =>
        member.target_version_id &&
        member.dataset_version_id &&
        member.scorer_version_ids.length,
    );
  async function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!api || !valid || busy) return;
    setBusy(true);
    setError(null);
    const body = {
      name: name.trim(),
      experiments: members.map((member) => ({
        target_version_id: member.target_version_id,
        dataset_version_id: member.dataset_version_id,
        scorer_version_ids: member.scorer_version_ids,
        concurrency: member.concurrency,
        timeout_seconds: member.timeout_seconds,
        repetitions: member.repetitions,
        attempt_selection: member.attempt_selection,
      })),
    };
    const serialized = JSON.stringify(body);
    const key =
      requestKey?.body === serialized ? requestKey.key : crypto.randomUUID();
    setRequestKey({ body: serialized, key });
    try {
      const result = await api.post<Batch>("/v1/experiment-batches", body, {
        "Idempotency-Key": key,
      });
      await Promise.all([
        client.invalidateQueries({ queryKey: ["batches"] }),
        client.invalidateQueries({ queryKey: ["experiments"] }),
        client.invalidateQueries({ queryKey: ["operations"] }),
      ]);
      onClose();
      navigate(`/batches/${result.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const ready =
    targets.data?.length && datasets.data?.length && scorers.data?.length;
  return (
    <Dialog
      title="创建多 Agent 批次"
      subtitle="为每个 Agent 单独配置任务，所有成员一次入队。"
      wide
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      {!api ? (
        <Disconnected />
      ) : targets.isPending || datasets.isPending || scorers.isPending ? (
        <Loading />
      ) : targets.error || datasets.error || scorers.error ? (
        <ErrorNotice
          error={targets.error || datasets.error || scorers.error}
          retry={() => {
            void targets.refetch();
            void datasets.refetch();
            void scorers.refetch();
          }}
        />
      ) : !ready ? (
        <Empty
          title="先准备 Agent、测试集和评分口径"
          description="发布所需版本后，再创建批次。"
          action={
            <Link
              className={buttonVariants({ variant: "outline" })}
              to="/targets"
              onClick={onClose}
            >
              配置目标 Agent
            </Link>
          }
        />
      ) : (
        <form className="form batch-form" onSubmit={submit}>
          <FieldSet disabled={busy}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="batch-name">批次名称</FieldLabel>
                <Input
                  id="batch-name"
                  data-autofocus
                  required
                  maxLength={200}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="例如：编码与检索 Agent 验收"
                />
              </Field>
            </FieldGroup>
            {members.map((member, index) => {
              const target = targets.data?.find(
                (item) => item.id === member.target_version_id,
              )?.content as unknown as TargetContent | undefined;
              return (
                <FieldSet className="batch-member" key={member.key}>
                  <FieldLegend>Agent {index + 1}</FieldLegend>
                  <FieldGroup>
                    <FieldGroup className="batch-fields">
                      <Field>
                        <FieldLabel htmlFor={`${member.key}-target`}>
                          目标版本
                        </FieldLabel>
                        <select
                          id={`${member.key}-target`}
                          required
                          value={member.target_version_id}
                          onChange={(e) =>
                            update(member.key, {
                              target_version_id: e.target.value,
                              concurrency: 1,
                            })
                          }
                        >
                          <option value="">选择 Agent 版本</option>
                          {targets.data?.map((item) => (
                            <option
                              key={item.id}
                              value={item.id}
                              disabled={members.some(
                                (other) =>
                                  other.key !== member.key &&
                                  other.target_version_id === item.id,
                              )}
                            >
                              {item.name} ·{" "}
                              {String(
                                item.content.external_version ||
                                  item.digest.slice(0, 8),
                              )}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field>
                        <FieldLabel htmlFor={`${member.key}-dataset`}>
                          测试集
                        </FieldLabel>
                        <select
                          id={`${member.key}-dataset`}
                          required
                          value={member.dataset_version_id}
                          onChange={(e) =>
                            update(member.key, {
                              dataset_version_id: e.target.value,
                            })
                          }
                        >
                          <option value="">选择测试集版本</option>
                          {datasets.data?.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name} · {item.digest.slice(0, 8)}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </FieldGroup>
                    <FieldSet>
                      <FieldLegend variant="label">
                        评分口径（至少一项）
                      </FieldLegend>
                      <div className="batch-scorers">
                        {scorers.data?.map((item) => (
                          <CheckItem
                            key={item.id}
                            checked={member.scorer_version_ids.includes(
                              item.id,
                            )}
                            onChange={(checked) =>
                              update(member.key, {
                                scorer_version_ids: checked
                                  ? [...member.scorer_version_ids, item.id]
                                  : member.scorer_version_ids.filter(
                                      (id) => id !== item.id,
                                    ),
                              })
                            }
                          >
                            {item.name} · {item.digest.slice(0, 8)}
                          </CheckItem>
                        ))}
                      </div>
                    </FieldSet>
                    <FieldGroup className="batch-fields three">
                      <Field>
                        <FieldLabel htmlFor={`${member.key}-concurrency`}>
                          任务并发数
                        </FieldLabel>
                        <Input
                          id={`${member.key}-concurrency`}
                          required
                          type="number"
                          min={1}
                          max={target?.concurrency_limit || 1}
                          value={member.concurrency}
                          onChange={(e) =>
                            update(member.key, {
                              concurrency: Number(e.target.value),
                            })
                          }
                        />
                        <FieldDescription>
                          {target
                            ? `目标共享容量 ${target.concurrency_limit}`
                            : "选择目标后设置"}
                        </FieldDescription>
                      </Field>
                      <Field>
                        <FieldLabel htmlFor={`${member.key}-timeout`}>
                          单任务超时 / 秒
                        </FieldLabel>
                        <Input
                          id={`${member.key}-timeout`}
                          required
                          type="number"
                          min={1}
                          max={86400}
                          value={member.timeout_seconds}
                          onChange={(e) =>
                            update(member.key, {
                              timeout_seconds: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                      <Field>
                        <FieldLabel htmlFor={`${member.key}-repetitions`}>
                          每用例重复次数
                        </FieldLabel>
                        <Input
                          id={`${member.key}-repetitions`}
                          required
                          type="number"
                          min={1}
                          max={100}
                          value={member.repetitions}
                          onChange={(e) =>
                            update(member.key, {
                              repetitions: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                    </FieldGroup>
                  </FieldGroup>
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={members.length === 1 || busy}
                      onClick={() =>
                        setMembers((values) =>
                          values.filter((value) => value.key !== member.key),
                        )
                      }
                      aria-label={`移除 Agent ${index + 1}`}
                    >
                      <Trash2 data-icon="inline-start" />
                      移除
                    </Button>
                  </div>
                </FieldSet>
              );
            })}
            <Button
              type="button"
              variant="outline"
              disabled={
                busy ||
                members.length >= Math.min(32, targets.data?.length || 0)
              }
              onClick={() => setMembers((values) => [...values, newDraft()])}
            >
              <Plus data-icon="inline-start" />
              添加 Agent
            </Button>
            <FieldDescription>
              {members.length} 个 Agent · 合计申请{" "}
              {members.reduce((n, member) => n + member.concurrency, 0)}{" "}
              个任务并发。实际并发受共享容量和 Runner
              槽位限制；环境未隔离的目标最多同时执行 1 个任务。
            </FieldDescription>
          </FieldSet>
          {error != null && <ErrorNotice error={error} />}
          <div className="form-actions">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={onClose}
            >
              取消
            </Button>
            <Button type="submit" disabled={busy || !valid}>
              {busy ? "正在创建…" : "创建批次并入队"}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
