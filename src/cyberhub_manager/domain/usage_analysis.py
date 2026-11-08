"""Actual usage, split at Vietnam hour boundaries rather than assigned to start day."""

from datetime import timedelta, timezone

VIETNAM = timezone(timedelta(hours=7))


def analyze_usage(sessions, start, end, now):
    stop = min(end, now)
    first, last = start.astimezone(VIETNAM).date(), stop.astimezone(VIETNAM).date()
    days = {
        first + timedelta(days=n): dict(usage_seconds=0, sessions_started=0)
        for n in range((last - first).days + 1)
    }
    hours, weekdays, stores, machine_ids = [0] * 24, [0] * 7, {}, set()
    lengths = []
    for row in sessions:
        if row["status"] not in ("ACTIVE", "COMPLETED"):
            continue
        begin, finish = max(start, row["started_at"]), min(stop, row["ended_at"] or now)
        if finish <= begin:
            continue
        seconds = int((finish - begin).total_seconds())
        lengths.append(seconds)
        machine_ids.add(row["machine_id"])
        store = stores.setdefault(
            row["store_id"], dict(store_name=row["store_name"], usage_seconds=0)
        )
        store["usage_seconds"] += seconds
        local_start = row["started_at"].astimezone(VIETNAM).date()
        if start <= row["started_at"] < stop and local_start in days:
            days[local_start]["sessions_started"] += 1
        cursor = begin
        while cursor < finish:
            local = cursor.astimezone(VIETNAM)
            boundary = local.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=1
            )
            until = min(finish, boundary)
            part = int((until - begin).total_seconds()) - int(
                (cursor - begin).total_seconds()
            )
            days[local.date()]["usage_seconds"] += part
            hours[local.hour] += part
            weekdays[local.weekday()] += part
            cursor = until
    total = sum(lengths)
    daily = [dict(day=day, **values) for day, values in days.items()]
    peak = max(daily, key=lambda r: r["usage_seconds"], default=None)
    return dict(
        usage_seconds=total,
        sessions=len(lengths),
        machines=len(machine_ids),
        average_seconds=total // len(lengths) if lengths else 0,
        longest_seconds=max(lengths, default=0),
        daily=daily,
        hours=[dict(hour=i, usage_seconds=v) for i, v in enumerate(hours)],
        weekdays=[dict(weekday=i, usage_seconds=v) for i, v in enumerate(weekdays)],
        stores=sorted(
            stores.values(), key=lambda r: (-r["usage_seconds"], r["store_name"])
        ),
        peak_day=peak if peak and peak["usage_seconds"] else None,
    )
