"""Optional Zoho CRM and WorkDrive context sources.

The sources are bounded, read-only retrieval adapters. Zoho OAuth remains the
authorization authority; LLMSlim neither persists tokens nor broadens scopes.
Every returned item is untrusted RAG provenance by default.
"""

from __future__ import annotations

import inspect
import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence, Union

from ..core import ContextRole
from ..planning.models import ContextItem, ContextKind

TokenProvider = Callable[[], Union[str, Awaitable[str]]]
RecordRedactor = Callable[[Mapping[str, Any]], Mapping[str, Any]]
ContentLoader = Callable[[Mapping[str, Any]], Awaitable[str]]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_DATA_CENTERS = {
    "US": "https://www.zohoapis.com",
    "EU": "https://www.zohoapis.eu",
    "IN": "https://www.zohoapis.in",
    "AU": "https://www.zohoapis.com.au",
    "JP": "https://www.zohoapis.jp",
    "CA": "https://www.zohoapis.ca",
    "SA": "https://www.zohoapis.sa",
}

DEFAULT_CRM_FIELDS: Dict[str, Sequence[str]] = {
    "Deals": ("Deal_Name", "Stage", "Amount", "Closing_Date", "Account_Name", "Modified_Time"),
    "Accounts": ("Account_Name", "Industry", "Phone", "Website", "Modified_Time"),
    "Contacts": ("Full_Name", "Account_Name", "Email", "Phone", "Modified_Time"),
    "Tasks": ("Subject", "Status", "Due_Date", "What_Id", "Who_Id", "Modified_Time"),
    "Events": ("Event_Title", "Start_DateTime", "End_DateTime", "What_Id", "Modified_Time"),
    "Calls": ("Subject", "Call_Status", "Call_Start_Time", "What_Id", "Modified_Time"),
}


class ZohoIntegrationError(RuntimeError):
    pass


class ZohoAuthenticationError(ZohoIntegrationError):
    pass


class ZohoRateLimitError(ZohoIntegrationError):
    pass


class _ZohoSourceBase:
    def __init__(
        self,
        *,
        access_token: Optional[str] = None,
        token_provider: Optional[TokenProvider] = None,
        data_center: str = "US",
        timeout_seconds: float = 20.0,
        client: Optional[Any] = None,
    ) -> None:
        if bool(access_token) == bool(token_provider):
            raise ValueError("provide exactly one of access_token or token_provider")
        dc = data_center.upper()
        if dc not in _DATA_CENTERS:
            raise ValueError("unsupported Zoho data center: " + data_center)
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._access_token = access_token
        self._token_provider = token_provider
        self._api_domain = _DATA_CENTERS[dc]
        self._owns_client = client is None
        if client is None:
            try:
                import httpx
            except ImportError as exc:  # pragma: no cover
                raise ImportError(
                    'Zoho sources require the optional extra: pip install "llmslim[zoho]"'
                ) from exc
            client = httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False)
        self._client = client

    async def _token(self) -> str:
        if self._access_token:
            return self._access_token
        assert self._token_provider is not None
        value = self._token_provider()
        token = await value if inspect.isawaitable(value) else value
        if not isinstance(token, str) or not token:
            raise ZohoAuthenticationError("Zoho token provider returned no token")
        return token

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> Mapping[str, Any]:
        token = await self._token()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = "Zoho-oauthtoken " + token
        headers.setdefault("Accept", "application/json")
        try:
            response = await self._client.request(
                method, self._api_domain + path, headers=headers, **kwargs
            )
        except Exception as exc:
            raise ZohoIntegrationError(
                f"Zoho request transport failed ({type(exc).__name__})"
            ) from None
        status = int(getattr(response, "status_code", 0))
        if status in {401, 403}:
            raise ZohoAuthenticationError("Zoho authorization failed")
        if status == 429:
            raise ZohoRateLimitError("Zoho API rate limit exceeded")
        if status == 204:
            return {"data": []}
        if status < 200 or status >= 300:
            raise ZohoIntegrationError(f"Zoho API request failed with HTTP {status}")
        try:
            payload = response.json()
        except Exception:
            raise ZohoIntegrationError("Zoho API returned malformed JSON") from None
        if not isinstance(payload, Mapping):
            raise ZohoIntegrationError("Zoho API returned a non-object response")
        return payload

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(api_domain={self._api_domain!r}, credentials=<redacted>)"


