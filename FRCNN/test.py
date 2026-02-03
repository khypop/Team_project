import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from FSRCNN_main import FSRCNN
import torchvision.transforms as transforms
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
# ==========================================
# 사용자 설정
# ==========================================
IMG_PATH = os.path.join(current_dir, "test_image.png")           # 테스트할 원본 고화질 이미지
MODEL_PATH = os.path.join(current_dir, "fsrcnn_x2_epoch200.pth") # 학습된 모델 파일 경로
SCALE_FACTOR = 2                      # 학습할 때 썼던 배율 (2배)
# ==========================================

def run_visualization():
    # 1. 장치 설정
    device = torch.device("cpu")
    #device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 2. 이미지 및 모델 로드
    if not os.path.exists(IMG_PATH):
        print(f"이미지 파일({IMG_PATH})이 없습니다.")
        return
        
    # 모델 준비
    model = FSRCNN(scale_factor=SCALE_FACTOR).to(device)
    try:
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    except:
        print(f"모델 파일({MODEL_PATH})을 찾을 수 없거나 경로가 잘못되었습니다.")
        return
    model.eval()

    # 3. 이미지 전처리 (HR -> LR 생성)
    # 원본(HR) 로드
    hr_img = Image.open(IMG_PATH).convert('YCbCr')
    hr_y, hr_cb, hr_cr = hr_img.split()
    
    # 원본 크기 구하기
    w, h = hr_img.size
    
    # 강제로 축소해서 LR(Low Resolution) 이미지 생성 (이게 '축소 후' 이미지)
    new_w, new_h = w // SCALE_FACTOR, h // SCALE_FACTOR
    lr_img = hr_img.resize((new_w, new_h), Image.BICUBIC) # 축소
    lr_y, lr_cb, lr_cr = lr_img.split() # LR의 Y, Cb, Cr 분리

    # 4. 모델 예측 (FSRCNN 적용)
    to_tensor = transforms.ToTensor()
    input_y = to_tensor(lr_y).unsqueeze(0).to(device) # (1, 1, h, w)

    with torch.no_grad():
        pred_y = model(input_y)

    # 5. 결과 후처리 (Tensor -> Image)
    pred_y = pred_y.cpu().squeeze(0).squeeze(0).numpy()
    pred_y = pred_y * 255.0
    pred_y = pred_y.clip(0, 255).astype(np.uint8)
    pred_y_img = Image.fromarray(pred_y, mode='L')

    # 색상 정보(Cb, Cr)는 AI가 아닌 일반 확대(Bicubic)로 크기만 맞춤
    # (FSRCNN은 흑백 형태만 학습했으므로 색상은 단순 확대로 합침)
    final_cb = lr_cb.resize(pred_y_img.size, Image.BICUBIC)
    final_cr = lr_cr.resize(pred_y_img.size, Image.BICUBIC)
    
    # 합치기
    fsr_result = Image.merge('YCbCr', [pred_y_img, final_cb, final_cr]).convert('RGB')
    
    # 비교를 위해 원본, LR도 RGB로 변환
    hr_rgb = hr_img.convert('RGB')
    lr_rgb = lr_img.convert('RGB')

    # 비교를 위해 '일반 확대(Bicubic)' 버전도 하나 만듦 (AI 성능 체감용)
    bicubic_result = lr_rgb.resize(hr_rgb.size, Image.BICUBIC)

    # ==========================================
    # 6. 결과 시각화 (Matplotlib)
    # ==========================================
    plt.figure(figsize=(15, 5))

    # 첫 번째: 원본 (High Resolution)
    plt.subplot(1, 4, 1)
    plt.title("1. Original (HR)")
    plt.imshow(hr_rgb)
    plt.axis('off')

    # 두 번째: 축소된 이미지 (Low Resolution)
    plt.subplot(1, 4, 2)
    plt.title(f"2. Input (LR) x{1/SCALE_FACTOR}")
    plt.imshow(lr_rgb)
    plt.axis('off') # 작은 크기 그대로 보여줌

    # 세 번째: 일반 확대 (Bicubic) - 비교용
    plt.subplot(1, 4, 3)
    plt.title("3. Bicubic (Standard Upscale)")
    plt.imshow(bicubic_result)
    plt.axis('off')

    # 네 번째: FSRCNN 결과
    plt.subplot(1, 4, 4)
    plt.title("4. FSRCNN (AI Result)")
    plt.imshow(fsr_result)
    plt.axis('off')

    plt.show() # 창 띄우기

if __name__ == "__main__":
    run_visualization()