import json

import httpx

from eyes.contracts.target import validate_control_url


def response_code(value):
    error = value.get("error") if isinstance(value, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else "http_error"


class ApiError(Exception):
    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code
        super().__init__(f"control API returned {status} ({code})")

    @property
    def retryable(self):
        return self.status in {408, 425, 429} or self.status >= 500


class ControlClient:
    def __init__(
        self,
        url: str,
        token: str,
        timeout: float,
        max_bytes=8 * 1024 * 1024,
        *,
        allow_insecure_http: bool = False,
    ):
        validate_control_url(url, allow_insecure_http=allow_insecure_http)
        self.max_bytes = max_bytes
        self.client = httpx.AsyncClient(
            base_url=url.rstrip("/") + "/",
            timeout=timeout,
            follow_redirects=False,
            headers={"Authorization": f"Bearer {token}"},
            trust_env=False,
        )

    async def request(self, method, path, *, json=None, content=None, max_bytes=None):
        async with self.client.stream(
            method, path.lstrip("/"), json=json, content=content
        ) as response:
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > (self.max_bytes if max_bytes is None else max_bytes):
                    raise ValueError("control API response exceeds Runner byte limit")
                chunks.append(chunk)
            import json as codec

            try:
                value = codec.loads(b"".join(chunks))
            except ValueError:
                if response.status_code >= 300:
                    raise ApiError(response.status_code, "http_error") from None
                raise ValueError("control API returned invalid JSON") from None
            if response.status_code >= 300:
                raise ApiError(response.status_code, response_code(value))
            return value

    async def artifact(self, artifact_id: str, max_bytes: int) -> bytes:
        chunks = []
        size = 0
        async with self.client.stream("GET", f"v1/artifacts/{artifact_id}/content") as response:
            if response.status_code != 200:
                # Preserve explicit API diagnostics; a 5xx/auth failure does not
                # establish that the assigned evidence is missing.
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ApiError(response.status_code, "http_error")
                    chunks.append(chunk)
                try:
                    code = response_code(json.loads(b"".join(chunks)))
                except ValueError:
                    code = "http_error"
                raise ApiError(response.status_code, code)
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("artifact exceeds Runner byte limit")
                chunks.append(chunk)
        return b"".join(chunks)

    async def close(self):
        await self.client.aclose()