class ZohoCRMContextSource(_ZohoSourceBase):
    """Bounded read-only Zoho CRM v8 search/COQL context source."""

    source_id = "zoho:crm"

    def __init__(
        self,
        *,
        modules: Sequence[str] = ("Deals", "Accounts", "Contacts", "Tasks", "Events", "Calls"),
        field_allowlists: Optional[Mapping[str, Sequence[str]]] = None,
        max_records: int = 25,
        redactor: Optional[RecordRedactor] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if not 1 <= max_records <= 200:
            raise ValueError("max_records must be between 1 and 200")
        self.modules = tuple(_validated_identifier(module, "module") for module in modules)
        supplied = field_allowlists or DEFAULT_CRM_FIELDS
        self.field_allowlists = {
            _validated_identifier(module, "module"): tuple(
                _validated_identifier(field, "field") for field in fields
            )
            for module, fields in supplied.items()
        }
        missing = [module for module in self.modules if module not in self.field_allowlists]
        if missing:
            raise ValueError("field allowlist required for modules: " + ", ".join(missing))
        self.max_records = max_records
        self.redactor = redactor

    async def search(self, query: str, limit: int = 10) -> Sequence[ContextItem]:
        bounded = min(_bounded_limit(limit), self.max_records)
        if not query.strip():
            raise ValueError("Zoho CRM search query must be non-empty")
        results: List[ContextItem] = []
        for module in self.modules:
            remaining = bounded - len(results)
            if remaining <= 0:
                break
            fields = self.field_allowlists[module]
            payload = await self._request_json(
                "GET",
                f"/crm/v8/{module}/search",
                params={"word": query, "per_page": remaining, "fields": ",".join(fields)},
            )
            records = payload.get("data", [])
            if not isinstance(records, list):
                raise ZohoIntegrationError("Zoho CRM data must be an array")
            for record in records[:remaining]:
                if not isinstance(record, Mapping):
                    continue
                results.append(self._record_item(module, record, len(results)))
        return tuple(results)

    async def fetch_record(self, module: str, record_id: str) -> Optional[ContextItem]:
        module = _validated_identifier(module, "module")
        if module not in self.field_allowlists:
            raise ValueError("module is not configured in the field allowlist")
        if not record_id or not re.fullmatch(r"[A-Za-z0-9_-]+", record_id):
            raise ValueError("record_id contains unsupported characters")
        fields = self.field_allowlists[module]
        payload = await self._request_json(
            "GET",
            f"/crm/v8/{module}/{record_id}",
            params={"fields": ",".join(fields)},
        )
        records = payload.get("data", [])
        if not isinstance(records, list) or not records:
            return None
        record = records[0]
        if not isinstance(record, Mapping):
            raise ZohoIntegrationError("Zoho CRM record must be an object")
        return self._record_item(module, record, 0)

    async def query_equal(
        self,
        module: str,
        equals: Mapping[str, Any],
        *,
        fields: Optional[Sequence[str]] = None,
        limit: int = 10,
    ) -> Sequence[ContextItem]:
        """Run safely constructed read-only COQL equality criteria."""

        module = _validated_identifier(module, "module")
        allowed = self.field_allowlists.get(module)
        if allowed is None:
            raise ValueError("module is not configured in the field allowlist")
        chosen = tuple(fields or allowed)
        if not chosen or any(field not in allowed for field in chosen):
            raise ValueError("COQL fields must be a non-empty subset of the field allowlist")
        if not equals or any(field not in allowed for field in equals):
            raise ValueError("COQL equality criteria must use allowlisted fields")
        bounded = min(_bounded_limit(limit), self.max_records)
        criteria = " and ".join(
            f"{_validated_identifier(field, 'field')} = '{_coql_literal(value)}'"
            for field, value in sorted(equals.items())
        )
        query = (
            f"select {', '.join(chosen)} from {module} where {criteria} "
            f"limit 0, {bounded}"
        )
        payload = await self._request_json(
            "POST", "/crm/v8/coql", json={"select_query": query}
        )
        records = payload.get("data", [])
        if not isinstance(records, list):
            raise ZohoIntegrationError("Zoho CRM COQL data must be an array")
        return tuple(
            self._record_item(module, record, index)
            for index, record in enumerate(records[:bounded])
            if isinstance(record, Mapping)
        )

    def _record_item(
        self, module: str, record: Mapping[str, Any], index: int
    ) -> ContextItem:
        fields = self.field_allowlists[module]
        safe = {field: record[field] for field in fields if field in record}
        if "id" in record:
            safe["id"] = record["id"]
        if self.redactor is not None:
            safe = dict(self.redactor(safe))
        record_id = str(record.get("id", index))
        return ContextItem(
            item_id=f"zoho-crm:{module}:{record_id}",
            content=json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str),
            kind=ContextKind.RAG_DOCUMENT,
            role=ContextRole.RAG,
            source=self.source_id,
            metadata={"module": module, "record_id": record_id},
        )


