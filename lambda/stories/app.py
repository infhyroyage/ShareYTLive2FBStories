"""WebSubでのYouTubeライブ配信通知情報をもとに、Facebookストーリーズを投稿する"""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context: dict) -> dict:
    """
    WebSubでのYouTubeライブ配信通知情報をもとに、Facebookストーリーズを投稿するLambda関数のハンドラー
    TODO: Hello Worldを返すように一時的に実装

    Args:
        event (dict): イベント
        context (dict): コンテキスト

    Returns:
        dict: レスポンス
    """
    logger.info("Received event: %s", json.dumps(event))

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Hello World from stories Lambda!"}),
    }
