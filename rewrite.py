import cv2
import io
from PIL import Image
from yomitoku.schemas import OCRSchema, WordPrediction
import json
import base64
import dotenv
import os
import asyncio
import httpx
from bs4 import BeautifulSoup
from additional.img import (
    processImageReplaceBlackAndThicken,
    processImageWithJimpWhiteBackground,
    processImageWithJimpBlackBackground,
    upscaleImage,
)
from yomitoku import OCR
import numpy as np

dotenv.load_dotenv()

http = httpx.AsyncClient()
ocr = OCR(visualize=True, device="cuda", configs={"model_name": "parseq"})


async def main():
    response = await http.get("https://secure.xserver.ne.jp/xapanel/login/xvps/")
    soup = BeautifulSoup(response.text, "html.parser")
    if element := soup.select_one('input[name="uniqid"]'):
        uniqId = element.attrs["value"]
    else:
        raise Exception("Failed to get uniq id")

    response = await http.post(
        "https://secure.xserver.ne.jp/xapanel/myaccount/login",
        data={
            "request_page": "",
            "site": "",
            "uniqid": uniqId,
            "memberid": os.getenv("xserver_username"),
            "user_password": os.getenv("xserver_password"),
        },
    )

    response = await http.get(
        f"https://secure.xserver.ne.jp/xapanel/xvps/server/freevps/extend/index?id_vps={os.getenv('xserver_vpsid')}"
    )
    soup = BeautifulSoup(response.text, "html.parser")
    if element := soup.select_one('input[name="uniqid"]'):
        uniqId = element.attrs["value"]
    else:
        raise Exception("Failed to get uniq id")

    response = await http.post(
        "https://secure.xserver.ne.jp/xapanel/xvps/server/freevps/extend/conf",
        data={
            "uniqid": uniqId,
            "ethna_csrf": "",
            "id_vps": os.getenv("xserver_vpsid"),
            "auth_code": "",
            "cf-turnstile-response": "",
        },
    )
    soup = BeautifulSoup(response.text, "html.parser")
    if element := soup.select_one('input[name="uniqid"]'):
        uniqId = element.attrs["value"]
    else:
        raise Exception("Failed to get uniq id")
    if element := soup.select_one('img[style="border: 1px solid black"]'):
        image = element.attrs["src"]
        if isinstance(image, str):
            result: bytes = upscaleImage(
                processImageWithJimpBlackBackground(
                    processImageWithJimpWhiteBackground(
                        processImageReplaceBlackAndThicken(
                            base64.b64decode(image.split(",", 1)[1])
                        )
                    )
                ),
                10,
            )
        else:
            raise Exception("Failed to get image")
    else:
        raise Exception("Failed to get image")

    with open("yeah.png", "wb") as f:
        f.write(result)

    results, ocr_vis = ocr(np.array(Image.open(io.BytesIO(result)).convert("RGB")))
    cv2.imwrite("ocr.jpg", ocr_vis)

    results: OCRSchema
    authCode = ""

    for word in results.words:
        word: WordPrediction
        authCode += word.content

    print(authCode)
    return

    response = await http.get(
        "http://localhost:5000/turnstile?url=https://secure.xserver.ne.jp&sitekey=0x4AAAAAABlb1fIlWBrSDU3B"
    )
    taskId = response.json()["task_id"]

    while True:
        try:
            response = await http.get(f"http://localhost:5000/result?id={taskId}")
            value = response.json().get("value")
            if value:
                break
        except json.decoder.JSONDecodeError:
            continue
        await asyncio.sleep(1)

    response = await http.post(
        "https://secure.xserver.ne.jp/xapanel/xvps/server/freevps/extend/do",
        data={
            "ethna_csrf": "",
            "id_vps": os.getenv("xserver_vpsid"),
            "auth_code": authCode,
            "cf-turnstile-response": value,
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
