import tensorflow as tf
import keras
from keras import layers, models
import tf2onnx
import onnx

def build_fsrcnn(scale=2, d=56, s=12, m=4):
    inputs = keras.Input(shape=(None, None, 3), name="input_image")
    
    x = layers.Conv2D(d, (5, 5), padding='same', activation='relu')(inputs)
    x = layers.Conv2D(s, (1, 1), padding='same', activation='relu')(x)
    for _ in range(m):
        x = layers.Conv2D(s, (3, 3), padding='same', activation='relu')(x)
    x = layers.Conv2D(d, (1, 1), padding='same', activation='relu')(x)
    outputs = layers.Conv2DTranspose(3, (9, 9), strides=scale, padding='same', name="output_image")(x)
    
    return models.Model(inputs, outputs, name="FSRCNN")