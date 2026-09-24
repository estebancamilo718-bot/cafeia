import csv
from pathlib import Path
import torch
from torch import nn
from torch.utils.data import Dataset
from torchvision import models, transforms
from PIL import Image, ImageOps
ROOT = Path(__file__).resolve().parents[1]

def read_rows():
    with (ROOT / 'data/processed/manifest.csv').open(encoding='utf-8') as f:
        return list(csv.DictReader(f))

def transform(training=False):
    ops = [transforms.Resize((224, 224))]
    if training:
        ops += [transforms.RandomHorizontalFlip(), transforms.RandomRotation(15)]
    return transforms.Compose(ops + [transforms.ToTensor(), transforms.Normalize(
        [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

class Leaves(Dataset):
    def __init__(self, rows, classes, training=False):
        self.rows, self.classes, self.tf = rows, classes, transform(training)
    def __len__(self):
        return len(self.rows)
    def __getitem__(self, i):
        r = self.rows[i]
        with Image.open(ROOT / r['path']) as im:
            x = self.tf(ImageOps.exif_transpose(im).convert('RGB'))
        return x, self.classes.index(r['label'])

def build(name, n, pretrained=False):
    if name == 'cnn':
        return nn.Sequential(nn.Conv2d(3,16,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(16,32,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(32,64,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),nn.Dropout(0.2),nn.Linear(64,n))
    if name == 'mobilenet':
        m = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None)
        for p in m.parameters(): p.requires_grad = False
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features,n)
        return m
    if name == 'resnet18':
        m = models.resnet18(weights=models.ResNet18_Weights.DEFAULT if pretrained else None)
        for p in m.parameters(): p.requires_grad = False
        m.fc = nn.Linear(m.fc.in_features,n)
        return m
    raise ValueError(name)

def load_checkpoint(path):
    ck = torch.load(path, map_location='cpu', weights_only=True)
    m = build(ck['model'], len(ck['classes']))
    m.load_state_dict(ck['state_dict']); m.eval()
    return m, ck