class ZohoWorkDriveContextSource(_ZohoSourceBase):
    """Bounded WorkDrive v1 metadata/content search source."""

    source_id = "zoho:workdrive"

    def __init__(
        self,
        team_id: str,
        *,
        parent_id: Optional[str] = None,
        max_records: int = 25,
        content_loader: Optional[ContentLoader] = None,
        redactor: Optional[RecordRedactor] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if not team_id or not re.fullmatch(r"[A-Za-z0-9_-]+", team_id):
            raise ValueError("team_id contains unsupported characters")
        if parent_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]+", parent_id):
            raise ValueError("parent_id contains unsupported characters")
        if not 1 <= max_records <= 200:
            raise ValueError("max_records must be between 1 and 200")
        self.team_id = team_id
        self.parent_id = parent_id
        self.max_records = max_records
        self.content_loader = content_loader
        self.redactor = redactor

    async def search(self, query: str, limit: int = 10) -> Sequence[ContextItem]:
        bounded = min(_bounded_limit(limit), self.max_records)
        if not query.strip():
            raise ValueError("Zoho WorkDrive search query must be non-empty")
        params: Dict[str, Any] = {"search[all]": query, "page[limit]": bounded}
        if self.parent_id:
            params["filter[parentId]"] = self.parent_id
        payload = await self._request_json(
            "GET", f"/workdrive/api/v1/teams/{self.team_id}/records", params=params
        )
        records = payload.get("data", [])
        if not isinstance(records, list):
            raise ZohoIntegrationError("Zoho WorkDrive data must be an array")
        items: List[ContextItem] = []
        for index, record in enumerate(records[:bounded]):
            if not isinstance(record, Mapping):
                continue
            attributes = record.get("attributes", {})
            if not isinstance(attributes, Mapping):
                attributes = {}
            safe = {
                key: attributes[key]
                for key in (
                    "name",
                    "description",
                    "type",
                    "extn",
                    "modified_time",
                    "created_time",
                    "permalink",
                    "parent_id",
                )
                if key in attributes
            }
            if self.redactor is not None:
                safe = dict(self.redactor(safe))
            loaded = await self.content_loader(record) if self.content_loader else ""
            content = loaded.strip() or json.dumps(
                safe, ensure_ascii=False, sort_keys=True, default=str
            )
            record_id = str(record.get("id", index))
            items.append(
                ContextItem(
                    item_id=f"zoho-workdrive:{record_id}",
                    content=content,
                    kind=ContextKind.RAG_DOCUMENT,
                    role=ContextRole.RAG,
                    source=self.source_id,
                    metadata={
                        "record_id": record_id,
                        "team_id": self.team_id,
                        "content_loaded": bool(loaded.strip()),
                    },
                )
            )
        return tuple(items)


def _validated_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Zoho {label} contains unsupported characters: {value!r}")
    return value


def _bounded_limit(value: int) -> int:
    if not 1 <= value <= 200:
        raise ValueError("Zoho result limit must be between 1 and 200")
    return value


def _coql_literal(value: Any) -> str:
    # Backslash-escape only within a quoted literal constructed by this module;
    # identifiers are independently allowlisted and validated.
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


__all__ = [
    "DEFAULT_CRM_FIELDS",
    "ZohoAuthenticationError",
    "ZohoCRMContextSource",
    "ZohoIntegrationError",
    "ZohoRateLimitError",
    "ZohoWorkDriveContextSource",
]
