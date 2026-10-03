import { Search } from "lucide-react";
import { useRef, useState } from "react";
import { formatDate, shortId } from "../format";
import type { Event } from "../types";
import { Empty, JsonBlock } from "./ui";

export function EventExplorer({
  events,
  selectedId,
  onSelect,
}: {
  events: Event[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const [search, setSearch] = useState("");
  const inspector = useRef<HTMLElement>(null);
  const visible = events.filter((event) =>
    `${event.content.type} ${event.content.source} ${event.producer_id} ${event.content.span_id || ""}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const selected = events.find((event) => event.id === selectedId);
  const current = selected || (!selectedId ? visible[0] : undefined);
  return (
    <div className="event-explorer">
      <div className="event-index">
        <div className="event-index-heading">
          <span className="section-label">已采集事件</span>
          <span className="count">{events.length} / 本页</span>
        </div>
        <div className="search">
          <Search size={15} />
          <input
            type="search"
            aria-label="搜索当前页事件"
            placeholder="类型、来源或 Span…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="event-list" aria-label="选择执行事件">
          {visible.length ? (
            visible.map((event) => (
              <button
                key={event.id}
                className={`event-choice ${current?.id === event.id ? "selected" : ""}`}
                aria-pressed={current?.id === event.id}
                onClick={() => {
                  onSelect(event.id);
                  if (window.matchMedia("(max-width: 700px)").matches)
                    inspector.current?.focus();
                }}
              >
                <span className="event-order">
                  {String(events.indexOf(event) + 1).padStart(2, "0")}
                </span>
                <span className="event-choice-copy">
                  <strong>{event.content.type}</strong>
                  <small>
                    {event.content.source} · #{event.content.sequence}
                  </small>
                  <small>{formatDate(event.content.occurred_at)}</small>
                </span>
              </button>
            ))
          ) : (
            <Empty
              compact
              title="没有匹配的事件"
              description="搜索范围为当前页，调整关键词或翻页。"
            />
          )}
        </div>
      </div>
      <section
        className="event-inspector"
        aria-label="选中事件的证据详情"
        ref={inspector}
        tabIndex={-1}
      >
        {current ? (
          <>
            <div className="section-label">EVENT / {shortId(current.id)}</div>
            <h3>{current.content.type}</h3>
            <div className="key-values">
              <div>
                <span>采集来源</span>
                <code>{current.content.source}</code>
              </div>
              <div>
                <span>生产者 / 序号</span>
                <code>
                  {current.producer_id} / {current.content.sequence}
                </code>
              </div>
              <div>
                <span>发生时间</span>
                <span>{formatDate(current.content.occurred_at)}</span>
              </div>
              <div>
                <span>接收时间</span>
                <span>{formatDate(current.created_at)}</span>
              </div>
              <div>
                <span>Span</span>
                <code>{current.content.span_id || "未提供"}</code>
              </div>
              <div>
                <span>父 Span</span>
                <code>{current.content.parent_span_id || "未提供"}</code>
              </div>
            </div>
            <JsonBlock title="事件内容" value={current.content.data} />
            <JsonBlock title="证据引用" value={`event:${current.id}`} />
          </>
        ) : (
          <Empty
            compact
            title={selectedId ? "该事件不在当前页" : "尚无已采集事件"}
            description={
              selectedId
                ? "切换事件页，或选择本页的事件继续审阅。"
                : "无事件不表示没有内部执行，采集范围取决于目标接入。"
            }
          />
        )}
      </section>
    </div>
  );
}
