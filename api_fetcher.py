"""
api_fetcher.py — Busca resultados reais na football-data.org e salva no SQLite.
Chamado pelo APScheduler a cada 5 minutos.

Fallback: worldcup26.ir (open-source, gratuito, Copa 2026).
"""
import os
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
}


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
            
            # Map status
            finished = str(g.get("finished", "")).strip().upper()
            time_elapsed = str(g.get("time_elapsed", "")).strip().lower()
            
            if finished == "TRUE":
                status = "FINISHED"
            elif time_elapsed == "live" or (time_elapsed.isdigit() and int(time_elapsed) > 0):
                status = "IN_PLAY"
            else:
                status = "SCHEDULED"
                
            # Parse scores
            hs = g.get("home_score")
            as_ = g.get("away_score")
            
            home_score = int(hs) if hs is not None and str(hs).isdigit() else None
            away_score = int(as_) if as_ is not None and str(as_).isdigit() else None
            
            matches_fmt.append({
                "status": status,
                "homeTeam": {"tla": home_tla},
                "awayTeam": {"tla": away_tla},
                "score": {
                    "fullTime": {
                        "home": home_score,
                        "away": away_score,
                    }
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
            logger.debug("Sem correspondência: %s x %s", home_tla, away_tla)
            continue

        score  = m.get("score", {})
        ft     = score.get("fullTime", {})
        sh     = ft.get("home")
        sa     = ft.get("away")

        if sh is not None and sa is not None:
            save_result(match_id, int(sh), int(sa), status)
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
