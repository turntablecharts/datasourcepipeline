import ftplib
import gnupg
import os
from datetime import datetime, timedelta
from ...utils.utils import EnvConstants

FTP_HOST = EnvConstants.FTP_HOST
FTP_USER =  EnvConstants.FTP_USER
FTP_PASS = EnvConstants.FTP_PASS
GPG_PASSPHRASE = EnvConstants.GPG_PASSPHRASE
GPG_PATH='/opt/homebrew/bin/gpg'

RAW_DATA_DIR = "./raw_data"

def get_dates_between(start_date_str, end_date_str):
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    formatted_dates = []

    current_date = start_date
    while current_date <= end_date:
        formatted_date = current_date.strftime('%Y%m%d')
        formatted_dates.append(formatted_date)
        current_date += timedelta(days=1)
    
    return formatted_dates


def decrypt_file(gpg_file, output_file):
    gpg = gnupg.GPG(binary=GPG_PATH)
    with open(gpg_file, 'rb') as f:
        decrypted_data = gpg.decrypt_file(f, passphrase=GPG_PASSPHRASE)

        if decrypted_data.ok:
            print('Decrypting ~ '+gpg_file)
            with open(output_file, 'wb') as outfile:
                outfile.write(decrypted_data.data)
            print('Decrypting completed ~ '+gpg_file)
        else:
            print("Decryption failed:", decrypted_data.status)

def download_files(files):
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    raw_data_dir = os.path.join(current_script_dir, '../../../raw_data')
    raw_data_dir = os.path.normpath(raw_data_dir)

    if not os.path.exists(raw_data_dir):
        print(f"Creating directory: {raw_data_dir}")
        os.makedirs(raw_data_dir)

    print('Connecting to FTP')
    print(files)
    ftp = ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASS)
    ftp.encoding = "utf-8"
    print('FTP - welcome ~ '+ftp.getwelcome())


    for i in range(0, len(files)):
        filename = files[i]

        full_save_path = os.path.join(raw_data_dir, filename)
        print("Downloading ~ "+filename)
        
        with open(full_save_path, 'wb') as file:
            ftp.retrbinary(f"RETR {filename}", file.write)
        print("Download completed for ~ "+filename)

        if filename.startswith('audiomack'):
            csv_full_save_path = full_save_path[:-4]
            decrypt_file(full_save_path, csv_full_save_path)
            
            #delete the encrypted file
            os.remove(full_save_path)


def generate_file_names(file_dates):
    result = []
    for i in range(0, len(file_dates)):
        boomplay_name = "Boomplay_NG_"+file_dates[i]+'.csv'
        audiomack_name = "audiomack_streams_"+file_dates[i]+'.csv.asc'

        result.append(boomplay_name)
        result.append(audiomack_name)
    return result


def get_files(start_date, end_date):
    download_files(generate_file_names(get_dates_between(start_date, end_date)))
    print('Download completed...')

