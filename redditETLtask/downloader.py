from datetime import datetime, timedelta
import os
import concurrent.futures
from dataDownloader import download_subreddit_data, pause_event
import logging.handlers
from dotenv import load_dotenv
from filtering import filter_data
from models import Subreddit, RedditPost, initialize_database, db, insert_subreddit_info
from sqlalchemy import func

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv()

def full_reddit_download():
    subreddit = os.getenv('SUBREDDIT')
    update = os.getenv('UPDATE', 'true').lower() == 'true'
    if update:
        log.info("Update true")
        # Use existing logic
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(os.getenv('YEARS', 2)) * 365)
        existing_subreddit = db.query(Subreddit).filter(Subreddit.subreddit_name == subreddit).first()
        if existing_subreddit:
            latest_post_timestamp = db.query(func.max(RedditPost.created_utc)).filter(RedditPost.subreddit_name == existing_subreddit.subreddit_name).scalar()
            if latest_post_timestamp is not None:
                start_date = max(latest_post_timestamp + timedelta(seconds=1), start_date)
        log.info(f"Start Date:{start_date.strftime("%Y-%m-%d %H:%M:%S")} End Date:{end_date.strftime("%Y-%m-%d %H:%M:%S")}")
    else:
        log.info("Update false")
        # Modify start_date to be the minimum of the date of the earliest post and the year
        earliest_post_timestamp = db.query(func.min(RedditPost.created_utc)).filter(RedditPost.subreddit_name == subreddit).scalar()
        if earliest_post_timestamp is not None:
            start_date = max(earliest_post_timestamp, datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0))
        end_date = earliest_post_timestamp - timedelta(seconds=1)  # Start downloading from the timestamp of the latest post
        log.info(f"Start Date:{start_date.strftime("%Y-%m-%d %H:%M:%S")} End Date:{end_date.strftime("%Y-%m-%d %H:%M:%S")}")
    log.info("Start Downloading")
    subreddits = [subreddit]

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for subreddit in subreddits:
            future = executor.submit(download_subreddit_data, start_date, end_date, subreddit, 'subredditData', True, pause_event)
            futures.append(future)
            future = executor.submit(download_subreddit_data, start_date, end_date, subreddit, 'subredditData', False, pause_event)
            futures.append(future)

        # Wait for all tasks to complete
        concurrent.futures.wait(futures)

        for future in futures:
            if future.exception():
                print(f"Error encountered: {future.exception()}")

def main():
    try:
        if(os.getenv('RECREATE', 'false').lower() == 'true'):
            log.info("Initializing DB")
            initialize_database()
        log.info('Inserting Subreddit info into DB')
        insert_subreddit_info()
        log.info("Starting reddit download")
        full_reddit_download()
        log.info("Finishing Subreddit info download")
        filter_data()
        log.info('Finished Filtering Data')
        db.close()
    except Exception as e:
        log.error(f'ERROR downloading reddit data:{e}')
        db.rollback()
        db.close()
        raise Exception(e)

if __name__ == '__main__':
    main()