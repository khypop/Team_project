import os
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import random

class SRDataset(Dataset):
    def __init__(self, image_dir, scale_factor=2, crop_size=144):
        """
        Args:
            image_dir (str): 학습 이미지가 있는 폴더 경로
            scale_factor (int): 확대 배율 (예: 2, 3, 4)
            crop_size (int): HR 이미지에서 잘라낼 패치 크기 (scale_factor의 배수여야 함)
        """
        self.image_filenames = [os.path.join(image_dir, x) for x in os.listdir(image_dir) if x.lower().endswith(('.png', '.jpg', '.jpeg'))]
        self.scale_factor = scale_factor
        self.crop_size = crop_size
        
        # 기본 텐서 변환기
        self.to_tensor = transforms.ToTensor()

    def __getitem__(self, index):
        # 1. 이미지 불러오기 및 YCbCr 변환
        img = Image.open(self.image_filenames[index]).convert('YCbCr')
        y, _, _ = img.split() # Y 채널만 사용 (흑백 정보)

        # 2. Random Crop (고해상도 원본에서 패치 자르기)
        # 이미지 크기가 crop_size보다 작으면 그대로 사용 (패딩 처리 등은 생략)
        w, h = y.size
        if w >= self.crop_size and h >= self.crop_size:
            left = random.randint(0, w - self.crop_size)
            top = random.randint(0, h - self.crop_size)
            hr_patch = y.crop((left, top, left + self.crop_size, top + self.crop_size))
        else:
            hr_patch = y # 이미지가 너무 작으면 원본 그대로 (배치 처리시 에러 날 수 있으니 큰 이미지 권장)

        # 3. Data Augmentation (과대적합 방지)
        # 랜덤 회전 및 대칭
        if random.random() < 0.5:
            hr_patch = hr_patch.transpose(Image.FLIP_LEFT_RIGHT)
        if random.random() < 0.5:
            hr_patch = hr_patch.transpose(Image.ROTATE_90)

        # 4. LR(저해상도) 이미지 생성
        # HR을 scale_factor만큼 줄여서 LR을 만듦 (Downsampling)
        lr_size = self.crop_size // self.scale_factor
        lr_patch = hr_patch.resize((lr_size, lr_size), resample=Image.BICUBIC)

        # 5. 텐서 변환 및 반환
        return self.to_tensor(lr_patch), self.to_tensor(hr_patch)

    def __len__(self):
        return len(self.image_filenames)