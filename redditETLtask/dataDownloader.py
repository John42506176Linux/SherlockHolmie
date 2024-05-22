import requests
import progressbar
import time
import pyarrow as pa
import pyarrow.parquet as pq
import os
import glob
import threading
import sys
import os
import threading
import time
import logging.handlers
import random

# List of User-Agent strings
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 Edge/16.16299',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
]

pause_event = threading.Event()
log = logging.getLogger("bot")

class DataDownloader:
    def __init__(self,start_date, end_date, subreddit,output_folder,is_post,pause_event):
        self.url = f"https://arctic-shift.photon-reddit.com/api/{'posts' if is_post else 'comments'}/search?sort=asc&subreddit={subreddit}"
        self.start_date = start_date.timestamp()
        self.end_date = end_date.timestamp()
        self.current_date = self.start_date
        self.subreddit = subreddit
        self.is_done = False
        self.is_running = True
        self.is_post=is_post
        self.widgets = [' [',
                        progressbar.Timer(format='elapsed time: %(elapsed)s'),
                        '] ',
                        progressbar.Bar('*'), ' (',
                        progressbar.ETA(), ') ',
                        f'Subreddit: {self.subreddit} '  # Displaying subreddit name
                       ]
        file_pattern = f"{subreddit}-{'posts' if is_post else 'comments'}.parquet"
        self.parquet_file = os.path.join(output_folder, file_pattern)

        # Search for existing files that match the pattern
        existing_files = sorted(glob.glob(self.parquet_file))
        if existing_files:
            # If there are existing files, use the most recent one
            self.parquet_file = existing_files[-1]
            if not self.verify_parquet_file(self.parquet_file):
                # If the file is corrupted or incomplete, handle accordingly
                print(f"File {self.parquet_file} is corrupted or not a Parquet file. Starting anew.")
                self.parquet_file = self.create_new_filename(output_folder, subreddit, is_post, end_date)
            else:
                # Open the most recent file to find the last timestamp
                print("Restarting file")
                parquet_file = pq.ParquetFile(self.parquet_file)
                last_batch = parquet_file.read_row_group(parquet_file.num_row_groups - 1)
                last_timestamp = last_batch.column('created_utc').to_pandas().iloc[-1]
                self.current_date = last_timestamp + 1  # Resume from the next second
        else:
            # If no existing files, create a new filename including the end date
            self.parquet_file = os.path.join(output_folder, f"{subreddit}-{'posts' if is_post else 'comments'}.parquet")

        # Create the output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        self.parquet_writer = None
        self.pause_event = pause_event

    def verify_parquet_file(self, file_path):
        try:
            # Attempt to read the first few rows to check file integrity
            pf = pq.ParquetFile(file_path)
            first_ten_rows = next(pf.iter_batches(batch_size = 10))
            df = pa.Table.from_batches([first_ten_rows]).to_pandas()
            df.head(10)
            return True  # File is okay
        except Exception as e:
            print(f"Verification failed for {file_path}: {str(e)}")
            return False  # File is corrupted or not a valid Parquet file

    def create_new_filename(self, output_folder, subreddit, is_post, end_date):
        # Generate a new filename based on current criteria
        return os.path.join(output_folder, f"{subreddit}-{'posts' if is_post else 'comments'}.parquet")


    def download_data(self):
        max_timestamp = self.end_date - self.current_date
        bar = progressbar.ProgressBar(max_value=max_timestamp,
                                       widgets=self.widgets).start()
        retry_count = 0
        while not self.is_done and self.is_running:
            try:
                response = requests.get(
                    f"{self.url}&limit=100&after={int(self.current_date)}&before={int(self.end_date)}&meta-app=download-tool"
                )
                response.raise_for_status()  # Raise HTTPError for non-200 status codes

                data = response.json()

                if 'error' in data or 'data' not in data:
                    raise Exception(data.get('error', 'No data returned'))

                if len(data['data']) == 0:
                    self.is_done = True
                    self.is_running = False
                    break

                new_timestamp = data['data'][-1]['created_utc']
                if new_timestamp == int(self.current_date):
                    new_timestamp += 1
                self.current_date = new_timestamp
                time_diff = self.end_date - new_timestamp
                bar.update(max_timestamp - time_diff)
                self.write_to_file(data['data'])

                retry_count = 0  # Reset retry count upon successful request
            except Exception as e:
                print(f"HTTP Error: {e}")
                retry_count += 1
                if retry_count > 10:  # Max retry attempts
                    print("Max retry attempts reached. Exiting.")
                    break
                # Exponential backoff
                wait_time = min(2 ** retry_count,360)  # Limit wait time to 60 seconds
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

    def write_to_file(self, data):
        if self.pause_event.is_set():
            # Handle pause logic here, e.g., break the loop, save state, etc.
            print("Download paused.")
            sys.exit(0)
            return
        fields = []
        # print(data)
        if self.is_post:
            fields = ["author", "archived", "title", "score", "selftext", "permalink", "subreddit", "created_utc", "gilded", "id", "num_comments"]
        else:
            fields = ["author","score","created_utc","permalink","body","subreddit","id","parent_id","link_id"]
        filtered_data = [{field: item[field] for field in fields} for item in data]
        # Create a PyArrow table from the filtered data
        table = pa.Table.from_pylist(filtered_data)

        if self.parquet_writer is None:
            self.parquet_writer = pq.ParquetWriter(self.parquet_file, table.schema, use_dictionary=True, compression='snappy', flavor='spark')

        self.parquet_writer.write_table(table)

