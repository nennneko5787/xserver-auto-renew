import asyncio
import base64
import logging
import os

import dotenv
import httpx
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

from additional.img import (
    processImageReplaceBlackAndThicken,
    processImageWithJimpBlackBackground,
    processImageWithJimpWhiteBackground,
)
from additional.solve import solveTurnstile

dotenv.load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


async def log_request(request):
    logger.debug(f">>> {request.method} {request.url}")


async def log_response(response):
    logger.debug(f"<<< {response.status_code} {response.url}")


mapping = {
    "ぜろ": "0",
    "いち": "1",
    "に": "2",
    "さん": "3",
    "よん": "4",
    "ご": "5",
    "ろく": "6",
    "なな": "7",
    "はち": "8",
    "きゅう": "9",
}


def convert(text):
    result = text

    # 長い順に置換
    for k in sorted(mapping.keys(), key=len, reverse=True):
        result = result.replace(k, mapping[k])

    return result


http = httpx.AsyncClient(
    timeout=None,
    follow_redirects=True,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    },
    event_hooks={
        "request": [log_request],
        "response": [log_response],
    },
)

client = genai.Client(api_key=os.getenv("gemini_key"))


async def main():
    logger.info("Xserver automation started")

    # Login page
    logger.info("Fetching login page...")
    response = await http.get("https://secure.xserver.ne.jp/xapanel/login/xvps/")
    soup = BeautifulSoup(response.text, "html.parser")

    if element := soup.select_one('input[name="uniqid"]'):
        uniqId = element.attrs["value"]
        logger.info(f"Got login uniqid: {uniqId[:10]}...")
    else:
        logger.error("Failed to get login uniqid")
        raise Exception("Failed to get uniq id")

    # Login
    logger.info("Logging in...")
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

    logger.info(f"Login response: {response.status_code}")

    if "ログアウト" in response.text:
        logger.info("Login success")
    else:
        logger.warning("Login may have failed")

    # Extend page
    logger.info("Fetching VPS extend page...")
    response = await http.get(
        f"https://secure.xserver.ne.jp/xapanel/xvps/server/freevps/extend/index?id_vps={os.getenv('xserver_vpsid')}"
    )

    soup = BeautifulSoup(response.text, "html.parser")

    if element := soup.select_one('input[name="uniqid"]'):
        uniqId = element.attrs["value"]
        logger.info(f"Got extend uniqid: {uniqId[:10]}...")
    else:
        logger.error("Failed to get extend uniqid")
        raise Exception("Failed to get uniq id")

    # Move to confirm page
    logger.info("Opening confirmation page...")
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
        logger.info(f"Got confirmation uniqid: {uniqId[:10]}...")
    else:
        logger.error("Failed to get confirmation uniqid")
        raise Exception("Failed to get uniq id")

    # Get captcha image
    logger.info("Extracting captcha image...")

    if element := soup.select_one('img[style="border: 1px solid black"]'):
        image = element.attrs["src"]

        if isinstance(image, str):
            result: bytes = processImageWithJimpBlackBackground(
                processImageWithJimpWhiteBackground(
                    processImageReplaceBlackAndThicken(
                        base64.b64decode(image.split(",", 1)[1])
                    )
                )
            )
            logger.info(f"Captcha processed ({len(result)} bytes)")
        else:
            logger.error("Captcha image src invalid")
            raise Exception("Failed to get image")
    else:
        logger.error("Captcha image not found")
        raise Exception("Failed to get image")

    with open("yeah.png", "wb") as f:
        f.write(result)

    logger.info("Saved captcha image -> yeah.png")

    # OCR
    logger.info("Sending captcha to Gemini OCR...")

    response = await client.aio.models.generate_content(
        model="gemma-4-26b-a4b-it",
        contents=[
            '画像に書いてある文字をそのままひらがなだけで読んでください。説明不要。スペースなし。ひらがな(["いち", "に", "さん", "よん", "ご", "ろく", "なな", "はち", "きゅう"])のみ出力。文字同士が重なっている場合があります。',
            types.Part.from_bytes(
                data=result,
                mime_type="image/png",
            ),
        ],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            )
        ),
    )

    if response.text is None:
        logger.error("Failed to get auth code")
        raise Exception("Failed to get auth code")
    rawText = response.text.strip()
    logger.info(f"Raw OCR text: {rawText}")

    authCode = convert(rawText)
    logger.info(f"OCR result: {authCode}")

    if len(authCode) != 6:
        logger.warning("OCR result is not 6 digits")

    """
    response = await http.get(
        "http://localhost:5000/turnstile?url=https://secure.xserver.ne.jp&sitekey=0x4AAAAAABlb1fIlWBrSDU3B"
    )
    jsonData = response.json()
    print(jsonData)
    taskId = jsonData["task_id"]

    while True:
        try:
            response = await http.get(f"http://localhost:5000/result?id={taskId}")
            jsonData = response.json()
            print(jsonData)
            if jsonData.get("elapsed_time"):
                value = jsonData.get("value")
                if value == "CAPTCHA_FAIL":
                    raise Exception("Failed to solve captcha")
                break
        except json.decoder.JSONDecodeError:
            continue
        await asyncio.sleep(1)

    print(value)
    """

    # Turnstile
    logger.info("Solving Cloudflare Turnstile...")

    value = await solveTurnstile(
        url="https://secure.xserver.ne.jp/xapanel/xvps/server/freevps/extend/conf",
        sitekey="0x4AAAAAABlb1fIlWBrSDU3B",
    )

    logger.info("Turnstile solved successfully")
    logger.debug(f"Token: {value[:30]}...")

    # Final submit
    logger.info("Submitting renewal request...")

    response = await http.post(
        "https://secure.xserver.ne.jp/xapanel/xvps/server/freevps/extend/do",
        data={
            "uniqid": uniqId,
            "ethna_csrf": "",
            "id_vps": os.getenv("xserver_vpsid"),
            "auth_code": authCode,
            "cf-turnstile-response": value,
        },
    )

    logger.info(f"Final response status: {response.status_code}")

    success = "失敗しました" not in response.text

    if success:
        logger.info("Renewal success")
    else:
        logger.error("Renewal failed")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(response.text)

    logger.info("Saved HTML response -> index.html")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("Unhandled exception occurred")
