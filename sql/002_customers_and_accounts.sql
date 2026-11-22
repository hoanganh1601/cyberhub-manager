-- Customer profiles, prepaid wallet accounts, and top-up bonus promotions.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE customers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone CHAR(10) NOT NULL,
    email VARCHAR(254) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_customers PRIMARY KEY (id),
    CONSTRAINT uq_customers_code UNIQUE (code),
    CONSTRAINT uq_customers_phone UNIQUE (phone),
    CONSTRAINT uq_customers_email UNIQUE (email),
    CONSTRAINT chk_customers_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_customers_full_name_length CHECK (CHAR_LENGTH(TRIM(full_name)) BETWEEN 2 AND 100),
    CONSTRAINT chk_customers_phone_format CHECK (REGEXP_LIKE(phone, '^0[0-9]{9}$', 'c')),
    CONSTRAINT chk_customers_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE accounts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    username VARCHAR(30) NOT NULL,
    password_hash VARCHAR(255) NULL,
    balance BIGINT NOT NULL DEFAULT 0,
    bonus_balance BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    auth_version BIGINT UNSIGNED NOT NULL DEFAULT 0,
    web_login_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_accounts PRIMARY KEY (id),
    CONSTRAINT uq_accounts_code UNIQUE (code),
    CONSTRAINT uq_accounts_customer UNIQUE (customer_id),
    CONSTRAINT uq_accounts_username UNIQUE (username),
    CONSTRAINT fk_accounts_customer
        FOREIGN KEY (customer_id) REFERENCES customers (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_accounts_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_accounts_username_format CHECK (REGEXP_LIKE(username, '^[A-Za-z0-9_.]{4,30}$', 'c')),
    CONSTRAINT chk_accounts_password_hash_not_blank CHECK (
        password_hash IS NULL OR CHAR_LENGTH(TRIM(password_hash)) > 0
    ),
    CONSTRAINT chk_accounts_balance_and_bonus CHECK (
        balance >= 0 AND bonus_balance >= 0 AND bonus_balance <= balance
    ),
    CONSTRAINT chk_accounts_status CHECK (status IN ('ACTIVE', 'LOCKED'))
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE promotions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    store_id BIGINT UNSIGNED NULL,
    minimum_amount BIGINT NOT NULL,
    bonus_percent INT NOT NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_promotions PRIMARY KEY (id),
    CONSTRAINT uq_promotions_code UNIQUE (code),
    CONSTRAINT fk_promotions_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_promotions_amount CHECK (minimum_amount > 0 AND minimum_amount <= 100000000),
    CONSTRAINT chk_promotions_percent CHECK (bonus_percent BETWEEN 0 AND 100),
    CONSTRAINT chk_promotions_period CHECK (ends_at > starts_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
