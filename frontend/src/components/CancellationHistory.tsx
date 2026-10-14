import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useConnection } from "../connection";
import { formatDate } from "../format";
import {
  Disconnected,
  Empty,
  ErrorNotice,
  JsonBlock,
  Loading,
  Pagination,
} from "./ui";

type Audit = {
  id: string;
  created_at: string;
  actor_id: string;
  actor_role: string;
  object_kind: string;
  object_id: string;
  parent_id: string | null;
  reason: string | null;
  outcome: string;
  result: unknown;
};
const outcomes: Record<string, string> = {
  processed: "平台已处理请求",
  no_change: "无新增改变",
  already_finished: "对象已结束，保持原结果",
  failed: "处理失败",
  partial_failure: "部分成员处理失败",
};

export function CancellationHistory({
  kind,
  id,
  parent,
}: {
  kind?: string;
  id?: string;
  parent?: string;
}) {
  const { api } = useConnection();
  const [page, setPage] = useState(0);
  const query = useQuery({
    queryKey: ["cancellation-audits", kind, id, parent, page],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({
        limit: "51",
        offset: String(page * 50),
      });
      if (kind) params.set("object_kind", kind);
      if (id) params.set("object_id", id);
      if (parent) params.set("parent_id", parent);
      return api!.request<{ items: Audit[] }>(
        `/v1/cancellation-audits?${params}`,
        { signal },
      );
    },
    enabled: !!api,
    refetchInterval: 10000,
  });
  return (
    <section className="panel panel-content">
      <h2>{parent ? "批次成员处理" : "取消请求审计"}</h2>
      <p className="detail-footnote">
        操作者为经认证的项目凭据；共享凭据无法区分自然人。平台处理记录不能证明
        Agent 已停止，请查看原 Attempt 的停止或核对事实。
      </p>
      {!api ? (
        <Disconnected />
      ) : query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorNotice error={query.error} retry={() => void query.refetch()} />
      ) : !query.data?.items.length ? (
        <Empty
          title="暂无取消请求记录"
          description="首次请求提交后将在此显示。"
        />
      ) : (
        <>
          {query.data.items.slice(0, 50).map((audit) => (
            <article
              key={audit.id}
              className="my-3 space-y-2 rounded-lg border p-4"
            >
              <p>
                {formatDate(audit.created_at)} ·{" "}
                {outcomes[audit.outcome] || audit.outcome}
              </p>
              <p className="break-words">
                凭据 {audit.actor_id} ({audit.actor_role}) · {audit.object_kind}{" "}
                {audit.object_id}
              </p>
              <p className="whitespace-pre-wrap break-words">
                理由：{audit.reason || "未填写"}
              </p>
              {audit.parent_id && (
                <p className="break-words">父请求：{audit.parent_id}</p>
              )}
              <details>
                <summary>处理前后事实</summary>
                <JsonBlock title="平台处理结果" value={audit.result} />
              </details>
              {audit.object_kind === "batch" && <AuditMembers id={audit.id} />}
            </article>
          ))}
          <Pagination
            page={page}
            next={query.data.items.length > 50}
            onPage={setPage}
          />
        </>
      )}
    </section>
  );
}

function AuditMembers({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>查看成员处理</summary>
      {open && <CancellationHistory parent={id} />}
    </details>
  );
}