def get_user_interactions(author):
    retry_count = 0
    while retry_count <= 5:
        try:
            subreddit_interaction_url = f"https://arctic-shift.photon-reddit.com/api/user_interactions/subreddits?author={author}"
            response = requests.get(subreddit_interaction_url)
            
            if response.status_code == 400:
                error_data = response.json()
                if 'error' in error_data  and 'not supported' in error_data['error']:
                    log.error(f"Author: {author} not supported for interaction data")
                    return None
                else:
                    log.error(f'400 error for Author {author}: error:{error_data}')
                    return None
            if response.status_code == 429:
                log.info("Rate limit exceeded. Waiting before retrying.")
                retry_count += 1
                if retry_count > 5:  # Max retry attempts
                    log.error("Max retry attempts reached. Exiting.")
                    return None
                # Exponential backoff
                wait_time = min(2 ** retry_count, 360)  # Limit wait time to 360 seconds (6 minutes)
                log.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue  # Retry the request
            response.raise_for_status()  # Raise HTTPError for non-200 status codes
            data = response.json()
            if 'error' in data or 'data' not in data:
                raise Exception(data.get('error', 'No data returned'))
            return data['data']
        except Exception as e:
            log.error(f"Interaction Data for user {author} Error: {e}")
    return None

def get_user_description(author):
    retries = 0
    max_retries = 5
    while retries <= max_retries:
        response = None
        try:
            url = f"https://www.reddit.com/u/{author}/about.json"
            user_agent = random.choice(user_agents)
            # Set the headers
            headers = {'User-Agent': user_agent}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data['data']['subreddit']['public_description']
            elif response.status_code == 404:
                log.error(f"Author {author} not found (404).")
                return None
            elif response.status_code == 429:
                log.error(f"Rate Limit on fetching user description for {author}")
                retries += 1
                if retries > max_retries:
                    log.error("Max retry attempts reached. Exiting.")
                    return None
                # Exponential backoff
                wait_time = min(2 ** retries, 360)  # Limit wait time to 360 seconds (6 minutes)
                log.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        except Exception as e:
            log.error(f"Request Error fetching user description: {e}")
            return None
    return None

def download_subreddit_data(start_date, end_date, subreddit, output_folder, is_post, pause_event):
    # Check if the subreddit exists in the database
    downloader = DataDownloader(start_date, end_date, subreddit, output_folder, is_post, pause_event)
    downloader.download_data()

def signal_handler(signal_received, frame):
    print("SIGINT received, signaling threads to pause...")
    pause_event.set()