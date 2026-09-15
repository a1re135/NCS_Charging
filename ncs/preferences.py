"""Account preferences, stored separately to preserve existing business tables."""
from .db import get_db, now

SQLITE_SCHEMA = '''CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    language TEXT NOT NULL DEFAULT 'zh' CHECK(language IN ('zh','en')),
    theme TEXT NOT NULL DEFAULT 'system' CHECK(theme IN ('light','dark','system')),
    updated_at TEXT NOT NULL
)'''
MYSQL_SCHEMA = '''CREATE TABLE IF NOT EXISTS user_preferences (
    user_id BIGINT UNSIGNED NOT NULL,
    language VARCHAR(8) NOT NULL DEFAULT 'zh',
    theme VARCHAR(16) NOT NULL DEFAULT 'system',
    updated_at VARCHAR(32) NOT NULL,
    PRIMARY KEY (user_id),
    CONSTRAINT fk_preferences_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'''

def get_preferences(user_id):
    row = get_db().execute(
        'SELECT language,theme FROM user_preferences WHERE user_id=?', (user_id,)
    ).fetchone()
    return dict(row) if row else None

def save_preferences(user_id, language, theme, backend):
    # A single atomic upsert also handles two tabs saving for the first time.
    suffix = (
        'ON DUPLICATE KEY UPDATE language=VALUES(language),theme=VALUES(theme),updated_at=VALUES(updated_at)'
        if backend == 'mysql' else
        'ON CONFLICT(user_id) DO UPDATE SET language=excluded.language,theme=excluded.theme,updated_at=excluded.updated_at'
    )
    get_db().execute(
        'INSERT INTO user_preferences(user_id,language,theme,updated_at) VALUES(?,?,?,?) ' + suffix,
        (user_id, language, theme, now())
    )
    return {'language': language, 'theme': theme}
