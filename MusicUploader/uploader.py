from dataclasses import dataclass
from PIL import Image
from io import BytesIO
import os
import json
import requests
import mutagen

API_URL = "http://113.44.33.81:29802/music"

@dataclass
class Config:
    name:   str = ""
    singer: str = ""
    album:  str = ""
    multiline: bool = False
    lyricsText: str = ""
    
    audioFilePath: str = ""
    coverImage: bytes = b""

    description: str = ""


def load_cover_image(data: bytes):
    image = Image.open(BytesIO(data))
    if image.size[0] > 1000:
        image = image.resize((1000, 1000))
    if image.mode == "RGBA":
        image = image.convert("RGB")
    bytesIO = BytesIO()
    image.save(bytesIO, "JPEG")
    return bytesIO.getvalue()


def upload(config: Config):
    # upload basic config
    basicPayload = {
        "name":     config.name,
        "singer":   config.singer,
        "album":    config.album,
        "multiline": config.multiline,
        "description": config.description
    }
    response = requests.post(f"{API_URL}/config", data=basicPayload)
    if response.status_code != 200:
        print(f"Error when update config, status-code={response.status_code}")
        return False
    response = response.json()
    newID = response["id"]

    # upload lyrics
    lyricsPayload = {
        "id": newID,
        "lyrics": config.lyricsText
    }
    response = requests.post(f"{API_URL}/lyrics", data=lyricsPayload)
    if response.status_code != 200:
        print("Error when update lyrics")
        return False
    
    # upload cover
    coverPayload = {
        "id": newID
    }
    coverFiles = {
        "image": load_cover_image(config.coverImage)
    }
    response = requests.post(f"{API_URL}/cover", data=coverPayload, files=coverFiles)
    if response.status_code != 200:
        print(f"Error when upload cover, status-code={response.status_code}")
        return False
    
    # upload audio
    audioPayload = {
        "id": newID
    }
    audioFiles = {
        "audio": open(config.audioFilePath, "rb").read()
    }
    response = requests.post(f"{API_URL}/audio", data=audioPayload, files=audioFiles)
    if response.status_code != 200:
        print(f"Error when upload audio, status-code={response.status_code}")
        return False
    
    print(f"Upload {config.name} SUCCESS, newID={newID}")
    return True


def get_abs_path(filename: str, pwd: str):
    if not os.path.isfile(filename):
        tmp = pwd + filename
        if os.path.isfile(tmp):
            return tmp
        else:
            raise FileNotFoundError(f'"{filename}" or "{tmp}"')
    else:
        return filename


def get_cover_from_audio(filepath: str) -> bytes:
    audioFile = mutagen.File(filepath)
    return audioFile.tags["APIC:"].data


def from_old_configure_file(filepath: str):
    config = Config()
    with open(filepath, encoding="utf-8") as f:
        c: dict = json.load(f)
    pwd = os.path.dirname(filepath)
    
    config.name = c["title"]
    config.singer, config.album = map(lambda s : s.strip(), c["subTitle"].split("-"))
    config.multiline = c.get("multilineLyrics", False)
    config.audioFilePath = get_abs_path(c["audioFilePath"], pwd)

    if c.get("coverFilePath", None) is None:
        config.coverImage = get_cover_from_audio(config.audioFilePath)
    else:
        config.coverImage = open(get_abs_path(c["coverFilePath"], pwd)).read()
    
    with open(get_abs_path(c["lyricsFilePath"], pwd), encoding="utf-8") as f:
         config.lyricsText = f.read()
    
    upload(config)


def from_163(songId: int, audioFilePath: str):
    if not os.path.isfile(audioFilePath):
        raise FileNotFoundError(audioFilePath)
    
    config = Config()
    config.audioFilePath = audioFilePath
    
    # load basic info
    songInfoURL = 'https://music.163.com/api/v3/song/detail?c=[{id: %d}]' % songId
    songInfoResponse = requests.get(songInfoURL)
    if songInfoResponse.status_code != 200:
        raise ValueError(f"Error when read basic info, songId={songId}, response_code={songInfoResponse.status_code}")
    songInfo: dict = songInfoResponse.json()["songs"][0]
    config.name   = songInfo["name"]
    config.singer = songInfo["ar"][0]["name"]
    config.album  = songInfo["al"]["name"]
    
    # load lyrics
    lyricsResponse = requests.get(f"https://music.163.com/api/song/media", params={"id": songId})
    if lyricsResponse.status_code != 200:
        raise ValueError(f"Error when read lyrics, songId={songId}, response_code={songInfoResponse.status_code}")
    lyricsText = lyricsResponse.json()["lyric"]
    config.lyricsText = lyricsText
    print(lyricsText)

    # load cover image
    coverImageURL = songInfo["al"]["picUrl"]
    coverImageResponse = requests.get(coverImageURL)
    if coverImageResponse.status_code != 200:
        raise ValueError(f"Error when read basic info, songId={songId}, response_code={coverImageResponse.status_code}")
    config.coverImage = coverImageResponse.content

    upload(config)


if __name__ == "__main__":
    from_163(2078700726, "D://Music//柯柯柯啊 - 姑娘别哭泣.mp3")
