import ctypes
import numpy as np
import os

class Engine:
    def __init__(self, dll_path, model_path):
        try:
            dll_path = os.path.abspath(dll_path)
            self.lib = ctypes.CDLL(dll_path)
            print(f"Successfully loaded DLL from {dll_path}")
        except OSError as e:
            print(f"Failed to load DLL: {e}")
            self.lib = None
            return
        
        self.lib.create_engine.argtypes = [ctypes.c_char_p]

        self.lib.RunInference.argtypes = [
            np.ctypeslib.ndpointer(dtype=np.float32, flags='C_CONTIGUOUS'), # 입력 배열
            np.ctypeslib.ndpointer(dtype=np.float32, flags='C_CONTIGUOUS'), # 출력 배열
            ctypes.c_int, # 높이
            ctypes.c_int  # 너비
        ]

        model_pathe_bytes = model_path.encode('utf-8')
        self.lib.Initmodel(model_pathe_bytes)
        print(f"Model initialized")

    def process(self, img_y):
        if not self.lib:
            print("DLL not loaded. Cannot process image.")
            return img_y
        
        h, w = img_y.shape
        input_data = np.ascontiguousarray(img_y.astype(np.float32)/255.0)
        output_data = np.ascontiguousarray(np.zeros((h*2, w*2), dtype=np.float32))

        self.lib.RunInference(input_data, output_data, h, w)

        result = (output_data * 255.0).clip(0, 255).astype(np.uint8)

        return result