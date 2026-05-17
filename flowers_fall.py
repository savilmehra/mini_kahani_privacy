"""
Devotional Video Agent — Fully Automated
==========================================
Pipeline:
  Stage 1 → Gemini generates prompt + metadata
  Stage 2 → OpenAI GPT Image Mini generates fine art image
  Stage 3 → Kie.ai animates image to video (with retry + FFmpeg fallback)
  Stage 3.5 → Convert 6sec to audio-length seamless loop locally
  Stage 4 → Add watermark via FFmpeg
  Stage 5 → Generate thumbnail
  Stage 6 → Add local theme-based audio (loop/trim to fit)
  Stage 7 → Upload to YouTube (specific channel)

CHANGES:
  - Video ratio: 3:2 (1080x720 landscape)
  - Video duration = audio file duration (auto-detected)
  - create_pro_animation_video updated for 3:2 ratio + audio-length
  - stage3_living_painting updated for 3:2 ratio + audio-length

Install:
    pip install pillow requests google-genai google-api-python-client google-auth-oauthlib openai
"""

import os
import time
import json
import math
import random
import base64
import pickle
import subprocess
import textwrap
import shutil
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

import requests
from openai import OpenAI
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import yt_dlp
import urllib.request
import tempfile
from lumaai import LumaAI
import cv2
import numpy as np
import argparse
from living_painting import animate as living_painting_animate
from stage3_particle_animation import stage3_particle_animation

# ─────────────────────────────────────────────────────────────
# VIDEO DIMENSIONS — 3:2 ratio (landscape)
# ─────────────────────────────────────────────────────────────
VIDEO_W = 1080
VIDEO_H = 720

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
LUMA_API_KEY        = ""
HF_TOKEN            = ""
GEMINI_API_KEY      = ""
KIE_API_KEY         = ""
IMGBB_API_KEY       = ""
YOUTUBE_CLIENT_FILE = "client_secrets.json"
TARGET_CHANNEL_ID   = ""
OPENAI_API_KEY      = ""
WATERMARK_TEXT      = "Savil"
TOKEN_FILE          = "youtube_token.pickle"

AUDIO_BASE_DIR      = r"C:\Users\savka\Documents\yOUTUBE AGENT\audio"

OUTPUT_IMAGE        = "god_image.png"
OUTPUT_VIDEO_RAW    = "god_video_raw.mp4"
OUTPUT_VIDEO_LOOPED = "god_video_looped.mp4"
OUTPUT_VIDEO_WM     = "god_video_watermarked.mp4"
OUTPUT_VIDEO_AUD    = "god_video_final.mp4"
OUTPUT_THUMBNAIL    = "thumbnail.jpg"

KIE_BASE = "https://api.kie.ai/api/v1"

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# ─────────────────────────────────────────────────────────────
# THEMES & COLORS
# ─────────────────────────────────────────────────────────────
THEMES = [
    "Hanuman dancing in divine joy with golden aura",
    "Hanuman carrying Sanjeevani mountain glowing with power",
    "Hanuman strength and devotion in fiery red sky",
    "Shiva cosmic meditation on Mount Kailash",
    "Shiva Tandava dance surrounded by fire and cosmos",
    "Neelkanth Shiva with glowing crescent moon and Ganga",
    "Sita Rama divine union under flower rain",
    "Krishna flute under moonlight with peacock feather crown",
    "Krishna Radha divine love in Vrindavan forest",
    "Bal Krishna with butter and divine mischief smile",
    "Ganesha festival celebration with marigold and modak",
    "Ganesha writing Mahabharata with golden quill",
    "Riddhi Siddhi Ganesha cosmic blessing pose",
    "Mata Durga trident strike against Mahishasura",
    "Durga Navratri form with ten arms and glowing weapons",
    "Sherawali Mata on white lion with crimson saree",
    "Lakshmi blessing moment with gold coins and lotus",
    "Dhanteras Lakshmi glowing with divine prosperity",
    "Lakshmi Vishnu cosmic divine couple on Sheshnag",
    "Saraswati wisdom and veena in white lotus throne",
    "Saraswati Vasant Panchami blessing students",
    "Saraswati divine knowledge with swan and peacock",
    "Kali Ma fierce warrior form with divine fire",
    "Parvati divine mother goddess with Uma and Kartikeya",
]

COLORS = [
    "maroon, mustard gold, ivory white",
    "crimson, saffron, antique gold",
    "midnight black, mustard gold, royal purple",
    "deep navy, saffron, silver",
    "peacock blue, mustard gold, maroon",
    "saffron orange, mustard gold, maroon red",
    "black, mustard gold, maroon crimson",
    "royal blue, mustard yellow, maroon gold",
    "lotus pink, mustard gold, deep maroon",
    "pure white, mustard saffron, maroon crimson",
]

SKIN_COLORS = [
    "pale ash white", "cool blue white", "deep cosmic blue",
    "warm golden saffron", "rich saffron orange", "soft lotus pink",
    "warm golden ivory", "pure pearl white", "deep obsidian black",
    "blazing golden orange", "warm earthy brown", "cool porcelain white",
]

MOON_COLORS = [
    "pure silver white", "warm golden yellow", "glowing emerald green",
    "deep sapphire blue", "pale ice blue", "blazing saffron orange",
    "deep blood red", "pale lavender pink", "soft blush rose",
]

THEME_AUDIO_FOLDER = {
    "Hanuman dancing in divine joy with golden aura":          "hanuman",
    "Hanuman carrying Sanjeevani mountain glowing with power": "hanuman",
    "Hanuman strength and devotion in fiery red sky":          "hanuman",
    "Shiva cosmic meditation on Mount Kailash":                "shiva",
    "Shiva Tandava dance surrounded by fire and cosmos":       "shiva",
    "Neelkanth Shiva with glowing crescent moon and Ganga":    "shiva",
    "Sita Rama divine union under flower rain":                "rama",
    "Krishna flute under moonlight with peacock feather crown":"krishna",
    "Krishna Radha divine love in Vrindavan forest":           "krishna",
    "Bal Krishna with butter and divine mischief smile":       "krishna",
    "Ganesha festival celebration with marigold and modak":    "ganesha",
    "Ganesha writing Mahabharata with golden quill":           "ganesha",
    "Riddhi Siddhi Ganesha cosmic blessing pose":              "ganesha",
    "Mata Durga trident strike against Mahishasura":           "durga",
    "Durga Navratri form with ten arms and glowing weapons":   "durga",
    "Sherawali Mata on white lion with crimson saree":         "durga",
    "Lakshmi blessing moment with gold coins and lotus":       "lakshmi",
    "Dhanteras Lakshmi glowing with divine prosperity":        "lakshmi",
    "Lakshmi Vishnu cosmic divine couple on Sheshnag":         "lakshmi",
    "Saraswati wisdom and veena in white lotus throne":        "saraswati",
    "Saraswati Vasant Panchami blessing students":             "saraswati",
    "Saraswati divine knowledge with swan and peacock":        "saraswati",
    "Kali Ma fierce warrior form with divine fire":            "durga",
    "Parvati divine mother goddess with Uma and Kartikeya":    "shiva",
}

