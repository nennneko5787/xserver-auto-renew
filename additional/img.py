from PIL.ImageFilter import UnsharpMask
from PIL import Image, ImageOps, ImageEnhance
import io
import numpy as np


# 純黒ピクセル (#000000) を白 (#ffffff) に置き換える
def processImageReplaceBlackAndThicken(buffer: bytes) -> bytes:
    image = Image.open(io.BytesIO(buffer)).convert("RGB")
    data = np.array(image)

    # 純黒を白に置き換え
    mask = (data[:, :, 0] == 0) & (data[:, :, 1] == 0) & (data[:, :, 2] == 0)
    data[mask] = [255, 255, 255]

    result = Image.fromarray(data)
    outputBuffer = io.BytesIO()
    result.save(outputBuffer, format="PNG")
    return outputBuffer.getvalue()


# 白背景用の画像処理
def processImageWithJimpWhiteBackground(buffer: bytes) -> bytes:
    image = Image.open(io.BytesIO(buffer)).convert("RGB")
    data = np.array(image)

    # 明度計算
    brightness = data.mean(axis=2)

    # 暗いピクセル → 黒、明るいピクセル → 白
    bw = np.where(brightness < 150, 0, 255).astype(np.uint8)
    result = np.stack([bw, bw, bw], axis=2)

    processedImage = Image.fromarray(result)
    processedImage = processedImage.resize((300, 90), Image.Resampling.LANCZOS)
    processedImage = processedImage.convert("L")
    processedImage = ImageOps.autocontrast(processedImage)
    processedImage = ImageEnhance.Contrast(processedImage).enhance(1.3)

    outputBuffer = io.BytesIO()
    processedImage.save(outputBuffer, format="PNG")
    return outputBuffer.getvalue()


# 黒背景用の画像処理
def processImageWithJimpBlackBackground(buffer: bytes) -> bytes:
    image = Image.open(io.BytesIO(buffer)).convert("RGB")
    data = np.array(image)

    # 明度計算
    brightness = data.mean(axis=2)

    # 暗いピクセル → 黒、明るいピクセル → 白
    bw = np.where(brightness < 150, 0, 255).astype(np.uint8)
    result = np.stack([bw, bw, bw], axis=2)

    processedImage = Image.fromarray(result)
    processedImage = processedImage.resize((300, 90), Image.Resampling.LANCZOS)
    processedImage = processedImage.convert("L")
    processedImage = ImageOps.autocontrast(processedImage)
    processedImage = ImageEnhance.Contrast(processedImage).enhance(1.3)

    # 色を反転（白 ⟷ 黒）
    processedImage = ImageOps.invert(processedImage)

    outputBuffer = io.BytesIO()
    processedImage.save(outputBuffer, format="PNG")
    return outputBuffer.getvalue()


# ── アップスケール ──────────────────────────────────────────


# PILベース: LANCZOSリサイズ + アンシャープマスクで鮮鋭化
def upscaleImage(buffer: bytes, scale: int = 2) -> bytes:
    image = Image.open(io.BytesIO(buffer)).convert("RGB")

    newWidth = image.width * scale
    newHeight = image.height * scale

    # LANCZOSで拡大
    upscaled = image.resize((newWidth, newHeight), Image.Resampling.LANCZOS)

    # アンシャープマスクでエッジを鮮鋭化 (radius, percent, threshold)
    upscaled = upscaled.filter(UnsharpMask(radius=1.5, percent=120, threshold=3))

    # わずかにコントラスト強調
    upscaled = ImageEnhance.Contrast(upscaled).enhance(1.1)
    upscaled = ImageEnhance.Sharpness(upscaled).enhance(1.2)

    outputBuffer = io.BytesIO()
    upscaled.save(outputBuffer, format="PNG")
    return outputBuffer.getvalue()
