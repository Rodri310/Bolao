import logging, sys
logging.disable(logging.CRITICAL)
sys.stdout.reconfigure(encoding='utf-8')

from data_manager import get_full_df
import sqlite3

result = get_full_df()
df, dim_jogos, dim_membros = result

# O match_id do COD x UZB nos palpites
mid_palpites = 'd2dd01d2-26ad-4008-a20a-3a591c7500b0'
print(f"match_id nos palpites: {mid_palpites}")

# Verificar o que tem no banco para esse UUID
conn = sqlite3.connect('results.db')
row = conn.execute(
    "SELECT * FROM match_results WHERE match_id = ?", (mid_palpites,)
).fetchone()
print(f"No DB para esse UUID: {row}")
print()

# O que a API retorna para COD x UZB - ver via API diretamente
import requests, re
resp = requests.get('https://worldcup26.ir/get/games', timeout=15)
games = resp.json().get('games', [])
print("=== API: jogos com COD ou UZB ===")
for g in games:
    home = str(g.get('home_team_name_en', '')).lower()
    away = str(g.get('away_team_name_en', '')).lower()
    if 'congo' in home or 'uzb' in home.replace(' ','') or 'congo' in away or 'uzbek' in away or 'congo' in home or 'democratic' in home:
        print(f"  id={g['id']}  {g.get('home_team_name_en','?')} x {g.get('away_team_name_en','?')}")
        print(f"    score: {g.get('home_score','?')}-{g.get('away_score','?')}")
        print(f"    finished={g.get('finished','?')}  type={g.get('type','?')}  group={g.get('group','?')}")
        print(f"    home_scorers={str(g.get('home_scorers',''))[:80]}")

conn.close()
