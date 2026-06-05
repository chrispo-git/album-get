import requests
import time
import os
import sys
import argparse
import shutil
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE2, TALB, TPE1, TYER, TDAT, TRCK, TCON, TORY

VALID_BROWSERS = ("firefox", "chrome", "chromium", "brave", "opera", "edge", "safari", "vivaldi", "whale")

headers = {
    "User-Agent": "album-get/0.1.0 (https://github.com/chrispo-git/album-get)"
}

#  MusicBrainz 

def AlbumQuery(album: str, artist: str):
    album_link = f'https://musicbrainz.org/ws/2/release/?query=release:"{album}" AND artist:"{artist}"&fmt=json'
    album_info = requests.get(album_link, headers=headers).json()
    return album_info["releases"]

def getAlbumMeta(query, entry: int):
    return query[entry]

def getAlbumData(id: str):
    data_link = f'https://musicbrainz.org/ws/2/release/{id}?inc=recordings+genres+release-groups&fmt=json'
    return requests.get(data_link, headers=headers).json()

def parseTracks(data):
    allTracks = data["media"][0]["tracks"]
    tracklist = []
    for i in allTracks:
        try:
            seconds = int((int(i["length"]) / 1000) % 60)
            minutes = int((int(i["length"]) / 1000) // 60)
        except TypeError:
            seconds = 0
            minutes = 0
        tracklist.append({
            "title":    i["title"],
            "position": f"{i['position']:02}",
            "length":   f"{minutes:02}:{seconds:02}",
        })
    return tracklist

def _extractYear(metadata: dict, data: dict) -> str:
    """
    Extract a 4-digit year string from the release metadata.
    Tries release date first, then release-group first-release-date.
    """
    date = metadata.get("date") or data.get("date", "")
    if date:
        return date[:4]
    rg = data.get("release-group", {})
    rg_date = rg.get("first-release-date", "")
    return rg_date[:4] if rg_date else ""

def _extractGenres(data: dict) -> str:
    """
    Extract genres from MusicBrainz release data.
    Genres are sorted by vote count descending; we take up to 3.
    Falls back to release-group genres if release has none.
    """
    genres = data.get("genres", [])
    if not genres:
        genres = data.get("release-group", {}).get("genres", [])
    # Sort by vote count descending (MusicBrainz already does this, but be safe)
    genres = sorted(genres, key=lambda g: g.get("count", 0), reverse=True)
    return ", ".join(g["name"] for g in genres[:3]) if genres else ""



def getSpace(string: str, space: int):
    return " " * (space - len(str(string)))

def middleSpace(string1: str, string2: str, size: int):
    space_length = size - len(str(string1)) - len(str(string2))
    return f"{string1}{' ' * space_length}{string2}"

def printTracklist(metadata):
    time.sleep(1)
    data = getAlbumData(metadata["id"])
    tracklist = parseTracks(data)
    totalLength = len(metadata["artist-credit"][0]["name"]) + len(metadata["title"]) + 3
    for i in tracklist:
        if len(i["title"]) + 9 > totalLength:
            totalLength = len(i["title"]) + 15
    print("\n")
    print(middleSpace(metadata["artist-credit"][0]["name"], metadata["title"], totalLength))
    print()
    print(f"#  Title{getSpace('', totalLength - 14)}Length")
    for i in tracklist:
        print(middleSpace(f"{i['position']}{getSpace(i['position'], 3)}{i['title']}", i["length"], totalLength))
    print()
    print(f"Status  : {metadata.get('status', 'Unknown')}")
    print(f"Country : {metadata.get('country', 'Unknown')}")
    try:
        print(f"Format  : {metadata['media'][0]['format']}")
    except (KeyError, IndexError):
        print("Format  : Unknown")

#  yt-dlp helpers 


def _shell(cmd: str, isVerbose: bool) -> list[str]:
    """Run a shell command and return non-empty stripped lines."""
    if isVerbose:
        print(f"$ {cmd}")
    out   = os.popen(cmd)
    lines = [l.strip() for l in out.readlines() if l.strip()]
    out.close()
    return lines


def _searchYouTube(query: str, n: int, browser: str | None, isVerbose: bool) -> list[dict]:
    """
    Search YouTube for up to n results via shell yt-dlp.
    Returns a list of {"id": ..., "title": ..., "duration": <seconds|None>}.
    Note: cookies are intentionally omitted here — --cookies-from-browser
    breaks --flat-playlist on yt-dlp 2026.x. Cookies are only needed for download.
    """
    safe_query = query.replace('"', '\\"')
    cmd = (
        f'yt-dlp "ytsearch{n}:{safe_query}" '
        f'--flat-playlist --print "%(id)s %(duration)s %(title)s" '
        f'--ignore-errors 2>/dev/null'
    )
    lines   = _shell(cmd, isVerbose)
    results = []
    for line in lines:
        parts = line.split(" ", 2)
        if len(parts) < 2:
            continue
        vid_id = parts[0]
        if vid_id.startswith("OLAK5uy_"):
            continue
        try:
            duration = float(parts[1])
        except ValueError:
            duration = None
        title = parts[2] if len(parts) == 3 else ""
        results.append({"id": vid_id, "title": title, "duration": duration})
    return results

def findArtistChannel(artist: str, browser: str | None, isVerbose: bool) -> str | None:
    """
    Find the artist's YouTube channel URL via shell search.
    Tries '<artist> - Topic' first, then plain artist name.
    Note: cookies omitted for same reason as _searchYouTube.
    """
    for search_term in [f"{artist} - Topic", artist]:
        safe_term = search_term.replace('"', '\\"')
        cmd = (
            f'yt-dlp "ytsearch5:{safe_term}" '
            f'--flat-playlist --print "%(channel_url)s\t%(channel)s" '
            f'--ignore-errors 2>/dev/null'
        )
        lines = _shell(cmd, isVerbose)
        for line in lines:
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            channel_url, channel_name = parts
            if artist.lower() in channel_name.lower() and channel_url.startswith("http"):
                if isVerbose:
                    print(f"Found channel '{channel_name}': {channel_url}")
                return channel_url

    if isVerbose:
        print(f"No matching channel found for '{artist}'")
    return None


def _isLikelyMusicVideo(title: str) -> bool:
    """Return True if the title suggests an official music video edit (to be deprioritised)."""
    t = title.lower()
    return any(phrase in t for phrase in [
        "official video", "official music video", "music video", "official mv",
    ])

def _videoScore(title: str) -> int:
    """Lower score = more preferred. Audio/lyric uploads beat music videos."""
    t = title.lower()
    if any(p in t for p in ["(audio)", "audio", "(lyrics)", "lyrics", "lyric video"]):
        return 0
    if _isLikelyMusicVideo(t):
        return 2
    return 1


def _expandPlaylist(playlist_id: str, isVerbose: bool) -> list[dict]:
    """Expand an OLAK5uy_ album playlist into individual track video IDs."""
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    cmd = (
        f'yt-dlp "{url}" '
        f'--flat-playlist --print "%(id)s %(duration)s %(title)s" '
        f'--ignore-errors 2>/dev/null'
    )
    lines = _shell(cmd, isVerbose)
    results = []
    for line in lines:
        parts = line.split(" ", 2)
        if len(parts) < 2:
            continue
        vid_id = parts[0]
        if vid_id.startswith("OLAK5uy_"):
            continue
        try:
            duration = float(parts[1])
        except ValueError:
            duration = None
        title = parts[2] if len(parts) == 3 else ""
        results.append({"id": vid_id, "title": title, "duration": duration})
    return results


def getChannelVideos(channel_url: str, browser: str | None, isVerbose: bool) -> list[dict]:
    """
    Pull video IDs, titles, and durations from the channel's /releases tab,
    expanding album playlists into individual tracks. Falls back to /videos
    if releases yields nothing, filtering out likely music video edits.
    """
    #  Try /releases first (expands OLAK5uy_ playlists into tracks) 
    releases_url = channel_url.rstrip("/") + "/releases"
    cmd = (
        f'yt-dlp "{releases_url}" '
        f'--flat-playlist --print "%(id)s %(duration)s %(title)s" '
        f'--ignore-errors 2>/dev/null'
    )
    lines = _shell(cmd, isVerbose)
    results = []
    for line in lines:
        parts = line.split(" ", 2)
        if len(parts) < 2:
            continue
        vid_id = parts[0]
        if vid_id.startswith("OLAK5uy_"):
            # Expand the album playlist into individual tracks
            expanded = _expandPlaylist(vid_id, isVerbose)
            results.extend(expanded)
            continue
        try:
            duration = float(parts[1])
        except ValueError:
            duration = None
        title = parts[2] if len(parts) == 3 else ""
        results.append({"id": vid_id, "title": title, "duration": duration})

    if results:
        if isVerbose:
            print(f"Got {len(results)} tracks from /releases (expanded)")
        return results

    #  Fall back to /videos, deprioritising music video edits 
    videos_url = channel_url.rstrip("/") + "/videos"
    cmd = (
        f'yt-dlp "{videos_url}" '
        f'--flat-playlist --print "%(id)s %(duration)s %(title)s" '
        f'--ignore-errors 2>/dev/null'
    )
    lines = _shell(cmd, isVerbose)
    results = []
    for line in lines:
        parts = line.split(" ", 2)
        if len(parts) < 2:
            continue
        vid_id = parts[0]
        if vid_id.startswith("OLAK5uy_"):
            continue
        try:
            duration = float(parts[1])
        except ValueError:
            duration = None
        title = parts[2] if len(parts) == 3 else ""
        results.append({"id": vid_id, "title": title, "duration": duration})

    # Sort: audio/lyric uploads first, music videos last
    results.sort(key=lambda v: _videoScore(v["title"]))

    if results:
        if isVerbose:
            print(f"Got {len(results)} videos from /videos (sorted by preference)")
    return results

#  Download + tagging 

def _parseSeconds(length_str: str) -> int:
    stripped = length_str.lstrip("0") or "0"
    if stripped.startswith(":"):
        stripped = "0" + stripped
    try:
        return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stripped.split(":"))))
    except ValueError:
        return 0


