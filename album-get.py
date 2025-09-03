import math
import requests
import time
import os
import sys
import yt_dlp
import time
import shutil
from datetime import datetime, timedelta
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error, TIT2, TPE2, TALB, TPE1, TYER, TDAT, TRCK, TCON, TORY, TPUB

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
def downloadTrackList(metadata):
    if not os.path.isdir("output"):
        os.mkdir("output")
    else:
        shutil.rmtree("output")
        os.mkdir("output")
    print("Downloading Album Cover...")
    cover = requests.get(f"https://coverartarchive.org/release/{metadata["id"]}/front").content
    with open('output/cover.jpg', 'wb') as img:
        img.write(cover)
    img.close()
    time.sleep(1)
    data = getAlbumData(metadata["id"])
    tracklist = parseTracks(data)
    for i in tracklist:
        downloadAudio(f"{i['title']} - {meta["artist-credit"][0]["name"]}", i['length'])

def tagTracklist(metadata):
    print("Tagging...")
    time.sleep(1)
    data = getAlbumData(metadata["id"])
    tracklist = parseTracks(data)
    
    for i in tracklist:
        audio = MP3(f"output/{i['title']} - {meta["artist-credit"][0]["name"]}.mp3",ID3=ID3)
        audio.pprint()
        audio.tags.add(
            APIC(
                encoding=0,
                mime='image/jpg',
                type=3,
                desc=u'Cover',
                data=open('output/cover.jpg', 'rb').read()
            )
        )
        audio.save()
        audio = ID3(f"output/{i['title']} - {meta["artist-credit"][0]["name"]}.mp3")
        audio.add(TIT2(encoding=3, text=u""+i['title']))    #TITLE
        audio.add(TRCK(encoding=3, text=u""+i['position']))    #TRACK
        audio.add(TPE1(encoding=3, text=u""+meta["artist-credit"][0]["name"]))    #ARTIST
        audio.add(TALB(encoding=3, text=u""+meta["title"]))   #ALBUM
        audio.add(TYER(encoding=3, text=u""+meta["date"])) #YEAR
        audio.add(TDAT(encoding=3, text=u""+meta["date"])) #YEAR
        audio.add(TORY(encoding=3, text=u""+meta["date"])) #ORIGYEAR
        audio.add(TPE2(encoding=3, text=u""+meta["artist-credit"][0]["name"]))   #ALBUMARTIST
        audio.add(TCON(encoding=3, text=u""))    #GENRE
        audio.save(v2_version=3)

def downloadAudio(query, desiredLength):
    print(f"Checking Youtube For '{query}'...")
    if desiredLength[0] == "0" and len(desiredLength) == 5:
        desiredLength = desiredLength[1:]
    replaced = False
    searchNum = 2
    finalUrl = ""
    while replaced == False:
        out = os.popen(f'yt-dlp ytsearch{searchNum}:"{query} Explicit" --get-id --get-duration --ignore-errors')
        text = out.readlines()
        out.close()
        songCandidates = []
        finalURL = text[0].replace("\n","")
        for i in range(0,len(text)-1, 2):
            songCandidates.append([text[i].replace("\n",""), text[i+1].replace("\n","")])
        print(desiredLength)
        print(songCandidates)
        for i in songCandidates:
            try:
                t1 = time.mktime(time.strptime(i[1], "%M:%S"))
                desiredTime = time.mktime(time.strptime(desiredLength, "%M:%S"))
            except ValueError:
                continue
            print(desiredTime-t1)
            if desiredTime - t1 < 4 and t1 - desiredTime < 4:
                finalURL = i[0]
                replaced = True 
        if replaced == False:
            searchNum *= 2
            if searchNum > 16:
                print("Unable to find video with correct length, defaulting to first video")
                break
            else:
                print(f"Searching first {searchNum} results...")
    os.system(f'yt-dlp -x --audio-format mp3 -o "output/{query}.mp3" https://www.youtube.com/watch?v={finalURL}')


album = input("Album Title:")
artist = input("Artist:")
query = AlbumQuery(album, artist)
if len(query) < 1:
    print("No Albums Found.")
    time.sleep(1)
    sys.exit()
entry = 0
meta = getAlbumMeta(query, 0)
while True:
    if entry >= len(query)-1:
        entry = 0
    meta = getAlbumMeta(query, entry)
    printTracklist(meta)
    exit = input("Is this the correct album? [y/n] ")
    if exit.lower() == "y":
        break
    entry += 1

start = time.time()
downloadTrackList(meta)
tagTracklist(meta)
end = time.time()
print(f"Finished in {int(end-start)//60}m {int(end-start)%60}s")
print("Done! :)")