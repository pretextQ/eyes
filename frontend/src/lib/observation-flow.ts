export type ObservationEvent = {
  id: string;
  content: {
    type: string;
    sequence: number;
    occurred_at: string;
    turn: number | null;
    tool_call_id: string | null;
    trace_id: string | null;
    span_id: string | null;
    parent_span_id: string | null;
    data: Record<string, unknown>;
    truncated: boolean;
  };
};

export type FlowState = "recorded" | "ended" | "running" | "error" | "unknown";
export type FlowStep = {
  id: string;
  kind: string;
  title: string;
  turn: number;
  sequence: number;
  state: FlowState;
  status: string;
  notes: string[];
  events: ObservationEvent[];
  duration?: number;
};
export type FlowTurn = {
  id: string;
  turn: number;
  title: string;
  steps: FlowStep[];
  events: ObservationEvent[];
  complete: boolean;
};

export const eventLabels: Record<string, string> = {
  run_start: "任务开始",
  run_end: "任务结束",
  input: "用户输入",
  turn_start: "开始新一轮",
  turn_end: "本轮结束",
  message_end: "模型响应",
  model_start: "请求模型",
  model_end: "模型请求结束",
  model_input: "模型输入与输出",
  tool_start: "执行工具",
  tool_end: "工具结果",
  compaction_start: "开始压缩上下文",
  compaction_end: "上下文压缩结束",
};

function pairKey(event: ObservationEvent): string | null {
  const c = event.content;
  const kind = c.type.replace(/_(start|end)$/, "");
  if (kind === "tool" && c.tool_call_id)
    return JSON.stringify([c.turn, kind, c.tool_call_id]);
  if (["model", "compaction"].includes(kind) && c.trace_id && c.span_id)
    return JSON.stringify([c.turn, kind, c.trace_id, c.span_id]);
  return null;
}

