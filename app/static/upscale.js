class FSRCNN_Upscaler {
    constructor(sourceVideoId, outputCanvasId, modelUrl) {
        this.video = document.getElementById(sourceVideoId);
        this.canvas = document.getElementById(outputCanvasId);
        this.ctx = this.canvas.getContext('2d');
        this.modelUrl = modelUrl;
        this.session = null;
        this.isRunning = false;
        this.animationId = null;
    }

    // 1. 모델 로드 (ONNX Runtime)
    async init() {
        console.log("🚀 FSRCNN 모델 로딩 중...");
        try {
            if (typeof ort === 'undefined') throw new Error("ONNX Runtime이 로드되지 않았습니다.");
            
            // WebGL 가속 사용
            this.session = await ort.InferenceSession.create(this.modelUrl, {
                executionProviders: ['webgl']
            });
            console.log("✅ 모델 로드 완료!");
            return true;
        } catch (e) {
            console.error("❌ 로드 실패:", e);
            return false;
        }
    }

    // 2. 원격 스트림 연결 (원격 제어 코드에서 호출할 것)
    async setRemoteStream(stream) {
        console.log("📡 원격 스트림 수신됨");
        this.video.srcObject = stream;
        return new Promise((resolve) => {
            this.video.onloadedmetadata = () => {
                this.video.play();
                resolve();
            };
        });
    }

    // 3. 실행 루프
    async processFrame() {
        if (!this.isRunning) return;

        // 비디오 프레임이 준비되었을 때만 실행
        if (this.video.readyState >= 2) {
            const width = this.video.videoWidth;
            const height = this.video.videoHeight;

            // 원격 화면 캡처용 임시 캔버스
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = width;
            tempCanvas.height = height;
            const tempCtx = tempCanvas.getContext('2d');
            tempCtx.drawImage(this.video, 0, 0);
            
            const imgData = tempCtx.getImageData(0, 0, width, height);

            // 전처리 (Y채널 추출)
            const inputData = new Float32Array(width * height);
            for (let i = 0; i < imgData.data.length; i += 4) {
                inputData[i / 4] = (0.299 * imgData.data[i] + 0.587 * imgData.data[i+1] + 0.114 * imgData.data[i+2]) / 255.0;
            }

            // ONNX 추론
            const inputTensor = new ort.Tensor('float32', inputData, [1, 1, height, width]);
            const feeds = { [this.session.inputNames[0]]: inputTensor };
            const results = await this.session.run(feeds);
            const output = results[this.session.outputNames[0]];

            // 결과 렌더링 (2배 확대)
            this.render(output, width * 2, height * 2);
        }
        this.animationId = requestAnimationFrame(() => this.processFrame());
    }

    render(tensor, w, h) {
        this.canvas.width = w;
        this.canvas.height = h;
        const data = tensor.data;
        const img = this.ctx.createImageData(w, h);
        for (let i = 0; i < data.length; i++) {
            const val = Math.min(Math.max(data[i] * 255, 0), 255);
            const idx = i * 4;
            img.data[idx] = img.data[idx+1] = img.data[idx+2] = val;
            img.data[idx+3] = 255;
        }
        this.ctx.putImageData(img, 0, 0);
    }

    start() {
        this.isRunning = true;
        this.processFrame();
    }
}