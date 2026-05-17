#!/usr/bin/env python3
"""
Wave Animator Pro v6 — Spin Float + Water Flow + Motion Leap + 9:16 (1080×1920) Export
Install: pip3 install opencv-python numpy pillow
Run:     python3 wave_animator_v5.py

NEW in v6
─────────
• DISPERSION  — A shared motion breakup control that adds turbulent, organic
  spread to supported warps and jumps.
• WATER FLOW  — Directional liquid-style advection with rolling turbulence and
  soft foam highlights inside the painted region.
• MOTION LEAP variants — three different energetic leap styles for painted
  objects: vertical hop, side leap, and pulse leap.

All earlier features remain available (Smoke Overlay, Layers, Spin Float, etc.).
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import cv2
import os, math, time, threading, random
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Export canvas ────────────────────────────────────────────────────────────
EXPORT_W = 1080
EXPORT_H = 1920

# ─── Animation type list ──────────────────────────────────────────────────────
ANIM_TYPES = [
    "Cloth Wave",                    # 0
    "Wind / Leaves",                 # 1
    "Water Ripple",                  # 2
    "Flag / Banner",                 # 3
    "Thunder & Lightning",           # 4
    "Particles / Bokeh",             # 5
    "Energy / Plasma",               # 6
    "Twinkling Stars",               # 7
    "Falling Leaves & Petals",       # 8
    "Leaves Wind",                   # 9
    "Fog / Mist",                    # 10
    "Flower Fall (Auto-Extract)",    # 11
    "Directional Scroll / River",    # 12
    "Clouds Moving",                 # 13
    "Rain",                          # 14
    "Sun / Energy Orb",              # 15
    "Floating Object",               # 16
    "Up / Down Breath",              # 17
    "Spin Float",                    # 18  ← NEW
    "Smoke (Area)",                  # 19
    "Cloud (Area)",                  # 20
    "Fire (Area)",                   # 21
    "Water Flow",                    # 22
    "Motion Leap (Hop)",             # 23
    "Motion Leap (Side)",            # 24
    "Motion Leap (Pulse)",           # 25
    "Motion Paths",                  # 26

    "3to2 Ratio Sway",               # 27
    "Flutter Pixaloop",              # 28
    "Living Painting",               # 29
    "ML Strip Wave (Sine)",          # 30  ← from MotionLeap agent
    "ML Strip Flow (Seamless)",      # 31  ← from MotionLeap agent
    "ML Strip Ripple",               # 32  ← from MotionLeap agent
    "Pixel Flow (MotionLeap)",       # 33  ← PixelFlowRenderer bilinear warp
    "Waterfall (Agent Flow)",        # 34  ← WaterfallState from agent.py
    "Cinematic Zoom (Agent)",        # 35  ← full-frame cinematic zoom/pan from agent.py
    "Firefly Glow (Jugnu)",          # 36  ← painted-area color fireflies / star glow
    "AI Orbit (MiDaS 2.5D)",        # 37  ← depth-based parallax orbit / Luma-style 3D
]

REGION_COLORS = [
    (0x89,0xb4,0xfa),(0xa6,0xe3,0xa1),(0xfa,0xb3,0x87),(0xf3,0x8b,0xa8),
    (0xcb,0xa6,0xf7),(0x94,0xe2,0xd5),(0xf9,0xe2,0xaf),(0xff,0xd7,0x00),
    (0xff,0x69,0xb4),(0x00,0xff,0xff),
]

BLEND_MODES = ["Normal", "Multiply", "Screen", "Overlay", "Soft Light", "Hard Light", "Add", "Difference"]

CAMERA_PRESETS = {
    "Eye Level":      {"pitch": 0.0,  "yaw": 0.0, "roll": 0.0, "zoom": 1.00},
    "Low Angle":      {"pitch": -9.0, "yaw": 0.0, "roll": 0.0, "zoom": 1.06},
    "High Angle":     {"pitch": 9.0,  "yaw": 0.0, "roll": 0.0, "zoom": 1.05},
    "Bird Eye View":  {"pitch": 20.0, "yaw": 0.0, "roll": 0.0, "zoom": 1.12},
}

CAMERA_SHOTS = [
    "Static",
    "Wide Zoom Slow Zoom",
    "Closeup Slow Motion",
    "Time Lapse Whip Pan",
    "Dolly In Push In",
    "Dolly Out",
    "Crane Shot",
    "Ken Burns",
    "Handheld Shake",
    "Earthquake Shake",
    "Breathing",
    "Orbit Arc",
    "Vertical Rise",
    "Pendulum Swing",
    "Dolly Zoom Vertigo",
    "Whip Pan Fast",
    "Push In Tilt",
    "360 Spin",
    "Slow Reveal Zoom",
    # ── From agent.py Cinematic Video Creator ──
    "Agent: Zoom In",
    "Agent: Zoom Out",
    "Agent: Ken Burns",
    "Agent: Drift Right",
    "Agent: Drift Left",
    "Agent: Push In Shake",
    "Agent: Crane Up",
    "Agent: Crane Down",
]

_noise_table = np.random.RandomState(42).uniform(-1, 1, 1024).astype(np.float32)

def _noise1d(x):
    x = np.asarray(x, dtype=np.float32)
    i = np.floor(x).astype(np.int32) & 1023
    f = x - np.floor(x)
    u = f * f * (3 - 2 * f)
    return _noise_table[i] * (1 - u) + _noise_table[(i + 1) & 1023] * u

def noise2d(x, y):
    return _noise1d(x + _noise1d(y * 7.3 + 13) * 2.1)


# ─────────────────────────────────────────────────────────────────────────────
#  EASING FUNCTIONS  (ported from agent.py)
# ─────────────────────────────────────────────────────────────────────────────
def _ease_in_out_cubic(t):
    if t < 0.5:
        return 4 * t * t * t
    p = 2 * t - 2
    return 0.5 * p * p * p + 1

def _ease_in_quad(t):
    return t * t

def _ease_out_quad(t):
    return t * (2 - t)

def _ease_in_expo(t):
    return 0.0 if t == 0 else math.pow(2, 10 * t - 10)

def _ease_in_out_sine(t):
    return -(math.cos(math.pi * t) - 1) / 2

_CINEMATIC_EASING = {
    "Smooth (Cubic)":    _ease_in_out_cubic,
    "Accelerate (Expo)": _ease_in_expo,
    "Ease In":           _ease_in_quad,
    "Ease Out":          _ease_out_quad,
    "Sinusoidal":        _ease_in_out_sine,
    "Linear":            lambda t: t,
}


# ─────────────────────────────────────────────────────────────────────────────
#  SMOKE OVERLAY
# ─────────────────────────────────────────────────────────────────────────────

SMOKE_COLOR_MAP = {
    "White":     (220, 225, 230),
    "Grey":      (150, 155, 160),
    "Dark":      ( 40,  42,  48),
    "Blue-Grey": (140, 160, 185),
    "Gold":      (210, 185, 130),
    "Teal":      (130, 195, 190),
}
SMOKE_COLOR_NAMES = list(SMOKE_COLOR_MAP.keys())


# ─────────────────────────────────────────────────────────────────────────────
#  SPIN FLOAT ANIMATION  (NEW in v5)
# ─────────────────────────────────────────────────────────────────────────────
class SpinFloatState:
    """
    The painted region rotates continuously around its own centroid while
    gently bobbing up/down and drifting side-to-side.  A soft elliptical
    shadow beneath stretches/shrinks with the bob for depth.

    Controls:
        amp   → bob height in pixels
        freq  → bob rate (cycles/sec)
        spd   → overall time scale
        spin_speed (extra param) → rotation speed multiplier
        bob_lateral (extra param) → lateral drift fraction (0-1)
    """
    def __init__(self, mask: np.ndarray, static_np: np.ndarray):
        self.H, self.W = static_np.shape[:2]
        ys, xs = np.where(mask > 128)
        if len(xs) == 0:
            self._empty = True
            return
        self._empty = False

        # Bounding box
        self.y0 = int(ys.min()); self.y1 = int(ys.max()) + 1
        self.x0 = int(xs.min()); self.x1 = int(xs.max()) + 1
        ph = self.y1 - self.y0
        pw = self.x1 - self.x0

        # Crop the painted patch with a generous transparent border so
        # rotation corners never clip the edge of the crop rectangle.
        pad = int(max(ph, pw) * 0.55) + 4          # enough for any rotation
        self._pad = pad

        # Build padded RGBA patch
        full_h = ph + pad * 2
        full_w = pw + pad * 2
        self._patch = np.zeros((full_h, full_w, 4), dtype=np.uint8)
        crop_img  = static_np[self.y0:self.y1, self.x0:self.x1]
        crop_mask = mask     [self.y0:self.y1, self.x0:self.x1]

        self._patch[pad:pad+ph, pad:pad+pw, :3] = crop_img
        self._patch[pad:pad+ph, pad:pad+pw,  3] = crop_mask

        # Feather the alpha edge a little for smooth compositing
        alpha_f = cv2.GaussianBlur(
            self._patch[:, :, 3].astype(np.float32), (0, 0), 2.5)
        self._patch[:, :, 3] = np.clip(alpha_f, 0, 255).astype(np.uint8)

        # Centre of rotation = centre of padded patch
        self._cx_patch = full_w / 2.0
        self._cy_patch = full_h / 2.0

        # Screen position of the patch centre (maps to original bbox centre)
        self._screen_cx = (self.x0 + self.x1) / 2.0
        self._screen_cy = (self.y0 + self.y1) / 2.0

        # Random per-region phases so multiple regions don't move in lockstep
        self._phase_bob  = random.uniform(0, math.tau)
        self._phase_lat  = random.uniform(0, math.tau)
        self._phase_spin = random.uniform(0, math.tau)   # spin start angle

    # ------------------------------------------------------------------
    def draw(self, frame: np.ndarray, t: float,
             amp: float, freq: float, spd: float,
             spin_speed: float = 1.0,
             bob_lateral: float = 0.25) -> np.ndarray:
        if self._empty:
            return frame

        # ── Motion parameters ──────────────────────────────────────────
        phase_t = t * spd

        # Vertical bob
        dy = amp * math.sin(freq * math.tau * phase_t + self._phase_bob)
        # Lateral drift (much smaller)
        dx = amp * bob_lateral * math.sin(freq * math.tau * phase_t * 0.71
                                          + self._phase_lat)
        # Continuous rotation angle (degrees)
        deg = (phase_t * spin_speed * 60.0
               + math.degrees(self._phase_spin)) % 360.0

        # ── Rotate the padded patch ────────────────────────────────────
        M = cv2.getRotationMatrix2D(
            (self._cx_patch, self._cy_patch), deg, 1.0)
        ph_h, ph_w = self._patch.shape[:2]
        rotated = cv2.warpAffine(
            self._patch, M, (ph_w, ph_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

        out = frame.copy()

        # ── Shadow (ellipse below the object, grows with bob height) ──
        shadow_lift   = abs(dy) * 0.30 + 3.0
        shadow_spread = max(0.3, 1.0 - abs(dy) / max(1.0, amp * 2.0))
        shadow_alpha  = 0.40 * shadow_spread

        sx = int(self._screen_cx + dx)
        sy = int(self._screen_cy + dy + shadow_lift)
        sh_rx = max(4, int(ph_w * 0.38 * shadow_spread))
        sh_ry = max(2, int(ph_h * 0.12 * shadow_spread))

        shadow_buf = np.zeros((self.H, self.W), dtype=np.float32)
        cv2.ellipse(shadow_buf, (sx, sy), (sh_rx, sh_ry),
                    0, 0, 360, 1.0, -1)
        shadow_buf = cv2.GaussianBlur(shadow_buf, (0, 0), max(sh_rx * 0.5, 4.0))
        shadow_buf = np.clip(shadow_buf * shadow_alpha, 0, 1)
        for c in range(3):
            out[:, :, c] = np.clip(
                out[:, :, c].astype(np.float32) * (1.0 - shadow_buf),
                0, 255).astype(np.uint8)

        # ── Blit rotated patch ────────────────────────────────────────
        # Top-left corner on screen where the padded patch will land
        px = int(self._screen_cx + dx) - ph_w // 2
        py = int(self._screen_cy + dy) - ph_h // 2

        fx0 = max(0, px);          fy0 = max(0, py)
        fx1 = min(self.W, px+ph_w); fy1 = min(self.H, py+ph_h)
        if fx1 <= fx0 or fy1 <= fy0:
            return out

        ox0 = fx0 - px;  oy0 = fy0 - py
        img_roi  = rotated[oy0:oy0+(fy1-fy0), ox0:ox0+(fx1-fx0), :3]
        mask_roi = rotated[oy0:oy0+(fy1-fy0), ox0:ox0+(fx1-fx0),  3].astype(np.float32) / 255.0
        m3 = mask_roi[:, :, np.newaxis]

        out[fy0:fy1, fx0:fx1] = (
                out[fy0:fy1, fx0:fx1].astype(np.float32) * (1.0 - m3)
                + img_roi.astype(np.float32) * m3
        ).astype(np.uint8)

        return out


# ─────────────────────────────────────────────────────────────────────────────
#  WATER FLOW + MOTION LEAP
# ─────────────────────────────────────────────────────────────────────────────
class WaterFlowState:
    def __init__(self, mask, static_np):
        self.mask = mask
        self.H, self.W = mask.shape
        ys, xs = np.where(mask > 128)
        self._empty = len(xs) == 0
        if self._empty:
            return
        self.y0 = int(ys.min()); self.y1 = int(ys.max()) + 1
        self.x0 = int(xs.min()); self.x1 = int(xs.max()) + 1
        self.tile = static_np[self.y0:self.y1, self.x0:self.x1].copy()
        self.mask_crop = mask[self.y0:self.y1, self.x0:self.x1].copy()
        self.ch, self.cw = self.tile.shape[:2]
        xs_l = np.arange(self.cw, dtype=np.float32)
        ys_l = np.arange(self.ch, dtype=np.float32)
        self.lx, self.ly = np.meshgrid(xs_l, ys_l)
        self.soft_mask = cv2.GaussianBlur(self.mask_crop.astype(np.float32) / 255.0, (0, 0), 4.0)

    def draw(self, frame, t, amp, freq, spd, direction, dispersion, foam):
        if self._empty:
            return frame
        rad = math.radians(direction)
        dx = math.cos(rad)
        dy = math.sin(rad)
        flow = t * max(0.1, spd) * 48.0
        base_x = self.lx + dx * flow
        base_y = self.ly + dy * flow
        wave_a = amp * (0.10 + dispersion * 0.16)
        perp_x = -dy
        perp_y = dx
        curve = np.sin((self.lx * perp_x + self.ly * perp_y) * 0.055 + t * freq * 4.1).astype(np.float32)
        curl_x = curve * perp_x * wave_a
        curl_y = curve * perp_y * wave_a
        if dispersion > 0.001:
            n1 = noise2d(self.lx * 0.032 + t * (0.9 + spd * 0.35), self.ly * 0.028 + 7.5).astype(np.float32)
            n2 = noise2d(self.ly * 0.030 - t * (0.8 + spd * 0.30), self.lx * 0.026 + 19.0).astype(np.float32)
            curl_x += n1 * amp * dispersion * 0.9
            curl_y += n2 * amp * dispersion * 0.6
        map_x = np.mod(base_x + curl_x, self.cw).astype(np.float32)
        map_y = np.mod(base_y + curl_y, self.ch).astype(np.float32)
        flowed = cv2.remap(self.tile, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

        shimmer = np.sin((self.lx * 0.14 + self.ly * 0.07) + t * (5.0 + spd * 2.5)).astype(np.float32)
        shimmer = np.clip((shimmer + 1.0) * 0.5, 0, 1)
        foam_mask = np.clip((curve * 0.5 + 0.5) * foam * 0.30 + shimmer * foam * 0.12, 0, 0.48)
        flowed_f = flowed.astype(np.float32)
        flowed_f[:, :, 0] = np.clip(flowed_f[:, :, 0] + foam_mask * 38.0, 0, 255)
        flowed_f[:, :, 1] = np.clip(flowed_f[:, :, 1] + foam_mask * 52.0, 0, 255)
        flowed_f[:, :, 2] = np.clip(flowed_f[:, :, 2] + foam_mask * 68.0, 0, 255)

        out = frame.copy()
        roi = out[self.y0:self.y1, self.x0:self.x1].astype(np.float32)
        mask3 = self.soft_mask[:, :, np.newaxis]
        out[self.y0:self.y1, self.x0:self.x1] = (roi * (1.0 - mask3) + flowed_f * mask3).astype(np.uint8)
        return out


class MotionLeapState:
    def __init__(self, mask, static_np, mode="hop"):
        self.mode = mode
        self.H, self.W = static_np.shape[:2]
        ys, xs = np.where(mask > 128)
        if len(xs) == 0:
            self._empty = True
            return
        self._empty = False
        self.y0 = int(ys.min()); self.y1 = int(ys.max()) + 1
        self.x0 = int(xs.min()); self.x1 = int(xs.max()) + 1
        ph = self.y1 - self.y0
        pw = self.x1 - self.x0
        pad = int(max(ph, pw) * 0.65) + 6
        self.patch = np.zeros((ph + pad * 2, pw + pad * 2, 4), dtype=np.uint8)
        crop = static_np[self.y0:self.y1, self.x0:self.x1]
        crop_mask = mask[self.y0:self.y1, self.x0:self.x1]
        self.patch[pad:pad+ph, pad:pad+pw, :3] = crop
        self.patch[pad:pad+ph, pad:pad+pw, 3] = crop_mask
        self.patch[:, :, 3] = np.clip(cv2.GaussianBlur(self.patch[:, :, 3].astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
        self.ph, self.pw = self.patch.shape[:2]
        self.cx_patch = self.pw / 2.0
        self.cy_patch = self.ph / 2.0
        self.screen_cx = (self.x0 + self.x1) / 2.0
        self.screen_cy = (self.y0 + self.y1) / 2.0
        self.phase = random.uniform(0, math.tau)
        self.phase2 = random.uniform(0, math.tau)

    def draw(self, frame, t, amp, freq, spd, dispersion):
        if self._empty:
            return frame
        cyc = (t * max(0.1, spd) * max(0.15, freq) + self.phase / math.tau) % 1.0
        jump = max(0.0, math.sin(cyc * math.pi))
        jump_e = jump ** 1.5
        dy = -amp * 1.45 * jump_e
        dx = 0.0
        scale_x = 1.0
        scale_y = 1.0
        rot = 0.0
        ghost_strength = 0.0

        if self.mode == "hop":
            rot = math.sin(cyc * math.pi * 2.0 + self.phase2) * amp * 0.18
            dx = math.sin(cyc * math.pi * 2.0 + self.phase2) * dispersion * amp * 0.25
            scale_x = 1.0 + (1.0 - jump) * 0.08
            scale_y = 1.0 - (1.0 - jump) * 0.06
            ghost_strength = dispersion * 0.22
        elif self.mode == "side":
            dx = math.sin(cyc * math.pi) * amp * (0.55 + dispersion * 0.75)
            rot = -math.sin(cyc * math.pi) * (10.0 + amp * 0.10)
            dy *= 0.92
            ghost_strength = 0.10 + dispersion * 0.28
        elif self.mode == "pulse":
            pulse = math.sin(cyc * math.pi) ** 2
            dy = -amp * 0.95 * pulse
            scale_x = 1.0 + pulse * (0.10 + dispersion * 0.18)
            scale_y = 1.0 - pulse * 0.08
            rot = math.sin(cyc * math.pi * 4.0 + self.phase2) * (3.0 + amp * 0.08)
            dx = math.sin(cyc * math.pi * 2.0 + self.phase2) * amp * dispersion * 0.16
            ghost_strength = 0.16 + dispersion * 0.26

        M = cv2.getRotationMatrix2D((self.cx_patch, self.cy_patch), rot, 1.0)
        M[0, 0] *= scale_x; M[0, 1] *= scale_x
        M[1, 0] *= scale_y; M[1, 1] *= scale_y
        transformed = cv2.warpAffine(
            self.patch, M, (self.pw, self.ph),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        out = frame.copy()

        shadow_spread = max(0.28, 1.0 - jump_e * 0.55)
        shadow_alpha = 0.38 * shadow_spread
        sx = int(self.screen_cx + dx)
        sy = int(self.screen_cy + amp * 0.12 + abs(dy) * 0.24)
        sh_rx = max(5, int(self.pw * 0.30 * shadow_spread))
        sh_ry = max(2, int(self.ph * 0.09 * shadow_spread))
        shadow = np.zeros((self.H, self.W), dtype=np.float32)
        cv2.ellipse(shadow, (sx, sy), (sh_rx, sh_ry), 0, 0, 360, 1.0, -1)
        shadow = cv2.GaussianBlur(shadow, (0, 0), max(4.0, sh_rx * 0.45))
        shadow = np.clip(shadow * shadow_alpha, 0, 1)
        for c in range(3):
            out[:, :, c] = np.clip(out[:, :, c].astype(np.float32) * (1.0 - shadow), 0, 255).astype(np.uint8)

        if ghost_strength > 0.01:
            for trail_mul, trail_alpha in ((-0.55, ghost_strength * 0.6), (-1.1, ghost_strength * 0.35)):
                out = self._blit(out, transformed, dx * trail_mul, dy * trail_mul * 0.4, trail_alpha)
        out = self._blit(out, transformed, dx, dy, 1.0)
        return out

    def _blit(self, frame, patch_rgba, dx, dy, alpha_mul):
        px = int(self.screen_cx + dx) - self.pw // 2
        py = int(self.screen_cy + dy) - self.ph // 2
        fx0 = max(0, px); fy0 = max(0, py)
        fx1 = min(self.W, px + self.pw); fy1 = min(self.H, py + self.ph)
        if fx1 <= fx0 or fy1 <= fy0:
            return frame
        ox0 = fx0 - px; oy0 = fy0 - py
        src = patch_rgba[oy0:oy0+(fy1-fy0), ox0:ox0+(fx1-fx0)]
        alpha = (src[:, :, 3].astype(np.float32) / 255.0) * alpha_mul
        a3 = alpha[:, :, np.newaxis]
        out = frame.copy()
        out[fy0:fy1, fx0:fx1] = (
                out[fy0:fy1, fx0:fx1].astype(np.float32) * (1.0 - a3)
                + src[:, :, :3].astype(np.float32) * a3
        ).astype(np.uint8)
        return out


def _render_motion_paths(static_np, frame, mask, freeze_mask, paths, anchors, t,
                         amp, freq, spd, dispersion,
                         path_radius=70.0, anchor_strength=1.0):
    """
    Motionleap-style directional flow animation.

    HOW MOTIONLEAP ACTUALLY WORKS (from reverse-engineering the reference video):
    ─────────────────────────────────────────────────────────────────────────────
    It does NOT warp/remap existing pixels.  Instead it uses a multi-layer
    FLOW ADVECTION technique:

    1. Build a smooth 2-D vector field (vx, vy) across the painted region
       by blending the direction of every drawn arrow, weighted by distance.
       Anchors set the field to zero.  Freeze keeps those pixels static.

    2. Render MULTIPLE semi-transparent "flow layers" — each layer samples
       the static image at coordinates offset by  (vx*layer_offset, vy*layer_offset).
       Each layer has a different phase so together they look like continuous
       motion along the arrows.

    3. Layer alphas fade in/out over time based on their phase so new content
       appears to stream in from behind and old content disappears ahead — this
       is what gives the seamless, edge-free "liquid flow" look.

    4. The final output composites all layers back over the static frame using
       the soft mask as the blend weight — so the boundary is always clean.

    KEY INSIGHT vs old approach:
    Old: warp src coords → hard displacement artifact / seams at mask edge
    New: alpha-blend multiple offset copies → seamless, no hard edges
    """
    H, W = mask.shape
    if not np.any(mask > 128) or not paths:
        return frame

    xs_1d = np.arange(W, dtype=np.float32)
    ys_1d = np.arange(H, dtype=np.float32)

    # ── 1. Build smooth directional vector field ──────────────────────────────
    field_x = np.zeros((H, W), dtype=np.float32)
    field_y = np.zeros((H, W), dtype=np.float32)
    weight_sum = np.zeros((H, W), dtype=np.float32)

    rad_base = max(20.0, float(path_radius))

    for path in paths:
        x1f = float(path["x1"]); y1f = float(path["y1"])
        x2f = float(path["x2"]); y2f = float(path["y2"])
        vx  = x2f - x1f;          vy  = y2f - y1f
        plen = math.hypot(vx, vy)
        if plen < 2.0:
            continue
        # unit direction
        uvx = vx / plen;  uvy = vy / plen

        sigma = max(12.0, rad_base + plen * 0.15)
        denom = vx * vx + vy * vy + 1e-6

        wx = xs_1d[np.newaxis, :] - x1f   # (1,W)
        wy = ys_1d[:, np.newaxis] - y1f   # (H,1)

        u  = np.clip((wx * vx + wy * vy) / denom, 0.0, 1.0)
        cx = x1f + u * vx
        cy = y1f + u * vy

        dist = np.sqrt((xs_1d[np.newaxis, :] - cx) ** 2 +
                       (ys_1d[:, np.newaxis] - cy) ** 2)
        w = np.exp(-(dist / sigma) ** 2).astype(np.float32)

        field_x   += w * uvx
        field_y   += w * uvy
        weight_sum += w

    # normalise so field is unit-direction weighted by coverage
    safe = np.where(weight_sum > 1e-4, weight_sum, 1.0)
    field_x /= safe
    field_y /= safe

    # ── 2. Apply soft mask so field is zero outside painted region ────────────
    soft_mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 6.0)

    # freeze mask zeroes the field
    if freeze_mask is not None and np.any(freeze_mask > 0):
        freeze_soft = cv2.GaussianBlur(freeze_mask.astype(np.float32) / 255.0, (0, 0), 5.0)
        soft_mask *= np.clip(1.0 - freeze_soft, 0.0, 1.0)

    # anchor points suppress field locally
    if anchors:
        for anc in anchors:
            ax = float(anc["x"]); ay = float(anc["y"])
            ar = max(20.0, rad_base * 0.8)
            hold = np.exp(-(
                    (xs_1d[np.newaxis, :] - ax) ** 2 +
                    (ys_1d[:, np.newaxis] - ay) ** 2
            ) / (2.0 * ar ** 2)).astype(np.float32) * float(anchor_strength)
            soft_mask *= np.clip(1.0 - hold, 0.0, 1.0)

    field_x *= soft_mask
    field_y *= soft_mask

    # optional organic turbulence
    if dispersion > 0.001:
        sc  = 6
        nH  = max(4, H // sc); nW = max(4, W // sc)
        gxn = np.linspace(0, 5.0, nW, dtype=np.float32)
        gyn = np.linspace(0, 5.0, nH, dtype=np.float32)
        GX, GY = np.meshgrid(gxn, gyn)
        nx = cv2.resize(noise2d(GX + t * 0.7, GY + 9.3).astype(np.float32),
                        (W, H), interpolation=cv2.INTER_LINEAR)
        ny = cv2.resize(noise2d(GY - t * 0.6, GX + 22.1).astype(np.float32),
                        (W, H), interpolation=cv2.INTER_LINEAR)
        field_x += nx * dispersion * 0.35 * soft_mask
        field_y += ny * dispersion * 0.25 * soft_mask

    # ── 3. Multi-layer flow advection ─────────────────────────────────────────
    # Each layer shifts the sample coords by a different "travel distance".
    # Layers scroll continuously — phase is time-driven so motion is smooth.
    #
    # travel_px: how many pixels the flow moves per second (scales with amp+spd)
    travel_px   = max(8.0, amp * 2.8) * max(0.1, spd)
    # number of layers — more = smoother but slightly heavier
    n_layers    = 6
    # layer spacing in phase (0–1)
    layer_gap   = 1.0 / n_layers
    # global phase advances with time
    global_phase = math.fmod(t * max(0.1, spd) * max(0.15, freq), 1.0)

    # accumulate weighted layers into a float RGB buffer
    acc_rgb   = np.zeros((H, W, 3), dtype=np.float32)
    acc_alpha = np.zeros((H, W),    dtype=np.float32)

    for i in range(n_layers):
        # each layer's phase offset (0–1)
        ph = math.fmod(global_phase + i * layer_gap, 1.0)
        # travel offset for this layer — moves continuously in field direction
        offset = ph * travel_px

        # sample coords: pull from upstream (negative offset = reading from behind)
        sx = np.clip(xs_1d[np.newaxis, :] - field_x * offset, 0, W - 1).astype(np.float32)
        sy = np.clip(ys_1d[:, np.newaxis] - field_y * offset, 0, H - 1).astype(np.float32)

        sampled = cv2.remap(static_np, sx, sy,
                            cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

        # layer alpha: smooth ramp up and down across the phase cycle
        # peaks at ph=0.5, zero at ph=0 and ph=1 — gives seamless crossfade
        layer_alpha = math.sin(ph * math.pi) ** 1.4  # slightly sharper than pure sin
        layer_alpha *= soft_mask  # only inside painted region

        acc_rgb   += sampled.astype(np.float32) * layer_alpha[:, :, np.newaxis]
        acc_alpha += layer_alpha

    # normalise by total alpha weight to get weighted average colour
    safe_alpha = np.where(acc_alpha > 1e-4, acc_alpha, 1.0)
    avg_rgb = acc_rgb / safe_alpha[:, :, np.newaxis]

    # ── 4. Composite: blend flow result over static frame ─────────────────────
    # Use soft_mask as the composite weight so boundary is always feathered
    # acc_alpha normalised to [0,1] controls how much of the flow shows
    blend_w = np.clip(acc_alpha / max(1e-4, n_layers * 0.5), 0.0, 1.0)
    blend_w *= soft_mask
    b3 = blend_w[:, :, np.newaxis]

    out = (frame.astype(np.float32) * (1.0 - b3) +
           avg_rgb * b3).astype(np.uint8)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  FLOATING OBJECT ANIMATION  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
class FloatingObjectState:
    def __init__(self, mask, static_np):
        self.H, self.W = static_np.shape[:2]
        ys, xs = np.where(mask > 128)
        if len(xs) == 0:
            self._empty = True; return
        self._empty = False
        self.y0 = int(ys.min()); self.y1 = int(ys.max()) + 1
        self.x0 = int(xs.min()); self.x1 = int(xs.max()) + 1
        self.mask_crop = mask[self.y0:self.y1, self.x0:self.x1].copy()
        self.img_crop  = static_np[self.y0:self.y1, self.x0:self.x1].copy()
        self.cx = (self.x0 + self.x1) / 2.0
        self.cy = (self.y0 + self.y1) / 2.0
        self._phase  = random.uniform(0, math.tau)
        self._phase2 = random.uniform(0, math.tau)

    def draw(self, frame, t, amp, freq, spd):
        if self._empty: return frame
        out = frame.copy()
        ph = t * spd * math.tau + self._phase
        dy = amp * math.sin(freq * ph)
        dx = amp * 0.15 * math.sin(freq * 0.7 * ph + self._phase2)
        rot_deg = amp * 0.4 * math.sin(freq * 0.5 * ph + self._phase2 + 1.0)
        ph_h, ph_w = self.img_crop.shape[:2]
        M = cv2.getRotationMatrix2D((ph_w / 2, ph_h / 2), rot_deg, 1.0)
        rotated_img  = cv2.warpAffine(self.img_crop,  M, (ph_w, ph_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        rotated_mask = cv2.warpAffine(self.mask_crop, M, (ph_w, ph_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        shadow_dy = abs(dy) * 0.25 + 4
        sx = int(self.cx) - ph_w // 2 + int(dx); sy = int(self.y0) + int(dy) + int(shadow_dy)
        shadow = np.zeros((ph_h, ph_w), dtype=np.float32)
        cv2.ellipse(shadow, (ph_w // 2, ph_h - 4), (int(ph_w * 0.4), max(4, int(6 - abs(dy) * 0.1))), 0, 0, 360, 1.0, -1)
        shadow = cv2.GaussianBlur(shadow, (0, 0), 8.0)
        for c in range(3):
            fx0s = max(0, sx); fy0s = max(0, sy); fx1s = min(self.W, sx + ph_w); fy1s = min(self.H, sy + ph_h)
            if fx1s > fx0s and fy1s > fy0s:
                ox0s = fx0s - sx; oy0s = fy0s - sy; sh_roi = shadow[oy0s:oy0s+(fy1s-fy0s), ox0s:ox0s+(fx1s-fx0s)]
                out[fy0s:fy1s, fx0s:fx1s, c] = np.clip(out[fy0s:fy1s, fx0s:fx1s, c].astype(np.float32) * (1 - sh_roi * 0.45), 0, 255)
        px = int(self.x0) + int(dx); py = int(self.y0) + int(dy)
        fx0 = max(0, px); fy0 = max(0, py); fx1 = min(self.W, px + ph_w); fy1 = min(self.H, py + ph_h)
        if fx1 <= fx0 or fy1 <= fy0: return out
        ox0 = fx0 - px; oy0 = fy0 - py
        img_roi  = rotated_img [oy0:oy0+(fy1-fy0), ox0:ox0+(fx1-fx0)]
        mask_roi = rotated_mask[oy0:oy0+(fy1-fy0), ox0:ox0+(fx1-fx0)].astype(np.float32) / 255.0
        mask3 = mask_roi[:, :, np.newaxis]
        out[fy0:fy1, fx0:fx1] = (out[fy0:fy1, fx0:fx1].astype(np.float32) * (1 - mask3) + img_roi.astype(np.float32) * mask3).astype(np.uint8)
        return out


# ─────────────────────────────────────────────────────────────────────────────
#  UP / DOWN BREATH ANIMATION  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
class UpDownState:
    def __init__(self, mask, static_np):
        self.mask = mask; self.H, self.W = static_np.shape[:2]
        ys, xs = np.where(mask > 128)
        if len(xs) == 0:
            self._empty = True; return
        self._empty = False
        self.y0 = int(ys.min()); self.y1 = int(ys.max()) + 1
        self.x0 = int(xs.min()); self.x1 = int(xs.max()) + 1
        self._phase = random.uniform(0, math.tau)

    def draw(self, frame, static_np, t, amp, freq, spd):
        if self._empty: return frame
        ph = t * spd * math.tau + self._phase
        shift = amp * math.sin(freq * ph)
        si = int(round(shift))
        if si == 0: return frame
        out = frame.copy()
        y0, y1 = self.y0, self.y1; x0, x1 = self.x0, self.x1
        mask_crop = self.mask[y0:y1, x0:x1]
        src_y0 = max(0, y0 - si); src_y1 = min(self.H, y1 - si)
        dst_y0 = src_y0 + si;     dst_y1 = src_y1 + si
        dst_y0c = max(0, dst_y0); dst_y1c = min(self.H, dst_y1)
        if dst_y1c <= dst_y0c: return out
        roff = dst_y0c - dst_y0; r_src_y0 = src_y0 + roff; r_src_y1 = r_src_y0 + (dst_y1c - dst_y0c)
        if r_src_y1 > self.H or r_src_y0 < 0: return out
        src_rows = static_np[r_src_y0:r_src_y1, x0:x1]
        mc_y0 = dst_y0c - y0; mc_y1 = mc_y0 + (dst_y1c - dst_y0c)
        mc_y0c = max(0, mc_y0); mc_y1c = min(mask_crop.shape[0], mc_y1)
        if mc_y1c <= mc_y0c: return out
        rr = mc_y0c - mc_y0; mc_rows = mask_crop[mc_y0c:mc_y1c, :]
        src_rows = src_rows[rr:rr+mc_rows.shape[0]]
        if src_rows.shape[0] == 0: return out
        m3 = mc_rows[:, :, np.newaxis].astype(np.float32) / 255.0
        roi = out[dst_y0c:dst_y0c+src_rows.shape[0], x0:x1]
        out[dst_y0c:dst_y0c+src_rows.shape[0], x0:x1] = (roi.astype(np.float32) * (1 - m3) + src_rows.astype(np.float32) * m3).astype(np.uint8)
        return out


# ─────────────────────────────────────────────────────────────────────────────
#  SMOKE  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
class SmokeParticle:
    __slots__ = ('x','y','r','vx','vy','life','max_life','alpha','expand_rate',
                 'rot','rot_spd','col','layer','W','H')
    def __init__(self, W, H, col, wind_vx, wind_vy, density_mul=1.0):
        self.W = W; self.H = H
        self.x  = random.uniform(0, W); self.y  = random.uniform(H * 0.7, H + 60)
        self.r  = random.uniform(30, 90)
        self.vx = wind_vx * random.uniform(0.5, 1.5) + random.uniform(-0.4, 0.4)
        self.vy = -(random.uniform(0.4, 1.2)) + wind_vy
        self.life     = random.uniform(0, 1.0); self.max_life = random.uniform(3.0, 7.0)
        self.alpha    = random.uniform(0.25, 0.55) * density_mul
        self.expand_rate = random.uniform(0.15, 0.45)
        self.rot      = random.uniform(0, math.tau); self.rot_spd  = random.uniform(-0.008, 0.008)
        self.col      = col; self.layer    = random.randint(0, 2)
    def update(self, dt, spd):
        self.life += dt * spd; self.x += self.vx * spd; self.y += self.vy * spd
        self.r += self.expand_rate * spd; self.rot += self.rot_spd * spd
    @property
    def done(self): return self.life >= self.max_life or self.r > 400
    @property
    def opacity(self):
        p = self.life / self.max_life
        if p < 0.12: return self.alpha * (p / 0.12)
        if p > 0.70: return self.alpha * (1.0 - (p - 0.70) / 0.30)
        return self.alpha


class SmokeState:
    _LUT_RADII = [int(8 * (1.22**i)) for i in range(30) if int(8*(1.22**i)) <= 300]
    def __init__(self):
        self.particles = []; self._W = self._H = 0; self._last_spawn = 0.0
        self._lut: dict = {}; self._build_lut()
    def _build_lut(self):
        for r in self._LUT_RADII: self._lut[r] = self._make_brush(r)
    @staticmethod
    def _make_brush(r):
        sz = r * 2; c = r
        ys = (np.arange(sz, dtype=np.float32) - c); xs = (np.arange(sz, dtype=np.float32) - c)
        PX, PY = np.meshgrid(xs, ys); d2 = PX**2 + PY**2
        g = (np.exp(-d2 / (2*(r*0.38)**2)) + np.exp(-d2 / (2*(r*0.62)**2)) * 0.50 + np.exp(-d2 / (2*(r*0.88)**2)) * 0.18)
        return np.clip(g, 0, 1).astype(np.float32)
    def _nearest_radius(self, r):
        best = self._LUT_RADII[0]
        for lr in self._LUT_RADII:
            if abs(lr - r) < abs(best - r): best = lr
        return best
    def render(self, frame, t, dt, color_name, wind_deg, density, speed, turbulence, opacity):
        H, W = frame.shape[:2]
        if W != self._W or H != self._H:
            self._W = W; self._H = H; self.particles.clear()
        col = np.array(SMOKE_COLOR_MAP.get(color_name, (220,225,230)), dtype=np.float32)
        rad = math.radians(wind_deg); wind_vx = math.cos(rad) * speed * 0.55; wind_vy = math.sin(rad) * speed * 0.28
        spawn_interval = max(0.04, 0.22 / max(0.1, density))
        if t - self._last_spawn > spawn_interval:
            n_spawn = max(1, int(density * 2))
            for _ in range(n_spawn): self.particles.append(SmokeParticle(W, H, (0,0,0), wind_vx, wind_vy, density))
            self._last_spawn = t
        live = []
        for p in self.particles:
            if turbulence > 0.01:
                nx = noise2d(p.x * 0.007 + t * 0.28, p.y * 0.005 + t * 0.1) * turbulence
                ny = noise2d(p.y * 0.006 + t * 0.22, p.x * 0.008 + 55)      * turbulence * 0.45
                p.x += nx; p.y += ny
            p.update(dt, speed)
            if not p.done: live.append(p)
        self.particles = live
        max_p = max(40, int(density * 80))
        if len(self.particles) > max_p: self.particles = self.particles[-max_p:]
        if not self.particles: return frame
        acc = np.zeros((H, W), dtype=np.float32)
        for p in self.particles:
            alpha = p.opacity * opacity
            if alpha < 0.005: continue
            r_raw = max(8, int(p.r)); r = self._nearest_radius(r_raw); brush = self._lut[r]
            px = int(p.x) - r; py = int(p.y) - r
            fx0 = max(0, px); fy0 = max(0, py); fx1 = min(W, px+r*2); fy1 = min(H, py+r*2)
            if fx1 <= fx0 or fy1 <= fy0: continue
            ox0 = fx0 - px; oy0 = fy0 - py; roi = brush[oy0:oy0+(fy1-fy0), ox0:ox0+(fx1-fx0)]
            acc[fy0:fy1, fx0:fx1] = np.minimum(1.0, acc[fy0:fy1, fx0:fx1] + roi * alpha * (1 - acc[fy0:fy1, fx0:fx1]))
        acc3 = acc[:, :, np.newaxis]; result = frame.astype(np.float32) * (1 - acc3) + col * acc3
        return np.clip(result, 0, 255).astype(np.uint8)


class AreaSmokeState:
    def __init__(self, mask):
        self.mask = mask
        self.H, self.W = mask.shape
        ys, xs = np.where(mask > 128)
        self._empty = len(xs) == 0
        if self._empty:
            return
        self.x0, self.x1 = int(xs.min()), int(xs.max())
        self.y0, self.y1 = int(ys.min()), int(ys.max())
        self.soft_mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 6.5)
        self.parts = []

    def _spawn(self, n):
        for _ in range(n):
            self.parts.append({
                "x": random.uniform(self.x0, self.x1),
                "y": random.uniform(self.y1 - max(8, (self.y1 - self.y0) * 0.25), self.y1 + 10),
                "r": random.uniform(7, 24),
                "vx": random.uniform(-0.24, 0.24),
                "vy": random.uniform(-1.2, -0.28),
                "life": random.uniform(0.0, 1.5),
                "max": random.uniform(2.0, 4.4),
                "seed": random.uniform(0, 1000),
            })

    def draw(self, frame, dt, density, speed, opacity):
        if self._empty:
            return frame
        spawn_n = max(1, int(density * 2.0))
        self._spawn(spawn_n)
        acc = np.zeros((self.H, self.W), dtype=np.float32)
        live = []
        for p in self.parts:
            p["life"] += dt * max(0.1, speed)
            n = noise2d(p["x"] * 0.01 + p["seed"], p["y"] * 0.01 + p["life"] * 1.3)
            p["x"] += (p["vx"] + n * 0.22) * max(0.2, speed)
            p["y"] += p["vy"] * max(0.2, speed)
            p["r"] += 0.12 * max(0.2, speed)
            if p["life"] >= p["max"] or p["y"] < self.y0 - 40:
                continue
            live.append(p)
            fade = 1.0 - p["life"] / p["max"]
            alpha = (0.35 + 0.65 * fade) * opacity
            r = max(3, int(p["r"]))
            x, y = int(p["x"]), int(p["y"])
            cv2.circle(acc, (x, y), r, alpha, -1, lineType=cv2.LINE_AA)
        self.parts = live[-260:]
        acc = cv2.GaussianBlur(np.clip(acc, 0, 1), (0, 0), 2.9)
        wisps = noise2d(np.linspace(0, 1, self.W, dtype=np.float32)[None, :] * 7.0 + time.perf_counter() * 0.18,
                        np.linspace(0, 1, self.H, dtype=np.float32)[:, None] * 6.5 + 21.0).astype(np.float32)
        wisps = np.clip((wisps + 1.0) * 0.5, 0, 1)
        acc *= (0.78 + wisps * 0.30) * self.soft_mask
        col = np.array([168, 172, 178], dtype=np.float32)
        a3 = acc[:, :, np.newaxis]
        out = frame.astype(np.float32) * (1.0 - a3) + col * a3
        return np.clip(out, 0, 255).astype(np.uint8)


class AreaCloudState:
    def __init__(self, mask):
        self.mask = mask
        self.H, self.W = mask.shape
        ys, xs = np.where(mask > 128)
        self._empty = len(xs) == 0
        if self._empty:
            return
        self.x0, self.x1 = int(xs.min()), int(xs.max())
        self.y0, self.y1 = int(ys.min()), int(ys.max())
        self.soft_mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 10.0)
        self.clouds = []
        for _ in range(7):
            self.clouds.append(self._new_cloud(False))

    def _new_cloud(self, respawn=True):
        if respawn:
            x = float(self.x0 - random.uniform(20, 120))
            y = random.uniform(self.y0, self.y1)
        else:
            x = random.uniform(self.x0, self.x1)
            y = random.uniform(self.y0, self.y1)
        return {
            "x": x, "y": y,
            "rx": random.uniform(34, 92), "ry": random.uniform(16, 40),
            "vx": random.uniform(0.25, 0.9), "a": random.uniform(0.12, 0.35),
            "seed": random.uniform(0, 999),
        }

    def draw(self, frame, dt, speed, opacity):
        if self._empty:
            return frame
        acc = np.zeros((self.H, self.W), dtype=np.float32)
        for c in self.clouds:
            c["x"] += c["vx"] * max(0.2, speed)
            if c["x"] - c["rx"] > self.x1 + 100:
                c.update(self._new_cloud(True))
            cx, cy = int(c["x"]), int(c["y"])
            cv2.ellipse(acc, (cx, cy), (int(c["rx"]), int(c["ry"])), 0, 0, 360, c["a"] * opacity, -1)
            cv2.ellipse(acc, (cx + int(c["rx"] * 0.25), cy - int(c["ry"] * 0.15)),
                        (max(6, int(c["rx"] * 0.58)), max(4, int(c["ry"] * 0.62))), 0, 0, 360, c["a"] * 0.9 * opacity, -1)
            cv2.ellipse(acc, (cx - int(c["rx"] * 0.28), cy + int(c["ry"] * 0.08)),
                        (max(6, int(c["rx"] * 0.52)), max(4, int(c["ry"] * 0.54))), 0, 0, 360, c["a"] * 0.78 * opacity, -1)
        acc = cv2.GaussianBlur(np.clip(acc, 0, 1), (0, 0), 10.0)
        depth = noise2d(np.linspace(0, 1, self.W, dtype=np.float32)[None, :] * 4.2 + time.perf_counter() * 0.06,
                        np.linspace(0, 1, self.H, dtype=np.float32)[:, None] * 3.8 + 9.7).astype(np.float32)
        depth = np.clip((depth + 1.0) * 0.5, 0, 1)
        acc *= (0.82 + depth * 0.25) * self.soft_mask
        lit = np.clip(acc * 1.15, 0, 1)[:, :, np.newaxis]
        base_col = np.array([205, 210, 218], dtype=np.float32)
        hi_col = np.array([240, 243, 248], dtype=np.float32)
        cloud_col = base_col * (1.0 - lit) + hi_col * lit
        a3 = acc[:, :, np.newaxis]
        out = frame.astype(np.float32) * (1.0 - a3) + cloud_col * a3
        return np.clip(out, 0, 255).astype(np.uint8)


class AreaFireState:
    def __init__(self, mask):
        self.mask = mask
        self.H, self.W = mask.shape
        ys, xs = np.where(mask > 128)
        self._empty = len(xs) == 0
        if self._empty:
            return
        self.x0, self.x1 = int(xs.min()), int(xs.max())
        self.y0, self.y1 = int(ys.min()), int(ys.max())
        self.soft_mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 4.5)
        self.flames = []

    def _spawn(self, n):
        for _ in range(n):
            self.flames.append({
                "x": random.uniform(self.x0, self.x1),
                "y": random.uniform(self.y1 - 8, self.y1 + 6),
                "r": random.uniform(4, 13),
                "vx": random.uniform(-0.25, 0.25),
                "vy": random.uniform(-2.0, -0.8),
                "life": 0.0,
                "max": random.uniform(0.55, 1.5),
                "seed": random.uniform(0, 1000),
            })

    def draw(self, frame, dt, intensity, speed):
        if self._empty:
            return frame
        self._spawn(max(1, int(intensity * 0.18)))
        red = np.zeros((self.H, self.W), dtype=np.float32)
        yel = np.zeros((self.H, self.W), dtype=np.float32)
        core = np.zeros((self.H, self.W), dtype=np.float32)
        live = []
        for f in self.flames:
            f["life"] += dt * max(0.3, speed)
            flow = noise2d(f["x"] * 0.018 + f["seed"], f["y"] * 0.014 + f["life"] * 3.1)
            f["x"] += (f["vx"] + flow * 0.35) * max(0.3, speed)
            f["y"] += f["vy"] * max(0.3, speed)
            if f["life"] >= f["max"] or f["y"] < self.y0 - 45:
                continue
            live.append(f)
            k = 1.0 - (f["life"] / f["max"])
            r = max(2, int(f["r"] * (0.7 + 0.5 * k)))
            x, y = int(f["x"]), int(f["y"])
            cv2.circle(red, (x, y), r, 0.85 * k, -1, lineType=cv2.LINE_AA)
            cv2.circle(yel, (x, y), max(1, int(r * 0.45)), 0.7 * k, -1, lineType=cv2.LINE_AA)
            if k > 0.35:
                cv2.circle(core, (x, y), max(1, int(r * 0.22)), 0.8 * (k - 0.2), -1, lineType=cv2.LINE_AA)
        self.flames = live[-300:]
        red = cv2.GaussianBlur(np.clip(red, 0, 1), (0, 0), 2.0) * self.soft_mask
        yel = cv2.GaussianBlur(np.clip(yel, 0, 1), (0, 0), 1.25) * self.soft_mask
        core = cv2.GaussianBlur(np.clip(core, 0, 1), (0, 0), 0.9) * self.soft_mask
        out = frame.astype(np.float32)
        out[:, :, 0] = np.clip(out[:, :, 0] + red * 235 + yel * 66 + core * 20, 0, 255)
        out[:, :, 1] = np.clip(out[:, :, 1] + red * 115 + yel * 205 + core * 90, 0, 255)
        out[:, :, 2] = np.clip(out[:, :, 2] + yel * 72 + core * 210, 0, 255)
        return out.astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
#  LAYER SYSTEM  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def _blend_layers(base, layer, alpha, mode):
    bH, bW = base.shape[:2]; lH, lW = layer.shape[:2]
    if (lH, lW) != (bH, bW): layer = cv2.resize(layer, (bW, bH), interpolation=cv2.INTER_LINEAR)
    b    = base.astype(np.float32) / 255.0; lRGB = layer[:, :, :3].astype(np.float32) / 255.0; lA = layer[:, :, 3:4].astype(np.float32) / 255.0
    if   mode == "Normal":     blended = lRGB
    elif mode == "Multiply":   blended = b * lRGB
    elif mode == "Screen":     blended = 1.0 - (1.0-b)*(1.0-lRGB)
    elif mode == "Overlay":
        low  = 2.0*b*lRGB; high = 1.0-2.0*(1.0-b)*(1.0-lRGB); blended = np.where(b < 0.5, low, high)
    elif mode == "Soft Light": blended = (1.0-2.0*lRGB)*b**2 + 2.0*lRGB*b
    elif mode == "Hard Light":
        low  = 2.0*b*lRGB; high = 1.0-2.0*(1.0-b)*(1.0-lRGB); blended = np.where(lRGB < 0.5, low, high)
    elif mode == "Add":        blended = np.clip(b+lRGB, 0, 1)
    elif mode == "Difference": blended = np.abs(b-lRGB)
    else:                      blended = lRGB
    effective_alpha = lA * alpha; result = b*(1.0-effective_alpha) + blended*effective_alpha
    return np.clip(result*255.0, 0, 255).astype(np.uint8)


class LayerSource:
    def __init__(self, path):
        self.path = path
        self.is_video = path.lower().endswith(('.mp4','.avi','.mov','.mkv','.webm'))
        self._cap = None; self._png_rgba = None
        self._duration = 0.0; self._fps = 30.0; self._frame_count = 0
        self._last_idx = -1; self._cache = None
        self._load()
    def _load(self):
        if self.is_video:
            self._cap = cv2.VideoCapture(self.path)
            if not self._cap.isOpened(): raise IOError(f"Cannot open video: {self.path}")
            self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
            self._frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self._duration = self._frame_count / self._fps
        else:
            pil = Image.open(self.path).convert("RGBA"); self._png_rgba = np.array(pil)
    def get_frame(self, t, W, H):
        if not self.is_video:
            frame = self._png_rgba
        else:
            if self._duration <= 0: return np.zeros((H,W,4),dtype=np.uint8)
            looped_t = math.fmod(t, self._duration); idx = int(looped_t * self._fps)
            idx = max(0, min(idx, self._frame_count-1))
            if idx == self._last_idx and self._cache is not None: frame = self._cache
            else:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, idx); ret, bgr = self._cap.read()
                if not ret: self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0); ret, bgr = self._cap.read()
                if not ret: return np.zeros((H,W,4),dtype=np.uint8)
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                frame = np.dstack([rgb, np.full(rgb.shape[:2],255,dtype=np.uint8)])
                self._last_idx = idx; self._cache = frame
        fH, fW = frame.shape[:2]
        if (fH,fW) != (H,W): frame = cv2.resize(frame,(W,H),interpolation=cv2.INTER_LINEAR)
        return frame
    def label(self):
        name = os.path.basename(self.path); kind = "MP4" if self.is_video else "PNG"
        return f"[{kind}] {name}"
    def release(self):
        if self._cap: self._cap.release(); self._cap = None


# ─────────────────────────────────────────────────────────────────────────────
#  All original animation classes (unchanged from v4)
# ─────────────────────────────────────────────────────────────────────────────

class FlowerParticle:
    def __init__(self,patch,ox,oy,H,W,speed,fade_frac,total_frames,delay):
        self.patch=patch;self.origin_x=ox;self.origin_y=oy;self.H,self.W=H,W
        self.fade_frac=fade_frac;self.delay=delay;self.total=total_frames
        ph=patch.shape[0];self.travel_dist=(H+ph)-oy
        base_vy=random.uniform(1.8,3.2)*speed
        self.travel_frames=max(1,min(int(self.travel_dist/base_vy),total_frames-5))
        self.vy=self.travel_dist/self.travel_frames;self.vx=random.uniform(-0.3,0.3)*speed
        self.sway_amp=random.uniform(4,18);self.sway_freq=random.uniform(0.015,0.05)
        self.sway_phase=random.uniform(0,math.tau);self.angle0=random.uniform(0,360)
        self.spin=random.uniform(-1.4,1.4)*speed
    def draw(self,canvas,frame_idx):
        local=(frame_idx-self.delay)%self.total
        if local>=self.travel_frames:return
        t=local;y=self.origin_y+self.vy*t
        x=self.origin_x+self.vx*t+self.sway_amp*math.sin(self.sway_freq*t+self.sway_phase)
        angle=self.angle0+self.spin*t;progress=t/self.travel_frames;alpha_mul=1.0
        if progress>(1.0-self.fade_frac) and self.fade_frac>0:alpha_mul=(1.0-progress)/self.fade_frac
        elif progress<self.fade_frac and self.fade_frac>0:alpha_mul=progress/self.fade_frac
        M=cv2.getRotationMatrix2D((self.patch.shape[1]/2,self.patch.shape[0]/2),angle,1.0)
        rotated=cv2.warpAffine(self.patch,M,(self.patch.shape[1],self.patch.shape[0]),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0,0))
        if alpha_mul<0.99:rotated[:,:,3]=(rotated[:,:,3]*max(0.0,alpha_mul)).astype(np.uint8)
        px,py=int(x)-rotated.shape[1]//2,int(y)-rotated.shape[0]//2;bH,bW=canvas.shape[:2];oh,ow=rotated.shape[:2]
        x0,y0=max(px,0),max(py,0);x1,y1=min(px+ow,bW),min(py+oh,bH)
        if x1<=x0 or y1<=y0:return
        ox0,oy0=x0-px,y0-py;src=rotated[oy0:oy0+(y1-y0),ox0:ox0+(x1-x0)].astype(np.float32);dst=canvas[y0:y1,x0:x1].astype(np.float32)
        sa=src[:,:,3:4]/255.0;da=dst[:,:,3:4]/255.0;oa=sa+da*(1-sa);oas=np.where(oa>0,oa,1.0)
        rgb=(src[:,:,:3]*sa+dst[:,:,:3]*da*(1-sa))/oas;canvas[y0:y1,x0:x1]=np.concatenate([rgb,oa*255],axis=2).clip(0,255).astype(np.uint8)

COLOR_PRESETS={"pink":[140,175,40,255,120,255],"red":[0,10,60,255,100,255],"red2":[170,180,60,255,100,255],"orange":[5,25,80,255,120,255],"yellow":[20,35,80,255,120,255],"white":[0,180,0,60,180,255],"purple":[125,155,40,255,80,255],"blue":[95,130,50,255,80,255]}

def _get_hsv_mask(img_bgr,color_name):
    extra_lo=extra_hi=None;pr=COLOR_PRESETS.get(color_name.lower(),COLOR_PRESETS["pink"])
    lo=np.array([pr[0],pr[2],pr[4]]);hi=np.array([pr[1],pr[3],pr[5]])
    if color_name.lower()=="red":pr2=COLOR_PRESETS["red2"];extra_lo=np.array([pr2[0],pr2[2],pr2[4]]);extra_hi=np.array([pr2[1],pr2[3],pr2[5]])
    hsv=cv2.cvtColor(img_bgr,cv2.COLOR_BGR2HSV);mask=cv2.inRange(hsv,lo,hi)
    if extra_lo is not None:mask=cv2.bitwise_or(mask,cv2.inRange(hsv,extra_lo,extra_hi))
    return mask,lo,hi,extra_lo,extra_hi


class FallingParticles:
    def __init__(self,mask_full,static_np,fall_delay_max=5.0,tile_size=None,repeat=False,repeat_min=2.0,repeat_max=8.0):
        ys,xs=np.where(mask_full>128)
        if len(xs)==0:self.particles=[];self._template=[];self._all_done=True;self.repeat=False;return
        self.H,self.W=static_np.shape[:2];self.fall_delay_max=fall_delay_max;self.repeat=repeat;self.repeat_min=repeat_min;self.repeat_max=repeat_max;self._next_cycle_t=None;self._waiting=False;self._all_done=False
        y_min,y_max=int(ys.min()),int(ys.max());x_min,x_max=int(xs.min()),int(xs.max())
        if tile_size is None:area=max(1,(y_max-y_min+1)*(x_max-x_min+1));tile_size=max(8,int(math.sqrt(area/60)))
        self._template=[]
        for ty in range(y_min,y_max+1,tile_size):
            for tx in range(x_min,x_max+1,tile_size):
                x0,y0=tx,ty;x1=min(self.W,tx+tile_size);y1=min(self.H,ty+tile_size)
                if x1<=x0 or y1<=y0:continue
                tile_mask=mask_full[y0:y1,x0:x1]
                if not tile_mask.any():continue
                tile_img=static_np[y0:y1,x0:x1].copy();ph,pw=tile_img.shape[:2]
                patch_rgba=np.zeros((ph,pw,4),dtype=np.uint8);patch_rgba[:,:,:3]=tile_img;patch_rgba[:,:,3]=tile_mask
                cx=x0+pw//2;cy=y0+ph//2;self._template.append({'ox':float(cx),'oy':float(cy),'patch':patch_rgba,'half':max(pw,ph)//2})
        self.particles=[];self._spawn_cycle(0.0)
    def _spawn_cycle(self,t_now):
        self.particles=[]
        for tmpl in self._template:
            self.particles.append({**tmpl,'x':tmpl['ox'],'y':tmpl['oy'],'vx':random.uniform(-0.4,0.4),'vy':random.uniform(0.6,2.2),'rot':random.uniform(0,360),'rot_spd':random.uniform(-3.0,3.0),'amp':random.uniform(6,20),'freq':random.uniform(0.4,1.4),'phase':random.uniform(0,6.28),'start_t':t_now+random.uniform(0.0,max(0.01,self.fall_delay_max)),'active':False,'done':False,'alpha':random.uniform(0.82,1.0),'fade_alpha':1.0})
        self._waiting=False;self._all_done=False
    @property
    def all_done(self):return self._all_done
    def update(self,t,dt,spd):
        if self._waiting:
            if self.repeat and t>=self._next_cycle_t:self._spawn_cycle(t)
            return
        cycle_all_done=True
        for p in self.particles:
            if p['done']:continue
            if t<p['start_t']:cycle_all_done=False;continue
            cycle_all_done=False
            if not p['active']:p['active']=True;p['x']=p['ox'];p['y']=p['oy']
            p['x']+=p['vx']*spd+math.sin(t*p['freq']+p['phase'])*p['amp']*dt;p['y']+=p['vy']*spd;p['rot']+=p['rot_spd']*spd
            fade_start=self.H*0.85
            if p['y']>fade_start:p['fade_alpha']=max(0.0,1.0-(p['y']-fade_start)/(self.H*0.15))
            else:p['fade_alpha']=1.0
            if p['y']-p['half']>self.H+20:p['done']=True
        if cycle_all_done or all(p['done'] for p in self.particles):
            if self.repeat:interval=random.uniform(self.repeat_min,max(self.repeat_min,self.repeat_max));self._next_cycle_t=t+interval;self._waiting=True;self._all_done=False
            else:self._all_done=True
    def _rotate_patch(self,patch_rgba,angle_deg):
        h,w=patch_rgba.shape[:2];M=cv2.getRotationMatrix2D((w/2,h/2),angle_deg,1.0)
        return cv2.warpAffine(patch_rgba,M,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0,0))
    def draw(self,frame):
        out=frame.copy()
        for p in self.particles:
            if not p['active'] or p['done']:continue
            rotated=self._rotate_patch(p['patch'],p['rot']);ph,pw=rotated.shape[:2]
            dx=int(p['x'])-pw//2;dy=int(p['y'])-ph//2;fx0=max(0,dx);fy0=max(0,dy);fx1=min(self.W,dx+pw);fy1=min(self.H,dy+ph)
            if fx1<=fx0 or fy1<=fy0:continue
            px0=fx0-dx;py0=fy0-dy;px1=px0+(fx1-fx0);py1=py0+(fy1-fy0);patch_roi=rotated[py0:py1,px0:px1];frame_roi=out[fy0:fy1,fx0:fx1]
            alpha_ch=(patch_roi[:,:,3:4].astype(np.float32)/255.0)*p['alpha']*p['fade_alpha']
            blended=frame_roi.astype(np.float32)*(1-alpha_ch)+patch_roi[:,:,:3].astype(np.float32)*alpha_ch
            out[fy0:fy1,fx0:fx1]=blended.astype(np.uint8)
        return out


class LeafWindState:
    LEAF_COLORS=[(34,120,34),(85,160,20),(200,160,30),(210,100,20),(175,45,20),(130,70,25),(230,200,50),(50,150,60),(220,130,10)]
    def __init__(self,mask,n=55):
        self.mask=mask;self.H,self.W=mask.shape;ys,xs=np.where(mask>128);self.leaves=[]
        if len(xs)==0:return
        self.x_min=int(xs.min());self.x_max=int(xs.max());self.y_min=int(ys.min());self.y_max=int(ys.max())
        for _ in range(n):self.leaves.append(self._new_leaf(respawn=False))
    def _new_leaf(self,respawn=True):
        if respawn:
            if random.random()<0.7:x=float(self.x_min)-random.uniform(10,80);y=random.uniform(float(self.y_min)-20,float(self.y_max)+20)
            else:x=random.uniform(float(self.x_min),float(self.x_max));y=float(self.y_min)-random.uniform(10,60)
        else:x=random.uniform(float(self.x_min),float(self.x_max));y=random.uniform(float(self.y_min),float(self.y_max))
        return {'x':x,'y':y,'vx':random.uniform(0.7,2.6),'vy':random.uniform(0.05,0.7),'rot':random.uniform(0,360),'rot_spd':random.uniform(-7,7),'size':random.randint(7,18),'color':random.choice(self.LEAF_COLORS),'alpha':random.uniform(0.65,0.96),'sway_amp':random.uniform(0.4,2.0),'sway_freq':random.uniform(0.7,2.8),'sway_phase':random.uniform(0,6.28),'type':random.randint(0,2)}
    def update(self,t,dt,spd):
        for p in self.leaves:
            sway=math.sin(t*p['sway_freq']+p['sway_phase'])*p['sway_amp'];p['x']+=(p['vx']+sway*0.25)*spd;p['y']+=(p['vy']+abs(sway)*0.1)*spd;p['rot']+=p['rot_spd']*spd
            if p['x']>self.x_max+80 or p['y']>self.y_max+80:p.update(self._new_leaf(respawn=True))
    def _blit_patch(self,out,patch,x,y):
        ph,pw=patch.shape[:2];dx=int(x)-pw//2;dy=int(y)-ph//2;fx0=max(0,dx);fy0=max(0,dy);fx1=min(self.W,dx+pw);fy1=min(self.H,dy+ph)
        if fx1<=fx0 or fy1<=fy0:return
        px0=fx0-dx;py0=fy0-dy;patch_roi=patch[py0:py0+(fy1-fy0),px0:px0+(fx1-fx0)];frame_roi=out[fy0:fy1,fx0:fx1]
        a=patch_roi[:,:,3:4].astype(np.float32)/255.0;out[fy0:fy1,fx0:fx1]=(frame_roi.astype(np.float32)*(1-a)+patch_roi[:,:,:3].astype(np.float32)*a).astype(np.uint8)
    def draw(self,frame):
        out=frame.copy()
        for p in self.leaves:
            s=p['size'];pad=s*3;tmp=np.zeros((pad*2,pad*2,4),dtype=np.uint8);cx,cy=pad,pad
            col3=(*p['color'],230);darker=(max(0,p['color'][0]-45),max(0,p['color'][1]-45),max(0,p['color'][2]-45),190)
            ltype=p['type']
            if ltype==0:cv2.ellipse(tmp,(cx,cy),(s,max(3,s//2)),0,0,360,col3,-1)
            elif ltype==1:pts=np.array([[cx,cy-s],[cx+s//2,cy],[cx,cy+s],[cx-s//2,cy]],np.int32);cv2.fillPoly(tmp,[pts],col3)
            else:cv2.circle(tmp,(cx,cy),s,col3,-1);cv2.circle(tmp,(cx,cy+s//3),s//3,(0,0,0,0),-1)
            cv2.line(tmp,(cx-s,cy),(cx+s,cy),darker,1)
            for sign in(-1,1):vx=int(cx+s*0.5);vy=int(cy+sign*s*0.35);cv2.line(tmp,(cx,cy),(vx,vy),darker,1)
            M=cv2.getRotationMatrix2D((float(cx),float(cy)),p['rot'],1.0);rotated=cv2.warpAffine(tmp,M,(pad*2,pad*2),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0,0))
            rotated[:,:,3]=(rotated[:,:,3].astype(np.float32)*p['alpha']).astype(np.uint8);self._blit_patch(out,rotated,p['x'],p['y'])
        return out


class ThunderState:
    def __init__(self):self.bolts=[];self.flash=0.0;self.next_bolt=random.uniform(0.5,2.0);self.last_t=0.0
    def update(self,t):
        dt=t-self.last_t;self.last_t=t;self.flash=max(0.0,self.flash-dt*4)
        if t>self.next_bolt:self._new_bolt();self.next_bolt=t+random.uniform(0.8,3.5)
    def _new_bolt(self):
        self.flash=1.0;x=random.randint(50,750);segs=[];cy=0;cx=x
        while cy<600:
            nx=cx+random.randint(-40,40);ny=cy+random.randint(20,60);segs.append(((cx,cy),(nx,ny)))
            if random.random()<0.3:
                bx,by=nx,ny
                for _ in range(random.randint(2,5)):nbx=bx+random.randint(-30,30);nby=by+random.randint(10,30);segs.append(((bx,by),(nbx,nby)));bx,by=nbx,nby
            cx,cy=nx,ny
        self.bolts.append({'segs':segs,'life':0.25,'age':0.0})
    def draw(self,frame,mask,dt):
        out=frame.copy()
        if self.flash>0:
            H,W=out.shape[:2];cx,cy=W/2.0,H/2.0;ys_,xs_=np.mgrid[0:H,0:W].astype(np.float32)
            vignette=1.0-0.45*np.clip(np.sqrt(((xs_-cx)/cx)**2+((ys_-cy)/cy)**2),0,1)
            intensity=self.flash*0.65*vignette[:,:,np.newaxis];flash_col=np.array([215,230,255],dtype=np.float32)
            out=np.clip(out.astype(np.float32)*(1-intensity)+flash_col*intensity,0,255).astype(np.uint8)
        alive=[]
        for b in self.bolts:
            b['age']+=dt;alpha=max(0.0,1.0-b['age']/b['life'])
            if alpha>0:
                for (x1,y1),(x2,y2) in b['segs']:col=(int(200*alpha),int(220*alpha),int(255*alpha));cv2.line(out,(x1,y1),(x2,y2),col,2,cv2.LINE_AA);cv2.line(out,(x1,y1),(x2,y2),(255,255,255),1,cv2.LINE_AA)
                alive.append(b)
        self.bolts=alive;return out


class BokehState:
    def __init__(self,mask,n=80):
        self.H,self.W=mask.shape;ys,xs=np.where(mask>128);self.particles=[]
        if len(xs)==0:return
        for _ in range(n):
            idx=random.randint(0,len(xs)-1);self.particles.append({'x':float(xs[idx]),'y':float(ys[idx]),'r':random.uniform(4,18),'vx':random.uniform(-0.3,0.3),'vy':random.uniform(-0.5,-0.1),'life':random.uniform(0,1.0),'max_life':random.uniform(1.5,4.0),'col':(random.randint(150,255),random.randint(100,200),random.randint(200,255))})
    def update(self,dt,spd):
        for p in self.particles:
            p['life']+=dt*spd;p['x']+=p['vx']*spd;p['y']+=p['vy']*spd
            if p['life']>=p['max_life']:p['life']=0.0;p['vy']=random.uniform(-0.5,-0.1)
    def draw(self,frame):
        out=frame.copy()
        for p in self.particles:
            alpha=math.sin(math.pi*p['life']/p['max_life'])
            if alpha<=0:continue
            x,y,r=int(p['x']),int(p['y']),int(p['r'])
            if x<0 or x>=self.W or y<0 or y>=self.H:continue
            overlay=out.copy();cv2.circle(overlay,(x,y),r,p['col'],-1);out=cv2.addWeighted(out,1-alpha*0.5,overlay,alpha*0.5,0)
        return out


class PlasmaState:
    def __init__(self,mask):self.mask=mask;self.H,self.W=mask.shape
    def draw(self,frame,t,amp):
        out=frame.copy();m=(self.mask>128)
        if not m.any():return out
        ys,xs=np.where(m);xn=xs/self.W;yn=ys/self.H
        v=(np.sin(xn*10+t*2)*0.5+np.sin(yn*8-t*1.5)*0.5+np.sin((xn+yn)*6+t)*0.5+np.sin(np.sqrt(xn**2+yn**2)*12-t*2)*0.5);v=(v+2)/4
        r=(np.sin(v*math.pi*2)*127+128).astype(np.uint8);g=(np.sin(v*math.pi*2+2.09)*127+128).astype(np.uint8);b=(np.sin(v*math.pi*2+4.19)*127+128).astype(np.uint8)
        alpha=amp/50.0*0.7;region=out[ys,xs].astype(np.float32);plasma=np.stack([r,g,b],axis=1).astype(np.float32)
        out[ys,xs]=(region*(1-alpha)+plasma*alpha).astype(np.uint8);return out


class TwinkleState:
    SPECTRAL_COLORS=[(155,176,255),(170,191,255),(202,215,255),(248,247,255),(255,244,234),(255,210,161),(255,168,108)]
    SPECTRAL_WEIGHTS=[1,3,6,10,12,10,8]
    def __init__(self,mask,n=120):
        self.mask=mask;self.H,self.W=mask.shape;ys,xs=np.where(mask>128);self.stars=[]
        if len(xs)==0:return
        total_w=sum(self.SPECTRAL_WEIGHTS);cum=[sum(self.SPECTRAL_WEIGHTS[:i+1])/total_w for i in range(len(self.SPECTRAL_WEIGHTS))]
        for _ in range(n):
            idx=random.randint(0,len(xs)-1);r_=random.random();stype=next(i for i,c in enumerate(cum) if r_<=c)
            base_col=self.SPECTRAL_COLORS[stype];hot_col=self.SPECTRAL_COLORS[max(0,stype-1)]
            glow=random.randint(2,12);n_spikes=random.choice([4,4,6]);spike_rot=random.uniform(0,math.pi/n_spikes)
            f1=random.uniform(1.8,5.0);f2=random.uniform(0.5,1.8);f3=random.uniform(8.0,18.0)
            p1=random.uniform(0,math.tau);p2=random.uniform(0,math.tau);p3=random.uniform(0,math.tau)
            self.stars.append({'x':int(xs[idx]),'y':int(ys[idx]),'base_col':np.array(base_col,dtype=np.float32),'hot_col':np.array(hot_col,dtype=np.float32),'glow':glow,'n_spikes':n_spikes,'spike_rot':spike_rot,'f1':f1,'f2':f2,'f3':f3,'p1':p1,'p2':p2,'p3':p3,'base':random.uniform(0.4,0.9),'amp':random.uniform(0.10,0.45),'sparkle_next':random.uniform(3.0,12.0),'sparkle_t':-99,'_glow_patch':self._make_glow_patch(base_col,glow)})
    @staticmethod
    def _make_glow_patch(col,r):
        sz=r*6+1;cx=sz//2;ys_=np.arange(sz,dtype=np.float32)-cx;xs_=np.arange(sz,dtype=np.float32)-cx
        PX,PY=np.meshgrid(xs_,ys_);d2=PX**2+PY**2
        core=np.exp(-d2/(2*(r*0.30)**2));halo=np.exp(-d2/(2*(r*0.90)**2))*0.28
        return np.clip(core+halo,0,1)[:,:,np.newaxis]*np.array(col,dtype=np.float32)
    @staticmethod
    def _draw_spikes(out_f,x,y,glow_r,n_spikes,spike_rot,col,bright,W,H):
        spike_len=glow_r*(3.5+bright*3.0)
        for k in range(n_spikes):
            angle=spike_rot+k*math.pi/n_spikes
            for sign in(1,-1):
                a=angle+(0 if sign==1 else math.pi);steps=max(8,int(spike_len))
                for s in range(steps):
                    frac=s/steps;fade=(1.0-frac)**2.0*bright*0.65
                    rx=int(x+math.cos(a)*spike_len*frac);ry=int(y+math.sin(a)*spike_len*frac)
                    for wx in range(-1,2):
                        for wy in range(-1,2):
                            if abs(wx)+abs(wy)>1:continue
                            px_=rx+wx;py_=ry+wy
                            if 0<=px_<W and 0<=py_<H:out_f[py_,px_]=np.clip(out_f[py_,px_]+col*fade,0,255)
    def draw(self,frame,t):
        out=frame.astype(np.float32);H,W=out.shape[:2]
        for s in self.stars:
            sc=(math.sin(s['f1']*t+s['p1'])*0.55+math.sin(s['f2']*t+s['p2'])*0.30+math.sin(s['f3']*t+s['p3'])*0.15)
            bright=max(0.0,min(1.0,s['base']+sc*s['amp']))
            if bright<0.02:continue
            t_mix=max(0.0,(bright-s['base'])/max(0.01,s['amp']));col=s['base_col']*(1-t_mix*0.4)+s['hot_col']*(t_mix*0.4)
            if t>=s['sparkle_next']:s['sparkle_t']=t;s['sparkle_next']=t+random.uniform(4.0,18.0)
            sparkle_age=t-s['sparkle_t']
            if sparkle_age<0.35:bright=min(1.0,bright+math.sin(math.pi*sparkle_age/0.35)*0.9)
            x,y=s['x'],s['y'];patch=s['_glow_patch'];ph,pw=patch.shape[:2]
            dx_=x-pw//2;dy_=y-ph//2;fx0=max(0,dx_);fy0=max(0,dy_);fx1=min(W,dx_+pw);fy1=min(H,dy_+ph)
            if fx1>fx0 and fy1>fy0:
                px0=fx0-dx_;py0=fy0-dy_;tinted=patch[py0:py0+(fy1-fy0),px0:px0+(fx1-fx0)]*(col/255.0)
                out[fy0:fy1,fx0:fx1]=np.clip(out[fy0:fy1,fx0:fx1]+tinted*bright,0,255)
            if bright>0.25:self._draw_spikes(out,x,y,s['glow'],s['n_spikes'],s['spike_rot'],col,bright,W,H)
        return out.astype(np.uint8)


class ScrollFlowState:
    def __init__(self,mask,static_np):
        self.mask=mask;self.H,self.W=mask.shape;ys,xs=np.where(mask>128)
        if len(xs)==0:self._empty=True;return
        self._empty=False;y0,y1=int(ys.min()),int(ys.max())+1;x0,x1=int(xs.min()),int(xs.max())+1
        self._y0,self._y1=y0,y1;self._x0,self._x1=x0,x1;self.tile=static_np[y0:y1,x0:x1].copy();self.tile_mask=mask[y0:y1,x0:x1].copy();self.crop_h=y1-y0;self.crop_w=x1-x0
        lxs=np.arange(self.crop_w,dtype=np.float32);lys=np.arange(self.crop_h,dtype=np.float32);self._lx,self._ly=np.meshgrid(lxs,lys)
    def draw(self,frame,t,spd,direction,stretch):
        if self._empty:return frame
        rad=math.radians(direction);dx=math.cos(rad);dy=math.sin(rad);scroll=t*spd*60.0;ox=dx*scroll;oy=dy*scroll
        lx=self._lx.copy();ly=self._ly.copy()
        if stretch>0.01:
            pdx,pdy=-dy,dx;perp=lx*pdx+ly*pdy;wave=np.sin(perp*0.04+t*2.0).astype(np.float32)*float(stretch)*6.0;lx+=dx*wave;ly+=dy*wave
        map_x=np.mod(lx+ox,self.crop_w).astype(np.float32);map_y=np.mod(ly+oy,self.crop_h).astype(np.float32)
        scrolled_tile=cv2.remap(self.tile,map_x,map_y,interpolation=cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)
        out=frame.copy();y0,y1=self._y0,self._y1;x0,x1=self._x0,self._x1
        mask_crop=self.tile_mask.astype(np.float32)/255.0;mask_crop=cv2.GaussianBlur(mask_crop,(0,0),4.0);mask3=mask_crop[:,:,np.newaxis]
        roi=out[y0:y1,x0:x1].astype(np.float32);out[y0:y1,x0:x1]=(roi*(1.0-mask3)+scrolled_tile.astype(np.float32)*mask3).astype(np.uint8)
        return out


class FlowerFallState:
    CYCLE_SECS=6.0
    def __init__(self,mask,static_np,speed=1.5,total_secs=6.0,repeat=True):
        self.H,self.W=static_np.shape[:2];self.repeat=repeat;self.speed=speed;self._t_last=0.0;self._cycle_done=False
        total_frames=max(30,int(total_secs*30));self.total_frames=total_frames
        img_bgr=cv2.cvtColor(static_np,cv2.COLOR_RGB2BGR);painted=mask>128;best_patches=[];best_count=0
        for cname in COLOR_PRESETS:
            if cname=="red2":continue
            cmask,*_=_get_hsv_mask(img_bgr,cname);combined=cv2.bitwise_and(cmask,cmask,mask=mask)
            n_labels,labels,stats,centroids=cv2.connectedComponentsWithStats(combined,connectivity=8);patches=[]
            for lbl in range(1,n_labels):
                area=stats[lbl,cv2.CC_STAT_AREA]
                if area<30:continue
                x0=stats[lbl,cv2.CC_STAT_LEFT];y0=stats[lbl,cv2.CC_STAT_TOP];bw=stats[lbl,cv2.CC_STAT_WIDTH];bh=stats[lbl,cv2.CC_STAT_HEIGHT];x1,y1=x0+bw,y0+bh
                patch_rgba=np.zeros((bh,bw,4),dtype=np.uint8);patch_rgba[:,:,:3]=static_np[y0:y1,x0:x1];patch_rgba[:,:,3]=combined[y0:y1,x0:x1];patches.append((patch_rgba,float(centroids[lbl][0]),float(centroids[lbl][1])))
            if len(patches)>best_count:best_count=len(patches);best_patches=patches
        if not best_patches:
            ys,xs=np.where(painted)
            if len(xs)>0:
                y_min,y_max=int(ys.min()),int(ys.max());x_min,x_max=int(xs.min()),int(xs.max());tile_size=max(12,int(math.sqrt(max(1,(y_max-y_min)*(x_max-x_min))/40)))
                for ty in range(y_min,y_max,tile_size):
                    for tx in range(x_min,x_max,tile_size):
                        tx1=min(self.W,tx+tile_size);ty1=min(self.H,ty+tile_size);tile_mask=mask[ty:ty1,tx:tx1]
                        if not tile_mask.any():continue
                        patch_rgba=np.zeros((ty1-ty,tx1-tx,4),dtype=np.uint8);patch_rgba[:,:,:3]=static_np[ty:ty1,tx:tx1];patch_rgba[:,:,3]=tile_mask;best_patches.append((patch_rgba,float(tx+(tx1-tx)/2),float(ty+(ty1-ty)/2)))
        fade_frac=0.15;self.particles=[]
        for patch_rgba,cx_f,cy_f in best_patches:
            delay=random.randint(0,max(1,total_frames//3));self.particles.append(FlowerParticle(patch=patch_rgba,ox=cx_f,oy=cy_f,H=self.H,W=self.W,speed=speed,fade_frac=fade_frac,total_frames=total_frames,delay=delay))
        self._frame_idx=0
    def update(self,t,dt,spd):self._frame_idx=int(t*30.0*spd)
    def draw(self,frame):
        canvas=cv2.cvtColor(frame,cv2.COLOR_RGB2RGBA).astype(np.uint8)
        for fp in self.particles:fp.draw(canvas,self._frame_idx)
        return cv2.cvtColor(canvas,cv2.COLOR_RGBA2RGB)


class CloudMovingState:
    COLOR_MAP={"White":(255,255,255),"Light Gray":(200,215,230),"Storm Gray":(130,142,155),"Sunset Gold":(255,205,110),"Dusk Pink":(255,168,175),"Night Blue":(105,122,205)}
    COLOR_NAMES=["White","Light Gray","Storm Gray","Sunset Gold","Dusk Pink","Night Blue"]
    def __init__(self,mask,n=10,color_name="White"):
        self.mask=mask;self.H,self.W=mask.shape;self.color=self.COLOR_MAP.get(color_name,(255,255,255));ys,xs=np.where(mask>128);self.clouds=[]
        if len(xs)==0:self._empty=True;return
        self._empty=False;self.x_min=int(xs.min());self.x_max=int(xs.max());self.y_min=int(ys.min());self.y_max=int(ys.max())
        for _ in range(n):self.clouds.append(self._new_cloud(respawn=False))
    @staticmethod
    def _render_patch(w,h,color,base_opacity):
        pad=max(28,int(max(w,h)*0.28));pw=w+pad*2;ph=h+pad*2;acc=np.zeros((ph,pw),dtype=np.float32);cx,cy=pw//2,ph//2
        for _ in range(random.randint(5,9)):
            bx=int(cx+random.uniform(-w*0.38,w*0.38));by=int(cy+random.uniform(-h*0.22,h*0.22));rx=max(8,int(random.uniform(w*0.18,w*0.44)));ry=max(6,int(random.uniform(h*0.22,h*0.52)))
            tmp=np.zeros((ph,pw),dtype=np.float32);cv2.ellipse(tmp,(bx,by),(rx,ry),0,0,360,1.0,-1);sig=max(3.5,min(rx,ry)*0.38);tmp=cv2.GaussianBlur(tmp,(0,0),sig);acc=np.clip(acc+tmp,0,1)
        acc=cv2.GaussianBlur(acc,(0,0),3.0);acc=np.clip(acc,0,1)*base_opacity;patch=np.zeros((ph,pw,4),dtype=np.uint8)
        patch[:,:,0]=color[0];patch[:,:,1]=color[1];patch[:,:,2]=color[2];patch[:,:,3]=(acc*255).astype(np.uint8);return patch
    def _new_cloud(self,respawn=True,direction=90.0):
        w=random.randint(90,240);h=random.randint(40,110);scale=random.uniform(0.7,1.40);w=max(30,int(w*scale));h=max(18,int(h*scale))
        base_op=random.uniform(0.55,0.95);patch=self._render_patch(w,h,self.color,base_op);ph,pw=patch.shape[:2]
        if respawn:
            rad=math.radians(direction);dx_,dy_=math.cos(rad),math.sin(rad)
            if abs(dx_)>=abs(dy_):x=float(self.x_min-pw-10) if dx_>0 else float(self.x_max+pw+10);y=random.uniform(float(self.y_min),float(self.y_max))
            else:y=float(self.y_min-ph-10) if dy_>0 else float(self.y_max+ph+10);x=random.uniform(float(self.x_min),float(self.x_max))
        else:x=random.uniform(float(self.x_min),float(self.x_max));y=random.uniform(float(self.y_min),float(self.y_max))
        return {'x':x,'y':y,'patch':patch,'pw':pw,'ph':ph,'speed_mul':random.uniform(0.50,1.55),'sway_amp':random.uniform(0.20,1.20),'sway_freq':random.uniform(0.05,0.22),'sway_phase':random.uniform(0,math.tau)}
    def update(self,t,dt,spd,direction,n_target):
        if self._empty:return
        while len(self.clouds)<n_target:self.clouds.append(self._new_cloud(respawn=True,direction=direction))
        while len(self.clouds)>n_target:self.clouds.pop()
        rad=math.radians(direction);vx_base=math.cos(rad)*spd*0.9;vy_base=math.sin(rad)*spd*0.9;perp_x=-math.sin(rad);perp_y=math.cos(rad)
        for c in self.clouds:
            sway=math.sin(t*c['sway_freq']+c['sway_phase'])*c['sway_amp'];c['x']+=(vx_base+perp_x*sway*0.30)*c['speed_mul'];c['y']+=(vy_base+perp_y*sway*0.30)*c['speed_mul']
            margin=max(c['pw'],c['ph'])+80;gone=(c['x']>self.x_max+margin or c['x']<self.x_min-margin or c['y']>self.y_max+margin or c['y']<self.y_min-margin)
            if gone:new=self._new_cloud(respawn=True,direction=direction);c.update(new)
    def draw(self,frame,opacity):
        if self._empty:return frame
        overlay=np.zeros((self.H,self.W,4),dtype=np.float32)
        for c in self.clouds:
            patch=c['patch'];ph,pw=patch.shape[:2];px=int(c['x'])-pw//2;py=int(c['y'])-ph//2;fx0=max(0,px);fy0=max(0,py);fx1=min(self.W,px+pw);fy1=min(self.H,py+ph)
            if fx1<=fx0 or fy1<=fy0:continue
            ox0=fx0-px;oy0=fy0-py;src=patch[oy0:oy0+(fy1-fy0),ox0:ox0+(fx1-fx0)].astype(np.float32);mask_roi=self.mask[fy0:fy1,fx0:fx1].astype(np.float32)/255.0
            mask_roi=cv2.GaussianBlur(mask_roi,(0,0),3.2)
            src_a=(src[:,:,3]/255.0)*opacity*mask_roi;dst_a=overlay[fy0:fy1,fx0:fx1,3]/255.0;out_a=src_a+dst_a*(1.0-src_a);safe=np.where(out_a>0,out_a,1.0)
            overlay[fy0:fy1,fx0:fx1,:3]=(src[:,:,:3]*src_a[:,:,np.newaxis]+overlay[fy0:fy1,fx0:fx1,:3]*(dst_a*(1-src_a))[:,:,np.newaxis])/safe[:,:,np.newaxis];overlay[fy0:fy1,fx0:fx1,3]=out_a*255.0
        out=frame.astype(np.float32);cloud_a=overlay[:,:,3:4]/255.0;out=out*(1.0-cloud_a)+overlay[:,:,:3]*cloud_a;return out.clip(0,255).astype(np.uint8)


class RainState:
    def __init__(self,mask,n=200):
        self.mask=mask;self.H,self.W=mask.shape;ys,xs=np.where(mask>128);self.drops=[]
        if len(xs)==0:self._empty=True;return
        self._empty=False;self.x_min=int(xs.min());self.x_max=int(xs.max());self.y_min=int(ys.min());self.y_max=int(ys.max())
        for _ in range(n):self.drops.append(self._new_drop(respawn=False))
    def _new_drop(self,respawn=True):
        length=random.randint(8,28);speed=random.uniform(8.0,20.0);alpha=random.uniform(0.3,0.75)
        if respawn:x=random.uniform(float(self.x_min-60),float(self.x_max+60));y=float(self.y_min)-random.uniform(0,(self.y_max-self.y_min)*0.5)
        else:x=random.uniform(float(self.x_min-30),float(self.x_max+30));y=random.uniform(float(self.y_min),float(self.y_max))
        return{'x':x,'y':y,'length':length,'speed':speed,'alpha':alpha}
    def draw(self,frame,t,spd,wind_deg,density):
        if self._empty:return frame
        rad=math.radians(wind_deg);vx=math.sin(rad-math.pi/2)*spd;vy=math.cos(rad-math.pi/2)*spd;out=frame.copy();n_active=max(10,int(len(self.drops)*density))
        for p in self.drops[:n_active]:
            travel=t*p['speed']*abs(vy)*0.8;y=(p['y']+travel)%(self.y_max-self.y_min+60)+self.y_min-30;drift=t*p['speed']*vx*0.3;x=p['x']+drift
            ex=int(x+vx*p['length']*0.5);ey=int(y+vy*p['length']);sx=int(x);sy=int(y)
            if(sx<0 and ex<0)or(sx>=self.W and ex>=self.W):continue
            if(sy<0 and ey<0)or(sy>=self.H and ey>=self.H):continue
            mx=max(0,min(self.W-1,(sx+ex)//2));my=max(0,min(self.H-1,(sy+ey)//2))
            if self.mask[my,mx]<128:continue
            col=(200,220,255);alpha_val=p['alpha'];overlay=out.copy();cv2.line(overlay,(sx,sy),(ex,ey),col,1,cv2.LINE_AA);out=cv2.addWeighted(out,1.0-alpha_val*0.6,overlay,alpha_val*0.6,0)
        m=(self.mask>128);tint=np.array([0.92,0.95,1.0],dtype=np.float32);tint_strength=0.08*min(density,1.0);out_f=out.astype(np.float32);out_f[m]=out_f[m]*(1-tint_strength)+out_f[m]*tint*tint_strength
        return out_f.clip(0,255).astype(np.uint8)


class SunOrbState:
    def __init__(self,mask):
        self.mask=mask;self.H,self.W=mask.shape;ys,xs=np.where(mask>128)
        if len(xs)==0:self._empty=True;return
        self._empty=False;self.x_min=int(xs.min());self.x_max=int(xs.max());self.y_min=int(ys.min());self.y_max=int(ys.max())
    def draw(self,frame,t,sun_x_pct,sun_y_pct,size,glow_strength,n_rays,orbit_radius,orbit_speed,energy_color_name):
        if self._empty:return frame
        COLOR_MAP={"Solar Yellow":((255,240,80),(255,200,40)),"Cool White":((220,240,255),(160,200,255)),"Plasma Blue":((100,180,255),(60,120,220)),"Inferno Red":((255,140,60),(255,80,20)),"Emerald":((80,255,160),(30,200,100))}
        core_col,corona_col=COLOR_MAP.get(energy_color_name,COLOR_MAP["Solar Yellow"])
        bw=max(1,self.x_max-self.x_min);bh=max(1,self.y_max-self.y_min);ax=self.x_min+int(sun_x_pct*bw/100.0);ay=self.y_min+int(sun_y_pct*bh/100.0)
        ox=int(math.cos(t*orbit_speed*math.tau)*orbit_radius);oy=int(math.sin(t*orbit_speed*math.tau)*orbit_radius*0.6)
        cx=max(0,min(self.W-1,ax+ox));cy=max(0,min(self.H-1,ay+oy));out=frame.astype(np.float32);R=int(size);glow_r=int(R*(1.5+glow_strength*2.5))
        for radius,col,strength in[(glow_r*2,corona_col,0.28*glow_strength),(glow_r,corona_col,0.45*glow_strength),(R*2,core_col,0.60),(R,(255,255,255),0.85)]:
            x0=max(0,cx-radius*2);y0=max(0,cy-radius*2);x1=min(self.W,cx+radius*2);y1=min(self.H,cy+radius*2)
            if x1<=x0 or y1<=y0:continue
            ys_r=np.arange(y0,y1,dtype=np.float32);xs_r=np.arange(x0,x1,dtype=np.float32);PX,PY=np.meshgrid(xs_r-cx,ys_r-cy);dist=np.sqrt(PX**2+PY**2)
            alpha_g=np.exp(-dist/(radius*0.45))*strength;alpha_g=np.clip(alpha_g,0,1);roi=out[y0:y1,x0:x1];a3=alpha_g[:,:,np.newaxis];col_arr=np.array(col,dtype=np.float32);out[y0:y1,x0:x1]=roi*(1-a3)+col_arr*a3
        n_r=max(4,int(n_rays))
        for i in range(n_r):
            angle=(i/n_r)*math.tau+t*0.5;ray_len=R*(2.8+math.sin(t*2.1+i*1.3)*0.5+glow_strength*1.5)
            for sub in range(3):
                a2=angle+(sub-1)*0.04;steps=max(8,int(ray_len))
                for s in range(steps):
                    frac=s/steps;rx=int(cx+math.cos(a2)*ray_len*frac*0.9);ry=int(cy+math.sin(a2)*ray_len*frac*0.9)
                    if rx<0 or rx>=self.W or ry<0 or ry>=self.H:continue
                    fade=(1.0-frac)**2.2*0.5*(1.0-sub*0.3);col_arr=np.array(corona_col,dtype=np.float32);out[ry,rx]=np.clip(out[ry,rx]*(1-fade)+col_arr*fade,0,255)
        for ring_i in range(3):
            phase=(t*1.8+ring_i*0.6)%1.0;ring_r=int(R*(1.0+phase*4.0*(1+glow_strength)));ring_alpha=(1.0-phase)*0.55
            if ring_r<=0 or ring_alpha<0.02:continue
            x0=max(0,cx-ring_r-4);y0=max(0,cy-ring_r-4);x1=min(self.W,cx+ring_r+4);y1=min(self.H,cy+ring_r+4)
            if x1<=x0 or y1<=y0:continue
            PX,PY=np.meshgrid(np.arange(x0,x1,dtype=np.float32)-cx,np.arange(y0,y1,dtype=np.float32)-cy)
            dist=np.sqrt(PX**2+PY**2);ring_mask=np.exp(-((dist-ring_r)/max(2,R*0.12))**2)*ring_alpha;ring_mask=np.clip(ring_mask,0,1)
            roi=out[y0:y1,x0:x1];a3=ring_mask[:,:,np.newaxis];col_arr=np.array(core_col,dtype=np.float32);out[y0:y1,x0:x1]=roi*(1-a3)+col_arr*a3
        x0=max(0,cx-R);y0=max(0,cy-R);x1=min(self.W,cx+R);y1=min(self.H,cy+R)
        if x1>x0 and y1>y0:
            PX,PY=np.meshgrid(np.arange(x0,x1,dtype=np.float32)-cx,np.arange(y0,y1,dtype=np.float32)-cy);dist=np.sqrt(PX**2+PY**2);core_mask=np.clip(1.0-dist/max(1,R),0,1)**0.5
            roi=out[y0:y1,x0:x1];a3=core_mask[:,:,np.newaxis];out[y0:y1,x0:x1]=roi*(1-a3)+np.array([255,255,240],dtype=np.float32)*a3
        soft_mask=cv2.GaussianBlur(self.mask.astype(np.float32)/255.0,(0,0),20.0);soft_mask3=soft_mask[:,:,np.newaxis]
        result=frame.astype(np.float32)*(1-soft_mask3)+out*soft_mask3;return result.clip(0,255).astype(np.uint8)


# ─── Main render pipeline ──────────────────────────────────────────────────────
# --- 3to2 Ratio sway animation ------------------------------------------------
def _pixaloop_motion_coefficients(phase, motion_type="seamless"):
    if motion_type == "bounce":
        return (phase + 1.0 if phase <= 0.0 else 1.0 - phase), 0.0, 0.0
    if motion_type == "loop":
        return (phase + 1.0) * 0.5, 0.0, 0.0
    sign = 1.0 if phase > 0.0 else -1.0
    return phase, sign * (abs(phase) - 1.0), abs(phase)


# --- Flutter Pixaloop animation ----------------------------------------------
def _render_flutter_pixaloop(static_np, frame, mask, freeze_mask, paths, anchors,
                             t, amp, freq, spd, dispersion,
                             path_radius=70.0, anchor_strength=1.0,
                             motion_type="seamless"):
    """Port of pixaloop_flutter_animate/lib/main.dart's vector-field warp."""
    H, W = mask.shape
    if not np.any(mask > 128) or not paths:
        return frame

    ys_1d = np.arange(H, dtype=np.float32)
    xs_1d = np.arange(W, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(xs_1d, ys_1d)

    field_x = np.zeros((H, W), dtype=np.float32)
    field_y = np.zeros((H, W), dtype=np.float32)
    weight_sum = np.zeros((H, W), dtype=np.float32)
    step_len = 30.0

    for path in paths:
        x1 = float(path["x1"]); y1 = float(path["y1"])
        x2 = float(path["x2"]); y2 = float(path["y2"])
        vx = x2 - x1; vy = y2 - y1
        length = math.hypot(vx, vy)
        if length <= 1e-6:
            continue
        count = max(1, int(math.ceil(length / max(step_len, 1.0))))
        for sample in range(1, count + 1):
            u = sample / count
            pu = max(0.0, u - step_len / length)
            sx = x1 + vx * u
            sy = y1 + vy * u
            px = x1 + vx * pu
            py = y1 + vy * pu
            seg_x = sx - px
            seg_y = sy - py
            dist_sq = np.maximum(1.0, (grid_x - sx) ** 2 + (grid_y - sy) ** 2)
            weight = (1.0 / dist_sq).astype(np.float32)
            field_x += seg_x * weight
            field_y += seg_y * weight
            weight_sum += weight

    has_weight = weight_sum > 1e-6
    field_x = np.where(has_weight, field_x / np.where(has_weight, weight_sum, 1.0), 0.0)
    field_y = np.where(has_weight, field_y / np.where(has_weight, weight_sum, 1.0), 0.0)

    for anc in anchors or []:
        ax = float(anc["x"]); ay = float(anc["y"])
        dist = np.sqrt((grid_x - ax) ** 2 + (grid_y - ay) ** 2)
        damper = np.power(np.clip(dist / 160.0, 0.0, 1.0), 1.7).astype(np.float32)
        damper = np.power(damper, max(0.1, float(anchor_strength)))
        field_x *= damper
        field_y *= damper

    soft_mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 5.0)
    if freeze_mask is not None and np.any(freeze_mask > 0):
        freeze_soft = cv2.GaussianBlur(freeze_mask.astype(np.float32) / 255.0, (0, 0), 4.0)
        soft_mask *= np.clip(1.0 - freeze_soft, 0.0, 1.0)

    if dispersion > 0.001:
        nx = noise2d(grid_x / max(1, W) * 6.0 + t * 0.5, grid_y / max(1, H) * 6.0 + 13.0).astype(np.float32)
        ny = noise2d(grid_y / max(1, H) * 6.0 - t * 0.4, grid_x / max(1, W) * 6.0 + 29.0).astype(np.float32)
        field_x += nx * step_len * dispersion * 0.25
        field_y += ny * step_len * dispersion * 0.18

    speed01 = np.clip(float(amp) / 60.0, 0.0, 1.0)
    strength = (0.35 + 1.3 * speed01) * max(0.1, float(spd))
    phase = math.fmod(t * max(0.05, freq) * max(0.05, spd), 1.0) * 2.0 - 1.0
    primary, secondary, blend = _pixaloop_motion_coefficients(phase, motion_type)

    def warped_for(coeff):
        sx = np.clip(grid_x - field_x * strength * coeff, 0, W - 1).astype(np.float32)
        sy = np.clip(grid_y - field_y * strength * coeff, 0, H - 1).astype(np.float32)
        return cv2.remap(static_np, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    warped = warped_for(primary).astype(np.float32)
    if blend > 0.0:
        secondary_img = warped_for(secondary).astype(np.float32)
        opacity = np.clip(1.0 - blend, 0.0, 1.0)
        warped = warped * (1.0 - opacity) + secondary_img * opacity

    a = soft_mask[:, :, np.newaxis]
    out = frame.astype(np.float32) * (1.0 - a) + warped * a
    return np.clip(out, 0, 255).astype(np.uint8)
def _render_3to2_ratio_sway(static_np, frame, mask, t, amp, freq, spd, dispersion):
    """
    Integrated from 3to2_ratio.py: a stem-driven vertical sway where the upper
    part of a painted region moves more than the base, with a soft blend edge.
    """
    H, W = static_np.shape[:2]
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return frame

    y_min = int(ys.min())
    y_max = int(ys.max())
    y_range = max(y_max - y_min, 1)

    rows = np.arange(H, dtype=np.float32)
    row_norm = np.clip(1.0 - (rows - y_min) / y_range, 0.0, 1.0)[:, None]
    mask_f = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 4.0)

    phase = math.tau * (t * freq * spd + row_norm * 0.3)
    dx = (amp * row_norm * np.sin(phase)).astype(np.float32)

    phase_y = math.tau * (t * freq * spd * 2.0 + row_norm * 0.2)
    dy = (amp * 0.25 * row_norm * np.sin(phase_y)).astype(np.float32)

    if dispersion > 0.001:
        xs_g = np.linspace(0, 1, W, dtype=np.float32)
        ys_g = np.linspace(0, 1, H, dtype=np.float32)
        gx, gy = np.meshgrid(xs_g, ys_g)
        flutter = noise2d(gx * 5.0 + t * spd, gy * 7.0 + 17.0).astype(np.float32)
        dx = dx + flutter * amp * dispersion * 0.18 * row_norm
        dy = dy + noise2d(gy * 6.0 - t * spd * 0.7, gx * 4.0 + 9.0).astype(np.float32) * amp * dispersion * 0.10 * row_norm

    grid_y, grid_x = np.mgrid[0:H, 0:W].astype(np.float32)
    src_x = np.clip(grid_x - dx * mask_f, 0, W - 1).astype(np.float32)
    src_y = np.clip(grid_y - dy * mask_f, 0, H - 1).astype(np.float32)
    warped = cv2.remap(static_np, src_x, src_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    a = mask_f[:, :, None]
    out = frame.astype(np.float32) * (1.0 - a) + warped.astype(np.float32) * a
    return np.clip(out, 0, 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
#  MOTIONLEAP STRIP ANIMATIONS  (indices 30-32)
#  Ported from agent.py (MotionLeapApp._compute_frame).
#  Three sub-modes share one rendering function:
#    "sine"   – classic sinusoidal strip warp (back-and-forth)
#    "flow"   – seamless unidirectional wrap  (BORDER_WRAP scroll)
#    "ripple" – modulated sinusoidal warp     (sin × cos for organic feel)
# ─────────────────────────────────────────────────────────────────────────────

def _render_ml_strip(static_np, frame, mask, t, amp, freq, spd, direction,
                     feather_radius, num_strips, wave_type):
    """
    Strip-based directional warp imported from MotionLeap (agent.py).

    Parameters
    ----------
    wave_type : "sine" | "flow" | "ripple"
    direction : motion angle in degrees (0 = rightward, 90 = downward)
    num_strips : number of phase bands across the motion axis (10-120)
    feather_radius : Gaussian feather px at mask edge (0-30)
    amp  : displacement amplitude in pixels
    spd  : time-speed multiplier
    """
    H, W = static_np.shape[:2]
    angle_rad = math.radians(direction)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)

    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    proj_motion = X * dx + Y * dy
    motion_range = float(proj_motion.max() - proj_motion.min()) + 1e-6
    strip_phase = (proj_motion - proj_motion.min()) / motion_range * (
        2.0 * math.pi * num_strips / 20.0)

    if wave_type == "flow":
        # Seamless unidirectional scroll — always increases, never reverses.
        scroll = (t / (2.0 * math.pi)) * spd * amp
        wrapped_disp = scroll % motion_range
        sample_x = (X - wrapped_disp * dx).astype(np.float32)
        sample_y = (Y - wrapped_disp * dy).astype(np.float32)
        warped = cv2.remap(static_np, sample_x, sample_y,
                           cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

    elif wave_type == "sine":
        disp = amp * np.sin(strip_phase + t * spd)
        sample_x = np.clip(X + disp * dx, 0, W - 1).astype(np.float32)
        sample_y = np.clip(Y + disp * dy, 0, H - 1).astype(np.float32)
        warped = cv2.remap(static_np, sample_x, sample_y,
                           cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    elif wave_type == "ripple":
        disp = (amp
                * np.sin(strip_phase + t * spd)
                * np.cos(strip_phase * 0.3))
        sample_x = np.clip(X + disp * dx, 0, W - 1).astype(np.float32)
        sample_y = np.clip(Y + disp * dy, 0, H - 1).astype(np.float32)
        warped = cv2.remap(static_np, sample_x, sample_y,
                           cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    else:
        warped = static_np.copy()

    # Feather mask edges and composite
    mask_f = mask.astype(np.float32) / 255.0
    if feather_radius > 1:
        fk = int(feather_radius) * 2 + 1
        mask_f = cv2.GaussianBlur(mask_f, (fk, fk), feather_radius)

    alpha = mask_f[:, :, np.newaxis]
    result = (warped.astype(np.float32) * alpha +
              frame.astype(np.float32) * (1.0 - alpha))
    return np.clip(result, 0, 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
#  PIXEL FLOW (MOTIONLEAP)  — index 33
#  Bilinear pixel-warp driven by arrow paths drawn on the region.
#  Direction arrows are taken from reg['paths'] (same as Motion Paths / index 26).
#  The painted mask determines where the warp applies; outside pixels remain static.
#  Three motion profiles via 'pf_motion' param: seamless_loop, loop, bounce.
# ─────────────────────────────────────────────────────────────────────────────

class PixelFlowRenderer:
    """
    Port of the MotionLeap app's core pixel-warp render engine.
    Warps source image pixels along an arrow-defined flow field using
    bilinear interpolation, blending back over the static frame via
    the painted mask.

    MAX_DISP: maximum pixel displacement at speed=1.0 (scaled by amp).
    """
    MAX_DISP = 40.0

    def __init__(self, static_np: np.ndarray):
        self._src  = static_np.astype(np.float32)
        self.H, self.W = static_np.shape[:2]

    @staticmethod
    def _compute_progress(raw01: float, motion_type: str, speed: float) -> float:
        r = (raw01 * 2.0 - 1.0) * speed
        if motion_type == "bounce":
            return (r + 1.0) if r <= 0.0 else (1.0 - r)
        # seamless_loop and loop both map to 0-1 via this formula
        return (r + 1.0) / 2.0

    def render(self, frame: np.ndarray, mask: np.ndarray,
               paths: list, t: float,
               amp: float, spd: float,
               motion_type: str = "seamless_loop") -> np.ndarray:
        """
        frame      : current frame RGB (H×W×3 uint8)
        mask       : painted region mask (H×W uint8, 0/255)
        paths      : list of {'x1','y1','x2','y2'} arrow dicts
        t          : animation time (seconds, loops via mod)
        amp        : amplitude → scales MAX_DISP (14 = 1×, 28 = 2×…)
        spd        : time-scale multiplier
        motion_type: 'seamless_loop' | 'loop' | 'bounce'
        """
        if not paths or not np.any(mask > 128):
            return frame

        H, W = self.H, self.W
        src   = self._src

        # ── 1. Build per-pixel displacement from arrow paths ──────────────────
        dx = np.zeros((H, W), dtype=np.float32)
        dy = np.zeros((H, W), dtype=np.float32)

        ys_1d = np.arange(H, dtype=np.float32)
        xs_1d = np.arange(W, dtype=np.float32)

        for path in paths:
            x1f, y1f = float(path["x1"]), float(path["y1"])
            x2f, y2f = float(path["x2"]), float(path["y2"])
            length = math.hypot(x2f - x1f, y2f - y1f)
            if length < 1.0:
                continue
            ndx = (x2f - x1f) / length
            ndy = (y2f - y1f) / length

            # Influence radius = 55% of arrow length (mirrors original MotionLeap)
            inf_r = max(length * 0.55, 40.0)
            mid_x = (x1f + x2f) / 2.0
            mid_y = (y1f + y2f) / 2.0

            dist  = np.hypot(xs_1d[np.newaxis, :] - mid_x,
                             ys_1d[:, np.newaxis] - mid_y)
            weight = np.clip(1.0 - dist / inf_r, 0.0, 1.0) ** 2

            dx += ndx * weight
            dy += ndy * weight

        # Normalise + scale by amp / MAX_DISP * speed
        mag     = np.sqrt(dx ** 2 + dy ** 2)
        mag_max = float(mag.max())
        if mag_max > 0:
            scale = (amp / 14.0) * self.MAX_DISP * spd   # 14 = neutral amp
            dx = dx / mag_max * scale
            dy = dy / mag_max * scale

        # ── 2. Animate via seamless phase (progress 0→1) ──────────────────────
        raw01    = math.fmod(t * max(0.1, spd) * 0.35, 1.0)   # matches MotionLeap tick rate
        progress = self._compute_progress(raw01, motion_type, 1.0)
        phase    = progress * 2.0 - 1.0                        # maps 0-1 → -1..+1

        dx_anim = dx * phase
        dy_anim = dy * phase

        # Apply mask so only painted pixels flow
        soft_mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 4.0)
        dx_eff = dx_anim * soft_mask
        dy_eff = dy_anim * soft_mask

        # ── 3. Bilinear sample (pull from displaced source position) ──────────
        ys_g, xs_g = np.mgrid[0:H, 0:W].astype(np.float32)
        xs_src = np.clip(xs_g - dx_eff, 0, W - 1).astype(np.float32)
        ys_src = np.clip(ys_g - dy_eff, 0, H - 1).astype(np.float32)

        xs0 = xs_src.astype(np.int32)
        ys0 = ys_src.astype(np.int32)
        xs1 = np.clip(xs0 + 1, 0, W - 1)
        ys1 = np.clip(ys0 + 1, 0, H - 1)
        fx  = (xs_src - xs0)[:, :, np.newaxis]
        fy  = (ys_src - ys0)[:, :, np.newaxis]

        warped = (
            src[ys0, xs0] * (1 - fx) * (1 - fy)
            + src[ys0, xs1] * fx       * (1 - fy)
            + src[ys1, xs0] * (1 - fx) * fy
            + src[ys1, xs1] * fx       * fy
        )

        # ── 4. Composite: warped inside mask, original outside ────────────────
        mask3 = soft_mask[:, :, np.newaxis]
        out   = (src * (1.0 - mask3) + warped * mask3)
        return np.clip(out, 0, 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
#  LIVING PAINTING  (index 29)
#  Volcano-style particle eruption rendered as a transparent overlay layer.
#  Particles spawn from the painted region, erupt upward carrying image
#  colours, then fade — composited over the main frame with alpha.
# ─────────────────────────────────────────────────────────────────────────────
class LivingPaintingState:
    # Physics defaults (can be overridden via params)
    _GRAVITY         = 0.18
    _ERUPT_Y         = 12.0
    _ERUPT_X         = 4.5
    _NOISE_STR       = 0.4
    _MAX_PARTICLES   = 35000
    _DECAY_SPEED     = 0.60   # fraction of total frames used for sweep

    def __init__(self, mask: np.ndarray, static_np: np.ndarray, fg_np=None):
        """
        fg_np : optional RGBA frame (H×W×4, uint8) from the foreground image.
                When supplied, particle colours come from the FG image and only
                pixels where the FG alpha > 0 are eligible to spawn particles.
                The animation is then composited as a transparent overlay so the
                background image shows through everywhere the FG alpha is zero.
        """
        self.H, self.W = static_np.shape[:2]

        # ── Decide colour source and valid spawn region ────────────────────────
        # If an FG image is provided, restrict spawning to pixels that are
        # both (a) inside the painted mask AND (b) non-transparent in the FG.
        if fg_np is not None:
            # fg_np is RGBA; resize to match static_np if needed
            if fg_np.shape[:2] != (self.H, self.W):
                fg_np = cv2.resize(fg_np, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
            fg_alpha_ch = fg_np[:, :, 3]          # 0-255 alpha channel
            spawn_mask  = (mask > 128) & (fg_alpha_ch > 32)
            colour_src  = fg_np[:, :, :3]         # RGB colours from FG
        else:
            spawn_mask  = mask > 128
            colour_src  = static_np                # fall back to main image

        ys, xs = np.where(spawn_mask)
        if len(xs) == 0:
            self._empty = True
            return
        self._empty = False

        # Subsample if too many masked pixels
        if len(xs) > self._MAX_PARTICLES:
            idx = np.random.choice(len(xs), self._MAX_PARTICLES, replace=False)
            xs, ys = xs[idx], ys[idx]

        N = len(xs)
        y_min, y_max = int(ys.min()), int(ys.max())
        x_min, x_max = int(xs.min()), int(xs.max())

        vent_x = (x_min + x_max) / 2.0

        # Normalise y position (0 = top of region, 1 = bottom)
        y_norm = (ys - y_min) / max(y_max - y_min, 1)

        # Cone: particles closer to the edge get more lateral push
        dx_from_vent = xs - vent_x
        cone_factor  = dx_from_vent / max(x_max - x_min, 1)

        speed_y_base = self._ERUPT_Y * (1.0 - y_norm * 0.4)
        noise_v      = np.random.normal(0, 2.5, N)

        vy_init = -(speed_y_base + np.abs(noise_v))
        vx_init = cone_factor * self._ERUPT_X * 2.0
        vx_init += np.random.normal(0, self._ERUPT_X * 0.4, N)

        # Particle radii: mostly 1–2 px for fine detail
        radii = np.random.choice([1, 1, 1, 2, 2], N).astype(np.int32)

        # Store per-particle data
        self._px     = xs.astype(np.float32).copy()
        self._py     = ys.astype(np.float32).copy()
        self._vx     = vx_init.astype(np.float32)
        self._vy     = vy_init.astype(np.float32)
        self._r      = colour_src[ys, xs, 0].astype(np.float32)
        self._g      = colour_src[ys, xs, 1].astype(np.float32)
        self._b      = colour_src[ys, xs, 2].astype(np.float32)
        # Store per-pixel FG alpha so surviving static pixels inherit it
        if fg_np is not None:
            self._spawn_fg_alpha = fg_np[ys, xs, 3].astype(np.float32) / 255.0
            self._has_fg = True
            # Full 2D colour + alpha maps for surviving-pixel lookup in draw()
            self._r_full = fg_np[:, :, 0]
            self._g_full = fg_np[:, :, 1]
            self._b_full = fg_np[:, :, 2]
            self._a_full = fg_np[:, :, 3]
        else:
            self._spawn_fg_alpha = np.ones(len(xs), np.float32)
            self._has_fg = False
        self._alpha  = np.ones(N, np.float32)
        self._radii  = radii
        self._N      = N

        self._y_min  = y_min
        self._y_max  = y_max
        self._vent_x = vent_x

        # Animation state
        self._sim_t  = -1.0   # last simulated time (seconds)
        self._fps    = 30.0   # assumed internal sim rate
        self._frame  = 0

        # Precompute start frames so bottom particles launch later (sweep)
        total_frames = int(self._fps * 10.0)  # 10 s base window
        self._start_f = (y_norm * (total_frames * self._DECAY_SPEED)).astype(np.float32)

        # Save original spawn positions for reset
        self._ox = self._px.copy()
        self._oy = self._py.copy()

        # Original velocities for reset
        self._ovx = self._vx.copy()
        self._ovy = self._vy.copy()

    # ── Physics step (called once per rendered frame) ────────────────────
    def _step(self, frame_idx: int):
        active = frame_idx >= self._start_f
        if not np.any(active):
            return
        n_active = int(np.sum(active))

        self._px[active] += self._vx[active]
        self._py[active] += self._vy[active]
        self._vy[active] += self._GRAVITY

        wind_x = np.random.normal(0, self._NOISE_STR, n_active)
        wind_y = np.random.normal(0, self._NOISE_STR * 0.3, n_active)
        self._vx[active] += wind_x
        self._py[active] += wind_y  # tiny vertical turbulence

        self._vx[active] *= 0.985
        self._vy[active] *= 0.992

        age = frame_idx - self._start_f[active]
        total_frames = int(self._fps * 10.0)
        lifetime = total_frames * 0.55
        fade      = np.clip(1.0 - (age / lifetime), 0, 1)
        old_fade  = np.clip(1.0 - (age / (lifetime * 0.7)) ** 2, 0, 1)
        self._alpha[active] = fade * old_fade

    # ── Render: returns RGBA (H×W×4) overlay ─────────────────────────────
    def draw(self, frame: np.ndarray, mask: np.ndarray,
             t: float, dt: float, amp: float, spd: float) -> np.ndarray:
        """
        Returns `frame` composited with the transparent particle overlay.
        Particles render on top of the main frame with their own alpha.
        """
        if self._empty:
            return frame

        H, W = frame.shape[:2]

        # Advance simulation by dt seconds
        new_frame_idx = max(0, int(t * self._fps * max(0.1, spd)))
        # Step simulation forward frame by frame if needed
        while self._frame < new_frame_idx:
            self._step(self._frame)
            self._frame += 1

        fi = self._frame
        total_frames = int(self._fps * 10.0)

        # ── Build transparent colour + alpha canvases ──────────────────
        color_canvas = np.zeros((H, W, 3), dtype=np.uint8)
        alpha_canvas = np.zeros((H, W),    dtype=np.uint8)

        # Ensure FG full maps match current frame resolution
        if self._has_fg and (self._r_full.shape[0] != H or self._r_full.shape[1] != W):
            self._r_full = cv2.resize(self._r_full, (W, H), interpolation=cv2.INTER_LINEAR)
            self._g_full = cv2.resize(self._g_full, (W, H), interpolation=cv2.INTER_LINEAR)
            self._b_full = cv2.resize(self._b_full, (W, H), interpolation=cv2.INTER_LINEAR)
            self._a_full = cv2.resize(self._a_full, (W, H), interpolation=cv2.INTER_LINEAR)

        # Sweep: keep static pixels below the "decay front"
        # When an FG image is the source, surviving pixels show FG colours +
        # respect FG alpha (so transparent FG areas remain see-through).
        sweep_progress = min(fi / max(1, total_frames * self._DECAY_SPEED), 1.0)
        decay_y = self._y_min + sweep_progress * (self._y_max - self._y_min)

        ys_all, xs_all = np.where(mask > 128)
        surviving = ys_all > decay_y
        if surviving.any():
            sy_ = ys_all[surviving]; sx_ = xs_all[surviving]
            if self._has_fg:
                color_canvas[sy_, sx_, 0] = self._r_full[sy_, sx_]
                color_canvas[sy_, sx_, 1] = self._g_full[sy_, sx_]
                color_canvas[sy_, sx_, 2] = self._b_full[sy_, sx_]
                alpha_canvas[sy_, sx_]    = self._a_full[sy_, sx_]
            else:
                color_canvas[sy_, sx_] = frame[sy_, sx_]
                alpha_canvas[sy_, sx_] = 255

        # ── Active particles ──────────────────────────────────────────
        active_mask = (fi >= self._start_f) & (self._alpha > 0.01)
        if active_mask.any():
            sx  = self._px[active_mask].astype(np.int32)
            sy  = self._py[active_mask].astype(np.int32)
            als = self._alpha[active_mask]
            rs  = self._r[active_mask]
            gs  = self._g[active_mask]
            bs  = self._b[active_mask]
            rds = self._radii[active_mask]
            fg_als = self._spawn_fg_alpha[active_mask]   # per-particle FG alpha weight
            vx_p = self._vx[active_mask]
            vy_p = self._vy[active_mask]
            speed = np.sqrt(vx_p ** 2 + vy_p ** 2)
            heat  = np.clip(speed / self._ERUPT_Y, 0, 1)

            in_bounds = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
            sx  = sx[in_bounds];  sy  = sy[in_bounds]
            als = als[in_bounds]; rs  = rs[in_bounds]
            gs  = gs[in_bounds];  bs  = bs[in_bounds]
            rds = rds[in_bounds]; heat = heat[in_bounds]
            fg_als = fg_als[in_bounds]

            for i in range(len(sx)):
                a_f       = float(als[i]) * float(fg_als[i])   # scale by FG alpha
                h_factor  = float(heat[i])
                sparkle   = np.random.uniform(0.9, 1.3)
                intensity = amp / 14.0  # normalised to default amp

                cr = int(np.clip(rs[i] * sparkle + 80 * h_factor * a_f * intensity, 0, 255))
                cg = int(np.clip(gs[i] * sparkle + 40 * h_factor * a_f * intensity, 0, 255))
                cb = int(np.clip(bs[i] * sparkle + 10 * h_factor * a_f * intensity, 0, 255))
                ca = int(a_f * 255)
                rad = int(rds[i])
                pt  = (int(sx[i]), int(sy[i]))

                # OpenCV uses BGR; frame is RGB so we use (cb,cg,cr) order for canvas
                cv2.circle(color_canvas, pt, rad, (cr, cg, cb), -1)
                cv2.circle(alpha_canvas,  pt, rad, ca,           -1)

                if h_factor > 0.5 and a_f > 0.4:
                    glow_ca = int(a_f * 60 * h_factor)
                    cv2.circle(color_canvas, pt, rad + 1, (cr, cg, cb), -1)
                    cv2.circle(alpha_canvas,  pt, rad + 1, glow_ca,      -1)

        # ── Composite particle layer over the input frame ──────────────
        a_float = alpha_canvas.astype(np.float32) / 255.0
        a3      = a_float[:, :, np.newaxis]
        out     = (frame.astype(np.float32) * (1.0 - a3)
                   + color_canvas.astype(np.float32) * a3).astype(np.uint8)
        return out

    def reset(self):
        """Reset simulation back to frame 0 (call when looping)."""
        if self._empty:
            return
        self._px    = self._ox.copy()
        self._py    = self._oy.copy()
        self._vx    = self._ovx.copy()
        self._vy    = self._ovy.copy()
        self._alpha = np.ones(self._N, np.float32)
        self._frame = 0


# ─────────────────────────────────────────────────────────────────────────────
#  WATERFALL ANIMATION  (index 34)
#  Ported from agent.py (Pro Pixel Flow).
#
#  The painted region is split into TWO seamlessly-looping alpha layers.
#  Each layer carries a copy of the image pixels, offset along a flow
#  direction chosen from the painted area's bounding diagonal.  Layers
#  cross-fade with sin²(progress·π) so there is never a hard seam.
#  A soft Gaussian mask confines the effect to the brushed region.
# ─────────────────────────────────────────────────────────────────────────────
class WaterfallState:
    """
    Two-layer seamless pixel-flow waterfall — faithfully reproduces the
    FlowGroup / FlowLayer logic from agent.py inside the numpy/OpenCV pipeline.

    Controls (via region params):
        amp        → travel distance scale (default 14)
        spd        → animation speed       (default 1.5)
        direction  → flow angle in degrees, 0=right 90=down (default 90)
        foam       → white-highlight brightness 0-1 (default 0.3)
    """
    _LAYER_COUNT  = 2          # exactly 2 for a mathematically seamless loop
    _LAYER_OFFSET = 0.5        # layers are 0.5 apart in phase (from agent.py)

    def __init__(self, mask: np.ndarray, static_np: np.ndarray):
        self.H, self.W = static_np.shape[:2]
        ys, xs = np.where(mask > 128)
        self._empty = len(xs) == 0
        if self._empty:
            return

        # Bounding box
        self.y0 = int(ys.min()); self.y1 = int(ys.max()) + 1
        self.x0 = int(xs.min()); self.x1 = int(xs.max()) + 1

        # Soft feathered mask — same role as group.mask in agent.py
        self.soft_mask = cv2.GaussianBlur(
            mask.astype(np.float32) / 255.0, (0, 0), 6.0)

        # Snapshot of the painted pixels (the "pixmap" in agent.py)
        self.tile = static_np.copy()

        # Area diagonal — used to cap travel like agent.py's safe_travel
        area_diag = math.sqrt((self.x1 - self.x0) ** 2 +
                               (self.y1 - self.y0) ** 2)
        # travel_fraction: cap to 20 % of diagonal (mirrors agent.py)
        self._area_diag = max(area_diag, 1.0)

        # Two layer phases — offset by 0.5 exactly as in agent.py
        self._phases = [i * self._LAYER_OFFSET
                        for i in range(self._LAYER_COUNT)]

    # ------------------------------------------------------------------
    def draw(self, frame: np.ndarray, t: float,
             amp: float, spd: float,
             direction: float = 90.0,
             foam: float = 0.30) -> np.ndarray:
        if self._empty:
            return frame

        H, W = self.H, self.W

        # ── Flow direction vector ──────────────────────────────────────
        rad  = math.radians(direction)
        fdx  = math.cos(rad)     # unit flow vector x
        fdy  = math.sin(rad)     # unit flow vector y

        # Maximum pixel travel (agent.py: safe_travel = min(path_len, area*0.2))
        # Here we use amp to scale it: amp=14 → 20 % of diagonal
        safe_travel = min(self._area_diag,
                          max(25.0, self._area_diag * 0.20)) * (amp / 14.0)

        # ── Advance layer phases ───────────────────────────────────────
        # phase increases with time and wraps at 1.0
        step = spd / 80.0          # tuned so amp=14, spd=1.5 ≈ agent's speed=4000
        self._phases = [math.fmod(ph + step, 1.0)
                        for ph in self._phases]

        # ── Build coordinate grids for the full frame ──────────────────
        ys_1d = np.arange(H, dtype=np.float32)
        xs_1d = np.arange(W, dtype=np.float32)
        xs_g, ys_g = np.meshgrid(xs_1d, ys_1d)   # (H, W)

        # Accumulate layers
        acc_rgb   = np.zeros((H, W, 3), dtype=np.float32)
        acc_alpha = np.zeros((H, W),    dtype=np.float32)

        for ph in self._phases:
            # sin²(progress·π) opacity — exactly agent.py's formula
            opacity = math.pow(math.sin(ph * math.pi), 2.0)

            # Pixel offset along flow direction — capped by safe_travel
            travel = ph * safe_travel
            off_x  = fdx * travel
            off_y  = fdy * travel

            # Sample coords: pull from upstream (subtract offset)
            sx = np.clip(xs_g - off_x, 0, W - 1).astype(np.float32)
            sy = np.clip(ys_g - off_y, 0, H - 1).astype(np.float32)

            sampled = cv2.remap(self.tile, sx, sy,
                                cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REPLICATE)

            # Foam/shimmer: brighten pixels that are near the crest of the wave
            if foam > 0.001:
                # Standing ripple perpendicular to flow
                perp_x = -fdy; perp_y = fdx
                crest = np.sin((xs_g * perp_x + ys_g * perp_y) * 0.055
                               + t * 4.1).astype(np.float32)
                crest = np.clip((crest + 1.0) * 0.5, 0.0, 1.0)
                foam_map = crest * foam * 0.35
                sampled_f = sampled.astype(np.float32)
                sampled_f[:, :, 0] = np.clip(sampled_f[:, :, 0] + foam_map * 32, 0, 255)
                sampled_f[:, :, 1] = np.clip(sampled_f[:, :, 1] + foam_map * 48, 0, 255)
                sampled_f[:, :, 2] = np.clip(sampled_f[:, :, 2] + foam_map * 64, 0, 255)
            else:
                sampled_f = sampled.astype(np.float32)

            # Layer contribution weighted by opacity and soft mask
            layer_w = opacity * self.soft_mask
            acc_rgb   += sampled_f * layer_w[:, :, np.newaxis]
            acc_alpha += layer_w

        # Normalise
        safe_a = np.where(acc_alpha > 1e-4, acc_alpha, 1.0)
        avg_rgb = acc_rgb / safe_a[:, :, np.newaxis]

        # Blend weight — mirrors agent.py DestinationIn mask composite
        blend_w = np.clip(acc_alpha / max(1e-4, self._LAYER_COUNT * 0.5),
                          0.0, 1.0) * self.soft_mask
        b3 = blend_w[:, :, np.newaxis]

        out = (frame.astype(np.float32) * (1.0 - b3) +
               avg_rgb * b3).astype(np.uint8)
        return out


# ─────────────────────────────────────────────────────────────────────────────
#  CINEMATIC ZOOM STATE  (index 35)
#  Full-frame cinematic camera motion ported from agent.py's VideoGenerator.
#  Applies per-frame crop+zoom with easing, Ken Burns travel, drift, shake,
#  vignette, brightness/contrast, and fade-in from black — exactly matching
#  agent.py's render pipeline.
#
#  Params (region params dict):
#    effect   → "Zoom In" | "Zoom Out" | "Ken Burns" | "Drift Right" |
#               "Drift Left" | "Push In Shake" | "Crane Up" | "Crane Down"
#    easing   → key into _CINEMATIC_EASING (default "Smooth (Cubic)")
#    zoom_start  → float, start zoom (default 1.0)
#    zoom_end    → float, end zoom   (default 3.0)
#    start_x, start_y  → normalised 0-1 camera start centre (default 0.5, 0.5)
#    end_x,   end_y    → normalised 0-1 camera end centre   (default 0.5, 0.45)
#    vignette   → 0.0-1.0 (default 0.35)
#    brightness → float (default 1.0)
#    contrast   → float (default 1.1)
#    fade_black → bool — fade to black at end (default True)
#    fade_white → bool — fade to white at end (default False)
#    fade_duration → seconds for fade (default 1.5)
#    duration   → total clip duration in seconds (default 8.0)
# ─────────────────────────────────────────────────────────────────────────────
class CinematicZoomState:
    """Applies agent.py-style cinematic crop+zoom animation to the full frame."""

    def __init__(self, static_np: np.ndarray):
        self.H, self.W = static_np.shape[:2]
        self._vignette_cache: dict = {}   # (W, H, strength) → mask

    # ------------------------------------------------------------------
    def _make_vignette(self, w: int, h: int, strength: float) -> np.ndarray:
        key = (w, h, round(strength, 3))
        if key not in self._vignette_cache:
            xs = np.linspace(-1, 1, w, dtype=np.float32)
            ys = np.linspace(-1, 1, h, dtype=np.float32)
            xg, yg = np.meshgrid(xs, ys)
            dist = np.sqrt(xg ** 2 + yg ** 2)
            dist = dist / dist.max()
            mask = 1.0 - dist * strength
            self._vignette_cache[key] = np.clip(mask, 0, 1).astype(np.float32)[:, :, np.newaxis]
        return self._vignette_cache[key]

    # ------------------------------------------------------------------
    def draw(self, frame: np.ndarray, t: float, duration: float, p: dict) -> np.ndarray:
        """
        frame    : current RGB frame (H×W×3)
        t        : animation time (seconds, 0 → duration)
        duration : total duration in seconds
        p        : params dict (see class docstring)
        """
        H, W = frame.shape[:2]
        iw, ih = W, H

        out_w, out_h = W, H
        effect     = p.get('effect', 'Zoom In')
        easing_key = p.get('easing', 'Smooth (Cubic)')
        ease_fn    = _CINEMATIC_EASING.get(easing_key, _ease_in_out_cubic)
        zoom_start = float(p.get('zoom_start', 1.0))
        zoom_end   = float(p.get('zoom_end', 3.0))
        sx_n = float(p.get('start_x', 0.5)); sy_n = float(p.get('start_y', 0.5))
        ex_n = float(p.get('end_x', 0.5));   ey_n = float(p.get('end_y', 0.45))
        vignette_str = float(p.get('vignette', 0.35))
        brightness   = float(p.get('brightness', 1.0))
        contrast_v   = float(p.get('contrast', 1.1))
        fade_black   = bool(p.get('fade_black', True))
        fade_white   = bool(p.get('fade_white', False))
        fade_dur     = float(p.get('fade_duration', 1.5))
        fps_equiv    = 30.0

        total_frames = max(1, int(fps_equiv * duration))
        fi = min(int(t * fps_equiv), total_frames - 1)
        tv = fi / max(total_frames - 1, 1)   # 0 → 1

        sp_cx = sx_n * iw;  sp_cy = sy_n * ih
        ep_cx = ex_n * iw;  ep_cy = ey_n * ih

        # ── Effect math (mirroring agent.py exactly) ──────────────────────
        if effect == "Zoom In":
            et    = ease_fn(tv)
            scale = zoom_start + (zoom_end - zoom_start) * et
            cx    = sp_cx + (ep_cx - sp_cx) * et
            cy    = sp_cy + (ep_cy - sp_cy) * et

        elif effect == "Zoom Out":
            et    = ease_fn(1 - tv)
            scale = zoom_start + (zoom_end - zoom_start) * (1 - et)
            fwd   = ease_fn(tv)
            cx    = ep_cx + (sp_cx - ep_cx) * fwd
            cy    = ep_cy + (sp_cy - ep_cy) * fwd

        elif effect == "Ken Burns":
            et    = ease_fn(tv)
            scale = zoom_start + (zoom_end - zoom_start) * et
            cx    = sp_cx + (ep_cx - sp_cx) * et
            cy    = sp_cy + (ep_cy - sp_cy) * et

        elif effect == "Drift Right":
            et    = ease_fn(tv)
            scale = zoom_start + (zoom_end - zoom_start) * et * 0.4
            cx    = sp_cx + (ep_cx - sp_cx) * et
            cy    = sp_cy + (ep_cy - sp_cy) * et

        elif effect == "Drift Left":
            et    = ease_fn(tv)
            scale = zoom_start + (zoom_end - zoom_start) * et * 0.4
            cx    = sp_cx + (ep_cx - sp_cx) * et
            cy    = sp_cy + (ep_cy - sp_cy) * et

        elif effect == "Push In Shake":
            et    = ease_fn(tv)
            scale = zoom_start + (zoom_end - zoom_start) * et
            cx    = sp_cx + (ep_cx - sp_cx) * et + math.sin(tv * 40) * 3 * (1 - et)
            cy    = sp_cy + (ep_cy - sp_cy) * et + math.cos(tv * 35) * 2 * (1 - et)

        elif effect == "Crane Up":
            et    = ease_fn(tv)
            scale = zoom_start + (zoom_end - zoom_start) * et
            cx    = sp_cx + (ep_cx - sp_cx) * et
            cy    = sp_cy + (ep_cy - sp_cy) * et

        elif effect == "Crane Down":
            et    = ease_fn(tv)
            scale = zoom_start + (zoom_end - zoom_start) * et
            cx    = sp_cx + (ep_cx - sp_cx) * et
            cy    = sp_cy + (ep_cy - sp_cy) * et

        else:  # fallback
            et    = ease_fn(tv)
            scale = zoom_start + (zoom_end - zoom_start) * et
            cx    = sp_cx + (ep_cx - sp_cx) * et
            cy    = sp_cy + (ep_cy - sp_cy) * et

        # ── Compute crop window (matching agent.py) ────────────────────
        crop_w = iw / max(scale, 0.01)
        crop_h = ih / max(scale, 0.01)
        ar = out_w / out_h
        if crop_w / max(crop_h, 1) > ar:
            crop_w = crop_h * ar
        else:
            crop_h = crop_w / ar

        x1 = max(0.0, cx - crop_w / 2)
        y1 = max(0.0, cy - crop_h / 2)
        x2 = x1 + crop_w;  y2 = y1 + crop_h
        if x2 > iw: x2 = iw; x1 = iw - crop_w
        if y2 > ih: y2 = ih; y1 = ih - crop_h
        x1 = max(0.0, x1); y1 = max(0.0, y1)

        # ── Crop & resize ─────────────────────────────────────────────
        crop_pil = frame[int(y1):int(y1+crop_h), int(x1):int(x1+crop_w)]
        if crop_pil.shape[0] < 1 or crop_pil.shape[1] < 1:
            return frame
        resized = cv2.resize(crop_pil, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)

        frame_np = resized.astype(np.float32)

        # ── Brightness ────────────────────────────────────────────────
        if brightness != 1.0:
            frame_np = np.clip(frame_np * brightness, 0, 255)

        # ── Contrast ─────────────────────────────────────────────────
        if contrast_v != 1.0:
            mean_val = 128.0
            frame_np = np.clip((frame_np - mean_val) * contrast_v + mean_val, 0, 255)

        # ── Vignette ──────────────────────────────────────────────────
        if vignette_str > 0:
            vig = self._make_vignette(out_w, out_h, vignette_str)
            frame_np *= vig

        # ── Fade to black / white at end ──────────────────────────────
        fade_frames = max(1, int(fps_equiv * fade_dur))
        frames_left = total_frames - fi
        if fade_black and frames_left <= fade_frames:
            alpha = (frames_left - 1) / fade_frames
            frame_np = frame_np * max(0.0, alpha)
        elif fade_white and frames_left <= fade_frames:
            alpha = (frames_left - 1) / fade_frames
            frame_np = frame_np * max(0.0, alpha) + 255.0 * (1.0 - max(0.0, alpha))

        # ── Fade in from black (first 0.5 s) ─────────────────────────
        fade_in_frames = max(1, int(fps_equiv * 0.5))
        if fi < fade_in_frames:
            alpha = fi / max(fade_in_frames - 1, 1)
            frame_np = frame_np * alpha

        return np.clip(frame_np, 0, 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
#  FIREFLY GLOW (JUGNU)  — index 36
#  Painted area spawns glowing firefly particles that pulse, drift, and fade
#  in the dominant color of the painted region.  Each firefly has:
#    • soft radial glow bloom (sampled from the region's avg color)
#    • sinusoidal pulse brightness  (the "breathing" of a real firefly)
#    • gentle random drift staying inside / near the painted area
#    • random phase so they never all light up at the same time
# ─────────────────────────────────────────────────────────────────────────────
class FireflyGlowState:
    def __init__(self, mask: np.ndarray, static_np: np.ndarray):
        self.H, self.W = static_np.shape[:2]
        ys, xs = np.where(mask > 128)
        self._empty = len(xs) == 0
        if self._empty:
            return

        # Sample dominant color from the painted region
        region_pixels = static_np[ys, xs].astype(np.float32)   # (N,3)
        self._base_color = region_pixels.mean(axis=0)            # (R,G,B) float

        # Bounding box for spawn area
        self.y0 = int(ys.min()); self.y1 = int(ys.max()) + 1
        self.x0 = int(xs.min()); self.x1 = int(xs.max()) + 1

        # Store mask coords so fireflies stay inside
        self._mask_ys = ys.astype(np.float32)
        self._mask_xs = xs.astype(np.float32)
        self._soft_mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 6.0)

    def _init_fireflies(self, n: int):
        """Randomly place n fireflies inside the mask region."""
        idxs = np.random.choice(len(self._mask_xs), size=n, replace=True)
        px = self._mask_xs[idxs].copy()
        py = self._mask_ys[idxs].copy()
        # random drift velocities (pixels/sec)
        vx = np.random.uniform(-6.0,  6.0, n).astype(np.float32)
        vy = np.random.uniform(-4.0,  4.0, n).astype(np.float32)
        # pulse phase (0–2π) — staggered so they blink independently
        phase = np.random.uniform(0, math.tau, n).astype(np.float32)
        # pulse frequency (Hz) — each firefly blinks at a slightly different rate
        freq  = np.random.uniform(0.4, 1.8, n).astype(np.float32)
        # glow radius in pixels
        radii = np.random.uniform(3.0, 9.0, n).astype(np.float32)
        # base brightness multiplier per firefly
        bright = np.random.uniform(0.6, 1.4, n).astype(np.float32)
        return dict(px=px, py=py, vx=vx, vy=vy, phase=phase, freq=freq,
                    radii=radii, bright=bright, n=n)

    def draw(self, frame: np.ndarray, t: float, dt: float,
             n_flies: int, spd: float, glow_size: float, glow_strength: float) -> np.ndarray:
        if self._empty:
            return frame

        H, W = self.H, self.W
        key = '_ff'
        if not hasattr(self, key) or getattr(self, '_ff_n', 0) != n_flies:
            self._ff = self._init_fireflies(n_flies)
            self._ff_n = n_flies

        ff = self._ff

        # ── Drift fireflies ────────────────────────────────────────────────────
        ff['px'] += ff['vx'] * dt * spd
        ff['py'] += ff['vy'] * dt * spd

        # Bounce / wrap back inside mask bounding box + random nudge
        oob_x = (ff['px'] < self.x0) | (ff['px'] > self.x1)
        oob_y = (ff['py'] < self.y0) | (ff['py'] > self.y1)
        ff['vx'][oob_x] *= -1.0
        ff['vy'][oob_y] *= -1.0
        ff['px'] = np.clip(ff['px'], self.x0, self.x1 - 1)
        ff['py'] = np.clip(ff['py'], self.y0, self.y1 - 1)

        # Small random wander each frame
        ff['vx'] += np.random.uniform(-0.8, 0.8, ff['n']).astype(np.float32) * spd
        ff['vy'] += np.random.uniform(-0.5, 0.5, ff['n']).astype(np.float32) * spd
        speed_cap = 8.0 * spd
        ff['vx'] = np.clip(ff['vx'], -speed_cap, speed_cap)
        ff['vy'] = np.clip(ff['vy'], -speed_cap, speed_cap)

        # ── Render glow blobs onto a float buffer ─────────────────────────────
        glow_buf = np.zeros((H, W, 3), dtype=np.float32)

        cr, cg, cb = self._base_color   # dominant region color

        for i in range(ff['n']):
            # pulse brightness: sin²(freq·t + phase) → always 0-1, never negative
            pulse = math.pow(math.sin(ff['freq'][i] * t + ff['phase'][i]), 2)
            if pulse < 0.02:
                continue   # firefly is "off" — skip for speed

            alpha = pulse * ff['bright'][i] * glow_strength
            px = int(ff['px'][i])
            py = int(ff['py'][i])

            # Check pixel is inside soft mask (so fireflies stay on the painted area)
            if 0 <= py < H and 0 <= px < W:
                if self._soft_mask[py, px] < 0.08:
                    continue

            r = max(2.0, ff['radii'][i] * glow_size)
            ri = int(math.ceil(r * 3.0))   # sample radius for the bloom

            # Bounding box
            x0b = max(0, px - ri); x1b = min(W, px + ri + 1)
            y0b = max(0, py - ri); y1b = min(H, py + ri + 1)
            if x1b <= x0b or y1b <= y0b:
                continue

            # Build gaussian glow patch
            PX = np.arange(x0b, x1b, dtype=np.float32) - px
            PY = np.arange(y0b, y1b, dtype=np.float32) - py
            GX, GY = np.meshgrid(PX, PY)
            dist2 = GX**2 + GY**2
            bloom = np.exp(-dist2 / (2.0 * r * r)).astype(np.float32) * alpha

            # Core bright spot (smaller, extra bright)
            core_r = max(1.0, r * 0.35)
            core   = np.exp(-dist2 / (2.0 * core_r * core_r)).astype(np.float32) * alpha * 1.8

            total = bloom + core

            # Clamp by soft_mask so glow fades at region boundary
            mask_roi = self._soft_mask[y0b:y1b, x0b:x1b]
            total   *= mask_roi

            glow_buf[y0b:y1b, x0b:x1b, 0] += total * cr
            glow_buf[y0b:y1b, x0b:x1b, 1] += total * cg
            glow_buf[y0b:y1b, x0b:x1b, 2] += total * cb

        # ── Composite: Screen blend (never darkens the image) ─────────────────
        # Screen: out = 1 - (1-base)*(1-glow)
        base_f   = frame.astype(np.float32) / 255.0
        glow_clamped = np.clip(glow_buf / 255.0, 0.0, 1.0)
        screened = 1.0 - (1.0 - base_f) * (1.0 - glow_clamped)
        return np.clip(screened * 255.0, 0, 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
#  AI ORBIT / 2.5D PARALLAX  (index 37)
#
#  Uses MiDaS DPT_Large (already downloaded) to estimate per-pixel depth,
#  then simulates a virtual camera orbiting around the scene by displacing
#  each pixel proportional to its depth — foreground moves more than background.
#
#  Works on the FULL image (no mask needed — the entire frame participates).
#  Optionally a painted mask restricts the depth warp to just that region.
#
#  Camera orbit modes:
#    orbit   → smooth circular horizontal orbit  (Luma / Shiva style)
#    figure8 → figure-8 / lemniscate path
#    dolly   → push-in / pull-out breathing zoom combined with tilt
#    drift   → slow sinusoidal drift (landscape, peaceful)
#
#  Controls (via region params):
#    orbit_radius  → parallax strength in pixels  (default 30)
#    orbit_speed   → cycles per second             (default 0.25)
#    orbit_mode    → "orbit" | "figure8" | "dolly" | "drift"
#    depth_boost   → exponent applied to depth map  (default 1.5)
#    depth_invert  → bool; invert depth             (default False)
# ─────────────────────────────────────────────────────────────────────────────

class OrbitParallaxState:
    """
    MiDaS-powered 2.5D parallax / orbit animation.

    KEY DESIGN DECISIONS (bugs fixed v2):
    ─────────────────────────────────────
    • Depth map is computed from the ORIGINAL full-res static image at init,
      then lazily resized to match whatever resolution draw() receives each frame
      (preview uses display-res; export uses full-res — both work correctly).
    • The warp source is always the current `frame` argument, NOT a stale copy
      stored at init time.  This means it composites correctly with all other
      animation layers that ran before it in the pipeline.
    • No mask guard — atype 37 is exempt from the `m.any()` skip (like atype 35),
      so it always runs even when no region is painted.
    • MiDaS transform returns a (1,3,H,W) batch tensor.  We handle squeeze
      carefully to avoid removing the wrong dimension when H or W == 1.
    """

    _MIDAS_MODEL     = None
    _MIDAS_TRANSFORM = None
    _MIDAS_DEVICE    = None
    _MIDAS_LOADED    = False
    _MIDAS_AVAILABLE = False

    # ── MiDaS loader (class-level singleton) ─────────────────────────────────
    @classmethod
    def _load_midas(cls):
        if cls._MIDAS_LOADED:
            return
        cls._MIDAS_LOADED = True
        try:
            import torch

            model = torch.hub.load(
                "intel-isl/MiDaS", "DPT_Large",
                pretrained=True, trust_repo=True,
            )
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model.to(device).eval()

            midas_transforms = torch.hub.load(
                "intel-isl/MiDaS", "transforms", trust_repo=True,
            )
            transform = midas_transforms.dpt_transform   # expects RGB HWC uint8

            cls._MIDAS_MODEL     = model
            cls._MIDAS_TRANSFORM = transform
            cls._MIDAS_DEVICE    = device
            cls._MIDAS_AVAILABLE = True
        except Exception:
            cls._MIDAS_AVAILABLE = False

    @classmethod
    def _run_midas(cls, rgb_np: np.ndarray) -> np.ndarray:
        """Run MiDaS on an RGB HWC uint8 array → float32 H×W depth (0=far,1=near)."""
        import torch
        inp = cls._MIDAS_TRANSFORM(rgb_np).to(cls._MIDAS_DEVICE)   # (1,3,H',W')
        with torch.no_grad():
            pred = cls._MIDAS_MODEL(inp)                             # (1,H',W')
        # resize back to original size
        pred_up = torch.nn.functional.interpolate(
            pred.unsqueeze(1).float(),
            size=rgb_np.shape[:2],
            mode="bicubic",
            align_corners=False,
        )                                                            # (1,1,H,W)
        depth = pred_up[0, 0].cpu().numpy().astype(np.float32)      # H×W
        # MiDaS inverse-depth: large = close → normalise to 0-1 (1=close)
        d_min, d_max = depth.min(), depth.max()
        if d_max > d_min:
            depth = (depth - d_min) / (d_max - d_min)
        return depth

    @classmethod
    def _estimate_depth(cls, rgb_np: np.ndarray) -> np.ndarray:
        """Return H×W float32 depth map (0=far, 1=near).  Fallback if no MiDaS."""
        cls._load_midas()
        if cls._MIDAS_AVAILABLE:
            try:
                return cls._run_midas(rgb_np)
            except Exception:
                pass
        # ── Fallback: centre-weighted Gaussian pseudo-depth ──────────────────
        # Works surprisingly well for portraits / statues: bright, central
        # regions are assumed closer.
        gray = cv2.cvtColor(rgb_np, cv2.COLOR_RGB2GRAY).astype(np.float32)
        H, W = gray.shape
        # Smooth out texture — just keep large-scale brightness variation
        blur_r = int(max(H, W) * 0.08) | 1   # must be odd
        blurred = cv2.GaussianBlur(gray, (blur_r, blur_r), 0)
        # Add a gentle radial centre-bias so the subject reads as "close"
        cy, cx = H / 2.0, W / 2.0
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        radial = 1.0 - np.sqrt(((xs - cx) / (W * 0.6)) ** 2 +
                                ((ys - cy) / (H * 0.6)) ** 2)
        radial = np.clip(radial, 0, 1)
        depth = blurred / 255.0 * 0.7 + radial * 0.3
        d_min, d_max = depth.min(), depth.max()
        if d_max > d_min:
            depth = (depth - d_min) / (d_max - d_min)
        return depth

    # ── Instance ─────────────────────────────────────────────────────────────
    def __init__(self, static_np: np.ndarray, mask: np.ndarray | None = None):
        """
        static_np : full-resolution source image (RGB uint8)
        mask      : optional painted mask at same resolution (uint8 0/255)
                    None or all-zero → full-frame effect
        """
        self._orig_H, self._orig_W = static_np.shape[:2]

        # Depth map at ORIGINAL resolution — will be resized on demand
        self._depth_orig = self._estimate_depth(static_np)   # H×W float32 0-1

        # Painted mask (full-frame if None/empty)
        if mask is not None and mask.any():
            self._mask_orig = cv2.GaussianBlur(
                mask.astype(np.float32) / 255.0, (0, 0), 6.0)
        else:
            self._mask_orig = None   # means "full frame"

        # Cache for the last frame size we saw (avoids recomputing grids every frame)
        self._cached_H = None
        self._cached_W = None
        self._depth_scaled = None
        self._mask_scaled  = None
        self._xs_g = None
        self._ys_g = None

    def _ensure_grids(self, H: int, W: int):
        """Lazily build / rebuild coordinate grids when frame size changes."""
        if self._cached_H == H and self._cached_W == W:
            return
        self._cached_H, self._cached_W = H, W

        # Resize depth to match current frame size
        if self._orig_H == H and self._orig_W == W:
            self._depth_scaled = self._depth_orig
        else:
            self._depth_scaled = cv2.resize(
                self._depth_orig, (W, H), interpolation=cv2.INTER_LINEAR)

        # Resize mask (or create full-frame one)
        if self._mask_orig is None:
            self._mask_scaled = np.ones((H, W), dtype=np.float32)
        elif self._mask_orig.shape == (H, W):
            self._mask_scaled = self._mask_orig
        else:
            self._mask_scaled = cv2.resize(
                self._mask_orig, (W, H), interpolation=cv2.INTER_LINEAR)

        # Base coordinate grids
        xs_1d = np.arange(W, dtype=np.float32)
        ys_1d = np.arange(H, dtype=np.float32)
        self._xs_g, self._ys_g = np.meshgrid(xs_1d, ys_1d)   # H×W

    # ── Camera path helpers ───────────────────────────────────────────────────
    @staticmethod
    def _cam_orbit(t, speed, radius):
        a = t * speed * math.tau
        return math.sin(a) * radius, math.cos(a) * radius * 0.38

    @staticmethod
    def _cam_figure8(t, speed, radius):
        a = t * speed * math.tau
        d = 1.0 + math.sin(a) ** 2 + 1e-6
        return radius * math.cos(a) / d, radius * 0.48 * math.sin(2 * a) / d

    @staticmethod
    def _cam_dolly(t, speed, radius):
        a = t * speed * math.tau
        return math.sin(a) * radius * 0.10, math.sin(a * 0.5 + 0.7) * radius * 0.38

    @staticmethod
    def _cam_drift(t, speed, radius):
        return (radius * 0.65 * math.sin(t * speed * math.tau),
                radius * 0.32 * math.sin(t * speed * math.tau * 0.61))

    # ── Main draw ─────────────────────────────────────────────────────────────
    def draw(self, frame: np.ndarray, t: float,
             orbit_radius: float = 30.0,
             orbit_speed:  float = 0.25,
             orbit_mode:   str   = "orbit",
             depth_boost:  float = 1.5,
             depth_invert: bool  = False) -> np.ndarray:

        H, W = frame.shape[:2]
        self._ensure_grids(H, W)

        # ── 1. Camera displacement ────────────────────────────────────────
        r = max(1.0, orbit_radius)
        s = max(0.01, orbit_speed)
        _paths = {"figure8": self._cam_figure8,
                  "dolly":   self._cam_dolly,
                  "drift":   self._cam_drift}
        cam_x, cam_y = _paths.get(orbit_mode, self._cam_orbit)(t, s, r)

        # ── 2. Depth → per-pixel parallax displacement ────────────────────
        depth = self._depth_scaled.copy()
        if depth_invert:
            depth = 1.0 - depth

        # Sharpen the depth separation: boost > 1 makes near pixels shift a LOT
        # more than far pixels, producing visible 3-D "pop"
        depth_w = np.power(np.clip(depth, 0, 1), max(0.1, depth_boost))

        # When camera moves RIGHT (+cam_x), foreground pixels must move LEFT
        # (negative source offset) to simulate parallax correctly.
        disp_x = depth_w * (-cam_x) * self._mask_scaled
        disp_y = depth_w * (-cam_y) * self._mask_scaled

        # ── 3. Warp THE LIVE FRAME (not a stale init copy) ───────────────
        # This means other animation effects that ran earlier are preserved.
        src_x = np.clip(self._xs_g + disp_x, 0, W - 1).astype(np.float32)
        src_y = np.clip(self._ys_g + disp_y, 0, H - 1).astype(np.float32)

        warped = cv2.remap(
            frame, src_x, src_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

        # ── 4. Composite: warped inside mask, original outside ────────────
        mask3 = self._mask_scaled[:, :, np.newaxis]
        out = (
            frame.astype(np.float32) * (1.0 - mask3)
            + warped.astype(np.float32) * mask3
        ).astype(np.uint8)

        return out


# ─────────────────────────────────────────────────────────────────────────────
#  3D CAMERA FLY-THROUGH  (After Effects-style parallax depth layers)
#
#  This system lets you define a stack of DEPTH LAYERS — each layer is a
#  painted region with its own:
#    • depth (Z position, 0 = background, 1 = foreground/main object)
#    • animation type (from ANIM_TYPES)
#    • blur (shallow depth-of-field: far layers are blurrier)
#    • scale factor (far layers scale down, near layers scale up)
#    • horizontal/vertical parallax multiplier
#
#  The virtual camera FLIES through all layers toward the main object:
#    - Phase 1 (0–50%): camera accelerates through far background layers
#    - Phase 2 (50–80%): camera decelerates past mid layers
#    - Phase 3 (80–100%): arrives at / orbits around main object
#
#  Camera motion styles:
#    "Fly Through"    — straight cinematic push-in through layers
#    "Arc Fly"        — sweeping arc trajectory
#    "Spiral Descent" — helical spiral toward subject
#    "Slow Reveal"    — gentle drift forward with drift
#    "Warp Speed"     — fast push with star-field stretch effect
# ─────────────────────────────────────────────────────────────────────────────

DEPTH_CAMERA_MODES = [
    "Fly Through",
    "Arc Fly",
    "Spiral Descent",
    "Slow Reveal",
    "Warp Speed",
]


def _depth_ease(t: float, mode: str) -> float:
    """Easing for camera progress 0→1."""
    t = max(0.0, min(1.0, t))
    if mode == "Fly Through":
        # Ease in strongly, then decelerate hard approaching subject
        if t < 0.6:
            return _ease_in_expo(t / 0.6) * 0.6
        return 0.6 + _ease_out_quad((t - 0.6) / 0.4) * 0.4
    elif mode == "Arc Fly":
        return _ease_in_out_cubic(t)
    elif mode == "Spiral Descent":
        return t * t * (3.0 - 2.0 * t)  # smoothstep
    elif mode == "Slow Reveal":
        return _ease_in_out_sine(t)
    elif mode == "Warp Speed":
        if t < 0.75:
            return _ease_in_expo(t / 0.75) * 0.85
        return 0.85 + (t - 0.75) / 0.25 * 0.15
    return t


def apply_3d_depth_layers(frame: np.ndarray, t: float, duration: float,
                           depth_layers: list, params: dict) -> np.ndarray:
    """
    Apply 3D camera fly-through effect compositing depth-separated layers.

    depth_layers: list of dicts, each:
        {
          'depth':   float 0..1,   # 0=background, 1=main subject
          'image':   np.ndarray,   # the rendered layer image (H×W×3)
          'mask':    np.ndarray,   # alpha mask (H×W) uint8
          'blur':    float,        # dof blur sigma (auto if None)
          'opacity': float,        # layer opacity 0..1
        }

    params: dict with keys:
        'cam_mode'    : str  (DEPTH_CAMERA_MODES)
        'cam_speed'   : float   0.1–3.0
        'dof_strength': float   depth-of-field blur amount
        'parallax_x'  : float   horizontal parallax strength px
        'parallax_y'  : float   vertical parallax strength px
        'scale_range' : float   how much near layers scale up (default 0.35)
        'vignette'    : float   0–1
        'chroma_ab'   : float   chromatic aberration on far layers
        'fog_near'    : float   atmospheric fog on far layers
    """
    if not depth_layers:
        return frame

    H, W = frame.shape[:2]
    mode       = params.get('cam_mode', 'Fly Through')
    cam_speed  = float(params.get('cam_speed', 1.0))
    dof_str    = float(params.get('dof_strength', 0.5))
    par_x      = float(params.get('parallax_x', 40.0))
    par_y      = float(params.get('parallax_y', 20.0))
    scale_rng  = float(params.get('scale_range', 0.35))
    vignette_s = float(params.get('vignette', 0.4))
    chroma_ab  = float(params.get('chroma_ab', 0.5))
    fog_near   = float(params.get('fog_near', 0.3))

    # Normalised time 0→1 over the animation duration
    raw_t = (t * cam_speed) / max(1.0, duration)
    raw_t = math.fmod(raw_t, 1.0)          # loop
    cam_prog = _depth_ease(raw_t, mode)    # eased camera progress

    # Camera path offsets based on mode
    if mode == "Arc Fly":
        cam_arc_x = math.sin(raw_t * math.pi) * par_x * 0.8
        cam_arc_y = -math.sin(raw_t * math.pi * 0.5) * par_y * 0.6
    elif mode == "Spiral Descent":
        angle = raw_t * math.tau * 1.5
        cam_arc_x = math.cos(angle) * par_x * (1.0 - raw_t) * 0.9
        cam_arc_y = math.sin(angle) * par_y * (1.0 - raw_t) * 0.5
    elif mode == "Slow Reveal":
        cam_arc_x = math.sin(t * 0.38) * par_x * 0.4
        cam_arc_y = math.cos(t * 0.27) * par_y * 0.25
    elif mode == "Warp Speed":
        cam_arc_x = math.sin(t * 1.1) * par_x * 0.15
        cam_arc_y = math.cos(t * 0.9) * par_y * 0.10
    else:  # Fly Through
        cam_arc_x = math.sin(t * 0.5) * par_x * 0.3
        cam_arc_y = math.cos(t * 0.35) * par_y * 0.18

    # Sort layers back-to-front (depth 0 = far → render first)
    sorted_layers = sorted(depth_layers, key=lambda l: l.get('depth', 0.5))

    out = frame.copy()

    for layer in sorted_layers:
        depth    = float(layer.get('depth', 0.5))
        img      = layer.get('image')
        mask     = layer.get('mask')
        opacity  = float(layer.get('opacity', 1.0))

        if img is None or mask is None:
            continue
        if img.shape[:2] != (H, W):
            img = cv2.resize(img, (W, H), interpolation=cv2.INTER_LINEAR)
        if mask.shape[:2] != (H, W):
            mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_NEAREST)

        # ── 1. Parallax displacement — far layers move MORE (reversed parallax) ──
        # When camera moves right, far layers shift left more than near layers
        inv_depth = 1.0 - depth   # 1 for far, 0 for near (main subject)
        layer_par_x = cam_arc_x * inv_depth * 1.8
        layer_par_y = cam_arc_y * inv_depth * 1.2

        # ── 2. Depth-based scale —  camera approaching = near layers enlarge ──
        # As cam_prog goes 0→1, near (high depth) layers grow, far layers stay
        scale_boost = 1.0 + scale_rng * depth * cam_prog
        # Far layers also get a slight shrink so they feel distant
        far_shrink  = 1.0 - (1.0 - depth) * 0.12 * (1.0 - cam_prog)
        final_scale = scale_boost * far_shrink

        # ── 3. Apply scale + pan to this layer ───────────────────────────────
        cx, cy = W * 0.5 + layer_par_x, H * 0.5 + layer_par_y
        M_scale = cv2.getRotationMatrix2D((W * 0.5, H * 0.5), 0.0, final_scale)
        M_scale[0, 2] += layer_par_x
        M_scale[1, 2] += layer_par_y

        img_t  = cv2.warpAffine(img,  M_scale, (W, H),
                                flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REFLECT)
        mask_t = cv2.warpAffine(mask, M_scale, (W, H),
                                flags=cv2.INTER_NEAREST,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)

        # ── 4. Depth-of-Field blur (far layers blurrier) ──────────────────────
        auto_blur = layer.get('blur', None)
        if auto_blur is None:
            blur_sigma = dof_str * inv_depth * 6.0 * (1.0 - cam_prog * depth)
        else:
            blur_sigma = float(auto_blur)
        if blur_sigma > 0.5:
            img_t = cv2.GaussianBlur(img_t, (0, 0), blur_sigma)

        # ── 5. Atmospheric fog on far layers ──────────────────────────────────
        if fog_near > 0.01 and inv_depth > 0.15:
            fog_alpha = fog_near * inv_depth * (1.0 - cam_prog * 0.8) * 0.6
            fog_color = np.array([200, 210, 220], dtype=np.float32)
            img_t = (img_t.astype(np.float32) * (1.0 - fog_alpha)
                     + fog_color * fog_alpha).clip(0, 255).astype(np.uint8)

        # ── 6. Chromatic aberration on very far layers ───────────────────────
        if chroma_ab > 0.1 and inv_depth > 0.5:
            shift = max(1, int(chroma_ab * inv_depth * 3.0 * (1.0 - cam_prog)))
            if shift > 0 and shift < W // 4:
                ca = img_t.copy()
                ca[:, shift:, 0] = img_t[:, :W - shift, 0]
                ca[:, :W - shift, 2] = img_t[:, shift:, 2]
                img_t = ca

        # ── 7. Composite this layer onto output using soft mask ───────────────
        soft_mask = cv2.GaussianBlur(mask_t.astype(np.float32) / 255.0,
                                     (0, 0), 4.0) * opacity
        m3 = soft_mask[:, :, np.newaxis]
        out = (out.astype(np.float32) * (1.0 - m3)
               + img_t.astype(np.float32) * m3).clip(0, 255).astype(np.uint8)

    # ── 8. Vignette darkens toward edges ─────────────────────────────────────
    if vignette_s > 0.01:
        Y_v, X_v = np.mgrid[0:H, 0:W].astype(np.float32)
        r_v = np.hypot((X_v - W / 2) / (W / 2), (Y_v - H / 2) / (H / 2))
        vig = np.clip(1.0 - r_v ** 2 * vignette_s * 1.35, 0.05, 1.0)
        out = (out.astype(np.float32) * vig[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)

    # ── 9. Warp Speed star-stretch effect ────────────────────────────────────
    if mode == "Warp Speed" and cam_prog > 0.5:
        stretch = (cam_prog - 0.5) * 2.0 * 0.4
        if stretch > 0.02:
            s_h = int(H * stretch * 0.5)
            if s_h > 1:
                top_strip    = out[:s_h, :].copy()
                bottom_strip = out[H - s_h:, :].copy()
                out[:s_h, :]    = cv2.GaussianBlur(top_strip,    (1, max(3, s_h | 1)), s_h * 0.5)
                out[H - s_h:, :] = cv2.GaussianBlur(bottom_strip, (1, max(3, s_h | 1)), s_h * 0.5)

    return out


def render_frame(static_np, regions, t, dt, extra_states,
                 bg_source=None, bg_alpha=1.0, bg_mode="Normal",
                 fg_source=None, fg_alpha=1.0, fg_mode="Normal",
                 smoke_enabled=False, smoke_params=None,
                 camera_params=None,
                 depth3d_params=None, depth3d_layers=None):
    H, W = static_np.shape[:2]
    if bg_source is not None:
        bg_frame = bg_source.get_frame(t, W, H)
        canvas = _blend_layers(np.zeros((H,W,3),dtype=np.uint8), bg_frame, bg_alpha, bg_mode)
    else:
        canvas = None
    if canvas is None:
        out = static_np.copy()
    else:
        base_rgba = np.dstack([static_np, np.full((H,W),255,dtype=np.uint8)])
        out = _blend_layers(canvas, base_rgba, 1.0, "Normal")
    out = render_regions(out, regions, t, dt, extra_states, fg_np=(fg_source.get_frame(t, W, H) if fg_source is not None else None))
    # Check if any Living Painting region consumed the FG — if so skip normal FG composite
    _fg_consumed = any(r.get('anim_type') == 29 for r in regions) and fg_source is not None
    if fg_source is not None and not _fg_consumed:
        fg_frame = fg_source.get_frame(t, W, H)
        out = _blend_layers(out, fg_frame, fg_alpha, fg_mode)
    if smoke_enabled and smoke_params:
        smoke_key = '__smoke__'
        if smoke_key not in extra_states:
            extra_states[smoke_key] = SmokeState()
        out = extra_states[smoke_key].render(
            out, t, dt,
            color_name  = smoke_params.get('color', 'White'),
            wind_deg    = smoke_params.get('wind_deg', 270.0),
            density     = smoke_params.get('density', 1.0),
            speed       = smoke_params.get('speed', 1.0),
            turbulence  = smoke_params.get('turbulence', 0.5),
            opacity     = smoke_params.get('opacity', 0.7),
        )
    # ── 3D Depth Layer fly-through (applied before final camera) ─────────────
    if depth3d_params is not None and depth3d_layers:
        dur = float(depth3d_params.get('_duration', 8.0))
        out = apply_3d_depth_layers(out, t, dur, depth3d_layers, depth3d_params)
    if camera_params is not None:
        camera_params["_t"] = t
        out = apply_camera_transform(out, camera_params)
    return out


def render_regions(static_np, regions, t, dt, extra_states, fg_np=None):
    H,W=static_np.shape[:2];out=static_np.copy()
    xs_g=np.linspace(0,1,W,dtype=np.float32);ys_g=np.linspace(0,1,H,dtype=np.float32);gx,gy=np.meshgrid(xs_g,ys_g)
    for ri,reg in enumerate(regions):
        mask=reg['mask'];atype=reg['anim_type'];p=reg['params']
        amp=float(p.get('amp',14));freq=float(p.get('freq',2.0));spd=float(p.get('spd',1.5));turb=float(p.get('turb',0.4));dispersion=float(p.get('dispersion',0.25))
        start_t=float(p.get('start_t',0.0));end_t=float(p.get('end_t',9999.0))
        if t<start_t or t>end_t:continue
        phase=t*spd*2.0*math.pi;m=(mask>128)
        if not m.any() and atype not in (35, 37):continue
        if atype==0:
            c_amp=float(p.get('c_amp',amp));c_freq=float(p.get('c_freq',freq));c_spd=float(p.get('c_spd',spd));c_amp2=float(p.get('c_amp2',c_amp*0.35));c_freq2=float(p.get('c_freq2',c_freq*2.1));c_drape=float(p.get('c_drape',0.55));c_shear=float(p.get('c_shear',0.25));c_turb=float(p.get('c_turb',turb));c_phase2=float(p.get('c_phase2',1.47))
            ph2=t*c_spd*2.0*math.pi;weight=np.power(np.clip(gy,0,1),c_drape*1.8+0.2)
            dr_primary=c_amp*np.sin(2*math.pi*c_freq*gx+ph2)*weight;dr_secondary=c_amp2*np.sin(2*math.pi*c_freq2*gx+ph2+c_phase2)*weight;dr_shear=c_amp*c_shear*np.sin(2*math.pi*c_freq*0.7*(gx+gy*0.4)+ph2*0.8)*weight;dc_lateral=c_amp*0.22*np.sin(2*math.pi*c_freq*0.5*gy+ph2*0.6)*weight
            if c_turb>0:nx=noise2d(gx*c_freq*1.2+t*0.5,gy*c_freq*0.9+t*0.7).astype(np.float32);ny=noise2d(gy*c_freq*1.0+t*0.8,gx*c_freq*0.7+t*0.4).astype(np.float32);dc_lateral+=c_turb*c_amp*0.14*nx*weight;dr_primary+=c_turb*c_amp*0.10*ny*weight
            dr_total=(dr_primary+dr_secondary+dr_shear).astype(np.float32);dc_total=dc_lateral.astype(np.float32);blur_sigma=max(2.0,c_amp*0.18);dr_total=cv2.GaussianBlur(dr_total,(0,0),blur_sigma);dc_total=cv2.GaussianBlur(dc_total,(0,0),blur_sigma)
            src_x=np.clip((gx*W)+dc_total,0,W-1).astype(np.float32);src_y=np.clip((gy*H)+dr_total,0,H-1).astype(np.float32);warped=cv2.remap(static_np,src_x,src_y,cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
            feather_sigma=4.0;mask_f=cv2.GaussianBlur(mask.astype(np.float32)/255.0,(0,0),feather_sigma);mask3=mask_f[:,:,np.newaxis];out=(out.astype(np.float32)*(1.0-mask3)+warped.astype(np.float32)*mask3).astype(np.uint8)
        elif atype==1:
            tip=np.power(np.clip(1-gy,0,1),0.4)*0.1+np.power(np.clip(gy,0,1),0.5)*0.9;base_wind=amp*np.sin(2*math.pi*freq*gx+phase)*tip;nx=noise2d(gx*freq*2+t*0.7,gy*freq+t*0.9).astype(np.float32);ny=noise2d(gy*3+t*1.1,gx*2+t*0.6).astype(np.float32);gust=amp*0.4*np.sin(2*math.pi*freq*0.3*gx+phase*0.35)*tip;dc=turb*amp*0.5*nx*tip+gust*0.3;dr=base_wind+turb*amp*0.3*ny*tip
            src_x=np.clip((gx*W)+dc,0,W-1).astype(np.float32);src_y=np.clip((gy*H)+dr,0,H-1).astype(np.float32);warped=cv2.remap(static_np,src_x,src_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE);m3=m[:,:,np.newaxis].repeat(3,axis=2);out[m3]=warped[m3]
        elif atype==2:
            cx2,cy2=0.5,0.5;dist=np.sqrt((gx-cx2)**2+(gy-cy2)**2)+1e-4;wave=amp*np.sin(2*math.pi*freq*dist*8-phase)*np.exp(-dist*3.5);dc=(gx-cx2)/dist*wave*0.5;dr=(gy-cy2)/dist*wave*0.5
            if dispersion>0.001:
                dc+=noise2d(gx*7.0+t*1.1,gy*6.0+11.0).astype(np.float32)*amp*dispersion*0.18
                dr+=noise2d(gy*7.5-t*0.9,gx*5.5+23.0).astype(np.float32)*amp*dispersion*0.18
            src_x=np.clip((gx*W)+dc,0,W-1).astype(np.float32);src_y=np.clip((gy*H)+dr,0,H-1).astype(np.float32);warped=cv2.remap(static_np,src_x,src_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE);m3=m[:,:,np.newaxis].repeat(3,axis=2);out[m3]=warped[m3]
        elif atype==3:
            pin=np.power(gx,1.4);dr=(amp*pin*np.sin(2*math.pi*freq*gx-phase)+amp*0.3*pin*np.sin(2*math.pi*freq*2.3*gx-phase*1.3+gy))
            src_x=np.clip((gx*W),0,W-1).astype(np.float32);src_y=np.clip((gy*H)+dr,0,H-1).astype(np.float32);warped=cv2.remap(static_np,src_x,src_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE);m3=m[:,:,np.newaxis].repeat(3,axis=2);out[m3]=warped[m3]
        elif atype==4:
            key=('thunder',ri)
            if key not in extra_states:extra_states[key]=ThunderState()
            st=extra_states[key];st.update(t);out=st.draw(out,mask,dt)
        elif atype==5:
            key=('bokeh',ri)
            if key not in extra_states:extra_states[key]=BokehState(mask)
            st=extra_states[key];st.update(dt,spd);out=st.draw(out)
        elif atype==6:
            key=('plasma',ri)
            if key not in extra_states:extra_states[key]=PlasmaState(mask)
            out=extra_states[key].draw(out,t,amp)
        elif atype==7:
            key=('twinkle',ri)
            if key not in extra_states:extra_states[key]=TwinkleState(mask)
            out=extra_states[key].draw(out,t)
        elif atype==8:
            key=('falling',ri)
            if key not in extra_states:extra_states[key]=FallingParticles(mask,reg.get('static_np',static_np),fall_delay_max=float(p.get('fall_delay',5.0)),tile_size=max(8,int(amp*1.2)),repeat=bool(p.get('repeat',False)),repeat_min=float(p.get('repeat_min',2.0)),repeat_max=float(p.get('repeat_max',8.0)))
            st=extra_states[key];st.update(t,dt,spd);out=st.draw(out)
        elif atype==9:
            key=('leafwind',ri)
            if key not in extra_states:extra_states[key]=LeafWindState(mask,n=max(20,int(amp*3.5)))
            st=extra_states[key];st.update(t,dt,spd);out=st.draw(out)
        elif atype==10:
            direction=float(p.get('direction',0.0));density=float(p.get('density',0.8));rad=math.radians(direction);dx_dir=math.cos(rad);dy_dir=math.sin(rad)
            ys2,xs2=np.where(m);xn=xs2.astype(np.float32)/W;yn=ys2.astype(np.float32)/H;fog=np.zeros(len(xs2),dtype=np.float32)
            for octave in range(4):
                sc=float(2**octave);speed=0.07*(octave+1)*spd;ox_=t*speed*dx_dir;oy_=t*speed*dy_dir;v=noise2d(xn*sc*2.5+ox_,yn*sc*2.0+oy_);fog+=v/(2.0**octave)
            fog=(fog/1.75+1.0)/2.0;fog=np.clip(fog*density*(amp/20.0),0,0.92);fog_col=np.array([205,220,232],dtype=np.float32);frame_roi=out[ys2,xs2].astype(np.float32);a3=fog[:,np.newaxis];out[ys2,xs2]=(frame_roi*(1.0-a3)+fog_col*a3).astype(np.uint8)
        elif atype==11:
            key=('flowerfall',ri)
            if key not in extra_states:extra_states[key]=FlowerFallState(mask,reg.get('static_np',static_np),speed=spd,total_secs=max(3.0,float(p.get('fall_delay',5.0))),repeat=bool(p.get('repeat',True)))
            st=extra_states[key];st.update(t,dt,spd);out=st.draw(out)
        elif atype==12:
            key=('scroll',ri)
            if key not in extra_states:extra_states[key]=ScrollFlowState(mask,static_np)
            out=extra_states[key].draw(out,t,spd,float(p.get('direction',90.0)),float(p.get('stretch',0.5))+dispersion*0.35)
        elif atype==13:
            key=('clouds',ri);color_name=p.get('cloud_color','White');n_clouds=max(1,int(round(float(p.get('cloud_count',10)))))
            if key not in extra_states:extra_states[key]=CloudMovingState(mask,n=n_clouds,color_name=color_name)
            direction=float(p.get('cloud_dir',90.0));opacity=float(p.get('cloud_alpha',0.85));st=extra_states[key];st.update(t,dt,spd,direction,n_clouds);out=st.draw(out,opacity)
        elif atype==14:
            key=('rain',ri)
            if key not in extra_states:n_drops=max(50,int(amp*18));extra_states[key]=RainState(mask,n=n_drops)
            wind_deg=float(p.get('rain_angle',90.0));density=float(p.get('rain_density',0.8));out=extra_states[key].draw(out,t,spd,wind_deg,density)
        elif atype==15:
            key=('sun',ri)
            if key not in extra_states:extra_states[key]=SunOrbState(mask)
            out=extra_states[key].draw(out,t,sun_x_pct=float(p.get('sun_x',50.0)),sun_y_pct=float(p.get('sun_y',50.0)),size=float(p.get('sun_size',18.0)),glow_strength=float(p.get('sun_glow',0.7)),n_rays=float(p.get('sun_rays',12.0)),orbit_radius=float(p.get('orbit_radius',0.0)),orbit_speed=float(p.get('orbit_speed',0.1)),energy_color_name=p.get('sun_color','Solar Yellow'))
        elif atype==16:
            key=('float',ri)
            if key not in extra_states:extra_states[key]=FloatingObjectState(mask,reg.get('static_np',static_np))
            out=extra_states[key].draw(out,t,amp,freq,spd)
        elif atype==17:
            key=('updown',ri)
            if key not in extra_states:extra_states[key]=UpDownState(mask,reg.get('static_np',static_np))
            out=extra_states[key].draw(out,reg.get('static_np',static_np),t,amp,freq,spd)
        elif atype==18:   # ── SPIN FLOAT (new) ──────────────────────────────
            key=('spinf',ri)
            if key not in extra_states:
                extra_states[key]=SpinFloatState(mask,reg.get('static_np',static_np))
            spin_speed  = float(p.get('spin_speed', 1.0))
            bob_lateral = float(p.get('bob_lateral', 0.25))
            out = extra_states[key].draw(out, t, amp, freq, spd,
                                         spin_speed=spin_speed,
                                         bob_lateral=bob_lateral)
        elif atype==19:
            key=('asmoke',ri)
            if key not in extra_states:extra_states[key]=AreaSmokeState(mask)
            out=extra_states[key].draw(out,dt,density=max(0.4,amp/16.0),speed=spd,opacity=min(1.0,0.35+turb*0.8))
        elif atype==20:
            key=('acloud',ri)
            if key not in extra_states:extra_states[key]=AreaCloudState(mask)
            out=extra_states[key].draw(out,dt,speed=spd,opacity=min(1.0,0.55+turb*0.35))
        elif atype==21:
            key=('afire',ri)
            if key not in extra_states:extra_states[key]=AreaFireState(mask)
            out=extra_states[key].draw(out,dt,intensity=amp,speed=spd)
        elif atype==22:
            key=('wflow',ri)
            if key not in extra_states:extra_states[key]=WaterFlowState(mask,reg.get('static_np',static_np))
            out=extra_states[key].draw(out,t,amp,freq,spd,float(p.get('direction',90.0)),dispersion,float(p.get('foam',0.55)))
        elif atype==23:
            key=('leap_hop',ri)
            if key not in extra_states:extra_states[key]=MotionLeapState(mask,reg.get('static_np',static_np),mode="hop")
            out=extra_states[key].draw(out,t,amp,freq,spd,dispersion)
        elif atype==24:
            key=('leap_side',ri)
            if key not in extra_states:extra_states[key]=MotionLeapState(mask,reg.get('static_np',static_np),mode="side")
            out=extra_states[key].draw(out,t,amp,freq,spd,dispersion)
        elif atype==25:
            key=('leap_pulse',ri)
            if key not in extra_states:extra_states[key]=MotionLeapState(mask,reg.get('static_np',static_np),mode="pulse")
            out=extra_states[key].draw(out,t,amp,freq,spd,dispersion)
        elif atype==26:
            out=_render_motion_paths(
                reg.get('static_np',static_np), out, mask,
                reg.get('freeze_mask'),
                reg.get('paths', []),
                reg.get('anchors', []),
                t, amp, freq, spd, dispersion,
                path_radius=float(p.get('path_radius', 70.0)),
                anchor_strength=float(p.get('anchor_strength', 1.0)),
            )
        elif atype==27:
            out=_render_3to2_ratio_sway(
                reg.get('static_np',static_np), out, mask,
                t, amp, freq, spd, dispersion,
            )
        elif atype==28:
            out=_render_flutter_pixaloop(
                reg.get('static_np',static_np), out, mask,
                reg.get('freeze_mask'),
                reg.get('paths', []),
                reg.get('anchors', []),
                t, amp, freq, spd, dispersion,
                path_radius=float(p.get('path_radius', 70.0)),
                anchor_strength=float(p.get('anchor_strength', 1.0)),
                motion_type=p.get('pixaloop_motion', 'seamless'),
            )
        elif atype==29:   # ── LIVING PAINTING ───────────────────────────────
            key=('livepaint',ri)
            if key not in extra_states:
                extra_states[key]=LivingPaintingState(mask,reg.get('static_np',static_np),fg_np=fg_np)
            lp_state=extra_states[key]
            # Auto-loop: reset when simulation passes the loop window
            loop_dur=float(p.get('lp_loop',10.0))
            loop_t=math.fmod(t,max(1.0,loop_dur))
            if loop_t<getattr(lp_state,'_last_loop_t',0.0):
                lp_state.reset()
            lp_state._last_loop_t=loop_t
            out=lp_state.draw(out,mask,loop_t,dt,amp,spd)
        # ── MOTIONLEAP STRIP ANIMATIONS (from agent.py) ───────────────────
        elif atype==30:   # ML Strip Wave (Sine)
            out=_render_ml_strip(
                reg.get('static_np',static_np), out, mask, t,
                amp=amp, freq=freq, spd=spd,
                direction=float(p.get('direction', 0.0)),
                feather_radius=int(p.get('feather_radius', 8)),
                num_strips=max(10, int(p.get('num_strips', 40))),
                wave_type='sine',
            )
        elif atype==31:   # ML Strip Flow (Seamless)
            out=_render_ml_strip(
                reg.get('static_np',static_np), out, mask, t,
                amp=amp, freq=freq, spd=spd,
                direction=float(p.get('direction', 0.0)),
                feather_radius=int(p.get('feather_radius', 8)),
                num_strips=max(10, int(p.get('num_strips', 40))),
                wave_type='flow',
            )
        elif atype==32:   # ML Strip Ripple
            out=_render_ml_strip(
                reg.get('static_np',static_np), out, mask, t,
                amp=amp, freq=freq, spd=spd,
                direction=float(p.get('direction', 0.0)),
                feather_radius=int(p.get('feather_radius', 8)),
                num_strips=max(10, int(p.get('num_strips', 40))),
                wave_type='ripple',
            )
        elif atype==33:   # ── PIXEL FLOW (MOTIONLEAP) ───────────────────────
            key=('pixflow', ri)
            if key not in extra_states:
                extra_states[key] = PixelFlowRenderer(reg.get('static_np', static_np))
            pf_motion = p.get('pf_motion', 'seamless_loop')
            out = extra_states[key].render(
                out, mask,
                paths=reg.get('paths', []),
                t=t,
                amp=amp,
                spd=spd,
                motion_type=pf_motion,
            )
        elif atype==34:   # ── WATERFALL (AGENT FLOW) ───────────────────────
            key=('waterfall', ri)
            if key not in extra_states:
                extra_states[key] = WaterfallState(mask, reg.get('static_np', static_np))
            out = extra_states[key].draw(
                out, t,
                amp=amp,
                spd=spd,
                direction=float(p.get('direction', 90.0)),
                foam=float(p.get('foam', 0.30)),
            )
        elif atype==35:   # ── CINEMATIC ZOOM (AGENT) ───────────────────────
            key=('cinzoom', ri)
            if key not in extra_states:
                extra_states[key] = CinematicZoomState(reg.get('static_np', static_np))
            dur = float(p.get('duration', 8.0))
            out = extra_states[key].draw(out, t, dur, p)
        elif atype==36:   # ── FIREFLY GLOW (JUGNU) ─────────────────────────
            key=('jugnu', ri)
            if key not in extra_states:
                extra_states[key] = FireflyGlowState(mask, reg.get('static_np', static_np))
            out = extra_states[key].draw(
                out, t, dt,
                n_flies    = max(10, int(p.get('jugnu_count',  60))),
                spd        = max(0.1, float(p.get('spd',        1.5))),
                glow_size  = max(0.2, float(p.get('jugnu_size', 1.0))),
                glow_strength = max(0.1, float(p.get('jugnu_bright', 1.0))),
            )
        elif atype==37:   # ── AI ORBIT (MiDaS 2.5D) ────────────────────────
            key=('orbit25d', ri)
            if key not in extra_states:
                # Use the FULL-RES static image for depth estimation
                src_for_depth = reg.get('static_np', static_np)
                # Pass mask only if user actually painted something
                painted_mask = mask if m.any() else None
                extra_states[key] = OrbitParallaxState(src_for_depth, painted_mask)
            out = extra_states[key].draw(
                out, t,
                orbit_radius = max(1.0,  float(p.get('orbit_radius', 30.0))),
                orbit_speed  = max(0.01, float(p.get('orbit_speed',   0.25))),
                orbit_mode   = str(p.get('orbit_mode', 'orbit')),
                depth_boost  = max(0.1,  float(p.get('depth_boost',   1.5))),
                depth_invert = bool(p.get('depth_invert', False)),
            )
    return out


# ─── letterbox helper ──────────────────────────────────────────────────────────
def letterbox_to(frame: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """Fill out_w×out_h completely — scale up so image covers the canvas,
    then centre-crop any overflow.  No black bars."""
    H, W = frame.shape[:2]
    scale = max(out_w / W, out_h / H)          # ← max fills; min would letterbox
    new_w = int(W * scale); new_h = int(H * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    y_off   = (new_h - out_h) // 2             # how much to crop top/bottom
    x_off   = (new_w - out_w) // 2             # how much to crop left/right
    return resized[y_off:y_off+out_h, x_off:x_off+out_w]


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease_in_out(u: float) -> float:
    return u * u * (3.0 - 2.0 * u)


def resolve_camera_director(keyframes, t: float):
    if not keyframes:
        base = CAMERA_PRESETS["Eye Level"].copy()
        base.update({"tx": 0.0, "ty": 0.0, "time_scale": 1.0, "shot": "Static"})
        return base
    kfs = sorted(keyframes, key=lambda k: float(k["time"]))
    if t <= float(kfs[0]["time"]):
        left = kfs[0]; right = kfs[0]
    elif t >= float(kfs[-1]["time"]):
        left = kfs[-1]; right = kfs[-1]
    else:
        left = kfs[0]; right = kfs[-1]
        for i in range(len(kfs) - 1):
            a = kfs[i]; b = kfs[i + 1]
            if float(a["time"]) <= t <= float(b["time"]):
                left = a; right = b; break

    ta = float(left["time"]); tb = float(right["time"])
    u = 0.0 if tb <= ta else (t - ta) / (tb - ta)
    u = max(0.0, min(1.0, u)); ue = _ease_in_out(u)

    p0 = CAMERA_PRESETS.get(left.get("preset", "Eye Level"), CAMERA_PRESETS["Eye Level"]).copy()
    p1 = CAMERA_PRESETS.get(right.get("preset", "Eye Level"), CAMERA_PRESETS["Eye Level"]).copy()
    # Allow keyframes to store custom override values (set by manual sliders)
    for key in ("pitch","yaw","roll","zoom"):
        if key in left:  p0[key] = float(left[key])
        if key in right: p1[key] = float(right[key])
    cam = {
        "pitch": _lerp(float(p0["pitch"]), float(p1["pitch"]), ue),
        "yaw":   _lerp(float(p0["yaw"]),   float(p1["yaw"]),   ue),
        "roll":  _lerp(float(p0["roll"]),  float(p1["roll"]),  ue),
        "zoom":  _lerp(float(p0["zoom"]),  float(p1["zoom"]),  ue),
        "tx": 0.0,
        "ty": 0.0,
        "time_scale": 1.0,
        "shot": left.get("shot", "Static"),
    }

    shot = left.get("shot", "Static")
    if shot == "Wide Zoom Slow Zoom":
        cam["zoom"] *= 0.86 + 0.14 * ue
    elif shot == "Closeup Slow Motion":
        cam["zoom"] *= 1.20 + 0.20 * ue
        cam["time_scale"] = 0.55
    elif shot == "Time Lapse Whip Pan":
        cam["time_scale"] = 2.2
        whip = math.exp(-((ue - 0.5) / 0.16) ** 2)
        cam["yaw"] += (32.0 if float(p1["yaw"]) >= float(p0["yaw"]) else -32.0) * whip
        cam["roll"] += 5.0 * (1.0 - abs(2.0 * ue - 1.0))
    elif shot == "Dolly In Push In":
        cam["zoom"] *= 1.0 + 0.45 * ue
        cam["ty"] += -48.0 * ue
    elif shot == "Dolly Out":
        cam["zoom"] *= 1.25 - 0.33 * ue
        cam["ty"] += 28.0 * ue
    elif shot == "Ken Burns":
        cam["zoom"] = cam["zoom"] * (1.0 + 0.30 * ue)
        cam["tx"] += -40.0 * ue
        cam["ty"] += -25.0 * ue
    elif shot == "Handheld Shake":
        shake_t = t * 6.5
        cam["pitch"] += _noise1d(shake_t + 0.0) * 1.2
        cam["yaw"]   += _noise1d(shake_t + 3.7) * 0.9
        cam["roll"]  += _noise1d(shake_t + 7.1) * 0.4
    elif shot == "Earthquake Shake":
        shake_t = t * 28.0
        intensity = 5.5
        cam["pitch"] += _noise1d(shake_t + 0.0) * intensity
        cam["yaw"]   += _noise1d(shake_t + 5.3) * intensity
        cam["roll"]  += _noise1d(shake_t + 11.9) * intensity * 0.4
        cam["tx"]    += _noise1d(shake_t + 17.2) * intensity * 8.0
        cam["ty"]    += _noise1d(shake_t + 23.6) * intensity * 8.0
    elif shot == "Breathing":
        cam["zoom"] = cam["zoom"] * (1.0 + 0.04 * math.sin(math.tau * t * 0.30))
    elif shot == "Orbit Arc":
        cam["yaw"]  += 30.0 * math.sin(math.tau * t * 0.20)
        cam["zoom"] = cam["zoom"] * (1.0 + 0.08 * abs(math.sin(math.tau * t * 0.20)))
    elif shot == "Vertical Rise":
        cam["ty"]    += -90.0 * ue
        cam["pitch"] += 9.0 * ue
        cam["zoom"]  = cam["zoom"] * (1.0 + 0.15 * ue)
    elif shot == "Pendulum Swing":
        decay = math.exp(-2.0 * t)
        cam["yaw"] += 22.0 * math.sin(math.tau * t * 0.55) * decay
        cam["roll"] += 6.0 * math.sin(math.tau * t * 0.55) * decay
    elif shot == "Dolly Zoom Vertigo":
        zoom_in = 1.0 + 0.55 * ue
        cam["zoom"] = cam["zoom"] * zoom_in
        cam["tx"] += -50.0 * ue
        cam["ty"] += -35.0 * ue
    elif shot == "Whip Pan Fast":
        whip_u = _ease_in_out(min(1.0, ue * 3.5))
        cam["yaw"] += 85.0 * whip_u
        cam["roll"] += 8.0 * (1.0 - abs(2.0 * whip_u - 1.0))
        cam["time_scale"] = 1.8
    elif shot == "Push In Tilt":
        cam["zoom"]  = cam["zoom"] * (1.0 + 0.55 * ue)
        cam["pitch"] += 8.0 * ue
        cam["ty"]    += -35.0 * ue
    elif shot == "360 Spin":
        cam["roll"] += 360.0 * ue
    elif shot == "Slow Reveal Zoom":
        cam["zoom"] = cam["zoom"] * (2.5 - 1.6 * ue)
        cam["ty"] += 40.0 * ue

    # ── Cinematic effects ported from agent.py ────────────────────────────────
    elif shot in ("Agent: Zoom In", "Agent: Zoom Out", "Agent: Ken Burns",
                  "Agent: Drift Right", "Agent: Drift Left",
                  "Agent: Push In Shake", "Agent: Crane Up", "Agent: Crane Down"):
        # Map agent.py effects to camera params for apply_camera_transform.
        # We re-use the easing and zoom math from agent.py directly.
        effect = shot.replace("Agent: ", "")
        easing_key = left.get("agent_easing", "Smooth (Cubic)")
        ease_fn = _CINEMATIC_EASING.get(easing_key, _ease_in_out_cubic)
        z_start = float(left.get("agent_zoom_start", 1.0))
        z_end   = float(left.get("agent_zoom_end",   3.0))

        if effect == "Zoom In":
            et = ease_fn(ue)
            cam["zoom"] *= z_start + (z_end - z_start) * et
            cam["tx"]   += -40.0 * et
            cam["ty"]   += -30.0 * et

        elif effect == "Zoom Out":
            et = ease_fn(1.0 - ue)
            cam["zoom"] *= z_start + (z_end - z_start) * (1.0 - ease_fn(ue))
            cam["tx"]   += 30.0 * ease_fn(ue)
            cam["ty"]   += 20.0 * ease_fn(ue)

        elif effect == "Ken Burns":
            et = ease_fn(ue)
            cam["zoom"] *= z_start + (z_end - z_start) * et
            cam["tx"]   += -50.0 * et
            cam["ty"]   += -35.0 * et

        elif effect == "Drift Right":
            et = ease_fn(ue)
            cam["zoom"] *= 1.0 + (z_end - z_start) * et * 0.25
            cam["tx"]   += 60.0 * et

        elif effect == "Drift Left":
            et = ease_fn(ue)
            cam["zoom"] *= 1.0 + (z_end - z_start) * et * 0.25
            cam["tx"]   += -60.0 * et

        elif effect == "Push In Shake":
            et = ease_fn(ue)
            cam["zoom"] *= z_start + (z_end - z_start) * et
            shake_t = t * 40.0
            cam["tx"]   += -45.0 * et + math.sin(shake_t) * 3.0 * (1.0 - et)
            cam["ty"]   += -32.0 * et + math.cos(shake_t * 0.875) * 2.0 * (1.0 - et)

        elif effect == "Crane Up":
            et = ease_fn(ue)
            cam["zoom"]  *= z_start + (z_end - z_start) * et * 0.5
            cam["ty"]    += -80.0 * et
            cam["pitch"] += 6.0 * et

        elif effect == "Crane Down":
            et = ease_fn(ue)
            cam["zoom"]  *= z_start + (z_end - z_start) * et * 0.5
            cam["ty"]    += 80.0 * et
            cam["pitch"] -= 6.0 * et

    return cam


def resolve_camera_params(keyframes, t: float):
    return resolve_camera_director(keyframes, t)


def _fisheye_maps(w, h, strength=0.35):
    cx, cy = w * 0.5, h * 0.5
    xs = (np.arange(w, dtype=np.float32) - cx) / cx
    ys = (np.arange(h, dtype=np.float32) - cy) / cy
    X, Y = np.meshgrid(xs, ys)
    r = np.sqrt(X*X + Y*Y)
    factor = 1.0 + strength * r * r
    map_x = (X / factor * cx + cx).astype(np.float32)
    map_y = (Y / factor * cy + cy).astype(np.float32)
    return map_x, map_y


def apply_camera_transform(frame: np.ndarray, cam_params: dict) -> np.ndarray:
    h, w = frame.shape[:2]
    pitch = float(cam_params.get("pitch", 0.0))
    yaw   = float(cam_params.get("yaw", 0.0))
    roll  = float(cam_params.get("roll", 0.0))
    zoom  = float(cam_params.get("zoom", 1.0))
    tx    = float(cam_params.get("tx", 0.0))
    ty    = float(cam_params.get("ty", 0.0))

    # ── Perspective (pitch / yaw) ──────────────────────────────────────────────
    src = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    yaw_shift = (yaw / 30.0) * (w * 0.11)
    pitch_shift = (pitch / 30.0) * (h * 0.11)
    dst = np.float32([
        [0 + yaw_shift,     0 + pitch_shift],
        [w - 1 + yaw_shift, 0 - pitch_shift],
        [w - 1 - yaw_shift, h - 1 - pitch_shift],
        [0 - yaw_shift,     h - 1 + pitch_shift],
    ])
    persp = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(frame, persp, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # ── Roll + Zoom + Pan ──────────────────────────────────────────────────────
    cx, cy = (w - 1) * 0.5, (h - 1) * 0.5
    M = cv2.getRotationMatrix2D((cx, cy), roll, zoom)
    M[0, 2] += tx
    M[1, 2] += ty
    out = cv2.warpAffine(out, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # ── Fisheye ───────────────────────────────────────────────────────────────
    fisheye_str = float(cam_params.get("fisheye", 0.0))
    if abs(fisheye_str) > 0.01:
        mx, my = _fisheye_maps(w, h, fisheye_str)
        out = cv2.remap(out, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # ── Lens distortion (barrel / pincushion) ─────────────────────────────────
    lens_dist = float(cam_params.get("lens_distortion", 0.0))
    if abs(lens_dist) > 0.001:
        fx = fy = max(w, h) * 1.0
        K = np.array([[fx, 0, w/2], [0, fy, h/2], [0, 0, 1]], dtype=np.float64)
        dist_coeffs = np.array([lens_dist, lens_dist*0.3, 0, 0, 0], dtype=np.float64)
        out = cv2.undistort(out, K, dist_coeffs)

    # ── Anamorphic squeeze ────────────────────────────────────────────────────
    anamorphic = float(cam_params.get("anamorphic", 0.0))
    if abs(anamorphic) > 0.001:
        squeeze = 1.0 - anamorphic * 0.12
        Msq = np.float32([[squeeze, 0, w*(1-squeeze)*0.5], [0, 1.0, 0]])
        out = cv2.warpAffine(out, Msq, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # ── Vignette ──────────────────────────────────────────────────────────────
    vignette = float(cam_params.get("vignette", 0.0))
    if vignette > 0.001:
        Y_v, X_v = np.mgrid[0:h, 0:w].astype(np.float32)
        r_v = np.hypot((X_v - w/2) / (w/2), (Y_v - h/2) / (h/2))
        vig = np.clip(1.0 - r_v**2 * vignette * 1.2, 0.05, 1.0)
        out = (out.astype(np.float32) * vig[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)

    # ── Chromatic aberration ──────────────────────────────────────────────────
    chroma = float(cam_params.get("chroma", 0.0))
    if abs(chroma) > 0.1:
        shift = int(round(chroma))
        ca = out.copy()
        if shift > 0:
            ca[:, shift:, 0] = out[:, :w-shift, 0]   # R right
            ca[:, :w-shift, 2] = out[:, shift:, 2]    # B left
        else:
            s = abs(shift)
            ca[:, :w-s, 0] = out[:, s:, 0]
            ca[:, s:, 2] = out[:, :w-s, 2]
        out = ca

    # ── Heat shimmer ──────────────────────────────────────────────────────────
    heat = float(cam_params.get("heat_shimmer", 0.0))
    heat_t = float(cam_params.get("_t", 0.0))
    if heat > 0.001:
        xs_1d = np.arange(w, dtype=np.float32)
        ys_1d = np.arange(h, dtype=np.float32)
        lx, ly = np.meshgrid(xs_1d, ys_1d)
        shift_y = heat * 4.0 * np.sin(lx * 0.05 + heat_t * 9.0).astype(np.float32)
        map_x = lx.astype(np.float32)
        map_y = np.clip(ly + shift_y, 0, h - 1).astype(np.float32)
        out = cv2.remap(out, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # ── Film grain ────────────────────────────────────────────────────────────
    grain = float(cam_params.get("grain", 0.0))
    if grain > 0.001:
        noise_g = np.random.normal(0, grain * 28.0, (h, w, 3)).astype(np.float32)
        out = np.clip(out.astype(np.float32) + noise_g, 0, 255).astype(np.uint8)

    # ── Scanlines ────────────────────────────────────────────────────────────
    scanlines = float(cam_params.get("scanlines", 0.0))
    if scanlines > 0.001:
        mask_s = np.ones((h, w), dtype=np.float32)
        mask_s[::2, :] = 1.0 - scanlines * 0.55
        out = (out.astype(np.float32) * mask_s[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)

    # ── Color grade ───────────────────────────────────────────────────────────
    grade = cam_params.get("color_grade", "None")
    if grade != "None":
        f = out.astype(np.float32)
        if grade == "Warm":
            f[:,:,0] = np.clip(f[:,:,0]*1.12 + 18, 0, 255)
            f[:,:,1] = np.clip(f[:,:,1]*1.04 + 5,  0, 255)
            f[:,:,2] = np.clip(f[:,:,2]*0.88 - 10, 0, 255)
        elif grade == "Cool":
            f[:,:,0] = np.clip(f[:,:,0]*0.88 - 10, 0, 255)
            f[:,:,1] = np.clip(f[:,:,1]*1.02 + 5,  0, 255)
            f[:,:,2] = np.clip(f[:,:,2]*1.14 + 18, 0, 255)
        elif grade == "Night":
            f[:,:,0] = np.clip(f[:,:,0]*0.72 - 8,  0, 255)
            f[:,:,1] = np.clip(f[:,:,1]*0.82 + 4,  0, 255)
            f[:,:,2] = np.clip(f[:,:,2]*1.18 + 22, 0, 255)
        elif grade == "Vintage":
            f[:,:,0] = np.clip(f[:,:,0]*1.10 + 15, 0, 255)
            f[:,:,1] = np.clip(f[:,:,1]*0.96 + 8,  0, 255)
            f[:,:,2] = np.clip(f[:,:,2]*0.80 - 5,  0, 255)
            noise_v = np.random.normal(0, 8, (h, w, 3)).astype(np.float32)
            f = np.clip(f + noise_v, 0, 255)
        elif grade == "Horror":
            gray = np.mean(f, axis=2, keepdims=True)
            f = f * 0.35 + gray * 0.65
            f[:,:,0] = np.clip(f[:,:,0]*1.25 + 10, 0, 255)
            f[:,:,1] = np.clip(f[:,:,1]*0.70,       0, 255)
            f[:,:,2] = np.clip(f[:,:,2]*0.70,       0, 255)
        elif grade == "Dreamy":
            blur_d = cv2.GaussianBlur(out, (0, 0), 3.5)
            f = np.clip(f * 0.65 + blur_d.astype(np.float32) * 0.55, 0, 255)
            f[:,:,2] = np.clip(f[:,:,2]*1.12 + 12, 0, 255)
        elif grade == "B&W":
            gray = (f[:,:,0]*0.299 + f[:,:,1]*0.587 + f[:,:,2]*0.114)
            f[:,:,0] = f[:,:,1] = f[:,:,2] = gray
        out = f.clip(0, 255).astype(np.uint8)

    # ── Mirror / Kaleidoscope ─────────────────────────────────────────────────
    mirror = cam_params.get("mirror", "None")
    if mirror == "Horizontal":
        half = out[:, :w//2]
        out = np.concatenate([half, np.fliplr(half)], axis=1)
    elif mirror == "Vertical":
        half = out[:h//2, :]
        out = np.concatenate([half, np.flipud(half)], axis=0)
    elif mirror == "Kaleidoscope":
        half_h = out[:h//2, :w//2]
        top = np.concatenate([half_h, np.fliplr(half_h)], axis=1)
        out = np.concatenate([top, np.flipud(top)], axis=0)

    # ── Focus pull (blur outside centre) ─────────────────────────────────────
    focus_blur = float(cam_params.get("focus_blur", 0.0))
    if focus_blur > 0.01:
        sigma = focus_blur * 6.0
        blurred = cv2.GaussianBlur(out, (0, 0), sigma)
        Y_f, X_f = np.mgrid[0:h, 0:w].astype(np.float32)
        r_f = np.hypot((X_f - w/2) / (w/2), (Y_f - h/2) / (h/2))
        alpha_f = np.clip((r_f - 0.3) / 0.7, 0.0, 1.0)[:, :, np.newaxis]
        out = (out.astype(np.float32) * (1 - alpha_f) + blurred.astype(np.float32) * alpha_f).clip(0, 255).astype(np.uint8)

    return out


# ─── App ──────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wave Animator Pro v8  —  3D Camera + Export: 1080×1920")
        self.configure(bg="#0d0d12"); self.geometry("1280x900"); self.resizable(True,True)
        self.static_np=None;self.disp_np=None;self.disp_scale=1.0
        self.zoom_level=1.0;self.zoom_min=0.25;self.zoom_max=8.0
        self.pan_x=0;self.pan_y=0;self._pan_start=None
        self.regions=[];self.active_reg=None
        self.paint_mode='paint';self.painting=False;self.brush_var=None
        self.edit_tool='paint';self._path_start=None;self._path_preview_x=0;self._path_preview_y=0
        self.prevOn=False;self.prev_t=0.0;self.prev_last=None
        self._after_id=None;self._tk_img=None;self._extra={}
        self._live_apply_blocked=False
        self._bg_source=None;self._fg_source=None
        self._cloud_color_var=tk.StringVar(value="White")
        self._sun_color_var=tk.StringVar(value="Solar Yellow")
        self._smoke_enabled=tk.BooleanVar(value=False)
        self._smoke_color_var=tk.StringVar(value="White")
        self.camera_keyframes=[{"time":0.0,"preset":"Eye Level","shot":"Static"}]
        self._timeline_internal=False
        self.timeline_time_var=tk.DoubleVar(value=0.0)
        self._track_drag_index=None
        self.prev_anim_t=0.0
        # ── Cinematic Zoom start/end point state (agent.py style) ─────────────
        self._cz_start_norm=(0.5,0.5)   # (x,y) normalised 0-1
        self._cz_end_norm  =(0.5,0.45)
        self._cz_click_mode="end"        # "start" or "end"
        # ── 3D Depth Fly-Through state ────────────────────────────────────────
        self._depth3d_enabled=tk.BooleanVar(value=False)
        self._depth3d_layers=[]          # list of {region_idx, depth, blur, opacity}
        self._depth3d_pvars={}           # cam_mode, cam_speed, dof_strength, etc.
        self._depth3d_cam_mode=tk.StringVar(value="Fly Through")
        self._build_ui()

    def _build_ui(self):
        bs=dict(bg="#1e1e2e",fg="#cdd6f4",activebackground="#313244",activeforeground="#cdd6f4",
                relief=tk.FLAT,font=("Courier New",9,"bold"),padx=8,pady=4,cursor="hand2")
        top=tk.Frame(self,bg="#0d0d12",pady=4);top.pack(fill=tk.X,padx=8)
        tk.Button(top,text="Open Image",   command=self.open_image,  **bs).pack(side=tk.LEFT,padx=2)
        tk.Button(top,text="Add Region",   command=self.add_region,  **bs).pack(side=tk.LEFT,padx=2)
        tk.Button(top,text="Clear Paint",  command=self.clear_paint, **bs).pack(side=tk.LEFT,padx=2)
        tk.Button(top,text="Clear Motion", command=self.clear_motion, **bs).pack(side=tk.LEFT,padx=2)
        tk.Button(top,text="Delete Region",command=self.delete_region,
                  bg="#3a1e1e",fg="#f38ba8",activebackground="#4a2e2e",
                  relief=tk.FLAT,font=("Courier New",9,"bold"),padx=8,pady=4,cursor="hand2").pack(side=tk.LEFT,padx=2)
        self.btn_prev=tk.Button(top,text="▶ Preview",command=self.toggle_preview,**bs);self.btn_prev.pack(side=tk.LEFT,padx=2)
        tk.Button(top,text="Export MP4  1080×1920",command=self.export_video,
                  bg="#1e3a4a",fg="#89b4fa",activebackground="#1a3040",
                  relief=tk.FLAT,font=("Courier New",9,"bold"),padx=8,pady=4,cursor="hand2").pack(side=tk.LEFT,padx=2)
        tk.Frame(top,bg="#313244",width=1,padx=1).pack(side=tk.LEFT,padx=6,fill=tk.Y)
        tk.Label(top,text="ZOOM:",bg="#0d0d12",fg="#585b70",font=("Courier New",8)).pack(side=tk.LEFT,padx=(4,2))
        ab2=dict(bg="#1e1e2e",fg="#cdd6f4",activebackground="#313244",relief=tk.FLAT,font=("Courier New",10,"bold"),padx=8,pady=4,cursor="hand2",width=2)
        tk.Button(top,text="−",command=self.zoom_out,**ab2).pack(side=tk.LEFT,padx=1)
        self.zoom_lbl=tk.Label(top,text="100%",bg="#0d0d12",fg="#a6adc8",font=("Courier New",8),width=6);self.zoom_lbl.pack(side=tk.LEFT)
        tk.Button(top,text="+",command=self.zoom_in, **ab2).pack(side=tk.LEFT,padx=1)
        tk.Button(top,text="Reset",command=self.zoom_reset,bg="#1e1e2e",fg="#585b70",activebackground="#313244",relief=tk.FLAT,font=("Courier New",8),padx=6,pady=4,cursor="hand2").pack(side=tk.LEFT,padx=2)
        tk.Frame(top,bg="#313244",width=1,padx=1).pack(side=tk.LEFT,padx=6,fill=tk.Y)
        tk.Label(top,text="PAN:",bg="#0d0d12",fg="#585b70",font=("Courier New",8)).pack(side=tk.LEFT,padx=(4,2))
        pan_step=30;ab3=dict(bg="#1e1e2e",fg="#cdd6f4",activebackground="#313244",relief=tk.FLAT,font=("Courier New",9,"bold"),padx=6,pady=4,cursor="hand2")
        for text,dx,dy in[("←",pan_step,0),("↑",0,pan_step),("↓",0,-pan_step),("→",-pan_step,0)]:
            tk.Button(top,text=text,command=lambda d=dx,e=dy:self._pan_by(d,e),**ab3).pack(side=tk.LEFT,padx=1)
        tk.Button(top,text="⌂",command=self.zoom_reset,bg="#1e1e2e",fg="#585b70",activebackground="#313244",relief=tk.FLAT,font=("Courier New",9),padx=6,pady=4,cursor="hand2").pack(side=tk.LEFT,padx=2)

        main=tk.Frame(self,bg="#0d0d12");main.pack(fill=tk.BOTH,expand=True,padx=8,pady=4)
        self.canvas=tk.Canvas(main,bg="#111118",highlightthickness=0,cursor="crosshair");self.canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        self.canvas.bind("<ButtonPress-1>",   self._press)
        self.canvas.bind("<B1-Motion>",       self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Configure>",       lambda e:self._refit())
        self.canvas.bind("<MouseWheel>",      self._on_mousewheel)
        self.canvas.bind("<Button-4>",        lambda e:self.zoom_in())
        self.canvas.bind("<Button-5>",        lambda e:self.zoom_out())
        self.canvas.bind("<ButtonPress-2>",   self._pan_start_cb)
        self.canvas.bind("<B2-Motion>",       self._pan_move_cb)
        self.canvas.bind("<ButtonRelease-2>", self._pan_end_cb)
        self.canvas.bind("<ButtonPress-3>",   self._pan_start_cb)
        self.canvas.bind("<B3-Motion>",       self._pan_move_cb)
        self.canvas.bind("<ButtonRelease-3>", self._pan_end_cb)
        self._hint=self.canvas.create_text(400,300,text="Open an image to begin",fill="#444455",font=("Courier New",13))

        panel_outer=tk.Frame(main,bg="#1a1a2e",width=320);panel_outer.pack(side=tk.RIGHT,fill=tk.Y,padx=(6,0));panel_outer.pack_propagate(False)
        _pscroll=tk.Scrollbar(panel_outer,orient=tk.VERTICAL,bg="#1a1a2e",troughcolor="#111118",relief=tk.FLAT,bd=0,width=8);_pscroll.pack(side=tk.RIGHT,fill=tk.Y)
        _pcanvas=tk.Canvas(panel_outer,bg="#1a1a2e",highlightthickness=0,yscrollcommand=_pscroll.set);_pcanvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True);_pscroll.config(command=_pcanvas.yview)
        panel=tk.Frame(_pcanvas,bg="#1a1a2e",padx=10,pady=8);_panel_win=_pcanvas.create_window((0,0),window=panel,anchor=tk.NW)
        def _on_panel_configure(e):_pcanvas.configure(scrollregion=_pcanvas.bbox("all"))
        def _on_pcanvas_resize(e):_pcanvas.itemconfig(_panel_win,width=e.width)
        panel.bind("<Configure>",_on_panel_configure);_pcanvas.bind("<Configure>",_on_pcanvas_resize)
        def _on_panel_mousewheel(e):_pcanvas.yview_scroll(int(-1*(e.delta/120)),"units")
        def _on_panel_mousewheel_linux_up(e):_pcanvas.yview_scroll(-1,"units")
        def _on_panel_mousewheel_linux_dn(e):_pcanvas.yview_scroll(1,"units")
        for w in(panel_outer,_pcanvas,panel):
            w.bind("<MouseWheel>",_on_panel_mousewheel);w.bind("<Button-4>",_on_panel_mousewheel_linux_up);w.bind("<Button-5>",_on_panel_mousewheel_linux_dn)
        def _bind_scroll_recursive(widget):
            widget.bind("<MouseWheel>",_on_panel_mousewheel,add="+");widget.bind("<Button-4>",_on_panel_mousewheel_linux_up,add="+");widget.bind("<Button-5>",_on_panel_mousewheel_linux_dn,add="+")
            for child in widget.winfo_children():_bind_scroll_recursive(child)
        panel.bind("<Map>",lambda e:_bind_scroll_recursive(panel))

        self._build_smoke_panel(panel)
        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=6)
        self._build_layer_panel(panel)
        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=6)
        self._build_depth3d_panel(panel)
        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=6)

        tk.Label(panel,text="REGIONS",bg="#1a1a2e",fg="#89b4fa",font=("Courier New",9,"bold")).pack(anchor=tk.W)
        lf=tk.Frame(panel,bg="#111118",relief=tk.FLAT,bd=1);lf.pack(fill=tk.X,pady=3)
        self.reg_listbox=tk.Listbox(lf,bg="#111118",fg="#cdd6f4",selectbackground="#313244",font=("Courier New",9),height=5,relief=tk.FLAT,highlightthickness=0);self.reg_listbox.pack(fill=tk.X)
        self.reg_listbox.bind("<<ListboxSelect>>",self._list_sel)
        tk.Label(panel,text="ANIMATION FOR SELECTED REGION",bg="#1a1a2e",fg="#89b4fa",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(8,2))
        self.anim_var=tk.IntVar(value=0)
        for i,name in enumerate(ANIM_TYPES):
            tk.Radiobutton(panel,text=name,variable=self.anim_var,value=i,bg="#1a1a2e",fg="#cdd6f4",selectcolor="#313244",activebackground="#1a1a2e",font=("Courier New",8),command=self._anim_changed).pack(anchor=tk.W)
        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=6)
        tk.Label(panel,text="PAINT TOOL",bg="#1a1a2e",fg="#89b4fa",font=("Courier New",9,"bold")).pack(anchor=tk.W)
        pr=tk.Frame(panel,bg="#1a1a2e");pr.pack(fill=tk.X,pady=3)
        self.paint_btn=tk.Button(pr,text="Paint",command=lambda:self._set_paint('paint'),bg="#2e4a2e",fg="#a6e3a1",relief=tk.FLAT,font=("Courier New",9),padx=8,pady=3,cursor="hand2");self.paint_btn.pack(side=tk.LEFT,padx=2)
        self.erase_btn=tk.Button(pr,text="Erase",command=lambda:self._set_paint('erase'),bg="#1e1e2e",fg="#cdd6f4",relief=tk.FLAT,font=("Courier New",9),padx=8,pady=3,cursor="hand2");self.erase_btn.pack(side=tk.LEFT,padx=2)
        self.path_btn=tk.Button(pr,text="Path",command=lambda:self._set_paint('path'),bg="#1e1e2e",fg="#cdd6f4",relief=tk.FLAT,font=("Courier New",9),padx=8,pady=3,cursor="hand2");self.path_btn.pack(side=tk.LEFT,padx=2)
        self.freeze_btn=tk.Button(pr,text="Freeze",command=lambda:self._set_paint('freeze'),bg="#1e1e2e",fg="#cdd6f4",relief=tk.FLAT,font=("Courier New",9),padx=8,pady=3,cursor="hand2");self.freeze_btn.pack(side=tk.LEFT,padx=2)
        self.anchor_btn=tk.Button(pr,text="Anchor",command=lambda:self._set_paint('anchor'),bg="#1e1e2e",fg="#cdd6f4",relief=tk.FLAT,font=("Courier New",9),padx=8,pady=3,cursor="hand2");self.anchor_btn.pack(side=tk.LEFT,padx=2)
        br=tk.Frame(panel,bg="#1a1a2e");br.pack(fill=tk.X,pady=2)
        tk.Label(br,text="Brush",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=6,anchor=tk.W).pack(side=tk.LEFT)
        self.brush_var=tk.IntVar(value=22)
        tk.Scale(br,from_=4,to=120,variable=self.brush_var,orient=tk.HORIZONTAL,bg="#1a1a2e",fg="#cdd6f4",highlightthickness=0,troughcolor="#313244",sliderrelief=tk.FLAT).pack(side=tk.LEFT,fill=tk.X,expand=True)
        tk.Label(panel,text="Motionleap-style workflow:\n1. Paint moving region\n2. Add Path arrows\n3. Add Anchor points\n4. Brush Freeze areas",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=6)
        tk.Label(panel,text="WAVE SETTINGS",bg="#1a1a2e",fg="#89b4fa",font=("Courier New",9,"bold")).pack(anchor=tk.W)
        self.pvars={}
        self._generic_frame=tk.Frame(panel,bg="#1a1a2e");self._generic_frame.pack(fill=tk.X)

        def _slider_row(parent,key,label,mn,mx,default,fmt=".1f"):
            row=tk.Frame(parent,bg="#1a1a2e");row.pack(fill=tk.X,pady=2)
            tk.Label(row,text=label,bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
            var=tk.DoubleVar(value=default);self.pvars[key]=var
            vlbl=tk.Label(row,text=f"{default:{fmt}}",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8),width=5);vlbl.pack(side=tk.RIGHT)
            ttk.Scale(row,from_=mn,to=mx,variable=var,orient=tk.HORIZONTAL,command=lambda v,l=vlbl,f=fmt:l.config(text=f"{float(v):{f}}")
                      ).pack(side=tk.LEFT,fill=tk.X,expand=True)
            return var,vlbl

        for key,label,mn,mx,default in[("amp","Intensity",1,60,14),("freq","Frequency",0.5,10,2.0),("spd","Speed",0.2,6,1.5),("turb","Turbulence",0.0,1,0.4),("dispersion","Dispersion",0.0,1.5,0.25),("fall_delay","Fall Stagger",0.0,20,5.0),("start_t","Start(s)",0.0,120.0,0.0),("end_t","End(s)",0.0,120.0,120.0)]:
            _slider_row(self._generic_frame,key,label,mn,mx,default)

        # Cloth panel
        self._cloth_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._cloth_frame,text="— CLOTH WAVE —",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        pre_row=tk.Frame(self._cloth_frame,bg="#1a1a2e");pre_row.pack(fill=tk.X,pady=2)
        tk.Label(pre_row,text="Preset",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=8,anchor=tk.W).pack(side=tk.LEFT)
        self._cloth_preset=tk.StringVar(value="Custom")
        preset_cb=ttk.Combobox(pre_row,textvariable=self._cloth_preset,width=14,state="readonly",values=["Silk","Heavy Fabric","Sheer Curtain","Satin","Denim","Custom"]);preset_cb.pack(side=tk.LEFT,padx=4);preset_cb.bind("<<ComboboxSelected>>",self._apply_cloth_preset)
        self._cloth_vlbls={}
        for key,label,mn,mx,default in[("c_amp","Primary",1,50,14),("c_freq","Freq",0.3,8,1.8),("c_spd","Speed",0.1,5,1.2),("c_amp2","2nd Wave",0,30,5),("c_freq2","2nd Freq",0.3,16,3.8),("c_drape","Drape",0,1,0.55),("c_shear","Shear",0,1,0.25),("c_turb","Turbulence",0,1,0.2),("c_phase2","2nd Phase",0,6.28,1.47)]:
            var,vlbl=_slider_row(self._cloth_frame,key,label,mn,mx,default,".2f");self._cloth_vlbls[key]=vlbl

        # Fog panel
        self._fog_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._fog_frame,text="— FOG / MIST —",bg="#1a1a2e",fg="#94e2d5",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        for key,label,mn,mx,default in[("direction","Direction°",0,360,0.0),("density","Density",0.1,3.0,0.8)]:_slider_row(self._fog_frame,key,label,mn,mx,default)

        # Scroll panel
        self._scroll_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._scroll_frame,text="— SCROLL / RIVER —",bg="#1a1a2e",fg="#f9e2af",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._scroll_frame,text="0°=right  90°=down  180°=left  270°=up",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        for key,label,mn,mx,default in[("direction","Direction°",0,360,90.0),("stretch","Stretch",0.0,3.0,0.5)]:_slider_row(self._scroll_frame,key,label,mn,mx,default)

        # Water Flow panel
        self._waterflow_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._waterflow_frame,text="— WATER FLOW —",bg="#1a1a2e",fg="#89dceb",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._waterflow_frame,text="Liquid-style directional motion.\nDispersion adds breakup and swirl.\nFoam adds bright crest highlights.",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        for key,label,mn,mx,default,fmt in[("direction","Direction°",0,360,90.0,".0f"),("foam","Foam",0.0,1.5,0.55,".2f")]:
            _slider_row(self._waterflow_frame,key,label,mn,mx,default,fmt)

        self._motionpath_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._motionpath_frame,text="— MOTION PATHS (Motionleap-style) —",bg="#1a1a2e",fg="#89b4fa",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._motionpath_frame,
                 text="1. Paint the moving area (petals, hair, cloth…)\n"
                      "2. Draw Path arrows — sets flow direction\n"
                      "3. Place Anchor points — pins still areas (roots)\n"
                      "4. Use Freeze brush — locks rigid sub-areas\n\n"
                      "Intensity  = flow travel distance\n"
                      "Frequency  = flow cycle speed\n"
                      "Speed      = overall time scale\n"
                      "Dispersion = organic turbulence\n"
                      "Path Radius= how wide each arrow influences",
                 bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        for key,label,mn,mx,default,fmt in[("path_radius","Path Radius",20,220,80.0,".0f"),("anchor_strength","Anchor Str",0.1,2.0,1.0,".2f")]:
            _slider_row(self._motionpath_frame,key,label,mn,mx,default,fmt)

        # Clouds panel
        self._cloud_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._cloud_frame,text="— CLOUDS MOVING —",bg="#1a1a2e",fg="#89dceb",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._cloud_frame,text="0°=right  90°=down  180°=left  270°=up",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        _slider_row(self._cloud_frame,"cloud_dir","Direction°",0,360,90.0);_slider_row(self._cloud_frame,"cloud_alpha","Opacity",0.0,1.0,0.85,".2f");_slider_row(self._cloud_frame,"cloud_count","Count",1,30,10,".0f")
        col_row=tk.Frame(self._cloud_frame,bg="#1a1a2e");col_row.pack(fill=tk.X,pady=3)
        tk.Label(col_row,text="Color",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._cloud_color_cb=ttk.Combobox(col_row,textvariable=self._cloud_color_var,values=CloudMovingState.COLOR_NAMES,state="readonly",width=14);self._cloud_color_cb.pack(side=tk.LEFT,padx=4);self._cloud_color_cb.bind("<<ComboboxSelected>>",lambda e:self.after_idle(self._cloud_color_changed))

        # Rain panel
        self._rain_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._rain_frame,text="— RAIN —",bg="#1a1a2e",fg="#89b4fa",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._rain_frame,text="Angle: 90°=straight down\n<90=left lean  >90=right lean",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        for key,label,mn,mx,default in[("rain_angle","Angle°",60,120,90.0),("rain_density","Density",0.1,1.0,0.8)]:_slider_row(self._rain_frame,key,label,mn,mx,default,".2f")

        # Sun panel
        self._sun_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._sun_frame,text="— SUN / ENERGY ORB —",bg="#1a1a2e",fg="#f9e2af",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._sun_frame,text="Position: % within painted region",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        for key,label,mn,mx,default,fmt in[("sun_x","X Pos %",0,100,50.0,".0f"),("sun_y","Y Pos %",0,100,50.0,".0f"),("sun_size","Size",4,60,18.0,".0f"),("sun_glow","Glow",0.0,2.0,0.7,".2f"),("sun_rays","Ray Count",4,24,12.0,".0f"),("orbit_radius","Orbit R",0,100,0.0,".0f"),("orbit_speed","Orbit Speed",0.0,1.0,0.1,".2f")]:
            _slider_row(self._sun_frame,key,label,mn,mx,default,fmt)
        sc_row=tk.Frame(self._sun_frame,bg="#1a1a2e");sc_row.pack(fill=tk.X,pady=3)
        tk.Label(sc_row,text="Color",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._sun_color_cb=ttk.Combobox(sc_row,textvariable=self._sun_color_var,values=["Solar Yellow","Cool White","Plasma Blue","Inferno Red","Emerald"],state="readonly",width=14);self._sun_color_cb.pack(side=tk.LEFT,padx=4);self._sun_color_cb.bind("<<ComboboxSelected>>",lambda e:self.after_idle(self._sun_color_changed))

        # Floating Object panel
        self._float_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._float_frame,text="— FLOATING OBJECT —",bg="#1a1a2e",fg="#94e2d5",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._float_frame,text="Paint the object to float.\nIntensity = bob height (px)\nFrequency = bob rate\nSpeed = time scale",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)

        # Up / Down Breath panel
        self._updown_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._updown_frame,text="— UP / DOWN BREATH —",bg="#1a1a2e",fg="#f9e2af",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._updown_frame,text="Painted region shifts up & down.\nIntensity = pixel shift amount\nFrequency = breath rate  Speed = time scale",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)

        # ── SPIN FLOAT panel (new) ────────────────────────────────────────────
        self._spinf_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._spinf_frame,text="— SPIN FLOAT —",bg="#1a1a2e",fg="#f5c2e7",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._spinf_frame,
                 text="Region spins around its own centre\nwhile floating up & down.\n"
                      "Intensity = bob height (px)\n"
                      "Frequency = bob rate\n"
                      "Speed     = overall time scale\n"
                      "Spin Spd  = rotation speed (× base 60°/s)\n"
                      "Lateral   = side-drift fraction",
                 bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        _slider_row(self._spinf_frame,"spin_speed","Spin Spd",0.05,5.0,1.0,".2f")
        _slider_row(self._spinf_frame,"bob_lateral","Lateral",0.0,1.0,0.25,".2f")

        # Motion Leap panels
        self._leap_hop_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._leap_hop_frame,text="— MOTION LEAP: HOP —",bg="#1a1a2e",fg="#f5c2e7",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._leap_hop_frame,text="A springy vertical hop.\nIntensity = jump height\nFrequency = jump rate\nDispersion = airy break-up / ghosting",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)

        self._leap_side_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._leap_side_frame,text="— MOTION LEAP: SIDE —",bg="#1a1a2e",fg="#fab387",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._leap_side_frame,text="An arcing side leap with tilt.\nIntensity = arc size\nFrequency = repeat rate\nDispersion = wider travel / smear",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)

        self._leap_pulse_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._leap_pulse_frame,text="— MOTION LEAP: PULSE —",bg="#1a1a2e",fg="#a6e3a1",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._leap_pulse_frame,text="A compact pulse-jump with squash/stretch.\nIntensity = pulse height\nFrequency = pulse rate\nDispersion = echo trail strength",bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)

        # Living Painting panel
        self._livepaint_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._livepaint_frame,text="— LIVING PAINTING —",bg="#1a1a2e",fg="#f9e2af",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._livepaint_frame,
                 text="Volcano-style particle eruption from\n"
                      "the painted region, rendered as a\n"
                      "transparent layer over the image.\n"
                      "Intensity  = particle heat/glow\n"
                      "Speed      = eruption time scale\n"
                      "Loop(s)    = cycle duration",
                 bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        _slider_row(self._livepaint_frame,"lp_loop","Loop(s)",2.0,30.0,10.0,".1f")

        # Pixel Flow (MotionLeap) panel — index 33
        self._pixflow_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._pixflow_frame,text="— PIXEL FLOW (MOTIONLEAP) —",bg="#1a1a2e",fg="#94e2d5",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._pixflow_frame,
                 text="Bilinear pixel-warp driven by Path arrows.\n"
                      "Draw arrows with the Path tool to set\n"
                      "the direction pixels flow inside the\n"
                      "painted region.\n\n"
                      "Intensity  = warp displacement\n"
                      "Speed      = flow time scale\n"
                      "Motion     = loop style",
                 bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        # Motion type dropdown for pf_motion
        pf_mot_row=tk.Frame(self._pixflow_frame,bg="#1a1a2e");pf_mot_row.pack(fill=tk.X,pady=(4,2))
        tk.Label(pf_mot_row,text="Motion",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._pf_motion_var=tk.StringVar(value="seamless_loop")
        ttk.Combobox(pf_mot_row,textvariable=self._pf_motion_var,
                     values=["seamless_loop","loop","bounce"],
                     state="readonly",width=14).pack(side=tk.LEFT,padx=4)
        # Store as a regular pvar so _build_params picks it up
        self.pvars['pf_motion']=self._pf_motion_var
        self._pf_motion_var.trace_add('write',lambda *_:self.after_idle(self._live_apply))

        # Waterfall (Agent Flow) panel — index 34
        self._waterfall_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._waterfall_frame,text="— WATERFALL (AGENT FLOW) —",bg="#1a1a2e",fg="#89dceb",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._waterfall_frame,
                 text="Two-layer seamless pixel-flow from agent.py.\n"
                      "Layers cross-fade with sin²  — no seams.\n\n"
                      "0°=right  90°=down  180°=left  270°=up\n\n"
                      "Intensity  = travel distance scale\n"
                      "Speed      = flow speed\n"
                      "Direction  = flow angle\n"
                      "Foam       = crest highlight brightness",
                 bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        for _wf_key,_wf_lbl,_wf_mn,_wf_mx,_wf_def,_wf_fmt in [
            ("direction","Direction°",0,360,90.0,".0f"),
            ("foam",     "Foam",      0.0,1.0,0.30,".2f"),
        ]:
            _slider_row(self._waterfall_frame,_wf_key,_wf_lbl,_wf_mn,_wf_mx,_wf_def,_wf_fmt)
        # ── Cinematic Zoom (Agent) panel — index 35 ──────────────────────────
        self._cinzoom_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._cinzoom_frame,text="— CINEMATIC ZOOM (AGENT) —",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._cinzoom_frame,
                 text="Full-frame cinematic crop+zoom from agent.py.\n"
                      "Click START/END buttons then click the image\n"
                      "to set camera travel points.\n\n"
                      "◎ START = where the camera begins\n"
                      "◉ END   = where the camera lands\n\n"
                      "Intensity, Freq, Speed sliders are unused\n"
                      "for this animation — use the controls below.",
                 bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        # Effect dropdown
        _cz_effect_row=tk.Frame(self._cinzoom_frame,bg="#1a1a2e");_cz_effect_row.pack(fill=tk.X,pady=(6,2))
        tk.Label(_cz_effect_row,text="Effect",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._cz_effect_var=tk.StringVar(value="Zoom In")
        _cz_effects=["Zoom In","Zoom Out","Ken Burns","Drift Right","Drift Left","Push In Shake","Crane Up","Crane Down"]
        _cz_effect_cb=ttk.Combobox(_cz_effect_row,textvariable=self._cz_effect_var,values=_cz_effects,state="readonly",width=14)
        _cz_effect_cb.pack(side=tk.LEFT,padx=4)
        def _cz_effect_changed(e=None):
            _presets={"Zoom In":(1.0,3.5,"Smooth (Cubic)"),"Zoom Out":(3.5,1.0,"Ease Out"),"Ken Burns":(1.2,2.8,"Smooth (Cubic)"),"Drift Right":(1.5,1.5,"Sinusoidal"),"Drift Left":(1.5,1.5,"Sinusoidal"),"Push In Shake":(1.0,4.0,"Accelerate (Expo)"),"Crane Up":(1.2,1.6,"Smooth (Cubic)"),"Crane Down":(1.2,1.6,"Smooth (Cubic)")}
            if self._cz_effect_var.get() in _presets:
                zs,ze,ease=_presets[self._cz_effect_var.get()]
                self._cz_zoom_start_var.set(zs);self._cz_zoom_start_lbl.config(text=f"{zs:.1f}×")
                self._cz_zoom_end_var.set(ze);  self._cz_zoom_end_lbl.config(text=f"{ze:.1f}×")
                self._cz_easing_var.set(ease)
            self.after_idle(self._live_apply)
        _cz_effect_cb.bind("<<ComboboxSelected>>",_cz_effect_changed)
        self._cz_effect_var.trace_add('write',lambda *_:self.after_idle(self._live_apply))
        # Easing dropdown
        _cz_ease_row=tk.Frame(self._cinzoom_frame,bg="#1a1a2e");_cz_ease_row.pack(fill=tk.X,pady=2)
        tk.Label(_cz_ease_row,text="Easing",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._cz_easing_var=tk.StringVar(value="Smooth (Cubic)")
        _cz_easing_cb=ttk.Combobox(_cz_ease_row,textvariable=self._cz_easing_var,values=list(_CINEMATIC_EASING.keys()),state="readonly",width=14)
        _cz_easing_cb.pack(side=tk.LEFT,padx=4)
        self._cz_easing_var.trace_add('write',lambda *_:self.after_idle(self._live_apply))
        # Zoom Start slider
        _cz_zs_row=tk.Frame(self._cinzoom_frame,bg="#1a1a2e");_cz_zs_row.pack(fill=tk.X,pady=(6,0))
        tk.Label(_cz_zs_row,text="Zoom Start",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._cz_zoom_start_var=tk.DoubleVar(value=1.0)
        self._cz_zoom_start_lbl=tk.Label(_cz_zs_row,text="1.0×",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8),width=5);self._cz_zoom_start_lbl.pack(side=tk.RIGHT)
        ttk.Scale(self._cinzoom_frame,from_=1.0,to=4.0,variable=self._cz_zoom_start_var,orient=tk.HORIZONTAL,
                  command=lambda v:self._cz_zoom_start_lbl.config(text=f"{float(v):.1f}×")).pack(fill=tk.X,pady=(0,4))
        self._cz_zoom_start_var.trace_add('write',lambda *_:self.after_idle(self._live_apply))
        # Zoom End slider
        _cz_ze_row=tk.Frame(self._cinzoom_frame,bg="#1a1a2e");_cz_ze_row.pack(fill=tk.X,pady=(0,0))
        tk.Label(_cz_ze_row,text="Zoom End",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._cz_zoom_end_var=tk.DoubleVar(value=3.0)
        self._cz_zoom_end_lbl=tk.Label(_cz_ze_row,text="3.0×",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8),width=5);self._cz_zoom_end_lbl.pack(side=tk.RIGHT)
        ttk.Scale(self._cinzoom_frame,from_=1.0,to=8.0,variable=self._cz_zoom_end_var,orient=tk.HORIZONTAL,
                  command=lambda v:self._cz_zoom_end_lbl.config(text=f"{float(v):.1f}×")).pack(fill=tk.X,pady=(0,4))
        self._cz_zoom_end_var.trace_add('write',lambda *_:self.after_idle(self._live_apply))
        # Cinematic look sliders
        for _cz_key,_cz_lbl2,_cz_mn,_cz_mx,_cz_def,_cz_fmt in[
            ("vignette","Vignette",0.0,1.0,0.35,".2f"),
            ("brightness","Brightness",0.3,2.0,1.0,".2f"),
            ("contrast","Contrast",0.5,2.0,1.1,".2f"),
            ("fade_duration","Fade Dur(s)",0.2,5.0,1.5,".1f"),
        ]:
            _slider_row(self._cinzoom_frame,_cz_key,_cz_lbl2,_cz_mn,_cz_mx,_cz_def,_cz_fmt)
        # Fade checkboxes
        _cz_fade_row=tk.Frame(self._cinzoom_frame,bg="#1a1a2e");_cz_fade_row.pack(fill=tk.X,pady=(4,2))
        self._cz_fade_black_var=tk.BooleanVar(value=True)
        self._cz_fade_white_var=tk.BooleanVar(value=False)
        def _cz_toggle_black():
            if self._cz_fade_black_var.get():self._cz_fade_white_var.set(False)
            self.after_idle(self._live_apply)
        def _cz_toggle_white():
            if self._cz_fade_white_var.get():self._cz_fade_black_var.set(False)
            self.after_idle(self._live_apply)
        tk.Checkbutton(_cz_fade_row,text="Fade→Black",variable=self._cz_fade_black_var,command=_cz_toggle_black,bg="#1a1a2e",fg="#cdd6f4",selectcolor="#313244",activebackground="#1a1a2e",font=("Courier New",8),cursor="hand2").pack(side=tk.LEFT,padx=(0,8))
        tk.Checkbutton(_cz_fade_row,text="Fade→White",variable=self._cz_fade_white_var,command=_cz_toggle_white,bg="#1a1a2e",fg="#cdd6f4",selectcolor="#313244",activebackground="#1a1a2e",font=("Courier New",8),cursor="hand2").pack(side=tk.LEFT)
        # Start / End point click-mode buttons (agent.py style)
        tk.Frame(self._cinzoom_frame,bg="#313244",height=1).pack(fill=tk.X,pady=(6,4))
        tk.Label(self._cinzoom_frame,text="CAMERA TRAVEL POINTS",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8,"bold")).pack(anchor=tk.W)
        tk.Label(self._cinzoom_frame,text="Click a button, then click the image",bg="#1a1a2e",fg="#585b70",font=("Courier New",7)).pack(anchor=tk.W)
        _cz_pt_row=tk.Frame(self._cinzoom_frame,bg="#1a1a2e");_cz_pt_row.pack(fill=tk.X,pady=(4,2))
        self._cz_start_btn=tk.Button(_cz_pt_row,text="◎  SET START",bg="#1e1e2e",fg="#a6adc8",
                                     relief=tk.FLAT,font=("Courier New",8,"bold"),padx=8,pady=4,cursor="hand2",
                                     command=lambda:self._cz_set_click_mode("start"))
        self._cz_start_btn.pack(side=tk.LEFT,padx=(0,4))
        self._cz_end_btn=tk.Button(_cz_pt_row,text="◉  SET END",bg="#4a1e1e",fg="#ff9a9a",
                                   relief=tk.FLAT,font=("Courier New",8,"bold"),padx=8,pady=4,cursor="hand2",
                                   command=lambda:self._cz_set_click_mode("end"))
        self._cz_end_btn.pack(side=tk.LEFT)
        self._cz_pt_info=tk.Label(self._cinzoom_frame,
                                  text="◎ Start (0.50, 0.50)   ◉ End (0.50, 0.45)",
                                  bg="#1a1a2e",fg="#585b70",font=("Courier New",7))
        self._cz_pt_info.pack(anchor=tk.W,pady=(2,0))
        # initialise click mode highlight
        self._cz_set_click_mode("end")

        # ── Firefly Glow (Jugnu) panel — index 36 ────────────────────────────
        self._jugnu_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._jugnu_frame,text="— FIREFLY GLOW (JUGNU) —",bg="#1a1a2e",fg="#f9e2af",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._jugnu_frame,
                 text="Paint the area where fireflies appear.\n"
                      "They pulse and drift in the region's\n"
                      "own dominant color — like real jugnu.\n\n"
                      "Count  = number of fireflies\n"
                      "Size   = glow bloom radius\n"
                      "Bright = glow intensity\n"
                      "Speed  = drift speed",
                 bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        _slider_row(self._jugnu_frame,"jugnu_count","Count",  5,  200, 60, ".0f")
        _slider_row(self._jugnu_frame,"jugnu_size", "Size",   0.2,4.0, 1.0,".2f")
        _slider_row(self._jugnu_frame,"jugnu_bright","Bright",0.1,3.0, 1.0,".2f")

        # ── AI Orbit (MiDaS 2.5D) panel — index 37 ───────────────────────────
        self._orbit25d_frame=tk.Frame(panel,bg="#1a1a2e")
        tk.Label(self._orbit25d_frame,text="— AI ORBIT (MiDaS 2.5D) —",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,2))
        tk.Label(self._orbit25d_frame,
                 text="Depth-aware parallax orbit using MiDaS.\n"
                      "Near objects shift more than far objects,\n"
                      "creating Luma-style cinematic 3D effect.\n\n"
                      "Paint mask = restrict effect to region.\n"
                      "Leave mask empty = full-frame effect.\n\n"
                      "NOTE: Depth map is computed once on\n"
                      "first play — may take a few seconds.\n"
                      "Requires: torch + MiDaS downloaded.\n"
                      "Falls back to luminance depth if absent.\n\n"
                      "Radius     = parallax strength (px)\n"
                      "Speed      = orbit cycles/sec\n"
                      "Depth Boost= depth separation exponent\n"
                      "Mode       = camera path style",
                 bg="#1a1a2e",fg="#585b70",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W)
        _slider_row(self._orbit25d_frame,"orbit_radius","Radius",   2, 120, 30.0,".0f")
        _slider_row(self._orbit25d_frame,"orbit_speed", "Speed",  0.02, 2.0,  0.25,".2f")
        _slider_row(self._orbit25d_frame,"depth_boost", "Depth Boost",0.3,4.0,1.5,".2f")
        # Orbit mode dropdown
        _om_row=tk.Frame(self._orbit25d_frame,bg="#1a1a2e");_om_row.pack(fill=tk.X,pady=(4,2))
        tk.Label(_om_row,text="Mode",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._orbit_mode_var=tk.StringVar(value="orbit")
        ttk.Combobox(_om_row,textvariable=self._orbit_mode_var,
                     values=["orbit","figure8","dolly","drift"],
                     state="readonly",width=10).pack(side=tk.LEFT,padx=4)
        self.pvars['orbit_mode']=self._orbit_mode_var
        self._orbit_mode_var.trace_add('write',lambda *_:self.after_idle(self._orbit25d_mode_changed))
        # Depth invert checkbox
        _di_row=tk.Frame(self._orbit25d_frame,bg="#1a1a2e");_di_row.pack(fill=tk.X,pady=2)
        self._orbit_invert_var=tk.BooleanVar(value=False)
        tk.Checkbutton(_di_row,text="Invert Depth (swap near/far)",
                       variable=self._orbit_invert_var,
                       bg="#1a1a2e",fg="#cdd6f4",selectcolor="#313244",
                       activebackground="#1a1a2e",activeforeground="#cdd6f4",
                       font=("Courier New",7),cursor="hand2").pack(side=tk.LEFT)
        self.pvars['depth_invert']=self._orbit_invert_var
        self._orbit_invert_var.trace_add('write',lambda *_:self.after_idle(self._orbit25d_reset_and_apply))

        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=(4,2))
        rep_row=tk.Frame(panel,bg="#1a1a2e");rep_row.pack(fill=tk.X,pady=2)
        self.pvars['repeat']=tk.BooleanVar(value=False)
        tk.Checkbutton(rep_row,text="Repeat Fall",variable=self.pvars['repeat'],bg="#1a1a2e",fg="#cdd6f4",selectcolor="#313244",activebackground="#1a1a2e",activeforeground="#cdd6f4",font=("Courier New",8),cursor="hand2").pack(side=tk.LEFT)
        for key,label,mn,mx,default in[("repeat_min","Wait Min(s)",0.5,30.0,2.0),("repeat_max","Wait Max(s)",0.5,60.0,8.0)]:_slider_row(panel,key,label,mn,mx,default)
        tk.Button(panel,text="Apply Params to Region",command=self._apply_params,bg="#1e3a2e",fg="#a6e3a1",relief=tk.FLAT,font=("Courier New",8),pady=3,cursor="hand2").pack(fill=tk.X,pady=4)

        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=4)
        tk.Label(panel,text="CAMERA TIMELINE",bg="#1a1a2e",fg="#89b4fa",font=("Courier New",9,"bold")).pack(anchor=tk.W)
        tk.Label(panel,text="Add camera angle keys; transitions are smooth between keys",bg="#1a1a2e",fg="#585b70",font=("Courier New",7)).pack(anchor=tk.W)
        trow=tk.Frame(panel,bg="#1a1a2e");trow.pack(fill=tk.X,pady=(3,2))
        tk.Label(trow,text="Time",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=6,anchor=tk.W).pack(side=tk.LEFT)
        self._timeline_scale=ttk.Scale(trow,from_=0.0,to=60.0,variable=self.timeline_time_var,orient=tk.HORIZONTAL,command=lambda _v:self._on_timeline_scrub())
        self._timeline_scale.pack(side=tk.LEFT,fill=tk.X,expand=True)
        self._timeline_lbl=tk.Label(trow,text="0.00s",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8),width=6)
        self._timeline_lbl.pack(side=tk.RIGHT)
        self._cam_track=tk.Canvas(panel,bg="#111118",height=34,highlightthickness=1,highlightbackground="#313244",cursor="hand2")
        self._cam_track.pack(fill=tk.X,pady=(0,3))
        self._cam_track.bind("<ButtonPress-1>",self._track_press)
        self._cam_track.bind("<B1-Motion>",self._track_drag)
        self._cam_track.bind("<ButtonRelease-1>",self._track_release)
        self._cam_track.bind("<Configure>",lambda e:self._draw_camera_track())
        krow=tk.Frame(panel,bg="#1a1a2e");krow.pack(fill=tk.X,pady=2)
        tk.Label(krow,text="Key @s",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=6,anchor=tk.W).pack(side=tk.LEFT)
        self._cam_key_t_var=tk.DoubleVar(value=0.0)
        tk.Spinbox(krow,from_=0.0,to=9999.0,increment=0.1,textvariable=self._cam_key_t_var,bg="#313244",fg="#cdd6f4",insertbackground="#cdd6f4",relief=tk.FLAT,font=("Courier New",8),width=6).pack(side=tk.LEFT,padx=(0,4))
        self._cam_angle_var=tk.StringVar(value="Eye Level")
        ttk.Combobox(krow,textvariable=self._cam_angle_var,values=list(CAMERA_PRESETS.keys()),state="readonly",width=12).pack(side=tk.LEFT,fill=tk.X,expand=True)
        srow=tk.Frame(panel,bg="#1a1a2e");srow.pack(fill=tk.X,pady=(0,2))
        tk.Label(srow,text="Shot",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=6,anchor=tk.W).pack(side=tk.LEFT)
        self._cam_shot_var=tk.StringVar(value="Static")
        ttk.Combobox(srow,textvariable=self._cam_shot_var,values=CAMERA_SHOTS,state="readonly",width=22).pack(side=tk.LEFT,fill=tk.X,expand=True)
        brow=tk.Frame(panel,bg="#1a1a2e");brow.pack(fill=tk.X,pady=(2,3))
        tk.Button(brow,text="+ Add/Update",command=self._add_camera_key,bg="#1e3a2e",fg="#a6e3a1",relief=tk.FLAT,font=("Courier New",8),pady=3,cursor="hand2").pack(side=tk.LEFT,fill=tk.X,expand=True)
        tk.Button(brow,text="Delete",command=self._delete_camera_key,bg="#3a1e1e",fg="#f38ba8",relief=tk.FLAT,font=("Courier New",8),pady=3,cursor="hand2").pack(side=tk.LEFT,fill=tk.X,expand=True,padx=(4,0))
        self._cam_list=tk.Listbox(panel,bg="#111118",fg="#cdd6f4",selectbackground="#313244",font=("Courier New",8),height=4,relief=tk.FLAT,highlightthickness=0)
        self._cam_list.pack(fill=tk.X,pady=(0,3))
        self._cam_list.bind("<<ListboxSelect>>",self._camera_list_sel)

        # ── Manual camera override sliders ────────────────────────────────────
        tk.Label(panel,text="CAMERA OVERRIDE  (live sliders)",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8,"bold")).pack(anchor=tk.W,pady=(4,0))
        tk.Label(panel,text="Adjust to preview camera angle instantly",bg="#1a1a2e",fg="#585b70",font=("Courier New",7)).pack(anchor=tk.W)
        self._cam_override_vars={}
        def _cam_slider(key,label,mn,mx,default,fmt=".1f"):
            row=tk.Frame(panel,bg="#1a1a2e");row.pack(fill=tk.X,pady=1)
            tk.Label(row,text=label,bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=7,anchor=tk.W).pack(side=tk.LEFT)
            var=tk.DoubleVar(value=default);self._cam_override_vars[key]=var
            vlbl=tk.Label(row,text=f"{default:{fmt}}",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",8),width=6);vlbl.pack(side=tk.RIGHT)
            ttk.Scale(row,from_=mn,to=mx,variable=var,orient=tk.HORIZONTAL,
                      command=lambda v,l=vlbl,f=fmt:l.config(text=f"{float(v):{f}}")
                      ).pack(side=tk.LEFT,fill=tk.X,expand=True)
            var.trace_add('write',lambda *_:self.after_idle(self._cam_override_changed))
        _cam_slider("pitch","Pitch°",-30,30,0.0,".1f")
        _cam_slider("yaw",  "Yaw°",  -30,30,0.0,".1f")
        _cam_slider("roll", "Roll°", -30,30,0.0,".1f")
        _cam_slider("zoom", "Zoom",  0.5,2.5,1.0,".2f")
        rst_row=tk.Frame(panel,bg="#1a1a2e");rst_row.pack(fill=tk.X,pady=(2,3))
        tk.Button(rst_row,text="Reset Camera",command=self._cam_override_reset,bg="#1e1e2e",fg="#585b70",relief=tk.FLAT,font=("Courier New",8),pady=3,cursor="hand2").pack(side=tk.LEFT,fill=tk.X,expand=True)

        # ── Lens effects ──────────────────────────────────────────────────────
        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=(6,2))
        tk.Label(panel,text="LENS EFFECTS",bg="#1a1a2e",fg="#fab387",font=("Courier New",8,"bold")).pack(anchor=tk.W)
        self._cam_lens_vars={}
        def _lens_slider(key,label,mn,mx,default,fmt=".2f"):
            row=tk.Frame(panel,bg="#1a1a2e");row.pack(fill=tk.X,pady=1)
            tk.Label(row,text=label,bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=12,anchor=tk.W).pack(side=tk.LEFT)
            var=tk.DoubleVar(value=default);self._cam_lens_vars[key]=var
            vlbl=tk.Label(row,text=f"{default:{fmt}}",bg="#1a1a2e",fg="#fab387",font=("Courier New",8),width=5);vlbl.pack(side=tk.RIGHT)
            ttk.Scale(row,from_=mn,to=mx,variable=var,orient=tk.HORIZONTAL,
                      command=lambda v,l=vlbl,f=fmt:l.config(text=f"{float(v):{f}}")
                      ).pack(side=tk.LEFT,fill=tk.X,expand=True)
            var.trace_add('write',lambda *_:self.after_idle(self._cam_override_changed))
        _lens_slider("vignette",    "Vignette",   0.0, 1.5, 0.0)
        _lens_slider("chroma",      "Chroma Aber",0.0, 8.0, 0.0, ".1f")
        _lens_slider("focus_blur",  "Focus Blur", 0.0, 1.0, 0.0)
        _lens_slider("lens_distortion","Barrel",  -0.4, 0.4, 0.0)
        _lens_slider("fisheye",     "Fisheye",    0.0, 0.8, 0.0)
        _lens_slider("anamorphic",  "Anamorphic", 0.0, 1.0, 0.0)

        # ── Special FX ───────────────────────────────────────────────────────
        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=(6,2))
        tk.Label(panel,text="SPECIAL FX",bg="#1a1a2e",fg="#f38ba8",font=("Courier New",8,"bold")).pack(anchor=tk.W)
        self._cam_fx_vars={}
        def _fx_slider(key,label,mn,mx,default,fmt=".2f"):
            row=tk.Frame(panel,bg="#1a1a2e");row.pack(fill=tk.X,pady=1)
            tk.Label(row,text=label,bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=12,anchor=tk.W).pack(side=tk.LEFT)
            var=tk.DoubleVar(value=default);self._cam_fx_vars[key]=var
            vlbl=tk.Label(row,text=f"{default:{fmt}}",bg="#1a1a2e",fg="#f38ba8",font=("Courier New",8),width=5);vlbl.pack(side=tk.RIGHT)
            ttk.Scale(row,from_=mn,to=mx,variable=var,orient=tk.HORIZONTAL,
                      command=lambda v,l=vlbl,f=fmt:l.config(text=f"{float(v):{f}}")
                      ).pack(side=tk.LEFT,fill=tk.X,expand=True)
            var.trace_add('write',lambda *_:self.after_idle(self._cam_override_changed))
        _fx_slider("grain",       "Film Grain",   0.0, 1.0, 0.0)
        _fx_slider("scanlines",   "Scanlines",    0.0, 1.0, 0.0)
        _fx_slider("heat_shimmer","Heat Shimmer", 0.0, 1.0, 0.0)
        # Color grade dropdown
        cg_row=tk.Frame(panel,bg="#1a1a2e");cg_row.pack(fill=tk.X,pady=2)
        tk.Label(cg_row,text="Color Grade",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=12,anchor=tk.W).pack(side=tk.LEFT)
        self._cam_grade_var=tk.StringVar(value="None")
        ttk.Combobox(cg_row,textvariable=self._cam_grade_var,
                     values=["None","Warm","Cool","Night","Vintage","Horror","Dreamy","B&W"],
                     state="readonly",width=10).pack(side=tk.LEFT,fill=tk.X,expand=True)
        self._cam_grade_var.trace_add('write',lambda *_:self.after_idle(self._cam_override_changed))
        # Mirror dropdown
        mir_row=tk.Frame(panel,bg="#1a1a2e");mir_row.pack(fill=tk.X,pady=2)
        tk.Label(mir_row,text="Mirror",bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=12,anchor=tk.W).pack(side=tk.LEFT)
        self._cam_mirror_var=tk.StringVar(value="None")
        ttk.Combobox(mir_row,textvariable=self._cam_mirror_var,
                     values=["None","Horizontal","Vertical","Kaleidoscope"],
                     state="readonly",width=10).pack(side=tk.LEFT,fill=tk.X,expand=True)
        self._cam_mirror_var.trace_add('write',lambda *_:self.after_idle(self._cam_override_changed))
        # Reset all FX button
        fx_rst=tk.Frame(panel,bg="#1a1a2e");fx_rst.pack(fill=tk.X,pady=(3,2))
        tk.Button(fx_rst,text="Reset All FX",command=self._cam_fx_reset,bg="#1e1e2e",fg="#585b70",relief=tk.FLAT,font=("Courier New",8),pady=3,cursor="hand2").pack(side=tk.LEFT,fill=tk.X,expand=True)

        tk.Frame(panel,bg="#313244",height=1).pack(fill=tk.X,pady=4)
        tk.Label(panel,text=f"EXPORT  (always {EXPORT_W}×{EXPORT_H}  9:16)",bg="#1a1a2e",fg="#89b4fa",font=("Courier New",9,"bold")).pack(anchor=tk.W)
        tk.Label(panel,text="Image letterboxed with black bars",bg="#1a1a2e",fg="#585b70",font=("Courier New",7)).pack(anchor=tk.W)
        for label,key,default in[("Duration(s)","duration",5),("FPS","fps",30)]:
            row=tk.Frame(panel,bg="#1a1a2e");row.pack(fill=tk.X,pady=2)
            tk.Label(row,text=label,bg="#1a1a2e",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
            var=tk.IntVar(value=default);self.pvars[key]=var
            tk.Spinbox(row,from_=1,to=120,textvariable=var,bg="#313244",fg="#cdd6f4",insertbackground="#cdd6f4",relief=tk.FLAT,font=("Courier New",8),width=5).pack(side=tk.LEFT)
            if key=="duration": var.trace_add('write',lambda *_:self.after_idle(self._duration_changed))

        self.status_var=tk.StringVar(value="Ready — open an image")
        tk.Label(self,textvariable=self.status_var,bg="#181825",fg="#585b70",font=("Courier New",8),anchor=tk.W).pack(fill=tk.X,side=tk.BOTTOM)

        for k,var in self.pvars.items():
            if k in('duration','fps'):continue
            var.trace_add('write',lambda *_,self=self:self.after_idle(self._live_apply))
        self._cloud_color_var.trace_add('write',lambda *_:self.after_idle(self._live_apply))
        self._sun_color_var.trace_add('write',  lambda *_:self.after_idle(self._live_apply))
        self._update_anim_panels()
        self._refresh_camera_list()
        self._duration_changed()

    # ── SMOKE PANEL ───────────────────────────────────────────────────────────
    def _build_smoke_panel(self, parent):
        lf=tk.LabelFrame(parent,text="",bg="#0e1120",fg="#f38ba8",relief=tk.FLAT,bd=1,padx=6,pady=6);lf.pack(fill=tk.X,pady=2)
        hdr_row=tk.Frame(lf,bg="#0e1120");hdr_row.pack(fill=tk.X)
        tk.Checkbutton(hdr_row,text="🌫  SMOKE OVERLAY",variable=self._smoke_enabled,
                       bg="#0e1120",fg="#cba6f7",selectcolor="#1a1a3e",activebackground="#0e1120",activeforeground="#cba6f7",
                       font=("Courier New",9,"bold"),cursor="hand2",
                       command=lambda:self.after_idle(self._live_apply)).pack(side=tk.LEFT)
        tk.Label(lf,text="Full-image overlay — no region painting needed",bg="#0e1120",fg="#45475a",font=("Courier New",7)).pack(anchor=tk.W)
        tk.Frame(lf,bg="#313244",height=1).pack(fill=tk.X,pady=4)
        self._smoke_pvars={}
        def _srow(key,label,mn,mx,default,fmt=".1f"):
            row=tk.Frame(lf,bg="#0e1120");row.pack(fill=tk.X,pady=2)
            tk.Label(row,text=label,bg="#0e1120",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
            var=tk.DoubleVar(value=default);self._smoke_pvars[key]=var
            vlbl=tk.Label(row,text=f"{default:{fmt}}",bg="#0e1120",fg="#cba6f7",font=("Courier New",8),width=5);vlbl.pack(side=tk.RIGHT)
            ttk.Scale(row,from_=mn,to=mx,variable=var,orient=tk.HORIZONTAL,command=lambda v,l=vlbl,f=fmt:l.config(text=f"{float(v):{f}}")
                      ).pack(side=tk.LEFT,fill=tk.X,expand=True)
            var.trace_add('write',lambda *_:self.after_idle(self._smoke_changed))
            return var
        _srow("density","Density",0.2,4.0,1.0)
        _srow("speed","Speed",0.1,4.0,1.0)
        _srow("turbulence","Turbulnce",0.0,2.0,0.5,".2f")
        _srow("opacity","Opacity",0.0,1.0,0.65,".2f")
        _srow("wind_deg","Wind Angle",0,360,270.0,".0f")
        col_row=tk.Frame(lf,bg="#0e1120");col_row.pack(fill=tk.X,pady=3)
        tk.Label(col_row,text="Color",bg="#0e1120",fg="#a6adc8",font=("Courier New",8),width=10,anchor=tk.W).pack(side=tk.LEFT)
        self._smoke_color_cb=ttk.Combobox(col_row,textvariable=self._smoke_color_var,values=SMOKE_COLOR_NAMES,state="readonly",width=12);self._smoke_color_cb.pack(side=tk.LEFT,padx=4)
        self._smoke_color_cb.bind("<<ComboboxSelected>>",lambda e:self.after_idle(self._smoke_changed))
        self._smoke_color_var.trace_add('write',lambda *_:self.after_idle(self._smoke_changed))
        self._smoke_enabled.trace_add('write',lambda *_:(self._extra.pop('__smoke__',None), self.after_idle(self._live_apply)))

    def _smoke_changed(self):
        self._extra.pop('__smoke__',None); self.after_idle(self._live_apply)

    def _get_smoke_params(self):
        sp={}
        for k,v in self._smoke_pvars.items(): sp[k]=v.get()
        sp['color']=self._smoke_color_var.get()
        return sp

    # ── LAYER PANEL ───────────────────────────────────────────────────────────
    def _build_layer_panel(self, parent):
        hdr=tk.Frame(parent,bg="#1a1a2e");hdr.pack(fill=tk.X,pady=(0,4))
        tk.Label(hdr,text="◈ LAYERS",bg="#1a1a2e",fg="#cba6f7",font=("Courier New",9,"bold")).pack(side=tk.LEFT)
        lf=tk.LabelFrame(parent,text="",bg="#111124",fg="#89b4fa",relief=tk.FLAT,bd=1,padx=6,pady=6);lf.pack(fill=tk.X,pady=2)
        tk.Label(lf,text="BACKGROUND  (behind image)",bg="#111124",fg="#89dceb",font=("Courier New",8,"bold")).pack(anchor=tk.W)
        bg_row=tk.Frame(lf,bg="#111124");bg_row.pack(fill=tk.X,pady=2)
        tk.Button(bg_row,text="Load PNG/MP4",command=self._load_bg,bg="#1e2e3a",fg="#89dceb",activebackground="#1a2530",relief=tk.FLAT,font=("Courier New",8),padx=6,pady=3,cursor="hand2").pack(side=tk.LEFT)
        tk.Button(bg_row,text="✕",command=self._remove_bg,bg="#3a1e1e",fg="#f38ba8",activebackground="#4a2e2e",relief=tk.FLAT,font=("Courier New",8),padx=6,pady=3,cursor="hand2").pack(side=tk.LEFT,padx=(4,0))
        self._bg_lbl=tk.Label(lf,text="— none —",bg="#111124",fg="#585b70",font=("Courier New",7),anchor=tk.W,wraplength=260,justify=tk.LEFT);self._bg_lbl.pack(fill=tk.X)
        bg_ctrl=tk.Frame(lf,bg="#111124");bg_ctrl.pack(fill=tk.X,pady=(2,0))
        tk.Label(bg_ctrl,text="Opacity",bg="#111124",fg="#a6adc8",font=("Courier New",7),width=7,anchor=tk.W).pack(side=tk.LEFT)
        self._bg_alpha_var=tk.DoubleVar(value=1.0);self._bg_alpha_lbl=tk.Label(bg_ctrl,text="100%",bg="#111124",fg="#cba6f7",font=("Courier New",7),width=4);self._bg_alpha_lbl.pack(side=tk.RIGHT)
        ttk.Scale(bg_ctrl,from_=0.0,to=1.0,variable=self._bg_alpha_var,orient=tk.HORIZONTAL,command=lambda v:self._bg_alpha_lbl.config(text=f"{float(v)*100:.0f}%")).pack(side=tk.LEFT,fill=tk.X,expand=True)
        bg_mode_row=tk.Frame(lf,bg="#111124");bg_mode_row.pack(fill=tk.X,pady=2)
        tk.Label(bg_mode_row,text="Blend",bg="#111124",fg="#a6adc8",font=("Courier New",7),width=7,anchor=tk.W).pack(side=tk.LEFT)
        self._bg_mode_var=tk.StringVar(value="Normal");ttk.Combobox(bg_mode_row,textvariable=self._bg_mode_var,values=BLEND_MODES,state="readonly",width=14).pack(side=tk.LEFT,padx=4)
        tk.Frame(lf,bg="#313244",height=1).pack(fill=tk.X,pady=6)
        tk.Label(lf,text="FOREGROUND  (on top of all)",bg="#111124",fg="#fab387",font=("Courier New",8,"bold")).pack(anchor=tk.W)
        fg_row=tk.Frame(lf,bg="#111124");fg_row.pack(fill=tk.X,pady=2)
        tk.Button(fg_row,text="Load PNG/MP4",command=self._load_fg,bg="#2e2a1e",fg="#fab387",activebackground="#252010",relief=tk.FLAT,font=("Courier New",8),padx=6,pady=3,cursor="hand2").pack(side=tk.LEFT)
        tk.Button(fg_row,text="✕",command=self._remove_fg,bg="#3a1e1e",fg="#f38ba8",activebackground="#4a2e2e",relief=tk.FLAT,font=("Courier New",8),padx=6,pady=3,cursor="hand2").pack(side=tk.LEFT,padx=(4,0))
        self._fg_lbl=tk.Label(lf,text="— none —",bg="#111124",fg="#585b70",font=("Courier New",7),anchor=tk.W,wraplength=260,justify=tk.LEFT);self._fg_lbl.pack(fill=tk.X)
        fg_ctrl=tk.Frame(lf,bg="#111124");fg_ctrl.pack(fill=tk.X,pady=(2,0))
        tk.Label(fg_ctrl,text="Opacity",bg="#111124",fg="#a6adc8",font=("Courier New",7),width=7,anchor=tk.W).pack(side=tk.LEFT)
        self._fg_alpha_var=tk.DoubleVar(value=1.0);self._fg_alpha_lbl=tk.Label(fg_ctrl,text="100%",bg="#111124",fg="#cba6f7",font=("Courier New",7),width=4);self._fg_alpha_lbl.pack(side=tk.RIGHT)
        ttk.Scale(fg_ctrl,from_=0.0,to=1.0,variable=self._fg_alpha_var,orient=tk.HORIZONTAL,command=lambda v:self._fg_alpha_lbl.config(text=f"{float(v)*100:.0f}%")).pack(side=tk.LEFT,fill=tk.X,expand=True)
        fg_mode_row=tk.Frame(lf,bg="#111124");fg_mode_row.pack(fill=tk.X,pady=2)
        tk.Label(fg_mode_row,text="Blend",bg="#111124",fg="#a6adc8",font=("Courier New",7),width=7,anchor=tk.W).pack(side=tk.LEFT)
        self._fg_mode_var=tk.StringVar(value="Normal");ttk.Combobox(fg_mode_row,textvariable=self._fg_mode_var,values=BLEND_MODES,state="readonly",width=14).pack(side=tk.LEFT,padx=4)
        tk.Label(lf,text="💡 PNG supports transparency (RGBA)\n   MP4 loops automatically",bg="#111124",fg="#45475a",font=("Courier New",7),justify=tk.LEFT).pack(anchor=tk.W,pady=(6,0))

    _LAYER_FTYPES=[("Image / Video","*.png *.jpg *.jpeg *.bmp *.webp *.mp4 *.avi *.mov *.mkv *.webm"),("PNG Images","*.png"),("MP4 / Video","*.mp4 *.avi *.mov *.mkv *.webm"),("All files","*.*")]
    def _load_bg(self):
        path=filedialog.askopenfilename(filetypes=self._LAYER_FTYPES)
        if not path:return
        try:
            if self._bg_source:self._bg_source.release()
            self._bg_source=LayerSource(path);self._bg_lbl.config(text=self._bg_source.label(),fg="#89dceb")
        except Exception as e:messagebox.showerror("Layer Error",str(e))
    def _remove_bg(self):
        if self._bg_source:self._bg_source.release();self._bg_source=None
        self._bg_lbl.config(text="— none —",fg="#585b70")
    def _load_fg(self):
        path=filedialog.askopenfilename(filetypes=self._LAYER_FTYPES)
        if not path:return
        try:
            if self._fg_source:self._fg_source.release()
            self._fg_source=LayerSource(path);self._fg_lbl.config(text=self._fg_source.label(),fg="#fab387")
            self._refresh_canvas()
        except Exception as e:messagebox.showerror("Layer Error",str(e))
    def _remove_fg(self):
        if self._fg_source:self._fg_source.release();self._fg_source=None
        self._fg_lbl.config(text="— none —",fg="#585b70")
        self._refresh_canvas()

    CLOTH_PRESETS={"Silk":(18,1.4,1.8,7,3.2,0.50,0.18,0.10,1.20),"Heavy Fabric":(9,0.8,0.6,3,1.8,0.80,0.10,0.05,1.80),"Sheer Curtain":(22,1.8,2.2,10,4.0,0.30,0.35,0.30,0.90),"Satin":(16,1.2,1.5,8,2.8,0.45,0.30,0.08,1.47),"Denim":(7,0.7,0.5,2,1.5,0.85,0.08,0.04,2.00)}
    _CLOTH_KEYS=("c_amp","c_freq","c_spd","c_amp2","c_freq2","c_drape","c_shear","c_turb","c_phase2")

    # ── 3D DEPTH LAYER PANEL ─────────────────────────────────────────────────
    def _build_depth3d_panel(self, parent):
        """Build the 3D Camera Fly-Through control panel."""
        BG = "#0e1120"; ACC = "#cba6f7"; ACC2 = "#f38ba8"; DIM = "#45475a"; FG = "#cdd6f4"
        lf = tk.LabelFrame(parent, text="", bg=BG, fg=ACC, relief=tk.FLAT, bd=1, padx=6, pady=6)
        lf.pack(fill=tk.X, pady=2)

        # Header with enable toggle
        hdr = tk.Frame(lf, bg=BG); hdr.pack(fill=tk.X)
        tk.Checkbutton(hdr, text="🎬  3D CAMERA FLY-THROUGH",
                       variable=self._depth3d_enabled,
                       bg=BG, fg=ACC, selectcolor="#1a1a3e",
                       activebackground=BG, activeforeground=ACC,
                       font=("Courier New", 9, "bold"), cursor="hand2",
                       command=lambda: self.after_idle(self._live_apply)).pack(side=tk.LEFT)
        tk.Label(lf, text="After Effects-style 3D parallax depth camera",
                 bg=BG, fg=DIM, font=("Courier New", 7)).pack(anchor=tk.W)
        tk.Label(lf,
                 text="Assign a DEPTH to each region below.\n"
                      "Camera flies through layers toward depth=1.0\n"
                      "Each layer keeps its own animation type.\n\n"
                      "depth 0.0 = far background\n"
                      "depth 1.0 = main subject (camera arrives here)",
                 bg=BG, fg=DIM, font=("Courier New", 7), justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 4))

        tk.Frame(lf, bg="#313244", height=1).pack(fill=tk.X, pady=4)

        # Camera mode
        mode_row = tk.Frame(lf, bg=BG); mode_row.pack(fill=tk.X, pady=2)
        tk.Label(mode_row, text="Cam Mode", bg=BG, fg="#a6adc8",
                 font=("Courier New", 8), width=10, anchor=tk.W).pack(side=tk.LEFT)
        ttk.Combobox(mode_row, textvariable=self._depth3d_cam_mode,
                     values=DEPTH_CAMERA_MODES, state="readonly", width=14).pack(side=tk.LEFT, padx=4)
        self._depth3d_cam_mode.trace_add('write', lambda *_: self.after_idle(self._live_apply))

        # Camera sliders
        self._depth3d_pvars = {}

        def _d3d_slider(key, label, mn, mx, default, fmt=".2f"):
            row = tk.Frame(lf, bg=BG); row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=label, bg=BG, fg="#a6adc8",
                     font=("Courier New", 8), width=10, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.DoubleVar(value=default); self._depth3d_pvars[key] = var
            vlbl = tk.Label(row, text=f"{default:{fmt}}", bg=BG, fg=ACC,
                            font=("Courier New", 8), width=5); vlbl.pack(side=tk.RIGHT)
            ttk.Scale(row, from_=mn, to=mx, variable=var, orient=tk.HORIZONTAL,
                      command=lambda v, l=vlbl, f=fmt: l.config(text=f"{float(v):{f}}")
                      ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            var.trace_add('write', lambda *_: self.after_idle(self._live_apply))

        _d3d_slider("cam_speed",   "Cam Speed",   0.1, 4.0,  1.0)
        _d3d_slider("dof_strength","DoF Blur",    0.0, 2.0,  0.6)
        _d3d_slider("parallax_x",  "Parallax X",  0,  120,  45.0, ".0f")
        _d3d_slider("parallax_y",  "Parallax Y",  0,   80,  22.0, ".0f")
        _d3d_slider("scale_range", "Depth Scale", 0.0, 1.0,  0.38)
        _d3d_slider("vignette",    "Vignette",    0.0, 1.5,  0.45)
        _d3d_slider("chroma_ab",   "Chrom.Aber.", 0.0, 3.0,  0.5)
        _d3d_slider("fog_near",    "Depth Fog",   0.0, 1.5,  0.35)

        tk.Frame(lf, bg="#313244", height=1).pack(fill=tk.X, pady=(6, 3))

        # ── Per-region depth layer list ───────────────────────────────────────
        tk.Label(lf, text="DEPTH LAYERS  (one per region)",
                 bg=BG, fg=ACC2, font=("Courier New", 8, "bold")).pack(anchor=tk.W)

        # Container that holds the per-region depth rows
        self._d3d_layers_frame = tk.Frame(lf, bg=BG)
        self._d3d_layers_frame.pack(fill=tk.X, pady=(3, 0))

        # Add-layer button
        add_row = tk.Frame(lf, bg=BG); add_row.pack(fill=tk.X, pady=(6, 2))
        tk.Button(add_row, text="➕  Add Depth Layer",
                  command=self._d3d_add_layer,
                  bg="#1a2e1a", fg="#a6e3a1", activebackground="#162614",
                  relief=tk.FLAT, font=("Courier New", 8, "bold"),
                  padx=8, pady=4, cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Rebuild whenever regions change
        self._d3d_refresh_layers()

    def _d3d_refresh_layers(self):
        """Rebuild the depth layer rows from self._depth3d_layers."""
        BG = "#0e1120"; ACC = "#cba6f7"; DIM = "#45475a"
        if not hasattr(self, '_d3d_layers_frame'):
            return
        for w in self._d3d_layers_frame.winfo_children():
            w.destroy()
        for i, lyr in enumerate(self._depth3d_layers):
            row = tk.Frame(self._d3d_layers_frame, bg="#111124",
                           relief=tk.FLAT, bd=1, padx=4, pady=3)
            row.pack(fill=tk.X, pady=2)

            # Region label
            reg_idx = lyr.get('region_idx', i)
            reg_label = f"Region {reg_idx + 1}"
            if 0 <= reg_idx < len(self.regions):
                at = self.regions[reg_idx]['anim_type']
                reg_label = f"R{reg_idx+1}: {ANIM_TYPES[at][:14]}"
            tk.Label(row, text=reg_label, bg="#111124", fg=ACC,
                     font=("Courier New", 7, "bold"), width=16, anchor=tk.W).pack(side=tk.LEFT)

            # Depth slider
            tk.Label(row, text="Z", bg="#111124", fg=DIM,
                     font=("Courier New", 7)).pack(side=tk.LEFT, padx=(4, 1))
            depth_var = lyr.setdefault('depth_var', tk.DoubleVar(value=lyr.get('depth', 0.5)))
            lyr['depth_var'] = depth_var
            depth_lbl = tk.Label(row, text=f"{depth_var.get():.2f}", bg="#111124", fg="#f9e2af",
                                 font=("Courier New", 7), width=4)
            depth_lbl.pack(side=tk.LEFT)
            depth_s = ttk.Scale(row, from_=0.0, to=1.0, variable=depth_var, orient=tk.HORIZONTAL,
                                length=70,
                                command=lambda v, l=depth_lbl, ld=lyr:
                                    (l.config(text=f"{float(v):.2f}"),
                                     ld.update({'depth': float(v)}),
                                     self.after_idle(self._live_apply)))
            depth_s.pack(side=tk.LEFT, padx=2)

            # Blur override
            tk.Label(row, text="Blur", bg="#111124", fg=DIM,
                     font=("Courier New", 7)).pack(side=tk.LEFT, padx=(4, 1))
            blur_var = lyr.setdefault('blur_var', tk.DoubleVar(value=lyr.get('blur_override', 0.0)))
            lyr['blur_var'] = blur_var
            blur_lbl = tk.Label(row, text=f"{blur_var.get():.1f}", bg="#111124", fg="#89dceb",
                                font=("Courier New", 7), width=3)
            blur_lbl.pack(side=tk.LEFT)
            blur_s = ttk.Scale(row, from_=0.0, to=12.0, variable=blur_var, orient=tk.HORIZONTAL,
                               length=55,
                               command=lambda v, l=blur_lbl, ld=lyr:
                                   (l.config(text=f"{float(v):.1f}"),
                                    ld.update({'blur_override': float(v) if float(v) > 0.1 else None}),
                                    self.after_idle(self._live_apply)))
            blur_s.pack(side=tk.LEFT, padx=2)

            # Remove button
            def _make_remove(idx):
                return lambda: self._d3d_remove_layer(idx)
            tk.Button(row, text="✕", command=_make_remove(i),
                      bg="#2a0e0e", fg="#f38ba8", activebackground="#3a1e1e",
                      relief=tk.FLAT, font=("Courier New", 8),
                      padx=4, pady=0, cursor="hand2").pack(side=tk.RIGHT)

    def _d3d_add_layer(self):
        """Add a new depth layer, defaulting to the first unassigned region."""
        used = {lyr.get('region_idx') for lyr in self._depth3d_layers}
        new_idx = 0
        for i in range(len(self.regions)):
            if i not in used:
                new_idx = i; break
        depth_default = 0.3 + len(self._depth3d_layers) * 0.15
        self._depth3d_layers.append({
            'region_idx':    new_idx,
            'depth':         min(0.95, depth_default),
            'blur_override': None,
            'opacity':       1.0,
        })
        self._d3d_refresh_layers()
        self.after_idle(self._live_apply)

    def _d3d_remove_layer(self, idx):
        if 0 <= idx < len(self._depth3d_layers):
            del self._depth3d_layers[idx]
        self._d3d_refresh_layers()
        self.after_idle(self._live_apply)

    def _get_depth3d_params(self):
        """Build the params dict for apply_3d_depth_layers()."""
        p = {'cam_mode': self._depth3d_cam_mode.get()}
        for k, var in self._depth3d_pvars.items():
            p[k] = var.get()
        dur = max(1.0, float(self.pvars.get("duration", tk.IntVar(value=5)).get()))
        p['_duration'] = dur
        return p

    def _get_depth3d_layers_for_render(self, static_np_ref, disp_np_ref, extra_states, t, dt):
        """Build the depth_layers list for render, rendering each region's animation into its own image."""
        if not self._depth3d_enabled.get() or not self._depth3d_layers:
            return None
        layers_out = []
        for lyr in self._depth3d_layers:
            reg_idx = lyr.get('region_idx', 0)
            if reg_idx < 0 or reg_idx >= len(self.regions):
                continue
            reg = self.regions[reg_idx]
            depth    = float(lyr.get('depth', 0.5))
            blur_ov  = lyr.get('blur_override', None)
            # Render this single region's animation
            single_reg_list = [{'mask':   reg['mask_disp'],
                                 'freeze_mask': reg.get('freeze_disp'),
                                 'anchors': reg.get('anchors', []),
                                 'paths':   reg.get('paths', []),
                                 'anim_type': reg['anim_type'],
                                 'params':  reg['params'],
                                 'static_np': disp_np_ref}]
            try:
                animated_frame = render_regions(disp_np_ref, single_reg_list, t, dt, extra_states)
            except Exception:
                animated_frame = disp_np_ref.copy()
            mask = reg['mask_disp']
            layers_out.append({
                'depth':   depth,
                'image':   animated_frame,
                'mask':    mask,
                'blur':    blur_ov,
                'opacity': float(lyr.get('opacity', 1.0)),
            })
        return layers_out if layers_out else None

    def _update_anim_panels(self):
        at=self.anim_var.get()
        for f in(self._cloth_frame,self._fog_frame,self._scroll_frame,self._cloud_frame,
                 self._rain_frame,self._sun_frame,self._float_frame,self._updown_frame,
                 self._spinf_frame,self._waterflow_frame,self._leap_hop_frame,
                 self._leap_side_frame,self._leap_pulse_frame,self._motionpath_frame,
                 self._livepaint_frame,self._pixflow_frame,self._waterfall_frame,
                 self._cinzoom_frame,self._jugnu_frame,self._orbit25d_frame):
            f.pack_forget()
        if at==0:  self._cloth_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==10: self._fog_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==12: self._scroll_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==13: self._cloud_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==14: self._rain_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==15: self._sun_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==16: self._float_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==17: self._updown_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==18: self._spinf_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==22: self._waterflow_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==23: self._leap_hop_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==24: self._leap_side_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==25: self._leap_pulse_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==26: self._motionpath_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==28: self._motionpath_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==29: self._livepaint_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==33: self._pixflow_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==34: self._waterfall_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==35: self._cinzoom_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==36: self._jugnu_frame.pack(fill=tk.X,after=self._generic_frame)
        if at==37: self._orbit25d_frame.pack(fill=tk.X,after=self._generic_frame)

    # ── Cinematic Zoom start/end point helpers (agent.py style) ──────────────
    def _cz_set_click_mode(self, mode):
        self._cz_click_mode=mode
        if mode=="start":
            self._cz_start_btn.config(bg="#2a2a6a",fg="#89b4fa")
            self._cz_end_btn.config(bg="#1e1e2e",fg="#a6adc8")
        else:
            self._cz_end_btn.config(bg="#4a1e1e",fg="#ff9a9a")
            self._cz_start_btn.config(bg="#1e1e2e",fg="#a6adc8")

    def _cz_handle_canvas_click(self, cx, cy):
        """Called from _press when anim type 35 is active and we're in CZ click mode."""
        if self.disp_np is None:
            return
        dH,dW=self.disp_np.shape[:2]
        ox=(self.canvas.winfo_width()-dW)//2+self.pan_x
        oy=(self.canvas.winfo_height()-dH)//2+self.pan_y
        ix=cx-ox;iy=cy-oy
        if ix<0 or iy<0 or ix>=dW or iy>=dH:
            return
        nx=ix/dW;ny=iy/dH
        if self._cz_click_mode=="start":
            self._cz_start_norm=(round(nx,4),round(ny,4))
        else:
            self._cz_end_norm=(round(nx,4),round(ny,4))
        sx,sy=self._cz_start_norm;ex,ey=self._cz_end_norm
        self._cz_pt_info.config(text=f"◎ Start ({sx:.2f}, {sy:.2f})   ◉ End ({ex:.2f}, {ey:.2f})")
        self._refresh_canvas()
        self.after_idle(self._live_apply)

    def _cz_draw_crosshairs(self):
        """Draw start (blue) and end (red) crosshairs on the main canvas for anim 35."""
        if self.disp_np is None:
            return
        dH,dW=self.disp_np.shape[:2]
        ox=(self.canvas.winfo_width()-dW)//2+self.pan_x
        oy=(self.canvas.winfo_height()-dH)//2+self.pan_y
        self.canvas.delete("cz_crosshair")
        # START point — blue/violet
        sx=ox+self._cz_start_norm[0]*dW
        sy=oy+self._cz_start_norm[1]*dH
        r=12
        self.canvas.create_oval(sx-r,sy-r,sx+r,sy+r,outline="#89b4fa",width=2,tags="cz_crosshair")
        self.canvas.create_oval(sx-4,sy-4,sx+4,sy+4,outline="#89b4fa",width=1.5,tags="cz_crosshair")
        for dx2,dy2,ex2,ey2 in[(-r-8,0,-r+2,0),(r-2,0,r+8,0),(0,-r-8,0,-r+2),(0,r-2,0,r+8)]:
            self.canvas.create_line(sx+dx2,sy+dy2,sx+ex2,sy+ey2,fill="#89b4fa",width=2,tags="cz_crosshair")
        self.canvas.create_oval(sx-2,sy-2,sx+2,sy+2,fill="#89b4fa",outline="",tags="cz_crosshair")
        self.canvas.create_text(sx+r+4,sy-r,text="START",fill="#89b4fa",font=("Courier New",7,"bold"),anchor="w",tags="cz_crosshair")
        # END point — red
        ex_c=ox+self._cz_end_norm[0]*dW
        ey_c=oy+self._cz_end_norm[1]*dH
        r2=14
        self.canvas.create_oval(ex_c-r2,ey_c-r2,ex_c+r2,ey_c+r2,outline="#ff6b6b",width=2,tags="cz_crosshair")
        r3=6
        self.canvas.create_oval(ex_c-r3,ey_c-r3,ex_c+r3,ey_c+r3,outline="#ff6b6b",width=1.5,tags="cz_crosshair")
        for dx2,dy2,ex2,ey2 in[(-r2-8,0,-r2+2,0),(r2-2,0,r2+8,0),(0,-r2-8,0,-r2+2),(0,r2-2,0,r2+8)]:
            self.canvas.create_line(ex_c+dx2,ey_c+dy2,ex_c+ex2,ey_c+ey2,fill="#ff6b6b",width=2,tags="cz_crosshair")
        self.canvas.create_oval(ex_c-3,ey_c-3,ex_c+3,ey_c+3,fill="#ff6b6b",outline="",tags="cz_crosshair")
        self.canvas.create_text(ex_c+r2+4,ey_c-r2,text="END (camera lands here)",fill="#ff6b6b",font=("Courier New",7,"bold"),anchor="w",tags="cz_crosshair")
        # Line connecting them
        self.canvas.create_line(sx,sy,ex_c,ey_c,fill="#585b70",width=1,dash=(4,4),tags="cz_crosshair")

    def _apply_cloth_preset(self,event=None):
        name=self._cloth_preset.get()
        if name not in self.CLOTH_PRESETS:return
        vals=self.CLOTH_PRESETS[name]
        for k,v in zip(self._CLOTH_KEYS,vals):
            self.pvars[k].set(v)
            if k in self._cloth_vlbls:self._cloth_vlbls[k].config(text=f"{v:.2f}")

    def _cloud_color_changed(self):
        if self.active_reg is None:return
        self._extra.pop(('clouds',self.active_reg),None);self._live_apply()
    def _sun_color_changed(self):
        if self.active_reg is None:return
        self._extra.pop(('sun',self.active_reg),None);self._live_apply()

    def _orbit25d_mode_changed(self):
        """Orbit mode changed — no need to reset depth, just re-render."""
        self.after_idle(self._live_apply)

    def _orbit25d_reset_and_apply(self):
        """Depth invert toggled — clear cached state so depth is recomputed."""
        if self.active_reg is not None:
            self._extra.pop(('orbit25d', self.active_reg), None)
        self.after_idle(self._live_apply)

    def _pan_by(self,dx,dy):self.pan_x+=dx;self.pan_y+=dy;self._refresh_canvas()
    def zoom_in(self):self.zoom_level=min(self.zoom_max,self.zoom_level*1.25);self._apply_zoom()
    def zoom_out(self):self.zoom_level=max(self.zoom_min,self.zoom_level/1.25);self._apply_zoom()
    def zoom_reset(self):self.zoom_level=1.0;self.pan_x=0;self.pan_y=0;self._apply_zoom()
    def _on_mousewheel(self,event):
        if event.delta>0:self.zoom_in()
        else:self.zoom_out()
    def _pan_start_cb(self,event):self._pan_start=(event.x,event.y,self.pan_x,self.pan_y)
    def _pan_move_cb(self,event):
        if self._pan_start is None:return
        sx,sy,px0,py0=self._pan_start;self.pan_x=px0+(event.x-sx);self.pan_y=py0+(event.y-sy);self._refresh_canvas()
    def _pan_end_cb(self,event):self._pan_start=None
    def _apply_zoom(self):
        self.zoom_lbl.config(text=f"{int(self.zoom_level*100)}%")
        if self.static_np is None:return
        self._build_disp_np();self._refresh_canvas()

    def _build_disp_np(self):
        if self.static_np is None:return
        cw=self.canvas.winfo_width() or 800;ch=self.canvas.winfo_height() or 600
        H,W=self.static_np.shape[:2];fit_scale=min(cw/W,ch/H,1.0);effective=fit_scale*self.zoom_level
        self.disp_scale=effective;dw=max(1,int(W*effective));dh=max(1,int(H*effective))
        self.disp_np=cv2.resize(self.static_np,(dw,dh),interpolation=cv2.INTER_AREA)
        for reg in self.regions:
            old=reg['mask_disp'];old_h,old_w=old.shape[:2]
            if old.shape!=(dh,dw):
                sx=(dw/max(1,old_w));sy=(dh/max(1,old_h))
                reg['mask_disp']=cv2.resize(old,(dw,dh),interpolation=cv2.INTER_NEAREST)
                reg['freeze_disp']=cv2.resize(reg.get('freeze_disp',np.zeros_like(old)),(dw,dh),interpolation=cv2.INTER_NEAREST)
                reg['anchors']=[{'x':a['x']*sx,'y':a['y']*sy} for a in reg.get('anchors',[])]
                reg['paths']=[{'x1':p['x1']*sx,'y1':p['y1']*sy,'x2':p['x2']*sx,'y2':p['y2']*sy} for p in reg.get('paths',[])]

    def _all_param_keys(self):
        return('amp','freq','spd','turb','fall_delay','repeat','repeat_min','repeat_max',
               'dispersion','foam','path_radius','anchor_strength',
               'c_amp','c_freq','c_spd','c_amp2','c_freq2','c_drape','c_shear','c_turb','c_phase2',
               'direction','density','stretch','cloud_dir','cloud_alpha','cloud_count',
               'rain_angle','rain_density','sun_x','sun_y','sun_size','sun_glow','sun_rays',
               'orbit_radius','orbit_speed','orbit_mode','depth_boost','depth_invert',
               'spin_speed','bob_lateral',
               'lp_loop',
               'pf_motion',
               'start_t','end_t',
               'vignette','brightness','contrast','fade_duration',
               'jugnu_count','jugnu_size','jugnu_bright')

    def _build_params(self):
        params={k:self.pvars[k].get() for k in self._all_param_keys() if k in self.pvars}
        params['cloud_color']=self._cloud_color_var.get();params['sun_color']=self._sun_color_var.get()
        # ── Cinematic Zoom (index 35) extra params ────────────────────────────
        params['effect']   =self._cz_effect_var.get()
        params['easing']   =self._cz_easing_var.get()
        params['zoom_start']=self._cz_zoom_start_var.get()
        params['zoom_end']  =self._cz_zoom_end_var.get()
        params['fade_black']=self._cz_fade_black_var.get()
        params['fade_white']=self._cz_fade_white_var.get()
        params['start_x'],params['start_y']=self._cz_start_norm
        params['end_x'],  params['end_y']  =self._cz_end_norm
        return params

    def _duration_changed(self):
        dur=max(1.0,float(self.pvars.get("duration",tk.IntVar(value=5)).get()))
        self._timeline_scale.configure(to=dur)
        if self.timeline_time_var.get()>dur:
            self._timeline_internal=True;self.timeline_time_var.set(dur);self._timeline_internal=False
        self._timeline_lbl.config(text=f"{self.timeline_time_var.get():.2f}s")
        self._draw_camera_track()

    def _refresh_camera_list(self):
        self.camera_keyframes=sorted(self.camera_keyframes,key=lambda k:float(k["time"]))
        self._cam_list.delete(0,tk.END)
        for i,k in enumerate(self.camera_keyframes):
            self._cam_list.insert(tk.END,f"{i+1:02d}  {float(k['time']):6.2f}s  {k['preset']}  |  {k.get('shot','Static')}")
        self._draw_camera_track()

    def _time_to_track_x(self, t):
        w=max(40,int(self._cam_track.winfo_width())-8);dur=max(1.0,float(self.pvars["duration"].get()))
        return 4 + max(0.0,min(1.0,float(t)/dur))*w

    def _track_x_to_time(self, x):
        w=max(40,int(self._cam_track.winfo_width())-8);dur=max(1.0,float(self.pvars["duration"].get()))
        xr=max(4,min(int(self._cam_track.winfo_width())-4,x))-4
        return (xr/w)*dur

    def _draw_camera_track(self):
        if not hasattr(self,"_cam_track"):return
        c=self._cam_track;c.delete("all")
        w=max(1,int(c.winfo_width()));h=max(1,int(c.winfo_height()))
        c.create_line(4,h//2,w-4,h//2,fill="#585b70",width=2)
        current_t=float(self.timeline_time_var.get());cx=self._time_to_track_x(current_t)
        c.create_line(cx,6,cx,h-6,fill="#89b4fa",width=2)
        for i,k in enumerate(self.camera_keyframes):
            x=self._time_to_track_x(float(k["time"]))
            color="#f9e2af" if i==self._track_drag_index else "#cba6f7"
            c.create_oval(x-5,h//2-5,x+5,h//2+5,fill=color,outline="")
            c.create_text(x,h-8,text=str(i+1),fill="#a6adc8",font=("Courier New",7))

    def _nearest_track_key(self, x):
        if not self.camera_keyframes:return None
        best_i=None;best_d=1e9
        for i,k in enumerate(self.camera_keyframes):
            d=abs(self._time_to_track_x(float(k["time"]))-x)
            if d<best_d:best_d=d;best_i=i
        return best_i if best_d<=12 else None

    def _track_press(self, e):
        idx=self._nearest_track_key(e.x)
        if idx is None:
            t=self._track_x_to_time(e.x)
            self._timeline_internal=True;self.timeline_time_var.set(t);self._timeline_internal=False
            self._timeline_lbl.config(text=f"{t:.2f}s")
            self._on_timeline_scrub()
            return
        self._track_drag_index=idx;self._draw_camera_track()
        self._cam_list.selection_clear(0,tk.END);self._cam_list.selection_set(idx);self._cam_list.activate(idx)
        self._camera_list_sel(None)

    def _track_drag(self, e):
        if self._track_drag_index is None:return
        dur=max(1.0,float(self.pvars["duration"].get()))
        t=max(0.0,min(self._track_x_to_time(e.x),dur))
        self.camera_keyframes[self._track_drag_index]["time"]=t
        self._cam_key_t_var.set(round(t,2))
        self._timeline_internal=True;self.timeline_time_var.set(t);self._timeline_internal=False
        self._timeline_lbl.config(text=f"{t:.2f}s")
        self._draw_camera_track()
        self._on_timeline_scrub()

    def _track_release(self, e):
        if self._track_drag_index is None:return
        drag_preset=self.camera_keyframes[self._track_drag_index]["preset"]
        drag_time=float(self.camera_keyframes[self._track_drag_index]["time"])
        collapsed=[]
        for k in sorted(self.camera_keyframes,key=lambda it:float(it["time"])):
            if collapsed and abs(float(collapsed[-1]["time"])-float(k["time"]))<1e-3:
                collapsed[-1]["preset"]=k["preset"];collapsed[-1]["shot"]=k.get("shot","Static")
            else:
                collapsed.append({"time":float(k["time"]),"preset":k["preset"],"shot":k.get("shot","Static")})
        self.camera_keyframes=collapsed
        new_idx=0
        for i,k in enumerate(self.camera_keyframes):
            if k["preset"]==drag_preset and abs(float(k["time"])-drag_time)<1e-3:
                new_idx=i;break
        self._track_drag_index=None
        self._refresh_camera_list()
        self._cam_list.selection_clear(0,tk.END)
        if self.camera_keyframes:
            self._cam_list.selection_set(new_idx);self._cam_list.activate(new_idx)
        self._camera_list_sel(None)

    def _cam_override_changed(self):
        if self.disp_np is None:return
        if not self.prevOn:self._on_timeline_scrub(force=True)

    def _cam_override_reset(self):
        for key,default in[("pitch",0.0),("yaw",0.0),("roll",0.0),("zoom",1.0)]:
            self._cam_override_vars[key].set(default)

    def _add_camera_key(self):
        dur=max(1.0,float(self.pvars["duration"].get()))
        t=max(0.0,min(float(self._cam_key_t_var.get()),dur));preset=self._cam_angle_var.get();shot=self._cam_shot_var.get()
        # Capture current override slider values into the keyframe
        custom={}
        if hasattr(self,'_cam_override_vars'):
            custom={k:float(v.get()) for k,v in self._cam_override_vars.items()}
        updated=False
        for k in self.camera_keyframes:
            if abs(float(k["time"])-t)<1e-6:
                k["preset"]=preset;k["shot"]=shot;k.update(custom);updated=True;break
        if not updated:
            entry={"time":t,"preset":preset,"shot":shot};entry.update(custom)
            self.camera_keyframes.append(entry)
        self._refresh_camera_list()
        self.status_var.set(f"{'Updated' if updated else 'Added'} key @ {t:.2f}s ({preset}, {shot})")
        if not self.prevOn:self._on_timeline_scrub(force=True)

    def _delete_camera_key(self):
        sel=self._cam_list.curselection()
        if not sel:return
        idx=sel[0]
        if idx<0 or idx>=len(self.camera_keyframes):return
        rem=self.camera_keyframes.pop(idx);self._refresh_camera_list()
        self.status_var.set(f"Deleted camera key @ {float(rem['time']):.2f}s")
        if not self.prevOn:self._on_timeline_scrub(force=True)

    def _camera_list_sel(self,e):
        sel=self._cam_list.curselection()
        if not sel:return
        idx=sel[0]
        if idx<0 or idx>=len(self.camera_keyframes):return
        k=self.camera_keyframes[idx]
        self._cam_key_t_var.set(round(float(k["time"]),2));self._cam_angle_var.set(k["preset"]);self._cam_shot_var.set(k.get("shot","Static"))
        # Populate override sliders from the selected preset values
        if hasattr(self,'_cam_override_vars'):
            p=CAMERA_PRESETS.get(k["preset"],CAMERA_PRESETS["Eye Level"])
            self._cam_override_vars["pitch"].set(float(p["pitch"]))
            self._cam_override_vars["yaw"].set(float(p["yaw"]))
            self._cam_override_vars["roll"].set(float(p["roll"]))
            self._cam_override_vars["zoom"].set(float(p["zoom"]))
        self._timeline_internal=True;self.timeline_time_var.set(float(k["time"]));self._timeline_internal=False
        self._timeline_lbl.config(text=f"{self.timeline_time_var.get():.2f}s")
        self._draw_camera_track()
        if not self.prevOn:self._on_timeline_scrub(force=True)

    def _draw_preview_frame(self, frame):
        pil=Image.fromarray(frame);self._tk_img=ImageTk.PhotoImage(pil)
        ox,oy=self._image_offset();dh,dw=self.disp_np.shape[:2]
        self.canvas.delete("img");self.canvas.create_image(ox+dw//2,oy+dh//2,anchor=tk.CENTER,image=self._tk_img,tags="img")

    def _cam_fx_reset(self):
        for key in self._cam_lens_vars:
            self._cam_lens_vars[key].set(0.0)
        for key in self._cam_fx_vars:
            self._cam_fx_vars[key].set(0.0)
        self._cam_grade_var.set("None")
        self._cam_mirror_var.set("None")

    def _get_cam_with_overrides(self, t):
        cam=resolve_camera_director(self.camera_keyframes,t)
        if hasattr(self,'_cam_override_vars'):
            cam["pitch"]=float(self._cam_override_vars["pitch"].get())
            cam["yaw"]  =float(self._cam_override_vars["yaw"].get())
            cam["roll"] =float(self._cam_override_vars["roll"].get())
            cam["zoom"] =float(self._cam_override_vars["zoom"].get())
        if hasattr(self,'_cam_lens_vars'):
            for k,v in self._cam_lens_vars.items():
                cam[k]=float(v.get())
        if hasattr(self,'_cam_fx_vars'):
            for k,v in self._cam_fx_vars.items():
                cam[k]=float(v.get())
        if hasattr(self,'_cam_grade_var'):
            cam["color_grade"]=self._cam_grade_var.get()
        if hasattr(self,'_cam_mirror_var'):
            cam["mirror"]=self._cam_mirror_var.get()
        return cam

    def _on_timeline_scrub(self, force=False):
        t=float(self.timeline_time_var.get());self._timeline_lbl.config(text=f"{t:.2f}s")
        self._draw_camera_track()
        if (self._timeline_internal and not force) or self.disp_np is None:return
        if self.prevOn:
            self.prev_t=t;self.prev_anim_t=t;self.prev_last=time.perf_counter()
            return
        try:
            cam=self._get_cam_with_overrides(t)
            anim_t=t*float(cam.get("time_scale",1.0))
            frame=render_frame(
                self.disp_np,self._disp_regions() if self.regions else [],
                anim_t,1/30.0,self._extra,
                bg_source=self._bg_source,bg_alpha=float(self._bg_alpha_var.get()),bg_mode=self._bg_mode_var.get(),
                fg_source=self._fg_source,fg_alpha=float(self._fg_alpha_var.get()),fg_mode=self._fg_mode_var.get(),
                smoke_enabled=self._smoke_enabled.get(),
                smoke_params=self._get_smoke_params() if self._smoke_enabled.get() else None,
                camera_params=cam,
                       )
            self._draw_preview_frame(frame)
        except Exception:
            self._refresh_canvas()

    def add_region(self):
        if self.static_np is None:messagebox.showinfo("Wave Animator","Open an image first.");return
        H,W=self.disp_np.shape[:2];col=REGION_COLORS[len(self.regions)%len(REGION_COLORS)]
        reg={'mask_disp':np.zeros((H,W),dtype=np.uint8),'freeze_disp':np.zeros((H,W),dtype=np.uint8),
             'anchors':[],'paths':[],'mask_full':None,'anim_type':self.anim_var.get(),
             'params':self._build_params(),'color':col}
        self.regions.append(reg);self.active_reg=len(self.regions)-1
        self.reg_listbox.insert(tk.END,f"Region {len(self.regions)}  [{ANIM_TYPES[reg['anim_type']]}]")
        self.reg_listbox.selection_clear(0,tk.END);self.reg_listbox.selection_set(self.active_reg)
        self._extra.clear();self._d3d_refresh_layers();self._refresh_canvas()

    def delete_region(self):
        if self.active_reg is None:return
        self.regions.pop(self.active_reg);self.reg_listbox.delete(self.active_reg)
        self.active_reg=None if not self.regions else min(self.active_reg,len(self.regions)-1)
        # Clean up orphaned depth layers
        self._depth3d_layers=[l for l in self._depth3d_layers if l.get('region_idx',0)<len(self.regions)]
        self._extra.clear();self._d3d_refresh_layers();self._refresh_canvas()

    def _list_sel(self,e):
        sel=self.reg_listbox.curselection()
        if not sel:return
        self.active_reg=sel[0];reg=self.regions[self.active_reg];self.anim_var.set(reg['anim_type']);self._live_apply_blocked=True
        for k,v in reg['params'].items():
            if k=='cloud_color':self._cloud_color_var.set(v)
            elif k=='sun_color':self._sun_color_var.set(v)
            elif k in self.pvars:self.pvars[k].set(v)
        # ── Restore cinematic zoom params if applicable ───────────────────────
        p=reg['params']
        if reg['anim_type']==35:
            if 'effect'    in p: self._cz_effect_var.set(p['effect'])
            if 'easing'    in p: self._cz_easing_var.set(p['easing'])
            if 'zoom_start'in p: self._cz_zoom_start_var.set(p['zoom_start'])
            if 'zoom_end'  in p: self._cz_zoom_end_var.set(p['zoom_end'])
            if 'fade_black'in p: self._cz_fade_black_var.set(p['fade_black'])
            if 'fade_white'in p: self._cz_fade_white_var.set(p['fade_white'])
            if 'start_x'   in p: self._cz_start_norm=(p['start_x'],p.get('start_y',0.5))
            if 'end_x'     in p: self._cz_end_norm  =(p['end_x'],  p.get('end_y',  0.45))
            sx,sy=self._cz_start_norm;ex,ey=self._cz_end_norm
            self._cz_pt_info.config(text=f"◎ Start ({sx:.2f}, {sy:.2f})   ◉ End ({ex:.2f}, {ey:.2f})")
        self._live_apply_blocked=False;self._update_anim_panels();self._refresh_canvas()

    def _anim_changed(self):
        if self.active_reg is None:return
        self.regions[self.active_reg]['anim_type']=self.anim_var.get();ri=self.active_reg
        for k in list(self._extra.keys()):
            if k[1]==ri:del self._extra[k]
        self._update_listbox_label(ri);self._update_anim_panels()
        self._live_apply()  # immediately save params (including cinzoom keys) to region

    def _live_apply(self):
        if self._live_apply_blocked:return
        if self.active_reg is None or self.active_reg>=len(self.regions):return
        self.regions[self.active_reg]['params']=self._build_params();ri=self.active_reg
        at=self.regions[ri]['anim_type']
        reset_map={9:'leafwind',8:'falling',5:'bokeh',6:'plasma',7:'twinkle',12:'scroll',
                   11:'flowerfall',13:'clouds',14:'rain',15:'sun',16:'float',17:'updown',
                   18:'spinf',19:'asmoke',20:'acloud',21:'afire',22:'wflow',
                   23:'leap_hop',24:'leap_side',25:'leap_pulse',34:'waterfall'}
        if at in reset_map:self._extra.pop((reset_map[at],ri),None)

    def _apply_params(self):
        if self.active_reg is None:return
        self._live_apply();ri=self.active_reg
        for k in list(self._extra.keys()):
            if k[1]==ri:del self._extra[k]

    def _update_listbox_label(self,i):
        reg=self.regions[i];self.reg_listbox.delete(i);self.reg_listbox.insert(i,f"Region {i+1}  [{ANIM_TYPES[reg['anim_type']]}]");self.reg_listbox.selection_set(i)

    def open_image(self):
        path=filedialog.askopenfilename(filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.tiff *.webp"),("All","*.*")])
        if not path:return
        pil=Image.open(path).convert("RGB");self.static_np=np.array(pil)
        self.regions.clear();self.reg_listbox.delete(0,tk.END);self.active_reg=None;self._extra.clear()
        self.camera_keyframes=[{"time":0.0,"preset":"Eye Level","shot":"Static"}];self._refresh_camera_list()
        self._timeline_internal=True;self.timeline_time_var.set(0.0);self._timeline_internal=False;self._timeline_lbl.config(text="0.00s")
        self.zoom_level=1.0;self.pan_x=0;self.pan_y=0
        if self.prevOn:self._stop_preview()
        self.canvas.itemconfig(self._hint,text="");self._refit();self.status_var.set(f"Loaded: {os.path.basename(path)} ({pil.width}×{pil.height})")

    def _refit(self):
        if self.static_np is None:return
        self._build_disp_np();self.zoom_lbl.config(text=f"{int(self.zoom_level*100)}%");self._refresh_canvas()

    def _image_offset(self):
        if self.disp_np is None:return 0,0
        cw=self.canvas.winfo_width() or 800;ch=self.canvas.winfo_height() or 600;dh,dw=self.disp_np.shape[:2]
        return(cw-dw)//2+self.pan_x,(ch-dh)//2+self.pan_y

    def _refresh_canvas(self):
        if self.disp_np is None:return
        base=Image.fromarray(self.disp_np)
        # ── Apply camera transform so camera settings are visible in edit mode ─
        if not self.prevOn:
            try:
                t=float(self.timeline_time_var.get())
                cam=self._get_cam_with_overrides(t)
                base_np=apply_camera_transform(np.array(base),cam)
                base=Image.fromarray(base_np)
            except Exception:
                pass
        # ── Composite foreground layer so it's visible in edit mode ──────
        if self._fg_source is not None:
            dh,dw=self.disp_np.shape[:2]
            fg_frame=self._fg_source.get_frame(0.0,dw,dh)  # RGBA
            fg_pil=Image.fromarray(fg_frame,'RGBA')
            base=Image.alpha_composite(base.convert('RGBA'),fg_pil).convert('RGB')
        # ─────────────────────────────────────────────────────────────────
        for i,reg in enumerate(self.regions):
            r,g,b=reg['color'];m=reg['mask_disp'];ys,xs=np.where(m>128)
            if len(xs)==0:continue
            overlay=np.zeros((*self.disp_np.shape[:2],4),dtype=np.uint8);overlay[ys,xs]=[r,g,b,130 if i==self.active_reg else 80]
            pil_ov=Image.fromarray(overlay,'RGBA');base=Image.alpha_composite(base.convert('RGBA'),pil_ov).convert('RGB')
        self._tk_img=ImageTk.PhotoImage(base);ox,oy=self._image_offset();dh,dw=self.disp_np.shape[:2]
        self.canvas.delete("img");self.canvas.create_image(ox+dw//2,oy+dh//2,anchor=tk.CENTER,image=self._tk_img,tags="img")
        if self.active_reg is not None and self.active_reg < len(self.regions):
            reg=self.regions[self.active_reg]
            fr=reg.get('freeze_disp')
            if fr is not None and np.any(fr>128):
                fy,fx=np.where(fr>128)
                if len(fx):
                    for x,y in zip(fx[::max(1,len(fx)//1800)],fy[::max(1,len(fy)//1800)]):
                        self.canvas.create_rectangle(ox+x,oy+y,ox+x+1,oy+y+1,outline="#89dceb",fill="#89dceb")
            for a in reg.get('anchors',[]):
                cx=ox+int(a['x']);cy=oy+int(a['y'])
                self.canvas.create_oval(cx-5,cy-5,cx+5,cy+5,outline="#f9e2af",width=2)
                self.canvas.create_line(cx-8,cy,cx+8,cy,fill="#f9e2af",width=1)
                self.canvas.create_line(cx,cy-8,cx,cy+8,fill="#f9e2af",width=1)
            for p in reg.get('paths',[]):
                x1=ox+int(p['x1']);y1=oy+int(p['y1']);x2=ox+int(p['x2']);y2=oy+int(p['y2'])
                self.canvas.create_line(x1,y1,x2,y2,fill="#89b4fa",width=3,arrow=tk.LAST,arrowshape=(10,12,4))
            if self._path_start is not None and self.edit_tool=='path':
                x1=ox+int(self._path_start[0]);y1=oy+int(self._path_start[1]);x2=self._path_preview_x;y2=self._path_preview_y
                self.canvas.create_line(x1,y1,x2,y2,fill="#cba6f7",width=2,dash=(4,3),arrow=tk.LAST)
        # ── Cinematic Zoom crosshairs (always show when anim 35 is active) ───
        if (self.active_reg is not None and self.active_reg < len(self.regions)
                and self.regions[self.active_reg]['anim_type']==35):
            self._cz_draw_crosshairs()

    def _set_paint(self,m):
        self.paint_mode=m;self.edit_tool=m
        self.paint_btn.config(bg="#2e4a2e" if m=='paint' else "#1e1e2e",fg="#a6e3a1" if m=='paint' else "#cdd6f4")
        self.erase_btn.config(bg="#2e4a2e" if m=='erase' else "#1e1e2e",fg="#a6e3a1" if m=='erase' else "#cdd6f4")
        self.path_btn.config(bg="#2e4a2e" if m=='path' else "#1e1e2e",fg="#a6e3a1" if m=='path' else "#cdd6f4")
        self.freeze_btn.config(bg="#2e4a2e" if m=='freeze' else "#1e1e2e",fg="#a6e3a1" if m=='freeze' else "#cdd6f4")
        self.anchor_btn.config(bg="#2e4a2e" if m=='anchor' else "#1e1e2e",fg="#a6e3a1" if m=='anchor' else "#cdd6f4")

    def _c2d(self,cx,cy):
        if self.disp_np is None:return 0,0
        ox,oy=self._image_offset();dh,dw=self.disp_np.shape[:2]
        return(max(0,min(dw-1,int(cx-ox))),max(0,min(dh-1,int(cy-oy))))

    def _press(self,e):
        # ── Cinematic Zoom click-to-set start/end point ───────────────────────
        if (self.active_reg is not None and self.active_reg < len(self.regions)
                and self.regions[self.active_reg]['anim_type']==35):
            self._cz_handle_canvas_click(e.x,e.y);return
        if self.disp_np is None or self.active_reg is None:return
        ix,iy=self._c2d(e.x,e.y);reg=self.regions[self.active_reg]
        if self.edit_tool=='anchor':
            reg.setdefault('anchors',[]).append({'x':float(ix),'y':float(iy)});self._refresh_canvas();return
        if self.edit_tool=='path':
            self._path_start=(float(ix),float(iy));self._path_preview_x=e.x;self._path_preview_y=e.y;self._refresh_canvas();return
        self.painting=True;self._do_brush(e.x,e.y)
    def _drag(self,e):
        if self.edit_tool=='path' and self._path_start is not None:
            self._path_preview_x=e.x;self._path_preview_y=e.y;self._refresh_canvas();return
        if self.painting:self._do_brush(e.x,e.y)
    def _release(self,e):
        if self.edit_tool=='path' and self._path_start is not None and self.active_reg is not None:
            ix,iy=self._c2d(e.x,e.y);sx,sy=self._path_start
            if math.hypot(ix-sx,iy-sy)>=6.0:
                self.regions[self.active_reg].setdefault('paths',[]).append({'x1':float(sx),'y1':float(sy),'x2':float(ix),'y2':float(iy)})
            self._path_start=None;self._refresh_canvas();return
        self.painting=False
        if self.active_reg is not None:
            reg=self.regions[self.active_reg];cnt=int(np.sum(reg['mask_disp']>128));self.status_var.set(f"Region {self.active_reg+1}: {cnt:,} px painted")
        self._refresh_canvas()

    def _do_brush(self,cx,cy):
        if self.active_reg is None:return
        reg=self.regions[self.active_reg];ix,iy=self._c2d(cx,cy);r=self.brush_var.get()//2
        H,W=reg['mask_disp'].shape;x0,y0=max(0,ix-r),max(0,iy-r);x1,y1=min(W-1,ix+r),min(H-1,iy+r)
        ys,xs=np.ogrid[y0:y1+1,x0:x1+1];circle=(xs-ix)**2+(ys-iy)**2<=r**2
        if self.paint_mode=='paint':reg['mask_disp'][y0:y1+1,x0:x1+1][circle]=255
        elif self.paint_mode=='erase':reg['mask_disp'][y0:y1+1,x0:x1+1][circle]=0
        elif self.paint_mode=='freeze':reg['freeze_disp'][y0:y1+1,x0:x1+1][circle]=255

    def clear_paint(self):
        if self.active_reg is None:return
        self.regions[self.active_reg]['mask_disp'][:]=0;ri=self.active_reg
        for k in list(self._extra.keys()):
            if k[1]==ri:del self._extra[k]
        self._refresh_canvas()

    def clear_motion(self):
        if self.active_reg is None:return
        reg=self.regions[self.active_reg]
        reg['freeze_disp'][:]=0;reg['anchors']=[];reg['paths']=[]
        ri=self.active_reg
        for k in list(self._extra.keys()):
            if len(k)>1 and k[1]==ri:del self._extra[k]
        self._refresh_canvas()

    def toggle_preview(self):
        if self.static_np is None:messagebox.showinfo("Wave Animator","Open an image first.");return
        if self.prevOn:self._stop_preview()
        else:self._start_preview()

    def _start_preview(self):
        self.prevOn=True;self.prev_t=float(self.timeline_time_var.get());self.prev_anim_t=self.prev_t;self.prev_last=time.perf_counter()
        self.btn_prev.config(text="Stop",bg="#2e4a2e",fg="#a6e3a1");self.status_var.set("Previewing...");self._extra.clear();self._prev_tick()

    def _stop_preview(self):
        self.prevOn=False
        if self._after_id:self.after_cancel(self._after_id);self._after_id=None
        self.btn_prev.config(text="▶ Preview",bg="#1e1e2e",fg="#cdd6f4");self._refresh_canvas()

    def _disp_regions(self):
        dur=max(1.0,float(self.pvars["duration"].get()))
        result=[]
        for reg in self.regions:
            p=reg['params']
            if reg['anim_type']==35:
                p=dict(p);p['duration']=dur   # inject live duration for cinzoom
            result.append({'mask':reg['mask_disp'],'freeze_mask':reg.get('freeze_disp'),'anchors':reg.get('anchors',[]),
                           'paths':reg.get('paths',[]),'anim_type':reg['anim_type'],'params':p,'static_np':self.disp_np})
        return result

    def _prev_tick(self):
        if not self.prevOn:return
        now=time.perf_counter();dt=now-self.prev_last;self.prev_t+=dt;self.prev_last=now
        dur=max(1.0,float(self.pvars["duration"].get()))
        if self.prev_t>dur:self.prev_t=math.fmod(self.prev_t,dur)
        self._timeline_internal=True;self.timeline_time_var.set(self.prev_t);self._timeline_internal=False
        self._timeline_lbl.config(text=f"{self.prev_t:.2f}s")
        try:
            cam=self._get_cam_with_overrides(self.prev_t)
            anim_dt=dt*float(cam.get("time_scale",1.0))
            self.prev_anim_t+=anim_dt
            frame=render_frame(
                self.disp_np,
                self._disp_regions() if self.regions else [],
                self.prev_anim_t,anim_dt,self._extra,
                bg_source=self._bg_source,bg_alpha=float(self._bg_alpha_var.get()),bg_mode=self._bg_mode_var.get(),
                fg_source=self._fg_source,fg_alpha=float(self._fg_alpha_var.get()),fg_mode=self._fg_mode_var.get(),
                smoke_enabled=self._smoke_enabled.get(),
                smoke_params=self._get_smoke_params() if self._smoke_enabled.get() else None,
                camera_params=cam,
                depth3d_params=self._get_depth3d_params() if self._depth3d_enabled.get() else None,
                depth3d_layers=self._get_depth3d_layers_for_render(self.static_np, self.disp_np, self._extra, self.prev_anim_t, anim_dt) if self._depth3d_enabled.get() else None,
            )
            self._draw_preview_frame(frame)
        except Exception as ex:
            self.status_var.set(f"Preview error: {ex}");self.prevOn=False;return
        self._after_id=self.after(33,self._prev_tick)

    def export_video(self):
        if self.static_np is None:
            messagebox.showinfo("Wave Animator","Open an image first.");return
        out=filedialog.asksaveasfilename(defaultextension=".mp4",filetypes=[("MP4","*.mp4"),("AVI","*.avi")],initialfile="wave_animation_9x16.mp4")
        if not out:return
        if self.prevOn:self._stop_preview()
        duration=int(self.pvars["duration"].get());fps_val=int(self.pvars["fps"].get());total=duration*fps_val
        n_workers=min(os.cpu_count() or 2,8)
        src_H,src_W=self.static_np.shape[:2]
        full_regions=[]
        disp_H,disp_W=self.disp_np.shape[:2]
        for reg in self.regions:
            mf=cv2.resize(reg['mask_disp'],(src_W,src_H),interpolation=cv2.INTER_NEAREST)
            ff=cv2.resize(reg.get('freeze_disp',np.zeros_like(reg['mask_disp'])),(src_W,src_H),interpolation=cv2.INTER_NEAREST)
            sx=src_W/max(1,disp_W);sy=src_H/max(1,disp_H)
            anchors=[{'x':a['x']*sx,'y':a['y']*sy} for a in reg.get('anchors',[])]
            paths=[{'x1':p['x1']*sx,'y1':p['y1']*sy,'x2':p['x2']*sx,'y2':p['y2']*sy} for p in reg.get('paths',[])]
            full_regions.append({'mask':mf,'freeze_mask':ff,'anchors':anchors,'paths':paths,'anim_type':reg['anim_type'],'params':reg['params'],'static_np':self.static_np})
        bg_src=self._bg_source;bg_alpha=float(self._bg_alpha_var.get());bg_mode=self._bg_mode_var.get()
        fg_src=self._fg_source;fg_alpha=float(self._fg_alpha_var.get());fg_mode=self._fg_mode_var.get()
        smoke_enabled=self._smoke_enabled.get();smoke_params=self._get_smoke_params() if smoke_enabled else None
        prog=tk.Toplevel(self);prog.title("Exporting 1080×1920...");prog.configure(bg="#0d0d12");prog.geometry("480x170");prog.grab_set()
        tk.Label(prog,text=f"Rendering {total} frames → fill-scaled to {EXPORT_W}×{EXPORT_H}",bg="#0d0d12",fg="#cdd6f4",font=("Courier New",10)).pack(pady=8)
        bar=ttk.Progressbar(prog,maximum=total,length=440);bar.pack(pady=4)
        plbl=tk.Label(prog,text="0/"+str(total),bg="#0d0d12",fg="#585b70",font=("Courier New",9));plbl.pack()
        slbl=tk.Label(prog,text="Rendering...",bg="#0d0d12",fg="#89b4fa",font=("Courier New",9));slbl.pack()
        prog.update()
        static_snap=self.static_np.copy();results=[None]*total;done_count=[0];lock=threading.Lock();t0=[time.perf_counter()]
        def ui_update(done,total):
            if not prog.winfo_exists():return
            el=time.perf_counter()-t0[0];fr=done/el if el>0 else 0;eta=(total-done)/fr if fr>0 else 0
            bar["value"]=done;plbl.config(text=f"{done}/{total}  |  {fr:.1f} fps  |  ETA {eta:.0f}s");prog.update_idletasks()
        def do_export():
            stateful={4,5,7,8,9,13,14,15,16,17,18,19,20,21,22,23,24,25,29,33,34,35,36,37};has_stateful=any(r['anim_type'] in stateful for r in full_regions)
            # Inject export duration into any cinzoom (anim 35) region params
            for r in full_regions:
                if r['anim_type']==35:
                    r['params']=dict(r['params']);r['params']['duration']=float(duration)
            has_video_layer=(bg_src and bg_src.is_video) or (fg_src and fg_src.is_video);has_smoke=smoke_enabled
            has_director_effect=any(k.get("shot","Static")!="Static" for k in self.camera_keyframes)
            has_depth3d=self._depth3d_enabled.get() and bool(self._depth3d_layers)
            d3d_params=self._get_depth3d_params() if has_depth3d else None
            if has_stateful or has_video_layer or has_smoke or has_director_effect or has_depth3d:
                local_extra={};prev_t=0.0;anim_clock=0.0
                for i in range(total):
                    t2=i/fps_val;dt=t2-prev_t;prev_t=t2
                    cam=resolve_camera_director(self.camera_keyframes,t2)
                    anim_dt=dt*float(cam.get("time_scale",1.0));anim_clock+=anim_dt
                    d3d_layers=self._get_depth3d_layers_for_render(static_snap,static_snap,local_extra,anim_clock,anim_dt) if has_depth3d else None
                    frame=render_frame(static_snap,full_regions,anim_clock,anim_dt,local_extra,bg_source=bg_src,bg_alpha=bg_alpha,bg_mode=bg_mode,fg_source=fg_src,fg_alpha=fg_alpha,fg_mode=fg_mode,smoke_enabled=smoke_enabled,smoke_params=smoke_params,camera_params=cam,depth3d_params=d3d_params,depth3d_layers=d3d_layers)
                    results[i]=cv2.cvtColor(letterbox_to(frame,EXPORT_W,EXPORT_H),cv2.COLOR_RGB2BGR)
                    done_count[0]+=1;self.after(0,ui_update,done_count[0],total)
            else:
                def job(i):
                    t2=i/fps_val
                    cam=resolve_camera_director(self.camera_keyframes,t2)
                    frame=render_frame(static_snap,full_regions,t2,1/fps_val,{},bg_source=bg_src,bg_alpha=bg_alpha,bg_mode=bg_mode,fg_source=fg_src,fg_alpha=fg_alpha,fg_mode=fg_mode,smoke_enabled=smoke_enabled,smoke_params=smoke_params,camera_params=cam)
                    return i,cv2.cvtColor(letterbox_to(frame,EXPORT_W,EXPORT_H),cv2.COLOR_RGB2BGR)
                with ThreadPoolExecutor(max_workers=n_workers) as ex:
                    futures={ex.submit(job,i):i for i in range(total)}
                    for f in as_completed(futures):
                        i,bgr=f.result();results[i]=bgr
                        with lock:done_count[0]+=1;self.after(0,ui_update,done_count[0],total)
            self.after(0,lambda:slbl.config(text=f"Writing {EXPORT_W}×{EXPORT_H} video..."))
            fourcc=cv2.VideoWriter_fourcc(*"mp4v");writer=cv2.VideoWriter(out,fourcc,fps_val,(EXPORT_W,EXPORT_H))
            for bgr in results:writer.write(bgr)
            writer.release();self.after(0,finish)
        def finish():
            if prog.winfo_exists():prog.destroy()
            self.status_var.set(f"Exported {EXPORT_W}×{EXPORT_H} → {out}")
            messagebox.showinfo("Done!",f"Video saved ({EXPORT_W}×{EXPORT_H} 9:16):\n{out}")
        threading.Thread(target=do_export,daemon=True).start()


if __name__=="__main__":
    App().mainloop()