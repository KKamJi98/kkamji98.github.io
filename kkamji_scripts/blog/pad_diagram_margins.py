#!/usr/bin/env python3
"""다이어그램 이미지의 사방(상하좌우) 여백을 동일하게 맞추는 도구.

drawio 등에서 export 한 이미지는 `-b`/`--crop` 옵션을 써도 border/shadow 처리
때문에 사방 여백이 비대칭으로 남는 경우가 많다. 이 스크립트는 export 결과를
후처리해서 균일한 여백을 보장한다.

동작:
  1. 흰색이 아닌(채널 < THRESHOLD) 픽셀의 bounding box(잉크 영역)를 찾는다.
  2. 그 영역만 잘라낸 뒤, 사방에 동일한 픽셀 패딩을 둔 흰 캔버스 중앙에 배치한다.

사용 (Pillow 필요 -> uv 권장):
  # 트림 + 사방 110px 균등 패딩 후 webp 저장
  uv run --with pillow python kkamji_scripts/blog/pad_diagram_margins.py in.png out.webp --pad 110

  # 결과 이미지의 사방 여백을 측정만 (L/R/T/B 가 같아야 함)
  uv run --with pillow python kkamji_scripts/blog/pad_diagram_margins.py out.webp --verify

참고: drawio 도형에 `shadow=1`을 두면 우하단에만 그림자가 생겨 잉크 bbox가
비대칭이 되므로, export 전에 그림자를 끄는 것을 권장한다.
"""

from __future__ import annotations

import argparse
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow가 필요합니다: `uv run --with pillow python ...` 로 실행하세요.")

THRESHOLD = 244  # 채널 값이 이 미만이면 잉크(비-흰색)로 간주

# 여백 비대칭 허용치(px).
#
# 패딩 자체는 정확하다. 잉크 bbox로 자른 뒤 사방에 같은 값을 덧대므로 무손실
# 이미지에서 재보면 네 변이 모두 같은 값으로 나온다. 그러나 저장 형식이
# webp(quality 92)면 인코더가 내용 경계 바깥으로 240대 초반의 옅은 halo를 한 픽셀
# 남기고, 그 halo가 변마다 다르게 걸려서 재측정값이 1~2px 흔들린다. 임계값을
# 낮춰 halo를 걸러내 봐도(236 실측) 어떤 파일은 반대로 halo를 잃어 R이 2px 커지므로,
# 임계값 조정은 잡음을 옮길 뿐이다.
#
# 이 검사가 잡으려는 결함은 drawio의 `--crop`이 만드는 비대칭이고 그 크기는
# 실측 L=162 R=104 T=162 B=42 처럼 수십 px 단위다. 따라서 인코더 잡음보다는 크고
# 실제 결함보다는 두 자릿수 작은 2px를 허용치로 둔다.
MAX_MARGIN_SPREAD = 2


def ink_bbox(im: "Image.Image") -> tuple[int, int, int, int]:
    """비-흰색 픽셀의 bounding box (minx, miny, maxx, maxy) 반환."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r < THRESHOLD or g < THRESHOLD or b < THRESHOLD:
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
    if maxx < 0:
        sys.exit("잉크(비-흰색) 픽셀을 찾지 못했습니다.")
    return minx, miny, maxx, maxy


def pad(src: str, dst: str, p: int) -> None:
    im = Image.open(src).convert("RGB")
    minx, miny, maxx, maxy = ink_bbox(im)
    content = im.crop((minx, miny, maxx + 1, maxy + 1))
    cw, ch = content.size
    fmt = "WEBP" if dst.lower().endswith(".webp") else None
    out = Image.new("RGB", (cw + 2 * p, ch + 2 * p), (255, 255, 255))
    out.paste(content, (p, p))
    out.save(dst, fmt, quality=92) if fmt else out.save(dst)
    print(f"{dst}: ink {cw}x{ch} -> {out.size[0]}x{out.size[1]} (pad {p} all sides)")


def verify(src: str) -> int:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    minx, miny, maxx, maxy = ink_bbox(im)
    left, right, top, bottom = minx, w - 1 - maxx, miny, h - 1 - maxy
    spread = max(left, right, top, bottom) - min(left, right, top, bottom)
    print(f"{src}: L={left} R={right} T={top} B={bottom} (spread {spread}px)")
    ok = spread <= MAX_MARGIN_SPREAD
    if ok:
        print("equal margins: OK")
    else:
        print(
            f"equal margins: MISMATCH (spread {spread}px > {MAX_MARGIN_SPREAD}px "
            "allowance; re-run the trim+pad pipeline instead of adjusting the border)"
        )
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="다이어그램 이미지 사방 여백 균일화/검증")
    ap.add_argument("src", help="입력 이미지 경로")
    ap.add_argument(
        "dst", nargs="?", help="출력 이미지 경로(.webp 권장). --verify 시 생략"
    )
    ap.add_argument("--pad", type=int, default=110, help="사방 패딩 픽셀 (기본 110)")
    ap.add_argument("--verify", action="store_true", help="여백 측정만 수행")
    args = ap.parse_args()

    if args.verify:
        return verify(args.src)
    if not args.dst:
        ap.error("출력 경로(dst)가 필요합니다 (또는 --verify 사용).")
    pad(args.src, args.dst, args.pad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
