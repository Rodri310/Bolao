"""
data_manager.py — Carrega e combina dados do bolão com resultados do DB.

Os palpites (fato_palpites) são estáticos — lidos uma vez do HTML e cacheados.
Os resultados reais são sempre lidos do SQLite (atualizado pelo scheduler).
"""
import os
import logging
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

HTML_PATH = os.getenv("HTML_PATH", "auditoria-guerreiros (1).html")

# Cache dos dados estáticos (palpites não mudam)
_static_cache: dict | None = None


def _load_static() -> dict | None:
    """Lê o HTML e cacheia dim_jogos, dim_membros, fato_palpites."""
    global _static_cache
    if _static_cache is not None:
        return _static_cache

    try:
        from Data_get import extrair_dados_bolao
        dim_jogos, dim_membros, fato_palpites = extrair_dados_bolao(HTML_PATH)

        # Normalizar tipos
        dim_jogos["match_id"]       = dim_jogos["match_id"].astype(str)
        dim_membros["member_id"]    = dim_membros["member_id"].astype(str)
        fato_palpites["match_id"]   = fato_palpites["match_id"].astype(str)
        fato_palpites["member_id"]  = fato_palpites["member_id"].astype(str)

        # Garantir coluna 'name' em dim_membros
        if "name" not in dim_membros.columns:
            for alt in ["nome", "username", "user"]:
                if alt in dim_membros.columns:
                    dim_membros = dim_membros.rename(columns={alt: "name"})
                    break
            else:
                dim_membros["name"] = dim_membros["member_id"]

        # Parsear datas no formato 'Quinta, 11/06' (sem ano)
        def parse_data_jogo(val):
            try:
                # Extrai a parte 'DD/MM' após a vírgula
                parte = str(val).split(',')[-1].strip()   # '11/06'
                return pd.to_datetime(parte + '/2026', format='%d/%m/%Y', errors='coerce')
            except Exception:
                return pd.NaT

        dim_jogos['data_dt'] = dim_jogos['data_jogo'].apply(parse_data_jogo)

        # Ordenar jogos por data e hora
        dim_jogos = dim_jogos.sort_values("data_dt").reset_index(drop=True)

        _static_cache = {
            "dim_jogos":     dim_jogos,
            "dim_membros":   dim_membros,
            "fato_palpites": fato_palpites,
        }
        logger.info(
            "Dados carregados: %d jogos, %d membros, %d palpites",
            len(dim_jogos), len(dim_membros), len(fato_palpites),
        )
    except Exception as exc:
        logger.error("Falha ao carregar dados do HTML: %s", exc)
        return None

    return _static_cache


def get_bolao_data() -> dict | None:
    """Retorna o cache estático (dim_jogos, dim_membros, fato_palpites)."""
    return _load_static()


def get_full_df():
    """
    Retorna (df_completo, dim_jogos_com_resultado, dim_membros).

    df_completo: fato_palpites + info de membros + info de jogos + resultado + pontos
    """
    from db import get_all_results
    from scoring import calcular_pontos

    static = _load_static()
    if static is None:
        return None

    dim_jogos    = static["dim_jogos"].copy()
    dim_membros  = static["dim_membros"].copy()
    fato_palpites = static["fato_palpites"].copy()

    # Mesclar resultados do DB
    results = get_all_results()
    if not results.empty:
        results["match_id"] = results["match_id"].astype(str)
        dim_jogos = dim_jogos.merge(
            results[["match_id", "score_home", "score_away", "status"]],
            on="match_id", how="left"
        )
    else:
        dim_jogos["score_home"] = None
        dim_jogos["score_away"] = None
        dim_jogos["status"]     = "SCHEDULED"

    # Montar DF completo
    df = fato_palpites.merge(dim_membros, on="member_id", how="left")
    df = df.merge(dim_jogos, on="match_id", how="left")

    # Calcular pontos
    df["pontos"] = df.apply(
        lambda r: calcular_pontos(
            r["placar_mandante"], r["placar_visitante"],
            r.get("score_home"),  r.get("score_away"),
        ),
        axis=1,
    )

    return df, dim_jogos, dim_membros
