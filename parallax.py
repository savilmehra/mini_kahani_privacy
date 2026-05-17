"""
cylinder_app.py  —  Cylinder Panorama Video Renderer  (Enhanced)
=================================================================
New features vs original
------------------------
  ✦ Speed control        – rotation speed multiplier slider
  ✦ Seamless edges       – blend-wrap the texture so left≡right
  ✦ Multiple images      – pick N images; they are stitched side-by-side
  ✦ Auto cylinder radius – derived from total image width (toggle)
  ✦ Camera distance      – independent "how far from the cylinder wall" slider

Requirements
------------
    pip install moderngl numpy Pillow imageio imageio-ffmpeg

Run
---
    python3 cylinder_app.py
"""

import math
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import imageio
import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULTS = dict(
    width=1080, height=1920,
    fps=30, duration=10,
    segments=128,
    cyl_radius=100.0, cyl_height=55.0,  # overridden by _compute_geometry at render time
    cam_y=0.0,
    cam_distance=0.5,       # orbit radius: small=subtle parallax, large=more motion
    fov=60.0,               # narrower FOV = natural perspective, less distortion
    speed=0.5,              # rotations per video: 1.0=full 360, 0.25=very slow drift
    blend_width=0.04,       # seamless edge blend (fraction of width, 0=off)
)

AUTO_RADIUS = False         # manual geometry by default for predictable framing

# ── Colours & fonts ───────────────────────────────────────────────────────────
BG       = "#0d0d0f"
PANEL    = "#15151a"
ACCENT   = "#c8922a"
ACCENT2  = "#e8b84b"
TEXT     = "#f0ead6"
SUBTEXT  = "#7a7068"
BTN_RDR  = "#c8922a"
BTN_HOV  = "#e8b84b"
ENTRY_BG = "#1e1e26"
BORDER   = "#2a2820"

FONT_HEAD = ("Georgia", 18, "bold")
FONT_SUB  = ("Georgia", 10, "italic")
FONT_LBL  = ("Courier", 10)
FONT_VAL  = ("Courier", 10, "bold")
FONT_BTN  = ("Georgia", 12, "bold")
FONT_LOG  = ("Courier", 9)


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def stitch_images(paths: list[str]) -> Image.Image:
    """Open and horizontally stitch all images to the same height."""
    imgs = [Image.open(p).convert("RGB") for p in paths]
    # Normalise heights
    target_h = max(im.height for im in imgs)
    resized  = []
    for im in imgs:
        if im.height != target_h:
            w2 = int(im.width * target_h / im.height)
            im = im.resize((w2, target_h), Image.LANCZOS)
        resized.append(im)
    total_w = sum(im.width for im in resized)
    canvas  = Image.new("RGB", (total_w, target_h))
    x = 0
    for im in resized:
        canvas.paste(im, (x, 0))
        x += im.width
    return canvas


def seamless_blend(img: Image.Image, blend_frac: float) -> Image.Image:
    """
    Blend the left and right edges so the texture wraps seamlessly.
    blend_frac: fraction of width used for the crossfade (e.g. 0.04 = 4 %).
    """
    if blend_frac <= 0:
        return img
    W, H   = img.size
    bw     = max(1, int(W * blend_frac))
    arr    = np.array(img, dtype=np.float32)

    # Ramp: 0→1 over `bw` pixels
    ramp = np.linspace(0.0, 1.0, bw, dtype=np.float32)

    # Left strip (columns 0..bw-1)  blended with right strip (W-bw..W-1)
    left_strip  = arr[:, :bw, :]           # what is currently at the left
    right_strip = arr[:, W-bw:, :]         # what is currently at the right

    # At col 0: fully right; at col bw-1: fully left  → smooth wrap
    alpha = ramp[np.newaxis, :, np.newaxis]          # shape (1, bw, 1)
    blended_left  = right_strip * (1 - alpha) + left_strip  * alpha
    blended_right = left_strip  * (1 - alpha) + right_strip * alpha

    arr[:, :bw, :]    = blended_left
    arr[:, W-bw:, :] = blended_right

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def auto_geometry_from_image(img: Image.Image, fov_deg: float = 90.0,
                              vid_w: int = 1080, vid_h: int = 1920):
    """
    Derive cylinder radius, height and cam_distance so the image fills the
    frame and looks like its actual size (not zoomed in).

    Key insight
    -----------
    For 90° hfov the camera always sees hfov/360 = 25% of the panorama width.
    To see the image at natural scale:
      • Camera sits near the CENTER of the cylinder (large cam_distance ≈ 0.95·R)
      • Cylinder height H is set so the image fills the frame vertically:
            H = 2 · cam_distance · tan(vfov/2)
      • Cylinder radius R is generous (fixed at 5.0) — the orbit radius
            CR = R − cam_distance is tiny, giving a gentle parallax pan.

    As the camera slowly orbits it reveals more of the panorama horizontally
    while the image always fills the frame — natural, unzoomed feel.
    """
    R        = 5.0                               # fixed, generous cylinder
    half_hfov = math.radians(fov_deg / 2)
    vid_aspect = vid_w / vid_h                   # e.g. 0.5625 for 1080×1920
    half_vfov  = math.atan(math.tan(half_hfov) / vid_aspect)

    # Camera sits 95 % of the way to the wall from center
    # → gap (camera-to-wall distance) = 0.95 · R
    gap      = R * 0.95
    cam_dist = gap                               # cam_distance = gap from wall

    # Cylinder height = what the camera sees vertically at this gap
    H        = 2.0 * gap * math.tan(half_vfov)

    return R, H, cam_dist


