"""The outreach workflow (US-ME14): the personal-network ask, one message to each creator the plan names, and at most
one follow-up each, all as Drafts the Founder alone sends.

Before the agent starts, the launcher works out which messages may be offered this run: the ask, when a reviewed
Dispatch request defines the personal-network Source link; a message for each creator in config/run.json that the
channel plan in Mandu still names; and a follow-up only for a creator whose first message the Founder approved and
recorded as sent, who has not replied, once the waiting period the Founder approved has passed, and only once. What
was sent and who replied is the Founder's outreach record, made on the sitting page (founder.py); the run state is
rebuilt from that record and the Review Queue every run, and any difference is repaired in their favor.

After the agent finishes, each Draft is checked (messages.check) and queued only if it passes. A message whose
follow-up is not due, or whose creator replied, is never offered, whatever a Draft says, and an item still open for
it is taken back. Only a record that could be read takes an item back: a follow-up whose record of the first message
is missing or could not be used is neither offered nor taken back that run, and an open one stands (queue.stands).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from . import exchange, founder, messages, proposals
from .areas import Areas, Store
from .boundary import FOUNDER, ConfigError
from .drafts import Context
from .exchange import plural
from .queue import APPROVED, Ledger, Stands, stands
from .state import OutreachState, Tally, target_key

WORKFLOW = "outreach"
EVIDENCE = "outreach"
FOLDER = (*messages.DRAFTS, "outreach")
NETWORK_KEY = "network"
RECORDS = f"{FOUNDER}/{founder.OUTREACH}"  # where the Founder's outreach records are, under ledger/
RULES_PROPOSAL = proposals.PROPOSALS / "outreach-word-lists.md"


# Configuration.


@dataclass(frozen=True)
class Creator:
    """A creator the plan may name: the key their Draft file and their items are named for, and their name."""

    key: str
    name: str


@dataclass(frozen=True)
class Settings:
    """config/run.json's outreach: the Source whose link the personal-network ask carries, or None for no ask; the
    days before a follow-up may be offered, unless the Founder's record sets another; and the creators a run may
    write to."""

    network_source: str | None
    wait_days: int
    creators: tuple[Creator, ...]


def settings(data: Mapping) -> Settings:
    block = data.get("outreach")
    if not isinstance(block, dict):
        raise ConfigError("config/run.json: outreach must be an object")
    source = block.get("network_ask_source")
    if source is not None and (not isinstance(source, str) or not source):
        raise ConfigError("config/run.json: outreach.network_ask_source must be null or a Source tag")
    wait = block.get("follow_up_wait_days")
    if isinstance(wait, bool) or not isinstance(wait, int) or not 1 <= wait <= exchange.MAX_WAIT_DAYS:
        raise ConfigError(
            f"config/run.json: outreach.follow_up_wait_days must be a whole number from 1 to {exchange.MAX_WAIT_DAYS}"
        )
    listed = block.get("creators")
    if not isinstance(listed, list):
        raise ConfigError("config/run.json: outreach.creators must be a list")
    creators = []
    for entry in listed:
        key, name = (entry.get("key"), entry.get("name")) if isinstance(entry, dict) else (None, None)
        if not isinstance(key, str) or not exchange.SLUG_PATTERN.fullmatch(key):
            raise ConfigError("config/run.json: each of outreach.creators needs a lowercase-with-hyphens key")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"config/run.json: outreach.creators {key} needs a name")
        creators.append(Creator(key, name.strip()))
    if len({creator.key for creator in creators}) != len(creators):
        raise ConfigError("config/run.json: outreach.creators keys must be distinct")
    return Settings(source, wait, tuple(creators))


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


@dataclass(frozen=True)
class Records:
    """The Founder's outreach records as a run read them from ledger/founder/outreach/: those in the format, why each
    other file there could not be used, by its name, and why the folder could not be read, if it could not."""

    read: tuple[exchange.Outreach, ...] = ()
    unusable: Mapping[str, str] = field(default_factory=dict)
    failure: str = ""


@dataclass
class Plan:
    """Everything the run knows about its outreach before the agent starts."""

    product: str
    run: str
    plan_path: str
    limits: messages.Limits
    folder: Path
    slots: list[messages.Slot] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # who gets no message this run, and why
    records: dict[str, exchange.Outreach] = field(default_factory=dict)  # the Founder's usable records, by item
    record_problems: dict[str, str] = field(default_factory=dict)  # why a record changes nothing, by its item
    records_failure: str = ""  # why none of the records could be read
    record_lines: list[str] = field(default_factory=list)  # what the records say of each creator
    unread: list[tuple[str, str]] = field(default_factory=list)  # whose follow-up no record could settle, and why
    stood: list[Stands] = field(default_factory=list)  # each open follow-up among them, left as it is
    problem: str = ""  # why nothing could be prepared at all

    def due(self) -> list[messages.Slot]:
        return [slot for slot in self.slots if slot.required and not slot.approved]


def usable_records(
    records: Records, ledger: Ledger, today: date
) -> tuple[dict[str, exchange.Outreach], dict[str, str]]:
    """The Founder's outreach records that name an approved message, and why each other one changes nothing, by the
    item its file is named for."""
    usable: dict[str, exchange.Outreach] = {}
    problems: dict[str, str] = {}
    for record in records.read:
        entry = ledger.entries.get(record.item)
        name = f"`{RECORDS}/{record.item}.json`"
        if entry is None or entry["kind"] != "message":
            problems[record.item] = f"{name} names no message in the Review Queue"
        elif APPROVED not in (entry["status"], entry.get("decided")):
            problems[record.item] = f"{name} records a message as sent that the Founder has not approved"
        elif record.sent_on > (today + timedelta(days=1)).isoformat():
            problems[record.item] = f"{name} gives a sent_on date that has not come yet"
        else:
            usable[record.item] = record
    for name, why in records.unusable.items():
        problems[name[: -len(".json")] if name.endswith(".json") else name] = f"`{RECORDS}/{name}`: {why}"
    return usable, problems


def prepare(
    repo_root: Path,
    config: Settings,
    registry: Mapping,
    mandu: Path,
    ledger: Ledger,
    records: Records,
    saved: OutreachState,
    areas: Areas,
    now: datetime,
    run_id: str,
    waitlist_live: bool,
) -> tuple[Plan | None, OutreachState]:
    """The run's outreach plan and the run state rebuilt from the Founder's records; None when no active Product has
    a channel plan."""
    found = package_role(registry)
    if found is None:
        return None, saved
    product, plan_path = found
    entry = next(item for item in registry["products"] if item["name"] == product)
    tags = tuple((entry.get("waitlist") or {}).get("source_tags") or ())
    today = now.astimezone().date()
    limits, links = messages.run_limits(repo_root, registry, waitlist_live)
    plan = Plan(product, run_id, plan_path, limits, areas.path("drafts", *FOLDER))
    plan.records, plan.record_problems = usable_records(records, ledger, today)
    plan.records_failure = records.failure
    state = OutreachState()
    if config.network_source is None and not config.creators:
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

    for creator in config.creators:
        if creator.name not in plan_text:
            plan.skipped.append((creator.name, f"the channel plan (`{plan_path}`) does not name them"))
            continue
        target = messages.Target(
            messages.CREATOR, creator.key, creator.name, wait_days=config.wait_days, plan=plan_path
        )
        first = messages.slot_for(ledger, product, target, plan.folder / f"creator-{creator.key}.md")
        plan.slots.append(first)
        second = follow_up(plan, creator, first, ledger, state, today, config.wait_days)
        if second is not None:
            plan.slots.append(second)
    return plan, state


def follow_up(
    plan: Plan,
    creator: Creator,
    first: messages.Slot,
    ledger: Ledger,
    state: OutreachState,
    today: date,
    wait_days: int,
) -> messages.Slot | None:
    """The one follow-up a creator may get, and why it may not be offered now, if it may not. None when the Founder's
    record of the first message is missing or could not be used: the plan then says why, and nothing is offered or
    taken back for it, since only a record that was read may take an open item back. An open follow-up then stands
    (queue.stands), and the plan holds it for the run's notice."""
    key = f"creator:{creator.key}"
    sent = str(first.approved["id"]) if first.approved else ""
    record = plan.records.get(sent)
    target = messages.Target(messages.FOLLOW_UP, creator.key, creator.name, plan=plan.plan_path)
    slot = messages.slot_for(ledger, plan.product, target, plan.folder / f"follow-up-{creator.key}.md")
    if not sent:
        target.reason = f"the first message to {creator.name} is not approved yet"
    elif record is None:
        lost = ""
        if plan.records_failure:
            lost = f"the Founder's outreach records could not be read ({plan.records_failure})"
        elif sent in plan.record_problems:
            lost = f"the Founder's record of the first message could not be used ({plan.record_problems[sent]})"
        elif slot.open:
            lost = f"`{RECORDS}/{sent}.json`, the Founder's record of the first message, is missing"
        if lost and not slot.approved:
            kept = stands(slot.open, [lost])
            if kept:
                plan.stood.append(kept)
            stays = f"the open `{kept.item}` stays as it is" if kept else "no follow-up is offered"
            plan.unread.append((f"{creator.name}, the one follow-up", f"{lost}, so {stays}"))
            return None
        target.reason = (
            "the one follow-up was already approved; no further contact"
            if lost
            else f"the first message to {creator.name} is not recorded as sent yet"
        )
    else:
        wait = record.wait_days or wait_days
        state.record_contact(key, date.fromisoformat(record.sent_on), wait)
        if record.replied_on:
            state.record_reply(key)
        allowed, why = state.may_follow_up(key, today)
        target.sent_on, target.wait_days = record.sent_on, wait
        entry = state.targets[target_key(key)]
        if record.replied_on:
            why = f"{creator.name} replied on {record.replied_on}; a follow-up goes only to a non-reply"
        target.reason = "" if allowed else why
        after = (
            "so no follow-up is ever offered"
            if record.replied_on
            else f"a follow-up may be offered from {entry['follow_up_after']} ({plural(wait, 'day')})"
        )
        replied = f"replied {record.replied_on}" if record.replied_on else "no reply recorded"
        plan.record_lines.append(f"{creator.name}: first message sent {record.sent_on}, {replied}; {after}")
    slot.required = not target.reason
    if slot.approved and record is not None:
        # The one follow-up is used: nothing further is ever offered for this creator.
        state.targets[target_key(key)]["follow_ups"] = 1
        target.reason = target.reason or "the one follow-up was already approved; no further contact"
    return slot


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
        "limits": dict(plan.limits.__dict__),
        "slots": [slot_json(slot, areas) for slot in plan.slots],
        "skipped": [list(entry) for entry in plan.skipped + plan.unread],
    }


