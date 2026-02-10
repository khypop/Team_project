import torch
print(torch.__version__)
print(torch.cuda.is_available())  # True가 나와야 함
print(torch.cuda.get_device_name(0)) # GeForce RTX 5070이 나와야 함