# ══════════════════════════════════════════════════════════════════════════════
#  3-D RENDERER
# ══════════════════════════════════════════════════════════════════════════════

VERT = """
#version 330 core
in vec3 in_position;
in vec2 in_uv;
uniform mat4 mvp;
out vec2 v_uv;
void main() {
    gl_Position = mvp * vec4(in_position, 1.0);
    v_uv = in_uv;
}
"""

FRAG = """
#version 330 core
in vec2 v_uv;
uniform sampler2D tex;
out vec4 out_color;
void main() {
    out_color = vec4(texture(tex, v_uv).rgb, 1.0);
}
"""


def _build_cylinder(radius, height, segs):
    """Build a full 360-degree cylinder. UVs go 0..1 around full circumference
    and 0..1 top-to-bottom. Caller controls what portion of the image is visible
    via the camera FOV and cylinder geometry."""
    verts, idxs = [], []
    half_h = height / 2
    for i in range(segs):
        a0 = 2 * math.pi * i / segs
        a1 = 2 * math.pi * (i + 1) / segs
        x0, z0 = radius * math.cos(a0), radius * math.sin(a0)
        x1, z1 = radius * math.cos(a1), radius * math.sin(a1)
        u0, u1 = i / segs, (i + 1) / segs
        b = len(verts) // 5
        verts += [x0, -half_h, z0, u0, 1.0,
                  x1, -half_h, z1, u1, 1.0,
                  x1,  half_h, z1, u1, 0.0,
                  x0,  half_h, z0, u0, 0.0]
        idxs  += [b, b+1, b+2, b, b+2, b+3]
    return np.array(verts, dtype='f4'), np.array(idxs, dtype='i4')


def _compute_geometry(fov_deg, vid_w, vid_h, img_w, img_h, orbit_r=0.5):
    """
    Compute cylinder geometry so the image displays at TRUE 1:1 size —
    same width and height as the source, no zoom, no stretch.

    Strategy:
      - Use a large cylinder (R=100) so camera sits near the wall.
      - cam_dist = R - orbit_r  (camera orbits at small radius for parallax)
      - The camera FOV covers a certain arc of the cylinder wall.
      - We size the cylinder height so the image fills the frame vertically.
      - Horizontal: image wraps around the full 360 deg cylinder.
        The visible arc at any moment = fov_deg of the full circumference.
        So the image is NOT zoomed — camera pans across it naturally.
      - Key: cyl_height / (2*pi*R) == img_h / img_w  (same aspect ratio as image)
        This ensures pixels are square on the cylinder — no stretch.
    """
    R        = 100.0
    cam_dist = R - orbit_r          # distance from camera to wall
    half_hfov = math.radians(fov_deg / 2)
    vid_aspect = vid_w / vid_h
    half_vfov  = math.atan(math.tan(half_hfov) / vid_aspect)

    # Cylinder height: match image aspect ratio relative to circumference
    # circumference = 2*pi*R; height = circumference * (img_h / img_w)
    cyl_h = 2 * math.pi * R * (img_h / img_w)

    return R, cyl_h, cam_dist


def _perspective(fov_deg, aspect, near, far):
    f  = 1.0 / math.tan(math.radians(fov_deg) / 2)
    nf = 1.0 / (near - far)
    return np.array([
        [f/aspect, 0, 0,              0            ],
        [0,        f, 0,              0            ],
        [0,        0, (far+near)*nf,  2*far*near*nf],
        [0,        0, -1,             0            ],
    ], dtype='f4')


