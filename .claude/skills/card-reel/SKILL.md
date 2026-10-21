---
name: "card-reel"
description: "@ai.sunbae 카드뉴스 PNG를 9:16 인스타 릴스 MP4(훅→카드→댓글 CTA)와 릴스 캡션으로 바꿀 때 사용. /card-reel 또는 '릴스로 만들어줘' 요청 시."
---

# card-reel: 카드뉴스 → 릴스 변환

@ai.sunbae 카드뉴스(1080×1350 PNG 여러 장)를 받아 릴스용 MP4와 캡션을 만든다.

## 0. 원칙
- 카드 내용을 지어내지 않는다. PNG 원본이 없으면(프로필 캡처·썸네일뿐이면) 만들지 말고 원본 전체를 요청한다.
- 훅·CTA 문구는 카드에 실제로 있는 내용(상황 문구, 프롬프트 개수)에서만 뽑는다.
- 줄바꿈 규칙: 문장 끝·쉼표 등 의미 단위에서만 끊고, 단어 중간 끊김 금지, 한 단어만 남는 줄 금지.
- 디자인: 배경 네이비 #0F1B3D, 포인트 라임 #C8F542, 텍스트 화이트, 굵은 고딕, 하단 @ai.sunbae.

## 1. 입력 확인
- 카드 PNG 전체(순서대로). 파일명이 순서를 말해주지 않으면 이미지를 Read로 직접 보고 표지 → 본문 → 마지막 장 순서를 정한다.
- 편마다 정할 것: 훅 문구(2줄 이내), 댓글 키워드(예: 보고/메일/공지), CTA 보조 문구(예: 프롬프트 5개 DM으로).
- 사용자가 안 정해줬으면 표지 상황 문구로 훅을 쓰고, 편 주제 한 단어를 키워드로 정한 뒤 답변에 무엇으로 정했는지 적는다.

## 2. 영상 구성 (총 8~12초)
| 구간 | 화면 | 길이 |
|---|---|---|
| 훅 | 네이비 전체 화면 + 큰 훅 문구 | 2초 |
| 표지 | 카드 1장 | 1.5초 |
| 본문 | 프롬프트 장마다 | 각 1초 |
| Before/After 장 | 전환이 핵심인 장 | 2초 |
| CTA | "댓글에 '키워드' 남기면" + 보조 문구 | 2.5초 |

- 카드는 1080×1920 안에 1080×1350으로 세로 가운데(y=285) 배치. 훅·CTA는 카드 없이 전체 화면에 크게.
- 음악은 넣지 않는다(사용자가 앱에서 인기 오디오를 붙임).

## 3. 폰트 준비
```bash
fc-list :lang=ko | head
```
한글 굵은 고딕이 없으면:
```bash
mkdir -p ~/fonts && curl -sSL -o ~/fonts/NotoSansKR.ttf "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"
```
둘 다 안 되면 사용자에게 막혔다고 말하고 멈춘다(다른 폰트로 대충 만들지 않는다).

## 4. 렌더링 스크립트
작업 폴더에 `make_reel.py`로 저장하고 `python3 make_reel.py spec.json`으로 실행. Pillow, ffmpeg가 없으면 설치(pip는 --break-system-packages).

spec.json 예시:
```json
{
  "font": "/root/fonts/NotoSansKR.ttf",
  "cards": ["01.png", "02.png", "03.png"],
  "long": [],
  "hook": "금요일 4시,\n주간보고 아직 0줄?",
  "keyword": "보고",
  "cta_sub": "프롬프트 5개 DM으로 보내드려요",
  "out": "weekly-report_reel.mp4"
}
```
`long`에는 2초로 보여줄 카드의 인덱스(0부터)를 넣는다(Before/After 장 등).

