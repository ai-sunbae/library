"""두부 EP01 「5분만」 — 9초 무대사 릴스 렌더러.

python3 render_ep01.py  ->  out/ep01_5min.mp4, out/ep01_cover.jpg
PIL로 프레임을 그리고 numpy로 효과음을 합성해 ffmpeg로 묶는다.
"""
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
S = 2  # 2배로 그린 뒤 축소해 선을 부드럽게
FPS = 30
DUR = 9.0
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

LINE = (58, 46, 42)
TOFU = (255, 253, 245)
BLUSH = (255, 182, 182)
WALL = (252, 232, 216)
FLOOR = (233, 201, 168)
BLANKET = (159, 201, 232)
RED = (232, 72, 72)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(FONT, int(size * S))
    return _fonts[size]


def p(*v):
    return [x * S for x in v]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def seg(t, a, b):
    return clamp((t - a) / (b - a))


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 3 * x * x - 2 * x * x * x


def lerp(a, b, x):
    return a + (b - a) * x


def mix(c1, c2, x):
    return tuple(int(lerp(a, b, x)) for a, b in zip(c1, c2))


# ---------- 캐릭터 ----------

def tofu(d, cx, cy, w, h, eyes="dot", mouth="small", legs=None, blush=True):
    lw = 9
    if legs is not None:  # legs = 달리기 위상(라디안)
        for side in (-1, 1):
            lift = max(0, math.sin(legs + (0 if side < 0 else math.pi))) * 26
            lx = cx + side * w * 0.22
            d.rounded_rectangle(p(lx - 22, cy + h / 2 - 20 - lift, lx + 22, cy + h / 2 + 34 - lift),
                                radius=18 * S, fill=TOFU, outline=LINE, width=lw * S)
    r = min(w, h) * 0.3
    d.rounded_rectangle(p(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                        radius=r * S, fill=TOFU, outline=LINE, width=lw * S)
    # 윗면 하이라이트
    d.arc(p(cx - w * 0.38, cy - h * 0.42, cx - w * 0.05, cy - h * 0.12), 190, 250,
          fill=(255, 255, 255), width=8 * S)
    ex, ey = w * 0.2, cy - h * 0.06
    for side in (-1, 1):
        x = cx + side * ex
        if eyes == "dot":
            d.ellipse(p(x - 13, ey - 15, x + 13, ey + 15), fill=LINE)
        elif eyes == "sleep":
            d.arc(p(x - 24, ey - 18, x + 24, ey + 14), 20, 160, fill=LINE, width=7 * S)
        elif eyes == "happy":
            d.arc(p(x - 24, ey - 8, x + 24, ey + 28), 200, 340, fill=LINE, width=7 * S)
        elif eyes == "shock":
            d.ellipse(p(x - 36, ey - 40, x + 36, ey + 40), fill=(255, 255, 255), outline=LINE, width=6 * S)
            d.ellipse(p(x - 9, ey - 9, x + 9, ey + 9), fill=LINE)
        elif eyes == "blank":
            d.ellipse(p(x - 6, ey - 6, x + 6, ey + 6), fill=LINE)
    if blush:
        for side in (-1, 1):
            x = cx + side * w * 0.33
            d.ellipse(p(x - 26, ey + 20, x + 26, ey + 38), fill=BLUSH)
    my = cy + h * 0.13
    if mouth == "small":
        d.arc(p(cx - 14, my - 10, cx + 14, my + 8), 20, 160, fill=LINE, width=6 * S)
    elif mouth == "smile":
        d.arc(p(cx - 26, my - 18, cx + 26, my + 14), 20, 160, fill=LINE, width=7 * S)
    elif mouth == "o":
        d.ellipse(p(cx - 22, my - 8, cx + 22, my + 40), fill=LINE)
        d.ellipse(p(cx - 12, my + 18, cx + 12, my + 36), fill=(240, 120, 120))
    elif mouth == "drool":
        d.ellipse(p(cx - 9, my - 4, cx + 9, my + 12), fill=LINE)
        d.ellipse(p(cx + 14, my + 4, cx + 26, my + 22), fill=(170, 220, 255), outline=LINE, width=3 * S)
    elif mouth == "flat":
        d.line(p(cx - 16, my + 4, cx + 16, my + 4), fill=LINE, width=6 * S)


def arm(d, x0, y0, x1, y1):
    d.line(p(x0, y0, x1, y1), fill=LINE, width=26 * S)
    d.line(p(x0, y0, x1, y1), fill=TOFU, width=12 * S)
    d.ellipse(p(x1 - 22, y1 - 22, x1 + 22, y1 + 22), fill=TOFU, outline=LINE, width=7 * S)


def sweat(d, x, y, s=1.0):
    d.polygon(p(x, y - 30 * s, x - 16 * s, y + 4 * s, x + 16 * s, y + 4 * s), fill=(150, 210, 255))
    d.ellipse(p(x - 16 * s, y - 12 * s, x + 16 * s, y + 20 * s), fill=(150, 210, 255), outline=LINE, width=4 * S)


def zz(d, x, y, t):
    for i in range(3):
        ph = (t * 0.9 + i / 3) % 1
        a = int(255 * math.sin(ph * math.pi))
        if a < 20:
            continue
        sz = 34 + 22 * ph
        d.text((p(x + 60 * ph + i * 8)[0], p(y - 160 * ph)[0]), "Z", font=font(sz),
               fill=mix(WALL, LINE, a / 255))


# ---------- 배경 ----------

def room(d, t, clock_min, ring, slam, light, cal_glow):
    d.rectangle(p(0, 0, W, 1300), fill=WALL)
    d.rectangle(p(0, 1300, W, H), fill=FLOOR)
    d.line(p(0, 1300, W, 1300), fill=LINE, width=8 * S)
    # 창문: light 0(새벽)->1(한낮)
    sky = mix((205, 222, 240), (140, 208, 255), light)
    d.rounded_rectangle(p(110, 300, 470, 700), radius=20 * S, fill=sky, outline=LINE, width=9 * S)
    sun_y = lerp(640, 420, light)
    d.ellipse(p(330 - 50, sun_y - 50, 330 + 50, sun_y + 50), fill=mix((255, 200, 150), (255, 220, 90), light))
    d.rounded_rectangle(p(110, 300, 470, 700), radius=20 * S, outline=LINE, width=9 * S)
    d.line(p(290, 300, 290, 700), fill=LINE, width=7 * S)
    d.line(p(110, 500, 470, 500), fill=LINE, width=7 * S)
    # 벽달력 (복선: 처음부터 걸려 있다)
    cx0, cy0 = 640, 380
    if cal_glow > 0:
        for k in range(10, 0, -1):
            g = cal_glow * k / 10
            d.ellipse(p(cx0 + 95 - 150 * g, cy0 + 120 - 150 * g, cx0 + 95 + 150 * g, cy0 + 120 + 150 * g),
                      fill=mix(WALL, (255, 240, 170), 1 - k / 10 * 0.6))
    d.rectangle(p(cx0, cy0, cx0 + 190, cy0 + 240), fill=(255, 255, 255), outline=LINE, width=8 * S)
    d.rectangle(p(cx0, cy0, cx0 + 190, cy0 + 60), fill=RED, outline=LINE, width=8 * S)
    d.text((p(cx0 + 95)[0], p(cy0 + 32)[0]), "SUN", font=font(36), fill=(255, 255, 255), anchor="mm")
    d.text((p(cx0 + 95)[0], p(cy0 + 152)[0]), "7", font=font(110), fill=RED, anchor="mm")
    d.ellipse(p(cx0 + 85, cy0 - 18, cx0 + 105, cy0 + 2), fill=LINE)
    # 침대
    d.rounded_rectangle(p(70, 1080, 700, 1320), radius=24 * S, fill=(214, 168, 128), outline=LINE, width=9 * S)
    d.rounded_rectangle(p(60, 960, 110, 1330), radius=20 * S, fill=(214, 168, 128), outline=LINE, width=9 * S)
    d.ellipse(p(110, 960, 340, 1090), fill=(255, 255, 255), outline=LINE, width=8 * S)
    # 협탁 + 시계
    d.rounded_rectangle(p(730, 1080, 980, 1320), radius=16 * S, fill=(214, 168, 128), outline=LINE, width=9 * S)
    d.line(p(745, 1190, 965, 1190), fill=LINE, width=6 * S)
    sx = math.sin(t * 90) * 9 * ring
    sq = 1 - 0.18 * slam
    ccx, ccy, cr = 855 + sx, 1080 - 92 * sq, 88
    for side in (-1, 1):
        bx = ccx + side * 58
        d.ellipse(p(bx - 30, ccy - cr - 18, bx + 30, ccy - cr + 30), fill=RED, outline=LINE, width=7 * S)
    d.ellipse(p(ccx - cr, ccy - cr * sq, ccx + cr, ccy + cr * sq), fill=(255, 255, 255), outline=LINE, width=9 * S)
    d.line(p(ccx - 50, ccy + cr * sq - 4, ccx - 64, ccy + cr * sq + 14), fill=LINE, width=8 * S)
    d.line(p(ccx + 50, ccy + cr * sq - 4, ccx + 64, ccy + cr * sq + 14), fill=LINE, width=8 * S)
    hm = clock_min / 60.0
    ha = math.radians(hm * 30 - 90)
    ma = math.radians((clock_min % 60) * 6 - 90)
    d.line(p(ccx, ccy, ccx + math.cos(ha) * 42, ccy + math.sin(ha) * 42 * sq), fill=LINE, width=10 * S)
    d.line(p(ccx, ccy, ccx + math.cos(ma) * 66, ccy + math.sin(ma) * 66 * sq), fill=RED, width=7 * S)
    d.ellipse(p(ccx - 9, ccy - 9, ccx + 9, ccy + 9), fill=LINE)
    if ring > 0:
        for side in (-1, 1):
            for k in range(2):
                rr = cr + 30 + k * 26
                d.arc(p(ccx - rr, ccy - rr, ccx + rr, ccy + rr),
                      (-60 if side > 0 else 200), (-20 if side > 0 else 240), fill=LINE, width=7 * S)
    return ccx, ccy


def blanket(d, lump):
    d.rounded_rectangle(p(250, 1030 - lump, 715, 1210), radius=60 * S, fill=BLANKET, outline=LINE, width=9 * S)
    for i in range(5):
        x = 320 + i * 85
        d.ellipse(p(x - 9, 1110 - 9, x + 9, 1110 + 9), fill=(255, 255, 255))


# ---------- 장면 ----------

def scene(t):
    img = Image.new("RGB", (W * S, H * S), WALL)
    d = ImageDraw.Draw(img)

    # 시간 경과: 2.6~3.6초에 7:00 -> 9:00
    clock_min = 7 * 60 + ease_in_out(seg(t, 2.6, 3.6)) * 120
    light = 0.15 + 0.85 * ease_in_out(seg(t, 2.6, 3.6))
    ring = 1.0 if t < 1.1 else (1.0 if 3.6 <= t < 3.95 else 0.0)
    slam = max(0.0, 1 - abs(t - 1.12) / 0.12) if 1.0 < t < 1.3 else 0.0
    cal_glow = ease_out(seg(t, 6.45, 6.8)) * (1 - seg(t, 7.6, 8.0))
    ccx, ccy = room(d, t, clock_min, ring, slam, light, cal_glow)

    breath = math.sin(t * 3.2) * 6
    bed_x, bed_y = 270, 1010

    if t < 3.7 or t >= 8.3:
        # 자는 중 (8.3초 이후는 루프용으로 다시 침대)
        sink = 18 * ease_out(seg(t, 1.4, 1.9)) if t < 3.7 else 18
        wig = math.sin(t * 20) * 10 * (seg(t, 2.6, 2.8) - seg(t, 3.4, 3.6)) if t < 3.7 else 0
        eyes = "happy" if 1.4 <= t < 2.6 else "sleep"
        mouth = "smile" if 1.4 <= t < 2.6 else "drool"
        tofu(d, bed_x + wig, bed_y + sink - breath / 2, 250 + breath, 220 - breath, eyes, mouth)
        blanket(d, 10 + breath)
        if 0.9 < t < 1.45:
            # 쭉 늘어나는 팔로 알람 탁
            reach = ease_out(seg(t, 0.9, 1.1)) * (1 - ease_in_out(seg(t, 1.2, 1.45)))
            tx, ty = lerp(560, ccx - 10, reach), lerp(1060, ccy - 70, reach)
            arm(d, 520, 1060, tx, ty)
        if 1.1 <= t < 3.7 or t >= 8.3:
            zz(d, bed_x + 110, bed_y - 120, t)
    elif t < 4.6:
        # 9시 확인 -> 기겁
        k = ease_out(seg(t, 3.7, 3.95))
        jump = math.sin(seg(t, 3.7, 4.35) * math.pi) * 330
        stretch = 1 + 0.25 * math.sin(seg(t, 3.7, 4.0) * math.pi)
        x = lerp(bed_x, 480, seg(t, 4.0, 4.6))
        y = lerp(bed_y, 1180, ease_in_out(seg(t, 4.0, 4.6))) - jump
        tofu(d, x, y, 250 / stretch, 220 * stretch, "shock", "o")
        blanket(d, 10 - 40 * k)
        sweat(d, x + 140, y - 90, 1.2)
        sweat(d, x - 150, y - 60, 0.9)
        d.text((p(x + 10)[0], p(y - 230)[0]), "!!", font=font(120), fill=RED, anchor="mm")
    elif t < 6.4:
        # 우왕좌왕 달리기
        blanket(d, -30)
        ph = (t - 4.6) * 2.6
        x = 540 + math.sin(ph * math.pi) * 300
        y = 1180 - abs(math.sin(t * 22)) * 14
        dirn = 1 if math.cos(ph * math.pi) > 0 else -1
        for k in range(3):
            lx = x - dirn * (170 + k * 40)
            d.line(p(lx, y - 40 + k * 40, lx - dirn * 70, y - 40 + k * 40), fill=LINE, width=6 * S)
        for k in range(3):
            px = x - dirn * (150 + k * 55)
            pr = 26 - k * 6
            d.ellipse(p(px - pr, y + 105 - pr, px + pr, y + 105 + pr), fill=(250, 245, 240), outline=LINE, width=4 * S)
        tofu(d, x, y, 240, 220, "shock", "o", legs=t * 30)
        sweat(d, x + dirn * -130, y - 110, 1.0)
    elif t < 7.4:
        # 달력 발견 -> 얼음
        blanket(d, -30)
        stop = ease_out(seg(t, 6.4, 6.55))
        x = lerp(700, 735, stop)
        y = 1180
        look = "dot" if t < 6.7 else "blank"
        tofu(d, x, y, 240, 220, look, "flat" if t >= 6.7 else "o")
        if t >= 6.8:
            for i in range(3):
                if t >= 6.8 + i * 0.15:
                    d.ellipse(p(x - 250 + i * 45 - 10, y - 130 - 10, x - 250 + i * 45 + 10, y - 130 + 10), fill=LINE)
    else:
        # 녹아내림
        blanket(d, -30)
        m = ease_in_out(seg(t, 7.4, 8.2))
        w = lerp(240, 470, m)
        h = lerp(220, 90, m)
        y = 1180 + (220 - h) / 2
        tofu(d, 735 - (w - 240) * 0.3, y, w, h, "happy", "smile")
        if m > 0.5:
            for i in range(4):
                hx = 580 + i * 70
                hy = 1170 - ((t * 120 + i * 40) % 100)
                d.text((p(hx)[0], p(hy)[0]), "~", font=font(60), fill=LINE, anchor="mm")

    # 카메라: 방을 화면 중앙에 1.23배로 잡고, 기겁 순간 흔들림 + 달력 줌
    shake = 0
    if 3.7 <= t < 4.2:
        shake = math.sin(t * 120) * 16 * (1 - seg(t, 3.7, 4.2))
    zk = ease_out(seg(t, 6.45, 6.8)) * (1 - ease_in_out(seg(t, 7.3, 7.6)))
    zoom = 1 + 0.55 * zk
    zx, zy = lerp(540, 735, zk), lerp(880, 700, zk)
    cw, ch = 880 / zoom, 1564 / zoom
    left = clamp(zx - cw / 2 + shake, 0, W - cw)
    top = clamp(zy - ch / 2, 0, H - ch)
    box = tuple(int(v * S) for v in (left, top, left + cw, top + ch))
    return img.crop(box).resize((W, H), Image.LANCZOS)


# ---------- 효과음 ----------

SR = 44100


def sfx():
    n = int(SR * DUR)
    a = np.zeros(n)
    tt = np.arange(n) / SR

    def add(start, sig):
        i = int(start * SR)
        a[i:i + len(sig)] += sig[: max(0, n - i)]

    def env(L, atk=0.005, rel=0.05):
        e = np.ones(L)
        ka, kr = int(atk * SR), int(rel * SR)
        e[:ka] = np.linspace(0, 1, ka)
        e[-kr:] = np.linspace(1, 0, kr)
        return e

    def beep(f, L):
        x = np.arange(int(L * SR)) / SR
        return np.sign(np.sin(2 * np.pi * f * x)) * 0.12 * env(len(x))

    for k in range(5):
        add(0.05 + k * 0.2, beep(1760, 0.1))
    x = np.arange(int(0.15 * SR)) / SR
    add(1.1, np.sin(2 * np.pi * 110 * x) * np.exp(-x * 30) * 0.6 + np.random.randn(len(x)) * np.exp(-x * 80) * 0.15)
    tick = np.random.randn(int(0.01 * SR)) * 0.25 * np.linspace(1, 0, int(0.01 * SR))
    ts = 2.6
    gap = 0.12
    while ts < 3.6:
        add(ts, tick)
        ts += gap
        gap = max(0.03, gap * 0.85)
    for k in range(2):
        add(3.6 + k * 0.16, beep(1760, 0.1))
    x = np.arange(int(0.35 * SR)) / SR
    f = np.linspace(260, 950, len(x))
    add(3.72, np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35 * np.exp(-x * 5))
    ts = 4.6
    while ts < 6.4:
        L = int(0.03 * SR)
        add(ts, np.random.randn(L) * 0.12 * np.linspace(1, 0, L))
        ts += 0.085
    x = np.arange(int(1.2 * SR)) / SR
    ding = sum(np.sin(2 * np.pi * 1320 * h * x) / h for h in (1, 2, 3)) * 0.22 * np.exp(-x * 3.5)
    add(6.45, ding)
    x = np.arange(int(0.8 * SR)) / SR
    f = np.linspace(620, 160, len(x))
    add(7.4, np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25 * env(len(x), 0.05, 0.3))
    x = np.arange(int(0.7 * SR)) / SR
    snore = np.convolve(np.random.randn(len(x)), np.ones(60) / 60, "same") * 0.5 * np.sin(np.pi * x / 0.7) ** 2
    add(8.3, snore)
    a = np.clip(a, -1, 1)
    return (a * 32767).astype(np.int16)


def main():
    os.makedirs(OUT, exist_ok=True)
    wav = os.path.join(OUT, "ep01_sfx.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(sfx().tobytes())

    mp4 = os.path.join(OUT, "ep01_5min.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(DUR * FPS)):
        t = i / FPS
        frame = scene(t)
        if abs(t - 3.9) < 0.5 / FPS:
            frame.save(os.path.join(OUT, "ep01_cover.jpg"), quality=92)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print(mp4)


if __name__ == "__main__":
    np.random.seed(7)
    main()