def _look_at(eye, center, up):
    f = center - eye;  f /= np.linalg.norm(f)
    s = np.cross(f, up); s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4, dtype='f4')
    m[0,:3]=s; m[1,:3]=u; m[2,:3]=-f
    m[0,3]=-np.dot(s,eye); m[1,3]=-np.dot(u,eye); m[2,3]=np.dot(f,eye)
    return m


def _load_texture(ctx, image_paths: list[str], blend_frac: float,
                  auto_radius: bool, cfg: dict,
                  vid_w: int = 1080, vid_h: int = 1920):
    """
    Stitch images, apply seamless blend, upload to GPU.
    Returns (tex, cyl_radius, cyl_height, cam_distance, stitched_img).
    When auto_radius=True all three geometry values are derived from the image.
    """
    img = stitch_images(image_paths)
    img = seamless_blend(img, blend_frac)

    if auto_radius:
        radius, cyl_h, cam_d = auto_geometry_from_image(
            img, fov_deg=cfg['fov'], vid_w=vid_w, vid_h=vid_h)
    else:
        radius = cfg['cyl_radius']
        cyl_h  = cfg['cyl_height']
        cam_d  = cfg['cam_distance']

    tex    = ctx.texture(img.size, 3, img.tobytes())
    tex.filter   = (moderngl.LINEAR, moderngl.LINEAR)
    tex.repeat_x = True
    tex.repeat_y = False  # no vertical tiling; out-of-range UV = black border
    return tex, radius, cyl_h, cam_d, img


def render_video(image_paths, output_path, cfg, auto_radius=False,
                 progress_cb=None, log_cb=None):
    """Run the full render."""
    W, H      = cfg['width'], cfg['height']
    FPS       = cfg['fps']
    SEGS      = cfg['segments']
    CY        = cfg['cam_y']
    FOV       = cfg['fov']
    DUR       = cfg['duration']
    SPEED     = cfg['speed']
    BLEND     = cfg['blend_width']
    NEAR, FAR = 0.05, 20.0
    # CH (cyl_height) and CAM_DIST are set by _load_texture (auto or from cfg)

    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.DEPTH_TEST)

    prog = ctx.program(vertex_shader=VERT, fragment_shader=FRAG)

    tex, R, CH, CAM_DIST, stitched = _load_texture(ctx, image_paths, BLEND, auto_radius, cfg, vid_w=W, vid_h=H)

    # Override geometry with true-size 1:1 mapping (no zoom, no stretch)
    _img_w, _img_h = stitched.size
    ORBIT_R = cfg.get('cam_distance', 0.5)  # cam_distance now = orbit radius for parallax
    R, CH, CAM_DIST = _compute_geometry(FOV, W, H, _img_w, _img_h, orbit_r=ORBIT_R)
    CR = ORBIT_R

    if log_cb:
        log_cb(f"Cylinder R={R:.1f} H={CH:.1f} cam_dist={CAM_DIST:.1f} orbit={ORBIT_R:.2f} img={_img_w}x{_img_h}")

    verts, idxs = _build_cylinder(R, CH, SEGS)
    vbo = ctx.buffer(verts.tobytes())
    ibo = ctx.buffer(idxs.tobytes())
    vao = ctx.vertex_array(prog, [(vbo, '3f 2f', 'in_position', 'in_uv')], ibo)

    tex.use(0); prog['tex'].value = 0

    fbo = ctx.framebuffer(
        color_attachments=[ctx.texture((W, H), 4)],
        depth_attachment=ctx.depth_renderbuffer((W, H)),
    )
    fbo.use()
    ctx.viewport = (0, 0, W, H)

    proj  = _perspective(FOV, W/H, NEAR, FAR)
    model = np.eye(4, dtype='f4')

    total = FPS * DUR
    writer = imageio.get_writer(output_path, fps=FPS, codec='libx264',
                                quality=8, output_params=['-pix_fmt', 'yuv420p'])

    if log_cb: log_cb(f"Rendering {total} frames…")

    for fi in range(total):
        # SPEED = rotations over entire video; 0.25=slow drift, 1.0=full 360
        ang = 2 * math.pi * SPEED * fi / total
        eye = np.array([CR*math.cos(ang), CY, CR*math.sin(ang)], dtype='f4')
        tgt = np.array([R *math.cos(ang), CY, R *math.sin(ang)], dtype='f4')
        up  = np.array([0, 1, 0], dtype='f4')

        view = _look_at(eye, tgt, up)
        mvp  = (proj @ view @ model).astype('f4')
        prog['mvp'].write(mvp.T.tobytes())

        ctx.clear(0.0, 0.0, 0.0, 1.0)
        vao.render()

        raw = fbo.read(components=4)
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((H, W, 4))
        writer.append_data(arr[::-1, :, :3])

        if progress_cb: progress_cb((fi+1)/total)
        if log_cb and fi % FPS == 0:
            log_cb(f"  frame {fi+1}/{total}  ({int((fi+1)/total*100)}%)")

    writer.close()
    ctx.release()
    if log_cb: log_cb(f"✓ Saved → {output_path}")


