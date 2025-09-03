import requests
import time
import json
headers = {
    "User-Agent": "album-get/0.1.0 (https://github.com/chrispo-git/album-get)"
}
def AlbumQuery(album: str, artist: str):
    album_link = f'https://musicbrainz.org/ws/2/release/?query=release:"{album}" AND artist:"{artist}"&fmt=json'
    album_info = requests.get(album_link, headers=headers).json()
    release = album_info["releases"]
    return release

def getAlbumMeta(query, entry: int):
    release_entry = query[entry]
    return release_entry

def getAlbumData(id: str):
    data_link = f'https://musicbrainz.org/ws/2/release/{id}?inc=recordings&fmt=json'
    return requests.get(data_link, headers=headers).json()

def parseTracks(data):
    allTracks = data["media"][0]["tracks"]
    tracklist = []
    for i in allTracks:
        seconds = int((int(i["length"])/1000)%60)
        minutes = int((int(i["length"])/1000)//60)
        trackInfo = {
            "title" : i["title"], 
            "position" : f"{i["position"]:02}", 
            "length" : f'{minutes:02}:{seconds:02}'
        }
        tracklist.append(trackInfo)
    return tracklist

def getSpace(string:str, space:int):
    space_length = space - len(str(string))
    space_separator = ""
    for i in range(0, space_length):
        space_separator = space_separator + " "
    return space_separator

def middleSpace(string1:str, string2:str, size:int):
    space_length = size - len(str(string1)) - len(str(string2))
    space_separator = ""
    for i in range(0, space_length):
        space_separator = space_separator + " "
    return f"{string1}{space_separator}{string2}"
def printTracklist(metadata):
    time.sleep(1)
    data = getAlbumData(metadata["id"])
    tracklist = parseTracks(data)
    totalLength = len(meta["artist-credit"][0]["name"])+ len(meta["title"]) + len("   ")
    for i in tracklist:
        if len(i['title'])+9 > totalLength:
            totalLength = len(i['title'])+15
    print("\n")
    print(middleSpace(meta["artist-credit"][0]["name"], meta["title"], totalLength))
    print("")
    print(f"#  Title{getSpace("",totalLength-14)}Length")
    for i in tracklist:
        print(middleSpace(f"{i['position']}{getSpace(i['position'],3)}{i['title']}", i['length'], totalLength))

album = input("Album Title:")
artist = input("Artist:")
query = AlbumQuery(album, artist)
entry = 0
while True:
    if entry >= len(query)-1:
        entry = 0
    meta = getAlbumMeta(query, entry)
    id = meta["id"]
    printTracklist(meta)
    exit = input("Is this the correct album? [y/n] ")
    if exit.lower() == "y":
        break
    entry += 1