LOOP_OPTIMIZED_VIDEO_PROMPTS = {
    "default": (
        "Hindu deity radiating divine light in sacred atmosphere, "
        "slow seamless loop, divine golden particles rising and falling in perfect cycle, "
        "sacred aura gently pulsing with warm celestial light, "
        "flower petals drifting slowly in continuous motion, "
        "motion starts and ends in identical state for seamless loop, "
        "cinematic slow motion 4K"
    )
}


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _get_video_duration(video_path: str) -> float:
    """Get video/audio duration in seconds using ffprobe."""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        video_path
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 30.0


def _cleanup(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
            print(f"  🧹 Temp file deleted: {path}")
    except Exception as e:
        print(f"  ⚠️  Could not delete temp file: {e}")


def get_audio_for_theme(theme: str) -> str:
    """Pick random local audio file based on theme. Returns local path."""
    folder_name = THEME_AUDIO_FOLDER.get(theme, "default")
    folder_path = os.path.join(AUDIO_BASE_DIR, folder_name)

    print(f"  🎵 Theme  : {theme}")
    print(f"  📂 Folder : {folder_path}")

    audio_files = []
    if os.path.exists(folder_path):
        audio_files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith((".mp3", ".wav", ".m4a", ".aac"))
        ]

    if not audio_files:
        print(f"  ⚠️  No audio in '{folder_name}' — trying default folder...")
        default_path = os.path.join(AUDIO_BASE_DIR, "default")
        if os.path.exists(default_path):
            audio_files = [
                os.path.join(default_path, f)
                for f in os.listdir(default_path)
                if f.lower().endswith((".mp3", ".wav", ".m4a", ".aac"))
            ]

    if not audio_files:
        raise Exception(
            f"No audio files found in '{folder_path}' or '{AUDIO_BASE_DIR}\\default\\' — "
            f"add .mp3 files to those folders first."
        )

    selected = random.choice(audio_files)
    print(f"  🎵 Selected: {os.path.basename(selected)}")
    return selected


def get_audio_duration_for_theme(theme: str) -> float:
    """
    Detect the duration of the audio file that will be used for this theme.
    Returns duration in seconds. Falls back to 30.0 if not found.
    """
    try:
        audio_path = get_audio_for_theme(theme)
        duration = _get_video_duration(audio_path)
        print(f"  🎵 Audio duration detected: {duration:.1f}s")
        return duration
    except Exception as e:
        print(f"  ⚠️  Could not detect audio duration: {e} — defaulting to 30s")
        return 30.0


def get_loop_prompt(theme: str, base_prompt: str) -> str:
    loop_suffix = (
        " The video must be perfectly seamless when looped — "
        "motion starts and ends in identical position and state, "
        "no visible jump cut when repeated, "
        "continuous breathing pulsing flowing motion only."
    )
    loop_prompt = LOOP_OPTIMIZED_VIDEO_PROMPTS.get(
        theme, LOOP_OPTIMIZED_VIDEO_PROMPTS["default"]
    )
    return loop_prompt + loop_suffix


# ─────────────────────────────────────────────────────────────
# STAGE 1 — Generate prompt + metadata via Gemini
# ─────────────────────────────────────────────────────────────

STYLE_SECTION = """
CRITICAL STYLE RULES — MUST FOLLOW EXACTLY:
Ultra detailed hyperrealistic digital painting, 8K resolution,
cinematic color grading, rich warm saturated, professional AAA concept art.
"""

def build_full_prompt(theme: str, color: str, skin: str, moon: str) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    return f"""You are a world-class AI art director and YouTube content strategist
specializing in Hindu devotional art.

Today is {today}. Your selected divine theme is: **{theme}**.

IMAGE PROMPT: A divine digital painting of {theme} in an elegant sitting pose,
glowing {color} {moon} behind head, wearing {color} dhoti, {skin} skin,
photo studio background, hyperrealistic painterly style, cinematic lighting,
highly detailed, 8K resolution.

OUTPUT FORMAT — respond ONLY in valid JSON, no markdown, no code fences:
{{
  "theme": "{theme}",
  "deity_name": "Primary deity name",
  "image_prompt": "Complete ultra-detailed prompt 80-120 words.",
  "video_prompt": "4-5 sentence seamless loop animation description, no zoom, deity stays centered, 4K 24fps.",
  "title": "YouTube title under 60 chars",
  "description": "YouTube description 200-250 chars ending with spiritual question",
  "thumbnail_hook": "MAX 6 WORDS ALL CAPS",
  "hashtags": "#devotional #divineart #hindugods #aiart #shorts #divine #spiritual",
  "tags": ["devotional", "divineart", "hindugods", "aiart", "divine", "spiritual"]
}}"""


def stage1_generate_metadata() -> dict:
    print("\n" + "="*50)
    print("[Stage 1] Generating metadata via Gemini...")
    print("="*50)

    client = genai.Client(api_key=GEMINI_API_KEY)
    theme  = "Shiva cosmic meditation on Mount Kailash"
    color  = random.choice(COLORS)
    skin   = random.choice(SKIN_COLORS)
    moon   = random.choice(MOON_COLORS)
    full_prompt = build_full_prompt(theme, color, skin, moon)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        print(f"  ✅ Theme : {data['theme']}")
        print(f"  ✅ Title : {data['title']}")
        return data

    except Exception as e:
        print(f"  ❌ Gemini failed: {e}")
        return {
            "theme":          theme,
            "deity_name":     "Hanuman",
            "image_prompt":   "Lord Hanuman glowing with divine power carrying Sanjeevani mountain",
            "video_prompt":   "Divine Hanuman glowing, seamless loop, golden aura pulsing, 4K",
            "title":          "Hanuman's Divine Power — Jai Bajrang Bali 🙏",
            "description":    "Feel Bajrang Bali's blessing. Can you feel his divine power? 🙏",
            "thumbnail_hook": "HANUMAN GLOWS WITH POWER",
            "hashtags":       "#hanuman #bajrangbali #devotional #aiart #divine",
            "tags":           ["hanuman", "bajrangbali", "devotional", "aiart", "divine"]
        }


