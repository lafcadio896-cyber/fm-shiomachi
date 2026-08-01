#!/usr/bin/env python3
"""Generate a processed MP3 for one FM Shiomachi broadcast using VOICEVOX Nemo."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BROADCASTS_PATH = ROOT / "data" / "broadcasts.json"
PRONUNCIATIONS_PATH = ROOT / "data" / "pronunciations.json"
AUDIO_DIR = ROOT / "audio"
JST = ZoneInfo("Asia/Tokyo")
DEFAULT_ENGINE_URL = "http://127.0.0.1:50021"
DEFAULT_VOICE_NUMBER = 6


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, value: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def request_json(url: str, *, data: bytes | None = None, method: str | None = None) -> object:
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"VOICEVOX API error {error.code}: {detail}") from error


def request_bytes(url: str, *, data: bytes) -> bytes:
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"VOICEVOX synthesis error {error.code}: {detail}") from error


def choose_nemo_voice(engine_url: str, voice_number: int) -> tuple[int, str]:
    speakers = request_json(f"{engine_url}/speakers")
    if not isinstance(speakers, list):
        raise RuntimeError("VOICEVOX /speakers returned an unexpected response")

    voices: list[tuple[int, str]] = []
    for speaker in speakers:
        if not isinstance(speaker, dict):
            continue
        speaker_name = str(speaker.get("name", "VOICEVOX Nemo"))
        styles = speaker.get("styles", [])
        if not isinstance(styles, list):
            continue
        for style in styles:
            if not isinstance(style, dict) or "id" not in style:
                continue
            style_type = style.get("type", "talk")
            if style_type not in (None, "talk"):
                continue
            style_name = str(style.get("name", "ノーマル"))
            voices.append((int(style["id"]), f"{speaker_name} / {style_name}"))

    if not 1 <= voice_number <= len(voices):
        raise RuntimeError(
            f"Nemo voice {voice_number} is unavailable; engine returned {len(voices)} talk voices"
        )
    return voices[voice_number - 1]


def load_pronunciations(broadcast: dict) -> dict[str, str]:
    replacements: dict[str, str] = {}

    if PRONUNCIATIONS_PATH.exists():
        data = load_json(PRONUNCIATIONS_PATH)
        global_replacements = data.get("replacements", {})
        if isinstance(global_replacements, dict):
            replacements.update(
                {
                    str(source): str(reading)
                    for source, reading in global_replacements.items()
                    if source and reading
                }
            )

    local_replacements = broadcast.get("pronunciations", {})
    if isinstance(local_replacements, dict):
        replacements.update(
            {
                str(source): str(reading)
                for source, reading in local_replacements.items()
                if source and reading
            }
        )

    return replacements


def apply_pronunciations(text: str, replacements: dict[str, str]) -> tuple[str, list[str]]:
    applied: list[str] = []
    # Replace longer expressions first so a place name such as 潮待市役所 is not
    # partially consumed by the shorter 潮待 replacement.
    for source in sorted(replacements, key=len, reverse=True):
        if source not in text:
            continue
        text = text.replace(source, replacements[source])
        applied.append(source)
    return text, applied


def create_query(engine_url: str, text: str, style_id: int) -> dict:
    params = urllib.parse.urlencode({"text": text, "speaker": style_id})
    query = request_json(f"{engine_url}/audio_query?{params}", data=b"", method="POST")
    if not isinstance(query, dict):
        raise RuntimeError("VOICEVOX /audio_query returned an unexpected response")

    # Calm automated-announcement voice, but not completely flat.
    query["speedScale"] = 0.95
    query["pitchScale"] = -0.02
    query["intonationScale"] = 0.42
    query["volumeScale"] = 0.92
    query["prePhonemeLength"] = 0.30
    query["postPhonemeLength"] = 0.44
    query["outputSamplingRate"] = 24000
    query["outputStereo"] = False
    return query


def process_radio_audio(wav_path: Path, mp3_path: Path) -> None:
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    audio_filter = (
        "highpass=f=180,"
        "lowpass=f=5800,"
        "acompressor=threshold=0.1:ratio=3:attack=20:release=250:makeup=1.5,"
        "alimiter=limit=0.90"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(wav_path),
            "-af",
            audio_filter,
            "-ar",
            "24000",
            "-ac",
            "1",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "64k",
            str(mp3_path),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(JST).date().isoformat())
    parser.add_argument("--engine-url", default=DEFAULT_ENGINE_URL)
    parser.add_argument("--voice-number", type=int, default=DEFAULT_VOICE_NUMBER)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    data = load_json(BROADCASTS_PATH)
    broadcast = next(
        (item for item in data.get("broadcasts", []) if item.get("date") == args.date),
        None,
    )
    if broadcast is None:
        raise RuntimeError(f"No broadcast found for {args.date}")

    output_path = AUDIO_DIR / f"{args.date}.mp3"
    if output_path.exists() and broadcast.get("audio") and not args.force:
        print(f"{args.date}: audio already exists")
        return 0

    source_text = str(broadcast.get("speech_text", broadcast["text"]))
    speech_text, applied_pronunciations = apply_pronunciations(
        source_text,
        load_pronunciations(broadcast),
    )
    if applied_pronunciations:
        print(f"{args.date}: pronunciation overrides: {', '.join(applied_pronunciations)}")

    style_id, voice_label = choose_nemo_voice(args.engine_url, args.voice_number)
    query = create_query(args.engine_url, speech_text, style_id)
    query_bytes = json.dumps(query, ensure_ascii=False).encode("utf-8")
    wav = request_bytes(
        f"{args.engine_url}/synthesis?speaker={style_id}",
        data=query_bytes,
    )

    with tempfile.TemporaryDirectory() as temporary_directory:
        wav_path = Path(temporary_directory) / "broadcast.wav"
        wav_path.write_bytes(wav)
        process_radio_audio(wav_path, output_path)

    broadcast["audio"] = output_path.relative_to(ROOT).as_posix()
    broadcast["voice"] = {
        "engine": "VOICEVOX Nemo",
        "number": args.voice_number,
        "style_id": style_id,
        "label": voice_label,
        "speed_scale": 0.95,
        "intonation_scale": 0.42,
        "processing": "fm-narrowband-v2",
        "pronunciation_overrides": applied_pronunciations,
    }
    data["updated_at"] = datetime.now(JST).isoformat(timespec="seconds")
    save_json(BROADCASTS_PATH, data)

    print(f"{args.date}: generated {output_path.relative_to(ROOT)} with {voice_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
