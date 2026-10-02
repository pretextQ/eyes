import type { CatalogKind, Version } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}
export class Api {
  constructor(readonly token: string) {}
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`/api${path}`, {
        ...options,
        signal: AbortSignal.any([
          ...(options.signal ? [options.signal] : []),
          AbortSignal.timeout(30000),
        ]),
        headers: {
          Authorization: `Bearer ${this.token}`,
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...options.headers,
        },
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError")
        throw error;
      if (error instanceof DOMException && error.name === "TimeoutError")
        throw new ApiError(
          408,
          "请求超时，请检查后端服务。创建实验重试会复用同参数的请求键。",
        );
      throw new ApiError(0, "无法连接控制 API，请检查后端服务和代理配置。");
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const messages: Record<number, string> = {
        401: "令牌无效或已撤销，请重新连接。",
        403: "当前令牌没有此操作的权限，请使用管理令牌。",
        404: "记录不存在或不属于当前项目。",
        503: "后端尚未就绪，请检查 PostgreSQL 和数据库迁移。",
      };
      throw new ApiError(
        response.status,
        messages[response.status] ||
          body?.error?.message ||
          `请求失败（${response.status}）`,
        body?.error?.details,
      );
    }
    if (response.status === 204) return undefined as T;
    const body = await response.json().catch(() => {
      throw new ApiError(502, "API 返回了无效响应，请检查 /api 反向代理。");
    });
    return body as T;
  }
  post<T>(path: string, body?: unknown, headers?: Record<string, string>) {
    return this.request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
      headers,
    });
  }
  async catalog(kind: CatalogKind, signal?: AbortSignal): Promise<Version[]> {
    const all: Version[] = [];
    for (let offset = 0; ; offset += 200) {
      const result = await this.request<{ items: Version[] }>(
        `/v1/catalog/${kind}?limit=200&offset=${offset}`,
        { signal },
      );
      all.push(...result.items);
      if (result.items.length < 200) return all;
    }
  }
  async caseRuns(id: string, signal?: AbortSignal) {
    const all: import("./types").CaseRun[] = [];
    for (let offset = 0; ; offset += 200) {
      const result = await this.request<{ items: import("./types").CaseRun[] }>(
        `/v1/experiments/${id}/case-runs?limit=200&offset=${offset}`,
        { signal },
      );
      all.push(...result.items);
      if (result.items.length < 200) return all;
    }
  }
  async download(id: string) {
    const response = await fetch(`/api/v1/artifacts/${id}/content`, {
      headers: { Authorization: `Bearer ${this.token}` },
      signal: AbortSignal.timeout(60000),
    });
    if (!response.ok)
      throw new ApiError(
        response.status,
        `产物下载失败（${response.status}），可能尚未发布或已过期。`,
      );
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `eyes-artifact-${id}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
