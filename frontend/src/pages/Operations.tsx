import { formatDate } from "../format";
import { useQuery } from "@tanstack/react-query";
import { Activity, RefreshCw, Server } from "lucide-react";
import { Link } from "react-router-dom";
import { useConnection } from "../connection";
import {
  Disconnected,
  Empty,
  ErrorNotice,
  Loading,
  Metrics,
  PageHeading,
} from "../components/ui";
import type { Operations } from "../types";

export function OperationsPage() {
  const { api } = useConnection();
  const query = useQuery({
    queryKey: ["operations"],
    queryFn: ({ signal }) =>
      api!.request<Operations>("/v1/operations", { signal }),
    enabled: !!api,
    refetchInterval: 10000,
  });
  const ready = useQuery({
    queryKey: ["ready"],
    queryFn: ({ signal }) =>
      api!.request<{ status: string; database_revision: string }>(
        "/health/ready",
        { signal },
      ),
    enabled: !!api,
    refetchInterval: 15000,
  });
  const total = (kind: string, status: string) =>
    query.data
      ? query.data.work_counts
          .filter((w) => w.kind === kind && w.status === status)
          .reduce((n, w) => n + w.count, 0)
      : "—";
  return (
    <>
      <PageHeading
        eyebrow="06 / OPERATIONS"
        title="运行状态"
        description="查看工作队列、后端就绪状态与 Runner 最近一次心跳。"
        action={
          <button
            className="button"
            disabled={!api || query.isFetching}
            onClick={() => {
              void query.refetch();
              void ready.refetch();
            }}
          >
            <RefreshCw size={16} className={query.isFetching ? "spin" : ""} />
            刷新状态
          </button>
        }
      />
      {api && (
        <Metrics
          items={[
            {
              label: "执行工作排队",
              value: total("execute", "queued"),
              note: "等待匹配 Runner",
            },
            {
              label: "已领取执行",
              value: total("execute", "claimed"),
              note: "由 Runner 执行和续租",
              accent: true,
            },
            {
              label: "评分工作排队",
              value: total("score", "queued"),
              note: "使用独立评分容量",
            },
            {
              label: "未知执行工作",
              value: total("execute", "unknown"),
              note: "仍可能占用目标额度",
            },
          ]}
        />
      )}
      {!api ? (
        <section className="panel">
          <Disconnected />
        </section>
      ) : (
        <>
          <div className="service-status">
            <Server size={18} />
            <div>
              <strong>控制 API</strong>
              <small>
                {ready.data
                  ? `数据库迁移 ${ready.data.database_revision}`
                  : ready.error
                    ? "数据库就绪检查未通过"
                    : "正在检查数据库就绪状态"}
              </small>
            </div>
            <span
              className={`service-label ${ready.data ? "good" : "warning"}`}
            >
              {ready.isPending ? "检查中" : ready.error ? "未就绪" : "已就绪"}
            </span>
            {query.data && (
              <time>观测于 {formatDate(query.data.observed_at)}</time>
            )}
          </div>
          {ready.error && (
            <ErrorNotice
              error={ready.error}
              retry={() => void ready.refetch()}
            />
          )}
          <section className="panel">
            <div className="panel-toolbar">
              <div className="toolbar-title">
                <Activity size={17} />
                Runner{" "}
                <span className="count">
                  {query.data?.runners.length ?? "—"}
                </span>
              </div>
              <span className="muted small-text">每 10 秒刷新</span>
            </div>
            {query.isPending ? (
              <Loading />
            ) : query.error ? (
              <ErrorNotice
                error={query.error}
                retry={() => void query.refetch()}
              />
            ) : !query.data.runners.length ? (
              <Empty
                title="还没有注册的 Runner"
                description="在目标宿主机配置 Runner 令牌与插件，启动后会显示最近一次心跳。"
                action={
                  <Link className="button primary" to="/guide">
                    查看 Runner 接入步骤
                  </Link>
                }
              />
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Runner</th>
                      <th>执行适配器</th>
                      <th>评分插件</th>
                      <th>最近心跳</th>
                      <th>注册时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.runners.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <strong>{r.name}</strong>
                          <small className="mono">{r.id.slice(0, 8)}</small>
                        </td>
                        <td>
                          {r.capabilities.adapters?.join(" / ") || "未声明"}
                        </td>
                        <td>
                          {r.capabilities.scorers?.join(" / ") || "未声明"}
                        </td>
                        <td>{formatDate(r.last_seen_at)}</td>
                        <td>{formatDate(r.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <section className="panel work-counts">
            <div className="panel-toolbar">
              <div className="toolbar-title">工作状态分布</div>
            </div>
            {query.isPending ? (
              <Loading />
            ) : query.error ? (
              <div className="panel-content muted">
                工作状态暂不可用，请重试上方请求。
              </div>
            ) : query.data?.work_counts.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>工作类型</th>
                      <th>服务端状态</th>
                      <th>数量</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.work_counts.map((w) => (
                      <tr key={`${w.kind}:${w.status}`}>
                        <td>{w.kind === "execute" ? "执行" : "评分"}</td>
                        <td className="mono">{w.status}</td>
                        <td className="mono">{w.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                compact
                title="暂无工作记录"
                description="创建实验后会生成执行工作，证据满足要求后生成评分工作。"
              />
            )}
          </section>
        </>
      )}
      <div className="notice">
        <p>
          心跳是最近通信时间，不证明 Runner
          此刻在线。租约失效也不证明外部目标已停止；未知工作需核对实际状态。
        </p>
      </div>
    </>
  );
}