def downloadAudio(
    query: str,
    desiredLength: str,
    output_folder: str,
    isForceFirst: bool,
    isVerbose: bool,
    browser: str | None = None,
    cookies_file: str | None = None,
    channel_videos: list[dict] | None = None,
):
    print(f"Checking YouTube for '{query}'...")

    desired_seconds = _parseSeconds(desiredLength)
    final_id = None

    #  1. Try to match from artist channel 
    if channel_videos:
        track_title = query.split(" - ")[0].lower()
        best_id = None
        best_diff = float("inf")

        for v in channel_videos:
            if track_title not in v["title"].lower():
                continue
            dur = float(v.get("duration") or 0)
            diff = abs(desired_seconds - dur) if dur > 0 else float("inf")
            if isVerbose:
                print(f"  Channel candidate: '{v['title']}' ({dur}s, diff={diff}s)")
            # Accept if: no duration info (official channel, trust title match),
            # duration matches within 4s, or force-first is set
            if dur == 0 or diff < 4 or isForceFirst:
                final_id = v["id"]
                print("success! (channel match)")
                break
            if diff < best_diff:
                best_diff = diff
                best_id = v["id"]

        if not final_id and best_id and best_diff <= 15:
            final_id = best_id
            if isVerbose:
                print(f"  Using closest channel match (diff={best_diff}s)")
            print("success! (channel match, approximate duration)")

    #  2. Fall back to generic YouTube search 
    if not final_id:
        if channel_videos is not None and isVerbose:
            print("No channel match found, falling back to search...")

        search_num = 1 if isForceFirst else 2
        replaced = False

        while not replaced:
            candidates = _searchYouTube(f"{query} Explicit", search_num, browser, isVerbose)
            # Prefer audio/lyric uploads over music video edits
            candidates.sort(key=lambda c: _videoScore(c["title"]))

            if isVerbose:
                print(f"Search candidates: {[(c['id'], c['duration']) for c in candidates]}")
                print(f"Target: {desiredLength} ({desired_seconds}s)")

            for c in candidates:
                dur = float(c.get("duration") or 0)
                if abs(desired_seconds - dur) < 6 or isForceFirst:
                    final_id = c["id"]
                    replaced = True
                    print("success!")
                    break
                if isForceFirst:
                    break

            if not replaced:
                search_num *= 2
                if search_num > 16:
                    print("Unable to find video with correct length, defaulting to first result")
                    final_id = candidates[0]["id"] if candidates else None
                    break
                print(f"Expanding search to first {search_num} results...")

    if not final_id:
        print(f"ERROR: could not find a video for '{query}', skipping.")
        return

    safe_query  = query.replace("/", "∕")
    cookie_flag = f'--cookies "{cookies_file}"' if cookies_file else ""
    os.system(
        f'yt-dlp -x --audio-format mp3 {cookie_flag}'
        f' -o "{output_folder}/{safe_query}.mp3"'
        f' https://www.youtube.com/watch?v={final_id}'
    )


