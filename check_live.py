import requests, json, sys

# Forcar UTF-8 no output
sys.stdout.reconfigure(encoding='utf-8')

resp = requests.get('https://worldcup26.ir/get/games', timeout=15)
games = resp.json().get('games', [])

# Jogo POR x CRO (mata-mata, id=83)
print("=== Jogo #83 POR x CRO (mata-mata) ===")
for g in games:
    if str(g.get('id')) == '83':
        for k, v in g.items():
            print(f"  {k}: {v}")
        break

print()

# Todos campos possiveis da API (primeiro jogo como referencia)
print("=== Campos disponiveis na API (exemplo jogo #73) ===")
for g in games:
    if str(g.get('id')) == '73':
        for k, v in g.items():
            print(f"  {k}: {repr(v)}")
        break

print()

# Qualquer jogo com time_elapsed nao-zero
print("=== Jogos com time_elapsed informado ===")
seen = set()
for g in games:
    te = str(g.get('time_elapsed', '')).strip()
    if te not in seen and te not in ('', '0', 'Finished', 'null'):
        seen.add(te)
        home = str(g.get('home_team_name_en', '?'))[:10]
        away = str(g.get('away_team_name_en', '?'))[:10]
        finished = g.get('finished', '?')
        hs = g.get('home_score', '?')
        as_ = g.get('away_score', '?')
        print(f"  {home} x {away}  |  time_elapsed={te!r}  |  score={hs}-{as_}  |  finished={finished}")
