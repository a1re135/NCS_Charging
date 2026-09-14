MYSQL_SCHEMA = [

"""
CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    phone VARCHAR(32) NOT NULL,
    nickname VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    role VARCHAR(32) NOT NULL DEFAULT 'user',

    balance_cents BIGINT NOT NULL DEFAULT 0,

    avatar VARCHAR(50) NOT NULL DEFAULT 'lavender',
    active TINYINT(1) NOT NULL DEFAULT 1,

    created_at VARCHAR(32) NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_users_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""",

"""
CREATE TABLE IF NOT EXISTS stations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NOT NULL,

    city VARCHAR(100) NOT NULL DEFAULT '北京市',
    business_hours VARCHAR(100) NOT NULL DEFAULT '00:00-24:00',
    contact_phone VARCHAR(50) NOT NULL DEFAULT '010-00000000',

    operating_status VARCHAR(32) NOT NULL DEFAULT 'operating',

    parking_info VARCHAR(500) NOT NULL DEFAULT '以现场停车规定为准',

    lng DOUBLE NOT NULL,
    lat DOUBLE NOT NULL,

    price_cents INT UNSIGNED NOT NULL,

    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""",

"""
CREATE TABLE IF NOT EXISTS chargers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    station_id BIGINT UNSIGNED NOT NULL,

    number VARCHAR(100) NOT NULL,

    kind VARCHAR(32) NOT NULL,

    power DOUBLE NOT NULL,

    status VARCHAR(32) NOT NULL DEFAULT 'idle',

    total_count BIGINT NOT NULL DEFAULT 0,
    total_minutes BIGINT NOT NULL DEFAULT 0,

    PRIMARY KEY (id),

    UNIQUE KEY uk_charger_number (number),

    KEY idx_charger_station_status (
        station_id,
        status
    ),

    CONSTRAINT fk_charger_station
        FOREIGN KEY (station_id)
        REFERENCES stations(id)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""",

"""
CREATE TABLE IF NOT EXISTS orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    user_id BIGINT UNSIGNED NOT NULL,
    charger_id BIGINT UNSIGNED NOT NULL,

    status VARCHAR(32) NOT NULL,

    created_at VARCHAR(32) NOT NULL,
    expires_at VARCHAR(32) NULL,
    started_at VARCHAR(32) NULL,
    ended_at VARCHAR(32) NULL,

    price_cents INT UNSIGNED NOT NULL,

    electricity_fee_cents INT UNSIGNED NOT NULL DEFAULT 0,
    service_fee_cents INT UNSIGNED NOT NULL DEFAULT 0,

    power DOUBLE NOT NULL,
    time_scale INT NOT NULL,

    energy DOUBLE NOT NULL DEFAULT 0,

    amount_cents BIGINT NOT NULL DEFAULT 0,
    paid_cents BIGINT NOT NULL DEFAULT 0,
    debt_cents BIGINT NOT NULL DEFAULT 0,

    balance_after BIGINT NULL,

    simulated_seconds BIGINT NOT NULL DEFAULT 0,

    active_user_id BIGINT UNSIGNED
        GENERATED ALWAYS AS (
            CASE
                WHEN status IN ('reserved', 'charging')
                THEN user_id
                ELSE NULL
            END
        ) STORED,

    active_charger_id BIGINT UNSIGNED
        GENERATED ALWAYS AS (
            CASE
                WHEN status IN ('reserved', 'charging')
                THEN charger_id
                ELSE NULL
            END
        ) STORED,

    PRIMARY KEY (id),

    UNIQUE KEY one_active_user (
        active_user_id
    ),

    UNIQUE KEY one_active_charger (
        active_charger_id
    ),

    KEY idx_order_user_created (
        user_id,
        created_at
    ),

    KEY idx_order_charger_status (
        charger_id,
        status
    ),

    CONSTRAINT fk_order_user
        FOREIGN KEY (user_id)
        REFERENCES users(id),

    CONSTRAINT fk_order_charger
        FOREIGN KEY (charger_id)
        REFERENCES chargers(id)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""",

"""
CREATE TABLE IF NOT EXISTS pricing_rules (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    station_id BIGINT UNSIGNED NOT NULL,

    start_minute INT NOT NULL,
    end_minute INT NOT NULL,

    electricity_fee_cents INT UNSIGNED NOT NULL,
    service_fee_cents INT UNSIGNED NOT NULL,

    PRIMARY KEY (id),

    KEY idx_pricing_station (
        station_id,
        start_minute
    ),

    CONSTRAINT fk_pricing_station
        FOREIGN KEY (station_id)
        REFERENCES stations(id)
        ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""",

"""
CREATE TABLE IF NOT EXISTS fault_records (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    charger_id BIGINT UNSIGNED NOT NULL,

    fault_type VARCHAR(100) NOT NULL,

    description VARCHAR(500) NOT NULL,

    status VARCHAR(32) NOT NULL DEFAULT 'pending',

    reported_at VARCHAR(32) NOT NULL,
    handled_at VARCHAR(32) NULL,

    resolution VARCHAR(500) NULL,

    reporter_id BIGINT UNSIGNED NULL,
    handler_id BIGINT UNSIGNED NULL,

    open_charger_id BIGINT UNSIGNED
        GENERATED ALWAYS AS (
            CASE
                WHEN status IN ('pending', 'processing')
                THEN charger_id
                ELSE NULL
            END
        ) STORED,

    PRIMARY KEY (id),

    UNIQUE KEY one_open_fault (
        open_charger_id
    ),

    KEY idx_fault_charger (
        charger_id,
        reported_at
    ),

    CONSTRAINT fk_fault_charger
        FOREIGN KEY (charger_id)
        REFERENCES chargers(id),

    CONSTRAINT fk_fault_reporter
        FOREIGN KEY (reporter_id)
        REFERENCES users(id),

    CONSTRAINT fk_fault_handler
        FOREIGN KEY (handler_id)
        REFERENCES users(id)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""",

"""
CREATE TABLE IF NOT EXISTS wallet_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    user_id BIGINT UNSIGNED NOT NULL,

    amount_cents BIGINT NOT NULL,

    kind VARCHAR(100) NOT NULL,

    created_at VARCHAR(32) NOT NULL,

    PRIMARY KEY (id),

    KEY idx_wallet_user (
        user_id,
        created_at
    ),

    CONSTRAINT fk_wallet_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
""",

"""
CREATE TABLE IF NOT EXISTS ops_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    actor_id BIGINT UNSIGNED NULL,

    operation VARCHAR(500) NOT NULL,

    created_at VARCHAR(32) NOT NULL,

    PRIMARY KEY (id),

    KEY idx_ops_actor (
        actor_id,
        created_at
    ),

    CONSTRAINT fk_ops_actor
        FOREIGN KEY (actor_id)
        REFERENCES users(id)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

]