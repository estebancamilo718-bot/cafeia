from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from torchvision.datasets import CIFAR10

from src.common import ROOT


PLANTVILLAGE_REPOSITORY = "https://github.com/spMohanty/PlantVillage-Dataset"
PLANTVILLAGE_API_ROOT = "https://api.github.com/repos/spMohanty/PlantVillage-Dataset/contents/raw/color"
PLANTVILLAGE_CLASSES = (
    "Apple___healthy",
    "Grape___healthy",
    "Potato___healthy",
    "Tomato___healthy",
    "Tomato___Spider_mites Two-spotted_spider_mite",
)
WIKIMEDIA_CATEGORIES = {
    "dog": "Golden Retriever",
    "cat": "Domestic cats",
    "car": "Sedans",
    "building": "Buildings",
    "cup": "Coffee cups",
}
GITHUB_OBJECT_SOURCES = (
    {
        "detail": "dog",
        "repository": "jigsawpieces/dog-api-images",
        "path": "labrador",
        "license": "GPL-3.0",
        "count": 25,
    },
    {
        "detail": "cat",
        "repository": "NotAShelf/catApi",
        "path": "images",
        "license": "MIT",
        "count": 25,
    },
)
OPENCV_OBJECT_FILES = (
    "HappyFish.jpg",
    "aero1.jpg",
    "aero3.jpg",
    "baboon.jpg",
    "basketball1.png",
    "basketball2.png",
    "blox.jpg",
    "board.jpg",
    "box.png",
    "box_in_scene.png",
    "building.jpg",
    "cards.png",
    "castle.jpg",
    "chessboard.png",
    "chicky_512.png",
    "gauge-1.jpg",
    "home.jpg",
    "lena.jpg",
    "licenseplate_motion.jpg",
    "messi5.jpg",
    "rubberwhale1.png",
    "rubberwhale2.png",
    "squirrel_cls.jpg",
    "starry_night.jpg",
    "sudoku.png",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_json(url: str):
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CafeIA-domain-audit"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "CafeIA-domain-audit"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def wikimedia_members(category: str) -> list[dict]:
    parameters = urllib.parse.urlencode(
        {
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": f"Category:{category}",
            "gcmnamespace": 6,
            "gcmtype": "file",
            "gcmlimit": 100,
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": 640,
            "format": "json",
            "formatversion": 2,
        }
    )
    payload = request_json(f"https://commons.wikimedia.org/w/api.php?{parameters}")
    members = []
    for page in payload.get("query", {}).get("pages", []):
        image_info = (page.get("imageinfo") or [{}])[0]
        mime = image_info.get("mime")
        if mime not in {"image/jpeg", "image/png"}:
            continue
        url = image_info.get("thumburl") or image_info.get("url")
        if not url:
            continue
        members.append(
            {
                "path": page["title"],
                "name": str(page["pageid"]),
                "download_url": url,
                "html_url": image_info.get("descriptionurl", ""),
                "mime": mime,
                "metadata": image_info.get("extmetadata", {}),
                "type": "file",
            }
        )
    return members


def github_members(repository: str, path: str) -> list[dict]:
    encoded_path = urllib.parse.quote(path, safe="/")
    return request_json(f"https://api.github.com/repos/{repository}/contents/{encoded_path}")


def deterministic_members(members: list[dict], count: int, seed: int) -> list[dict]:
    ranked = sorted(
        (member for member in members if member.get("type") == "file" and member.get("download_url")),
        key=lambda member: hashlib.sha256(f"{seed}:{member['path']}".encode()).hexdigest(),
    )
    if len(ranked) < count:
        raise RuntimeError(f"Solo hay {len(ranked)} archivos disponibles; se solicitaron {count}")
    return ranked[:count]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara negativos públicos separados para evaluar dominio")
    parser.add_argument("--output-dir", type=Path, default=Path("provenance/ood_benchmark"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--plantvillage-per-class", type=int, default=25)
    parser.add_argument("--cifar-per-class", type=int, default=25)
    parser.add_argument("--wikimedia-per-category", type=int, default=25)
    parser.add_argument("--skip-cifar", action="store_true")
    parser.add_argument("--skip-wikimedia", action="store_true")
    parser.add_argument("--include-github-objects", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reutiliza archivos ya descargados y completa solamente los faltantes.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()) and not args.resume:
        raise FileExistsError(f"La carpeta no está vacía: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    plant_dir = output_dir / "plantvillage"
    for class_name in PLANTVILLAGE_CLASSES:
        encoded = urllib.parse.quote(class_name, safe="")
        members = request_json(f"{PLANTVILLAGE_API_ROOT}/{encoded}?ref=master")
        selected = deterministic_members(members, args.plantvillage_per_class, args.seed)
        class_dir = plant_dir / class_name
        class_dir.mkdir(parents=True, exist_ok=True)
        for member in selected:
            destination = class_dir / member["name"]
            if destination.is_file():
                data = destination.read_bytes()
            else:
                data = download(member["download_url"])
                destination.write_bytes(data)
            rows.append(
                {
                    "path": destination.relative_to(ROOT).as_posix(),
                    "source": "plantvillage",
                    "category": "non_coffee_leaf",
                    "detail": class_name,
                    "original_id": member["path"],
                    "source_url": member["html_url"],
                    "sha256": sha256_bytes(data),
                    "license": "See PlantVillage repository",
                    "creator": "PlantVillage",
                }
            )

    if not args.skip_cifar:
        cifar_root = output_dir / "cifar10_download"
        cifar = CIFAR10(root=cifar_root, train=False, download=True)
        cifar_dir = output_dir / "cifar10"
        counters = {name: 0 for name in cifar.classes}
        for index, (image, class_index) in enumerate(cifar):
            class_name = cifar.classes[class_index]
            if counters[class_name] >= args.cifar_per_class:
                continue
            class_dir = cifar_dir / class_name
            class_dir.mkdir(parents=True, exist_ok=True)
            destination = class_dir / f"{index:05d}.png"
            if not destination.is_file():
                image.save(destination)
            data = destination.read_bytes()
            rows.append(
                {
                    "path": destination.relative_to(ROOT).as_posix(),
                    "source": "cifar10",
                    "category": "non_leaf_object",
                    "detail": class_name,
                    "original_id": f"test:{index}",
                    "source_url": "https://www.cs.toronto.edu/~kriz/cifar.html",
                    "sha256": sha256_bytes(data),
                    "license": "See source terms",
                    "creator": "",
                }
            )
            counters[class_name] += 1
            if all(value >= args.cifar_per_class for value in counters.values()):
                break

    if not args.skip_wikimedia:
        wikimedia_dir = output_dir / "wikimedia_commons"
        for detail, category in WIKIMEDIA_CATEGORIES.items():
            selected = deterministic_members(wikimedia_members(category), args.wikimedia_per_category, args.seed)
            detail_dir = wikimedia_dir / detail
            detail_dir.mkdir(parents=True, exist_ok=True)
            for member in selected:
                extension = ".jpg" if member["mime"] == "image/jpeg" else ".png"
                destination = detail_dir / f"{member['name']}{extension}"
                if destination.is_file():
                    data = destination.read_bytes()
                else:
                    data = download(member["download_url"])
                    destination.write_bytes(data)
                metadata = member["metadata"]
                rows.append(
                    {
                        "path": destination.relative_to(ROOT).as_posix(),
                        "source": "wikimedia_commons",
                        "category": "non_leaf_object",
                        "detail": detail,
                        "original_id": member["path"],
                        "source_url": member["html_url"],
                        "sha256": sha256_bytes(data),
                        "license": metadata.get("LicenseShortName", {}).get("value", "unknown"),
                        "creator": metadata.get("Artist", {}).get("value", "unknown"),
                    }
                )

    if args.include_github_objects:
        github_dir = output_dir / "github_objects"
        for source in GITHUB_OBJECT_SOURCES:
            members = github_members(source["repository"], source["path"])
            selected = deterministic_members(members, source["count"], args.seed)
            detail_dir = github_dir / source["detail"]
            detail_dir.mkdir(parents=True, exist_ok=True)
            for member in selected:
                destination = detail_dir / member["name"]
                if destination.is_file():
                    data = destination.read_bytes()
                else:
                    data = download(member["download_url"])
                    destination.write_bytes(data)
                rows.append(
                    {
                        "path": destination.relative_to(ROOT).as_posix(),
                        "source": "github_objects",
                        "category": "non_leaf_object",
                        "detail": source["detail"],
                        "original_id": member["path"],
                        "source_url": member["html_url"],
                        "sha256": sha256_bytes(data),
                        "license": source["license"],
                        "creator": source["repository"],
                    }
                )

        opencv_members = {
            member["name"]: member for member in github_members("opencv/opencv", "samples/data")
        }
        missing = sorted(set(OPENCV_OBJECT_FILES) - set(opencv_members))
        if missing:
            raise RuntimeError(f"Faltan archivos esperados de OpenCV: {missing}")
        detail_dir = github_dir / "mixed_objects"
        detail_dir.mkdir(parents=True, exist_ok=True)
        for name in OPENCV_OBJECT_FILES:
            member = opencv_members[name]
            destination = detail_dir / name
            if destination.is_file():
                data = destination.read_bytes()
            else:
                data = download(member["download_url"])
                destination.write_bytes(data)
            rows.append(
                {
                    "path": destination.relative_to(ROOT).as_posix(),
                    "source": "github_objects",
                    "category": "non_leaf_object",
                    "detail": "mixed_objects",
                    "original_id": member["path"],
                    "source_url": member["html_url"],
                    "sha256": sha256_bytes(data),
                    "license": "Apache-2.0",
                    "creator": "opencv/opencv",
                }
            )

    manifest_path = output_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path",
                "source",
                "category",
                "detail",
                "original_id",
                "source_url",
                "sha256",
                "license",
                "creator",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    metadata = {
        "seed": args.seed,
        "plantvillage_repository": PLANTVILLAGE_REPOSITORY,
        "plantvillage_classes": list(PLANTVILLAGE_CLASSES),
        "plantvillage_per_class": args.plantvillage_per_class,
        "cifar10_source": "https://www.cs.toronto.edu/~kriz/cifar.html",
        "cifar10_per_class": args.cifar_per_class,
        "cifar10_included": not args.skip_cifar,
        "wikimedia_commons_api": "https://commons.wikimedia.org/w/api.php",
        "wikimedia_categories": WIKIMEDIA_CATEGORIES,
        "wikimedia_per_category": args.wikimedia_per_category,
        "wikimedia_included": not args.skip_wikimedia,
        "github_objects_included": args.include_github_objects,
        "github_object_sources": GITHUB_OBJECT_SOURCES,
        "opencv_object_files": list(OPENCV_OBJECT_FILES),
        "total": len(rows),
        "purpose": "local development evaluation only; files are excluded from Git",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
