import requests
import json
headers = {
    "User-Agent": "album-get/0.1.0 (chaastrup865@gmail.com)"
}
def getAlbumID(album: str, artist: str):
    album_link = f'https://musicbrainz.org/ws/2/release/?query=release:"{album}" AND artist:"{artist}"&fmt=json'
    album_info = requests.get(album_link, headers=headers).json()
    release_id = album_info["releases"][0]["id"]
    return release_id


print(getAlbumID("The College Dropout", "Kanye West"))