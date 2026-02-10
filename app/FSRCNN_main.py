import torch.nn as nn
import math

class FSRCNN(nn.Module):
    def __init__(self, scale_factor, num_channels=1, d=56, s=12, m=4):
        super(FSRCNN, self).__init__()
        
        self.feature_extraction = nn.Sequential(
            nn.Conv2d(num_channels, d, kernel_size=5, padding=5//2),
            nn.PReLU(d)
        )
        
        self.shrinking = nn.Sequential(
            nn.Conv2d(d, s, kernel_size=1, padding=0),
            nn.PReLU(s)
        )
        
        mapping_layers = []
        for _ in range(m):
            mapping_layers.extend([
                nn.Conv2d(s, s, kernel_size=3, padding=3//2),
                nn.PReLU(s)
            ])
        self.mapping = nn.Sequential(*mapping_layers)
        
        self.expanding = nn.Sequential(
            nn.Conv2d(s, d, kernel_size=1, padding=0),
            nn.PReLU(d)
        )
        
        self.deconvolution = nn.ConvTranspose2d(d, num_channels, 
                                                kernel_size=9, 
                                                stride=scale_factor, 
                                                padding=9//2,
                                                output_padding=scale_factor-1)
        
        self._initialize_weights()

    def forward(self, x):
        x = self.feature_extraction(x)
        x = self.shrinking(x)
        x = self.mapping(x)
        x = self.expanding(x)
        x = self.deconvolution(x)
        return x

    # 가중치 초기화 함수 정의
    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight.data, a=0, mode='fan_in', nonlinearity='relu')
                if m.bias is not None:
                    m.bias.data.zero_()
            
            elif isinstance(m, nn.ConvTranspose2d):
                nn.init.normal_(m.weight.data, mean=0.0, std=0.001)
                if m.bias is not None:
                    m.bias.data.zero_()