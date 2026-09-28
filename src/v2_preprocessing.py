"""Preprocesamiento explícito del experimento pareado CaféIA v2.

No modifica ``src.common.transform``: la versión 1 y el backend activo siguen
usando su procedimiento original hasta que exista una decisión posterior.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image
from torchvision import transforms
from torchvision.transforms import InterpolationMode
from torchvision.transforms import functional as vision_functional


TARGET_SIZE = 224
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
PADDING_RGB = (124, 116, 104)
VARIANTS = ("control", "candidate")


@dataclass(frozen=True)
class AspectPadToSquare:
    """Escala el lado mayor y centra la imagen sobre un lienzo cuadrado."""

    size: int = TARGET_SIZE
    fill: tuple[int, int, int] = PADDING_RGB

    def geometry(self, width: int, height: int) -> dict[str, object]:
        if width < 1 or height < 1:
            raise ValueError(f"Dimensiones inválidas: {width}x{height}")
        scale = self.size / max(width, height)
        resized_width = max(1, min(self.size, round(width * scale)))
        resized_height = max(1, min(self.size, round(height * scale)))
        horizontal_remainder = self.size - resized_width
        vertical_remainder = self.size - resized_height
        left = horizontal_remainder // 2
        right = horizontal_remainder - left
        top = vertical_remainder // 2
        bottom = vertical_remainder - top
        return {
            "input_size": [width, height],
            "scale": scale,
            "resized_size": [resized_width, resized_height],
            "padding_left_top_right_bottom": [left, top, right, bottom],
            "output_size": [self.size, self.size],
        }

    def __call__(self, image: Image.Image) -> Image.Image:
        geometry = self.geometry(*image.size)
        resized_width, resized_height = geometry["resized_size"]
        resized = vision_functional.resize(
            image,
            [resized_height, resized_width],
            interpolation=InterpolationMode.BILINEAR,
            antialias=True,
        )
        return vision_functional.pad(
            resized,
            geometry["padding_left_top_right_bottom"],
            fill=self.fill,
            padding_mode="constant",
        )


def geometry_transform(variant: str):
    if variant == "control":
        return transforms.Resize(
            (TARGET_SIZE, TARGET_SIZE),
            interpolation=InterpolationMode.BILINEAR,
            antialias=True,
        )
    if variant == "candidate":
        return AspectPadToSquare()
    raise ValueError(f"Variante desconocida: {variant}")


def build_transform(variant: str, training: bool):
    operations = [geometry_transform(variant)]
    if training:
        operations.extend(
            [
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomRotation(
                    degrees=15,
                    interpolation=InterpolationMode.NEAREST,
                    expand=False,
                    fill=0,
                ),
            ]
        )
    operations.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    return transforms.Compose(operations)


def preprocessing_config(variant: str) -> dict[str, object]:
    common = {
        "orientation": "ImageOps.exif_transpose",
        "color_mode": "RGB",
        "target_tensor_shape_channels_height_width": [3, TARGET_SIZE, TARGET_SIZE],
        "resize_interpolation": "InterpolationMode.BILINEAR",
        "resize_antialias": True,
        "training_operations_after_geometry": [
            "RandomHorizontalFlip(p=0.5)",
            "RandomRotation(degrees=15, interpolation=NEAREST, expand=False, fill=0)",
        ],
        "validation_augmentation": False,
        "tensor_conversion": "ToTensor",
        "normalization_mean": list(IMAGENET_MEAN),
        "normalization_std": list(IMAGENET_STD),
        "complete_order": [
            "EXIF transpose",
            "RGB",
            "geometry",
            "RandomHorizontalFlip(p=0.5) [TRAIN only]",
            "RandomRotation(15 degrees) [TRAIN only]",
            "ToTensor",
            "Normalize(ImageNet mean/std)",
        ],
        "implementation": "src.v2_preprocessing.build_transform",
    }
    if variant == "control":
        return {
            "id": "cafeia-v2-control-stretch-224-v1",
            "variant": variant,
            **common,
            "geometry": {
                "method": "direct resize; aspect ratio not preserved",
                "output_size_width_height": [TARGET_SIZE, TARGET_SIZE],
                "padding": None,
            },
        }
    if variant == "candidate":
        return {
            "id": "cafeia-v2-aspect-pad-224-v1",
            "variant": variant,
            **common,
            "geometry": {
                "method": "scale longest side to 224, preserve aspect ratio, center on square",
                "dimension_rounding": "Python round after multiplying both dimensions by 224 / max(width, height)",
                "padding_mode": "constant",
                "padding_color_rgb": list(PADDING_RGB),
                "padding_position": "center; left/top=floor(remainder/2), right/bottom receive remainder",
                "output_size_width_height": [TARGET_SIZE, TARGET_SIZE],
            },
        }
    raise ValueError(f"Variante desconocida: {variant}")