# ─────────────────────────────────────────────────────────────
# STAGE 2 — Generate image via OpenAI GPT Image
# ─────────────────────────────────────────────────────────────

def stage2_generate_image(image_prompt: str) -> str:
    print("\n" + "="*50)
    print("[Stage 2] Generating image via OpenAI GPT Image...")
    print("="*50)

    client = OpenAI(api_key=OPENAI_API_KEY)
    print(f"  ⏳ Generating image with gpt-image-1...")

    img = client.images.generate(
        model="gpt-image-1",
        prompt=image_prompt,
        n=1,
        size="1536x1024"   # ← 3:2 landscape ratio
    )

    image_bytes = base64.b64decode(img.data[0].b64_json)
    with open(OUTPUT_IMAGE, "wb") as f:
        f.write(image_bytes)

    img_pil = Image.open(OUTPUT_IMAGE)
    img_pil = ImageEnhance.Brightness(img_pil).enhance(1.3)
    img_pil = ImageEnhance.Color(img_pil).enhance(1.4)
    img_pil = ImageEnhance.Contrast(img_pil).enhance(1.1)
    img_pil.save(OUTPUT_IMAGE, quality=98)

    size_kb = os.path.getsize(OUTPUT_IMAGE) // 1024
    print(f"  ✅ Image saved: {OUTPUT_IMAGE} ({size_kb} KB)")
    return OUTPUT_IMAGE


# ─────────────────────────────────────────────────────────────
# STAGE 3 — Animate image to video via Kie.ai
# ─────────────────────────────────────────────────────────────

def upload_image_to_imgbb(image_path: str) -> str:
    print(f"  📸 Uploading image to imgbb...")
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": image_data},
        timeout=30
    )
    resp.raise_for_status()
    url = resp.json()["data"]["url"]
    print(f"  ✅ Image URL: {url}")
    return url


