from vespa.application import Vespa
from vespa.io import VespaResponse, VespaQueryResponse
from datasets import load_dataset
from datetime import datetime, timezone
import json
import time
from typing import List, Dict, Any

app = Vespa(url="http://35.91.108.46:8080")

def get_all_subreddit_names() -> List[str]:
    """Get list of all subreddit names in the database."""
    with app.syncio() as session:
        response: VespaQueryResponse = session.query(
            yql="select * from reddit_post where true | all(group(subreddit_name) each(output(count())))",
            hits=0,
            summary='minimal',
        )
        subreddit_names = [
            child['value']
            for group in response.hits
            for subgroup in group.get('children', [])
            if subgroup['label'] == 'subreddit_name'
            for child in subgroup.get('children', [])
        ]
        return subreddit_names

def get_latest_posts(subreddit_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get the latest posts from a specific subreddit."""
    with app.syncio() as session:
        response: VespaQueryResponse = session.query(
            yql=f"select created_utc,subreddit_name from reddit_post where subreddit_name contains '{subreddit_name}' order by created_utc desc",
            hits=limit,
            summary='minimal',
        )
        latest_timestamp = datetime.fromtimestamp(
            response.hits[0]['fields']['created_utc'], 
            tz=timezone.utc
        )
        return {
            'posts': response.hits,
            'latest_timestamp': latest_timestamp
        }

def get_earliest_post(subreddit_name: str) -> Dict[str, Any]:
    """Get the earliest post from a specific subreddit."""
    with app.syncio() as session:
        response: VespaQueryResponse = session.query(
            yql=f"select created_utc,subreddit_name from reddit_post where subreddit_name contains '{subreddit_name}' order by created_utc asc",
            hits=1,
            summary='minimal',
        )
        earliest_timestamp = datetime.fromtimestamp(
            response.hits[0]['fields']['created_utc'], 
            tz=timezone.utc
        )
        return {
            'post': response.hits[0],
            'earliest_timestamp': earliest_timestamp
        }

def semantic_query(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Perform a semantic search query."""
    with app.syncio(connections=1, compress="auto") as session:
        response: VespaQueryResponse = session.query(
            hits=limit,
            body={
                "yql": "select * from reddit_post where (userQuery()) or ({targetHits:5000}nearestNeighbor(mrl_bq_embedding,q_binary)) or ({targetHits:5000}nearestNeighbor(title_embedding,q))",
                "query": query,
                "queryProfile": 'largeQueryProfile',
                "ranking": "weighted_closeness_combination",
                "timeout": "1000s",
                "input.query(q)": "embed(mxbai,@query)",
                "input.query(qt)" : "embed(colbert,@query)",
                "input.query(q_binary)": "embed(mxbai,@query)",
            },
        )
        reddit_documents = []
        for hit in response.hits:
            fields = hit['fields']
            filtered_fields = {k: v for k, v in fields.items() if k not in ['documentid', 'sddocname', 'matchfeatures']}
            filtered_fields['relevance'] = hit['relevance']
            reddit_documents.append(filtered_fields)
        return reddit_documents

if __name__ == "__main__":
    # Example usage
    print("All subreddits:", get_all_subreddit_names())
    
    test_subreddit = "serverless"
    print(f"\nLatest posts from {test_subreddit}:", 
          get_latest_posts(test_subreddit))
    start_time =  time.time()
    semantic_query_result = semantic_query("What are the problems with serverless", limit=100)
    end_time = time.time()
    print(f"\nSemantic query result:")
    for i, doc in enumerate(semantic_query_result, start=1):
        print(f"Post {i}:")
        for field, value in doc.items():
            print(f"  {field}: {value}")
    print("Elapsed Time: ", end_time-start_time)
