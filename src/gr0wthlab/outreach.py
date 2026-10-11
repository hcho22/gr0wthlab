"""The outreach workflow (US-ME14): the personal-network ask, one message to each creator the plan names, and at most
one follow-up each, all as Drafts the Founder alone sends.

Before the agent starts, the launcher works out which messages may be offered this run: the ask, when a reviewed
Dispatch request defines the personal-network Source link; a message for each creator in config/sources.json that the
channel plan in Mandu still names; and a follow-up only for a creator whose first message the Founder approved and
recorded as sent, who has not replied, once the waiting period the Founder approved has passed, and only once. What
was sent and who replied is the Founder's record in Mandu (docs/mandu-exchange.md); the run state is rebuilt from
that record and the Review Queue every run, and any difference is repaired in their favor.

After the agent finishes, each Draft is checked (messages.check) and queued only if it passes. A message whose
follow-up is not due, or whose creator replied, is never offered, whatever a Draft says, and an item still open for
it is taken back.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from . import exchange, messages, proposals
from .areas import Areas, Store
from .boundary import ConfigError
from .drafts import Context
from .package import READ
from .queue import APPROVED, Ledger
from .sources import Creator, Snapshot
from .state import OutreachState, Tally, target_key

WORKFLOW = "outreach"
EVIDENCE = "outreach"
FOLDER = (*messages.DRAFTS, "outreach")
NETWORK_KEY = "network"
RULES_PROPOSAL = proposals.PROPOSALS / "outreach-word-lists.md"


def plural(count: int, noun: str) -> str:
    return messages.plural(count, noun)


# Configuration.


@dataclass(frozen=True)
class Settings:
    """config/run.json's outreach: the Source whose link the personal-network ask carries, or None for no ask; the
    days before a follow-up may be offered, unless the Founder's record sets another; and a message's word limit."""

    network_source: str | None
    wait_days: int
    max_words: int


def settings(data: Mapping) -> Settings:
    block = data.get("outreach")
    if not isinstance(block, dict):
        raise ConfigError("config/run.json: outreach must be an object")
    source = block.get("network_ask_source")
    if source is not None and (not isinstance(source, str) or not source):
        raise ConfigError("config/run.json: outreach.network_ask_source must be null or a Source tag")
    numbers = []
    for key, low, high in (("follow_up_wait_days", 1, exchange.MAX_WAIT_DAYS), ("max_message_words", 30, 400)):
        value = block.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ConfigError(f"config/run.json: outreach.{key} must be a whole number from {low} to {high}")
        numbers.append(value)
    return Settings(source, numbers[0], numbers[1])


def package_role(registry: Mapping) -> tuple[str, str] | None:
    """The active Product whose outreach a run prepares, and its channel plan's path in Mandu, which must be one of
    the package sources every run snapshots."""
    for product in registry.get("products", []):
        package = product.get("go_to_market_package") or {}
        block = package.get("outreach")
        if product.get("status") != "active" or not block:
            continue
        path = block.get("channel_plan") if isinstance(block, dict) else None
        covered = isinstance(path, str) and any(
            path == entry.get("path") or (str(entry.get("path", "")).endswith("/") and path.startswith(entry["path"]))
            for entry in package.get("sources") or ()
        )
        if not covered:
            raise ConfigError(f"{product['name']} outreach.channel_plan must be one of its package sources")
        return str(product["name"]), path
    return None


# Before the agent.


@dataclass
class Plan:
    """Everything the run knows about its outreach before the agent starts."""

    product: str
    run: str
    settings: Settings
    plan_path: str
    limits: messages.Limits
    folder: Path
    slots: list[messages.Slot] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # who gets no message this run, and why
    records: dict[str, exchange.Outreach] = field(default_factory=dict)  # the Founder's usable records, by item
    record_problems: list[str] = field(default_factory=list)
    record_lines: list[str] = field(default_factory=list)  # what the records say of each creator
    notes: list[str] = field(default_factory=list)  # where the saved run state disagreed with the records
    problem: str = ""  # why nothing could be prepared at all

    def due(self) -> list[messages.Slot]:
        return [slot for slot in self.slots if slot.required and not slot.approved]


def usable_records(
    records: Sequence[exchange.Outreach], ledger: Ledger, today: date
) -> tuple[dict[str, exchange.Outreach], list[str]]:
    """The Founder's outreach records that name an approved message, and why each other one changes nothing."""
    usable: dict[str, exchange.Outreach] = {}
    problems = []
    for record in records:
        entry = ledger.entries.get(record.item)
        name = f"`outreach/{record.item}.json`"
        if entry is None or entry["kind"] != "message":
            problems.append(f"{name} names no message in the Review Queue")
        elif APPROVED not in (entry["status"], entry.get("decided")):
            problems.append(f"{name} records a message as sent that the Founder has not approved")
        elif record.sent_on > (today + timedelta(days=1)).isoformat():
            problems.append(f"{name} gives a sent_on date that has not come yet")
        else:
            usable[record.item] = record
    return usable, problems


