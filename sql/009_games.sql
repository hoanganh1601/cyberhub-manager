-- Đợt 3: game đầu tiên (vòng quay may mắn) và xu game.
-- Xu game là đơn vị riêng: không phải tiền trong ví, không phải điểm thành viên;
-- chỉ đổi được sang voucher theo danh mục (reward_catalog.coin_cost).

CREATE TABLE games (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(60) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    daily_limit INT NOT NULL,             -- số lượt mỗi tài khoản mỗi ngày (giờ Việt Nam)
    min_interval_seconds INT NOT NULL,    -- khoảng cách tối thiểu giữa hai lượt
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_games PRIMARY KEY (id),
    CONSTRAINT uq_games_code UNIQUE (code),
    CONSTRAINT chk_games_daily_limit CHECK (daily_limit BETWEEN 1 AND 20),
    CONSTRAINT chk_games_interval CHECK (min_interval_seconds BETWEEN 1 AND 60)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE game_prizes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    game_id BIGINT UNSIGNED NOT NULL,
    sort_order INT NOT NULL,              -- vị trí ô trên vòng quay (0, 1, 2, ...)
    label VARCHAR(40) NOT NULL,
    coins INT NOT NULL,                   -- 0 = "Chúc may mắn lần sau"
    weight INT NOT NULL,                  -- tỉ lệ trúng tương đối
    CONSTRAINT pk_game_prizes PRIMARY KEY (id),
    CONSTRAINT uq_game_prizes_slot UNIQUE (game_id, sort_order),
    CONSTRAINT fk_game_prizes_game FOREIGN KEY (game_id)
        REFERENCES games (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_game_prizes_coins CHECK (coins BETWEEN 0 AND 1000),
    CONSTRAINT chk_game_prizes_weight CHECK (weight BETWEEN 1 AND 1000),
    CONSTRAINT chk_game_prizes_label CHECK (CHAR_LENGTH(TRIM(label)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Một ví xu cho mỗi tài khoản khách; khóa được khi phát hiện bất thường.
CREATE TABLE game_wallets (
    account_id BIGINT UNSIGNED NOT NULL,
    balance BIGINT NOT NULL DEFAULT 0,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    locked_reason VARCHAR(200) NULL,
    locked_at DATETIME NULL,
    suspicious_count INT NOT NULL DEFAULT 0,   -- số lần bị chặn (quá lượt/quá nhanh) trong ngày
    suspicious_on DATE NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_game_wallets PRIMARY KEY (account_id),
    CONSTRAINT fk_game_wallets_account FOREIGN KEY (account_id)
        REFERENCES accounts (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_game_wallets_balance CHECK (balance >= 0),
    CONSTRAINT chk_game_wallets_lock CHECK (
        (is_locked = TRUE AND locked_reason IS NOT NULL AND locked_at IS NOT NULL)
        OR (is_locked = FALSE AND locked_reason IS NULL AND locked_at IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Lịch sử phiên chơi: giải thưởng chụp lại (nhãn, ô, số xu) để sửa vòng quay không đổi lịch sử.
CREATE TABLE game_sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    account_id BIGINT UNSIGNED NOT NULL,
    game_id BIGINT UNSIGNED NOT NULL,
    prize_index INT NOT NULL,
    prize_label VARCHAR(40) NOT NULL,
    coins INT NOT NULL,
    played_on DATE NOT NULL,              -- ngày theo giờ Việt Nam, dùng đếm lượt
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_game_sessions PRIMARY KEY (id),
    CONSTRAINT fk_game_sessions_account FOREIGN KEY (account_id)
        REFERENCES accounts (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_game_sessions_game FOREIGN KEY (game_id)
        REFERENCES games (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_game_sessions_coins CHECK (coins BETWEEN 0 AND 1000),
    INDEX idx_game_sessions_account_day (account_id, played_on),
    INDEX idx_game_sessions_game_time (game_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Sổ cái xu: mọi thay đổi số dư xu đều có đúng một dòng. UNIQUE(reason, ref) chống ghi trùng
-- (một phiên chơi chỉ cộng một lần, một khóa đổi thưởng chỉ trừ một lần).
CREATE TABLE game_coin_ledger (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    account_id BIGINT UNSIGNED NOT NULL,
    delta BIGINT NOT NULL,
    reason VARCHAR(10) NOT NULL,
    ref VARCHAR(64) NOT NULL,
    balance_after BIGINT NOT NULL,
    voucher_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_game_coin_ledger PRIMARY KEY (id),
    CONSTRAINT uq_game_coin_ledger_ref UNIQUE (reason, ref),
    CONSTRAINT fk_game_coin_ledger_account FOREIGN KEY (account_id)
        REFERENCES accounts (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_game_coin_ledger_voucher FOREIGN KEY (voucher_id)
        REFERENCES customer_vouchers (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_game_coin_ledger_reason CHECK (reason IN ('PLAY', 'REDEEM', 'AD', 'ADJUST')),
    CONSTRAINT chk_game_coin_ledger_delta CHECK (delta <> 0),
    CONSTRAINT chk_game_coin_ledger_balance CHECK (balance_after >= 0),
    INDEX idx_game_coin_ledger_account (account_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Vòng quay mặc định: 3 lượt/ngày, cách nhau tối thiểu 3 giây; trung bình ~11 xu/lượt.
INSERT INTO games (code, name, is_active, daily_limit, min_interval_seconds)
VALUES ('LUCKY_WHEEL', 'Vòng quay CyberHub', TRUE, 3, 3);
INSERT INTO game_prizes (game_id, sort_order, label, coins, weight)
SELECT id, s.sort_order, s.label, s.coins, s.weight
FROM games
JOIN (
    SELECT 0 AS sort_order, '5 xu' AS label, 5 AS coins, 30 AS weight
    UNION ALL SELECT 1, 'Chúc may mắn', 0, 25
    UNION ALL SELECT 2, '10 xu', 10, 25
    UNION ALL SELECT 3, '20 xu', 20, 15
    UNION ALL SELECT 4, '50 xu', 50, 5
    UNION ALL SELECT 5, '100 xu', 100, 2
) AS s
WHERE games.code = 'LUCKY_WHEEL';
