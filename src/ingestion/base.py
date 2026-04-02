from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class DependencyError(RuntimeError):
    """Raised when an external dependency request fails."""


@dataclass(slots=True)
class JsonHttpResponse:
    status_code: int
    payload: Any


Transport = Callable[[str, Mapping[str, Any] | None], JsonHttpResponse]


def default_json_transport(url: str, params: Mapping[str, Any] | None = None) -> JsonHttpResponse:
    query_url = url
    if params:
        filtered_params = {key: value for key, value in params.items() if value is not None}
        if filtered_params:
            query_url = f"{url}?{urlencode(filtered_params)}"

    request = Request(query_url, headers={"User-Agent": "crypto-trading-data-miner/0.1"})
    try:
        with urlopen(request, timeout=30) as response:
            return JsonHttpResponse(
                status_code=response.status,
                payload=json.loads(response.read().decode("utf-8")),
            )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DependencyError(f"http error {exc.code} for {query_url}: {detail}") from exc
    except URLError as exc:
        raise DependencyError(f"request failed for {query_url}: {exc.reason}") from exc


class JsonHttpClient:
    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport or default_json_transport

    def get_json(self, url: str, params: Mapping[str, Any] | None = None) -> Any:
        response = self._transport(url, params)
        if response.status_code >= 400:
            raise DependencyError(f"http error {response.status_code} for {url}")
        return response.payload
