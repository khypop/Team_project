import FSRCNN_main as FSRCNN
import data as SRDataset
import torch
from torch.utils.data import DataLoader
import torch.optim as optim
import torch.nn as nn
import math

# ==========================================
# 1. 하이퍼파라미터 설정
# ==========================================
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
EPOCHS = 100
SCALE_FACTOR = 2  # 2배 확대
TRAIN_IMG_DIR = "./train_images" # 이미지가 들어있는 폴더 경로 (미리 생성 필요)

# GPU 설정 (CUDA 없으면 CPU 사용)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# ==========================================
# 2. 데이터 로더 준비
# ==========================================
# 실제 사용시엔 "./train_images" 폴더를 만들고 안에 사진을 넣어주세요.
# 테스트를 위해 코드를 돌리려면 폴더와 이미지가 반드시 있어야 합니다.
try:
    train_dataset = SRDataset(TRAIN_IMG_DIR, scale_factor=SCALE_FACTOR, crop_size=96)
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0) # Windows에선 num_workers=0 권장
except Exception as e:
    print(f"데이터셋 로드 실패: {e}")
    print("현재 경로에 'train_images' 폴더가 있는지, 안에 이미지가 있는지 확인해주세요.")
    train_loader = None

# ==========================================
# 3. 모델, 손실함수, 최적화함수 생성
# ==========================================
# 앞서 작성하신 FSRCNN 클래스가 정의되어 있다고 가정합니다.
model = FSRCNN(scale_factor=SCALE_FACTOR).to(device)

# Loss: MSE보다는 L1 Loss가 사람이 보기에 더 선명함
criterion = nn.L1Loss() 

# Optimizer: Adam이 무난하게 성능이 좋음
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

# ==========================================
# 4. PSNR 계산 함수 (성능 평가용)
# ==========================================
def calculate_psnr(img1, img2):
    mse = nn.functional.mse_loss(img1, img2)
    if mse == 0:
        return 100
    return 10 * math.log10(1. / mse.item())

# ==========================================
# 5. 학습 루프 시작
# ==========================================
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
        
        # (선택) 모델 저장 - 10 에포크마다
        if (epoch + 1) % 10 == 0:
            torch.save(model.state_dict(), f"fsrcnn_x{SCALE_FACTOR}_epoch{epoch+1}.pth")

    print("학습 완료!")