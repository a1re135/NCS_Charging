"""One-time, transactional demo expansion; existing IDs and business data are preserved."""
NEW_STATIONS = [
    ('房山 · 良乡充电站', '北京市房山区良乡区域', '北京市房山区', 116.1433, 39.7479, 145),
    ('大兴 · 黄村充电站', '北京市大兴区黄村区域', '北京市大兴区', 116.3380, 39.7289, 145),
    ('通州 · 运河充电站', '北京市通州区运河区域', '北京市通州区', 116.6564, 39.9099, 150),
    ('昌平 · 未来充电站', '北京市昌平区城区区域', '北京市昌平区', 116.2312, 40.2207, 150),
    ('顺义 · 空港充电站', '北京市顺义区城区区域', '北京市顺义区', 116.6546, 40.1302, 155),
]
VERSION = 'demo_ten_stations_ten_chargers_v1'

def expand_network(db):
    from .db import _add_default_pricing

    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS ncs_data_migrations (
            version VARCHAR(80) PRIMARY KEY,
            completed INTEGER NOT NULL DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        '''
    )

    db.execute(
        '''
        INSERT IGNORE INTO ncs_data_migrations(
            version,
            completed
        )
        VALUES(?, 0)
        ''',
        (VERSION,),
    )

    db.begin()

    try:
        row = db.execute(
            '''
            SELECT completed
            FROM ncs_data_migrations
            WHERE version=?
            FOR UPDATE
            ''',
            (VERSION,),
        ).fetchone()

        if row and row['completed']:
            db.commit()
            return

        # Add the extra demo stations if they do not exist yet.
        for (
            name,
            address,
            city,
            lng,
            lat,
            price,
        ) in NEW_STATIONS:

            existing = db.execute(
                '''
                SELECT id
                FROM stations
                WHERE name=?
                ''',
                (name,),
            ).fetchone()

            if existing:
                continue

            cur = db.execute(
                '''
                INSERT INTO stations(
                    name,
                    address,
                    city,
                    business_hours,
                    contact_phone,
                    operating_status,
                    parking_info,
                    lng,
                    lat,
                    price_cents
                )
                VALUES(
                    ?,
                    ?,
                    ?,
                    '00:00-24:00',
                    '010-00000000',
                    'operating',
                    '演示站点，停车规则以现场公告为准',
                    ?,
                    ?,
                    ?
                )
                ''',
                (
                    name,
                    address,
                    city,
                    lng,
                    lat,
                    price,
                ),
            )

            _add_default_pricing(
                db,
                cur.lastrowid,
                price,
            )

        # Ensure every station has at least 10 chargers.
        for station in db.execute(
            '''
            SELECT id
            FROM stations
            '''
        ).fetchall():

            sid = station['id']

            count = db.execute(
                '''
                SELECT COUNT(*) AS n
                FROM chargers
                WHERE station_id=?
                ''',
                (sid,),
            ).fetchone()['n']

            number_index = 1

            while count < 10:
                number = (
                    f'NCS-{sid:02d}'
                    f'{number_index:02d}'
                )

                number_index += 1

                existing_charger = db.execute(
                    '''
                    SELECT id
                    FROM chargers
                    WHERE number=?
                    ''',
                    (number,),
                ).fetchone()

                if existing_charger:
                    continue

                fast = count < 8

                db.execute(
                    '''
                    INSERT INTO chargers(
                        station_id,
                        number,
                        kind,
                        power,
                        status
                    )
                    VALUES(?,?,?,?,?)
                    ''',
                    (
                        sid,
                        number,
                        (
                            'fast'
                            if fast
                            else 'slow'
                        ),
                        (
                            60
                            if fast
                            else 7
                        ),
                        'idle',
                    ),
                )

                count += 1

        db.execute(
            '''
            UPDATE ncs_data_migrations
            SET completed=1
            WHERE version=?
            ''',
            (VERSION,),
        )

        db.commit()

    except Exception:
        db.rollback()
        raise