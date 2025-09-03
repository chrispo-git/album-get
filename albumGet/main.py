import math
import requests
import time
import os
import sys
import yt_dlp
import time
import argparse
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
        try:
            seconds = int((int(i["length"])/1000)%60)
            minutes = int((int(i["length"])/1000)//60)
        except TypeError:
            seconds = 0
            minutes = 0
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
    totalLength = len(metadata["artist-credit"][0]["name"])+ len(metadata["title"]) + len("   ")
    for i in tracklist:
        if len(i['title'])+9 > totalLength:
            totalLength = len(i['title'])+15
    print("\n")
    print(middleSpace(metadata["artist-credit"][0]["name"], metadata["title"], totalLength))
    print(f"")
    print(f"#  Title{getSpace("",totalLength-14)}Length")
    for i in tracklist:
        print(middleSpace(f"{i['position']}{getSpace(i['position'],3)}{i['title']}", i['length'], totalLength))
    print("")
    try:
        print(f"Status : {metadata["status"]}")
    except KeyError:
        print(f"Status : Unknown")
    try:
        print(f"Country : {metadata["country"]}")
    except KeyError:
        print(f"Country : Unknown")
    try:
        print(f"Format : {metadata["media"][0]["format"]}")
    except KeyError:
        print(f"Format : Unknown")
def downloadTrackList(metadata, output_folder, isForceFirst, isVerbose):
    if not os.path.isdir(f"{output_folder}"):
        os.mkdir(f"{output_folder}")
    else:
        shutil.rmtree(f"{output_folder}")
        os.mkdir(f"{output_folder}")
    print("Downloading Album Cover...")
    if isVerbose:
        print(f"Downloading from https://coverartarchive.org/release/{metadata["id"]}/front")
    cover = requests.get(f"https://coverartarchive.org/release/{metadata["id"]}/front").content
    with open(f'{output_folder}/cover.jpg', 'wb') as img:
        img.write(cover)
    img.close()
    time.sleep(1)
    data = getAlbumData(metadata["id"])
    tracklist = parseTracks(data)
    for i in tracklist:
        downloadAudio(f"{i['title']} - {metadata["artist-credit"][0]["name"]}", i['length'], output_folder, isForceFirst, isVerbose)

def tagTracklist(metadata, output_folder):
    print("Tagging...")
    time.sleep(1)
    data = getAlbumData(metadata["id"])
    tracklist = parseTracks(data)
    
    for i in tracklist:
        query = f"{i['title']} - {metadata["artist-credit"][0]["name"]}"
        if "/" in query:
            query = query.replace("/", "∕")
        audio = MP3(f"{output_folder}/{query}.mp3",ID3=ID3)
        audio.pprint()
        audio.tags.add(
            APIC(
                encoding=0,
                mime='image/jpg',
                type=3,
                desc=u'Cover',
                data=open(f'{output_folder}/cover.jpg', 'rb').read()
            )
        )
        audio.save()
        audio = ID3(f"{output_folder}/{query}.mp3")
        audio.add(TIT2(encoding=3, text=u""+i['title']))    #TITLE
        audio.add(TRCK(encoding=3, text=u""+i['position']))    #TRACK
        audio.add(TPE1(encoding=3, text=u""+metadata["artist-credit"][0]["name"]))    #ARTIST
        audio.add(TALB(encoding=3, text=u""+metadata["title"]))   #ALBUM
        audio.add(TYER(encoding=3, text=u""+metadata["date"])) #YEAR
        audio.add(TDAT(encoding=3, text=u""+metadata["date"])) #YEAR
        audio.add(TORY(encoding=3, text=u""+metadata["date"])) #ORIGYEAR
        audio.add(TPE2(encoding=3, text=u""+metadata["artist-credit"][0]["name"]))   #ALBUMARTIST
        audio.add(TCON(encoding=3, text=u""))    #GENRE
        audio.save(v2_version=3)

def downloadAudio(query, desiredLength, output_folder, isForceFirst, isVerbose):
    print(f"Checking Youtube For '{query}'...")
    if desiredLength[0] == "0" and len(desiredLength) == 5:
        desiredLength = desiredLength[1:]
    replaced = False
    searchNum = 2
    finalUrl = ""
    if isForceFirst:
        searchNum = 1
    while replaced == False:
        out = os.popen(f'yt-dlp ytsearch{searchNum}:"{query} Explicit" --get-id --get-duration --ignore-errors')
        text = out.readlines()
        out.close()
        songCandidates = []
        finalURL = text[0].replace("\n","")
        for i in range(0,len(text)-1, 2):
            songCandidates.append([text[i].replace("\n",""), text[i+1].replace("\n","")])
        if isVerbose:
            print(f"Candidates for {query}:")
            for i in range(0,len(songCandidates)):
                print(f"{i} - {songCandidates[i]}")
            print(f"target time - {desiredLength}")
        for i in songCandidates:
            try:
                t1 = sum(int(x) * 60 ** i for i, x in enumerate(reversed(i[1].split(':'))))
                desiredTime = sum(int(x) * 60 ** i for i, x in enumerate(reversed(desiredLength.split(':'))))
            except ValueError:
                continue
            if isVerbose:
                print(f"Candidate {i[0]} - {i[1]}")
                print(f"Time Difference {desiredTime - t1}")
            if (desiredTime - t1 < 4 and t1 - desiredTime < 4) or isForceFirst:
                finalURL = i[0]
                replaced = True 
                print("success!")
            if isForceFirst:
                if isVerbose:
                    print("force first: forced success.")
                break
        if replaced == False:
            searchNum *= 2
            if searchNum > 16:
                print("Unable to find video with correct length, defaulting to first video")
                break
            else:
                print(f"Searching first {searchNum} results...")
    if "/" in query:
        query = query.replace("/", "∕")
    os.system(f'yt-dlp -x --audio-format mp3 -o "{output_folder}/{query}.mp3" https://www.youtube.com/watch?v={finalURL}')



def cli():
    parser = argparse.ArgumentParser(
        description="Download album tracks via MusicBrainz + YouTube"
    )
    parser.add_argument("artist", help="Artist name")
    parser.add_argument("album", help="Album name")
    parser.add_argument(
        "-o", "--output", default=os.path.join(os.getcwd(), "album-out"),
        help="Save Directory"
    )
    parser.add_argument(
        "-ff", "--force-first",
        action="store_true",
        help="Forces downloading the first youtube result"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging"
    )
    args = parser.parse_args()
    album = args.album
    artist = args.artist
    query = AlbumQuery(album, artist)
    output_folder = args.output
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
    downloadTrackList(meta, output_folder, args.force_first, args.verbose)
    tagTracklist(meta, output_folder)
    end = time.time()
    print(f"Finished in {int(end-start)//60}m {int(end-start)%60}s")
    print("Done! :)")
