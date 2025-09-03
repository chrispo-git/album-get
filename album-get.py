import requests
import json

def getAlbumJson(album: str, artist: str):
    album_link = f'https://musicbrainz.org/ws/2/release/?query=release:"{album}" AND artist:"{artist}"&fmt=json'
    album_info = requests.get(album_link).json()
    release_id = album_info["releases"][0]["id"]
    print(release_id)
    return 


getAlbumJson("The College Dropout", "Kanye West")

#print(getAlbumJson("The College Dropout", "Kanye West"))