```python
import json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

NAVY, LIME, WHITE, GRAY = "#0F1B3D", "#C8F542", "#FFFFFF", "#AEB6CC"
W, H = 1080, 1920
spec = json.load(open(sys.argv[1]))

def font(size):
    f = ImageFont.truetype(spec["font"], size)
    try:
        f.set_variation_by_axes([800])  # variable font면 굵게
    except Exception:
        pass
    return f

def center_lines(draw, lines, y, size, gap=1.3):
    f = font(size)
    for parts in lines:  # parts: [(text, color), ...]
        widths = [draw.textlength(t, font=f) for t, _ in parts]
        x = (W - sum(widths)) / 2
        for (t, c), w in zip(parts, widths):
            draw.text((x, y), t, font=f, fill=c)
            x += w
        y += size * gap
    return y

def handle(draw):
    f = font(40)
    t = "@ai.sunbae"
    draw.text(((W - draw.textlength(t, font=f)) / 2, 1560), t, font=f, fill=GRAY)

tmp = tempfile.mkdtemp()
frames = []

# 훅
im = Image.new("RGB", (W, H), NAVY); d = ImageDraw.Draw(im)
lines = spec["hook"].split("\n")
y0 = H / 2 - len(lines) * 110 * 1.3 / 2 - 40
center_lines(d, [[(l, WHITE if i == 0 else LIME)] for i, l in enumerate(lines)], y0, 110)
handle(d)
p = f"{tmp}/00_hook.png"; im.save(p); frames.append((p, 2.0))

# 카드
for i, c in enumerate(spec["cards"]):
    im = Image.new("RGB", (W, H), NAVY)
    card = Image.open(c).convert("RGB").resize((1080, 1350), Image.LANCZOS)
    im.paste(card, (0, (H - 1350) // 2))
    dur = 1.5 if i == 0 else (2.0 if i in spec.get("long", []) else 1.0)
    p = f"{tmp}/{i+1:02d}.png"; im.save(p); frames.append((p, dur))

# CTA
im = Image.new("RGB", (W, H), NAVY); d = ImageDraw.Draw(im)
y = center_lines(d, [[("댓글에 ", WHITE), (f"'{spec['keyword']}'", LIME)], [("남기면", WHITE)]], 700, 110)
center_lines(d, [[(spec["cta_sub"], WHITE)]], y + 40, 56)
handle(d)
p = f"{tmp}/99_cta.png"; im.save(p); frames.append((p, 2.5))

lst = f"{tmp}/list.txt"
with open(lst, "w") as fh:
    for p, dur in frames:
        fh.write(f"file '{p}'\nduration {dur}\n")
    fh.write(f"file '{frames[-1][0]}'\n")

subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
    "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "18",
    "-movflags", "+faststart", spec["out"]], check=True)
print("done:", spec["out"], "frames:", tmp)
```

## 5. 검수 (필수)
- `ffprobe -v error -show_entries format=duration -of csv=p=0 out.mp4`로 길이 8~12초 확인.
- 구간마다 프레임 추출 후 Read로 직접 본다: `ffmpeg -ss 1 -i out.mp4 -frames:v 1 check_hook.png` (훅·표지·CTA는 반드시).
- 확인할 것: 한글 깨짐 없음, 훅·CTA 줄바꿈이 규칙에 맞음, 키워드만 라임색, 카드 순서 맞음, 글자가 화면 밖으로 안 나감.
- 문제 있으면 고쳐서 다시 렌더링한 뒤에만 전달.

## 6. 캡션
- 첫 줄: 검색될 키워드 문장 (예: 주간보고 AI 프롬프트 5개, 복붙하면 10분 컷)
- 본문 2~3줄: 어떤 상황에 쓰는지
- CTA: 댓글에 '키워드' 남기면 프롬프트 링크 DM으로 보내드려요 / 저장해두고 꺼내 쓰세요
- 해시태그: 중요도순 5개만

## 7. 전달
- MP4는 SendUserFile로 편마다 보낸다(휴대폰에 저장해 업로드).
- 캡션은 답변 본문에 복사하기 좋게 코드블록으로.
- 업로드 팁 한 줄씩: 체험판 릴스로 올리기, 커버는 표지 프레임 선택, 저녁 7~9시 업로드(카드뉴스 오전 8시와 분리), 앱에서 인기 오디오 추가.