def restore(record: Mapping, areas: Areas, run_id: str) -> Plan:
    """A plan as the launcher recorded it, for check-work; the standing is never worked out again."""
    limits = messages.Limits(**record["limits"])
    plan = Plan(str(record["product"]), run_id, str(record["plan_path"]), limits, areas.path("drafts", *FOLDER))
    plan.problem = str(record["problem"])
    plan.skipped = [(str(who), str(why)) for who, why in record["skipped"]]
    for entry in record["slots"]:
        target = messages.Target(
            entry["purpose"],
            entry["key"],
            entry["label"],
            entry["reason"],
            entry["source_link"],
            entry["link_source"],
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
    if publish and (plan.slots or plan.skipped or plan.unread or plan.record_problems):
        data = {
            "run": run_id,
            "at": now.isoformat(),
            "product": plan.product,
            "channel_plan": plan.plan_path,
            "skipped": [{"who": who, "why": why} for who, why in plan.skipped + plan.unread],
            "records": plan.record_lines,
            "record_problems": list(plan.record_problems.values()),
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


def gaps(plan: Plan | None, result: Result | None, problem: str, agent_gap: str) -> list[str]:
    """Why the outreach Drafts are incomplete this run: a source a Draft is checked against could not be read, a
    Draft is missing, or the plan, the records, the take-in, or the agent fell short. A Draft blocked by a check the
    launcher could make is the check working, not a gap."""
    if plan is None:
        return [problem] if problem else []
    found = [plan.problem] if plan.problem else []
    found += [f"{who}: {why}" for who, why in plan.skipped if who == "the personal-network ask"]
    found += [f"{who}: {why}" for who, why in plan.unread]
    if result is None:
        found.append(problem or "the Drafts were not taken in")
    else:
        found += messages.unread(result.outcomes)
        missing = [o.target.label for o in result.outcomes if o.status == messages.MISSING]
        if missing:
            found.append(f"no Draft for {', '.join(missing)}")
    if plan.due() and agent_gap:
        found.append(agent_gap)
    return found


def tally(plan: Plan | None, result: Result | None, problem: str, agent_gap: str) -> Tally:
    """What the outreach workflow checked and acted on this run."""
    incomplete = "; ".join(gaps(plan, result, problem, agent_gap))
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


def brief_lines(plan: Plan | None, context: Context | None, mandu: Path, check: str) -> list[str]:
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
        "| For | Front matter | Draft file | In the Review Queue |",
        "| --- | --- | --- | --- |",
    ]
    for slot in plan.slots:
        target = slot.target
        front = f"`purpose: {target.purpose}`, `to: {target.key}`"
        lines.append(f"| {target.label}, {kind_of(target)} | {front} | `{slot.path}` | {slot.standing()} |")
    if not plan.slots:
        lines.append("| - | - | - | No message is due this run. |")
    lines += ["", f"- The plan for all of them, read it first: `{mandu / plan.plan_path}`."]
    for slot in plan.slots:
        target = slot.target
        if target.purpose == messages.NETWORK:
            lines.append(
                f"- The ask carries the personal-network Source link `{target.source_link}`, exactly as"
                f" `{target.link_source}` defines it, and no other link. Never invent or alter a link."
            )
    lines.append(
        f"- A message holds no email address. A message to a creator offers one of: {', '.join(messages.OFFERS)}."
    )
    if context is not None:
        lines += messages.describe_rules(context, creator=True)
    lines += [f"- Not prepared: {who}: {why}." for who, why in plan.skipped + plan.unread]
    return lines


def report_lines(plan: Plan | None, result: Result | None, filing: str, problem: str = "") -> list[str]:
    lines = ["## Outreach", ""]
    if plan is None:
        return lines + [problem or "No active Product has a channel plan, so no outreach message was prepared."]
    if plan.problem:
        lines.append(f"{plan.problem[0].upper()}{plan.problem[1:]}.")
    lines += [f"- Not prepared: {who}: {why}." for who, why in plan.skipped + plan.unread]
    lines += [f"- From the Founder's outreach records: {line}." for line in plan.record_lines]
    unusable = plan.record_problems.values()
    lines += [f"- One of the Founder's outreach records could not be used: {line}." for line in unusable]
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


def notice_section(
    plan: Plan | None, result: Result | None, day_text: str, again: bool = False
) -> tuple[int, str, str] | None:
    """The outreach messages not offered, any taken back, and any record of the Founder's that could not be used.
    again says a fresh, whole run follows this one by itself, which writes a message that has no Draft or reports on
    it itself, so such a message is left out."""
    if plan is None or result is None:
        return None
    lines = []
    blocked = [outcome for outcome in result.outcomes if outcome.status == messages.BLOCKED]
    missing = [] if again else [outcome for outcome in result.outcomes if outcome.status == messages.MISSING]
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
    for problem in plan.record_problems.values():
        lines.append(f"- One of the Founder's outreach records could not be used, so it changed nothing: {problem}.")
    if not lines:
        return None
    count = len(blocked) + len(missing) + len(taken_back) + len(plan.record_problems)
    what = "1 outreach message or record needs" if count == 1 else f"{count} outreach messages or records need"
    return count, f"{what} a look on {day_text}", "\n".join(lines)
