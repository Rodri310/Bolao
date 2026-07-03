import requests, json, re

resp = requests.get('https://worldcup26.ir/get/games', timeout=15)
games = resp.json().get('games', [])

r32 = [g for g in games if g.get('type') == 'r32' and g.get('finished') == 'TRUE']

print("Jogos R32 finalizados com prorrogacao ou penaltis:")
for g in r32:
    match_id = g['id']
    home = g.get('home_score', '?')
    away = g.get('away_score', '?')
    hs = str(g.get('home_scorers', ''))
    as_ = str(g.get('away_scorers', ''))

    all_goals = re.findall(r'"([^"]+)"', hs + as_)
    et_goals = []
    for goal in all_goals:
        m = re.search(r'(\d+)(?:\+\d+)?[^\']*\'', goal)
        if m and int(m.group(1)) > 90:
            et_goals.append(goal.strip())

    has_pen = bool(g.get('home_penalty_score'))
    home_name = str(g.get('home_team_name_en', '?'))[:3]
    away_name = str(g.get('away_team_name_en', '?'))[:3]

    if et_goals or has_pen:
        print(f"  #{match_id} {home_name}x{away_name}: {home}-{away} | ET_goals:{et_goals} | PEN:{has_pen}")

print()
print("Todos jogos R32 finalizados:")
for g in r32:
    match_id = g['id']
    home = g.get('home_score', '?')
    away = g.get('away_score', '?')
    home_name = str(g.get('home_team_name_en', '?'))[:10]
    away_name = str(g.get('away_team_name_en', '?'))[:10]
    has_pen = bool(g.get('home_penalty_score'))
    hs = str(g.get('home_scorers', ''))
    as_ = str(g.get('away_scorers', ''))
    print(f"  #{match_id} {home_name}x{away_name}: {home}-{away} pen={has_pen}")
    print(f"         home_scorers: {hs[:120]}")
    print(f"         away_scorers: {as_[:120]}")
