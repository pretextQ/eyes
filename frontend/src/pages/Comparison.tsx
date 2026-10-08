import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";
import { useConnection } from "../connection";
import {
  Disconnected,
  Empty,
  ErrorNotice,
  PageHeading,
  Pagination,
  TableLoading,
} from "../components/ui";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDate, shortId } from "../format";
import type { ComparisonReport } from "@/lib/comparison";
import { ComparisonCreate } from "@/components/ComparisonCreate";
import { ComparisonReportView, GateBadge } from "@/components/ComparisonReport";

export function ComparisonPage() {
  const { api } = useConnection();
  const [params, setParams] = useSearchParams();
  const reportId = params.get("report") || "";
  const sourceId = params.get("source") || "";
  const creating =
    params.get("new") === "1" || (!reportId && !!params.get("baseline"));
  const value = Number(params.get("page"));
  const page = Number.isSafeInteger(value) && value >= 0 ? value : 0;
  const reports = useQuery({
    queryKey: ["comparison-reports", page],
    queryFn: ({ signal }) =>
      api!.request<{ items: ComparisonReport[] }>(
        `/v1/comparisons?limit=51&offset=${page * 50}`,
        { signal },
      ),
    enabled: !!api && !reportId && !creating,
  });
  const report = useQuery({
    queryKey: ["comparison-report", reportId],
    queryFn: ({ signal }) =>
      api!.request<ComparisonReport>(`/v1/comparisons/${reportId}`, { signal }),
    enabled: !!api && !!reportId,
  });
  const source = useQuery({
    queryKey: ["comparison-report", sourceId],
    queryFn: ({ signal }) =>
      api!.request<ComparisonReport>(`/v1/comparisons/${sourceId}`, { signal }),
    enabled: !!api && creating && !!sourceId,
  });
  return (
    <>
      <PageHeading
        eyebrow="COMPARISON"
        title="回归报告"
        description="固定比较口径与执行证据，查看改善、退化和发布门槛。"
        action={
          !creating && (
            <Link className={buttonVariants()} to="/comparison?new=1">
              <Plus data-icon="inline-start" />
              新建回归报告
            </Link>
          )
        }
      />
      {!api ? (
        <section className="panel">
          <Disconnected />
        </section>
      ) : reportId ? (
        <>
          <Link className="back-link" to="/comparison">
            返回报告列表
          </Link>
          {report.isPending ? (
            <TableLoading label="正在读取固定回归报告" />
          ) : report.error ? (
            <ErrorNotice
              error={report.error}
              retry={() => void report.refetch()}
            />
          ) : (
            <ComparisonReportView key={reportId} report={report.data} />
          )}
        </>
      ) : creating ? (
        <>
          <Link className="back-link" to="/comparison">
            返回报告列表
          </Link>
          {sourceId && source.isPending ? (
            <TableLoading label="正在读取原报告配置" />
          ) : sourceId && source.error ? (
            <ErrorNotice
              error={source.error}
              retry={() => void source.refetch()}
            />
          ) : (
            <ComparisonCreate
              key={`${sourceId}:${params.get("baseline")}:${params.get("candidate")}`}
              initialBaseline={
                source.data?.baseline_id || params.get("baseline") || ""
              }
              initialCandidate={
                source.data?.candidate_id || params.get("candidate") || ""
              }
              initialRequest={
                sourceId ? source.data?.content.request : undefined
              }
              onCreated={(id) => setParams({ report: id })}
            />
          )}
        </>
      ) : (
        <section className="panel">
          <div className="panel-toolbar">
            <h2 className="toolbar-title">已保存的报告</h2>
            <Button
              variant="ghost"
              size="sm"
              disabled={reports.isFetching}
              onClick={() => void reports.refetch()}
            >
              <RefreshCw data-icon="inline-start" />
              刷新
            </Button>
          </div>
          {reports.isPending ? (
            <TableLoading />
          ) : reports.error ? (
            <ErrorNotice
              error={reports.error}
              retry={() => void reports.refetch()}
            />
          ) : !reports.data.items.length ? (
            <Empty
              title={page ? "本页没有报告" : "保存一次可追溯的回归比较"}
              description="选择基线与候选实验，确认评分口径和门槛。报告生成后保持不变。"
              action={
                <Link className={buttonVariants()} to="/comparison?new=1">
                  新建回归报告
                </Link>
              }
            />
          ) : (
            <Table
              containerProps={{
                tabIndex: 0,
                role: "region",
                "aria-label": "回归报告列表，可横向滚动",
              }}
            >
              <TableHeader>
                <TableRow>
                  <TableHead>报告 / 创建时间</TableHead>
                  <TableHead>基线 → 候选</TableHead>
                  <TableHead>门槛结论</TableHead>
                  <TableHead>评分口径</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.data.items.slice(0, 50).map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <Link
                        className="text-button"
                        to={`/comparison?report=${item.id}`}
                      >
                        {shortId(item.id)}
                      </Link>
                      <div className="muted small-text">
                        {formatDate(item.created_at)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <code>
                        {shortId(item.baseline_id)} →{" "}
                        {shortId(item.candidate_id)}
                      </code>
                    </TableCell>
                    <TableCell>
                      <GateBadge status={item.content.gate.status} />
                    </TableCell>
                    <TableCell>{item.content.scorers.length} 组</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <Pagination
            page={page}
            next={(reports.data?.items.length || 0) > 50}
            onPage={(next) => setParams({ page: String(next) })}
          />
        </section>
      )}
    </>
  );
}
