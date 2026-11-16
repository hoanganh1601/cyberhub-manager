-- Professional employee credential lifecycle: temporary passwords and session revocation.
ALTER TABLE employees
    ADD COLUMN auth_version INT UNSIGNED NOT NULL DEFAULT 0,
    ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN password_changed_at DATETIME NULL;
