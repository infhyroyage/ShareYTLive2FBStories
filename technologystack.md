# YouTube ライブ配信の Facebook ストーリーズ自動投稿システム

## 1. 要件と概要

### 1.1 要件

YouTube でライブ配信を開始した直後に、そのライブ配信の開始を通知する Facebook ストーリーズを自動で作成する。

### 1.2 ソリューション概要

YouTube Data API の PubSubHubbub(Webhook)機能を使用してライブ配信開始イベントを検知し、AWS Lambda で自動処理を行い、Facebook Graph API を使用してストーリーズに投稿するサーバーレスアーキテクチャを構築する。このアプローチにより、手動操作なしでリアルタイムな通知を実現する。

### 1.3 データフロー

システム全体の処理フローは以下の通りである:

1. ユーザーが YouTube でライブ配信を開始する
2. YouTube が登録された Webhook(Amazon API Gateway)に通知を送信する
3. Amazon API Gateway が AWS Lambda 関数を起動する
4. AWS Lambda 関数が YouTube API から配信詳細(タイトル、サムネイル URL、ライブ URL)を取得する
5. AWS Lambda 関数が Amazon DynamoDB で処理済みかチェック(重複投稿防止)する
6. AWS Lambda 関数が YouTube からサムネイル画像をダウンロードし、Facebook Graph API を使用してストーリーズに投稿する
   - サムネイル画像
   - 配信タイトル
   - ライブ配信への直接リンク
7. 処理結果を Amazon DynamoDB に記録する

## 2. アーキテクチャと技術スタック

### 2.1 使用サービス

#### AWS サービス

本システムでは、以下の AWS サービスを利用して、スケーラブルかつ耐障害性の高いアーキテクチャを構築する:

- Amazon API Gateway (YouTube からの PubSubHubbub 受信)
- Amazon CloudWatch (ログ・モニタリング)
- Amazon DynamoDB (配信状態管理)
- Amazon EventBridge (スケジュールタスク・自動更新)
- AWS CodeBuild (コードビルド・テスト実行)
- AWS CodeDeploy (SAM テンプレートベースのデプロイ)
- AWS CodePipeline (CI/CD パイプライン管理)
- AWS IAM (権限管理)
- AWS Lambda (サーバーレスロジック実装)
- AWS Systems Manager Parameter Store (シークレット管理)

#### 外部サービス

AWS 以外の外部サービスとも連携することにより、コア機能を実現する:

- YouTube Data API v3 (ライブ配信情報取得)
- Facebook Graph API v14.0+ (ストーリーズ投稿)
- GitHub (コードリポジトリ)

### 2.2 AWS リソース構成

以下の表は、本システムで使用する主要な AWS リソースとその役割を示している:

| AWS リソース名(論理 ID)                       | AWS サービス       | 概要                                                               |
| --------------------------------------------- | ------------------ | ------------------------------------------------------------------ |
| `ytlive2fbstories-apig`                       | Amazon API Gateway | YouTube からの PubSubHubbub 通知を受け取る API エンドポイント      |
| `ytlive2fbstories-build`                      | AWS CodeBuild      | ビルドプロセスを実行するプロジェクト                               |
| `ytlive2fbstories-cwlogs`                     | Amazon CloudWatch  | システムログを保存するロググループ                                 |
| `ytlive2fbstories-deploy`                     | AWS CodeDeploy     | AWS SAM テンプレートによるデプロイを管理するアプリケーション       |
| `ytlive2fbstories-dynamodb`                   | Amazon DynamoDB    | 処理済みライブ配信を記録するテーブル                               |
| `ytlive2fbstories-ebrule-update-fbtoken`      | Amazon EventBridge | Facebook 長期アクセストークン更新 Lambda を定期実行するルール      |
| `ytlive2fbstories-ebrule-update-pubsubhubbub` | Amazon EventBridge | PubSubHubbub 更新 Lambda を定期実行するルール                      |
| `ytlive2fbstories-lambda-submit`              | AWS Lambda         | PubSubHubbub を処理し、Facebook へのストーリーズ投稿を実行する関数 |
| `ytlive2fbstories-lambda-update-fbtoken`      | AWS Lambda         | Facebook 長期アクセストークンを更新する関数                        |
| `ytlive2fbstories-lambda-update-pubsubhubbub` | AWS Lambda         | YouTube PubSubHubbub を更新する関数                                |
| `ytlive2fbstories-pipeline`                   | AWS CodePipeline   | CI/CD パイプラインを管理する                                       |

### 2.3 AWS アーキテクチャー図

以下の図は、システム全体のアーキテクチャを示している:

![architecture.drawio](architecture.drawio.svg)

## 3. コア機能の実装詳細

### 3.1 YouTube ライブ配信検知の仕組み

YouTube の新規ライブ配信を検知するために、PubSubHubbub(Webhook)機能を利用する。この機能により、ポーリングによる遅延や API コスト増大を避け、リアルタイムな通知を受け取ることができる。

YouTube Data API の PubSubHubbub(Webhook)機能を使用して、以下のトピックを購読する:

```
https://www.youtube.com/xml/feeds/videos.xml?channel_id={CHANNEL_ID}
```

PubSubHubbub の登録時に、以下の設定を行う:

- **トピック**: 上記 URL(特定チャンネルの動画フィードを指定)
- **コールバック URL**: Amazon API Gateway のエンドポイント
- **通知タイプ**: `video` (新しい動画やライブ配信が開始された場合に通知)
- **リース期間**: 10 日間(自動更新が必要)

通知が届いたら、AWS Lambda 関数で以下の処理を行う:

1. XML を解析して動画 ID を抽出する
2. YouTube API で動画詳細を取得し、ライブ配信かどうかを確認する
3. ライブ配信の場合、Facebook ストーリーズに投稿する

### 3.2 Facebook ストーリーズ投稿内容

ライブ配信が検知されると、視覚的に魅力的なコンテンツを Facebook ストーリーズに自動投稿する。Facebook Graph API を使用して、以下の内容を含むストーリーズを投稿する:

- **画像**: YouTube ライブ配信のサムネイル画像(AWS Lambda 内でダウンロードして直接アップロード)
- **テキスト**: YouTube ライブ配信の配信タイトル
- **リンク**: ライブ配信の URL (`https://www.youtube.com/watch?v={VIDEO_ID}`)

この構成により、ストーリーズを閲覧したユーザーが直感的にライブ配信の内容を理解し、ワンタップでアクセスできるようになる。

## 4. 自動更新メカニズム

サービスの継続的な運用を保証するため、期限切れになる認証情報やサブスクリプションを自動的に更新する仕組みを実装する。

### 4.1 YouTube PubSubHubbub 自動更新

YouTube Data API の PubSubHubbub 登録には以下の制約がある:

- **最大有効期間**: 10 日間
- **登録方法**: POST リクエストを `https://pubsubhubbub.appspot.com/subscribe` に送信
- **認証要件**: API エンドポイントへのチャレンジ応答が必要

PubSubHubbub の有効期限を更新する構成として、以下のステップを採用する:

1. YouTube API に PubSubHubbub 再登録リクエストを送信する AWS Lambda 関数を、7 日ごとに実行するように、Amazon EventBridge ルールを定義する

   - 最大有効期限の 10 日間から余裕を持って更新する

2. API キーや認証情報、PubSubHubbub 設定情報(チャンネル ID、コールバック URL、検証トークン、最終更新日時)を AWS Systems Manager Parameter Store に保管する

### 4.2 Facebook アクセストークン自動更新

同様に、Facebook Graph API のアクセストークンにも有効期限があり、自動更新が必要である:

- **短期アクセストークン**: 数時間有効
- **長期アクセストークン**: 約 60 日間有効
- **更新方法**: 既存の有効な長期トークンを使用して新しい長期トークンを取得

> [!NOTE]
> 短期アクセストークンは初期設定時にのみ使用され、ユーザーが Facebook にログインして認証した後に長期アクセストークンに交換される。その後の自動更新では長期アクセストークンのみを扱う。

長期アクセストークンの有効期限を更新する構成として、以下のステップを採用する:

1. Facebook Graph API に長期アクセストークン更新リクエストを送信する AWS Lambda 関数を、57 日ごとに実行するように、Amazon EventBridge ルールを定義する

   - 最大有効期限の 60 日間から余裕を持って更新する

2. 長期アクセストークンと更新日時を AWS Systems Manager Parameter Store に保管する

## 5. 開発・運用ガイドライン

### 5.1 開発ツール

本システムの開発には、以下のツールとテクノロジーを使用する:

- Python 3.12 (プログラミング言語)
  - サーバーレス環境との互換性と、多数の API クライアントライブラリの利用可能性から選定
- AWS SAM CLI (ローカルテストとデプロイ)
- pytest (ユニットテスト)
- pylint (コード静的解析)

### 5.2 重要な制約事項

セキュリティとシステム信頼性を確保するため、以下の制約事項を遵守する:

- YouTube API キー、クライアント ID、シークレット、PubSubHubbub の設定情報(チャンネル ID、コールバック URL、検証トークン)は AWS Systems Manager Parameter Store で安全に管理し、リポジトリには保存しない
- Facebook Graph API 長期アクセストークンは AWS Systems Manager Parameter Store で管理し、57 日ごとに自動更新する

### 5.3 開発時の実装規則

コード品質と一貫性を確保するため、以下の実装規則に従う:

- AWS リソースは `template.yml` に SAM テンプレートとして管理する。すべてのインフラはコードとして定義し、手動構成は行わない
- CI/CD パイプラインは、以下の AWS サービスを連携させて構築した AWS CodePipeline を使用し、GitHub リポジトリの main ブランチへの commit をトリガーとして実行される
  - **AWS CodeBuild**: `buildspec.yml`で定義したビルド・テスト処理(依存関係解決、テスト実行、SAM パッケージング)
  - **AWS CodeDeploy**: `appspec.yml`で定義したデプロイ処理(Lambda 関数のデプロイと段階的トラフィック移行)
- 以下のコマンドでユニットテストを実行し、stmt のカバレッジ率 80%以上を確保する
  ```bash
  coverage run -m unittest discover -s lambda/tests && coverage report -m
  ```
- AWS Lambda 関数は Python を用いてコーディングし、Pylint のデフォルトルールを採用してコード品質を担保する。Pylint の静的解析は以下のコマンドで実行する
  ```bash
  pylint lambda/*.py
  ```