def creator_target(creator: Creator, snapshot: Snapshot | None, plan_path: str, wait_days: int) -> messages.Target:
    """A creator, with what the launcher read of their work this run, or why it read none."""
    source = f"creator:{creator.key}"
    reading = snapshot.reading(source) if snapshot else None
    work = tuple(snapshot.of(source)) if snapshot else ()
    if reading is None:
        problem = f"{creator.name}'s own feed was not read this run"
    elif reading.status != READ:
        problem = f"{creator.name}'s own feed could not be read this run ({reading.detail.rstrip('.')})"
    else:
        problem = "" if work else f"{creator.name}'s own feed held nothing this run"
    return messages.Target(
        messages.CREATOR,
        creator.key,
        creator.name,
        work=work,
        work_problem=problem,
        wait_days=wait_days,
        plan=plan_path,
    )


def prepare(
    repo_root: Path,
    config: Settings,
    registry: Mapping,
    mandu: Path,
    ledger: Ledger,
    snapshot: Snapshot | None,
    creators: Sequence[Creator],
    records: Sequence[exchange.Outreach],
    saved: OutreachState,
    areas: Areas,
    now: datetime,
    run_id: str,
    waitlist_live: bool,
    snapshot_file: str,
) -> tuple[Plan | None, OutreachState]:
    """The run's outreach plan and the run state rebuilt from the Founder's records; None when no active Product has
    a channel plan."""
    found = package_role(registry)
    if found is None:
        return None, saved
    product, plan_path = found
    products = [str(entry["name"]) for entry in registry.get("products", [])]
    entry = next(item for item in registry["products"] if item["name"] == product)
    tags = tuple((entry.get("waitlist") or {}).get("source_tags") or ())
    today = now.astimezone().date()
    links = messages.source_links(repo_root, products, tags)
    site = next((link.split("/", 1)[0] for link, _ in links.values()), "")
    limits = messages.Limits(config.max_words, site, snapshot_file, waitlist_live)
    plan = Plan(product, run_id, config, plan_path, limits, areas.path("drafts", *FOLDER))
    plan.records, plan.record_problems = usable_records(records, ledger, today)
    state = OutreachState()
    if config.network_source is None and not creators:
        return plan, state  # nothing to prepare, so the plan in Mandu need not be read
    try:
        plan_text = (mandu / plan_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        why = getattr(error, "strerror", None) or str(error)
        plan.problem = f"the channel plan `{plan_path}` could not be read ({why}), so no outreach message was prepared"
        return plan, saved

    if config.network_source is not None:
        link, where = links.get(config.network_source, ("", ""))
        if config.network_source not in tags:
            plan.skipped.append(("the personal-network ask", f"`{config.network_source}` is not a Waitlist Source tag"))
        elif not link:
            why = f"no reviewed Dispatch request defines a link for Source `{config.network_source}`"
            plan.skipped.append(("the personal-network ask", why))
        else:
            target = messages.Target(
                messages.NETWORK,
                NETWORK_KEY,
                "your personal network",
                source_link=link,
                link_source=where,
                plan=plan_path,
            )
            plan.slots.append(messages.slot_for(ledger, product, target, plan.folder / "network-ask.md"))

    for creator in creators:
        if creator.name not in plan_text:
            plan.skipped.append((creator.name, f"the channel plan (`{plan_path}`) does not name them"))
            continue
        target = creator_target(creator, snapshot, plan_path, config.wait_days)
        first = messages.slot_for(ledger, product, target, plan.folder / f"creator-{creator.key}.md")
        plan.slots.append(first)
        plan.slots.append(follow_up(plan, creator, target, first, ledger, state, today))
    plan.notes = differences(saved, state)
    return plan, state


def follow_up(
    plan: Plan,
    creator: Creator,
    first_target: messages.Target,
    first: messages.Slot,
    ledger: Ledger,
    state: OutreachState,
    today: date,
) -> messages.Slot:
    """The one follow-up a creator may get, and why it may not be offered now, if it may not."""
    key = f"creator:{creator.key}"
    record = plan.records.get(str(first.approved["id"])) if first.approved else None
    target = messages.Target(
        messages.FOLLOW_UP,
        creator.key,
        creator.name,
        work=first_target.work,
        work_problem=first_target.work_problem,
        plan=first_target.plan,
    )
    path = plan.folder / f"follow-up-{creator.key}.md"
    if first.approved is None:
        target.reason = f"the first message to {creator.name} is not approved yet"
    elif record is None:
        target.reason = f"the first message to {creator.name} is not recorded as sent in Mandu yet"
    else:
        wait = record.wait_days or plan.settings.wait_days
        state.record_contact(key, date.fromisoformat(record.sent_on), wait)
        if record.replied_on:
            state.record_reply(key)
        allowed, why = state.may_follow_up(key, today)
        target.sent_on, target.wait_days = record.sent_on, wait
        entry = state.targets[target_key(key)]
        if record.replied_on:
            why = f"{creator.name} replied on {record.replied_on}; a follow-up goes only to a non-reply"
        target.reason = "" if allowed else why
        replied = f"replied {record.replied_on}" if record.replied_on else "no reply recorded"
        plan.record_lines.append(
            f"{creator.name}: first message sent {record.sent_on}, {replied}; a follow-up may be offered from"
            f" {entry['follow_up_after']} ({plural(wait, 'day')})"
        )
    slot = messages.slot_for(ledger, plan.product, target, path, required=not target.reason)
    if slot.approved and record is not None:
        # The one follow-up is used: nothing further is ever offered for this creator.
        state.targets[target_key(key)]["follow_ups"] = 1
        target.reason = target.reason or "the one follow-up was already approved; no further contact"
    return slot


def differences(saved: OutreachState, rebuilt: OutreachState) -> list[str]:
    """Where the saved run state disagreed with what the Founder's records and the Review Queue say now."""
    changed = sum(
        1 for key in set(saved.targets) | set(rebuilt.targets) if saved.targets.get(key) != rebuilt.targets.get(key)
    )
    if not changed or not saved.targets:
        return []
    return [f"the outreach state differed from Mandu's records for {plural(changed, 'target')}; the records win"]


# The plan's record, for the agent's own check.


def slot_json(slot: messages.Slot, areas: Areas) -> dict[str, object]:
    target = slot.target
    return {
        "purpose": target.purpose,
        "key": target.key,
        "label": target.label,
        "reason": target.reason,
        "source_link": target.source_link,
        "link_source": target.link_source,
        "work": [document.id for document in target.work],
        "work_problem": target.work_problem,
        "wait_days": target.wait_days,
        "sent_on": target.sent_on,
        "plan": target.plan,
        "path": areas.relative(slot.path),
        "required": slot.required,
        **messages.slot_record(slot),
    }


def plan_record(plan: Plan, areas: Areas) -> dict[str, object]:
    """What the launcher fixed for this run's outreach, once, after taking in the Founder's decisions and records and
    before the agent started."""
    return {
        "product": plan.product,
        "plan_path": plan.plan_path,
        "problem": plan.problem,
        "settings": dict(plan.settings.__dict__),
        "limits": dict(plan.limits.__dict__),
        "slots": [slot_json(slot, areas) for slot in plan.slots],
        "skipped": [list(entry) for entry in plan.skipped],
    }


def restore(record: Mapping, snapshot: Snapshot | None, areas: Areas, run_id: str) -> Plan:
    """A plan as the launcher recorded it, for check-work; the standing is never worked out again."""
    limits = messages.Limits(**record["limits"])
    folder = areas.path("drafts", *FOLDER)
    plan = Plan(
        str(record["product"]), run_id, Settings(**record["settings"]), str(record["plan_path"]), limits, folder
    )
    plan.problem = str(record["problem"])
    plan.skipped = [(str(who), str(why)) for who, why in record["skipped"]]
    for entry in record["slots"]:
        work = tuple(snapshot.documents[key] for key in entry["work"] if snapshot and key in snapshot.documents)
        target = messages.Target(
            entry["purpose"],
            entry["key"],
            entry["label"],
            entry["reason"],
            entry["source_link"],
            entry["link_source"],
            work=work,
            work_problem=entry["work_problem"],
            wait_days=entry["wait_days"],
            sent_on=entry["sent_on"],
            plan=entry["plan"],
        )
        path = areas.path(*Path(entry["path"]).parts)
        slot = messages.Slot(target, path, entry["required"], entry["open"], entry["approved"], list(entry["rejected"]))
        plan.slots.append(slot)
    return plan


# After the agent.


@dataclass
class Result:
    outcomes: list[messages.Outcome] = field(default_factory=list)
    published: list[str] = field(default_factory=list)
    record: str | None = None

    @property
    def withdrawn(self) -> list[str]:
        return [outcome.withdrawn for outcome in self.outcomes if outcome.withdrawn]


def take(
    plan: Plan,
    context: Context,
    areas: Areas,
    store: Store,
    ledger: Ledger,
    run_id: str,
    now: datetime,
    products: Sequence[str],
    publish: bool = True,
) -> Result:
    """Check every outreach Draft and queue each that passes; with publish off, only say what a run would do."""
    result = Result()
    for slot in plan.slots:
        outcome = messages.take(slot, context, plan.limits, areas, store, ledger, run_id, now, products, publish)
        if outcome is None:
            continue
        result.outcomes.append(outcome)
        if outcome.status == messages.QUEUED and outcome.item:
            result.published.append(outcome.item)
    if publish and (plan.slots or plan.skipped or plan.record_problems):
        data = {
            "run": run_id,
            "at": now.isoformat(),
            "product": plan.product,
            "channel_plan": plan.plan_path,
            "skipped": [{"who": who, "why": why} for who, why in plan.skipped],
            "records": plan.record_lines,
            "record_problems": plan.record_problems,
            "messages": [messages.record(outcome) for outcome in result.outcomes],
        }
        path = store.path("evidence", EVIDENCE, f"{run_id}.json")
        store.write_json(path, data)
        result.record = store.relative(path)
    return result


def kind_of(target: messages.Target) -> str:
    return {
        messages.NETWORK: "ask",
        messages.CREATOR: "first message",
        messages.FOLLOW_UP: "the one follow-up",
    }[target.purpose]


def gaps(plan: Plan | None, result: Result | None, problem: str, agent_finished: bool) -> list[str]:
    """Why the outreach Drafts are incomplete this run. A blocked Draft is the check working, not a gap."""
    if plan is None:
        return [problem] if problem else []
    found = [plan.problem] if plan.problem else []
    found += [f"{who}: {why}" for who, why in plan.skipped if who == "the personal-network ask"]
    if result is None:
        found.append(problem or "the Drafts were not taken in")
    else:
        missing = [o.target.label for o in result.outcomes if o.status == messages.MISSING]
        if missing:
            found.append(f"no Draft for {', '.join(missing)}")
    if plan.due() and not agent_finished:
        found.append("the agent did not finish")
    return found


def tally(plan: Plan | None, result: Result | None, problem: str, agent_finished: bool) -> Tally:
    """What the outreach workflow checked and acted on this run."""
    incomplete = "; ".join(gaps(plan, result, problem, agent_finished))
    if plan is None:
        return Tally(WORKFLOW, 0, 0, problem or "no active Product has a channel plan", incomplete)
    if result is None:
        return Tally(WORKFLOW, 0, 0, plan.problem or problem or "no message was taken in", incomplete)
    note = ", ".join(messages.counts(result.outcomes)) or "no message was due"
    acted = len(result.published) + len(result.withdrawn)
    return Tally(
        WORKFLOW, len(result.outcomes), acted, f"{plural(len(result.outcomes), 'message')}: {note}", incomplete
    )


# What the agent, the run report, and the Founder are told.


def brief_lines(plan: Plan | None, context: Context | None, mandu: Path, ledger_root: Path, check: str) -> list[str]:
    lines = ["## Outreach", ""]
    if plan is None:
        return lines + ["No active Product has a channel plan, so no outreach message is prepared."]
    if plan.problem:
        return lines + [f"{plan.problem[0].upper()}{plan.problem[1:]}; write no outreach Draft this run."]
    lines += [
        "Write each message below as the file its row names, with your file-editing tool, in the format the task"
        f" definition gives. Check them before you finish: `{check}`. The launcher queues a message only from a Draft"
        " that passes every check; the Founder alone sends it.",
        "",
        "| For | Draft file | In the Review Queue |",
        "| --- | --- | --- |",
    ]
    for slot in plan.slots:
        who = f"{slot.target.label}, {kind_of(slot.target)}"
        lines.append(f"| {who} | `{slot.path}` | {slot.standing()} |")
    if not plan.slots:
        lines.append("| - | - | No message is due this run. |")
    lines += ["", f"- The plan for all of them, read it first: `{mandu / plan.plan_path}`."]
    for slot in plan.slots:
        target = slot.target
        if target.purpose == messages.NETWORK:
            lines.append(
                f"- The ask carries the personal-network Source link `{target.source_link}`, exactly as"
                f" `{target.link_source}` defines it, once in the message and once in the line to forward, and no other"
                " link. Never invent or alter a link."
            )
        elif target.purpose == messages.CREATOR:
            if target.work:
                ids = ", ".join(f"`{document.id}`" for document in target.work[:5])
                lines.append(
                    f"- {target.label}: the launcher read {plural(len(target.work), 'piece')} of their work this run"
                    f" ({ids} in `{ledger_root / plan.limits.snapshot}`). Cite one by its link as `work:`, only if it"
                    " gives an honest reason to write now; otherwise write `work: none`."
                )
            else:
                lines.append(
                    f"- {target.label}: {target.work_problem}. Write `work: none`; the item will say no hook was"
                    " found. Never write as if you had seen their recent work."
                )
    lines.append(
        f"- A message is at most {plan.limits.max_words} words, holds no email address, and names no competitor."
        f" A message to a creator offers one of: {', '.join(messages.OFFERS)}."
    )
    if context is not None:
        lines += messages.describe_rules(context, creator=True)
    lines += [f"- Not prepared: {who}: {why}." for who, why in plan.skipped]
    return lines


def report_lines(plan: Plan | None, result: Result | None, filing: str, problem: str = "") -> list[str]:
    lines = ["## Outreach", ""]
    if plan is None:
        return lines + [problem or "No active Product has a channel plan, so no outreach message was prepared."]
    if plan.problem:
        lines.append(f"{plan.problem[0].upper()}{plan.problem[1:]}.")
    lines += [f"- Not prepared: {who}: {why}." for who, why in plan.skipped]
    lines += [f"- From the Founder's records in Mandu: {line}." for line in plan.record_lines]
    lines += [f"- A record in Mandu could not be used: {line}." for line in plan.record_problems]
    if filing:
        lines.append(f"- Proposed loss-framing and sponsorship lists: {filing}")
    if result is None:
        return lines + ["", problem or "The outreach Drafts were not taken in this run."]
    if result.record:
        lines.append(f"- Every check of every message: `{result.record}`.")
    if not result.outcomes:
        return lines + ["", "No message was due this run."]
    lines += ["", "| For | Message | Result | Detail |", "| --- | --- | --- | --- |"]
    for outcome in result.outcomes:
        detail = messages.outcome_detail(outcome).replace("|", "\\|")
        lines.append(f"| {outcome.target.label} | {kind_of(outcome.target)} | {outcome.status} | {detail} |")
    return lines


def notice_section(plan: Plan | None, result: Result | None, day_text: str) -> tuple[int, str, str] | None:
    """The outreach messages not offered, any taken back, and any record of the Founder's that could not be used."""
    if plan is None or result is None:
        return None
    lines = []
    blocked = [outcome for outcome in result.outcomes if outcome.status == messages.BLOCKED]
    missing = [outcome for outcome in result.outcomes if outcome.status == messages.MISSING]
    taken_back = [outcome for outcome in result.outcomes if outcome.withdrawn and outcome.status != messages.BLOCKED]
    if blocked:
        lines.append("These outreach Drafts were not offered for approval; each line names what blocked it:")
        for outcome in blocked:
            what = f"{outcome.target.label}, {kind_of(outcome.target)}"
            lines.append(f"- {what} (`{outcome.draft}`): {'; '.join(messages.failing(outcome))}")
            if outcome.withdrawn:
                lines.append(f"- The open `{outcome.withdrawn}` is withdrawn, since its Draft no longer passes.")
    for outcome in missing:
        lines.append(
            f"- {outcome.target.label}, {kind_of(outcome.target)}: no Draft was written, so nothing is offered."
        )
    for outcome in taken_back:
        lines.append(f"- The open `{outcome.withdrawn}` is withdrawn: {outcome.detail}.")
    for problem in plan.record_problems:
        lines.append(f"- A record in Mandu could not be used, so it changed nothing: {problem}.")
    if not lines:
        return None
    count = len(blocked) + len(missing) + len(taken_back) + len(plan.record_problems)
    return count, f"{plural(count, 'outreach message or record')} needs a look on {day_text}", "\n".join(lines)
