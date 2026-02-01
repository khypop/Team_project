import torch.nn as nn

#nn.Module을 상속받아 FSRCNN 모델 정의
class FSRCNN(nn.Module):
    def __init__(self, scale_factor, num_channels=1, d=56, s=12, m=4):
        super(FSRCNN, self).__init__()
        
        # 1. Feature Extraction
        self.feature_extraction = nn.Sequential(
            nn.Conv2d(num_channels, d, kernel_size=5, padding=5//2),
            nn.PReLU(d)
        )
        
        # 2. Shrinking
        self.shrinking = nn.Sequential(
            nn.Conv2d(d, s, kernel_size=1, padding=0),
            nn.PReLU(s)
        )
        
        # 3. Mapping (m개의 레이어)
        mapping_layers = []
        for _ in range(m):
            mapping_layers.extend([
                nn.Conv2d(s, s, kernel_size=3, padding=3//2),
                nn.PReLU(s)
            ])
        self.mapping = nn.Sequential(*mapping_layers)
        
        # 4. Expanding
        self.expanding = nn.Sequential(
            nn.Conv2d(s, d, kernel_size=1, padding=0),
            nn.PReLU(d)
        )
        
        # 5. Deconvolution (Upsampling)
        # stride=scale_factor가 핵심입니다.
        self.deconvolution = nn.ConvTranspose2d(d, num_channels, 
                                                kernel_size=9, 
                                                stride=scale_factor, 
                                                padding=9//2,
                                                output_padding=scale_factor-1) 
                                                # output_padding은 차원 계산 필요

    def forward(self, x):
        x = self.feature_extraction(x)
        x = self.shrinking(x)
        x = self.mapping(x)
        x = self.expanding(x)
        x = self.deconvolution(x)
        return x