from vespa.application import Vespa
from vespa.io import VespaResponse, VespaQueryResponse
from datasets import load_dataset
from datetime import datetime, timezone
import json
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
                "yql": "select * from reddit_post where (userQuery()) or ({targetHits:5000}nearestNeighbor(body_embedding,q)) or ({targetHits:5000}nearestNeighbor(mrl_bq_embedding,q_binary)) or ({targetHits:5000}nearestNeighbor(title_embedding,q)) or ({targetHits:5000}nearestNeighbor(keyword_embeddings,q))",
                "query": query,
                "ranking": "weighted_closeness_combination",
                "timeout": "1000s",
                "input.query(q)": "embed(mxbai,@query)",
                "input.query(q_binary)": "embed(mxbai,@query)",
                "input.query(q_rerank)": "embed(tokenizer,@query)"
            },
        )
        return response.hits

if __name__ == "__main__":
    # Example usage
    print("All subreddits:", get_all_subreddit_names())
    
    test_subreddit = "LocalLLM"
    print(f"\nLatest posts from {test_subreddit}:", 
          get_latest_posts(test_subreddit))
    
    semantic_query_result = semantic_query("What is the best mac for Local LLms", limit=100)
    print(f"\nSemantic query result:", semantic_query_result)