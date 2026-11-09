-- Đợt 4: quảng cáo nhận thưởng (tự nguyện, có nhãn "Quảng cáo", không chặn chức năng cơ bản).
-- HOUSE  : quảng cáo nội bộ của CyberHub; máy chủ chỉ cộng thưởng khi đủ thời lượng xem theo đồng hồ máy chủ.
-- NETWORK: mạng quảng cáo bên ngoài; chỉ cộng thưởng khi nhà cung cấp gọi callback có chữ ký HMAC
--          (server-side verification). Khóa bí mật đọc từ biến môi trường, không lưu trong database.

CREATE TABLE ad_settings (
    id TINYINT UNSIGNED NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    mode VARCHAR(10) NOT NULL DEFAULT 'HOUSE',
    daily_cap INT NOT NULL DEFAULT 3,          -- số lần nhận thưởng tối đa mỗi tài khoản mỗi ngày
    reward_type VARCHAR(12) NOT NULL DEFAULT 'EXTRA_SPIN',
    reward_amount INT NOT NULL DEFAULT 1,      -- số lượt quay thêm hoặc số xu
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_ad_settings PRIMARY KEY (id),
    CONSTRAINT chk_ad_settings_singleton CHECK (id = 1),
    CONSTRAINT chk_ad_settings_mode CHECK (mode IN ('HOUSE', 'NETWORK')),
    CONSTRAINT chk_ad_settings_cap CHECK (daily_cap BETWEEN 1 AND 10),
    CONSTRAINT chk_ad_settings_reward CHECK (
        (reward_type = 'EXTRA_SPIN' AND reward_amount BETWEEN 1 AND 3)
        OR (reward_type = 'COINS' AND reward_amount BETWEEN 1 AND 100)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
INSERT INTO ad_settings (id) VALUES (1);

-- Nội dung quảng cáo nội bộ do CyberHub tự soạn.
CREATE TABLE ad_creatives (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    title VARCHAR(80) NOT NULL,
    body VARCHAR(300) NOT NULL,
    cta VARCHAR(40) NOT NULL DEFAULT '',
    duration_seconds INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_ad_creatives PRIMARY KEY (id),
    CONSTRAINT uq_ad_creatives_code UNIQUE (code),
    CONSTRAINT chk_ad_creatives_duration CHECK (duration_seconds BETWEEN 5 AND 60),
    CONSTRAINT chk_ad_creatives_title CHECK (CHAR_LENGTH(TRIM(title)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
INSERT INTO ad_creatives (code, title, body, cta, duration_seconds) VALUES
    ('COMBO_NIGHT', 'Combo đêm game chỉ từ 45.000đ', 'Mì xào bò + khoai tây chiên + nước ngọt, giao tận máy. Gọi ngay trong tab Menu đồ ăn.', 'Xem menu', 15),
    ('VIP_ROOM', 'Phòng VIP: ghế công thái học, màn 240Hz', 'Trải nghiệm phòng VIP của CyberHub, đặt máy tại quầy hoặc xem tình trạng phòng trong ứng dụng.', 'Xem phòng trống', 15),
    ('VOUCHER_WEEK', 'Tuần lễ voucher CyberHub', 'Quay thưởng mỗi ngày, gom xu và đổi voucher đồ ăn, nước uống, giờ chơi.', 'Đến vòng quay', 10);

-- Mỗi lần bắt đầu xem là một sự kiện có token dùng một lần; độc lập với kết quả game.
CREATE TABLE ad_reward_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    token CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    account_id BIGINT UNSIGNED NOT NULL,
    creative_id BIGINT UNSIGNED NULL,
    provider VARCHAR(10) NOT NULL,
    reward_type VARCHAR(12) NOT NULL,
    reward_amount INT NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'ISSUED',
    played_on DATE NOT NULL,                  -- ngày theo giờ Việt Nam, dùng giới hạn mỗi ngày
    issued_at DATETIME NOT NULL,
    min_complete_at DATETIME NOT NULL,        -- sớm nhất được nhận thưởng (issued_at + thời lượng)
    expires_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    provider_txn_id VARCHAR(80) NULL,         -- mã giao dịch của mạng quảng cáo (NETWORK)
    reject_reason VARCHAR(40) NULL,
    CONSTRAINT pk_ad_reward_events PRIMARY KEY (id),
    CONSTRAINT uq_ad_reward_events_token UNIQUE (token),
    CONSTRAINT uq_ad_reward_events_txn UNIQUE (provider_txn_id),
    CONSTRAINT fk_ad_reward_events_account FOREIGN KEY (account_id)
        REFERENCES accounts (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_ad_reward_events_creative FOREIGN KEY (creative_id)
        REFERENCES ad_creatives (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_ad_reward_events_provider CHECK (provider IN ('HOUSE', 'NETWORK')),
    CONSTRAINT chk_ad_reward_events_reward CHECK (reward_type IN ('EXTRA_SPIN', 'COINS') AND reward_amount > 0),
    CONSTRAINT chk_ad_reward_events_status CHECK (status IN ('ISSUED', 'COMPLETED', 'REJECTED')),
    CONSTRAINT chk_ad_reward_events_period CHECK (min_complete_at >= issued_at AND expires_at > min_complete_at),
    CONSTRAINT chk_ad_reward_events_done CHECK (
        (status = 'COMPLETED' AND completed_at IS NOT NULL AND reject_reason IS NULL)
        OR (status = 'REJECTED' AND reject_reason IS NOT NULL)
        OR (status = 'ISSUED' AND completed_at IS NULL)
    ),
    INDEX idx_ad_reward_events_account_day (account_id, played_on, status),
    INDEX idx_ad_reward_events_day (played_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
