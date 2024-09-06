
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from datetime import datetime, timedelta
import concurrent.futures
from downloaders.redditDownloader import download_subreddit_data
from embedders.redditEmbedder import RedditEmbedder
import logging.handlers
from dotenv import load_dotenv
from processors.redditProcessor import RedditDataProcessor
from models.models import  RedditPost
from managers.weaviateDBManager import WeaviateManager
from sqlalchemy import func
import pytz

# TODO: Set up full logging
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv(override=True)

def full_reddit_download(db_manager: WeaviateManager):
    subreddit = os.getenv('SUBREDDIT')
    update = os.getenv('UPDATE', 'true').lower() == 'true'
    if update:
        log.info("Update true")
        # Use existing logic
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=int(os.getenv('YEARS', 2)) * 365)
        latest_time = db_manager.get_latest_subreddit_time(subreddit)
        if latest_time is not None:
            start_date = max(latest_time + timedelta(seconds=1), start_date)                
        log.info(f"Start Date:{start_date.strftime('%Y-%m-%d %H:%M:%S')} End Date:{end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        log.info("Update false")
        # Modify start_date to be the minimum of the date of the earliest post and the year
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=int(os.getenv('YEARS', 2)) * 365)
        earliest_post_timestamp =db_manager.get_earliest_subreddit_time(subreddit)
        if earliest_post_timestamp is not None:
            start_date = min(earliest_post_timestamp, datetime.now() - timedelta(days=int(os.getenv('YEARS', 2)) * 365))
            end_date = earliest_post_timestamp - timedelta(seconds=1)  # Start downloading from the timestamp of the latest post
        log.info(f"Start Date:{start_date.strftime('%Y-%m-%d %H:%M:%S')} End Date:{end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("Start Downloading")
    subreddits = [subreddit]

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for subreddit in subreddits:
            future = executor.submit(download_subreddit_data, start_date, end_date, subreddit, 'subredditData', True)
            futures.append(future)
            future = executor.submit(download_subreddit_data, start_date, end_date, subreddit, 'subredditData', False)
            futures.append(future)

        # Wait for all tasks to complete
        concurrent.futures.wait(futures)

        for future in futures:
            if future.exception():
                print(f"Error encountered: {future.exception()}")

def main():
    wv_manager = WeaviateManager()
    try:
        log.info('Inserting Subreddit info into DB')
        log.info(f"Subreddit:{os.getenv('SUBREDDIT')}")
        log.info("Starting reddit download")
        full_reddit_download(wv_manager)
        log.info("Finishing Subreddit info download")
        processor = RedditDataProcessor()
        processor.process_data()
        log.info('Finished Filtering Data')
        embedder = RedditEmbedder(wv_manager=wv_manager)
        embedder.bulk_embed_posts()
    except Exception as e:
        log.error(f'ERROR downloading reddit data:{e}')
    wv_manager.close()

if __name__ == '__main__':
    main()