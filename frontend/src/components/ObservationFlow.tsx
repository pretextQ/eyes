import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import type { CSSProperties, ReactNode } from "react";
import {
  ReactFlow,
  Background,
  ReactFlowProvider,
  Handle,
  Position,
  MarkerType,
  useReactFlow,
  useViewport,
  type Node,
  type NodeProps,
  type Edge,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import {
  Activity,
  ArrowDownToLine,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Cpu,
  FileText,
  GitBranch,
  List,
  Maximize,
  MessageSquare,
  Minus,
  Plus,
  ScanLine,
  Wrench,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Sheet,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from "@/components/ui/sheet";
import { JsonBlock } from "./ui";
import { cn } from "@/lib/utils";
import { formatDate } from "@/format";
import {
  buildObservationFlow,
  eventLabels,
  formatFlowDuration,
  type FlowState,
  type FlowStep,
  type FlowTurn,
  type ObservationEvent,
} from "@/lib/observation-flow";

const variants = {
  recorded: "secondary",
  ended: "success",
  running: "active",
  error: "destructive",
  unknown: "warning",
} as const;
const icons = {
  model: Cpu,
  tool: Wrench,
  compaction: ScanLine,
  message_end: MessageSquare,
  model_input: FileText,
};
type TraceNode = Node<
  {
    step: FlowStep;
    selected: boolean;
    vertical: boolean;
    select: (id: string) => void;
  },
  "step"
>;
type TurnNode = Node<
  {
    turn: FlowTurn;
    collapsed: boolean;
    selected: boolean;
    select: (id: string) => void;
    toggle: (id: string) => void;
  },
  "turn"
>;
type GraphNode = TraceNode | TurnNode;

function StepNode({ data }: NodeProps<TraceNode>) {
  const { step, vertical } = data;
  const Icon = icons[step.kind as keyof typeof icons] || Activity;
  return (
    <>
      <Handle
        type="target"
        position={vertical ? Position.Top : Position.Left}
        isConnectable={false}
      />
      <button
        className={cn("trace-node nodrag", data.selected && "is-selected")}
        data-state={step.state}
        onClick={(event) => {
          event.stopPropagation();
          data.select(step.id);
        }}
        aria-label={`查看${step.title}详情，${step.status}，事件 ${step.sequence}`}
        aria-pressed={data.selected}
        aria-expanded={data.selected}
        aria-haspopup="dialog"
        aria-controls={data.selected ? "trace-node-detail" : undefined}
      >
        <span className="trace-node-top">
          <span className="trace-node-icon">
            <Icon size={17} />
          </span>
          <span>{step.title}</span>
          <ChevronRight size={14} />
        </span>
        <span className="trace-node-status">
          <Badge variant={variants[step.state]}>{step.status}</Badge>
          {step.notes.length > 0 && (
            <CircleAlert size={14} aria-label="含观测提示" />
          )}
        </span>
        <span className="trace-node-meta">
          <span>
            {step.duration == null
              ? `#${step.sequence} · ${step.events.length} 条记录`
              : formatFlowDuration(step.duration)}
          </span>
          <span>{data.selected ? "收起详情" : "查看详情"}</span>
        </span>
      </button>
      <Handle
        type="source"
        position={vertical ? Position.Bottom : Position.Right}
        isConnectable={false}
      />
    </>
  );
}

function GroupNode({ data }: NodeProps<TurnNode>) {
  const { turn } = data;
  const errors = turn.steps.filter((s) => s.state === "error").length;
  return (
    <div className={cn("trace-turn", data.selected && "is-selected")}>
      <Handle type="target" position={Position.Top} isConnectable={false} />
      <div className="trace-turn-heading">
        <button
          className="trace-turn-title nodrag"
          onClick={() => data.select(turn.id)}
          aria-label={`查看${turn.title}详情`}
          aria-pressed={data.selected}
        >
          <span>{turn.title}</span>
          <span>{turn.steps.length} 个节点</span>
          {errors > 0 && <Badge variant="destructive">{errors} 个错误</Badge>}
        </button>
        <Button
          variant="ghost"
          size="icon-sm"
          className="nodrag"
          onClick={() => data.toggle(turn.id)}
          aria-label={`${data.collapsed ? "展开" : "折叠"}${turn.title}`}
          aria-expanded={!data.collapsed}
        >
          {data.collapsed ? <ChevronRight /> : <ChevronDown />}
        </Button>
      </div>
      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}
const nodeTypes = { step: StepNode, turn: GroupNode };
const compactQuery = "(max-width: 1100px)";
function subscribeCompact(onChange: () => void) {
  const media = window.matchMedia(compactQuery);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}
function compactSnapshot() {
  return window.matchMedia(compactQuery).matches;
}

function layout(turns: FlowTurn[], collapsed: Set<string>, vertical: boolean) {
  const nodes: GraphNode[] = [];
  const edges: Edge[] = [];
  const width = 232,
    height = 124;
  let y = 0;
  for (const [index, turn] of turns.entries()) {
    const closed = collapsed.has(turn.id);
    const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    graph.setGraph({
      rankdir: vertical ? "TB" : "LR",
      ranksep: 38,
      nodesep: 24,
      marginx: 20,
      marginy: 20,
    });
    if (!closed) {
      turn.steps.forEach((step) => graph.setNode(step.id, { width, height }));
      turn.steps.forEach((step, i) => {
        if (i) graph.setEdge(turn.steps[i - 1].id, step.id);
      });
      if (turn.steps.length) dagre.layout(graph);
    }
    const size = graph.graph();
    const groupWidth = Math.max(
      280,
      closed ? (vertical ? 280 : 320) : size.width || 280,
    );
    const groupHeight = closed ? 56 : (size.height || 40) + 48;
    nodes.push({
      id: turn.id,
      type: "turn",
      position: { x: 0, y },
      style: { width: groupWidth, height: groupHeight },
      data: {
        turn,
        collapsed: closed,
        selected: false,
        select: () => {},
        toggle: () => {},
      },
    });
    if (index)
      edges.push({
        id: `turn-edge-${turn.id}`,
        source: turns[index - 1].id,
        target: turn.id,
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed },
        className: "trace-order-edge",
      });
    if (!closed) {
      for (const [i, step] of turn.steps.entries()) {
        const pos = graph.node(step.id);
        nodes.push({
          id: step.id,
          type: "step",
          parentId: turn.id,
          extent: "parent",
          position: { x: pos.x - width / 2, y: pos.y - height / 2 + 48 },
          style: { width, height },
          data: { step, vertical, selected: false, select: () => {} },
        });
        if (i)
          edges.push({
            id: `order-${step.id}`,
            source: turn.steps[i - 1].id,
            target: step.id,
            type: "smoothstep",
            markerEnd: { type: MarkerType.ArrowClosed },
            className: "trace-order-edge",
          });
      }
    }
    y += groupHeight + 44;
  }
  return { nodes, edges };
}

function summaryStep(turn: FlowTurn): FlowStep {
  const hasError = turn.steps.some((s) => s.state === "error");
  return {
    id: turn.id,
    kind: "turn",
    title: turn.title,
    turn: turn.turn,
    sequence: turn.events[0]?.content.sequence || 0,
    state: hasError ? "error" : "recorded",
    status: hasError
      ? "含错误记录"
      : turn.complete
        ? "本轮已结束"
        : "已采集记录",
    notes: [],
    events: turn.events,
  };
}

function StepDetails({
  step,
  captureBody,
}: {
  step: FlowStep;
  captureBody: boolean;
}) {
  const ordered = step.events;
  const start = ordered.find((e) => e.content.type.endsWith("_start"));
  const end = ordered.find((e) =>
    step.kind === "turn"
      ? e.content.type === "turn_end"
      : e.content.type.endsWith("_end"),
  );
  const fields = [
    ["prompt", "用户任务"],
    ["arguments", "工具参数"],
    ["request", "模型输入"],
    ["response", "模型输出"],
    ["text", "响应正文"],
    ["tool_calls", "模型提出的工具调用"],
    ["output", "工具输出"],
    ["answer", "最终回答"],
    ["error", "错误信息"],
    ["reason", "原因"],
    ["usage", "Token 用量"],
  ];
  const payloads = ordered.flatMap((event) =>
    fields
      .filter(
        ([key]) =>
          event.content.data[key] != null && event.content.data[key] !== "",
      )
      .map(([key, label]) => ({
        event,
        key,
        label:
          key === "text" && event.content.type === "input" ? "用户输入" : label,
        value: event.content.data[key],
      })),
  );
  return (
    <div className="trace-detail-body">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={variants[step.state]}>{step.status}</Badge>
        <span className="muted small-text">
          {formatFlowDuration(step.duration)}
        </span>
      </div>
      {step.notes.map((note) => (
        <Alert key={note}>
          <CircleAlert />
          <AlertDescription>{note}</AlertDescription>
        </Alert>
      ))}
      <dl className="trace-detail-facts">
        <div>
          <dt>所属轮次</dt>
          <dd>{step.turn ? `第 ${step.turn} 轮` : "任务入口"}</dd>
        </div>
        <div>
          <dt>原始记录</dt>
          <dd>{ordered.length} 条</dd>
        </div>
        <div>
          <dt>开始 / 首次记录</dt>
          <dd>{formatDate((start || ordered[0]).content.occurred_at)}</dd>
        </div>
        <div>
          <dt>结束记录</dt>
          <dd>{end ? formatDate(end.content.occurred_at) : "未提供"}</dd>
        </div>
      </dl>
      {!captureBody && (
        <p className="muted small-text">
          此任务未启用正文采集，参数与完整输入输出可能不可用。
        </p>
      )}
      {payloads.map(({ event, key, label, value }) => (
        <section key={`${event.id}-${key}`} className="trace-payload">
          {typeof value === "string" ? (
            <>
              <h4>
                {label}
                <span>#{event.content.sequence}</span>
              </h4>
              <pre tabIndex={0} aria-label={label}>
                {value}
              </pre>
            </>
          ) : (
            <JsonBlock
              value={value}
              title={`${label} · #${event.content.sequence}`}
            />
          )}
        </section>
      ))}
      {!payloads.length && (
        <p className="muted small-text">
          该节点只有运行信息。可在原始事件中查看已上报字段。
        </p>
      )}
      <section className="trace-raw-events">
        <h4>原始事件与关联标识</h4>
        {ordered.map((event) => (
          <details key={event.id}>
            <summary>
              <span>
                #{event.content.sequence} ·{" "}
                {eventLabels[event.content.type] || event.content.type}
              </span>
              {event.content.truncated && (
                <Badge variant="warning">已截断</Badge>
              )}
            </summary>
            <JsonBlock
              title={`原始事件 #${event.content.sequence}`}
              value={event}
            />
          </details>
        ))}
      </section>
    </div>
  );
}

type Props = {
  events: ObservationEvent[];
  status: string;
  evidenceStatus: string;
  hasMore: boolean;
  captureBody: boolean;
  children: ReactNode;
};

export function ObservationFlow(props: Props) {
  return (
    <ReactFlowProvider>
      <FlowWorkspace {...props} />
    </ReactFlowProvider>
  );
}

function FlowWorkspace({
  events,
  status,
  evidenceStatus,
  hasMore,
  captureBody,
  children,
}: Props) {
  const [view, setView] = useState("graph");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const returnFocus = useRef<HTMLElement | null>(null);
  const [detailPosition, setDetailPosition] = useState<CSSProperties>({
    visibility: "hidden",
  });
  const canvas = useRef<HTMLDivElement | null>(null);
  const compact = useSyncExternalStore(
    subscribeCompact,
    compactSnapshot,
    () => false,
  );
  const flow = useReactFlow<GraphNode>();
  const viewport = useViewport();
  const turns = useMemo(
    () => buildObservationFlow(events, { status, hasMore, evidenceStatus }),
    [events, status, hasMore, evidenceStatus],
  );
  const steps = turns.flatMap((t) => t.steps);
  const selected =
    steps.find((s) => s.id === selectedId) ||
    (turns.find((t) => t.id === selectedId)
      ? summaryStep(turns.find((t) => t.id === selectedId)!)
      : null);
  const graph = useMemo(
    () => layout(turns, collapsed, compact),
    [turns, collapsed, compact],
  );
  const anchorFor = (id: string) => {
    const target =
      collapsed.has(id) || graph.nodes.some((node) => node.id === id)
        ? id
        : `turn-${steps.find((step) => step.id === id)?.turn}`;
    return canvas.current?.querySelector<HTMLElement>(
      `[data-id="${CSS.escape(target)}"] .trace-node, [data-id="${CSS.escape(target)}"] .trace-turn-title`,
    );
  };
  const open = (id: string) => {
    const anchor = anchorFor(id);
    returnFocus.current = anchor || (document.activeElement as HTMLElement);
    if (id !== selectedId && anchor) {
      const rect = anchor.getBoundingClientRect();
      const bounds = canvas.current!.getBoundingClientRect();
      const desiredTop = Math.min(460, window.innerHeight * 0.55) + 28;
      const shiftY = Math.max(
        0,
        Math.min(
          desiredTop - rect.top,
          bounds.bottom - rect.bottom - 16,
          window.innerHeight - rect.bottom - 16,
        ),
      );
      const center = rect.left + rect.width / 2;
      const width = Math.min(600, window.innerWidth - 32);
      const shiftX =
        Math.max(
          width / 2 + 16,
          Math.min(center, window.innerWidth - width / 2 - 16),
        ) - center;
      const viewport = flow.getViewport();
      void flow.setViewport({
        ...viewport,
        x: viewport.x + shiftX,
        y: viewport.y + shiftY,
      });
    }
    setSelectedId((current) => (current === id ? null : id));
  };
  const selectedAnchorId = graph.nodes.some((node) => node.id === selectedId)
    ? selectedId
    : selected
      ? `turn-${selected.turn}`
      : null;
  useLayoutEffect(() => {
    if (!selectedAnchorId || view !== "graph") return;
    let previous = "";
    const followAnchor = () => {
      const element = canvas.current?.querySelector<HTMLElement>(
        `[data-id="${CSS.escape(selectedAnchorId)}"] .trace-node, [data-id="${CSS.escape(selectedAnchorId)}"] .trace-turn-title`,
      );
      const rect = element?.getBoundingClientRect();
      const bounds = canvas.current?.getBoundingClientRect();
      const width = Math.min(600, window.innerWidth - 32);
      const center = rect ? rect.left + rect.width / 2 : 0;
      const left = Math.max(
        16,
        Math.min(center - width / 2, window.innerWidth - width - 16),
      );
      const visible =
        rect &&
        bounds &&
        rect.top > 120 &&
        rect.top < Math.min(window.innerHeight, bounds.bottom) &&
        rect.bottom > bounds.top &&
        center > bounds.left &&
        center < bounds.right;
      const position: CSSProperties = {
        left,
        width,
        bottom: window.innerHeight - (rect?.top || 0) + 12,
        maxHeight: Math.min(460, (rect?.top || 0) - 28),
        visibility: visible ? "visible" : "hidden",
        "--trace-arrow-x": `${Math.max(20, Math.min(width - 20, center - left))}px`,
      } as CSSProperties;
      const signature = JSON.stringify(position);
      if (signature !== previous) {
        previous = signature;
        setDetailPosition(position);
      }
    };
    followAnchor();
    window.addEventListener("scroll", followAnchor, true);
    window.addEventListener("resize", followAnchor);
    const observer = new ResizeObserver(followAnchor);
    if (canvas.current) observer.observe(canvas.current);
    return () => {
      window.removeEventListener("scroll", followAnchor, true);
      window.removeEventListener("resize", followAnchor);
      observer.disconnect();
    };
  }, [selectedAnchorId, view, viewport.x, viewport.y, viewport.zoom, compact]);
  const toggle = (id: string) =>
    setCollapsed((old) => {
      const next = new Set(old);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const nodes = graph.nodes.map((node): GraphNode =>
    node.type === "step"
      ? {
          ...node,
          data: {
            ...node.data,
            selected: node.id === selectedId,
            select: open,
          },
        }
      : {
          ...node,
          data: {
            ...node.data,
            selected: node.id === selectedId,
            select: open,
            toggle,
          },
        },
  );
  const errors = steps.filter((s) => s.state === "error");
  const pending = steps.filter((s) => s.state === "running");
  function locate(candidates: FlowStep[]) {
    const next =
      candidates[
        (candidates.findIndex((s) => s.id === selectedId) + 1) %
          candidates.length
      ];
    if (!next) return;
    // Collapsed turns remain compact; their summary is a stable navigation target.
    const target = collapsed.has(`turn-${next.turn}`)
      ? `turn-${next.turn}`
      : next.id;
    void flow
      .fitView({ nodes: [{ id: target }], padding: 0.4, maxZoom: 1 })
      .then(() => open(next.id));
  }
  const problem =
    hasMore || evidenceStatus === "partial" || status === "disconnected";
  return (
    <section className="trace-workspace" aria-label="执行链路视图">
      <div className="trace-toolbar">
        <ToggleGroup
          value={[view]}
          onValueChange={(value) => {
            if (value.length) setView(value[0]);
          }}
          variant="outline"
          size="sm"
          spacing={0}
          aria-label="执行链路展示方式"
        >
          <ToggleGroupItem value="graph">
            <GitBranch data-icon="inline-start" />
            流程图
          </ToggleGroupItem>
          <ToggleGroupItem value="events">
            <List data-icon="inline-start" />
            事件列表
          </ToggleGroupItem>
        </ToggleGroup>
        {view === "graph" && (
          <div className="trace-actions">
            <Button
              variant="ghost"
              size="sm"
              disabled={!pending.length}
              onClick={() => locate(pending)}
            >
              <ArrowDownToLine data-icon="inline-start" />
              当前调用
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={!errors.length}
              onClick={() => locate(errors)}
            >
              <CircleAlert data-icon="inline-start" />
              定位错误{errors.length > 0 && ` (${errors.length})`}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                setCollapsed(
                  collapsed.size
                    ? new Set()
                    : new Set(turns.filter((t) => t.complete).map((t) => t.id)),
                )
              }
              disabled={!collapsed.size && !turns.some((t) => t.complete)}
            >
              {collapsed.size ? "展开全部" : "折叠已结束轮次"}
            </Button>
          </div>
        )}
      </div>
      {view === "graph" ? (
        <>
          <div className="trace-caption">
            <span>{steps.length} 个节点 · 点击查看详情</span>
            <span>箭头表示事件记录顺序，不代表并行或因果关系</span>
          </div>
          {problem && (
            <Alert className="trace-notice">
              <CircleAlert />
              <AlertDescription>
                {hasMore
                  ? "仅展示已加载事件，请加载后续记录以查看完整路径。"
                  : "当前观测不完整，缺少结束记录的节点保持未知。"}
                {status === "disconnected" && " 观测中断不代表 Agent 已停止。"}
              </AlertDescription>
            </Alert>
          )}
          <div className="trace-layout">
            <div
              className="trace-canvas"
              aria-label="Agent 执行流程图"
              ref={canvas}
            >
              <ReactFlow<GraphNode>
                key={compact ? "vertical" : "horizontal"}
                nodes={nodes}
                edges={graph.edges}
                nodeTypes={nodeTypes}
                onNodeClick={(_event, node) => {
                  if (node.type === "step") open(node.id);
                }}
                onPaneClick={() => setSelectedId(null)}
                nodesDraggable={false}
                nodesConnectable={false}
                nodesFocusable={false}
                edgesFocusable={false}
                elementsSelectable={false}
                minZoom={0.2}
                maxZoom={1.5}
                zoomOnDoubleClick={false}
                onInit={(instance) => {
                  if (compact) {
                    void instance.setViewport({
                      x: 16,
                      y: 16,
                      zoom: Math.min(
                        1,
                        ((canvas.current?.clientWidth || 320) - 32) / 280,
                      ),
                    });
                    return;
                  }
                  void instance
                    .fitView({
                      nodes: graph.nodes
                        .filter((n) => n.type === "turn")
                        .slice(0, 2),
                      padding: 0.15,
                      minZoom: 0.75,
                      maxZoom: 1,
                    })
                    .then(() =>
                      instance.setViewport({
                        x: 20,
                        y: 20,
                        zoom: instance.getZoom(),
                      }),
                    );
                }}
              >
                <Background gap={24} size={1} color="var(--line-strong)" />
              </ReactFlow>
              <div className="trace-canvas-tools" aria-label="流程图缩放">
                <Button
                  variant="outline"
                  size="icon-sm"
                  aria-label="放大流程图"
                  onClick={() => void flow.zoomIn()}
                >
                  <Plus />
                </Button>
                <Button
                  variant="outline"
                  size="icon-sm"
                  aria-label="缩小流程图"
                  onClick={() => void flow.zoomOut()}
                >
                  <Minus />
                </Button>
                <Button
                  variant="outline"
                  size="icon-sm"
                  aria-label="适应全部节点"
                  onClick={() =>
                    void flow.fitView({ padding: 0.15, maxZoom: 1 })
                  }
                >
                  <Maximize />
                </Button>
              </div>
            </div>
          </div>
          <div className="trace-legend">
            {(
              [
                ["ended", "已结束"],
                ["running", "等待结束"],
                ["error", "错误"],
                ["unknown", "记录待确认"],
              ] as [FlowState, string][]
            ).map(([state, label]) => (
              <Badge key={state} variant={variants[state]}>
                {label}
              </Badge>
            ))}
            <span>已结束仅指收到结束记录。</span>
          </div>
        </>
      ) : (
        children
      )}
      <Sheet
        modal={false}
        disablePointerDismissal
        open={!!selected && view === "graph"}
        onOpenChange={(isOpen) => {
          if (!isOpen) setSelectedId(null);
        }}
      >
        <DialogPrimitive.Portal>
          <DialogPrimitive.Popup
            id="trace-node-detail"
            className="trace-floating-detail"
            style={detailPosition}
            initialFocus={false}
            finalFocus={returnFocus}
          >
            <SheetHeader>
              <div className="trace-detail-kicker">
                节点详情 ·{" "}
                {selected?.turn ? `第 ${selected.turn} 轮` : "任务入口"}
              </div>
              <SheetTitle>{selected?.title || "节点详情"}</SheetTitle>
              <SheetDescription>
                再次点击此节点可收起 · 点击其他节点可切换
              </SheetDescription>
              <SheetClose
                render={
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="关闭节点详情"
                  />
                }
              >
                <X />
              </SheetClose>
            </SheetHeader>
            <div className="trace-floating-scroll" key={selected?.id}>
              {selected && (
                <StepDetails step={selected} captureBody={captureBody} />
              )}
            </div>
          </DialogPrimitive.Popup>
        </DialogPrimitive.Portal>
      </Sheet>
    </section>
  );
}
