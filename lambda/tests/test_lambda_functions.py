"""Test the basic lambda response format"""

import json
from typing import Callable

import pytest


def mock_lambda_handler(message: str) -> Callable[[dict, dict], dict]:
    """
    テスト用のモックLambdaハンドラー

    Args:
        message (str): テスト用のメッセージ

    Returns:
        dict: テスト用のモックLambdaハンドラーの戻り値
    """

    def handler(event: dict, context: dict) -> dict:
        """
        テスト用のモックLambdaハンドラー

        Args:
            event (dict): テスト用のイベント
            context (dict): テスト用のコンテキスト

        Returns:
            dict: テスト用のモックLambdaハンドラーの戻り値
        """
        return {"statusCode": 200, "body": json.dumps({"message": message})}

    return handler


@pytest.mark.parametrize("name", ["stories", "fbtoken", "websub"])
def test_lambda_response_format(name: str):
    """
    各Lambda関数のユニットテストを実行する

    Args:
        name (str): テスト対象のLambda関数の名前
    """
    handlers = {
        "stories": mock_lambda_handler("Hello World from stories Lambda!"),
        "fbtoken": mock_lambda_handler("Hello World from fbtoken Lambda!"),
        "websub": mock_lambda_handler("Hello World from websub Lambda!"),
    }

    handler = handlers[name]
    event = {}
    response = handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == f"Hello World from {name} Lambda!"
