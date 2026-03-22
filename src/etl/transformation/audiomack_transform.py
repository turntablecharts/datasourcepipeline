import pandas as pd
import os
import zipfile

current_script_dir = os.path.dirname(os.path.abspath(__file__))
raw_data_dir = os.path.join(current_script_dir, '../../../raw_data')
raw_data_dir = os.path.normpath(raw_data_dir)

transformed_data_dir = os.path.join(current_script_dir, '../../../processed_data')
transformed_data_dir = os.path.normpath(transformed_data_dir)


def get_audiomack_data():
    audiomack_files = []
    files = os.listdir('raw_data')
    for file in files:
        if 'audiomack' in file:
            audiomack_files.append(file)
    return audiomack_files

def get_date_range(files):
    #file name format is 'audiomack_streams_20260128.csv.asc'
    dates = []
    
    for file in files:
        try:
            # Extract date part: audiomack_streams_20260123.csv.asc -> 20260123
            date_str = file.split('_')[2].split('.')[0]
            dates.append(date_str)
        except IndexError:
            continue
            
    if not dates:
        return None, None
        
    dates.sort()
    return dates[0], dates[-1]


def transform_audiomack_data():

    #get the files
    data = get_audiomack_data()

    start_date, end_date = get_date_range(data)

    #only run if we have 7 files
    if len(data) != 7:
        return None

    #concatenate all the files
    all_audiomack_data = []
    for file in data:
        try:
            full_save_path = os.path.join(raw_data_dir, file)
            df = pd.read_csv(full_save_path, encoding='latin1')
            os.remove(full_save_path)
        except Exception as e:
            print(e, 'excepthnsi')
            continue

        #concat artist and title to retain information
        df['song_info'] = df['artist'].str.strip().str.lower() + '|' + df['title'].str.strip().str.lower()
        all_audiomack_data.append(df)

    full_audiomack_data = pd.concat(all_audiomack_data)

    x = full_audiomack_data.groupby('song_info')['total'].sum().sort_values(ascending=False)

    x = pd.DataFrame(x).reset_index()

    x['Artist'] = x['song_info'].str.split(pat='|', n=-1, expand=True)[0]
    x['Song'] = x['song_info'].str.split(pat='|', n=-1, expand=True)[1]

    x['Artist'] = x['Artist'].str.title()
    x['Song'] = x['Song'].str.title()

    x.drop('song_info', inplace=True, axis=1)

    x = x[['Artist', 'Song', 'total']]

    x.to_csv(f"{transformed_data_dir}/Audiomack{start_date}_{end_date}.csv", index=False)

    zip_file(f"{transformed_data_dir}/Audiomack{start_date}_{end_date}.csv")

    #remove file
    os.remove(f"{transformed_data_dir}/Audiomack{start_date}_{end_date}.csv")



def zip_file(file_path):
    # 1. Create the zip filename (e.g., 'data.csv' -> 'data.zip')
    zip_name = os.path.splitext(file_path)[0] + ".zip"
    
    print(f"Zipping {file_path} into {zip_name}...")
    
    # 2. Create the Zip
    # compression=zipfile.ZIP_DEFLATED ensures the file size actually shrinks
    with zipfile.ZipFile(zip_name, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
        # arcname is CRITICAL here. 
        # It tells the zip file to store "file.csv" instead of "Users/user/documents/..."
        zipf.write(file_path, arcname=os.path.basename(file_path))

    print("✅ Done!")


# if __name__ == '__main__':
#     transform_audiomack_data()