def make_preview_frame(image_paths, cfg, auto_radius=False):
    """Render a single frame at t=0.25 for the preview thumbnail."""
    W, H      = 480, 270
    SEGS      = cfg['segments']
    CY        = cfg['cam_y']
    FOV       = cfg['fov']
    BLEND     = cfg['blend_width']
    NEAR, FAR = 0.05, 20.0

    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.DEPTH_TEST)
    prog = ctx.program(vertex_shader=VERT, fragment_shader=FRAG)

    tex, R, CH, CAM_DIST, stitched_p = _load_texture(ctx, image_paths, BLEND, auto_radius, cfg, vid_w=W, vid_h=H)
    _img_w, _img_h = stitched_p.size
    ORBIT_R = cfg.get('cam_distance', 0.5)
    R, CH, CAM_DIST = _compute_geometry(FOV, W, H, _img_w, _img_h, orbit_r=ORBIT_R)
    CR = ORBIT_R
    verts, idxs = _build_cylinder(R, CH, SEGS)
    vbo = ctx.buffer(verts.tobytes())
    ibo = ctx.buffer(idxs.tobytes())
    vao = ctx.vertex_array(prog, [(vbo, '3f 2f', 'in_position', 'in_uv')], ibo)
    tex.use(0); prog['tex'].value = 0

    fbo = ctx.framebuffer(
        color_attachments=[ctx.texture((W, H), 4)],
        depth_attachment=ctx.depth_renderbuffer((W, H)),
    )
    fbo.use()
    ctx.viewport = (0, 0, W, H)

    proj  = _perspective(FOV, W/H, NEAR, FAR)
    model = np.eye(4, dtype='f4')

    t   = 0.25
    ang = 2 * math.pi * t
    eye = np.array([CR*math.cos(ang), CY, CR*math.sin(ang)], dtype='f4')
    tgt = np.array([R *math.cos(ang), CY, R *math.sin(ang)], dtype='f4')
    up  = np.array([0, 1, 0], dtype='f4')

    view = _look_at(eye, tgt, up)
    mvp  = (proj @ view @ model).astype('f4')
    prog['mvp'].write(mvp.T.tobytes())
    ctx.clear(0, 0, 0, 1)
    vao.render()

    raw = fbo.read(components=4)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape((H, W, 4))
    result = Image.fromarray(arr[::-1, :, :3])
    ctx.release()
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cylinder Panorama Renderer  ✦  Enhanced")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 600)

        self.image_paths = []               # list of selected image paths
        self.output_path = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "cylinder_orbit.mp4"))
        self.cfg         = {k: tk.DoubleVar(value=v) for k, v in DEFAULTS.items()}
        self.auto_radius = tk.BooleanVar(value=AUTO_RADIUS)
        self._rendering  = False
        self._preview_img = None

        self._build_ui()
        self._bind_mousewheel_recursive()
        self._center()

    # ── Scrollable panel helper ──────────────────────────────────────────────
    def _make_scroll_panel(self, parent, side, fill, expand=False, padx=0):
        """Return (outer_frame, inner_frame). inner_frame is scrollable."""
        outer = tk.Frame(parent, bg=BG)
        outer.pack(side=side, fill=fill, expand=expand, padx=padx)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0,
                           bd=0, relief='flat')
        sb = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)

        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        inner.bind('<Configure>', _on_frame_configure)

        def _on_canvas_configure(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind('<Configure>', _on_canvas_configure)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        def _on_mousewheel_linux(e, direction):
            canvas.yview_scroll(direction, 'units')

        for widget in (canvas, inner):
            widget.bind('<MouseWheel>', _on_mousewheel)          # Win/Mac
            widget.bind('<Button-4>',  lambda e: _on_mousewheel_linux(e, -1))  # Linux
            widget.bind('<Button-5>',  lambda e: _on_mousewheel_linux(e,  1))  # Linux

        return outer, inner, canvas

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Fixed header (not scrollable) ─────────────────────────────────────
        hdr = tk.Frame(self, bg=BG, pady=18)
        hdr.pack(fill='x', padx=30)
        tk.Label(hdr, text="⬡  CYLINDER PANORAMA", font=FONT_HEAD,
                 bg=BG, fg=ACCENT2).pack(side='left')
        tk.Label(hdr, text="  interior orbit renderer  ✦  enhanced",
                 font=FONT_SUB, bg=BG, fg=SUBTEXT).pack(side='left', pady=6)

        tk.Frame(self, bg=ACCENT, height=1).pack(fill='x', padx=30)

        # ── Scrollable body (fills all space between header and log) ──────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True, padx=10, pady=(10, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        _, left,  _ = self._make_scroll_panel(body, 'left',  'both', expand=True, padx=(20,0))
        _, right, _ = self._make_scroll_panel(body, 'right', 'both', expand=True, padx=(0,20))

        # ── Image picker (left) ───────────────────────────────────────────────
        self._section(left, "SOURCE IMAGES  (one or more)")
        pick_row = tk.Frame(left, bg=BG)
        pick_row.pack(fill='x', pady=(0,6))

        self._drop_zone = tk.Label(
            pick_row,
            text="◻  Click to pick image(s)\n(JPG / PNG / WEBP — select multiple for panorama)",
            font=FONT_LOG, bg=ENTRY_BG, fg=SUBTEXT,
            relief='flat', width=46, height=5,
            cursor='hand2'
        )
        self._drop_zone.pack(fill='x')
        self._drop_zone.bind("<Button-1>", lambda e: self._pick_images())

        # image list display
        self._img_list_lbl = tk.Label(left, text="No images selected.",
                                      font=FONT_LOG, bg=BG, fg=SUBTEXT,
                                      anchor='w', justify='left', wraplength=460)
        self._img_list_lbl.pack(fill='x', pady=(2,8))

        # Clear button
        clear_row = tk.Frame(left, bg=BG)
        clear_row.pack(fill='x', pady=(0,8))
        self._btn(clear_row, "✕  Clear Images", self._clear_images).pack(side='left')

        # Preview
        self._section(left, "3-D PREVIEW")
        self._canvas = tk.Canvas(left, height=270,
                                 bg="#080808", highlightthickness=0)
        self._canvas.pack(fill='x', pady=(0,4))
        self._canvas.create_text(240, 135, text="pick an image to preview",
                                 fill=SUBTEXT, font=FONT_LOG, tags='hint')

        # Preview refresh button
        preview_row = tk.Frame(left, bg=BG)
        preview_row.pack(fill='x', pady=(4, 8))
        self._preview_btn = self._btn(preview_row, "⟳  Refresh Preview", self._refresh_preview)
        self._preview_btn.pack(side='left')

        # Output path
        self._section(left, "OUTPUT FILE")
        out_row = tk.Frame(left, bg=BG)
        out_row.pack(fill='x', pady=(0,14))
        tk.Entry(out_row, textvariable=self.output_path, bg=ENTRY_BG,
                 fg=TEXT, insertbackground=ACCENT2,
                 relief='flat', font=FONT_LOG, width=44).pack(side='left', padx=(0,8), ipady=6)
        self._btn(out_row, "Browse", self._pick_output).pack(side='left')

        # ── Settings (right) ─────────────────────────────────────────────────
        self._section(right, "RENDER SETTINGS")
        self._sliders = {}

        slider_defs = [
            ("Resolution",   None,           None, None),
            ("  Width",      'width',         360,  3840),
            ("  Height",     'height',        360,  2160),
            ("Timing",       None,           None, None),
            ("  Duration",   'duration',      2,    30),
            ("  FPS",        'fps',           15,   60),
            ("  Speed ×rev", 'speed',         0.05, 3.0),  # rotations over video duration
            ("Geometry",     None,           None, None),
            ("  Cyl Radius", 'cyl_radius',   0.5,  20.0),
            ("  Cyl Height", 'cyl_height',   0.5,  50.0),
            ("  Segments",   'segments',     32,   256),
            ("Camera",       None,           None, None),
            ("  Orbit Radius",'cam_distance', 0.05, 99.95),  # repurposed: orbit radius
            ("  Cam Y",      'cam_y',        -1.5, 1.5),
            ("  FOV",        'fov',          40,   150),
            ("Texture",      None,           None, None),
            ("  Edge Blend", 'blend_width',  0.0,  0.25),   # NEW
        ]

        for label, key, lo, hi in slider_defs:
            if key is None:
                tk.Label(right, text=label, font=("Courier",9,"bold"),
                         bg=BG, fg=ACCENT, anchor='w').pack(fill='x', pady=(10,2))
                continue
            row = tk.Frame(right, bg=BG)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=label, font=FONT_LBL,
                     bg=BG, fg=TEXT, width=16, anchor='w').pack(side='left')

            # cam_distance: text entry only, no slider, no limit
            if key == 'cam_distance':
                val_lbl = tk.Label(row, font=FONT_VAL, bg=BG, fg=ACCENT2, width=0)
                val_lbl.pack(side='right')  # hidden, kept for _update compat
                entry_frame = tk.Frame(row, bg=ACCENT, padx=1, pady=1)
                entry_frame.pack(side='right', padx=(0, 4))
                entry = tk.Entry(entry_frame,
                                 font=("Courier", 11, "bold"),
                                 bg="#2a2820", fg=ACCENT2,
                                 insertbackground=ACCENT2,
                                 relief='flat', width=10, justify='center',
                                 highlightthickness=0)
                entry.insert(0, f"{self.cfg[key].get():.4f}")
                entry.pack()

                def _cam_commit(event=None, var=self.cfg[key], e=entry):
                    try:
                        var.set(float(e.get()))
                    except ValueError:
                        e.delete(0, 'end')
                        e.insert(0, f"{var.get():.4f}")

                entry.bind('<Return>', _cam_commit)
                entry.bind('<FocusOut>', _cam_commit)
                sl = None  # no slider
            else:
                val_lbl = tk.Label(row, font=FONT_VAL, bg=BG, fg=ACCENT2, width=6)
                val_lbl.pack(side='right')
                sl = ttk.Scale(row, from_=lo, to=hi, variable=self.cfg[key],
                               orient='horizontal', length=150)
                sl.pack(side='right', padx=4)

            def _update(*args, vl=val_lbl, vr=self.cfg[key], k=key):
                v = vr.get()
                if k in ('width','height','fps','segments','duration'):
                    vl.config(text=f"{int(v)}")
                    if v != int(v): vr.set(int(v))
                elif k == 'speed':
                    # Show rotations label: e.g. 0.25x, 0.5x, 1.0x=full 360
                    if v <= 0.1:
                        desc = "crawl"
                    elif v <= 0.3:
                        desc = "slow"
                    elif v <= 0.6:
                        desc = "drift"
                    elif v <= 1.0:
                        desc = "1 rev"
                    elif v <= 2.0:
                        desc = "fast"
                    else:
                        desc = "rapid"
                    vl.config(text=f"{v:.2f}x")
                else:
                    vl.config(text=f"{v:.2f}")
            self.cfg[key].trace_add('write', _update)
            _update(None)
            self._sliders[key] = sl

        # Speed hint label
        self._speed_hint = tk.Label(right,
            text="  ↳ Speed = rotations over video  (0.05=crawl · 0.5=drift · 1.0=full 360°)",
            font=("Courier", 8, "italic"), bg=BG, fg=SUBTEXT, anchor='w', wraplength=270)
        self._speed_hint.pack(fill='x', pady=(0,4))

        # Auto-radius checkbox
        ar_row = tk.Frame(right, bg=BG)
        ar_row.pack(fill='x', pady=(8,2))
        tk.Checkbutton(ar_row, text="Auto cylinder radius from image width",
                       variable=self.auto_radius,
                       bg=BG, fg=TEXT, selectcolor=ENTRY_BG,
                       activebackground=BG, activeforeground=ACCENT2,
                       font=FONT_LBL, anchor='w',
                       command=self._on_auto_radius_toggle).pack(fill='x')
        self._auto_radius_note = tk.Label(right,
            text="  ↳ Cyl Radius slider disabled (computed from image)",
            font=("Courier", 8, "italic"), bg=BG, fg=SUBTEXT, anchor='w')
        self._auto_radius_note.pack(fill='x')
        self._on_auto_radius_toggle()   # set initial state

        # Progress + Render
        tk.Frame(right, bg=BORDER, height=1).pack(fill='x', pady=16)
        self._progress = ttk.Progressbar(right, length=280, mode='determinate')
        self._progress.pack(fill='x', pady=(0,10))

        self._render_btn = self._btn(right, "▶  RENDER VIDEO", self._start_render,
                                     big=True, color=BTN_RDR)
        self._render_btn.pack(fill='x', pady=(0,4))

        self._status = tk.Label(right, text="Ready.", font=FONT_LOG,
                                bg=BG, fg=SUBTEXT, wraplength=280, justify='left')
        self._status.pack(fill='x')

        # ── Fixed log bar at bottom (not scrollable) ────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill='x', padx=30)
        log_frame = tk.Frame(self, bg=PANEL)
        log_frame.pack(fill='x', padx=30, pady=(0,10))
        log_sb = ttk.Scrollbar(log_frame, orient='vertical')
        self._log = tk.Text(log_frame, height=5, bg=PANEL, fg="#5a6a4a",
                            font=FONT_LOG, relief='flat',
                            insertbackground=ACCENT2, state='disabled',
                            yscrollcommand=log_sb.set)
        log_sb.config(command=self._log.yview)
        log_sb.pack(side='right', fill='y', pady=8)
        self._log.pack(fill='both', expand=True, padx=(10,0), pady=8)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _section(self, parent, title):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill='x', pady=(14,4))
        tk.Label(f, text=title, font=("Courier",9,"bold"),
                 bg=BG, fg=ACCENT).pack(side='left')
        tk.Frame(f, bg=BORDER, height=1).pack(side='left', fill='x',
                                               expand=True, padx=(8,0))

    def _btn(self, parent, text, cmd, big=False, color=ACCENT):
        return tk.Button(parent, text=text, command=cmd,
                         bg=color, fg="#0d0d0f" if big else TEXT,
                         activebackground=BTN_HOV, activeforeground=BG,
                         relief='flat', cursor='hand2',
                         font=FONT_BTN if big else FONT_LBL,
                         padx=12, pady=8 if big else 5)

    def _bind_mousewheel_recursive(self):
        """Propagate scroll events from any child widget to its ancestor canvas."""
        def _find_scroll_canvas(w):
            p = w.master
            while p:
                if isinstance(p, tk.Canvas) and hasattr(p, 'yview'):
                    return p
                p = getattr(p, 'master', None)
            return None

        def _bind_widget(w):
            canvas = _find_scroll_canvas(w)
            if canvas:
                w.bind('<MouseWheel>',
                       lambda e, c=canvas: c.yview_scroll(int(-1*(e.delta/120)), 'units'),
                       add='+')
                w.bind('<Button-4>',
                       lambda e, c=canvas: c.yview_scroll(-1, 'units'), add='+')
                w.bind('<Button-5>',
                       lambda e, c=canvas: c.yview_scroll( 1, 'units'), add='+')
            for child in w.winfo_children():
                _bind_widget(child)

        for child in self.winfo_children():
            _bind_widget(child)

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # Default size: 90% of screen, capped sensibly
        dw = min(1400, int(sw * 0.90))
        dh = min(920,  int(sh * 0.90))
        x  = (sw - dw) // 2
        y  = (sh - dh) // 2
        self.geometry(f"{dw}x{dh}+{x}+{y}")

    def _on_auto_radius_toggle(self):
        if self.auto_radius.get():
            self._sliders['cyl_radius'].config(state='disabled')
            self._auto_radius_note.pack(fill='x')
        else:
            self._sliders['cyl_radius'].config(state='normal')
            self._auto_radius_note.pack_forget()

    # ── Image picking ─────────────────────────────────────────────────────────
    def _pick_images(self):
        paths = filedialog.askopenfilenames(
            title="Pick texture image(s)",
            filetypes=[("Images","*.png *.jpg *.jpeg *.webp *.bmp *.tiff"),
                       ("All files","*.*")]
        )
        if not paths:
            return
        self.image_paths = list(paths)
        self._refresh_image_list()
        cfg        = self._get_cfg()
        auto_rad   = self.auto_radius.get()   # read on main thread
        self._status.config(text="Generating preview…")
        threading.Thread(target=self._render_preview,
                         args=(cfg, auto_rad), daemon=True).start()

    def _clear_images(self):
        self.image_paths = []
        self._drop_zone.config(
            text="◻  Click to pick image(s)\n(JPG / PNG / WEBP — select multiple for panorama)",
            fg=SUBTEXT)
        self._img_list_lbl.config(text="No images selected.")
        self._canvas.delete('all')
        self._canvas.create_text(240, 135, text="pick an image to preview",
                                 fill=SUBTEXT, font=FONT_LOG, tags='hint')
        self._status.config(text="Ready.")

    def _refresh_image_list(self):
        n = len(self.image_paths)
        if n == 0:
            self._img_list_lbl.config(text="No images selected.")
            self._drop_zone.config(
                text="◻  Click to pick image(s)\n(JPG / PNG / WEBP — select multiple for panorama)",
                fg=SUBTEXT)
        elif n == 1:
            self._drop_zone.config(
                text=f"✓  {os.path.basename(self.image_paths[0])}", fg=ACCENT2)
            self._img_list_lbl.config(text="1 image selected.")
        else:
            names = ",  ".join(os.path.basename(p) for p in self.image_paths)
            self._drop_zone.config(text=f"✓  {n} images selected", fg=ACCENT2)
            self._img_list_lbl.config(text=f"{n} images: {names}")
        self._log_msg(f"Selected {n} image(s).")

    def _pick_output(self):
        path = filedialog.asksaveasfilename(
            title="Save video as",
            defaultextension=".mp4",
            filetypes=[("MP4 video","*.mp4")]
        )
        if path:
            self.output_path.set(path)

    # ── Preview ───────────────────────────────────────────────────────────────
    def _refresh_preview(self):
        """Manually trigger a preview render with current settings."""
        if not self.image_paths:
            messagebox.showwarning("No image", "Please pick at least one source image first.")
            return
        cfg      = self._get_cfg()
        auto_rad = self.auto_radius.get()
        self._status.config(text="Generating preview…")
        threading.Thread(target=self._render_preview,
                         args=(cfg, auto_rad), daemon=True).start()

    def _render_preview(self, cfg, auto_rad):
        # Runs on a worker thread — NO tkinter calls allowed here
        try:
            paths = list(self.image_paths)   # snapshot (list is fine to read)
            frame = make_preview_frame(paths, cfg, auto_radius=auto_rad)
            # Hand the PIL image back to the main thread
            self.after(0, lambda img=frame: self._set_preview(img))
        except Exception as e:
            err = str(e)
            self.after(0, lambda msg=err:
                       self._status.config(text=f"Preview error: {msg}"))

    def _set_preview(self, pil_img):
        # Runs on the main thread — safe to create ImageTk here
        tk_img = ImageTk.PhotoImage(pil_img)
        self._preview_img = tk_img          # keep reference so GC won't collect it
        self._canvas.delete('all')
        self._canvas.create_image(0, 0, anchor='nw', image=tk_img)
        self._status.config(text="Preview ready.  Adjust settings and click Render.")

    # ── Render ────────────────────────────────────────────────────────────────
    def _get_cfg(self):
        return {k: (int(v.get()) if k in ('width','height','fps','segments','duration')
                    else float(v.get()))
                for k, v in self.cfg.items()}

    def _start_render(self):
        if self._rendering:
            return
        if not self.image_paths:
            messagebox.showwarning("No image", "Please pick at least one source image.")
            return
        out = self.output_path.get()
        if not out:
            messagebox.showwarning("No output", "Please set an output file path.")
            return
        self._rendering = True
        self._render_btn.config(state='disabled', text="Rendering…")
        self._progress['value'] = 0
        cfg      = self._get_cfg()
        auto_rad = self.auto_radius.get()   # read on main thread
        threading.Thread(target=self._render_thread,
                         args=(cfg, list(self.image_paths), out, auto_rad),
                         daemon=True).start()

    def _render_thread(self, cfg, image_paths, out_path, auto_rad):
        try:
            render_video(
                image_paths,
                out_path,
                cfg,
                auto_radius=auto_rad,
                progress_cb=lambda p: self.after(0, lambda pv=p: self._set_progress(pv)),
                log_cb=lambda m: self.after(0, lambda msg=m: self._log_msg(msg)),
            )
            self.after(0, self._render_done)
        except Exception as e:
            err = str(e)
            self.after(0, lambda msg=err: self._render_error(msg))

    def _set_progress(self, p):
        self._progress['value'] = p * 100

    def _render_done(self):
        self._rendering = False
        self._render_btn.config(state='normal', text="▶  RENDER VIDEO")
        self._progress['value'] = 100
        self._status.config(text=f"✓ Done!  Saved to:\n{self.output_path.get()}")
        messagebox.showinfo("Done", f"Video saved!\n{self.output_path.get()}")

    def _render_error(self, err):
        self._rendering = False
        self._render_btn.config(state='normal', text="▶  RENDER VIDEO")
        self._status.config(text=f"Error: {err}")
        messagebox.showerror("Render Error", err)

    def _log_msg(self, msg):
        self._log.config(state='normal')
        self._log.insert('end', msg + "\n")
        self._log.see('end')
        self._log.config(state='disabled')


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    style = ttk.Style()
    try:
        style.theme_use('clam')
    except Exception:
        pass
    style.configure("TScale",       background=BG, troughcolor=ENTRY_BG,
                    sliderthickness=14, sliderrelief='flat')
    style.configure("TProgressbar", troughcolor=ENTRY_BG, background=ACCENT,
                    thickness=8)

    app = App()
    app.mainloop()