"""
LUCOST AI real worker (RunPod serverless handler).

Contract (same as the test worker, plus the real content):
  input: job_id, script, style, aspect_ratio, characters (JSON list of
         {name, image_url, voice_url, variations}), music, description, tier,
         subtitles, language, language_mode, resolution, chunk_index, chunk_count, gpu_count
  output: {"video_url": ..., "chunk_index": ...}  or  {"error": ...}

This worker handles one part of a video. The app splits the script and calls it once per part.
"""

import json
import os
import re
import subprocess
import tempfile
import urllib.request

import boto3
import imageio_ffmpeg
import runpod

import models

RESOLUTIONS = {"1920x1080": (1920, 1080), "1080x1080": (1080, 1080), "1080x1920": (1080, 1920)}
SILENCE_BETWEEN_LINES = 0.4  # seconds


def parse_lines(script: str):
    """Each dialogue line 'Name: words' becomes (speaker, words). Scene lines are kept as narration."""
    lines = []
    for raw in (script or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^([^:]{1,40}?)\s*:\s*(\S.*)$", line)
        if m and m.group(1).strip().lower() != "scene":
            lines.append((m.group(1).strip(), m.group(2).strip()))
        else:
            lines.append((None, line))  # scene or stage text, no speaker
    return lines


def _load_characters(raw):
    try:
        return json.loads(raw or "[]")
    except ValueError:
        return []


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _download(url: str, path: str):
    with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


def _ffmpeg(*args):
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + result.stderr[-300:])


def _r2():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY"],
        aws_secret_access_key=os.environ["R2_SECRET_KEY"],
        region_name="auto",
    )


def build_part(inp, tmp):
    """Make the video for this part. Returns the path of the finished MP4."""
    characters = {_norm(c.get("name")): c for c in _load_characters(inp.get("characters")) if isinstance(c, dict)}
    w, h = RESOLUTIONS.get(inp.get("resolution", "1920x1080"), (1920, 1080))
    clips = []
    for i, (speaker, text) in enumerate(parse_lines(inp.get("script", ""))):
        if speaker is None:
            continue  # scene text is not spoken or shown in this version
        card = characters.get(_norm(speaker))
        if not card:
            raise RuntimeError(f"No character card for {speaker}.")
        photo = _download(card["image_url"], os.path.join(tmp, f"face{i}.img"))
        snippet = _download(card["voice_url"], os.path.join(tmp, f"voice{i}.bin"))
        wav = models.synthesize_speech(text, snippet, inp.get("language", "English (US)"), os.path.join(tmp, f"line{i}.wav"))
        mp4 = models.animate_face(photo, wav, os.path.join(tmp, f"clip{i}.mp4"))
        clips.append(mp4)
    if not clips:
        raise RuntimeError("This part of the script has no spoken lines.")

    # Join the lines in order, scaled to the frame, with one encoder setting
    listfile = os.path.join(tmp, "list.txt")
    scaled = []
    for i, c in enumerate(clips):
        out = os.path.join(tmp, f"scaled{i}.mp4")
        _ffmpeg("-i", c, "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "2", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", out)
        scaled.append(out)
    with open(listfile, "w", encoding="utf-8") as f:
        for p in scaled:
            f.write("file '" + p + "'\n")
    final = os.path.join(tmp, "part.mp4")
    _ffmpeg("-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", "-movflags", "+faststart", final)
    return final


def handler(job):
    inp = job.get("input", {}) or {}
    job_id = inp.get("job_id", "test")
    part = int(inp.get("chunk_index", 0))
    try:
        models.ensure_ready()
        with tempfile.TemporaryDirectory() as tmp:
            path = build_part(inp, tmp)
            key = f"parts/{job_id}/part{part}.mp4"
            _r2().upload_file(path, os.environ["R2_BUCKET"], key, ExtraArgs={"ContentType": "video/mp4"})
        return {"video_url": f"{os.environ['R2_PUBLIC_URL'].rstrip('/')}/{key}", "chunk_index": part}
    except models.ModelNotConfigured as e:
        return {"error": str(e), "chunk_index": part}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
  
