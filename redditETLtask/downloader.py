from datetime import datetime, timedelta
import os
import concurrent.futures
from dataDownloader import download_subreddit_data
import logging.handlers
from dotenv import load_dotenv
from dataProcessor import RedditDataProcessor
from models.models import Subreddit, RedditPost, DatabaseManager
from sqlalchemy import func

# TODO: Set up full logging
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv()

def full_reddit_download(db_manager: DatabaseManager):
    subreddit = os.getenv('SUBREDDIT')
    update = os.getenv('UPDATE', 'true').lower() == 'true'
    if update:
        log.info("Update true")
        # Use existing logic
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(os.getenv('YEARS', 2)) * 365)
        existing_subreddit = db_manager.db.query(Subreddit).filter(Subreddit.subreddit_name == subreddit).first()
        if existing_subreddit:
            latest_post_timestamp = db_manager.db.query(func.max(RedditPost.created_utc)).filter(RedditPost.subreddit_name == existing_subreddit.subreddit_name).scalar()
            if latest_post_timestamp is not None:
                start_date = max(latest_post_timestamp + timedelta(seconds=1), start_date)
        log.info(f"Start Date:{start_date.strftime('%Y-%m-%d %H:%M:%S')} End Date:{end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        log.info("Update false")
        # Modify start_date to be the minimum of the date of the earliest post and the year
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(os.getenv('YEARS', 2)) * 365)
        earliest_post_timestamp = db_manager.db.query(func.min(RedditPost.created_utc)).filter(RedditPost.subreddit_name == subreddit).scalar()
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
    try:
        db_manager = DatabaseManager()
        if(os.getenv('RECREATE', 'false').lower() == 'true'):
            log.info("Initializing DB")
            db_manager.initialize_database()
        log.info('Inserting Subreddit info into DB')
        db_manager.insert_subreddit_info(os.getenv('SUBREDDIT'))
        log.info("Starting reddit download")
        full_reddit_download(db_manager)
        log.info("Finishing Subreddit info download")
        processor = RedditDataProcessor(db_manager)
        processor.process_data()
        log.info('Finished Filtering Data')
        db_manager.db.close()
    except Exception as e:
        log.error(f'ERROR downloading reddit data:{e}')
        db_manager.db.rollback()
        db_manager.db.close()
        raise Exception(e)

if __name__ == '__main__':
    main()