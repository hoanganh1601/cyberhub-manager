-- Existing machines are STANDARD until a manager explicitly classifies them.
CREATE TABLE machine_room_types (
    machine_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    room_type VARCHAR(10) NOT NULL,
    CONSTRAINT fk_machine_room_machine FOREIGN KEY (machine_id) REFERENCES machines(id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT chk_machine_room_type CHECK (room_type IN ('STANDARD','VIP'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Password changes revoke older customer sessions without affecting employee logins.
ALTER TABLE accounts ADD COLUMN auth_version BIGINT UNSIGNED NOT NULL DEFAULT 0;
