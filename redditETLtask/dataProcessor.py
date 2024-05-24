import pandas as pd
import os
from models.models import DatabaseManager
import logging.handlers

log = logging.getLogger("bot")

class RedditDataProcessor:
    def __init__(self, db_manager:DatabaseManager, directory_path='subredditData', output_file_path='reddit_data_filtered.parquet'):
        self.directory_path = directory_path
        self.output_file_path = output_file_path
        self.posts_df = pd.DataFrame()
        self.comments_df = pd.DataFrame()
        self.db_manager = db_manager

    def remove_repeated_occurrences(self, df, num=25):
        value_counts = df['body'].value_counts()
        repeated_values = value_counts[value_counts > num].index
        df_filtered = df[~df['body'].isin(repeated_values)]
        return df_filtered

    def combine_text(self, row, df_dict):
        if pd.notnull(row['title']):
            combined_text = 'Post: ' + row['title'] + ' ' + row['body']
        else:
            parent_id = row['parent_id'].split('_')[1]
            if parent_id in df_dict:
                parent_type = df_dict[parent_id]['is_post']
                if parent_type:
                    combined_text = 'Parent Post: ' + df_dict[parent_id]['body'] + ' Comment: ' + row['body']
                else:
                    combined_text = 'Parent Comment: ' + df_dict[parent_id]['body'] + ' Comment: ' + row['body']
            else:
                combined_text = 'Comment: ' + row['body']
        return combined_text

    def load_data(self):
        for filename in os.listdir(self.directory_path):
            file_path = os.path.join(self.directory_path, filename)
            if filename.endswith("-posts.parquet"):
                posts_data = pd.read_parquet(file_path)
                self.posts_df = pd.concat([self.posts_df, posts_data], ignore_index=True)
            elif filename.endswith("-comments.parquet"):
                comments_data = pd.read_parquet(file_path)
                self.comments_df = pd.concat([self.comments_df, comments_data], ignore_index=True)

    def filter_data(self):
        if not self.posts_df.empty:
            self.posts_df.drop(self.posts_df[self.posts_df['selftext'] == '[removed]'].index, inplace=True)
            self.posts_df.dropna(subset=['selftext'], inplace=True)
            self.posts_df.rename(columns={"selftext": "body"}, inplace=True)
            self.posts_df['is_post'] = True

        if not self.comments_df.empty:
            self.comments_df.dropna(subset=['body'], inplace=True)
            self.comments_df['is_post'] = False
        combined_df = pd.concat([self.comments_df, self.posts_df], ignore_index=True, sort=False)
        if not combined_df.empty:
            combined_df = self.remove_repeated_occurrences(combined_df, 25)
            df_dict = combined_df.set_index('id')[['body', 'is_post']].to_dict('index')
            combined_df['combined_text'] = combined_df.apply(self.combine_text, axis=1, args=(df_dict,))
            combined_df['title'].fillna('Comment', inplace=True)
            combined_df['num_comments'].fillna(-1, inplace=True)
            combined_df['archived'].fillna('False', inplace=True)
            combined_df['archived'] = combined_df['archived'].astype(bool)
            self.db_manager.insert_users(combined_df['author'].unique().tolist())
            combined_df.to_parquet(self.output_file_path, index=True, compression='gzip')

    def process_data(self):
        self.load_data()
        log.info(f"Total Posts: {self.posts_df.shape[0]}")
        if not self.posts_df.empty or not self.comments_df.empty:
            log.info(f"Posts Data:{self.posts_df.head()}")
            log.info(f"Comments Data:{self.comments_df.head()}")
            self.filter_data()
        else:
            raise Exception("No More data to download")