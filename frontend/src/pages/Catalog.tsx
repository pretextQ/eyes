import { formatDate } from "../format";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  FileJson,
  Fingerprint,
  Plus,
  Search,
  Upload,
} from "lucide-react";
import { useConnection } from "../connection";
import {
  Badge,
  CheckItem,
  Dialog,
  Disconnected,
  Empty,
  ErrorNotice,
  Field,
  JsonBlock,
  Loading,
  PageHeading,
} from "../components/ui";
import type { CatalogKind, Payload, TargetContent, Version } from "../types";

const info = {
  targets: {
    eyebrow: "03 / TARGETS",
    title: "目标 Agent",
    description: "发布接入配置与能力声明，为每次实验固定目标版本。",
    action: "接入 Agent",
    empty: "还没有接入目标 Agent",
    text: "支持 HTTP 和 Python 接入。目标在独立 Runner 环境执行。",
  },
  datasets: {
    eyebrow: "04 / DATASETS",
    title: "测试集",
    description: "用稳定的用例标识，把测试输入、预期和环境要求一起固定。",
    action: "导入测试集",
    empty: "把你的测试用例带进来",
    text: "导入 JSONL，整体校验后发布；无效记录会报告具体行号。",
  },
  scorers: {
    eyebrow: "05 / SCORERS",
    title: "评分口径",
    description: "让每一个质量结论，都能追溯到固定口径和执行证据。",
    action: "发布评分器",
    empty: "定义实验的质量标准",
    text: "支持规则与可信 Python 插件，固定实现摘要和所需证据。",
  },
};
export function CatalogPage({ kind }: { kind: CatalogKind }) {
  return <CatalogView key={kind} kind={kind} />;
}
function CatalogView({ kind }: { kind: CatalogKind }) {
  const { api, openConnection } = useConnection();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Version | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const query = useQuery({
    queryKey: ["catalog", kind],
    queryFn: ({ signal }) => api!.catalog(kind, signal),
    enabled: !!api,
  });
  const config = info[kind];
  const filtered =
    query.data?.filter((v) =>
      `${v.name} ${v.digest} ${v.id}`
        .toLowerCase()
        .includes(search.toLowerCase()),
    ) || [];
  const visible = filtered.slice(page * 50, (page + 1) * 50);
  const publish = () => (api ? setOpen(true) : openConnection());
  return (
    <>
      <PageHeading
        eyebrow={config.eyebrow}
        title={config.title}
        description={config.description}
        action={
          <button className="button primary" onClick={publish}>
            {kind === "datasets" ? <Upload size={16} /> : <Plus size={16} />}{" "}
            {config.action}
          </button>
        }
      />
      <div className="catalog-intro">
        <Fingerprint size={20} strokeWidth={1.4} />
        <p>
          已发布版本不可变。更新配置时发布新版本，已有实验继续引用原始快照。
        </p>
        <span className="mono">IMMUTABLE VERSIONS</span>
      </div>
      <section className="panel">
        <div className="panel-toolbar">
          <div className="toolbar-title">
            版本目录{" "}
            <span className="count">
              {query.data ? query.data.length : "—"}
            </span>
          </div>
          <div className="search">
            <Search size={15} />
            <input
              aria-label={`搜索${config.title}`}
              placeholder="搜索名称或摘要…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
            />
          </div>
        </div>
        {!api ? (
          <Disconnected />
        ) : query.isPending ? (
          <Loading />
        ) : query.error ? (
          <ErrorNotice error={query.error} retry={() => void query.refetch()} />
        ) : !query.data.length ? (
          <Empty
            title={config.empty}
            description={config.text}
            action={
              <button className="button" onClick={publish}>
                {config.action}
                <ArrowUpRight size={16} />
              </button>
            }
          />
        ) : !filtered.length ? (
          <Empty
            compact
            title="没有匹配的版本"
            description="修改搜索词，或清除筛选查看全部版本。"
            action={
              <button className="button" onClick={() => setSearch("")}>
                清除搜索
              </button>
            }
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>名称</th>
                  <th>
                    {kind === "datasets"
                      ? "用例数量"
                      : kind === "targets"
                        ? "接入与观测"
                        : "评分插件"}
                  </th>
                  <th>
                    {kind === "targets"
                      ? "容量"
                      : kind === "datasets"
                        ? "协议"
                        : "所需证据"}
                  </th>
                  <th>内容摘要</th>
                  <th>发布时间</th>
                  <th>
                    <span className="sr-only">查看版本</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <button
                        className="text-button table-title"
                        onClick={() => setSelected(v)}
                      >
                        {v.name}
                        <ArrowUpRight size={14} />
                      </button>
                      <small className="mono">{v.id.slice(0, 8)}</small>
                    </td>
                    <td>
                      {kind === "targets" ? (
                        <>
                          {String((v.content.capabilities as Payload)?.adapter)}
                          <small>
                            {(
                              (v.content.capabilities as Payload)
                                ?.observation as string[]
                            )?.join(" · ")}
                          </small>
                        </>
                      ) : kind === "datasets" ? (
                        `${(v.content.cases as unknown[])?.length || 0} 条`
                      ) : (
                        String(v.content.plugin)
                      )}
                    </td>
                    <td>
                      {kind === "targets" ? (
                        `${v.content.concurrency_limit} 并发`
                      ) : kind === "datasets" ? (
                        <span className="subtle-tag">JSONL / 1.0</span>
                      ) : (
                        <span className="mono">
                          {(v.content.required_evidence as string[])?.join(
                            ", ",
                          )}
                        </span>
                      )}
                    </td>
                    <td className="mono">{v.digest.slice(0, 12)}</td>
                    <td className="date-cell">{formatDate(v.created_at)}</td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`查看 ${v.name} 版本`}
                        onClick={() => setSelected(v)}
                      >
                        <ArrowUpRight size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {filtered.length > 50 && (
          <div className="pagination">
            <span>
              第 {page + 1} 页 · 共 {filtered.length} 个版本
            </span>
            <div>
              <button
                className="button small"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                上一页
              </button>
              <button
                className="button small"
                disabled={(page + 1) * 50 >= filtered.length}
                onClick={() => setPage((p) => p + 1)}
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </section>
      <div className="catalog-footnote">
        <FileJson size={16} />
        {config.text}
      </div>
      {open && <PublishDialog kind={kind} onClose={() => setOpen(false)} />}{" "}
      {selected && (
        <VersionDialog
          version={selected}
          kind={kind}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
function VersionDialog({
  version,
  kind,
  onClose,
}: {
  version: Version;
  kind: CatalogKind;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const cases = kind === "datasets" ? (version.content.cases as Payload[]) : [];
  return (
    <Dialog
      wide
      title={version.name}
      subtitle={`版本 ${version.id}`}
      onClose={onClose}
    >
      <div className="form">
        <div className="version-meta">
          <span>
            <Fingerprint size={15} />
            内容摘要
          </span>
          <code>{version.digest}</code>
        </div>
        {kind === "datasets" ? (
          <>
            <div className="search">
              <Search size={15} />
              <input
                aria-label="搜索用例"
                placeholder="搜索用例标识或标签…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="dataset-cases">
              {cases
                .filter((c) =>
                  `${c.case_id} ${(c.tags as string[])?.join(" ")}`.includes(
                    search,
                  ),
                )
                .map((c) => (
                  <details key={String(c.case_id)}>
                    <summary>
                      <span>{String(c.case_id)}</span>
                      <span className="mono">
                        {(c.tags as string[])?.join(" / ")}
                      </span>
                    </summary>
                    <JsonBlock value={c} />
                  </details>
                ))}
            </div>
          </>
        ) : (
          <JsonBlock title="固定发布配置" value={version.content} />
        )}
        <div className="form-actions">
          <Badge status="sealed" />
          <button className="button" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>
    </Dialog>
  );
}
function parseObject(text: string, name: string): Payload {
  const value = JSON.parse(text);
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error(`${name}必须是 JSON 对象。`);
  return value;
}
function PublishDialog({
  kind,
  onClose,
}: {
  kind: CatalogKind;
  onClose: () => void;
}) {
  const { api } = useConnection();
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [externalVersion, setExternalVersion] = useState("");
  const [adapter, setAdapter] = useState("http");
  const [limit, setLimit] = useState(1);
  const [capabilities, setCapabilities] = useState({
    session_isolation: false,
    environment_isolation: false,
    cancellation: false,
    idempotency: false,
    reconciliation: false,
  });
  const [observation, setObservation] = useState(["task"]);
  const [config, setConfig] = useState("{}");
  const [secrets, setSecrets] = useState("{}");
  const [jsonl, setJsonl] = useState("");
  const [filename, setFilename] = useState("");
  const [plugin, setPlugin] = useState("rules");
  const [digest, setDigest] = useState("");
  const [requiredEvidence, setRequiredEvidence] = useState(["output"]);
  const [numeric, setNumeric] = useState("null");
  const [timeout, setTimeout] = useState(60);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function readFile(file?: File) {
    if (!file) return;
    if (file.size > 7 * 1024 * 1024) {
      setError(new Error("文件超过控制台 7 MiB 导入上限，请拆分数据集。"));
      return;
    }
    setJsonl(await file.text());
    setFilename(file.name);
    setError(null);
  }
  async function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!api) return;
    setBusy(true);
    setError(null);
    try {
      let path: string, body: unknown;
      if (kind === "datasets") {
        path = "/v1/datasets/import";
        body = { schema_version: "1.0", name: name.trim(), jsonl };
      } else if (kind === "targets") {
        path = "/v1/targets";
        const content: TargetContent = {
          name: name.trim(),
          external_version: externalVersion.trim() || null,
          config: parseObject(config, "接入配置"),
          secret_refs: parseObject(secrets, "密钥引用") as Record<
            string,
            string
          >,
          concurrency_limit: limit,
          capabilities: {
            adapter: adapter.trim(),
            ...capabilities,
            observation,
          },
        };
        body = { schema_version: "1.0", ...content };
      } else {
        path = "/v1/scorers";
        body = {
          schema_version: "1.0",
          name: name.trim(),
          plugin: plugin.trim(),
          implementation_digest: digest.trim(),
          config: parseObject(config, "评分配置"),
          secret_refs: parseObject(secrets, "密钥引用"),
          required_evidence: requiredEvidence,
          numeric: JSON.parse(numeric),
          timeout_seconds: timeout,
        };
      }
      await api.post<Version>(path, body);
      await client.invalidateQueries({ queryKey: ["catalog", kind] });
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const labels: Record<string, string> = {
    session_isolation: "会话隔离",
    environment_isolation: "环境隔离",
    cancellation: "支持取消",
    idempotency: "支持幂等",
    reconciliation: "支持状态核对",
  };
  return (
    <Dialog
      wide
      title={info[kind].action}
      subtitle="发布新的固定版本，不改变已有实验与历史记录。"
      onClose={onClose}
    >
      <form className="form" onSubmit={submit}>
        <Field label="名称">
          <input
            required
            maxLength={200}
            placeholder={
              kind === "targets"
                ? "目标 Agent 的稳定名称"
                : kind === "datasets"
                  ? "测试集名称"
                  : "评分口径名称"
            }
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        {kind === "datasets" ? (
          <>
            <label className="file-drop">
              <Upload size={23} />
              <strong>{filename || "选择 JSONL 文件"}</strong>
              <span>每行一个单轮用例 · 最大 7 MiB</span>
              <input
                type="file"
                accept=".jsonl,.ndjson,.json,text/plain,application/json"
                onChange={(e) => {
                  void readFile(e.target.files?.[0]);
                }}
              />
            </label>
            <Field
              label="JSONL 内容"
              hint="必需 case_id、input 对象；可选 expectations、tags、environment、artifact_requirements。空行、重复标识和非空 steps 会拒绝整个版本。"
            >
              <textarea
                required
                className="code-input tall"
                spellCheck={false}
                value={jsonl}
                onChange={(e) => {
                  setJsonl(e.target.value);
                  setFilename("");
                }}
                placeholder={"每行一个 JSON 对象，粘贴你的测试用例"}
              />
            </Field>
            <p className="muted">
              {jsonl
                ? `${jsonl.split(/\r?\n/).length} 个文本行，实际用例数由服务端校验。`
                : "也可以直接粘贴 JSONL 内容。"}
            </p>
          </>
        ) : (
          <>
            {kind === "targets" ? (
              <>
                <div className="form-grid">
                  <Field
                    label="适配器标识"
                    hint="必须与 Runner 已安装适配器一致。"
                  >
                    <input
                      required
                      list="adapter-options"
                      value={adapter}
                      onChange={(e) => setAdapter(e.target.value)}
                    />
                    <datalist id="adapter-options">
                      <option value="http" />
                      <option value="python" />
                    </datalist>
                  </Field>
                  <Field label="外部版本（可选）">
                    <input
                      maxLength={200}
                      value={externalVersion}
                      onChange={(e) => setExternalVersion(e.target.value)}
                      placeholder="如 Git revision 或发布版本"
                    />
                  </Field>
                </div>
                <fieldset>
                  <legend>实际能力声明</legend>
                  <div className="checkbox-grid">
                    {Object.entries(capabilities).map(([key, value]) => (
                      <CheckItem
                        key={key}
                        checked={value}
                        onChange={(v) =>
                          setCapabilities((s) => ({ ...s, [key]: v }))
                        }
                      >
                        {labels[key]}
                      </CheckItem>
                    ))}
                  </div>
                </fieldset>
                <Field
                  label="目标并发容量"
                  hint="大于 1 需要同时声明会话与环境隔离。同名目标版本共享固定容量。"
                >
                  <input
                    required
                    type="number"
                    min={1}
                    max={1000}
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                  />
                </Field>
                <fieldset>
                  <legend>观测范围（至少一项）</legend>
                  <div className="checkbox-grid">
                    {[
                      { id: "task", label: "任务接口" },
                      { id: "sdk", label: "SDK 埋点" },
                      { id: "target_trace", label: "目标轨迹" },
                    ].map((o) => (
                      <CheckItem
                        key={o.id}
                        checked={observation.includes(o.id)}
                        onChange={(v) =>
                          setObservation((s) =>
                            v ? [...s, o.id] : s.filter((i) => i !== o.id),
                          )
                        }
                      >
                        {o.label}
                      </CheckItem>
                    ))}
                  </div>
                </fieldset>
              </>
            ) : (
              <>
                <div className="form-grid">
                  <Field label="评分插件标识">
                    <input
                      required
                      value={plugin}
                      onChange={(e) => setPlugin(e.target.value)}
                    />
                  </Field>
                  <Field label="评分超时 / 秒">
                    <input
                      required
                      type="number"
                      min={1}
                      max={86400}
                      value={timeout}
                      onChange={(e) => setTimeout(Number(e.target.value))}
                    />
                  </Field>
                </div>
                <Field
                  label="实现摘要 / SHA-256"
                  hint="运行 eyes-runner --config runner.toml plugins 获取真实摘要。"
                >
                  <input
                    className="mono"
                    required
                    pattern="[0-9a-f]{64}"
                    minLength={64}
                    maxLength={64}
                    value={digest}
                    onChange={(e) => setDigest(e.target.value)}
                    placeholder="64 位小写十六进制摘要"
                  />
                </Field>
                <fieldset>
                  <legend>所需证据</legend>
                  <div className="checkbox-grid">
                    {["input", "output", "events", "artifacts", "sealed"].map(
                      (id) => (
                        <CheckItem
                          key={id}
                          checked={requiredEvidence.includes(id)}
                          onChange={(v) =>
                            setRequiredEvidence((s) =>
                              v ? [...s, id] : s.filter((i) => i !== id),
                            )
                          }
                        >
                          {id}
                        </CheckItem>
                      ),
                    )}
                  </div>
                </fieldset>
                <Field
                  label="数值语义 / JSON"
                  hint="无数值评分使用 null；否则提供 minimum、maximum、direction、threshold、aggregation。"
                >
                  <textarea
                    className="code-input"
                    value={numeric}
                    onChange={(e) => setNumeric(e.target.value)}
                    spellCheck={false}
                  />
                </Field>
              </>
            )}
            <Field
              label={kind === "targets" ? "接入配置 / JSON" : "评分配置 / JSON"}
              hint={
                kind === "targets"
                  ? "HTTP 使用 url；Python 使用 agent 别名与 parameters。配置不保存明文密钥。"
                  : "规则插件使用 checks 数组；Python 插件按自身配置契约填写。"
              }
            >
              <textarea
                required
                className="code-input"
                spellCheck={false}
                value={config}
                onChange={(e) => setConfig(e.target.value)}
              />
            </Field>
            <Field
              label="密钥引用 / JSON"
              hint="仅填写运行环境引用名，禁止填入真实凭据。无需密钥时保留空对象。"
            >
              <textarea
                className="code-input short"
                spellCheck={false}
                value={secrets}
                onChange={(e) => setSecrets(e.target.value)}
              />
            </Field>
          </>
        )}
        {error != null && <ErrorNotice error={error} />}
        <div className="form-actions">
          <button type="button" className="button" onClick={onClose}>
            取消
          </button>
          <button
            className="button primary"
            disabled={
              busy ||
              !name.trim() ||
              (kind === "targets" && !observation.length)
            }
          >
            <Upload size={16} />
            {busy ? "正在发布…" : "校验并发布"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
