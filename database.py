import os
import psycopg2
from urllib.parse import urlparse
from passlib.hash import pbkdf2_sha256

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

def init_db():
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()

        # Periksa apakah tabel urls ada
        c.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'urls'
            );
        """)
        table_exists = c.fetchone()[0]

        if not table_exists:
            # Buat tabel urls jika belum ada
            c.execute('''CREATE TABLE urls (
                short_code TEXT PRIMARY KEY,
                original_url TEXT,
                clicks INTEGER DEFAULT 0,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
        else:
            # Periksa struktur tabel urls dan tambahkan kolom jika belum ada
            c.execute("""
                SELECT column_name, data_type, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'urls';
            """)
            columns = {row[0]: (row[1], row[2]) for row in c.fetchall()}

            expected_columns = {
                'short_code': ('text', None),
                'original_url': ('text', None),
                'clicks': ('integer', '0'),
                'created_by': ('text', None),
                'created_at': ('timestamp without time zone', 'CURRENT_TIMESTAMP')
            }

            for col, (dtype, default) in expected_columns.items():
                if col not in columns:
                    c.execute(f"ALTER TABLE urls ADD COLUMN {col} {dtype} {'NOT NULL' if col == 'created_by' else ''} DEFAULT {default if default else 'NULL'}")
                elif columns[col][0] != dtype or (columns[col][1] != default and not (columns[col][1] is None and default is None)):
                    c.execute("DROP TABLE urls")
                    c.execute('''CREATE TABLE urls (
                        short_code TEXT PRIMARY KEY,
                        original_url TEXT,
                        clicks INTEGER DEFAULT 0,
                        created_by TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
                    break

        # Periksa apakah tabel users ada
        c.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            );
        """)
        users_table_exists = c.fetchone()[0]

        if not users_table_exists:
            c.execute('''CREATE TABLE users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )''')
            default_password = pbkdf2_sha256.hash("swordart123")
            c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ("seoxxx", default_password))
        else:
            c.execute("SELECT COUNT(*) FROM users WHERE username = %s", ("seoxxx",))
            user_exists = c.fetchone()[0]
            if user_exists == 0:
                default_password = pbkdf2_sha256.hash("swordart123")
                c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ("seoxxx", default_password))
            else:
                default_password = pbkdf2_sha256.hash("swordart123")
                c.execute("UPDATE users SET password = %s WHERE username = %s", (default_password, "seoxxx"))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error in init_db: {e}")

def save_url(short_code, original_url, created_by):
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()
        c.execute("INSERT INTO urls (short_code, original_url, clicks, created_by) VALUES (%s, %s, 0, %s) ON CONFLICT (short_code) DO UPDATE SET original_url = %s",
                  (short_code, original_url, created_by, original_url))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error in save_url: {e}")
        raise

def get_url(short_code):
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()
        c.execute("SELECT original_url FROM urls WHERE short_code = %s", (short_code,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error in get_url: {e}")
        raise

def increment_clicks(short_code):
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()
        c.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = %s", (short_code,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error in increment_clicks: {e}")
        raise

def get_clicks(short_code):
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()
        c.execute("SELECT clicks FROM urls WHERE short_code = %s", (short_code,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        print(f"Error in get_clicks: {e}")
        raise

def verify_user(username, password):
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = %s", (username,))
        result = c.fetchone()
        conn.close()
        if result and pbkdf2_sha256.verify(password, result[0]):
            return True
        return False
    except Exception as e:
        print(f"Error in verify_user: {e}")
        raise

def get_user_urls(username, page=1, per_page=10):
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()
        # Hitung total data untuk pagination
        c.execute("SELECT COUNT(*) FROM urls WHERE created_by = %s", (username,))
        total_urls = c.fetchone()[0]

        # Hitung offset berdasarkan halaman
        offset = (page - 1) * per_page

        # Ambil data dengan limit, offset, dan urutkan dari yang terbaru (ORDER BY created_at DESC)
        c.execute(
            "SELECT short_code, original_url, clicks FROM urls WHERE created_by = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (username, per_page, offset)
        )
        result = c.fetchall()
        conn.close()
        return result, total_urls
    except Exception as e:
        print(f"Error in get_user_urls: {e}")
        raise

def update_url(short_code, new_original_url, new_short_code):
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()
        if short_code != new_short_code:
            # Jika short_code berubah, pastikan yang baru belum digunakan
            c.execute("SELECT short_code FROM urls WHERE short_code = %s", (new_short_code,))
            if c.fetchone():
                conn.close()
                return False  # Short code sudah digunakan
            c.execute("UPDATE urls SET short_code = %s, original_url = %s WHERE short_code = %s",
                      (new_short_code, new_original_url, short_code))
        else:
            c.execute("UPDATE urls SET original_url = %s WHERE short_code = %s",
                      (new_original_url, short_code))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error in update_url: {e}")
        raise

def delete_url(short_code):
    try:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        c = conn.cursor()
        c.execute("DELETE FROM urls WHERE short_code = %s", (short_code,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error in delete_url: {e}")
        raise