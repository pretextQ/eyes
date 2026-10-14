import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { ApiError } from "../api";
import { useConnection } from "../connection";
import { Badge } from "./ui/badge";
import { Disconnected, Empty, ErrorNotice, Loading } from "./ui";

type Measurement = {
  scope: string;
  project_id?: string;
  used_bytes?: number | null;
  free_bytes?: number | null;
  total_bytes?: number | null;
  limit_bytes?: number | null;
  minimum_free_bytes?: number | null;
  warning_percent?: number | null;
  measured_at?: string;
  state?: string;
  reason?: string | null;
};
type Capacity = {
  measurements?: Measurement[];
  alerts?: (Measurement & { id: string })[];
};
const scopes = ["project_event_content", "artifact_volume"] as const;
const reasons: Record<string, string> = {
  quota_reached: "已达到逻辑正文额度",
  quota_near_limit: "已接近逻辑正文额度",
  below_minimum_free_bytes: "可用空间低于最低余量",
};
const validNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const bytes = (value: unknown) =>
  validNumber(value) ? `${value.toLocaleString("zh-CN")} B` : "无法确认";
const timestamp = (value?: string) =>
  value && Number.isFinite(Date.parse(value)) ? value : "无法确认";
const reasonText = (value?: string | null) =>
  value === undefined ? "未提供" : value ? reasons[value] || value : "无";

