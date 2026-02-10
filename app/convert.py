import torch
import torch.onnx
from FSRCNN_main import FSRCNN  # 작성하신 모델 파일 불러오기

# ==========================================
# 사용자 설정
# ==========================================
SCALE_FACTOR = 2
PTH_FILE_PATH = 'C:\\Users\\user1\\Desktop\\smj_test\\app\\web_model\\fsrcnn_x2_epoch20.pth'  # 학습된 가중치 파일명 (정확히 입력!)
ONNX_FILE_PATH = "fsrcnn_x2.onnx" # 저장될 파일명

def convert():
    print(f"🔄 Loading model from {PTH_FILE_PATH}...")
    
    # 1. 모델 초기화 (학습할 때와 똑같은 옵션이어야 함)
    # 만약 Lite 모델을 학습했다면 d=32, s=5, m=1 등으로 바꿔야 합니다.
    model = FSRCNN(scale_factor=SCALE_FACTOR)
    
    # 2. 가중치 로드
    # map_location='cpu' : GPU에서 학습했더라도 변환은 CPU에서 하는 게 안전함
    try:
        model.load_state_dict(torch.load(PTH_FILE_PATH, map_location='cpu', weights_only=True))
    except FileNotFoundError:
        print(f"❌ 오류: '{PTH_FILE_PATH}' 파일을 찾을 수 없습니다.")
        return

    model.eval() # 평가 모드 전환 (필수!)

    # 3. 더미 입력 데이터 생성
    # (배치크기 1, 채널 1, 높이, 너비) - 크기는 아무거나 상관없음 (동적 축 때문)
    dummy_input = torch.randn(1, 1, 240, 426) 

    print("🔄 Exporting to ONNX...")

    # 4. ONNX 추출 (Export)
    torch.onnx.export(
        model,                      # 실행될 모델
        dummy_input,                # 모델 입력값 (차원 감지용)
        ONNX_FILE_PATH,             # 저장 경로
        export_params=True,         # 가중치 포함 여부
        opset_version=11,           # 호환성 좋은 버전
        do_constant_folding=True,   # 상수 폴딩 최적화
        input_names=['input'],      # 입력 노드 이름 (나중에 중요!)
        output_names=['output'],    # 출력 노드 이름
        dynamic_axes={
            'input': {2: 'height', 3: 'width'},  # 높이(2), 너비(3)는 변해도 됨
            'output': {2: 'height', 3: 'width'}
        }
    )

    print(f"✅ 변환 완료! 파일 생성됨: {ONNX_FILE_PATH}")
    print("   이 파일을 client.exe 만들 때 같이 포함시키세요.")

if __name__ == "__main__":
    convert()