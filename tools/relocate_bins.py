"""Перемещает все .dll/.pyd в подпапку bin/ в папке билда."""

import os
import shutil
import sys


def _auto_find_dist(base_dir):
    candidates = []
    for name in os.listdir(base_dir):
        if not name.endswith(".dist"):
            continue
        path = os.path.join(base_dir, name)
        if os.path.isdir(path):
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "--auto"
    if arg == "--auto":
        dist_dir = _auto_find_dist(os.getcwd())
        if not dist_dir:
            print("Не удалось найти папку *.dist. Укажите путь вручную.")
            return 1
    else:
        dist_dir = arg
    dist_dir = os.path.abspath(dist_dir)
    if not os.path.isdir(dist_dir):
        print(f"Папка не найдена: {dist_dir}")
        return 1
    bin_dir = os.path.join(dist_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    moved = []
    skipped = []
    for name in os.listdir(dist_dir):
        path = os.path.join(dist_dir, name)
        if not os.path.isfile(path):
            continue
        low = name.lower()
        # Оставляем рядом с exe только указанные .pyd
        if low in ("_ctypes.pyd", "pyexpat.pyd"):
            skipped.append(name)
            continue
        if low.endswith(".dll") or low.endswith(".pyd"):
            target = os.path.join(bin_dir, name)
            try:
                shutil.move(path, target)
                moved.append(name)
            except Exception as exc:
                print(f"Не удалось переместить {name}: {exc}")
    print(f"Готово. Перемещено: {len(moved)} файлов.")
    if skipped:
        print(f"Оставлены рядом с exe (критично для запуска): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
