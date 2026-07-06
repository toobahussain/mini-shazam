import os
from contextlib import contextmanager
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/shazam",
)


@contextmanager
def get_conn():
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_song(title: str, artist: str = "") -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO songs (title, artist) VALUES (%s, %s) RETURNING id",
                (title, artist),
            )
            return cur.fetchone()[0]


def store_fingerprints(song_id: int, hashes):
    """hashes: list of (hash, offset_time) tuples"""
    rows = [(h, song_id, offset) for h, offset in hashes]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO fingerprints (hash, song_id, offset_time) VALUES (%s, %s, %s)",
                rows,
            )


def lookup_hashes(hashes):
    """
    hashes: list of (hash, offset_time) tuples from the clip being identified.
    Returns rows of (hash, song_id, db_offset_time) for every matching hash
    found in the database.
    """
    hash_values = [h for h, _ in hashes]
    if not hash_values:
        return []

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT hash, song_id, offset_time FROM fingerprints WHERE hash = ANY(%s)",
                (hash_values,),
            )
            return cur.fetchall()


def get_song(song_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, artist FROM songs WHERE id = %s", (song_id,))
            return cur.fetchone()


def list_songs():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, artist FROM songs ORDER BY id")
            return cur.fetchall()
