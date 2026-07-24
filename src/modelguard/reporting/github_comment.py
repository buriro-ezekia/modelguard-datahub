"""Idempotent GitHub pull-request comment publication."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from urllib import error, parse, request

if TYPE_CHECKING:
    from modelguard.reporting.publication import ChannelReceipt, PublicationPlan

_API_VERSION = "2026-03-10"
HttpTransport = Callable[[str, str, dict[str, str], dict[str, Any] | None], Any]


class GitHubCommentWriter:
    """Publish one stable ModelGuard comment without creating duplicates."""

    def __init__(
        self,
        *,
        mode: str = "fixture",
        token: str | None = None,
        fixture_state: Path | None = None,
        api_url: str = "https://api.github.com",
        transport: HttpTransport | None = None,
    ) -> None:
        if mode not in {"off", "fixture", "live"}:
            raise ValueError(f"unsupported GitHub publication mode: {mode}")
        self.mode = mode
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.fixture_state = fixture_state
        self.api_url = api_url.rstrip("/")
        self.transport = transport or _json_request

    def publish(self, plan: PublicationPlan, *, apply: bool) -> ChannelReceipt:
        from modelguard.reporting.publication import ChannelReceipt

        if self.mode == "off":
            return ChannelReceipt(
                channel="github",
                mode="off",
                status="skipped",
                action="disabled",
            )
        if not apply:
            return ChannelReceipt(
                channel="github",
                mode=self.mode,
                status="planned",
                action="create_or_update_comment",
                details={"marker": plan.marker},
            )
        try:
            if self.mode == "fixture":
                return self._publish_fixture(plan)
            return self._publish_live(plan)
        except Exception as exc:
            return ChannelReceipt(
                channel="github",
                mode=self.mode,
                status="failed",
                action="error",
                details={"warnings": [f"GitHub publication failed: {exc}"]},
            )

    def _publish_fixture(self, plan: PublicationPlan) -> ChannelReceipt:
        from modelguard.reporting.publication import ChannelReceipt

        state_path = self.fixture_state or Path("artifacts/github_publication_state.json")
        state = _load_state(state_path, {"comments": []})
        comments = state.setdefault("comments", [])
        existing = next(
            (item for item in comments if item.get("marker") == plan.marker),
            None,
        )
        if existing is None:
            identifier = f"fixture-comment-{len(comments) + 1}"
            existing = {
                "id": identifier,
                "marker": plan.marker,
                "body": plan.github_comment,
                "url": (
                    f"https://github.com/{plan.repository}/pull/"
                    f"{plan.pull_request}#issuecomment-{identifier}"
                ),
            }
            comments.append(existing)
            action = "created"
        elif existing.get("body") == plan.github_comment:
            action = "noop"
        else:
            existing["body"] = plan.github_comment
            action = "updated"
        _save_state(state_path, state)
        return ChannelReceipt(
            channel="github",
            mode="fixture",
            status="noop" if action == "noop" else "published",
            action=action,
            external_id=str(existing["id"]),
            url=str(existing["url"]),
            details={"state_path": str(state_path)},
        )

    def _publish_live(self, plan: PublicationPlan) -> ChannelReceipt:
        from modelguard.reporting.publication import ChannelReceipt

        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is required for live publication")
        owner, repository = plan.repository.split("/", 1)
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": "modelguard-datahub",
        }
        comments_url = (
            f"{self.api_url}/repos/{parse.quote(owner)}/{parse.quote(repository)}"
            f"/issues/{plan.pull_request}/comments?per_page=100"
        )
        comments = self.transport("GET", comments_url, headers, None)
        if not isinstance(comments, list):
            raise RuntimeError("GitHub comment listing returned an invalid response")
        existing = next(
            (
                item
                for item in comments
                if isinstance(item, dict) and plan.marker in str(item.get("body") or "")
            ),
            None,
        )
        if existing is not None and existing.get("body") == plan.github_comment:
            return ChannelReceipt(
                channel="github",
                mode="live",
                status="noop",
                action="noop",
                external_id=str(existing.get("id")),
                url=_optional_text(existing.get("html_url")),
            )
        payload = {"body": plan.github_comment}
        if existing is None:
            endpoint = (
                f"{self.api_url}/repos/{parse.quote(owner)}/{parse.quote(repository)}"
                f"/issues/{plan.pull_request}/comments"
            )
            result = self.transport("POST", endpoint, headers, payload)
            action = "created"
        else:
            endpoint = f"{self.api_url}/repos/{owner}/{repository}/issues/comments/{existing['id']}"
            result = self.transport("PATCH", endpoint, headers, payload)
            action = "updated"
        if not isinstance(result, dict) or not result.get("id"):
            raise RuntimeError("GitHub comment write returned an invalid response")
        return ChannelReceipt(
            channel="github",
            mode="live",
            status="published",
            action=action,
            external_id=str(result["id"]),
            url=_optional_text(result.get("html_url")),
        )


def _json_request(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(
        url,
        data=body,
        method=method,
        headers={**headers, "Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode()
    except error.HTTPError as exc:
        message = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {message[:500]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc
    return json.loads(raw) if raw else {}


def _load_state(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read fixture state {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"fixture state {path} must contain a JSON object")
    return value


def _save_state(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