/** A presentation of reported boundaries; never a replacement for run state. */
export function buildObservationFlow(
  input: ObservationEvent[],
  context: { status: string; hasMore: boolean; evidenceStatus: string },
): FlowTurn[] {
  const events = [...new Map(input.map((e) => [e.id, e])).values()].sort(
    (a, b) => a.content.sequence - b.content.sequence,
  );
  const pairs = new Map<string, ObservationEvent[]>();
  for (const event of events) {
    const key = pairKey(event);
    if (key) pairs.set(key, [...(pairs.get(key) || []), event]);
  }
  const consumed = new Set<string>();
  const steps: FlowStep[] = [];
  for (const event of events) {
    const c = event.content;
    if (consumed.has(event.id) || ["turn_start", "turn_end"].includes(c.type))
      continue;
    const kind = c.type.replace(/_(start|end)$/, "");
    const paired = ["model", "tool", "compaction"].includes(kind);
    const key = paired ? pairKey(event) : null;
    const candidates = (key && pairs.get(key)) || [event];
    const starts = candidates.filter((e) => e.content.type.endsWith("_start"));
    const ends = candidates.filter((e) => e.content.type.endsWith("_end"));
    // Reused or ambiguous identities stay separate, rather than silently merging calls.
    const ambiguous = starts.length > 1 || ends.length > 1;
    const records = ambiguous ? [event] : candidates;
    records.forEach((e) => consumed.add(e.id));
    const start = records.find((e) => e.content.type === `${kind}_start`);
    const end = records.find((e) => e.content.type === `${kind}_end`);
    const data = end?.content.data || c.data;
    const status = typeof data.status === "string" ? data.status : "";
    const notes: string[] = [];
    let state: FlowState = "recorded";
    let label = "已记录";
    if (paired) {
      if (end) {
        state = "ended";
        label = "已结束";
        const error =
          (kind === "tool" && status !== "success" && !!status) ||
          status === "ERROR" ||
          !!data.error;
        if (error) {
          state = "error";
          label = "错误";
        }
        if (!start) {
          notes.push(
            "未观察到开始事件，不能据此确认实际执行过。可查看结果中的错误原因。",
          );
          if (!error) {
            state = "unknown";
            label = "开始记录缺失";
          }
        }
      } else if (
        context.status === "running" &&
        !context.hasMore &&
        context.evidenceStatus === "collecting" &&
        !events.some(
          (e) => e.content.type === "turn_end" && e.content.turn === c.turn,
        )
      ) {
        state = "running";
        label = "等待结束";
      } else {
        state = "unknown";
        label = context.hasMore ? "等待加载后续" : "结束记录缺失";
        notes.push(
          context.hasMore
            ? "后续事件尚未全部加载，结束记录可能在后续页中。"
            : "没有配对的结束事件，无法确定这次调用的最终结果。",
        );
      }
    } else if (c.type === "run_end") {
      state =
        status === "failed"
          ? "error"
          : status === "completed"
            ? "ended"
            : "unknown";
      label =
        (
          {
            completed: "已完成",
            failed: "失败",
            limited: "达到限制",
            cancelled: "已取消",
          } as Record<string, string>
        )[status] || "结果未知";
    }
    if (ambiguous)
      notes.push("关联标识被重复使用，已保留为独立事件，未自动配对。");
    if (records.some((e) => e.content.truncated))
      notes.push("部分事件内容已截断。");
    const name = records
      .map((e) => e.content.data.name)
      .find((v) => typeof v === "string");
    const title =
      kind === "tool"
        ? String(name || "工具调用")
        : kind === "model"
          ? "模型调用"
          : kind === "compaction"
            ? "上下文压缩"
            : eventLabels[c.type] || c.type;
    const duration =
      typeof data.duration_ms === "number" &&
      Number.isFinite(data.duration_ms) &&
      data.duration_ms >= 0
        ? data.duration_ms
        : undefined;
    steps.push({
      id:
        paired && key && !ambiguous
          ? `call-${encodeURIComponent(key)}`
          : event.id,
      kind: paired ? kind : c.type,
      title,
      turn: c.type === "run_start" ? 0 : c.turn || 0,
      sequence: records[0].content.sequence,
      state,
      status: label,
      notes,
      events: records,
      duration,
    });
  }

  // Deta's model_input span is the explicit parent of its attempt span.
  // Attach the body only when it identifies exactly one observed call.
  const attached = new Set<string>();
  for (const body of steps.filter((s) => s.kind === "model_input")) {
    const c = body.events[0].content;
    if (!c.trace_id || !c.span_id) continue;
    const matches = steps.filter(
      (s) =>
        s.kind === "model" &&
        s.turn === body.turn &&
        s.events.some(
          (e) =>
            e.content.trace_id === c.trace_id &&
            e.content.parent_span_id === c.span_id,
        ),
    );
    if (matches.length === 1) {
      matches[0].events.push(...body.events);
      matches[0].notes.push(...body.notes);
      attached.add(body.id);
    }
  }
  const groups = new Map<number, FlowTurn>();
  for (const event of events) {
    const turn =
      event.content.type === "run_start" ? 0 : event.content.turn || 0;
    if (!groups.has(turn))
      groups.set(turn, {
        id: `turn-${turn}`,
        turn,
        title: turn ? `第 ${turn} 轮` : "任务入口",
        steps: [],
        events: [],
        complete: false,
      });
    const group = groups.get(turn)!;
    group.events.push(event);
    if (event.content.type === "turn_end") group.complete = true;
  }
  for (const step of steps) {
    if (attached.has(step.id)) continue;
    step.events.sort((a, b) => a.content.sequence - b.content.sequence);
    groups.get(step.turn)!.steps.push(step);
  }
  return [...groups.values()];
}

export function formatFlowDuration(value?: number): string {
  if (value == null) return "耗时未提供";
  return value < 1000
    ? `${value.toFixed(0)} ms`
    : `${(value / 1000).toFixed(2)} s`;
}
