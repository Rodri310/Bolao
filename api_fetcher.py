"""
api_fetcher.py — Busca resultados reais na football-data.org e salva no SQLite.
Chamado pelo APScheduler a cada 5 minutos.

Fallback: worldcup26.ir (open-source, gratuito, Copa 2026).
"""
import os
import re
import logging
import requests
from dotenv import load_dotenv
from db import save_result

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY  = os.getenv("FOOTBALL_API_KEY", "")
BASE_URL = "https://api.football-data.org/v4"

# Mapeamento de códigos portugueses/bolão → TLA da football-data.org
# (inclui apenas os casos onde diferem)
CODE_MAP = {
    "ALE": "GER",  # Alemanha
    "ING": "ENG",  # Inglaterra
    "HOL": "NED",  # Holanda
    "DIN": "DEN",  # Dinamarca
    "SUE": "SWE",  # Suécia
    "NOR": "NOR",
    "IRE": "IRL",  # Irlanda
    "GAL": "WAL",  # País de Gales
    "EUA": "USA",  # Estados Unidos
    "ESQ": "USA",
    "JAP": "JPN",  # Japão
    "CAM": "CMR",  # Camarões
    "GAN": "GHA",  # Gana
    "NIG": "NGA",  # Nigéria
    "EGI": "EGY",  # Egito
    "COT": "CIV",  # Costa do Marfim
    "SER": "SRB",  # Sérvia
    "ROM": "ROU",  # Romênia
    "CHE": "CZE",  # República Checa
    "URC": "UKR",  # Ucrânia
    "COC": "KOR",  # Coreia do Sul
    "ARA": "SAU",  # Arábia Saudita
    "IRA": "IRN",  # Irã
}


def _normalize(code: str) -> str:
    """Tenta mapear código do bolão para TLA da API."""
    c = str(code).strip().upper()
    return CODE_MAP.get(c, c)


FALLBACK_NAME_MAP = {
    "algeria": "ALG",
    "argentina": "ARG",
    "australia": "AUS",
    "austria": "AUT",
    "belgium": "BEL",
    "bosnia and herzegovina": "BIH",
    "brazil": "BRA",
    "canada": "CAN",
    "cape verde": "CPV",
    "colombia": "COL",
    "croatia": "CRO",
    "curaçao": "CUW",
    "cura&ccedil;ao": "CUW",
    "curaao": "CUW",
    "czech republic": "CZE",
    "democratic republic of the congo": "COD",
    "ecuador": "ECU",
    "egypt": "EGY",
    "england": "ENG",
    "france": "FRA",
    "germany": "GER",
    "ghana": "GHA",
    "haiti": "HAI",
    "iran": "IRN",
    "iraq": "IRQ",
    "ivory coast": "CIV",
    "japan": "JPN",
    "jordan": "JOR",
    "mexico": "MEX",
    "morocco": "MAR",
    "netherlands": "NED",
    "new zealand": "NZL",
    "norway": "NOR",
    "panama": "PAN",
    "paraguay": "PAR",
    "portugal": "POR",
    "qatar": "QAT",
    "saudi arabia": "KSA",
    "scotland": "SCO",
    "senegal": "SEN",
    "south africa": "RSA",
    "south korea": "KOR",
    "spain": "ESP",
    "sweden": "SWE",
    "switzerland": "SUI",
    "tunisia": "TUN",
    "turkey": "TUR",
    "united states": "USA",
    "uruguay": "URU",
    "uzbekistan": "UZB",
    # Fases eliminatórias — nomes adicionais que podem aparecer
    "australia": "AUS",
    "costa rica": "CRC",
    "democratic republic of congo": "COD",
    "republic of congo": "CGO",
    "cape verde islands": "CPV",
}


# ---------------------------------------------------------------------------
# Helpers de placar de tempo regulamentar (90 minutos)
# ---------------------------------------------------------------------------

def _parse_goal_minute(goal_str: str) -> int:
    """
    Extrai o minuto principal de uma string de gol.
    Exemplos:
      'Tielemans 125(P)\''  -> 125  (prorrogacao)
      'Lukaku 86\''          -> 86   (tempo normal)
      'Diop 90+1\''          -> 90   (acrescimos do 2o tempo = tempo normal)
      'Gabriel 90+5\''       -> 90   (acrescimos = tempo normal)
    """
    m = re.search(r'(\d+)(?:\+\d+)?\s*(?:\([^)]*\))?\s*\'', goal_str)
    return int(m.group(1)) if m else 0


def _count_rt_goals(scorers_str) -> int:
    """
    Conta gols marcados em tempo regulamentar (<= 90 min, incluindo acrescimos).
    scorers_str: string JSON-like do estilo '{"Nome 56\'","Nome 90+2\'"}'.
    """
    if not scorers_str or str(scorers_str).strip().lower() in ('null', '', 'none'):
        return 0
    goals = re.findall(r'"([^"]+)"', str(scorers_str))
    return sum(1 for g in goals if _parse_goal_minute(g) <= 90)


