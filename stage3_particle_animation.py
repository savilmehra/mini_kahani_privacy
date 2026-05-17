"""
stage3_particle_animation.py
============================
Drop-in replacement for stage3_living_painting() in the devotional video agent.
Uses particle_animation_v3 logic — extracts real colored objects from the image
and animates them falling or rising in a seamlessly looping video.

USAGE in run_agent():
    from stage3_particle_animation import stage3_particle_animation

    video_file = stage3_particle_animation(
        image_file,
        output_path    = "god_video.mp4",
        color          = "pink",          # preset OR custom "h_lo,h_hi,s_lo,s_hi,v_lo,v_hi"
        direction      = "down",          # "down" or "up"
        source_region  = (0.0, 0.42),     # Y fraction of image to extract objects from
        duration       = audio_duration,  # seconds — pass audio_duration to match audio
        fps            = 30,
        particles      = 80,              # number of falling particles
        speed          = 1.0,             # 0.3=slow dreamy, 1.0=normal, 2.0=fast
        fade           = 0.12,            # edge fade for seamless loop (0.0–0.3)
    )
"""

import cv2
import numpy as np
import random
import math
import subprocess
import shutil
import sys
from pathlib import Path


# ── Color presets ─────────────────────────────────────────────────────────────
COLOR_PRESETS = {
    "gold":   (13,  36,  80,  255, 140, 255),
    "yellow": (20,  35,  80,  255, 100, 255),
    "blue":   (95,  135, 80,  255, 55,  255),
    "red":    (0,   10,  80,  255, 60,  255),
    "red2":   (160, 180, 80,  255, 60,  255),
    "green":  (40,  85,  60,  255, 40,  255),
    "white":  (0,   180, 0,   40,  200, 255),
    "pink":   (140, 175, 50,  255, 100, 255),
    "orange": (10,  25,  100, 255, 100, 255),
    "purple": (125, 155, 50,  255, 50,  255),
    "cyan":   (80,  100, 80,  255, 80,  255),
}


def _hsv_bounds(color: str):
    """Return (lo, hi, extra_lo, extra_hi) numpy arrays for HSV masking."""
    extra_lo = extra_hi = None
    if "," in color:
        v = [int(x) for x in color.split(",")]
        if len(v) != 6:
            raise ValueError("Custom color must be 6 ints: h_lo,h_hi,s_lo,s_hi,v_lo,v_hi")
        lo = np.array([v[0], v[2], v[4]])
        hi = np.array([v[1], v[3], v[5]])
    else:
        name = color.lower()
        if name not in COLOR_PRESETS:
            raise ValueError(f"Unknown color '{color}'. Options: {list(COLOR_PRESETS.keys())}")
        pr = COLOR_PRESETS[name]
        lo = np.array([pr[0], pr[2], pr[4]])
        hi = np.array([pr[1], pr[3], pr[5]])
        if name == "red":   # red wraps around hue 0/180
            pr2 = COLOR_PRESETS["red2"]
            extra_lo = np.array([pr2[0], pr2[2], pr2[4]])
            extra_hi = np.array([pr2[1], pr2[3], pr2[5]])
    return lo, hi, extra_lo, extra_hi


def _build_mask(bgr_roi, lo, hi, extra_lo, extra_hi):
    hsv  = cv2.cvtColor(bgr_roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lo, hi)
    if extra_lo is not None:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, extra_lo, extra_hi))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)


