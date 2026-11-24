-- Strict 3NF follow-up: remove business dates that are functionally derived
-- from authoritative UTC timestamps in game and advertising event tables.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

DROP PROCEDURE IF EXISTS validate_031_business_days;
DELIMITER $$
CREATE PROCEDURE validate_031_business_days()
BEGIN
    IF EXISTS (
        SELECT 1 FROM game_sessions
        WHERE played_on <> DATE(DATE_ADD(created_at, INTERVAL 7 HOUR))
        LIMIT 1
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = '031 aborted: game_sessions.played_on conflicts with created_at UTC+7';
    END IF;

    IF EXISTS (
        SELECT 1 FROM ad_reward_events
        WHERE played_on <> DATE(DATE_ADD(issued_at, INTERVAL 7 HOUR))
        LIMIT 1
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = '031 aborted: ad_reward_events.played_on conflicts with issued_at UTC+7';
    END IF;
END$$
DELIMITER ;

CALL validate_031_business_days();
DROP PROCEDURE validate_031_business_days;

ALTER TABLE game_sessions
    DROP INDEX idx_game_sessions_account_day,
    DROP COLUMN played_on,
    ADD INDEX idx_game_sessions_account_game_time (account_id, game_id, created_at);

ALTER TABLE ad_reward_events
    DROP INDEX idx_ad_reward_events_account_day,
    DROP INDEX idx_ad_reward_events_day,
    DROP COLUMN played_on,
    ADD INDEX idx_ad_reward_events_account_time (account_id, issued_at),
    ADD INDEX idx_ad_reward_events_reward_time (account_id, status, reward_type, issued_at),
    ADD INDEX idx_ad_reward_events_issued_at (issued_at);
