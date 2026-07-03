"""
db.py — Acesso ao SQLite para resultados reais dos jogos.
Os palpites são imutáveis (vêm do HTML); apenas os resultados reais são armazenados aqui.

Coluna score_home_90 / score_away_90:
  Placar ao final dos 90 minutos (tempo regulamentar), sem prorrogacao.
  Para jogos da fase de grupos, e igual ao score_home/score_away (sem prorrogacao).
  Para jogos do mata-mata com prorrogacao, pode diferir do placar final.
  Usado como referencia para calculo de pontos.
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
    """Cria a tabela de resultados se nao existir e adiciona colunas novas."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_results (
            match_id      TEXT PRIMARY KEY,
            score_home    INTEGER NOT NULL,
            score_away    INTEGER NOT NULL,
            status        TEXT    NOT NULL DEFAULT 'FINISHED',
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Adicionar colunas de placar dos 90 min (sem prorrogacao) se ainda nao existirem
    for col in ("score_home_90", "score_away_90"):
        try:
            conn.execute(f"ALTER TABLE match_results ADD COLUMN {col} INTEGER")
        except Exception:
            pass  # Coluna ja existe
    conn.commit()
    conn.close()
    logger.info("DB inicializado em %s", DB_PATH)


def save_result(
    match_id: str,
    score_home: int,
    score_away: int,
    status: str = "FINISHED",
    score_home_90: int | None = None,
    score_away_90: int | None = None,
):
    """
    Insere ou atualiza o resultado de uma partida.

    score_home / score_away     : placar final (incluindo prorrogacao se houver)
    score_home_90 / score_away_90: placar ao fim dos 90 minutos regulamentares.
                                   Se None, assume igual ao placar final.
    """
    h90 = int(score_home_90) if score_home_90 is not None else int(score_home)
    a90 = int(score_away_90) if score_away_90 is not None else int(score_away)

    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO match_results
            (match_id, score_home, score_away, status, score_home_90, score_away_90, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (str(match_id), int(score_home), int(score_away), status, h90, a90))
    conn.commit()
    conn.close()
    logger.debug(
        "Resultado salvo: match_id=%s %d-%d (90min: %d-%d)",
        match_id, score_home, score_away, h90, a90,
    )


def get_all_results() -> pd.DataFrame:
    """Retorna todos os resultados como DataFrame."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM match_results", conn)
        # Garantir colunas de 90 min (retrocompatibilidade com registros antigos)
        if "score_home_90" not in df.columns:
            df["score_home_90"] = df["score_home"]
            df["score_away_90"] = df["score_away"]
        else:
            # Preencher NULLs com o placar final (registros antes da migracao)
            mask = df["score_home_90"].isna()
            df.loc[mask, "score_home_90"] = df.loc[mask, "score_home"]
            df.loc[mask, "score_away_90"] = df.loc[mask, "score_away"]
    except Exception as exc:
        logger.warning("Erro ao ler resultados do DB: %s", exc)
        df = pd.DataFrame(columns=[
            "match_id", "score_home", "score_away", "status",
            "score_home_90", "score_away_90", "updated_at",
        ])
    finally:
        conn.close()
    return df
