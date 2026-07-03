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

HTML_PATH    = os.getenv("HTML_PATH",    "auditoria-guerreiros (1).html")
HTML_R32_PATH = os.getenv("HTML_R32_PATH", "palpites-16avos.html")

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

        # ── Carregar palpites do mata-mata (R32) ────────────────────────────
        import os as _os
        if _os.path.exists(HTML_R32_PATH):
            try:
                from Data_get_knockout import extrair_dados_knockout
                dim_jogos_r32, fato_palpites_r32 = extrair_dados_knockout(HTML_R32_PATH)

                if not dim_jogos_r32.empty:
                    dim_jogos_r32["match_id"] = dim_jogos_r32["match_id"].astype(str)

                    # Adicionar colunas ausentes para manter compatibilidade com dim_jogos
                    for col in dim_jogos.columns:
                        if col not in dim_jogos_r32.columns:
                            dim_jogos_r32[col] = None

                    dim_jogos = pd.concat(
                        [dim_jogos, dim_jogos_r32[dim_jogos.columns]], ignore_index=True
                    )
                    logger.info("Jogos R32 adicionados: %d jogos totais", len(dim_jogos))

                if not fato_palpites_r32.empty:
                    fato_palpites_r32["match_id"] = fato_palpites_r32["match_id"].astype(str)

                    # Resolver member_id pelo nome (join com dim_membros)
                    name_to_id = dict(
                        zip(dim_membros["name"].str.strip(),
                            dim_membros["member_id"])
                    )
                    fato_palpites_r32["member_id"] = (
                        fato_palpites_r32["member_name"]
                        .str.strip()
                        .map(name_to_id)
                    )

                    # Participantes sem match de nome: logar e ignorar
                    sem_id = fato_palpites_r32["member_id"].isna()
                    if sem_id.any():
                        nomes = fato_palpites_r32.loc[sem_id, "member_name"].unique()
                        logger.warning(
                            "Participantes das oitavas sem member_id correspondente: %s",
                            list(nomes)
                        )

                    fato_palpites_r32 = fato_palpites_r32.dropna(subset=["member_id"])
                    fato_palpites_r32["member_id"] = fato_palpites_r32["member_id"].astype(str)

                    # Manter apenas colunas compatíveis com fato_palpites
                    cols_fp = ["member_id", "match_id", "placar_mandante", "placar_visitante"]
                    fato_palpites = pd.concat(
                        [fato_palpites, fato_palpites_r32[cols_fp]], ignore_index=True
                    )
                    logger.info("Palpites R32 adicionados: %d palpites totais", len(fato_palpites))

            except Exception as exc_r32:
                logger.warning("Falha ao carregar palpites R32: %s", exc_r32)
        else:
            logger.info("HTML das oitavas não encontrado em '%s' — pulando.", HTML_R32_PATH)

        # Parsear datas — fase de grupos: 'Quinta, 11/06'; mata-mata: '28/06'
        def parse_data_jogo(val):
            try:
                # Extrai a parte 'DD/MM' após a vírgula (fase de grupos)
                # ou usa diretamente se já vier no formato 'DD/MM'
                parte = str(val).split(',')[-1].strip()   # '11/06' ou '28/06'
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
            results[["match_id", "score_home", "score_away",
                      "score_home_90", "score_away_90", "status"]],
            on="match_id", how="left"
        )
    else:
        dim_jogos["score_home"]    = None
        dim_jogos["score_away"]    = None
        dim_jogos["score_home_90"] = None
        dim_jogos["score_away_90"] = None
        dim_jogos["status"]        = "SCHEDULED"

    # Montar DF completo
    df = fato_palpites.merge(dim_membros, on="member_id", how="left")
    df = df.merge(dim_jogos, on="match_id", how="left")

    # Calcular pontos usando o placar dos 90 minutos (tempo regulamentar).
    # score_home_90 / score_away_90 ja estao corretos para todos os jogos:
    #   - Fase de grupos: igual ao placar final (sem prorrogacao).
    #   - Mata-mata com prorrogacao: placar ao fim dos 90 min (sem gols da prorrogacao).
    df["pontos"] = df.apply(
        lambda r: calcular_pontos(
            r["placar_mandante"], r["placar_visitante"],
            r.get("score_home_90"),  r.get("score_away_90"),
        ),
        axis=1,
    )

    return df, dim_jogos, dim_membros
