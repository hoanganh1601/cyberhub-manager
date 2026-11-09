"""Đợt 4 — Repository quảng cáo nhận thưởng trong bộ nhớ (demo, unit test).

Cùng chữ ký với repositories/ad_repository.py. Sự kiện được lưu trong MemoryGameRepository.ad_events
để vòng quay đếm được lượt quay thêm; transaction bọc transaction của game (→ voucher → P1).
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace

from cyberhub_manager.domain.ad import AdCreative, AdEvent, AdMode, AdRewardType, AdSettings, AdStatus

DEMO_CREATIVES = (
    AdCreative(1, "COMBO_NIGHT", "Combo đêm game chỉ từ 45.000đ",
               "Mì xào bò + khoai tây chiên + nước ngọt, giao tận máy. Gọi ngay trong tab Menu đồ ăn.", "Xem menu",
               15, True),
    AdCreative(2, "VIP_ROOM", "Phòng VIP: ghế công thái học, màn 240Hz",
               "Trải nghiệm phòng VIP của CyberHub, đặt máy tại quầy hoặc xem tình trạng phòng trong ứng dụng.",
               "Xem phòng trống", 15, True),
    AdCreative(3, "VOUCHER_WEEK", "Tuần lễ voucher CyberHub",
               "Quay thưởng mỗi ngày, gom xu và đổi voucher đồ ăn, nước uống, giờ chơi.", "Đến vòng quay", 10, True),
)


class MemoryAdRepository:
    def __init__(self, data, game_repo):
        self.data = data
        self.games = game_repo
        self.config = AdSettings(True, AdMode.HOUSE, 3, AdRewardType.EXTRA_SPIN, 1)
        self.creative_list: list[AdCreative] = list(DEMO_CREATIVES)

    @contextmanager
    def transaction(self):
        with self.games.transaction() as conn:
            snapshot = deepcopy((self.config, self.creative_list))
            try:
                yield conn
            except Exception:
                self.config, self.creative_list = snapshot
                raise

    @property
    def _events(self):
        return self.games.ad_events

    def _name(self, account_id):
        customer = next((c for c in self.data.customers.values() if c.account.id == account_id), None)
        return customer.full_name if customer else ""

    def _event(self, e):
        return AdEvent(e["id"], e["token"], e["account_id"], self._name(e["account_id"]), e["creative_id"],
                       AdMode(e["provider"]), AdRewardType(e["reward_type"]), e["reward_amount"],
                       AdStatus(e["status"]), e["played_on"], e["issued_at"], e["min_complete_at"], e["expires_at"],
                       e["completed_at"], e["provider_txn_id"], e["reject_reason"])

    # ----- Cấu hình ------------------------------------------------------------------
    def settings(self, conn, *, lock=False):
        return self.config

    def save_settings(self, conn, s):
        self.config = s

    def creatives(self, conn):
        return list(self.creative_list)

    def creative_code_taken(self, conn, code, exclude_id):
        return any(c.code == code and c.id != exclude_id for c in self.creative_list)

    def save_creative(self, conn, creative_id, *, code, title, body, cta, duration_seconds, is_active):
        if creative_id is None:
            creative_id = max((c.id for c in self.creative_list), default=0) + 1
            self.creative_list.append(AdCreative(creative_id, code, title, body, cta, duration_seconds, is_active))
        else:
            self.creative_list = [
                replace(c, code=code, title=title, body=body, cta=cta, duration_seconds=duration_seconds,
                        is_active=is_active) if c.id == creative_id else c
                for c in self.creative_list
            ]
        return creative_id

    # ----- Sự kiện ----------------------------------------------------------------------
    def insert_event(self, conn, *, token, account_id, creative_id, provider, reward_type, reward_amount, played_on,
                     issued_at, min_complete_at, expires_at):
        if any(e["token"] == token for e in self._events):
            raise ValueError("duplicate token")  # tương đương UNIQUE(token)
        event_id = len(self._events) + 1
        self._events.append(dict(
            id=event_id, token=token, account_id=account_id, creative_id=creative_id, provider=str(provider),
            reward_type=str(reward_type), reward_amount=reward_amount, status="ISSUED", played_on=played_on,
            issued_at=issued_at, min_complete_at=min_complete_at, expires_at=expires_at, completed_at=None,
            provider_txn_id=None, reject_reason=None,
        ))
        return event_id

    def get_event(self, conn, token, *, lock=False):
        found = next((e for e in self._events if e["token"] == token), None)
        return None if found is None else self._event(found)

    def txn_used(self, conn, txn_id):
        return any(e["provider_txn_id"] == txn_id for e in self._events)

    def supersede_issued(self, conn, account_id):
        for e in self._events:
            if e["account_id"] == account_id and e["status"] == "ISSUED":
                e.update(status="REJECTED", reject_reason="SUPERSEDED")

    def finish_event(self, conn, event_id, *, status, completed_at=None, reason=None, txn_id=None):
        event = next((e for e in self._events if e["id"] == event_id), None)
        if event is None or event["status"] != "ISSUED":
            return False
        if txn_id is not None and self.txn_used(conn, txn_id):
            raise ValueError("duplicate provider txn")  # tương đương UNIQUE(provider_txn_id)
        event.update(status=str(status), completed_at=completed_at, reject_reason=reason, provider_txn_id=txn_id)
        return True

    def count_events(self, conn, account_id, day, status=None):
        return sum(1 for e in self._events if e["account_id"] == account_id and e["played_on"] == day
                   and (status is None or e["status"] == str(status)))

    def daily_stats(self, conn, since_day, now):
        days = {}
        for e in self._events:
            if e["played_on"] < since_day:
                continue
            row = days.setdefault(e["played_on"], dict(day=e["played_on"], issued=0, completed=0, rejected=0,
                                                       expired=0, spins=0, coins=0))
            row["issued"] += 1
            if e["status"] == "COMPLETED":
                row["completed"] += 1
                row["spins" if e["reward_type"] == "EXTRA_SPIN" else "coins"] += e["reward_amount"]
            elif e["status"] == "REJECTED":
                row["rejected"] += 1
            elif e["expires_at"] < now:
                row["expired"] += 1
        return sorted(days.values(), key=lambda r: r["day"], reverse=True)

    def recent_events(self, conn, limit=30):
        found = sorted(self._events, key=lambda e: (e["issued_at"], e["id"]), reverse=True)[:limit]
        return [self._event(e) for e in found]
