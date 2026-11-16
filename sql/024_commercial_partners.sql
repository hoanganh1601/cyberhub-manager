-- Commercial partners, contracts, campaigns, placements, verified events,
-- reward outbox and revenue reconciliation.
-- Browser/iframe events are analytics only. Reward-bearing COMPLETE events must
-- be verified server-to-server before a grant can enter the outbox.

CREATE TABLE commercial_partners (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(24) NOT NULL,
    name VARCHAR(120) NOT NULL,
    partner_type VARCHAR(12) NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'ACTIVE',
    callback_secret_ref VARCHAR(80) NULL,
    contact_name VARCHAR(100) NULL,
    contact_email VARCHAR(120) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_commercial_partners_code UNIQUE (code),
    CONSTRAINT chk_commercial_partners_type CHECK (partner_type IN ('GAME','AD_NETWORK','BOTH')),
    CONSTRAINT chk_commercial_partners_status CHECK (status IN ('ACTIVE','SUSPENDED','TERMINATED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE commercial_contracts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    partner_id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(24) NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'DRAFT',
    revenue_model VARCHAR(8) NOT NULL,
    rate_amount BIGINT UNSIGNED NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'VND',
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    approved_by BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_commercial_contracts_code UNIQUE (code),
    CONSTRAINT fk_commercial_contracts_partner FOREIGN KEY (partner_id) REFERENCES commercial_partners(id),
    CONSTRAINT fk_commercial_contracts_creator FOREIGN KEY (created_by) REFERENCES employees(id),
    CONSTRAINT fk_commercial_contracts_approver FOREIGN KEY (approved_by) REFERENCES employees(id),
    CONSTRAINT chk_commercial_contracts_model CHECK (revenue_model IN ('CPM','CPC','CPA','FIXED')),
    CONSTRAINT chk_commercial_contracts_status CHECK (status IN ('DRAFT','ACTIVE','SUSPENDED','EXPIRED','TERMINATED')),
    CONSTRAINT chk_commercial_contracts_period CHECK (ends_on >= starts_on),
    CONSTRAINT chk_commercial_contracts_currency CHECK (currency = 'VND'),
    CONSTRAINT chk_commercial_contracts_approval CHECK (
        (status='DRAFT' AND approved_by IS NULL AND approved_at IS NULL)
        OR (status<>'DRAFT' AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE commercial_campaigns (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    contract_id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(24) NOT NULL,
    name VARCHAR(120) NOT NULL,
    kind VARCHAR(8) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'DRAFT',
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    budget_amount BIGINT UNSIGNED NULL,
    reward_type VARCHAR(12) NOT NULL DEFAULT 'NONE',
    reward_amount INT UNSIGNED NOT NULL DEFAULT 0,
    created_by BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_commercial_campaigns_code UNIQUE (code),
    CONSTRAINT fk_commercial_campaigns_contract FOREIGN KEY (contract_id) REFERENCES commercial_contracts(id),
    CONSTRAINT fk_commercial_campaigns_creator FOREIGN KEY (created_by) REFERENCES employees(id),
    CONSTRAINT chk_commercial_campaigns_kind CHECK (kind IN ('AD','GAME')),
    CONSTRAINT chk_commercial_campaigns_status CHECK (status IN ('DRAFT','ACTIVE','PAUSED','ENDED')),
    CONSTRAINT chk_commercial_campaigns_period CHECK (ends_at > starts_at),
    CONSTRAINT chk_commercial_campaigns_reward CHECK (
        (reward_type='NONE' AND reward_amount=0)
        OR (reward_type IN ('COINS','VOUCHER','EXTRA_SPIN') AND reward_amount>0)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE commercial_placements (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    campaign_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NULL,
    code VARCHAR(32) NOT NULL,
    placement_type VARCHAR(8) NOT NULL,
    surface VARCHAR(24) NOT NULL,
    embed_url VARCHAR(500) NULL,
    allowed_origin VARCHAR(255) NULL,
    sandbox_policy VARCHAR(120) NOT NULL DEFAULT 'allow-scripts allow-pointer-lock',
    legacy_game_id BIGINT UNSIGNED NULL,
    legacy_ad_creative_id BIGINT UNSIGNED NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_commercial_placements_code UNIQUE (code),
    CONSTRAINT fk_commercial_placements_campaign FOREIGN KEY (campaign_id) REFERENCES commercial_campaigns(id),
    CONSTRAINT fk_commercial_placements_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_commercial_placements_game FOREIGN KEY (legacy_game_id) REFERENCES games(id),
    CONSTRAINT fk_commercial_placements_ad FOREIGN KEY (legacy_ad_creative_id) REFERENCES ad_creatives(id),
    CONSTRAINT chk_commercial_placements_type CHECK (placement_type IN ('AD','GAME')),
    CONSTRAINT chk_commercial_placements_surface CHECK (surface IN ('PORTAL_BANNER','REWARDED_AD','GAME_CENTER')),
    CONSTRAINT chk_commercial_placements_status CHECK (status IN ('ACTIVE','INACTIVE')),
    CONSTRAINT chk_commercial_placements_embed CHECK (
        (placement_type='GAME' AND embed_url IS NOT NULL AND allowed_origin IS NOT NULL)
        OR placement_type='AD'
    ),
    INDEX idx_commercial_placements_store (store_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE commercial_play_sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    placement_id BIGINT UNSIGNED NOT NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    token_hash CHAR(64) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'ISSUED',
    reward_type VARCHAR(12) NOT NULL,
    reward_amount INT UNSIGNED NOT NULL,
    issued_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    CONSTRAINT uq_commercial_play_sessions_token UNIQUE (token_hash),
    CONSTRAINT fk_commercial_play_sessions_placement FOREIGN KEY (placement_id) REFERENCES commercial_placements(id),
    CONSTRAINT fk_commercial_play_sessions_account FOREIGN KEY (account_id) REFERENCES accounts(id),
    CONSTRAINT chk_commercial_play_sessions_status CHECK (status IN ('ISSUED','COMPLETED','EXPIRED','REJECTED')),
    CONSTRAINT chk_commercial_play_sessions_reward CHECK (
        (reward_type='NONE' AND reward_amount=0)
        OR (reward_type IN ('COINS','VOUCHER','EXTRA_SPIN') AND reward_amount>0)
    ),
    CONSTRAINT chk_commercial_play_sessions_period CHECK (expires_at > issued_at),
    INDEX idx_commercial_play_sessions_account (account_id, status, issued_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE commercial_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    placement_id BIGINT UNSIGNED NOT NULL,
    campaign_id BIGINT UNSIGNED NOT NULL,
    play_session_id BIGINT UNSIGNED NULL,
    account_id BIGINT UNSIGNED NULL,
    event_type VARCHAR(10) NOT NULL,
    event_key VARCHAR(80) NOT NULL,
    provider_event_id VARCHAR(100) NULL,
    verification_method VARCHAR(8) NOT NULL,
    accepted BOOLEAN NOT NULL DEFAULT TRUE,
    occurred_at DATETIME NOT NULL,
    verified_at DATETIME NULL,
    payload_digest CHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_commercial_events_key UNIQUE (event_key),
    CONSTRAINT uq_commercial_events_provider UNIQUE (provider_event_id),
    CONSTRAINT fk_commercial_events_placement FOREIGN KEY (placement_id) REFERENCES commercial_placements(id),
    CONSTRAINT fk_commercial_events_campaign FOREIGN KEY (campaign_id) REFERENCES commercial_campaigns(id),
    CONSTRAINT fk_commercial_events_session FOREIGN KEY (play_session_id) REFERENCES commercial_play_sessions(id),
    CONSTRAINT fk_commercial_events_account FOREIGN KEY (account_id) REFERENCES accounts(id),
    CONSTRAINT chk_commercial_events_type CHECK (event_type IN ('IMPRESSION','START','COMPLETE','CLICK')),
    CONSTRAINT chk_commercial_events_verification CHECK (verification_method IN ('CLIENT','SERVER','SSV')),
    CONSTRAINT chk_commercial_events_complete CHECK (event_type<>'COMPLETE' OR verification_method IN ('SERVER','SSV')),
    CONSTRAINT chk_commercial_events_verified CHECK (
        (verification_method='CLIENT' AND verified_at IS NULL)
        OR (verification_method IN ('SERVER','SSV') AND verified_at IS NOT NULL)
    ),
    INDEX idx_commercial_events_campaign (campaign_id, event_type, accepted, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE commercial_reward_grants (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    event_id BIGINT UNSIGNED NOT NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    reward_type VARCHAR(12) NOT NULL,
    reward_amount INT UNSIGNED NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_at DATETIME NULL,
    failure_reason VARCHAR(255) NULL,
    CONSTRAINT uq_commercial_reward_grants_event UNIQUE (event_id),
    CONSTRAINT fk_commercial_reward_grants_event FOREIGN KEY (event_id) REFERENCES commercial_events(id),
    CONSTRAINT fk_commercial_reward_grants_account FOREIGN KEY (account_id) REFERENCES accounts(id),
    CONSTRAINT chk_commercial_reward_grants_reward CHECK (reward_type IN ('COINS','VOUCHER','EXTRA_SPIN') AND reward_amount>0),
    CONSTRAINT chk_commercial_reward_grants_status CHECK (status IN ('PENDING','APPLIED','FAILED')),
    INDEX idx_commercial_reward_grants_pending (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE commercial_settlements (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    contract_id BIGINT UNSIGNED NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    gross_amount BIGINT UNSIGNED NOT NULL,
    adjustment_amount BIGINT NOT NULL DEFAULT 0,
    adjustment_reason VARCHAR(255) NULL,
    net_amount BIGINT UNSIGNED NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'DRAFT',
    generated_by BIGINT UNSIGNED NOT NULL,
    reviewed_by BIGINT UNSIGNED NULL,
    reviewed_at DATETIME NULL,
    paid_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_commercial_settlements_period UNIQUE (contract_id, period_start, period_end),
    CONSTRAINT fk_commercial_settlements_contract FOREIGN KEY (contract_id) REFERENCES commercial_contracts(id),
    CONSTRAINT fk_commercial_settlements_generator FOREIGN KEY (generated_by) REFERENCES employees(id),
    CONSTRAINT fk_commercial_settlements_reviewer FOREIGN KEY (reviewed_by) REFERENCES employees(id),
    CONSTRAINT chk_commercial_settlements_period CHECK (period_end >= period_start),
    CONSTRAINT chk_commercial_settlements_status CHECK (status IN ('DRAFT','APPROVED','PAID','VOID')),
    CONSTRAINT chk_commercial_settlements_amount CHECK (net_amount = gross_amount + adjustment_amount),
    CONSTRAINT chk_commercial_settlements_adjustment CHECK (
        (adjustment_amount=0 AND adjustment_reason IS NULL)
        OR (adjustment_amount<>0 AND CHAR_LENGTH(TRIM(adjustment_reason))>=5)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE commercial_settlement_lines (
    settlement_id BIGINT UNSIGNED NOT NULL,
    placement_id BIGINT UNSIGNED NOT NULL,
    event_type VARCHAR(10) NOT NULL,
    units BIGINT UNSIGNED NOT NULL,
    unit_rate BIGINT UNSIGNED NOT NULL,
    amount BIGINT UNSIGNED NOT NULL,
    CONSTRAINT pk_commercial_settlement_lines PRIMARY KEY (settlement_id, placement_id, event_type),
    CONSTRAINT fk_commercial_settlement_lines_settlement FOREIGN KEY (settlement_id) REFERENCES commercial_settlements(id),
    CONSTRAINT fk_commercial_settlement_lines_placement FOREIGN KEY (placement_id) REFERENCES commercial_placements(id),
    CONSTRAINT chk_commercial_settlement_lines_event CHECK (event_type IN ('IMPRESSION','CLICK','COMPLETE','FIXED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
