from vespa.application import Vespa
from vespa.io import VespaResponse, VespaQueryResponse
from datasets import load_dataset
from datetime import datetime, timezone
import json

app = Vespa(url = "http://localhost:8080")

from dataclasses import dataclass
from typing import Callable, Optional, Iterable, Dict

subreddit_name = "ChoujinX"
# with app.syncio() as session:
#     response: VespaQueryResponse = session.query(
#         yql="select * from reddit_post where true | all(group(subreddit_name) each(output(count())))",
#         hits=0,
#         summary='minimal',
#     )
#     data = response.hits
#     print(data)
#     subreddit_names = [
#     child['value']
#     for group in data
#     for subgroup in group.get('children', [])
#     if subgroup['label'] == 'subreddit_name'
#     for child in subgroup.get('children', [])
#     ]

#     # Print the result
#     print(subreddit_names)

with app.syncio() as session:
    response: VespaQueryResponse = session.query(
        yql=f"select created_utc,subreddit_name from reddit_post where subreddit_name contains '{subreddit_name}' order by created_utc desc",
        hits=10,
        summary='minimal',
    )
    data = response.hits
    print(data)
    print(datetime.fromtimestamp(response.hits[0]['fields']['created_utc'], tz=timezone.utc))

with app.syncio() as session:
    response: VespaQueryResponse = session.query(
        yql=f"select created_utc,subreddit_name from reddit_post where subreddit_name contains '{subreddit_name}' order by created_utc asc",
        hits=1,
        summary='minimal',
    )
    data = response.hits
    print(data)
    print(datetime.fromtimestamp(response.hits[0]['fields']['created_utc'], tz=timezone.utc))