def _extract_patches(bgra, mask_crop, y_top, y_bot, lo, hi, extra_lo, extra_hi):
    """
    Detect contours in mask_crop (cropped to source_region).
    Returns list of (patch_bgra, origin_x, origin_y) in full-image coordinates.
    """
    H, W = bgra.shape[:2]
    contours, _ = cv2.findContours(mask_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    patches = []

    for c in contours:
        area = cv2.contourArea(c)
        if area < 150:
            continue

        # Large merged blobs → grid-sample into individual object-sized patches
        if area > 40000:
            x, y, w, h = cv2.boundingRect(c)
            step = 55
            for gy in range(y, y + h - step, step):
                for gx in range(x, x + w - step, step):
                    lcx, lcy = gx + step // 2, gy + step // 2
                    if lcy >= mask_crop.shape[0] or mask_crop[lcy, lcx] == 0:
                        continue
                    sz   = random.randint(42, 88)
                    half = sz // 2
                    fcx, fcy = lcx, lcy + y_top
                    x1 = max(0, fcx - half);  y1 = max(0, fcy - half)
                    x2 = min(W, fcx + half);  y2 = min(y_bot, fcy + half)
                    if x2 - x1 < 16 or y2 - y1 < 16:
                        continue
                    pb = bgra[y1:y2, x1:x2, :3].copy()
                    pa = np.zeros((y2-y1, x2-x1, 4), dtype=np.uint8)
                    pa[:, :, :3] = pb
                    roi_hsv = cv2.cvtColor(pb, cv2.COLOR_BGR2HSV)
                    am = cv2.inRange(roi_hsv, lo, hi)
                    if extra_lo is not None:
                        am = cv2.bitwise_or(am, cv2.inRange(roi_hsv, extra_lo, extra_hi))
                    pa[:, :, 3] = am
                    if am.mean() > 10:
                        patches.append((pa, float(fcx), float(fcy)))
            continue

        # Normal blob
        x, y, bw, bh = cv2.boundingRect(c)
        pad = 4
        x1 = max(0, x - pad)
        y1 = max(0, y_top + y - pad)
        x2 = min(W, x + bw + pad)
        y2 = min(y_bot, y_top + y + bh + pad)
        if x2 <= x1 or y2 <= y1:
            continue

        pb = bgra[y1:y2, x1:x2, :3].copy()
        pa = np.zeros((y2-y1, x2-x1, 4), dtype=np.uint8)
        pa[:, :, :3] = pb

        # Sharp contour alpha mask
        lm = np.zeros((y2-y1, x2-x1), dtype=np.uint8)
        c_local = c.copy()
        c_local[:, :, 0] -= (x - pad)
        c_local[:, :, 1] -= (y - pad)
        cv2.drawContours(lm, [c_local], -1, 255, -1)
        feathered = cv2.GaussianBlur(lm.astype(np.float32), (3, 3), 0.8)
        pa[:, :, 3] = np.clip(feathered, 0, 255).astype(np.uint8)

        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"]) + y_top

        if pa[:, :, 3].mean() > 8:
            patches.append((pa, float(cx), float(cy)))

    return patches


def _rotate_patch(patch, angle_deg):
    h, w = patch.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return cv2.warpAffine(patch, M, (w, h),
                          flags=cv2.INTER_NEAREST,
                          borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(0, 0, 0, 0))


def _alpha_composite(base, overlay, x, y):
    bH, bW = base.shape[:2]
    oh, ow = overlay.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + ow, bW), min(y + oh, bH)
    if x1 <= x0 or y1 <= y0:
        return
    ox0, oy0 = x0 - x, y0 - y
    src = overlay[oy0:oy0+(y1-y0), ox0:ox0+(x1-x0)].astype(np.float32)
    dst = base[y0:y1, x0:x1].astype(np.float32)
    sa  = src[:, :, 3:4] / 255.0
    da  = dst[:, :, 3:4] / 255.0
    oa  = sa + da * (1 - sa)
    oas = np.where(oa > 0, oa, 1.0)
    rgb = (src[:, :, :3] * sa + dst[:, :, :3] * da * (1 - sa)) / oas
    base[y0:y1, x0:x1] = np.concatenate([rgb, oa * 255], axis=2).clip(0, 255).astype(np.uint8)


class _Particle:
    """
    Exact-origin seamless particle.
    Starts at its TRUE image position, travels to exit edge,
    becomes invisible during reset, reappears at same origin.
    Staggered delay keeps screen populated at all times.
    """
    def __init__(self, patch, origin_x, origin_y,
                 total_frames, H, W, direction, speed, fade_frac, delay):
        self.patch     = patch
        self.origin_x  = origin_x
        self.origin_y  = origin_y
        self.H, self.W = H, W
        self.direction = direction
        self.fade_frac = fade_frac
        self.delay     = delay
        self.total     = total_frames

        ph = patch.shape[0]
        self.half_h = ph // 2

        if direction == "down":
            self.travel_dist = (H + ph) - origin_y
        else:
            self.travel_dist = origin_y + ph

        base_vy = random.uniform(1.8, 3.2) * speed
        self.travel_frames = max(1, min(int(self.travel_dist / base_vy), total_frames - 5))
        self.vy = self.travel_dist / self.travel_frames

        self.vx         = random.uniform(-0.3, 0.3) * speed
        self.sway_amp   = random.uniform(4, 18)
        self.sway_freq  = random.uniform(0.015, 0.05)
        self.sway_phase = random.uniform(0, math.tau)

        self.angle0 = random.uniform(0, 360)
        self.spin   = random.uniform(-1.4, 1.4) * speed

    def draw(self, canvas, frame):
        local = (frame - self.delay) % self.total
        if local >= self.travel_frames:
            return  # invisible during reset period

        t = local

        if self.direction == "down":
            y = self.origin_y + self.vy * t
        else:
            y = self.origin_y - self.vy * t

        x = (self.origin_x
             + self.vx * t
             + self.sway_amp * math.sin(self.sway_freq * t + self.sway_phase))

        angle = self.angle0 + self.spin * t

        # Smooth fade in + fade out near exit edge
        progress = t / self.travel_frames
        if progress > (1.0 - self.fade_frac) and self.fade_frac > 0:
            alpha_mul = (1.0 - progress) / self.fade_frac
        elif progress < self.fade_frac and self.fade_frac > 0:
            alpha_mul = progress / self.fade_frac
        else:
            alpha_mul = 1.0

        rotated = _rotate_patch(self.patch, angle)
        if alpha_mul < 0.999:
            rotated = rotated.copy()
            rotated[:, :, 3] = (rotated[:, :, 3] * max(0.0, alpha_mul)).astype(np.uint8)

        px = int(x) - rotated.shape[1] // 2
        py = int(y) - rotated.shape[0] // 2
        _alpha_composite(canvas, rotated, px, py)