def downloadTrackList(metadata, output_folder, isForceFirst, isVerbose, browser, cookies_file):
    if not os.path.isdir(output_folder):
        os.mkdir(output_folder)
    else:
        shutil.rmtree(output_folder)
        os.mkdir(output_folder)

    print("Downloading album cover...")
    if isVerbose:
        print(f"Cover URL: https://coverartarchive.org/release/{metadata['id']}/front")
    cover = requests.get(f"https://coverartarchive.org/release/{metadata['id']}/front").content
    with open(f"{output_folder}/cover.jpg", "wb") as img:
        img.write(cover)

    artist_name = metadata["artist-credit"][0]["name"]

    print(f"Looking up YouTube channel for '{artist_name}'...")
    channel_url = findArtistChannel(artist_name, browser, isVerbose)
    channel_videos: list[dict] = []
    if channel_url:
        channel_videos = getChannelVideos(channel_url, browser, isVerbose)
        print(f"Found {len(channel_videos)} videos on channel — will prefer channel matches.")
    else:
        print("Could not resolve artist channel; using generic search fallback.")

    time.sleep(1)
    data = getAlbumData(metadata["id"])
    tracklist = parseTracks(data)

    for i in tracklist:
        downloadAudio(
            f"{i['title']} - {artist_name}",
            i["length"],
            output_folder,
            isForceFirst,
            isVerbose,
            browser=browser,
            cookies_file=cookies_file,
            channel_videos=channel_videos,
        )


