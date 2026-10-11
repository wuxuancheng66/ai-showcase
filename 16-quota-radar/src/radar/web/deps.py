"""FastAPI 依赖：每请求一个 SQLite 连接。"""

from radar.db import connect


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
