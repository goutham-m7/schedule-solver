"""Dependency-free, escaped, accessible static calendar. No scripts or remote assets."""

from collections import defaultdict
from datetime import UTC, timedelta
from html import escape
from zoneinfo import ZoneInfo

from .models import Result, Workload


def calendar_html(work: Workload, result: Result) -> str:
    def e(value):
        return escape(str(value), quote=True)

    days = defaultdict(list)
    people = {p.id: p for p in work.people}
    for meeting in result.meetings:
        days[meeting.start.astimezone(UTC).date()].append(meeting)
    boards = []
    for day, meetings in sorted(days.items()):
        origin = min(m.start for m in meetings).replace(minute=0)
        finish = max(m.end for m in meetings)
        span = max(120, int((finish - origin).total_seconds() // 60) + 30)
        lanes = ['<div class="lane axis" aria-label="UTC hours">']
        for minute in range(0, span, 60):
            lanes.append(
                f'<span class="tick" style="top:{minute * 1.6}px">{(origin + timedelta(minutes=minute)):%H:%M}</span>'
            )
        lanes.append("</div>")
        for person in work.people:
            cards = []
            for meeting in meetings:
                if person.id not in meeting.attendees:
                    continue
                top = (meeting.start - origin).total_seconds() / 60 * 1.6
                height = (meeting.end - meeting.start).total_seconds() / 60 * 1.6
                local = meeting.start.astimezone(ZoneInfo(person.timezone))
                cards.append(
                    f'<article class="event" style="top:{top}px;height:{height}px"><strong>{e(meeting.request_id)}</strong><span>{meeting.start:%H:%M}–{meeting.end:%H:%M} UTC</span><small>{local:%H:%M %Z} · {e(person.id)}</small></article>'
                )
            lanes.append(
                f'<div class="lane" aria-label="{e(person.id)} calendar">{"".join(cards)}</div>'
            )
        headers = "<div>UTC</div>" + "".join(
            f"<div><strong>{e(p.id)}</strong><small>{e(p.timezone)}</small></div>"
            for p in work.people
        )
        boards.append(
            f'<section aria-label="Calendar {day}"><h2>{day:%A, %d %B %Y}</h2><div class="scroll"><div class="headers" style="--n:{len(people)}">{headers}</div><div class="board" style="--n:{len(people)};--height:{span * 1.6}px">{"".join(lanes)}</div></div></section>'
        )
    explanations = "".join(
        f'<details><summary>{e(x.request_id)} <span class="tag">{e(x.kind)}</span></summary><ul>'
        + "".join(f"<li>{e(f)}</li>" for f in x.facts)
        + f"</ul><p>{e(', '.join(x.conflict))}</p></details>"
        for x in result.explanations
    )
    metrics = result.metrics
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>schedule-solver · calendar</title><style>
:root{{color-scheme:light;--ink:#182b33;--muted:#4b626a;--line:#d8e1df;--accent:#006b5d}}
*{{box-sizing:border-box}}body{{margin:0;background:#f5f5ef;color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1500px;margin:auto;padding:40px 24px}}header{{border-top:5px solid var(--accent);padding:22px 0}}h1{{font-size:clamp(32px,5vw,58px);letter-spacing:-2px;margin:8px 0}}h2{{font-size:21px}}.eyebrow{{text-transform:uppercase;letter-spacing:3px;font-size:12px;color:var(--accent)}}.lede{{max-width:760px;color:var(--muted)}}
.stats{{display:flex;flex-wrap:wrap;gap:30px;padding:20px 0;border-block:1px solid var(--line);margin:25px 0}}.stat strong{{display:block;font-size:30px;font-variant-numeric:tabular-nums}}.stat span,small{{display:block;color:var(--muted);font-size:12px}}
.scroll{{overflow:auto;border:1px solid var(--line);background:white}}.headers,.board{{display:grid;grid-template-columns:70px repeat(var(--n),minmax(185px,1fr));min-width:calc(70px + var(--n)*185px)}}.headers>div{{padding:12px;border-right:1px solid var(--line)}}.lane{{height:var(--height);position:relative;border-right:1px solid var(--line);background:repeating-linear-gradient(to bottom,transparent 0,transparent 47px,#edf1ef 47px,#edf1ef 48px)}}.axis{{background:#f0f3ee}}.tick{{position:absolute;font:12px ui-monospace,monospace;left:10px}}.event{{position:absolute;left:5px;right:5px;overflow:auto;border-left:3px solid var(--accent);background:#dcefe8;padding:4px 7px;font-size:12px;line-height:1.3}}.event strong,.event span{{display:block}}.event small{{font-size:10px}}.tag{{font:11px ui-monospace,monospace;color:var(--accent)}}details{{padding:12px 0;border-bottom:1px solid var(--line)}}summary{{cursor:pointer;font-weight:600}}footer{{margin-top:40px;font-size:12px;color:var(--muted)}}
</style></head><body><main><header><div class="eyebrow">Constraint-first · Explainable scheduling</div><h1>Time, used intentionally.</h1><p class="lede">A feasible calendar, a measurable objective, and a checked reason for every excluded request. All lanes use UTC; cards show attendee-local time.</p></header>
<div class="stats"><div class="stat"><strong>{metrics.meetings_scheduled}/{len(work.requests)}</strong><span>meetings scheduled</span></div><div class="stat"><strong>{metrics.priority_scheduled}</strong><span>weighted priority</span></div><div class="stat"><strong>{metrics.gap_minutes} min</strong><span>internal gaps</span></div><div class="stat"><strong>{metrics.load_spread_minutes} min</strong><span>load spread</span></div></div>
{"".join(boards) or "<p>No meetings scheduled.</p>"}<section><h2>Decision record</h2>{explanations or "<p>Run with explanations enabled for checked certificates.</p>"}</section><footer>{e(result.algorithm)} · Solver wall time {metrics.solve_seconds:.3f}s · A feasible incumbent is not necessarily a proven optimum. Certificates hold other meetings fixed.</footer></main></body></html>"""
