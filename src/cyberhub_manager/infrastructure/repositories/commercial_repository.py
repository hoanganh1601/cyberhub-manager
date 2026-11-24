"""Persistence for commercial partners and verified external-game events."""

from cyberhub_manager.infrastructure.repositories.sql import execute, rows


class CommercialRepository:
    def overview(self, conn, store_id, *, include_global=False):
        placement_scope = (
            ""
            if include_global
            else "WHERE pl.store_id IS NULL OR pl.store_id=%s "
        )
        placement_params = () if include_global else (store_id,)
        placement_query = (
            "SELECT pl.*,ca.name AS campaign_name,p.name AS partner_name "
            "FROM commercial_placements pl "
            "JOIN commercial_campaigns ca ON ca.id=pl.campaign_id "
            "JOIN commercial_contracts co ON co.id=ca.contract_id "
            "JOIN commercial_partners p ON p.id=co.partner_id "
            + placement_scope
            + "ORDER BY pl.created_at DESC,pl.id DESC LIMIT 200"
        )
        result = {
            "partners": [],
            "contracts": [],
            "settlements": [],
            "placements": rows(
                conn,
                placement_query,
                placement_params,
            ),
        }
        if not include_global:
            return result
        result.update({
            "partners": rows(
                conn,
                "SELECT id,code,name,partner_type,status,contact_name,contact_email "
                "FROM commercial_partners ORDER BY name,id",
            ),
            "contracts": rows(
                conn,
                "SELECT c.*,p.name AS partner_name FROM commercial_contracts c "
                "JOIN commercial_partners p ON p.id=c.partner_id "
                "ORDER BY c.created_at DESC,c.id DESC LIMIT 200",
            ),
            "settlements": rows(
                conn,
                "SELECT s.*,(CAST(s.gross_amount AS SIGNED)+s.adjustment_amount) AS net_amount,"
                "c.code AS contract_code,p.name AS partner_name "
                "FROM commercial_settlements s "
                "JOIN commercial_contracts c ON c.id=s.contract_id "
                "JOIN commercial_partners p ON p.id=c.partner_id "
                "ORDER BY s.period_end DESC,s.id DESC LIMIT 200",
            ),
        })
        return result

    def partner(self, conn, partner_id, *, lock=False):
        result = rows(
            conn,
            "SELECT * FROM commercial_partners WHERE id=%s"
            + (" FOR UPDATE" if lock else ""),
            (partner_id,),
        )
        return result[0] if result else None

    def save_partner(self, conn, partner_id, values):
        if partner_id:
            execute(
                conn,
                "UPDATE commercial_partners SET code=%s,name=%s,partner_type=%s,"
                "status=%s,callback_secret_ref=%s,contact_name=%s,contact_email=%s "
                "WHERE id=%s",
                (*values, partner_id),
            )
            return partner_id
        return execute(
            conn,
            "INSERT INTO commercial_partners(code,name,partner_type,status,"
            "callback_secret_ref,contact_name,contact_email) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            values,
        )

    def contract(self, conn, contract_id, *, lock=False):
        result = rows(
            conn,
            "SELECT c.*,p.status AS partner_status,p.partner_type,p.callback_secret_ref "
            "FROM commercial_contracts c JOIN commercial_partners p ON p.id=c.partner_id "
            "WHERE c.id=%s" + (" FOR UPDATE" if lock else ""),
            (contract_id,),
        )
        return result[0] if result else None

    def create_contract(self, conn, values):
        return execute(
            conn,
            "INSERT INTO commercial_contracts(partner_id,code,revenue_model,rate_amount,"
            "starts_on,ends_on,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            values,
        )

    def activate_contract(self, conn, contract_id, employee_id):
        return execute(
            conn,
            "UPDATE commercial_contracts SET status='ACTIVE',approved_by=%s,"
            "approved_at=UTC_TIMESTAMP() WHERE id=%s AND status='DRAFT'",
            (employee_id, contract_id),
        )

    def create_campaign(self, conn, values):
        return execute(
            conn,
            "INSERT INTO commercial_campaigns(contract_id,code,name,kind,status,starts_at,"
            "ends_at,budget_amount,reward_type,reward_amount,created_by) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            values,
        )

    def campaign(self, conn, campaign_id, *, lock=False):
        result = rows(
            conn,
            "SELECT ca.*,co.status AS contract_status,p.status AS partner_status "
            "FROM commercial_campaigns ca JOIN commercial_contracts co ON co.id=ca.contract_id "
            "JOIN commercial_partners p ON p.id=co.partner_id WHERE ca.id=%s"
            + (" FOR UPDATE" if lock else ""),
            (campaign_id,),
        )
        return result[0] if result else None

    def set_campaign_status(self, conn, campaign_id, status):
        return execute(
            conn,
            "UPDATE commercial_campaigns SET status=%s WHERE id=%s AND status<>%s",
            (status, campaign_id, status),
        )

    def create_placement(self, conn, values):
        return execute(
            conn,
            "INSERT INTO commercial_placements(campaign_id,store_id,code,placement_type,"
            "surface,embed_url,allowed_origin,sandbox_policy,legacy_game_id,"
            "legacy_ad_creative_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            values,
        )

    def active_placement(self, conn, code, store_id, now, *, lock=False):
        result = rows(
            conn,
            "SELECT pl.*,ca.contract_id,ca.reward_type,ca.reward_amount,ca.kind,"
            "p.callback_secret_ref,p.status AS partner_status "
            "FROM commercial_placements pl "
            "JOIN commercial_campaigns ca ON ca.id=pl.campaign_id "
            "JOIN commercial_contracts co ON co.id=ca.contract_id "
            "JOIN commercial_partners p ON p.id=co.partner_id "
            "WHERE pl.code=%s AND (pl.store_id IS NULL OR pl.store_id=%s) "
            "AND pl.status='ACTIVE' AND ca.status='ACTIVE' AND co.status='ACTIVE' "
            "AND p.status='ACTIVE' AND ca.starts_at<=%s AND ca.ends_at>%s "
            "AND co.starts_on<=DATE(%s) AND co.ends_on>=DATE(%s)"
            + (" FOR UPDATE" if lock else ""),
            (code, store_id, now, now, now, now),
        )
        return result[0] if result else None

    def callback_placement(self, conn, code, now, *, lock=False):
        """Resolve an active placement for a signed partner-server callback."""

        result = rows(
            conn,
            "SELECT pl.*,ca.id AS campaign_id,ca.contract_id,ca.kind,"
            "p.callback_secret_ref,"
            "p.status AS partner_status "
            "FROM commercial_placements pl "
            "JOIN commercial_campaigns ca ON ca.id=pl.campaign_id "
            "JOIN commercial_contracts co ON co.id=ca.contract_id "
            "JOIN commercial_partners p ON p.id=co.partner_id "
            "WHERE pl.code=%s AND pl.status='ACTIVE' AND ca.status='ACTIVE' "
            "AND co.status='ACTIVE' AND p.status='ACTIVE' "
            "AND ca.starts_at<=%s AND ca.ends_at>%s "
            "AND co.starts_on<=DATE(%s) AND co.ends_on>=DATE(%s)"
            + (" FOR UPDATE" if lock else ""),
            (code, now, now, now, now),
        )
        return result[0] if result else None

    def create_play_session(self, conn, values):
        return execute(
            conn,
            "INSERT INTO commercial_play_sessions(placement_id,account_id,token_hash,"
            "reward_type,reward_amount,issued_at,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            values,
        )

    def play_session(self, conn, token_hash, *, lock=False):
        result = rows(
            conn,
            "SELECT ps.*,pl.campaign_id,pl.code AS placement_code,p.callback_secret_ref,"
            "p.status AS partner_status,ca.status AS campaign_status,co.status AS contract_status,"
            "pl.status AS placement_status "
            "FROM commercial_play_sessions ps "
            "JOIN commercial_placements pl ON pl.id=ps.placement_id "
            "JOIN commercial_campaigns ca ON ca.id=pl.campaign_id "
            "JOIN commercial_contracts co ON co.id=ca.contract_id "
            "JOIN commercial_partners p ON p.id=co.partner_id WHERE ps.token_hash=%s"
            + (" FOR UPDATE" if lock else ""),
            (token_hash,),
        )
        return result[0] if result else None

    def event_by_provider_id(self, conn, provider_event_id):
        result = rows(
            conn,
            "SELECT e.*,pl.campaign_id,g.id AS grant_id,g.status AS grant_status FROM commercial_events e "
            "JOIN commercial_placements pl ON pl.id=e.placement_id "
            "LEFT JOIN commercial_reward_grants g ON g.event_id=e.id "
            "WHERE e.provider_event_id=%s",
            (provider_event_id,),
        )
        return result[0] if result else None

    def event_by_key(self, conn, event_key):
        result = rows(
            conn,
            "SELECT e.*,pl.campaign_id FROM commercial_events e "
            "JOIN commercial_placements pl ON pl.id=e.placement_id WHERE e.event_key=%s",
            (event_key,),
        )
        return result[0] if result else None

    def insert_event(self, conn, values):
        # values[1] was redundant campaign_id (now derived via placement_id in 028).
        normalized = (values[0], *values[2:])
        return execute(
            conn,
            "INSERT INTO commercial_events(placement_id,play_session_id,"
            "account_id,event_type,event_key,provider_event_id,verification_method,accepted,"
            "occurred_at,verified_at,payload_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            normalized,
        )

    def complete_play_session(self, conn, session_id, completed_at):
        return execute(
            conn,
            "UPDATE commercial_play_sessions SET status='COMPLETED',completed_at=%s "
            "WHERE id=%s AND status='ISSUED'",
            (completed_at, session_id),
        )

    def create_reward_grant(self, conn, event_id, account_id, reward_type, reward_amount):
        return execute(
            conn,
            "INSERT INTO commercial_reward_grants(event_id,account_id,reward_type,reward_amount) "
            "VALUES(%s,%s,%s,%s)",
            (event_id, account_id, reward_type, reward_amount),
        )

    def settlement_units(self, conn, contract_id, event_type, start, before):
        return rows(
            conn,
            "SELECT pl.id AS placement_id,COUNT(*) AS units FROM commercial_events e "
            "JOIN commercial_placements pl ON pl.id=e.placement_id "
            "JOIN commercial_campaigns ca ON ca.id=pl.campaign_id "
            "WHERE ca.contract_id=%s AND e.event_type=%s AND e.accepted=TRUE "
            "AND e.verification_method IN ('SERVER','SSV') "
            "AND e.occurred_at>=%s AND e.occurred_at<%s "
            "GROUP BY pl.id ORDER BY pl.id",
            (contract_id, event_type, start, before),
        )

    def contract_placements(self, conn, contract_id):
        return rows(
            conn,
            "SELECT pl.id AS placement_id FROM commercial_placements pl "
            "JOIN commercial_campaigns ca ON ca.id=pl.campaign_id "
            "WHERE ca.contract_id=%s ORDER BY pl.id",
            (contract_id,),
        )

    def overlapping_settlement(self, conn, contract_id, start, end):
        result = rows(
            conn,
            "SELECT id FROM commercial_settlements WHERE contract_id=%s AND status<>'VOID' "
            "AND period_start<=%s AND period_end>=%s LIMIT 1 FOR UPDATE",
            (contract_id, end, start),
        )
        return result[0] if result else None

    def create_settlement(self, conn, values, lines):
        # values[6] was derived net_amount; line[4] was derived amount (NF-01).
        settlement_id = execute(
            conn,
            "INSERT INTO commercial_settlements(contract_id,period_start,period_end,"
            "gross_amount,adjustment_amount,adjustment_reason,generated_by) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (*values[:6], values[7]),
        )
        for line in lines:
            execute(
                conn,
                "INSERT INTO commercial_settlement_lines(settlement_id,placement_id,event_type,"
                "units,unit_rate) VALUES(%s,%s,%s,%s,%s)",
                (settlement_id, *line[:4]),
            )
        return settlement_id

    def settlement(self, conn, settlement_id, *, lock=False):
        result = rows(
            conn,
            "SELECT s.*,(CAST(s.gross_amount AS SIGNED)+s.adjustment_amount) AS net_amount "
            "FROM commercial_settlements s WHERE s.id=%s"
            + (" FOR UPDATE" if lock else ""),
            (settlement_id,),
        )
        return result[0] if result else None

    def approve_settlement(self, conn, settlement_id, employee_id):
        return execute(
            conn,
            "UPDATE commercial_settlements SET status='APPROVED',reviewed_by=%s,"
            "reviewed_at=UTC_TIMESTAMP() WHERE id=%s AND status='DRAFT'",
            (employee_id, settlement_id),
        )
