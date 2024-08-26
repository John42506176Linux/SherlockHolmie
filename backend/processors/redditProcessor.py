import pandas as pd
import os
import logging.handlers

log = logging.getLogger("bot")

class RedditDataProcessor:
    def __init__(self,directory_path='subredditData', output_file_path='reddit_data_filtered.parquet'):
        self.directory_path = directory_path
        self.output_file_path = output_file_path
        self.posts_df = pd.DataFrame()
        self.comments_df = pd.DataFrame()

    def remove_repeated_occurrences(self, df, num=25):
        value_counts = df['body'].value_counts()
        repeated_values = value_counts[value_counts > num].index
        df_filtered = df[~df['body'].isin(repeated_values)]
        return df_filtered
    
    def get_title(self, row, df_dict):
        title = ''
        parent_id = row['link_id'].split('_')[1]
        if parent_id in df_dict:
            title = df_dict[parent_id]['title']
        return title
    
    def get_parent_post(self, row,df_dict):
        
        parent_post = ''
        parent_id = row['link_id'].split('_')[1]
        if parent_id in df_dict:
            parent_post = df_dict[parent_id]['body']
        return parent_post
    
          

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
        parent_dict = {}
        if not self.posts_df.empty:
            self.posts_df.drop(self.posts_df[self.posts_df['selftext'] == '[removed]'].index, inplace=True)
            self.posts_df.dropna(subset=['selftext'], inplace=True)
            self.posts_df.rename(columns={"selftext": "body"}, inplace=True)
            self.posts_df['is_post'] = True
            self.posts_df['parent_post'] = ''
            parent_dict = self.posts_df.set_index('id')[['body', 'title']].to_dict('index')
        if not self.comments_df.empty:
            self.comments_df.dropna(subset=['body'], inplace=True)
            self.comments_df['is_post'] = False
            self.comments_df['title'] = self.comments_df.apply(self.get_title,axis=1,args=(parent_dict,))
            self.comments_df['parent_post'] = self.comments_df.apply(self.get_parent_post,axis=1,args=(parent_dict,))
        combined_df = pd.concat([self.comments_df, self.posts_df], ignore_index=True, sort=False)
        if not combined_df.empty:
            combined_df = self.remove_repeated_occurrences(combined_df, 25)
            combined_df['num_comments'].fillna(-1, inplace=True)
            combined_df['archived'].fillna('False', inplace=True)
            combined_df['archived'] = combined_df['archived'].astype(bool)
            combined_df.to_parquet(self.output_file_path, index=True, compression='gzip')

    def process_data(self):
        self.load_data()
        if not self.posts_df.empty or not self.comments_df.empty:
            self.filter_data()
        else:
            raise Exception("No More data to download")