def fetch_and_store_results(dim_jogos):
    """
    Busca jogos na worldcup26.ir (primary) e persiste no SQLite.
    Se falhar, tenta a football-data.org (fallback).
    dim_jogos: DataFrame com colunas match_id, mandante_sigla, visitante_sigla.
    """
    # Build lookup: (home_tla, away_tla) → bolão match_id
    lookup = {}
    for _, row in dim_jogos.iterrows():
        h = _normalize(row["mandante_sigla"])
        a = _normalize(row["visitante_sigla"])
        lookup[(h, a)] = str(row["match_id"])

    logger.info("Buscando resultados da API primária (worldcup26.ir)...")
    try:
        resp = requests.get("https://worldcup26.ir/get/games", timeout=15)
        resp.raise_for_status()
        games_data = resp.json()
        games = games_data.get("games", [])
        
        matches_fmt = []
        for g in games:
            home_name = str(g.get("home_team_name_en", "")).strip().lower()
            away_name = str(g.get("away_team_name_en", "")).strip().lower()

            home_tla = FALLBACK_NAME_MAP.get(home_name, "")
            away_tla = FALLBACK_NAME_MAP.get(away_name, "")

            # Status
            finished     = str(g.get("finished", "")).strip().upper()
            time_elapsed = str(g.get("time_elapsed", "")).strip().lower()

            if finished == "TRUE":
                status = "FINISHED"
            elif time_elapsed == "live" or (time_elapsed.isdigit() and int(time_elapsed) > 0):
                status = "IN_PLAY"
            else:
                status = "SCHEDULED"

            # Placar final
            hs  = g.get("home_score")
            as_ = g.get("away_score")
            home_score = int(hs)  if hs  is not None and str(hs).isdigit()  else None
            away_score = int(as_) if as_ is not None and str(as_).isdigit() else None

            # Placar dos 90 minutos (tempo regulamentar)
            # Para jogos sem prorrogacao, e igual ao placar final.
            # Para jogos com prorrogacao, calculamos a partir dos scorers.
            home_hs = g.get("home_scorers")
            away_hs = g.get("away_scorers")

            if home_score is not None and away_score is not None:
                if status == "FINISHED":
                    # Jogo encerrado: calcular gols ate 90min pelo scorer
                    h90 = _count_rt_goals(home_hs)
                    a90 = _count_rt_goals(away_hs)
                    # Sanidade: sem dados de scorers -> assume sem prorrogacao
                    all_scorers = str(home_hs) + str(away_hs)
                    if h90 == 0 and a90 == 0 and '"' not in all_scorers:
                        h90, a90 = home_score, away_score
                else:
                    # Jogo em andamento (IN_PLAY/PAUSED): usar placar atual diretamente.
                    # Acrescimos do 2o tempo (92', 94'...) NAO sao prorrogacao!
                    # O ajuste de ET so faz sentido em jogos FINALIZADOS.
                    h90, a90 = home_score, away_score
            else:
                h90, a90 = None, None

            matches_fmt.append({
                "status":    status,
                "homeTeam":  {"tla": home_tla},
                "awayTeam":  {"tla": away_tla},
                "score": {
                    "fullTime":      {"home": home_score, "away": away_score},
                    "regularTime":   {"home": h90,        "away": a90},
                },
            })
        
        _process_matches(matches_fmt, lookup)
        logger.info("Resultados buscados com sucesso da worldcup26.ir.")
        return
        
    except Exception as exc:
        logger.warning("Falha ao buscar da worldcup26.ir: %s. Tentando fallback football-data.org...", exc)
        _try_football_data(lookup)


def _process_matches(matches: list, lookup: dict):
    stored = 0
    for m in matches:
        status = m.get("status", "")
        if status not in ("FINISHED", "IN_PLAY", "PAUSED"):
            continue

        home_tla = m.get("homeTeam", {}).get("tla", "").upper()
        away_tla = m.get("awayTeam", {}).get("tla", "").upper()

        match_id = lookup.get((home_tla, away_tla))
        if not match_id:
            logger.debug("Sem correspondencia: %s x %s", home_tla, away_tla)
            continue

        score = m.get("score", {})
        ft    = score.get("fullTime",    {})
        rt    = score.get("regularTime", {})

        sh = ft.get("home")
        sa = ft.get("away")
        # Placar 90 min: usa regularTime se disponivel, senao usa fullTime
        sh90 = rt.get("home") if rt.get("home") is not None else sh
        sa90 = rt.get("away") if rt.get("away") is not None else sa

        if sh is not None and sa is not None:
            save_result(match_id, int(sh), int(sa), status,
                        score_home_90=int(sh90) if sh90 is not None else None,
                        score_away_90=int(sa90) if sa90 is not None else None)
            stored += 1

    logger.info("Resultados armazenados/atualizados: %d", stored)


def _try_football_data(lookup: dict):
    """Fallback: busca resultados na football-data.org."""
    if not API_KEY:
        logger.warning("FOOTBALL_API_KEY não configurada — pulando fallback.")
        return

    headers = {"X-Auth-Token": API_KEY}
    try:
        resp = requests.get(
            f"{BASE_URL}/competitions/WC/matches",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
        logger.info("API Fallback: %d partidas recebidas da football-data.org", len(matches))
        _process_matches(matches, lookup)
    except Exception as exc:
        logger.error("Fallback football-data.org também falhou: %s", exc)
