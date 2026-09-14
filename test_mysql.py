import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

connection = pymysql.connect(
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

try:
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connection_test (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message VARCHAR(100) NOT NULL
            )
        """)

        cursor.execute(
            "INSERT INTO connection_test(message) VALUES (%s)",
            ("Python can write to MySQL",)
        )

        connection.commit()

        cursor.execute("SELECT * FROM connection_test")
        rows = cursor.fetchall()

        print(rows)

        cursor.execute("DROP TABLE connection_test")
        connection.commit()

        print("Create, insert, select and drop all successful!")

finally:
    connection.close()