import requests
import json
import re
import time
import os
import openai # https://cookbook.openai.com/examples/how_to_format_inputs_to_chatgpt_models
from dotenv import load_dotenv


def remove_key_from_dict(_dict, key):
    try:
        _dict.pop(key)
        print(f'Removed key `{key}` from dictionary')
    except:
        print(f'Error: key `{key}` not in dictionary')

ignored_projects = [
    'shell-00',
    'shell-01',
    'c-00',
    'c-01',
    'c-02',
    'c-03',
    'c-04',
    'c-05',
    'c-06',
    'c-07',
    'c-08',
    'c-09',
    'c-10',
    'c-11',
    'c-12',
    'c-13',
    'rush-00',
    'rush-01',
    'rush-02'
]

load_dotenv()

# Step 1: get 42 API access token
url_access_token='https://api.intra.42.fr/oauth/token'
data = {
    "grant_type": 'client_credentials',
    "client_id": os.environ.get('FT_API_UID'),
    "client_secret": os.environ.get('FT_API_SECRET')
}
response = requests.post(url=url_access_token, data=data)

# 200 only
if response.status_code != 200:
    print(f'{response.url} Error {response.status_code} {response.reason}')
    exit()

access_token = response.json().get('access_token')
if access_token is None:
    print(f'Error: no access token received from {url_access_token}')
    exit()

# Step 2: get 42 user's id
ft_user = os.environ.get('FT_USER')
url_user=f'https://api.intra.42.fr/v2/users/{ft_user}'
headers = { "Authorization": f"Bearer {access_token}" }
response = requests.get(url=url_user, headers=headers)

# 200 only
if response.status_code != 200:
    print(f'{response.url} Error {response.status_code} {response.reason}')
    exit()

user_id = response.json().get('id')
if user_id is None:
    print(f'Error: no user id received from {url_user}')
    exit()

# Step 3: get all its evaluation comments
page = 1
# TODO url_team=''
comments = {} # to the form { str: [str] }, with project name as key and comments as values
while True: # emulate a do-while
    params = { 'page[number]': page }
    print(f'== querying page {page} ==')
    response = requests.get(url=f'https://api.intra.42.fr/v2/users/{user_id}/scale_teams/as_corrected', headers=headers, params=params)
    # 200 only
    if response.status_code != 200:
        print(f'{response.url} Error {response.status_code} {response.reason}')
        exit()
    # need `Links` field in header
    links = response.headers.get('Link')
    if links is None:
        print(f'Error: no links received from https://api.intra.42.fr/v2/users/{user_id}/scale_teams/as_corrected?page={page}')
        exit()
    # display the comments
    json_response = json.loads(response.text)
    if isinstance(json_response, list):
        for obj in json_response:
            comment = obj.get('comment')
            project = obj.get('team').get('project_gitlab_path').split('/')[-1]
            if project and comment:
                if project not in comments:
                    comments[project] = []
                comments[project].append(comment)
    else:
        print(f'Error: response from {response.url} is not a list')
        exit()
    # looking for the next comments page
    pattern = r'<https://api.intra.42.fr/v2/users/' + str(user_id) + r'/scale_teams/as_corrected\?page=(\d+)>; rel="(\w+)"'
    next_page = page
    for match in re.finditer(pattern, links):
        if match.group(2) == 'next':
            next_page = int(match.group(1)) # we got a next page to query
            break
    if next_page == page: # all pages have been queried
        break
    page = next_page
    time.sleep(1) # avoid 429 too many requests (2 by secs)

# otherwise message too big for chatGPT API
for project in ignored_projects:
    remove_key_from_dict(comments, project)

json_comments = json.dumps(comments, indent=2)
print(json_comments)

# exit()

# Step 4: send them to chatGPT
openai.api_key = os.environ.get("OPENAI_API_KEY")

prompt = """
Tu vas recevoir un dictionnaire python.
Chaque clé correspond à un travail, le plus souvent un programme informatique.
Chaque valeur est une liste d' analyses/commentaires/réactions au projet identifié par sa clé.
Chaque element de cette liste est rédigé par une personne distincte, avec un niveau d'expertise en informatique propre.

Certains de ces avis sont rédigés en anglais. Traduis les et tiens en compte comme tout autre.

Tu vas produire un résumé de ces avis récoltés.
Ce résumé présentera les traits et caractéristiques communes des travaux considérés: ses qualités, ses faiblesses et ses axes d'amélioration.

Un biais est toutefois présent dans ces commentaires.
La plupart du temps, ils évaluent un travail mené à terme.
Des expressions telles que 'bon travail', 'bravo' ou 'bon courage' sont souvent présentes.
Ne les prend pas en considération outre mesure, ils pourraient t'amener à surévaluer la qualité du travail considéré.

Dresse en même tempsle portrait (qualités, défauts et axes d'amérioration) de celui a réalisé ces travaux.
"""

response = openai.ChatCompletion.create(
    messages=[
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': json_comments},
    ],
    model='gpt-3.5-turbo',
    temperature=0,
)

print(response['choices'][0]['message']['content'])