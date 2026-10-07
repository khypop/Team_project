class FSRCNN_Upscaler {
    constructor(sourceVideoId, outputCanvasId, modelUrl) {
        this.video = document.getElementById(sourceVideoId);
        this.canvas = document.getElementById(outputCanvasId);
        this.modelUrl = modelUrl;
        this.model = null;
        this.isRunning = false;
        this.animationId = null;
    }

    // 1. 모델 로드 (초기화)
    async init() {
        console.log("🚀 FSRCNN 모델 로딩 중...");
        try {
            // TensorFlow.js 로드 확인
            if (typeof tf === 'undefined') throw new Error("TensorFlow.js가 로드되지 않았습니다.");

            this.model = await tf.loadLayersModel(this.modelUrl);
            
            // 웜업 (첫 실행 렉 방지)
            const dummy = tf.zeros([1, 270, 480, 3]);
            this.model.predict(dummy).dispose();
            dummy.dispose();

            console.log("✅ 모델 로드 완료! (GPU 가속 활성화)");
            return true;
        } catch (e) {
            console.error("❌ 모델 로드 실패:", e);
            return false;
        }
    }

    // 2. 업스케일링 시작
    start() {
        if (!this.model) {
            console.warn("모델이 로드되지 않았습니다.");
            return;
        }
        this.isRunning = true;
        this.processFrame();
        console.log("▶ 업스케일링 시작");
    }

    // 3. 실시간 프레임 처리 루프
    async processFrame() {
        if (!this.isRunning) return;

        // 비디오가 재생 중일 때만 처리
        if (this.video.readyState >= 2) { 
            tf.tidy(() => { // 메모리 자동 정리 (매우 중요)
                // (1) 비디오에서 픽셀 가져오기 (GPU Texture)
                const img = tf.browser.fromPixels(this.video);
                
                // (2) 전처리: 0~255 정수 -> 0.0~1.0 소수 변환 & 차원 추가
                const input = img.expandDims(0).toFloat().div(255.0);

                // (3) AI 추론 (FSRCNN)
                const output = this.model.predict(input);

                // (4) 후처리: 0.0~1.0 -> 0~255 변환 & 캔버스 그리기
                // clipByValue: 0보다 작거나 255보다 큰 이상한 값 자르기
                const finalImg = output.mul(255.0).clipByValue(0, 255).toInt().squeeze(0);
                
                tf.browser.toPixels(finalImg, this.canvas);
            });
        }

        // 다음 프레임 요청 (무한 반복)
        this.animationId = requestAnimationFrame(() => this.processFrame());
    }

    // 4. 중지
    stop() {
        this.isRunning = false;
        if (this.animationId) cancelAnimationFrame(this.animationId);
        console.log("⏹ 업스케일링 중지");
    }
}