import pandas as pd
import os
import zipfile

current_script_dir = os.path.dirname(os.path.abspath(__file__))
raw_data_dir = os.path.join(current_script_dir, '../../../raw_data')
raw_data_dir = os.path.normpath(raw_data_dir)

transformed_data_dir = os.path.join(current_script_dir, '../../../processed_data')
transformed_data_dir = os.path.normpath(transformed_data_dir)


def get_boomplay_data():
    boomplay_files = []
    files = os.listdir('raw_data')
    for file in files:
        if 'Boomplay' in file:
            boomplay_files.append(file)
    return boomplay_files

def get_date_range(files):
    #file name format is 'Boomplay_NG_20260124.csv'
    dates = []
    
    for file in files:
        try:
            # Extract date part: boomplay_streams_20260123.csv.asc -> 20260123
            date_str = file.split('_')[2].split('.')[0]
            dates.append(date_str)
        except IndexError:
            continue
            
    if not dates:
        return None, None
        
    dates.sort()
    return dates[0], dates[-1]


def transform_boomplay_data():

    #get the files
    data = get_boomplay_data()

    start_date, end_date = get_date_range(data)

    #only run if we have 7 files
    if len(data) != 7:
        print("Not up to 7files,", len(data))
        return None

    #concatenate all the files
    all_boomplay_data = []
    for file in data:
        try:
            full_save_path = os.path.join(raw_data_dir, file)
            df = pd.read_csv(full_save_path, encoding='latin1')
            os.remove(full_save_path)
        except Exception as e:
            print(e, 'excepthnsi')
            continue

        #concat artist and title to retain information
        df['song_info'] = df['Artist'].str.strip().str.lower() + '|' + df['Track Title'].str.strip().str.lower()
        all_boomplay_data.append(df)

    full_boomplay_data = pd.concat(all_boomplay_data)

    x = full_boomplay_data.groupby('song_info')['Ad Supported Plays'].sum().sort_values(ascending=False)

    x = pd.DataFrame(x).reset_index()

    x['Artist'] = x['song_info'].str.split(pat='|', n=-1, expand=True)[0]
    x['Song'] = x['song_info'].str.split(pat='|', n=-1, expand=True)[1]

    x['Artist'] = x['Artist'].str.title()
    x['Song'] = x['Song'].str.title()

    x.drop('song_info', inplace=True, axis=1)

    x = x[['Artist', 'Song', 'Ad Supported Plays']]

    x.to_csv(f"{transformed_data_dir}/Boomplay_{start_date}_{end_date}.csv", index=False)

    zip_file(file_path=f"{transformed_data_dir}/Boomplay_{start_date}_{end_date}.csv")

    #clean dir
    os.remove(f"{transformed_data_dir}/Boomplay_{start_date}_{end_date}.csv")


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
#     transform_boomplay_data()