def tagTracklist(metadata, output_folder):
    print("Tagging...")
    time.sleep(1)
    data = getAlbumData(metadata["id"])
    tracklist = parseTracks(data)
    artist_name = metadata["artist-credit"][0]["name"]
    year  = _extractYear(metadata, data)
    genre = _extractGenres(data)
    if genre:
        print(f"Genre: {genre}")
    if year:
        print(f"Year:  {year}")

    for i in tracklist:
        query = f"{i['title']} - {artist_name}"
        if "/" in query:
            query = query.replace("/", "∕")

        audio = MP3(f"{output_folder}/{query}.mp3", ID3=ID3)
        audio.tags.add(
            APIC(
                encoding=0,
                mime="image/jpg",
                type=3,
                desc=u"Cover",
                data=open(f"{output_folder}/cover.jpg", "rb").read(),
            )
        )
        audio.save()

        tags = ID3(f"{output_folder}/{query}.mp3")
        tags.add(TIT2(encoding=3, text=u"" + i["title"]))
        tags.add(TRCK(encoding=3, text=u"" + i["position"]))
        tags.add(TPE1(encoding=3, text=u"" + artist_name))
        tags.add(TALB(encoding=3, text=u"" + metadata["title"]))
        tags.add(TYER(encoding=3, text=u"" + year))
        tags.add(TDAT(encoding=3, text=u"" + year))
        tags.add(TORY(encoding=3, text=u"" + year))
        tags.add(TPE2(encoding=3, text=u"" + artist_name))
        tags.add(TCON(encoding=3, text=u"" + genre))
        tags.save(v2_version=3)

#  CLI 

def cli():
    parser = argparse.ArgumentParser(
        description="Download album tracks via MusicBrainz + YouTube"
    )
    parser.add_argument("artist", help="Artist name")
    parser.add_argument("album",  help="Album name")
    parser.add_argument(
        "-o", "--output", default=os.path.join(os.getcwd(), "album-out"),
        help="Save directory",
    )
    parser.add_argument(
        "-ff", "--force-first",
        action="store_true",
        help="Force downloading the first YouTube result",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    parser.add_argument(
        "-c", "--cookies",
        default=None,
        metavar="FILE",
        help="Path to a Netscape cookies file for YouTube authentication. "
             "Export once with: yt-dlp --cookies-from-browser chrome --cookies cookies.txt https://www.youtube.com",
    )
        help=(
            "Pass cookies from your browser to bypass bot detection. "
            f"Supported: {', '.join(VALID_BROWSERS)}"
        ),
    )
    args = parser.parse_args()

    if args.browser and args.browser.lower() not in VALID_BROWSERS:
        print(f"Error: '{args.browser}' is not a supported browser.")
        print(f"Supported browsers: {', '.join(VALID_BROWSERS)}")
        sys.exit(1)
    browser = args.browser.lower() if args.browser else None

    query = AlbumQuery(args.album, args.artist)
    if len(query) < 1:
        print("No albums found.")
        time.sleep(1)
        sys.exit()

    entry = 0
    while True:
        if entry >= len(query):
            entry = 0
        meta = getAlbumMeta(query, entry)
        printTracklist(meta)
        answer = input("Is this the correct album? [y/n] ")
        if answer.lower() == "y":
            break
        entry += 1

    start = time.time()
    downloadTrackList(meta, args.output, args.force_first, args.verbose, browser, args.cookies)
    tagTracklist(meta, args.output)
    end = time.time()
    elapsed = int(end - start)
    print(f"Finished in {elapsed // 60}m {elapsed % 60}s")
    print("Done! :)")


if __name__ == "__main__":
    cli()
