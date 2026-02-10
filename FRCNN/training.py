from FSRCNN_main import FSRCNN
from data import SRDataset
import torch
from torch.utils.data import DataLoader
import torch.optim as optim
import torch.nn as nn
import math
import os
from torch.optim.lr_scheduler import StepLR

current_dir = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 1. 하이퍼파라미터 설정
# ==========================================
BATCH_SIZE = 32
LEARNING_RATE = 1e-4
EPOCHS = 500
SCALE_FACTOR = 2  # 2배 확대
TRAIN_IMG_DIR = os.path.join(current_dir, "train_images")

#GPU 사용 설정
#device = torch.device("cpu")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

try:
    train_dataset = SRDataset(TRAIN_IMG_DIR, scale_factor=SCALE_FACTOR, crop_size=96)
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0) # Windows에선 num_workers=0 권장
except Exception as e:
    print(f"데이터셋 로드 실패: {e}")
    print("현재 경로에 'train_images' 폴더가 있는지, 안에 이미지가 있는지 확인해주세요.")
    train_loader = None

model = FSRCNN(scale_factor=SCALE_FACTOR).to(device)

criterion = nn.L1Loss() 

optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

def calculate_psnr(img1, img2):
    mse = nn.functional.mse_loss(img1, img2)
    if mse == 0:
        return 100
    return 10 * math.log10(1. / mse.item())

if train_loader:
    print("학습 시작...")
    model.train()
    
    for epoch in range(EPOCHS):
        epoch_loss = 0
        epoch_psnr = 0
        
        for i, (lr_imgs, hr_imgs) in enumerate(train_loader):
            lr_imgs = lr_imgs.to(device)
            hr_imgs = hr_imgs.to(device)
            
            # Forward
            outputs = model(lr_imgs)
            loss = criterion(outputs, hr_imgs)
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            epoch_psnr += calculate_psnr(outputs, hr_imgs)
            
        # 에포크마다 로그 출력
        avg_loss = epoch_loss / len(train_loader)
        avg_psnr = epoch_psnr / len(train_loader)
        
        print(f"Epoch [{epoch+1}/{EPOCHS}] Loss: {avg_loss:.6f} | PSNR: {avg_psnr:.2f}dB")
        
        if (epoch+1) == EPOCHS:
            torch.save(model.state_dict(), f"fsrcnn_x{SCALE_FACTOR}.pth")

    print("학습 완료!")