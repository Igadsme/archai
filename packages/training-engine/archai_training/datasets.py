from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageDatasetConfig:
    name: str
    root: str
    validation_fraction: float = 0.1
    download: bool = False
    seed: int = 0


def build_image_datasets(config: ImageDatasetConfig):
    """Build train/validation/test datasets; downloads are never implicit."""
    try:
        import torch
        from torchvision import datasets, transforms
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install torchvision and the 'ml' extra for image datasets") from exc
    if not 0 < config.validation_fraction < 1:
        raise ValueError("validation_fraction must be between zero and one")
    if config.name == "cifar10":
        dataset_type, classes = datasets.CIFAR10, 10
    elif config.name == "cifar100":
        dataset_type, classes = datasets.CIFAR100, 100
    else:
        raise ValueError("supported image datasets are cifar10 and cifar100")
    transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5,) * 3, (0.5,) * 3)])
    train_full = dataset_type(config.root, train=True, transform=transform, download=config.download)
    test = dataset_type(config.root, train=False, transform=transform, download=config.download)
    validation_size = max(1, int(len(train_full) * config.validation_fraction))
    train_size = len(train_full) - validation_size
    train, validation = torch.utils.data.random_split(train_full, [train_size, validation_size],
                                                       generator=torch.Generator().manual_seed(config.seed))
    return {"train": train, "validation": validation, "test": test, "classes": classes}
