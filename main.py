import requests

url = "https://api.football-data.org/v4/competitions/WC/matches"

headers = {
    "X-Auth-Token": "2a750a0f112949a58de3bc0ad3102118"
}


response = requests.get(url, headers=headers)

data = response.json()
for match in data['matches']:
    home = match['homeTeam']['name']
    away = match['awayTeam']['name']
    date = match['utcDate'][:10]
    status = match['status']
    print(f"{date}| {home} vs {away} | {status}")