export function CapacityStatus() {
  const { api } = useConnection();
  const [clock, setClock] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 5000);
    return () => window.clearInterval(timer);
  }, []);
  const query = useQuery({
    queryKey: ["capacity"],
    queryFn: ({ signal }) =>
      api!.request<Capacity>("/v1/operations/capacity", { signal }),
    enabled: !!api,
    retry: false,
    refetchInterval: (query) =>
      query.state.error instanceof ApiError &&
      [401, 403].includes(query.state.error.status)
        ? false
        : 15000,
    refetchIntervalInBackground: false,
  });
  const measurements = Array.isArray(query.data?.measurements)
    ? query.data.measurements
    : [];
  const alerts =
    Array.isArray(query.data?.alerts) &&
    query.data.alerts.every(
      (item) =>
        item &&
        typeof item.id === "string" &&
        scopes.some((scope) => scope === item.scope),
    )
      ? query.data.alerts
      : null;
  const denied = query.error instanceof ApiError && query.error.status === 403;
  const stale = clock - query.dataUpdatedAt > 60000;
  return (
    <section className="panel">
      <div className="panel-toolbar flex-wrap gap-3">
        <div className="toolbar-title">容量与当前告警</div>
        <button
          className="button"
          disabled={!api || query.isFetching}
          onClick={() => void query.refetch({ cancelRefetch: false })}
        >
          <RefreshCw size={16} className={query.isFetching ? "spin" : ""} />
          刷新容量
        </button>
      </div>
      <div className="panel-content space-y-4">
        <p className="detail-footnote">
          项目事件正文按 PostgreSQL JSON
          文本字节计量，逻辑额度不等于数据库硬磁盘容量。
          产物卷空间是整个文件系统的用量，包含其他项目或进程。
        </p>
        <p className="muted small-text">
          可见页面每 15 秒刷新；测量超过 60 秒标为过期，无法确认当前状态。
          告警仅在此更新，不重复弹出；额度为 0 表示未启用限制。
        </p>
        {!api ? (
          <Disconnected />
        ) : query.isPending ? (
          <Loading label="正在读取容量" />
        ) : query.error ? (
          <>
            <p>{denied ? "无权限查看容量" : "无法确认当前容量"}</p>
            <p className="detail-footnote">
              {denied
                ? "仅管理令牌可读取本项目用量和共享卷空间。"
                : "读取失败，历史数值不作为当前用量或正常状态。"}
            </p>
            <ErrorNotice
              error={query.error}
              retry={() => void query.refetch({ cancelRefetch: false })}
            />
          </>
        ) : !measurements.length ? (
          <Empty
            compact
            title="没有容量测量，无法确认"
            description="服务端未返回计量数据，请刷新或检查控制 API。"
          />
        ) : (
          <>
            <div className="grid gap-6 md:grid-cols-2">
              {scopes.map((scope) => {
                const matches = measurements.filter(
                  (item) => item?.scope === scope,
                );
                return (
                  <CapacityMeasurement
                    key={scope}
                    scope={scope}
                    measurement={matches.length === 1 ? matches[0] : undefined}
                    stale={stale}
                    clock={clock}
                  />
                );
              })}
            </div>
            <div className="border-t pt-4">
              <h3>当前告警</h3>
              {stale ? (
                <p>测量已过期，无法确认当前告警，请刷新。</p>
              ) : alerts === null ? (
                <p>告警数据缺失，无法确认。</p>
              ) : alerts.some(
                  (alert) =>
                    !alert.measured_at ||
                    !Number.isFinite(Date.parse(alert.measured_at)) ||
                    clock - Date.parse(alert.measured_at) > 60000,
                ) ? (
                <p>告警测量缺失或已过期，无法确认，请刷新。</p>
              ) : alerts.length ? (
                <ul className="space-y-2">
                  {Array.from(
                    new Map(alerts.map((item) => [item.id, item])).values(),
                  ).map((alert) => (
                    <li key={alert.id} className="break-words">
                      {alert.scope === "project_event_content"
                        ? "项目事件正文"
                        : "产物卷"}
                      ：{reasonText(alert.reason)}（{alert.state || "无法确认"}
                      ）
                    </li>
                  ))}
                </ul>
              ) : (
                <p>服务端当前告警集合为空；各项测量状态见上方。</p>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function CapacityMeasurement({
  scope,
  measurement: item,
  stale,
  clock,
}: {
  scope: (typeof scopes)[number];
  measurement?: Measurement;
  stale: boolean;
  clock: number;
}) {
  const event = scope === "project_event_content";
  const limit = event ? item?.limit_bytes : item?.minimum_free_bytes;
  const measured = item?.measured_at ? Date.parse(item.measured_at) : NaN;
  const expired =
    stale || (Number.isFinite(measured) && clock - measured > 60000);
  const complete =
    item &&
    Number.isFinite(measured) &&
    (item.reason === null || typeof item.reason === "string") &&
    validNumber(item.used_bytes) &&
    validNumber(limit) &&
    (event
      ? !!item.project_id &&
        validNumber(item.warning_percent) &&
        item.warning_percent >= 1 &&
        item.warning_percent <= 100
      : validNumber(item.free_bytes) && validNumber(item.total_bytes));
  const state =
    !complete ||
    expired ||
    !["ok", "warning", "blocked"].includes(item?.state || "")
      ? "unknown"
      : item!.state;
  const label =
    state === "unknown"
      ? "无法确认"
      : state === "blocked"
        ? event
          ? "已达额度"
          : "空间不足"
        : state === "warning"
          ? "接近阈值"
          : limit === 0
            ? "未启用限制"
            : "正常";
  const fields = event
    ? [
        ["项目", item?.project_id || "无法确认"],
        ["已保留正文", bytes(item?.used_bytes)],
        ["逻辑正文额度", limit === 0 ? "未启用（0 B）" : bytes(limit)],
        [
          "告警阈值（后端配置）",
          validNumber(item?.warning_percent)
            ? `${item.warning_percent}%`
            : "无法确认",
        ],
      ]
    : [
        ["文件系统已用", bytes(item?.used_bytes)],
        ["实际可用空间", bytes(item?.free_bytes)],
        ["文件系统总量", bytes(item?.total_bytes)],
        ["最低可用余量", limit === 0 ? "未启用（0 B）" : bytes(limit)],
      ];
  return (
    <article className="min-w-0 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3>{event ? "项目事件正文" : "产物卷空间"}</h3>
        <Badge
          variant={
            state === "blocked"
              ? "destructive"
              : state === "unknown" || state === "warning"
                ? "warning"
                : limit === 0
                  ? "secondary"
                  : "success"
          }
        >
          {label}
        </Badge>
      </div>
      {(!complete || expired) && (
        <p className="detail-footnote">
          {expired
            ? "测量已过期，下列为历史读数。"
            : "测量缺失或不完整，无法确认当前状态。"}
        </p>
      )}
      <dl className="space-y-2 text-sm">
        {[
          ...fields,
          [
            "原因",
            !item
              ? "测量缺失"
              : expired
                ? "测量过期"
                : !complete && !item.reason
                  ? "计量字段缺失或无效"
                  : reasonText(item.reason),
          ],
          ["测量时间（含时区）", timestamp(item?.measured_at)],
        ].map(([name, value]) => (
          <div
            key={name}
            className="flex flex-wrap justify-between gap-x-4 gap-y-1"
          >
            <dt className="muted">{name}</dt>
            <dd className="min-w-0 break-all tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      {!event && (
        <p className="detail-footnote">
          空间低于最低余量时由后端判定 blocked，不设额外百分比阈值。
        </p>
      )}
    </article>
  );
}
