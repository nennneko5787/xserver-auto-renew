import asyncio
import logging
import os

import dotenv
import httpx

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


async def solveTurnstile(*, url: str, sitekey: str) -> str:
    logger.info("Starting 2Captcha Turnstile solve")

    async with httpx.AsyncClient(base_url="https://api.2captcha.com/") as http:
        # Create task
        logger.info("Creating 2Captcha task...")

        response = await http.post(
            "createTask",
            json={
                "clientKey": os.getenv("2captcha_key"),
                "task": {
                    "type": "TurnstileTaskProxyless",
                    "websiteURL": url,
                    "websiteKey": sitekey,
                },
            },
        )

        logger.debug(f"createTask status={response.status_code}")

        data = response.json()

        logger.debug(f"createTask response={data}")

        if data["errorId"] != 0:
            logger.error(f"2Captcha createTask failed: {data}")
            raise Exception(f"2Captcha error: {data}")

        task_id = data["taskId"]

        logger.info(f"2Captcha task created: task_id={task_id}")

        poll_count = 0

        # Polling
        while True:
            poll_count += 1

            logger.info(f"Polling 2Captcha... attempt={poll_count}")

            response = await http.post(
                "getTaskResult",
                json={
                    "clientKey": os.getenv("2captcha_key"),
                    "taskId": task_id,
                },
            )

            logger.debug(f"getTaskResult status={response.status_code}")

            data = response.json()

            logger.debug(f"getTaskResult response={data}")

            # API error
            if data["errorId"] != 0:
                logger.error(f"2Captcha getTaskResult failed: {data}")
                raise Exception(f"2Captcha error: {data}")

            status = data["status"]

            # Still processing
            if status == "processing":
                logger.info(f"Captcha still processing (attempt={poll_count})")
                await asyncio.sleep(3)
                continue

            # Success
            if status == "ready":
                token = data["solution"]["token"]

                logger.info(f"Captcha solved after {poll_count} polls")

                logger.debug(f"Token received: {token[:40]}...")

                return token

            # Unexpected status
            logger.error(f"Unexpected 2Captcha status: {status}")

            raise Exception(f"Unexpected 2Captcha status: {status}")
