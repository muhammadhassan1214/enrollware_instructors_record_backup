import requests
from urllib.parse import urljoin
from .api_headers import get_headers
from typing import Any, Dict, Iterable, Optional, Tuple, Union


DEFAULT_BASE_URL = "https://api.enrollnationwide.com/api/"


class APIClient:
    """Lightweight client to hit any enrollnationwide API endpoint."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.headers.update(get_headers())

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        expected_status: Union[int, Iterable[int]] = (200, 201),
    ) -> Any:
        url = urljoin(self.base_url, endpoint.lstrip("/"))
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                data=payload,
                json=json,
                params=params,
                files=files,
                headers=headers,
            )
            response.raise_for_status()

            expected: Tuple[int, ...] = tuple(expected_status) if isinstance(expected_status, Iterable) else (expected_status,)
            if expected and response.status_code not in expected:
                raise requests.HTTPError(
                    f"Unexpected status {response.status_code} for {url}", response=response
                )

            return self._parse_response(response)
        except requests.HTTPError as exc:
            response = exc.response
            detail = ""
            if response is not None:
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        detail = str(payload.get("message") or payload.get("error") or payload)
                    else:
                        detail = str(payload)
                except ValueError:
                    detail = response.text.strip()
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"API request to {url} failed{suffix}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"API request to {url} failed") from exc

    def get(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("PUT", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("DELETE", endpoint, **kwargs)

    @staticmethod
    def _parse_response(response: requests.Response) -> Any:
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text
