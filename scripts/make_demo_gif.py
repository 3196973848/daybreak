"""Convert a recorded screen capture (mp4) into docs/screenshots/demo.gif.

Usage:
    python scripts/make_demo_gif.py <input.mp4> [output.gif]
"""

import sys
from pathlib import Path

import imageio.v2 as iio
from PIL import Image


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/make_demo_gif.py <input.mp4> [output.gif]")
        sys.exit(1)
    source = Path(sys.argv[1])
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs/screenshots/demo.gif")
    target.parent.mkdir(parents=True, exist_ok=True)

    reader = iio.get_reader(str(source))
    meta = reader.get_meta_data()
    fps = float(meta.get("fps", 30) or 30)
    step = max(1, round(fps / 12))

    frames: list[Image.Image] = []
    for index, frame in enumerate(reader):
        if index % step != 0:
            continue
        image = Image.fromarray(frame)
        if image.width > 900:
            height = round(image.height * 900 / image.width)
            image = image.resize((900, height), Image.LANCZOS)
        frames.append(image)
        if len(frames) >= 240:
            break

    if not frames:
        print("没有读到帧，请确认输入文件是有效的视频")
        sys.exit(1)

    duration_ms = max(80, round(step / fps * 1000))
    frames[0].save(
        target,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    print(f"已生成 {target}（{len(frames)} 帧，{duration_ms}ms/帧）")


if __name__ == "__main__":
    main()