def _kie_animate_kling30(image_path: str, video_prompt: str) -> str:
    print("  ⏳ Trying Kling 3.0 (pro mode)...")
    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json"
    }
    image_url = upload_image_to_imgbb(image_path)
    payload = {
        "model": "kling-3.0/video",
        "input": {
            "prompt":       video_prompt,
            "image_urls":   [image_url],
            "sound":        False,
            "duration":     "5",
            "aspect_ratio": "3:2",   # ← updated ratio
            "mode":         "pro",
            "multi_shots":  False
        }
    }
    response = requests.post(f"{KIE_BASE}/jobs/createTask", json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    resp_data = response.json()
    if resp_data.get("code") != 200 or not resp_data.get("data"):
        raise Exception(f"Kling 3.0 task failed: {resp_data.get('msg')}")
    task_id = resp_data["data"]["taskId"]
    print(f"  ✅ Kling 3.0 task submitted → ID: {task_id}")
    print("  ⏳ Waiting for Kling 3.0 video", end="", flush=True)
    for _ in range(60):
        time.sleep(10)
        print(".", end="", flush=True)
        status = requests.get(f"{KIE_BASE}/jobs/recordInfo", params={"taskId": task_id}, headers=headers, timeout=30).json()
        data  = status.get("data", {})
        state = data.get("state", "")
        if state == "success":
            result = json.loads(data.get("resultJson", "{}"))
            urls   = result.get("resultUrls", [])
            if not urls:
                raise Exception("No resultUrls in Kling 3.0 response")
            video_url = urls[0]
            print(f"\n  ✅ Kling 3.0 video ready!")
            break
        elif state == "fail":
            raise Exception(f"Kling 3.0 failed: {data.get('failMsg')}")
    else:
        raise TimeoutError("Kling 3.0 timed out after 10 minutes")
    video_bytes = requests.get(video_url, timeout=120).content
    with open(OUTPUT_VIDEO_RAW, "wb") as f:
        f.write(video_bytes)
    size_kb = os.path.getsize(OUTPUT_VIDEO_RAW) // 1024
    print(f"  ✅ Kling 3.0 video saved: {OUTPUT_VIDEO_RAW} ({size_kb} KB)")
    return OUTPUT_VIDEO_RAW


def _kie_animate_grok(image_path: str, video_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json"
    }
    image_url = upload_image_to_imgbb(image_path)
    payload = {
        "model": "grok-imagine/image-to-video",
        "input": {
            "task_id":    f"task_{int(time.time())}",
            "image_urls": [image_url],
            "prompt":     video_prompt,
            "mode":       "normal",
            "duration":   "6",
            "resolution": "720p"
        }
    }
    response = requests.post(f"{KIE_BASE}/jobs/createTask", json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    resp_data = response.json()
    if resp_data.get("code") != 200 or not resp_data.get("data"):
        raise Exception(f"grok-imagine failed: {resp_data.get('msg')}")
    task_id = resp_data["data"]["taskId"]
    print(f"  ✅ Task submitted → ID: {task_id}")
    print("  ⏳ Waiting for video", end="", flush=True)
    for _ in range(60):
        time.sleep(10)
        print(".", end="", flush=True)
        status = requests.get(f"{KIE_BASE}/jobs/recordInfo", params={"taskId": task_id}, headers=headers, timeout=30).json()
        data  = status.get("data", {})
        state = data.get("state", "")
        if state == "success":
            result = json.loads(data.get("resultJson", "{}"))
            urls   = result.get("resultUrls", [])
            if not urls:
                raise Exception("No resultUrls in response")
            video_url = urls[0]
            print(f"\n  ✅ Video ready!")
            break
        elif state == "fail":
            raise Exception(f"grok-imagine failed: {data.get('failMsg')}")
    else:
        raise TimeoutError("grok-imagine timed out")
    video_bytes = requests.get(video_url, timeout=120).content
    with open(OUTPUT_VIDEO_RAW, "wb") as f:
        f.write(video_bytes)
    size_kb = os.path.getsize(OUTPUT_VIDEO_RAW) // 1024
    print(f"  ✅ Video saved: {OUTPUT_VIDEO_RAW} ({size_kb} KB)")
    return OUTPUT_VIDEO_RAW


def _luma_animate(image_path: str, video_prompt: str) -> str:
    print("  ⏳ Trying Luma Dream Machine (Ray 2)...")
    client    = LumaAI(auth_token=LUMA_API_KEY)
    image_url = upload_image_to_imgbb(image_path)
    generation = client.generations.create(
        prompt=video_prompt,
        model="ray-2",
        aspect_ratio="3:2",   # ← updated ratio
        duration="5s",
        loop=False,
        keyframes={"frame0": {"type": "image", "url": image_url}},
    )
    print(f"  ✅ Luma task submitted → ID: {generation.id}")
    print("  ⏳ Waiting for Luma video", end="", flush=True)
    for _ in range(60):
        time.sleep(10)
        print(".", end="", flush=True)
        generation = client.generations.get(id=generation.id)
        if generation.state == "completed":
            video_url = generation.assets.video
            if not video_url:
                raise Exception("Luma completed but no video asset found")
            print(f"\n  ✅ Luma video ready!")
            break
        elif generation.state == "failed":
            raise Exception(f"Luma failed: {generation.failure_reason}")
    else:
        raise TimeoutError("Luma timed out after 10 minutes")
    video_bytes = requests.get(video_url, timeout=120).content
    with open(OUTPUT_VIDEO_RAW, "wb") as f:
        f.write(video_bytes)
    size_kb = os.path.getsize(OUTPUT_VIDEO_RAW) // 1024
    print(f"  ✅ Luma video saved: {OUTPUT_VIDEO_RAW} ({size_kb} KB)")
    return OUTPUT_VIDEO_RAW


def _ffmpeg_animate(image_path: str, duration: float = 30.0) -> str:
    """FFmpeg static hold — 3:2 ratio, no crop."""
    print("  ⏳ Creating video with FFmpeg (static hold)...")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-vf", (
            f"scale={VIDEO_W}:{VIDEO_H}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_W}:{VIDEO_H}:"
            f"(ow-iw)/2:(oh-ih)/2:"
            f"color=black,"
            f"setsar=1"
        ),
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-r", "24",
        "-pix_fmt", "yuv420p",
        "-an",
        OUTPUT_VIDEO_RAW
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg failed: {result.stderr[-300:]}")
    size_kb = os.path.getsize(OUTPUT_VIDEO_RAW) // 1024
    print(f"  ✅ FFmpeg video: {OUTPUT_VIDEO_RAW} ({size_kb} KB)")
    return OUTPUT_VIDEO_RAW


def stage3_animate_video(image_path: str, video_prompt: str, duration: float = 30.0) -> str:
    print("\n" + "="*50)
    print("[Stage 3] Animating image to video...")
    print("="*50)

    for attempt in range(1, 3):
        try:
            print(f"\n  [Method 1] Kling 3.0 — attempt {attempt}/2")
            return _kie_animate_kling30(image_path, video_prompt)
        except Exception as e:
            print(f"  ❌ Kling 3.0 attempt {attempt} failed: {e}")
            if attempt < 2:
                time.sleep(20)

    for attempt in range(1, 3):
        try:
            print(f"\n  [Method 2] grok-imagine — attempt {attempt}/2")
            return _kie_animate_grok(image_path, video_prompt)
        except Exception as e:
            print(f"  ❌ grok-imagine attempt {attempt} failed: {e}")
            if attempt < 2:
                time.sleep(20)

    for attempt in range(1, 3):
        try:
            print(f"\n  [Method 3] Luma Dream Machine — attempt {attempt}/2")
            return _luma_animate(image_path, video_prompt)
        except Exception as e:
            print(f"  ❌ Luma attempt {attempt} failed: {e}")
            if attempt < 2:
                time.sleep(20)

    print("\n  [Method 4] FFmpeg local fallback...")
    return _ffmpeg_animate(image_path, duration)


def stage35_create_loop_video(video_path: str, target_duration: float) -> str:
    """Loop/extend video to match audio duration exactly."""
    print("\n" + "="*50)
    print(f"[Stage 3.5] Creating seamless {target_duration:.1f}s video...")
    print("="*50)

    input_duration = _get_video_duration(video_path)
    loops_needed   = math.ceil(target_duration / input_duration) + 1

    print(f"  📽️  Input duration : {input_duration:.2f}s")
    print(f"  🎯 Target duration : {target_duration:.1f}s")
    print(f"  🔁 Loops needed    : {loops_needed}x")

    output_path = OUTPUT_VIDEO_LOOPED
    concat_file = os.path.join(os.path.dirname(os.path.abspath(video_path)), "concat_list.txt")
    abs_video   = os.path.abspath(video_path)

    with open(concat_file, "w", encoding="utf-8") as f:
        for _ in range(loops_needed):
            f.write(f"file '{abs_video}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-t", str(target_duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-vf", f"fps=24,scale={VIDEO_W}:{VIDEO_H},setsar=1",
        "-pix_fmt", "yuv420p",
        "-an",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    try:
        os.remove(concat_file)
    except:
        pass

    if result.returncode != 0:
        raise Exception(f"Loop failed: {result.stderr[-300:]}")

    duration = _get_video_duration(output_path)
    print(f"  ✅ Looped video: {output_path} ({duration:.1f}s)")
    return output_path


# ─────────────────────────────────────────────────────────────
# STAGE 3 (ALT) — Living Painting
# ─────────────────────────────────────────────────────────────

def stage3_living_painting(
        image_file,
        output_path  = "living_painting.mp4",
        colors       = None,
        duration     = None,       # ← None = auto-detect from audio
        fps          = 30,
        width        = VIDEO_W,    # ← 3:2: 1080px wide
        amplitude    = 10.0,
        parallax     = 8.0,
        frequency    = 0.042,
        dilate       = 3,
        blur         = 25,
        preview_mask = False,
        theme        = None,       # ← pass theme to auto-detect audio duration
):
    # Auto-detect duration from audio if not specified
    if duration is None:
        if theme:
            duration = get_audio_duration_for_theme(theme)
        else:
            duration = 30.0
        print(f"  🎬 Video duration set to audio length: {duration:.1f}s")

    args = argparse.Namespace(
        image        = image_file,
        colors       = colors or ["gold", "hair", "orange", "yellow"],
        output       = output_path,
        width        = width,
        frames       = int(duration * fps),
        fps          = fps,
        amplitude    = amplitude,
        frequency    = frequency,
        parallax     = parallax,
        dilate       = dilate,
        blur         = blur,
        preview_mask = preview_mask,
    )
    living_painting_animate(args)
    return output_path


# ─────────────────────────────────────────────────────────────
# STAGE 3 (ALT) — Pro Animation (updated for 3:2 + audio duration)
# ─────────────────────────────────────────────────────────────

def create_pro_animation_video(
        image_path: str,
        output_path: str = "pro_animation.mp4",
        duration: float  = None,   # ← None = auto-detect from audio
        effect: str      = "auto",
        theme: str       = None,   # ← pass theme for audio duration detection
) -> str:
    """
    Professional cinematic image animation engine — 3:2 ratio (1080x720).
    Duration auto-matches audio file length when theme is provided.

    Effects:
      "ken_burns"       — Slow cinematic zoom + pan
      "breathe"         — Gentle scale pulse
      "parallax"        — Depth layers move at different speeds
      "light_rays"      — God rays sweep across the frame
      "particle_ascent" — Golden particles float upward
      "ripple_warp"     — Subtle water ripple distortion
      "vignette_pulse"  — Vignette breathes in/out
      "combo"           — Ken Burns + particles + light rays (most premium)
      "auto"            — Picks best effect based on image filename
    """
    # ─── Auto-detect duration from audio ──────────────────────────
    if duration is None:
        if theme:
            duration = get_audio_duration_for_theme(theme)
        else:
            duration = 30.0
        print(f"  🎬 Video duration set to audio length: {duration:.1f}s")

    print("\n" + "="*60)
    print(f"[Pro Animation] Effect: {effect} | Duration: {duration:.1f}s | Ratio: 3:2 ({VIDEO_W}x{VIDEO_H})")
    print("="*60)

    # ─── Setup ────────────────────────────────────────────────────
    try:
        base_pil = Image.open(image_path).convert("RGBA")
        # Force 3:2 ratio
        base_pil = base_pil.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
        img_w, img_h = VIDEO_W, VIDEO_H
    except Exception as e:
        raise Exception(f"Cannot open image: {e}")

    FPS          = 30
    total_frames = int(duration * FPS)
    frames_dir   = "pro_anim_frames"
    os.makedirs(frames_dir, exist_ok=True)

    # ─── Auto-select effect ───────────────────────────────────────
    if effect == "auto":
        name = os.path.basename(image_path).lower()
        if any(k in name for k in ["krishna", "flute", "radha"]):
            effect = "particle_ascent"
        elif any(k in name for k in ["shiva", "kailash", "cosmic"]):
            effect = "light_rays"
        elif any(k in name for k in ["durga", "kali", "warrior"]):
            effect = "vignette_pulse"
        elif any(k in name for k in ["lakshmi", "ganesha", "blessing"]):
            effect = "combo"
        else:
            effect = "combo"
        print(f"  🎯 Auto-selected effect: {effect}")

    # ══════════════════════════════════════════════════════════════
    # EFFECT RENDERERS
    # ══════════════════════════════════════════════════════════════

    def ease_sin(t, cycles=1):
        return (math.sin(t * 2 * math.pi * cycles)) / 2 + 0.5

    def apply_ken_burns(frame_idx):
        t      = frame_idx / total_frames
        scale  = 1.0 + 0.18 * t
        pan_x  = int(img_w * 0.02 * math.sin(t * math.pi))
        pan_y  = int(img_h * 0.01 * t)
        new_w  = int(img_w * scale)
        new_h  = int(img_h * scale)
        scaled = base_pil.resize((new_w, new_h), Image.LANCZOS)
        left   = max(0, min((new_w - img_w) // 2 + pan_x, new_w - img_w))
        top    = max(0, min((new_h - img_h) // 2 + pan_y, new_h - img_h))
        return scaled.crop((left, top, left + img_w, top + img_h))

    def apply_breathe(frame_idx):
        t      = frame_idx / total_frames
        scale  = 1.0 + 0.06 * ease_sin(t, cycles=0.4 * duration)
        new_w  = int(img_w * scale)
        new_h  = int(img_h * scale)
        scaled = base_pil.resize((new_w, new_h), Image.LANCZOS)
        left   = (new_w - img_w) // 2
        top    = (new_h - img_h) // 2
        return scaled.crop((left, top, left + img_w, top + img_h))

    def apply_light_rays(frame_idx, base_frame):
        t       = frame_idx / total_frames
        overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)
        num_rays   = 8
        ray_origin = (img_w // 2, int(img_h * 0.05))
        for i in range(num_rays):
            angle_base = math.radians(-60 + i * 18)
            sweep      = math.radians(8 * math.sin(t * 2 * math.pi + i * 0.7))
            angle      = angle_base + sweep
            ray_len    = img_h * 1.6
            end_x      = int(ray_origin[0] + ray_len * math.sin(angle))
            end_y      = int(ray_origin[1] + ray_len * math.cos(angle))
            brightness = int(28 * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 0.3 + i)))
            ray_width  = random.randint(18, 55)
            draw.line([ray_origin, (end_x, end_y)], fill=(255, 240, 180, brightness), width=ray_width)
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=22))
        return Image.alpha_composite(base_frame.convert("RGBA"), overlay)

    random.seed(42)
    particles = []
    for _ in range(220):
        particles.append({
            "x":       random.uniform(0, img_w),
            "y":       random.uniform(0, img_h),
            "speed":   random.uniform(40, 140),
            "size":    random.uniform(1.5, 5.0),
            "alpha":   random.randint(80, 200),
            "drift":   random.uniform(-15, 15),
            "twinkle": random.uniform(0, 2 * math.pi),
            "color":   random.choice([
                (255, 215, 80), (255, 240, 160), (255, 180, 60),
                (255, 255, 200), (200, 255, 220),
            ])
        })

    def apply_particle_ascent(frame_idx, base_frame):
        t       = frame_idx / FPS
        overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)
        for p in particles:
            y_pos = (p["y"] - t * p["speed"]) % img_h
            x_pos = (p["x"] + p["drift"] * math.sin(t * 0.8 + p["twinkle"])) % img_w
            twinkle_alpha = int(p["alpha"] * (0.5 + 0.5 * math.sin(t * 3.0 + p["twinkle"])))
            twinkle_alpha = max(0, min(255, twinkle_alpha))
            s  = p["size"]
            r, g, b = p["color"]
            draw.ellipse([int(x_pos-s), int(y_pos-s), int(x_pos+s), int(y_pos+s)],
                         fill=(r, g, b, twinkle_alpha))
            if s > 3.5:
                cross_alpha = twinkle_alpha // 2
                draw.line([(int(x_pos)-4, int(y_pos)), (int(x_pos)+4, int(y_pos))],
                          fill=(255, 255, 220, cross_alpha), width=1)
                draw.line([(int(x_pos), int(y_pos)-4), (int(x_pos), int(y_pos)+4)],
                          fill=(255, 255, 220, cross_alpha), width=1)
        return Image.alpha_composite(base_frame.convert("RGBA"), overlay)

    def apply_ripple_warp(frame_idx):
        t     = frame_idx / FPS
        amp   = 4.0
        freq  = 0.012
        speed = 1.8
        h, w  = img_h, img_w
        y_coords = np.arange(h).reshape(-1, 1).astype(np.float32)
        x_coords = np.arange(w).reshape(1, -1).astype(np.float32)
        dx = amp * np.sin(2 * np.pi * (y_coords * freq + t * speed))
        dy = amp * np.sin(2 * np.pi * (x_coords * freq + t * speed * 0.7))
        map_x = np.clip((x_coords + dx).astype(np.float32), 0, w - 1)
        map_y = np.clip((y_coords + dy).astype(np.float32), 0, h - 1)
        warped = cv2.remap(np.array(base_pil.convert("RGB")), map_x, map_y,
                           interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        return Image.fromarray(warped).convert("RGBA")

    def apply_vignette_pulse(frame_idx, base_frame):
        t       = frame_idx / total_frames
        vig_str = 0.55 + 0.20 * math.sin(t * 2 * math.pi * 0.5)
        warm_bias = int(12 * math.sin(t * 2 * math.pi * 0.3))
        overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)
        for i in range(14):
            ratio   = i / 14
            pad_x   = int(img_w * 0.5 * (1 - ratio) * vig_str)
            pad_y   = int(img_h * 0.5 * (1 - ratio) * vig_str)
            alpha_v = int(55 * (1 - ratio) ** 2)
            bbox    = [pad_x, pad_y, img_w - pad_x, img_h - pad_y]
            line_w  = max(1, int(img_w * 0.05 * (1 - ratio)))
            draw.ellipse(bbox, outline=(0, 0, 20, alpha_v), width=line_w)
        result = Image.alpha_composite(base_frame.convert("RGBA"), overlay)
        r, g, b, a = result.split()
        r = r.point(lambda x: min(255, x + warm_bias))
        b = b.point(lambda x: max(0, x - warm_bias // 2))
        return Image.merge("RGBA", (r, g, b, a))

    def apply_parallax(frame_idx):
        t       = frame_idx / total_frames
        shift_x = int(img_w * 0.025 * math.sin(t * 2 * math.pi * 0.3))
        shift_y = int(img_h * 0.010 * math.sin(t * 2 * math.pi * 0.2))
        result  = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 255))
        bg_region  = base_pil.crop((0, img_h//2, img_w, img_h))
        result.paste(bg_region, (0, img_h//2))
        mid_region = base_pil.crop((0, img_h//5, img_w, img_h*3//4))
        mid_canvas = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        mid_canvas.paste(mid_region, (shift_x // 2, img_h//5))
        result     = Image.alpha_composite(result, mid_canvas)
        fg_region  = base_pil.crop((0, 0, img_w, img_h*2//5))
        fg_canvas  = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        fg_canvas.paste(fg_region, (shift_x, shift_y))
        result     = Image.alpha_composite(result, fg_canvas)
        return result

    # ─── Render all frames ─────────────────────────────────────────
    print(f"  🎬 Rendering {total_frames} frames ({FPS}fps, {duration:.1f}s, {VIDEO_W}x{VIDEO_H})...")

    for f in range(total_frames):
        t = f / total_frames

        if effect in ("ken_burns", "combo"):
            base_frame = apply_ken_burns(f)
        elif effect == "breathe":
            base_frame = apply_breathe(f)
        elif effect == "ripple_warp":
            base_frame = apply_ripple_warp(f)
        elif effect == "parallax":
            base_frame = apply_parallax(f)
        else:
            base_frame = base_pil.copy()

        base_frame = base_frame.convert("RGBA")

        if effect in ("light_rays", "combo"):
            base_frame = apply_light_rays(f, base_frame)

        if effect in ("particle_ascent", "combo"):
            base_frame = apply_particle_ascent(f, base_frame)

        if effect == "vignette_pulse":
            base_frame = apply_vignette_pulse(f, base_frame)

        # Global cinematic grade
        brightness_factor = 0.92 + 0.08 * math.sin(t * 2 * math.pi * 0.25)
        graded = ImageEnhance.Brightness(base_frame.convert("RGB")).enhance(brightness_factor)
        graded = ImageEnhance.Contrast(graded).enhance(1.08)
        graded = ImageEnhance.Color(graded).enhance(1.12)

        frame_path = os.path.join(frames_dir, f"frame_{f:04d}.png")
        graded.convert("RGB").save(frame_path, format="PNG")

        if f % 150 == 0:
            print(f"    [{int(f/total_frames*100):3d}%] Frame {f}/{total_frames}")

    print("  ✅ All frames rendered")

    # ─── Encode via FFmpeg ─────────────────────────────────────────
    print("  🎞️  Encoding video with FFmpeg...")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-vf", (
            f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H}:(iw-{VIDEO_W})/2:(ih-{VIDEO_H})/2,"
            f"setsar=1"
        ),
        "-c:v",     "libx264",
        "-preset",  "slow",
        "-crf",     "16",
        "-r",       str(FPS),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        output_path
    ]
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

    try:
        shutil.rmtree(frames_dir)
        print("  🧹 Frames cleaned up")
    except Exception as e:
        print(f"  ⚠️  Cleanup failed: {e}")

    if result.returncode != 0:
        print(f"  ❌ FFmpeg error:\n{result.stderr[-600:]}")
        raise Exception(f"Pro animation failed: {result.stderr[-200:]}")

    size_mb   = os.path.getsize(output_path) / (1024 * 1024)
    final_dur = _get_video_duration(output_path)
    print(f"  ✅ Pro animation done: {output_path} ({final_dur:.1f}s, {size_mb:.1f} MB, {VIDEO_W}x{VIDEO_H})")
    return output_path


# ─────────────────────────────────────────────────────────────
# STAGE 4 — Add watermark
# ─────────────────────────────────────────────────────────────

def stage4_add_watermark(video_path: str) -> str:
    print("\n" + "="*50)
    print(f"[Stage 4] Adding watermark: '{WATERMARK_TEXT}'...")
    print("="*50)

    safe_text = WATERMARK_TEXT.replace("'", "\u2019").replace(":", "\\:")
    font_path = "C\\:/Windows/Fonts/impact.ttf"

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", (
            f"drawtext=fontfile='{font_path}':"
            f"text='{safe_text}':"
            f"fontcolor=white@0.6:"
            f"fontsize=28:"
            f"x=w-tw-20:y=h-th-20:"
            f"shadowcolor=black@0.6:shadowx=2:shadowy=2:"
            f"box=1:boxcolor=black@0.3:boxborderw=6"
        ),
        "-codec:a", "copy",
        OUTPUT_VIDEO_WM
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️  Watermark failed — using original: {result.stderr[-200:]}")
        return video_path

    print(f"  ✅ Watermarked: {OUTPUT_VIDEO_WM}")
    return OUTPUT_VIDEO_WM


# ─────────────────────────────────────────────────────────────
# STAGE 5 — Generate thumbnail (3:2 ratio: 1080x720)
# ─────────────────────────────────────────────────────────────

def stage5_generate_thumbnail(video_path: str, hook_text: str, title: str) -> str:
    print("\n" + "="*50)
    print("[Stage 5] Generating thumbnail (3:2 ratio)...")
    print("="*50)

    THUMB_W, THUMB_H = VIDEO_W, VIDEO_H   # 1080x720 for 3:2

    frame_path = "thumb_frame.jpg"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-ss", "00:00:01", "-vframes", "1",
        "-q:v", "2", f"-vf", f"scale={THUMB_W}:{THUMB_H}",
        frame_path
    ], capture_output=True)

    if not os.path.exists(frame_path):
        print("  ⚠️  Frame extract failed — using generated image")
        img = Image.open(OUTPUT_IMAGE).convert("RGB").resize((THUMB_W, THUMB_H))
    else:
        img = Image.open(frame_path).convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS)

    img = ImageEnhance.Brightness(img).enhance(0.65)
    img = ImageEnhance.Contrast(img).enhance(1.4)
    img = ImageEnhance.Color(img).enhance(0.8)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 80))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    fade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_fade = ImageDraw.Draw(fade)
    for y in range(img.height):
        alpha = int(180 * (y / img.height) ** 2)
        draw_fade.line([(0, y), (img.width, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), fade).convert("RGB")

    draw = ImageDraw.Draw(img)
    W, H = img.size

    def load_font(path, size):
        try:
            return ImageFont.truetype(path, size)
        except:
            return ImageFont.load_default()

    # Smaller font sizes for landscape 720px height
    hook_font  = load_font(r"C:\Windows\Fonts\impact.ttf", 80)
    title_font = load_font(r"C:\Windows\Fonts\arialbd.ttf", 36)
    wm_font    = load_font(r"C:\Windows\Fonts\arialbd.ttf", 24)

    hook_clean  = hook_text.upper().strip()
    wrapped     = textwrap.fill(hook_clean, width=20)   # wider wrap for landscape
    lines       = wrapped.split("\n")
    line_height = 95
    total_h     = len(lines) * line_height
    y_start     = (H // 2) - (total_h // 2) - 60

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        tw   = bbox[2] - bbox[0]
        x    = (W - tw) // 2
        y    = y_start + (i * line_height)
        for dx, dy in [(-4,0),(4,0),(0,-4),(0,4),(-3,-3),(3,3)]:
            draw.text((x+dx, y+dy), line, font=hook_font, fill=(220, 140, 0))
        draw.text((x+3, y+3), line, font=hook_font, fill=(0, 0, 0))
        draw.text((x, y),     line, font=hook_font, fill=(255, 255, 255))

    short_title = title[:55] + ("..." if len(title) > 55 else "")
    bbox = draw.textbbox((0, 0), short_title, font=title_font)
    tw   = bbox[2] - bbox[0]
    tx   = (W - tw) // 2
    draw.text((tx+2, H-80+2), short_title, font=title_font, fill=(0, 0, 0))
    draw.text((tx,   H-80),   short_title, font=title_font, fill=(255, 220, 0))

    bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=wm_font)
    tw   = bbox[2] - bbox[0]
    draw.text((W-tw-18+2, 18+2), WATERMARK_TEXT, font=wm_font, fill=(0, 0, 0))
    draw.text((W-tw-18,   18),   WATERMARK_TEXT, font=wm_font, fill=(255, 255, 255))

    img.save(OUTPUT_THUMBNAIL, quality=95)
    print(f"  ✅ Thumbnail saved: {OUTPUT_THUMBNAIL} ({THUMB_W}x{THUMB_H})")
    return OUTPUT_THUMBNAIL


# ─────────────────────────────────────────────────────────────
# STAGE 6 — Add local theme-based audio
# ─────────────────────────────────────────────────────────────

def stage6_add_audio(video_path: str, theme: str) -> str:
    print("\n" + "="*50)
    print("[Stage 6] Adding local theme-based audio...")
    print("="*50)

    try:
        audio_path = get_audio_for_theme(theme)
    except Exception as e:
        print(f"  ⚠️  {e} — skipping audio")
        return video_path

    video_duration = _get_video_duration(video_path)
    audio_duration = _get_video_duration(audio_path)
    fade_out_start = max(0, video_duration - 2)

    print(f"  🎬 Video duration : {video_duration:.1f}s")
    print(f"  🎵 Audio duration : {audio_duration:.1f}s")

    if audio_duration < video_duration:
        loops_needed = int(video_duration / audio_duration) + 2
        print(f"  🔁 Audio shorter — looping {loops_needed}x then trimming...")
        audio_filter = (
            f"[1:a]"
            f"aloop=loop={loops_needed}:size=2e+09,"
            f"atrim=0:{video_duration},"
            f"afade=t=in:st=0:d=1,"
            f"afade=t=out:st={fade_out_start}:d=2,"
            f"asetpts=PTS-STARTPTS[aout]"
        )
    else:
        print(f"  ✂️  Audio longer — trimming to {video_duration:.1f}s...")
        audio_filter = (
            f"[1:a]"
            f"atrim=0:{video_duration},"
            f"afade=t=in:st=0:d=1,"
            f"afade=t=out:st={fade_out_start}:d=2,"
            f"asetpts=PTS-STARTPTS[aout]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex", audio_filter,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-t", str(video_duration),
        OUTPUT_VIDEO_AUD
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️  Audio filter failed — trying simple add...")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-stream_loop", "-1",
            "-i", audio_path,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy",
            "-t", str(video_duration),
            "-shortest",
            OUTPUT_VIDEO_AUD
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("  ⚠️  Audio failed — returning video without audio")
            return video_path

    size_kb   = os.path.getsize(OUTPUT_VIDEO_AUD) // 1024
    final_dur = _get_video_duration(OUTPUT_VIDEO_AUD)
    print(f"  ✅ Final video: {OUTPUT_VIDEO_AUD} ({final_dur:.1f}s, {size_kb} KB)")
    return OUTPUT_VIDEO_AUD


# ─────────────────────────────────────────────────────────────
# STAGE 7 — Upload to YouTube
# ─────────────────────────────────────────────────────────────

def get_youtube_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_FILE, YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)


def stage7_upload_youtube(video_file: str, metadata: dict, thumbnail_path: str) -> str:
    print("\n" + "="*50)
    print("[Stage 7] Uploading to YouTube...")
    print("="*50)

    youtube = get_youtube_service()
    channels_resp = youtube.channels().list(part="snippet", mine=True).execute()
    available_channels = channels_resp.get("items", [])
    target_found = False
    print("  📺 Available channels:")
    for ch in available_channels:
        ch_id   = ch["id"]
        ch_name = ch["snippet"]["title"]
        marker  = "← TARGET ✅" if ch_id == TARGET_CHANNEL_ID else ""
        print(f"     {ch_name} | {ch_id} {marker}")
        if ch_id == TARGET_CHANNEL_ID:
            target_found = True

    if not target_found:
        raise Exception(f"Target channel {TARGET_CHANNEL_ID} not found!")

    hashtags    = metadata.get("hashtags", "#devotional #divine")
    description = metadata["description"] + "\n\n" + hashtags + "\n\n#Reels"

    body = {
        "snippet": {
            "title":       metadata["title"],
            "description": description,
            "tags":        metadata["tags"],
            "categoryId":  "22",
            "channelId":   TARGET_CHANNEL_ID,
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
        }
    }

    media   = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload: {int(status.progress() * 100)}%")

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  ✅ Uploaded → {url}")

    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId    = video_id,
                media_body = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            ).execute()
            print("  ✅ Thumbnail set")
        except Exception as e:
            print(f"  ⚠️  Thumbnail failed: {e}")

    return url


# ─────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────

def run_agent():
    print("\n" + "█"*50)
    print("   DEVOTIONAL VIDEO AGENT — Auto Run")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Video ratio: 3:2 ({VIDEO_W}x{VIDEO_H})")
    print(f"   Duration: matches audio file length")
    print("█"*50)

    try:
        # Stage 1 — Generate prompt + metadata
        #metadata = stage1_generate_metadata()
        metadata=""


        # Stage 2 — Generate fine art image (3:2 → 1536x1024)
        # image_file = stage2_generate_image(metadata["image_prompt"])
        image_file = r"C:\Users\savka\Documents\yOUTUBE AGENT\6.png"


        # Stage 3 — Animate (choose ONE method below)

        # Option A: Living Painting (hair/cloth ripple cinemagraph)
        video_file = stage3_particle_animation(
            image_file,
            output_path   = "god_video.mp4",
            color         = "blue",          # match your image's flower color
            direction     = "down",          # "down" or "up"
            source_region = (0.0, 0.42),     # top 42% = where the flowers are
            duration      = 30,  # ← automatically matches audio length
            fps           = 60,
            particles     = 50,
            speed         = 0.5,
            fade          = 0.15,
        )

        # Option B: Pro Animation (ken_burns / combo / light_rays etc.)
        #  video_file = create_pro_animation_video(
        #    image_file,
        #   output_path = "god_video.mp4",
        #   duration    = audio_duration,    # ← matches audio
        #   effect      = "auto",
        #  theme       = metadata["theme"],
        #)

        # Stage 4 — Add watermark
        #  video_file = stage4_add_watermark(video_file)

        # Stage 5 — Generate thumbnail
        thumbnail = stage5_generate_thumbnail(
            video_path = video_file,
            hook_text  = metadata["thumbnail_hook"],
            title      = metadata["title"]
        )

        # Stage 6 — Add devotional audio
        # video_file = stage6_add_audio(video_file, metadata["theme"])

        # Stage 7 — Upload to YouTube
       # youtube_url = stage7_upload_youtube(video_file, metadata, thumbnail)
        youtube_url = ""   # ← comment above and uncomment this to skip upload

        # Log success
        log = {
            "date":        datetime.now().isoformat(),
            "theme":       metadata["theme"],
            "title":       metadata["title"],
            "hook":        metadata["thumbnail_hook"],
            "youtube_url": youtube_url,
            "video_size":  f"{VIDEO_W}x{VIDEO_H}",
            "status":      "success"
        }
        with open("agent_log.json", "a") as f:
            f.write(json.dumps(log) + "\n")

        print("\n" + "█"*50)
        print("  ✅ DONE!")
        print(f"  🎬 Watch → {youtube_url}")
        print("█"*50)

    except Exception as e:
        print(f"\n  ❌ Agent failed: {e}")
        with open("agent_log.json", "a") as f:
            f.write(json.dumps({
                "date":   datetime.now().isoformat(),
                "status": "failed",
                "error":  str(e)
            }) + "\n")
        raise


if __name__ == "__main__":
    run_agent()

    # ── Quick config reminders ─────────────────────────────────────
    # step 1: change theme in stage1_generate_metadata() line ~220
    # step 2: add audio mp3 files to AUDIO_BASE_DIR subfolders
    # step 3: comment/uncomment Option A or Option B in run_agent()
    # step 4: set youtube_url = "" to skip upload during testing