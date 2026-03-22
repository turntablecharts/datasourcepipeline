import pandas as pd
import os
from typing import List

def split_cat(col, df, sep):
    x = df.join(df.pop(col)
                   .str.strip(sep)
                   .str.split(sep, expand=True)
                   .stack()
                   .reset_index(level=1, drop=True)
                   .rename(col)).reset_index(drop=True)
    x = x[['Points', col]]
    return x

def extract_category_data(df, category, file_name, output_dir) -> str:
    df_copy = df.copy()
    if category in df_copy.columns:
        df_copy[category] = df_copy[category].astype(str).str.replace('&', ',')

        df_new = split_cat(category, df_copy, ',')
        df_new[category] = df_new[category].str.strip().str.lower()

        #confirm that Points is a numeric value
        df_new['Points'] = pd.to_numeric(df_new['Points'], errors='coerce')

        x = df_new.groupby(category)['Points'].sum()
        x = x.sort_values(ascending=False)
        x = x.reset_index()

        x[category] = x[category].str.title()

        output_path = os.path.join(output_dir, f"{category}_from_{file_name}.csv")
        x.to_csv(output_path, index=False)
        return output_path
    return None


def extract_artist_data(df, file_name, output_dir) -> str:
    df_copy = df.copy()
    df_copy['Points'] = pd.to_numeric(df_copy['Points'], errors='coerce')
    df_copy['Points'].fillna(0, inplace=True)
    df_copy.fillna('none', inplace=True)

    # Check if columns exist before concatenation
    artist_cols = ['Artiste ', 'Featured Artiste ', 'Featured Artiste .1', 'Featured Artiste .2', 'Featured Artiste .3', 'Featured Artiste .4']
    existing_cols = [col for col in artist_cols if col in df_copy.columns]
    
    if not existing_cols:
         return None

    df_copy['nw artist'] = df_copy[existing_cols].astype(str).agg(';'.join, axis=1)

    df_copy['nw artist'] = df_copy['nw artist'].str.replace(',', ';')
    df_copy['nw artist'] = df_copy['nw artist'].str.replace('&', ';')

    df_art = split_cat('nw artist', df_copy, ';')
    df_art['nw artist'] = df_art['nw artist'].str.lower().str.strip()

    x = df_art.groupby('nw artist')['Points'].sum()
    x = x.sort_values(ascending=False)
    x = x.reset_index()

    x = x[x['nw artist'] != 'none']

    x['nw artist'] = x['nw artist'].str.title()

    output_path = os.path.join(output_dir, f"Artist_from_{file_name}.csv")
    x.to_csv(output_path, index=False)
    return output_path

def process_data(input_file_path: str, output_dir: str) -> List[str]:
    """
    Process the input CSV file and return a list of paths to the generated files.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    try:
        df = pd.read_csv(input_file_path, encoding='latin1')
    except Exception as e:
        # Try default encoding if latin1 fails, or just raise
        try:
             df = pd.read_csv(input_file_path)
        except:
            raise ValueError(f"Could not read CSV file: {e}")

    file_name = os.path.splitext(os.path.basename(input_file_path))[0]
    generated_files = []

    #extract Producer and Genre data
    categories = ["Genre", "ProducedBy"]
    for cat in categories:
        path = extract_category_data(df, cat, file_name, output_dir)
        if path:
            generated_files.append(path)
    
    #extract artist data
    artist_path = extract_artist_data(df, file_name, output_dir)
    if artist_path:
        generated_files.append(artist_path)
        
    return generated_files