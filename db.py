"""
db.py — Acesso ao SQLite para resultados reais dos jogos.
Os palpites são imutáveis (vêm do HTML); apenas os resultados reais são armazenados aqui.
"""
import sqlite3
import os
import logging
import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "results.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria a tabela de resultados se não existir."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_results (
            match_id   TEXT PRIMARY KEY,
            score_home INTEGER NOT NULL,
            score_away INTEGER NOT NULL,
            status     TEXT    NOT NULL DEFAULT 'FINISHED',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("DB inicializado em %s", DB_PATH)


def save_result(match_id: str, score_home: int, score_away: int, status: str = "FINISHED"):
    """Insere ou atualiza o resultado de uma partida."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO match_results (match_id, score_home, score_away, status, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (str(match_id), int(score_home), int(score_away), status))
    conn.commit()
    conn.close()
    logger.debug("Resultado salvo: match_id=%s %d x %d", match_id, score_home, score_away)


def get_all_results() -> pd.DataFrame:
    """Retorna todos os resultados como DataFrame."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM match_results", conn)
    except Exception as exc:
        logger.warning("Erro ao ler resultados do DB: %s", exc)
        df = pd.DataFrame(columns=["match_id", "score_home", "score_away", "status", "updated_at"])
    finally:
        conn.close()
    return df
