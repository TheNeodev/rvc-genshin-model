import os
import re
import six
import sys
import wget
import shutil
import zipfile
import requests
import json
import argparse
from bs4 import BeautifulSoup
from urllib.parse import unquote, urlencode, parse_qs, urlparse

# Set up working directory and append current directory to the path.
now_dir = os.getcwd()
sys.path.append(now_dir)

# Import your helper functions from your rvc package.
from rvc.lib.utils import format_title
from rvc.lib.tools import gdown


def find_folder_parent(search_dir, folder_name):
    for dirpath, dirnames, _ in os.walk(search_dir):
        if folder_name in dirnames:
            return os.path.abspath(dirpath)
    return None


# Find the folder (for example, a folder called "logs") and create a zips subfolder.
file_path = find_folder_parent(now_dir, "logs")
zips_path = os.path.join(file_path, "zips")


def search_pth_index(folder):
    pth_paths = [
        os.path.join(folder, file)
        for file in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, file)) and file.endswith(".pth")
    ]
    index_paths = [
        os.path.join(folder, file)
        for file in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, file)) and file.endswith(".index")
    ]
    return pth_paths, index_paths


def get_mediafire_download_link(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    download_button = soup.find(
        "a", {"class": "input popsok", "aria-label": "Download file"}
    )
    if download_button:
        download_link = download_button.get("href")
        return download_link
    else:
        return None


def download_from_url(url):
    os.makedirs(zips_path, exist_ok=True)
    if url != "":
        if "drive.google.com" in url:
            if "file/d/" in url:
                file_id = url.split("file/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
            else:
                return None

            if file_id:
                os.chdir(zips_path)
                try:
                    gdown.download(
                        f"https://drive.google.com/uc?id={file_id}",
                        quiet=True,
                        fuzzy=True,
                    )
                except Exception as error:
                    error_message = f"An error occurred downloading the file: {error}"
                    if ("Too many users have viewed or downloaded this file recently" in error_message):
                        os.chdir(now_dir)
                        return "too much use"
                    elif ("Cannot retrieve the public link of the file." in error_message):
                        os.chdir(now_dir)
                        return "private link"
                    else:
                        print(error_message)
                        os.chdir(now_dir)
                        return None
        elif "disk.yandex.ru" in url:
            base_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download?"
            public_key = url
            final_url = base_url + urlencode(dict(public_key=public_key))
            response = requests.get(final_url)
            download_url = response.json()["href"]
            download_response = requests.get(download_url)

            if download_response.status_code == 200:
                filename = parse_qs(urlparse(unquote(download_url)).query).get(
                    "filename", [""]
                )[0]
                if filename:
                    os.chdir(zips_path)
                    with open(filename, "wb") as f:
                        f.write(download_response.content)
            else:
                print("Failed to get filename from URL.")
                return None

        elif "pixeldrain.com" in url:
            try:
                file_id = url.split("pixeldrain.com/u/")[1]
                os.chdir(zips_path)
                print("Downloading from pixeldrain, file id:", file_id)
                response = requests.get(f"https://pixeldrain.com/api/file/{file_id}")
                if response.status_code == 200:
                    file_name = (
                        response.headers.get("Content-Disposition")
                        .split("filename=")[-1]
                        .strip('";')
                    )
                    with open(os.path.join(zips_path, file_name), "wb") as newfile:
                        newfile.write(response.content)
                    os.chdir(file_path)
                    return "downloaded"
                else:
                    os.chdir(file_path)
                    return None
            except Exception as error:
                print(f"An error occurred downloading the file: {error}")
                os.chdir(file_path)
                return None

        elif "cdn.discordapp.com" in url:
            file = requests.get(url)
            os.chdir(zips_path)
            if file.status_code == 200:
                name = url.split("/")
                with open(os.path.join(zips_path, name[-1]), "wb") as newfile:
                    newfile.write(file.content)
            else:
                return None
        elif "/blob/" in url or "/resolve/" in url:
            os.chdir(zips_path)
            if "/blob/" in url:
                url = url.replace("/blob/", "/resolve/")

            response = requests.get(url, stream=True)
            if response.status_code == 200:
                content_disposition = six.moves.urllib_parse.unquote(
                    response.headers["Content-Disposition"]
                )
                m = re.search(r'filename="([^"]+)"', content_disposition)
                file_name = m.groups()[0]
                file_name = file_name.replace(os.path.sep, "_")
                total_size_in_bytes = int(response.headers.get("content-length", 0))
                block_size = 1024
                progress_bar_length = 50
                progress = 0

                with open(os.path.join(zips_path, file_name), "wb") as file:
                    for data in response.iter_content(block_size):
                        file.write(data)
                        progress += len(data)
                        progress_percent = int((progress / total_size_in_bytes) * 100)
                        num_dots = int((progress / total_size_in_bytes) * progress_bar_length)
                        progress_bar = "[" + "." * num_dots + " " * (progress_bar_length - num_dots) + "]"
                        print(f"{progress_percent}% {progress_bar} {progress}/{total_size_in_bytes}  ", end="\r")
                        if progress_percent == 100:
                            print("\n")

            else:
                os.chdir(now_dir)
                return None
        elif "/tree/main" in url:
            os.chdir(zips_path)
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            temp_url = ""
            for link in soup.find_all("a", href=True):
                if link["href"].endswith(".zip"):
                    temp_url = link["href"]
                    break
            if temp_url:
                url = temp_url
                url = url.replace("blob", "resolve")
                if "huggingface.co" not in url:
                    url = "https://huggingface.co" + url
                wget.download(url)
            else:
                os.chdir(now_dir)
                return None
        elif "applio.org" in url:
            parts = url.split("/")
            id_with_query = parts[-1]
            id_parts = id_with_query.split("?")
            id_number = id_parts[0]

            url = "https://cjtfqzjfdimgpvpwhzlv.supabase.co/rest/v1/models"
            headers = {
                "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNqdGZxempmZGltZ3B2cHdoemx2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE2OTUxNjczODgsImV4cCI6MjAxMDc0MzM4OH0.7z5WMIbjR99c2Ooc0ma7B_FyGq10G8X-alkCYTkKR10"
            }
            params = {"id": f"eq.{id_number}"}
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                json_response = response.json()
                print(json_response)
                if json_response:
                    link = json_response[0]["link"]
                    verify = download_from_url(link)
                    if verify == "downloaded":
                        return "downloaded"
                    else:
                        return None
            else:
                return None
        else:
            try:
                os.chdir(zips_path)
                wget.download(url)
            except Exception as error:
                os.chdir(now_dir)
                print(f"An error occurred downloading the file: {error}")
                return None

        # Rename any zip files to remove extra dots if needed.
        for currentPath, _, zipFiles in os.walk(zips_path):
            for file in zipFiles:
                parts = file.split(".")
                extension = parts[-1]
                new_name = "_".join(parts[:-1]) + "." + extension
                os.rename(os.path.join(currentPath, file), os.path.join(currentPath, new_name))

        os.chdir(now_dir)
        return "downloaded"

    os.chdir(now_dir)
    return None


def extract_and_show_progress(zipfile_path, unzips_path):
    try:
        with zipfile.ZipFile(zipfile_path, "r") as zip_ref:
            for file_info in zip_ref.infolist():
                zip_ref.extract(file_info, unzips_path)
        os.remove(zipfile_path)
        return True
    except Exception as error:
        print(f"An error occurred extracting the zip file: {error}")
        return False


def unzip_file(zip_path, zip_file_name):
    zip_file_path = os.path.join(zip_path, zip_file_name + ".zip")
    extract_path = os.path.join(file_path, zip_file_name)
    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(extract_path)
    os.remove(zip_file_path)


def model_download_pipeline(url: str):
    try:
        verify = download_from_url(url)
        if verify == "downloaded":
            extract_folder_path = ""
            for filename in os.listdir(zips_path):
                if filename.endswith(".zip"):
                    zipfile_path = os.path.join(zips_path, filename)
                    print("Proceeding with the extraction...")

                    model_zip = os.path.basename(zipfile_path)
                    model_name = format_title(model_zip.split(".zip")[0])
                    extract_folder_path = os.path.join("logs", os.path.normpath(model_name))
                    success = extract_and_show_progress(zipfile_path, extract_folder_path)

                    # Remove any temporary macOS folders if present.
                    macosx_path = os.path.join(extract_folder_path, "__MACOSX")
                    if os.path.exists(macosx_path):
                        shutil.rmtree(macosx_path)

                    # If only one subfolder exists, move its contents up one level.
                    subfolders = [
                        f for f in os.listdir(extract_folder_path)
                        if os.path.isdir(os.path.join(extract_folder_path, f))
                    ]
                    if len(subfolders) == 1:
                        subfolder_path = os.path.join(extract_folder_path, subfolders[0])
                        for item in os.listdir(subfolder_path):
                            s = os.path.join(subfolder_path, item)
                            d = os.path.join(extract_folder_path, item)
                            shutil.move(s, d)
                        os.rmdir(subfolder_path)

                    # Optionally, rename files so that the model’s .pth and .index files match the model name.
                    for item in os.listdir(extract_folder_path):
                        if ".pth" in item:
                            file_name = item.split(".pth")[0]
                            if file_name != model_name:
                                os.rename(
                                    os.path.join(extract_folder_path, item),
                                    os.path.join(extract_folder_path, model_name + ".pth"),
                                )
                        else:
                            if "v2" not in item:
                                if "_nprobe_1_" in item and "_v1" in item:
                                    file_name = item.split("_nprobe_1_")[1].split("_v1")[0]
                                    if file_name != model_name:
                                        new_file_name = item.split("_nprobe_1_")[0] + "_nprobe_1_" + model_name + "_v1"
                                        os.rename(
                                            os.path.join(extract_folder_path, item),
                                            os.path.join(extract_folder_path, new_file_name + ".index"),
                                        )
                            else:
                                if "_nprobe_1_" in item and "_v2" in item:
                                    file_name = item.split("_nprobe_1_")[1].split("_v2")[0]
                                    if file_name != model_name:
                                        new_file_name = item.split("_nprobe_1_")[0] + "_nprobe_1_" + model_name + "_v2"
                                        os.rename(
                                            os.path.join(extract_folder_path, item),
                                            os.path.join(extract_folder_path, new_file_name + ".index"),
                                        )

                    if success:
                        print(f"Model {model_name} downloaded!")
                    else:
                        print(f"Error downloading {model_name}")
                        return "Error"
            if extract_folder_path == "":
                print("Zip file was not found.")
                return "Error"
            result = search_pth_index(extract_folder_path)
            return result
        else:
            return "Error"
    except Exception as error:
        print(f"An unexpected error occurred: {error}")
        return "Error"


###############################################################################
# NEW FUNCTIONALITY: Downloading models from a JSON configuration file
###############################################################################

def download_models_from_config(config_file):
    """
    Reads a JSON config file and downloads models specified in the "model_data" list.
    Each entry in "model_data" should be a list with at least three items:
       [version, model_name, download_url, (optional image URL)]
    """
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    model_data = config.get("model_data", [])
    for model in model_data:
        if len(model) < 3:
            print("Skipping invalid model entry:", model)
            continue
        version, model_name, download_url = model[:3]
        print(f"\nDownloading model: {model_name} (version: {version})")
        result = model_download_pipeline(download_url)
        if result == "Error":
            print(f"Error downloading {model_name}.")
        else:
            pth_files, index_files = result
            print(f"Downloaded {model_name}: {len(pth_files)} .pth files and {len(index_files)} .index files found.")


###############################################################################
# MAIN: Parse arguments and start the download process.
###############################################################################

if __name__ == "__main__":
    
    download_models_from_config("genshin_model.json")