# ── Public API ────────────────────────────────────────────────────────────────

def stage3_particle_animation(
    image_path: str,
    output_path: str    = "god_video.mp4",
    color: str          = "pink",
    direction: str      = "down",
    source_region: tuple = (0.0, 0.42),
    duration: float     = 6.0,
    fps: int            = 30,
    particles: int      = 80,
    speed: float        = 1.0,
    fade: float         = 0.12,
) -> str:
    """
    Animate particles from an image falling or rising seamlessly.

    Parameters
    ----------
    image_path     : path to the input image
    output_path    : where to save the output MP4
    color          : color preset name OR custom HSV string "h_lo,h_hi,s_lo,s_hi,v_lo,v_hi"
                     Presets: blue red green yellow white pink orange purple cyan gold
    direction      : "down" (fall) or "up" (rise/float)
    source_region  : (top_frac, bot_frac) — Y fraction of image to extract objects from
                     e.g. (0.0, 0.42) = top 42% of image
    duration       : video duration in seconds (pass audio_duration to match audio)
    fps            : frames per second
    particles      : number of animated particles
    speed          : speed multiplier (0.3=slow dreamy, 1.0=normal, 2.0=fast)
    fade           : edge fade fraction for seamless loop blend (0.0–0.3)

    Returns
    -------
    str : path to the output video file
    """
    print(f"\n[Stage 3 — Particle Animation]")
    print(f"  Image     : {image_path}")
    print(f"  Color     : {color}  |  Direction: {direction}")
    print(f"  Region    : {source_region}  |  Particles: {particles}")
    print(f"  Duration  : {duration}s @ {fps}fps  |  Speed: {speed}×")

    # ── Load image ─────────────────────────────────────────────────────────
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Cannot open image: '{image_path}'")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    H, W = img.shape[:2]
    print(f"  Image size: {W}×{H}")

    # ── Source region ───────────────────────────────────────────────────────
    r_top, r_bot = source_region
    y_top = int(H * r_top)
    y_bot = int(H * r_bot)

    # ── Color mask ──────────────────────────────────────────────────────────
    lo, hi, extra_lo, extra_hi = _hsv_bounds(color)
    roi_bgr   = img[y_top:y_bot, :, :3]
    mask_crop = _build_mask(roi_bgr, lo, hi, extra_lo, extra_hi)
    n_px = int(np.sum(mask_crop > 0))
    print(f"  Mask pixels: {n_px}")
    if n_px < 50:
        print("  ⚠️  Very few matching pixels — try a different color or source_region")

    # ── Extract patches ─────────────────────────────────────────────────────
    patches_raw = _extract_patches(img, mask_crop, y_top, y_bot, lo, hi, extra_lo, extra_hi)
    print(f"  Patches extracted: {len(patches_raw)}")
    if not patches_raw:
        raise RuntimeError(
            f"No patches found for color='{color}', source_region={source_region}. "
            "Try a different --color preset or adjust source_region."
        )

    # ── Build particle pool ─────────────────────────────────────────────────
    total_frames = int(fps * duration)
    pool = patches_raw * (particles // max(len(patches_raw), 1) + 2)
    random.shuffle(pool)
    chosen = pool[:particles]

    particle_list = []
    for i, (patch, ox, oy) in enumerate(chosen):
        # Evenly stagger delays so screen is always populated
        delay = int((i / particles) * total_frames)
        p = _Particle(
            patch        = patch,
            origin_x     = ox,
            origin_y     = oy,
            total_frames = total_frames,
            H            = H,
            W            = W,
            direction    = direction,
            speed        = speed,
            fade_frac    = fade,
            delay        = delay,
        )
        particle_list.append(p)

    # ── Render ──────────────────────────────────────────────────────────────
    tmp_path = str(Path(output_path).with_suffix(".tmp.mp4"))
    fourcc   = cv2.VideoWriter_fourcc(*"mp4v")
    writer   = cv2.VideoWriter(tmp_path, fourcc, fps, (W, H))

    print(f"  Rendering {total_frames} frames …")
    for f in range(total_frames):
        canvas = img.copy()
        for p in particle_list:
            p.draw(canvas, f)
        writer.write(cv2.cvtColor(canvas, cv2.COLOR_BGRA2BGR))
        if f % (fps * 2) == 0:
            pct = int(f / total_frames * 100)
            print(f"    {pct:3d}%  frame {f}/{total_frames}")

    writer.release()

    # Re-encode to H.264 for universal playback
    if shutil.which("ffmpeg"):
        ret = subprocess.run([
            "ffmpeg", "-y", "-i", tmp_path,
            "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
            output_path
        ], capture_output=True)
        Path(tmp_path).unlink(missing_ok=True)
        if ret.returncode != 0:
            shutil.move(tmp_path, output_path)
            print("  ⚠️  ffmpeg re-encode failed, kept mp4v output")
    else:
        shutil.move(tmp_path, output_path)

    print(f"  ✅ Saved → {output_path}  ({total_frames} frames, seamless loop)")
    return output_path
