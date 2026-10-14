"""Package-change proposals the launcher files itself, once each: a reviewed text in src/proposals/ that firstmate
wrote for the Founder to decide, such as the brand lint's word lists (F1), or that says in the package what the
Founder decided, such as the floor counting views (ADR 0004).

Each is queued at most once, under the identifier it first got, and never re-asked whatever the Founder decides: the
ledger entry's origin names the text it came from, which also keeps any item the agent writes from superseding it
(queue.check_incoming). A proposal whose keys Mandu's file already holds is not filed at all. The text is a one-time
source only; no check ever reads it, so the lint keeps exactly one rule source, Mandu.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import exchange
from .areas import Store
from .queue import Ledger

PROPOSALS = Path("src/proposals")
BRAND_RULES = PROPOSALS / "brand-rules-word-lists.md"
# The Founder's decision of 2026-10-14 that the 200-impression floor counts each platform's views, for Mandu to put in
# read-the-results.md (ADR 0004).
VIEWS_FLOOR = PROPOSALS / "read-the-results-views-floor.md"
ORIGIN = "proposal"
FILED = "filed"
QUEUED_BEFORE = "queued before"
IN_MANDU = "already in Mandu"
UNUSABLE = "unusable"


@dataclass(frozen=True)
class Filing:
    source: str
    status: str
    item: str | None
    detail: str
    adds: tuple[str, ...] = ()


def item_text(text: str) -> str:
    """The item, without the one-line header that names the text it was adapted from."""
    lines = text.splitlines()
    while lines and lines[0].startswith("<!--"):
        lines.pop(0)
    return "\n".join(lines) + "\n"


def proposed_keys(body: str) -> tuple[str, ...]:
    """The keys the proposal's JSON block adds."""
    match = re.search(r"```json\n(.*?)\n```", body, re.DOTALL)
    try:
        data = json.loads(match.group(1)) if match else None
    except ValueError:
        data = None
    return tuple(data) if isinstance(data, dict) else ()


def file_once(
    repo_root: Path,
    source: Path,
    target: Mapping | None,
    store: Store,
    ledger: Ledger,
    products: Sequence[str],
    run_id: str,
    now: datetime,
    seen: dict[str, str],
) -> Filing:
    """Queue the proposal unless it was ever queued, or the file it changes already holds every key it adds.

    target is that file's current content in Mandu, or None when it could not be read, in which case the proposal is
    still filed, since nothing shows it applied.
    """
    relative = str(source)
    origin = f"{ORIGIN}/{source.stem}"
    for entry in ledger.entries.values():
        if entry.get("origin") == origin:
            decided = entry.get("decided") or entry["status"]
            return Filing(relative, QUEUED_BEFORE, str(entry["id"]), str(decided))
    try:
        text = item_text((repo_root / source).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        return Filing(relative, UNUSABLE, None, f"could not be read ({error})")
    check = exchange.check_item(text, products)
    if check.item is None or check.item.kind != "package-change-proposal":
        return Filing(relative, UNUSABLE, None, "; ".join(check.problems) or "it is not a package-change proposal")
    adds = proposed_keys(check.item.body)
    if adds and isinstance(target, Mapping) and all(key in target for key in adds):
        return Filing(relative, IN_MANDU, None, "Mandu's file already holds every key it adds", adds)
    fingerprint = exchange.item_hash(check.item)
    if fingerprint in seen:
        return Filing(relative, QUEUED_BEFORE, seen[fingerprint], "the same proposal is already queued", adds)
    identifier = ledger.publish(store, check.item, source.stem, run_id, now, origin=origin)
    seen[fingerprint] = identifier
    return Filing(relative, FILED, identifier, "queued this run", adds)


def describe(filing: Filing, ledger: Ledger) -> str:
    """One line on where the proposal stands, for the run report."""
    entry = ledger.entries.get(filing.item or "")
    if filing.status == IN_MANDU:
        return f"`{filing.source}`: not filed; {filing.detail}."
    if filing.status == UNUSABLE:
        return f"`{filing.source}`: could not be filed: {filing.detail}."
    if entry is None:
        return f"`{filing.source}`: {filing.detail}."
    status = str(entry.get("decided") or entry["status"])
    where = {
        "open": "open for the Founder's decision",
        "rejected": f"rejected: {entry.get('reason', 'no reason recorded')}",
        "superseded": f"replaced by `{entry.get('superseded_by')}`",
    }.get(status, status)
    when = "filed this run" if filing.status == FILED else "filed earlier, never re-asked"
    return f"`{filing.source}` is `{entry['id']}`, {when}: {where.rstrip('.')}."
