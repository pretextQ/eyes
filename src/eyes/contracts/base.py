from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

SCHEMA_VERSION = "1.0"

SENSITIVE_KEYS = {
    "password",
    "token",
    "api_key",
    "apikey",
    "api_token",
    "authorization",
    "proxy_authorization",
    "secret",
    "access_token",
    "refresh_token",
    "auth_token",
    "client_secret",
    "private_key",
    "x_api_key",
    "x_auth_token",
    "x_access_token",
    "cookie",
    "set_cookie",
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["1.0"] = SCHEMA_VERSION


type Payload = dict[str, JsonValue]
