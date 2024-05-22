import pandas as pd
import os 
from models import insert_users

def remove_repeated_occurrences(df, num=25):
    value_counts = df['body'].value_counts()
    repeated_values = value_counts[value_counts > num].index
    df_filtered = df[~df['body'].isin(repeated_values)]
    return df_filtered

def combine_text(row,df_dict):
    if pd.notnull(row['title']):
        combined_text = 'Post: ' + row['title'] + ' ' + row['body']
    else:
        parent_id =  row['parent_id'].split('_')[1]
        if parent_id in df_dict:
          parent_type = df_dict[parent_id]['is_post']
          if parent_type:
            combined_text = 'Parent Post: ' +  df_dict[parent_id]['body'] + 'Comment: ' + row['body']
          else:
            combined_text = 'Parent Comment: ' +  df_dict[parent_id]['body'] + 'Comment: ' + row['body']
        else:
          combined_text =  'Comment: ' + row['body']
    return combined_text

def filter_data():
    directory_path = 'subredditData'
    # Initialize empty DataFrames
    posts_df = pd.DataFrame()
    comments_df = pd.DataFrame()

    # Iterate through files in the directory
    for filename in os.listdir(directory_path):
        if filename.endswith("-posts.parquet"):
            # Reading posts data
            posts_data = pd.read_parquet(os.path.join(directory_path, filename))
            # Concatenate with the existing posts_df
            posts_df = pd.concat([posts_df, posts_data], ignore_index=True)
        elif filename.endswith("-comments.parquet"):
            # Reading comments data
            comments_data = pd.read_parquet(os.path.join(directory_path, filename))
            # Concatenate with the existing comments_df
            comments_df = pd.concat([comments_df, comments_data], ignore_index=True)
    if not posts_df.empty or not comments_df.empty:
        # Check is posts is empty before filtering
        if not posts_df.empty:
            posts_df.drop(posts_df[posts_df['selftext'] == '[removed]'].index, inplace=True)
            posts_df.dropna(subset=['selftext'], inplace=True)
            posts_df.rename(columns={"selftext": "body"}, inplace=True)
            posts_df['is_post'] = True

        # Check if comments is empty before filtering
        if not comments_df.empty:
            comments_df.dropna(subset=['body'], inplace=True)
            comments_df['is_post'] = False

        combined_df = pd.concat([comments_df, posts_df], ignore_index=True, sort=False)

        combined_df = remove_repeated_occurrences(combined_df,25)
        df_dict = combined_df.set_index('id')[['body', 'is_post']].to_dict('index')
        combined_df['combined_text'] = combined_df.apply(combine_text, axis=1,args=(df_dict,))
        combined_df['title'].fillna('Comment',inplace=True)
        combined_df['num_comments'].fillna(-1,inplace=True)
        combined_df['archived'].fillna('False',inplace=True)
        combined_df['archived'] = combined_df['archived'].astype(bool)
        insert_users(combined_df['author'].unique().tolist())
        output_file_path = 'reddit_data_filtered.parquet'
        combined_df.to_parquet(output_file_path, index=True, compression='gzip')
    else:
        raise Exception("No More data to download")

