# YouTube ライブ配信の Facebook ストーリーズ自動投稿システム

## 1. 要件と概要

### 1.1 要件

YouTube でライブ配信を開始した直後に、そのライブ配信の開始を通知する Facebook ストーリーズを自動で作成する。

### 1.2 ソリューション概要

Google PubSubHubbub Hub を経由した WebSub の仕組みを利用して YouTube ライブ配信開始イベントを検知し、Facebook Graph API を使用して Facebook ストーリーズに投稿するように AWS Lambda を実行するサーバーレスアプリケーションを構築する。このアプローチにより、手動操作なしでリアルタイムな通知を実現する。

### 1.3 データフロー

システム全体の処理フローは以下の通りである:

1. ユーザーが YouTube でライブ配信を開始する。
2. YouTube が事前に登録された Google PubSubHubbub Hub に RSS を通知する。
3. Google PubSubHubbub Hub が Amazon API Gateway に通知し、Amazon API Gateway が AWS Lambda 関数を起動する。
4. AWS Lambda 関数が 配信詳細(タイトル、サムネイル URL、ライブ URL)を取得する。
5. AWS Lambda 関数が Amazon DynamoDB で処理済みかチェック(重複投稿防止)する。
6. AWS Lambda 関数が YouTube からサムネイル画像をダウンロードし、Facebook Graph API を使用してストーリーズに投稿する。
   - サムネイル画像
   - 配信タイトル
   - ライブ配信への直接リンク
7. 処理結果を Amazon DynamoDB に記録する。

## 2. アーキテクチャと技術スタック

### 2.1 使用サービス

#### AWS サービス

本システムでは、以下の AWS サービスを利用して、スケーラブルかつ耐障害性の高いアーキテクチャを構築する:

- Amazon API Gateway (Google PubSubHubbub Hub からの通知受信)
- Amazon CloudWatch (ログ・モニタリング)
- Amazon DynamoDB (配信状態管理)
- Amazon EventBridge (スケジュールタスク・自動更新)
- Amazon S3 (ビルドアーティファクトのストレージ)
- AWS CloudFormation (サーバーレスアプリケーションのデプロイ)
- AWS CodeBuild (コードビルド・テスト実行)
- AWS CodePipeline (CI/CD パイプライン管理)
- AWS IAM (権限管理)
- AWS Lambda (サーバーレスアプリケーションのロジック実装)
- AWS Systems Manager Parameter Store (パラメーター管理)

#### 外部サービス

AWS 以外の外部サービスとも連携することにより、コア機能を実現する:

- YouTube Data API v3 (ライブ配信情報取得)
- Facebook Graph API v14.0+ (ストーリーズ投稿)
- GitHub (コードリポジトリ)

### 2.2 AWS リソース構成

以下の表は、本システムで使用する主要な AWS リソースとその役割を示している:

| AWS リソース名(論理 ID)                              | AWS サービス       | 概要                                                                                        |
| ---------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------- |
| `ytlive2fbstories-apig`                              | Amazon API Gateway | WebSub での YouTube ライブ配信通知を受け取る API エンドポイント                             |
| `ytlive2fbstories-build`                             | AWS CodeBuild      | ビルドプロセスを管理するアプリケーション                                                    |
| `/aws/apigateway/ytlive2fbstories-apig`              | Amazon CloudWatch  | `ytlive2fbstories-apig` のアクセスログを保存するロググループ                                |
| `/aws/lambda/ytlive2fbstories-lambda-fbtoken`        | Amazon CloudWatch  | `ytlive2fbstories-lambda-fbtoken` のログを保存するロググループ                              |
| `/aws/lambda/ytlive2fbstories-lambda-stories`        | Amazon CloudWatch  | `ytlive2fbstories-lambda-stories` のログを保存するロググループ                              |
| `/aws/lambda/ytlive2fbstories-lambda-websub`         | Amazon CloudWatch  | `ytlive2fbstories-lambda-websub` のログを保存するロググループ                               |
| `ytlive2fbstories-dynamodb`                          | Amazon DynamoDB    | 処理済みの YouTube ライブ配信を記録するテーブル                                             |
| `ytlive2fbstories-ebrule-fbtoken`                    | Amazon EventBridge | `ytlive2fbstories-lambda-fbtoken`を定期実行するルール                                       |
| `ytlive2fbstories-ebrule-websub`                     | Amazon EventBridge | `ytlive2fbstories-lambda-websub`を定期実行するルール                                        |
| `ytlive2fbstories-lambda-stories`                    | AWS Lambda         | WebSub での YouTube ライブ配信通知情報をもとに、Facebook ストーリーズを投稿する Lambda 関数 |
| `ytlive2fbstories-lambda-fbtoken`                    | AWS Lambda         | Facebook 長期アクセストークンを更新する Lambda 関数                                         |
| `ytlive2fbstories-lambda-websub`                     | AWS Lambda         | Google PubSubHubbub Hub を更新する Lambda 関数                                              |
| `ytlive2fbstories-pipeline`                          | AWS CodePipeline   | `ytlive2fbstories-build`・`ytlive2fbstories-stack`を管理する CI/CD パイプライン             |
| (`ytlive2fbstories-stack`構築時にパラメーターで設定) | Amazon S3          | CI/CD パイプラインのビルドアーティファクトを保存するバケット                                |
| `ytlive2fbstories-stack`                             | AWS CloudFormation | サーバーレスアプリケーションリソースを管理するスタック                                      |

### 2.3 AWS アーキテクチャー図

以下の図は、システム全体のアーキテクチャを示している:

![architecture.drawio](architecture.drawio.svg)

## 3. コア機能の実装詳細

### 3.1 YouTube ライブ配信検知

YouTube の新規ライブ配信を検知するために、Google PubSubHubbub Hub を経由した WebSub の仕組みを利用する。この仕組みにより、ポーリングによる遅延や API クオーター超過を避け、リアルタイムな通知を受け取ることができる。

Google PubSubHubbub Hub は、以下のトピックを RSS で購読するようにサブスクリプションを登録する必要がある:

```
https://www.youtube.com/xml/feeds/videos.xml?channel_id={CHANNEL_ID}
```

Google PubSubHubbub Hub の登録時に、以下の設定を行う:

- **トピック**: 上記 URL(特定チャンネルの動画フィードを指定)
- **コールバック URL**: Amazon API Gateway のエンドポイント
- **通知タイプ**: `video` (新しい動画やライブ配信が開始された場合に通知)
- **リース期間**: 10 日間(自動更新が必要)

通知が届いたら、AWS Lambda 関数で以下の処理を行う:

1. XML を解析して動画 ID を抽出する。
2. YouTube API で動画詳細を取得し、ライブ配信かどうかを判定する。
3. ライブ配信の場合、Facebook ストーリーズに投稿する。

### 3.2 Facebook ストーリーズの投稿

YouTube ライブ配信が検知されると、長期アクセストークン(自動更新が必要)を指定した Facebook Graph API を使用して、以下の内容を含む Facebook ストーリーズを投稿する:

- **画像**: YouTube ライブ配信のサムネイル画像(AWS Lambda 内でダウンロードして直接アップロード)
- **テキスト**: YouTube ライブ配信の配信タイトル
- **リンク**: ライブ配信の URL (`https://www.youtube.com/watch?v={VIDEO_ID}`)

## 4. 自動更新メカニズム

サービスの継続的な運用を保証するため、期限切れになる認証情報やサブスクリプションを自動的に更新する仕組みを実装する。

### 4.1 Google PubSubHubbub Hub 自動更新

Google PubSubHubbub Hub 登録の最大有効期間は 10 日間である。登録した Google PubSubHubbub Hub を更新する仕組みとして、以下のステップを採用する:

1. Google PubSubHubbub Hub を再登録する AWS Lambda 関数を、7 日ごとに実行するように、Amazon EventBridge ルールを定義する。

   - 最大有効期限の 10 日間から余裕を持って更新する。

2. API キーや認証情報、Google PubSubHubbub Hub 設定情報(チャンネル ID、コールバック URL、検証トークン、最終更新日時)を AWS Systems Manager Parameter Store に保管する。

### 4.2 Facebook アクセストークン自動更新

Facebook Graph API のアクセストークンには以下の有効期限がある:

- **短期アクセストークン**: 数時間有効
- **長期アクセストークン**: 約 60 日間有効

> [!NOTE]
> 短期アクセストークンは初期設定時にのみ使用され、ユーザーが Facebook にログインして認証した後に長期アクセストークンに交換される。その後の自動更新では長期アクセストークンのみを扱う。

長期アクセストークンの有効期限を更新する構成として、以下のステップを採用する:

1. Facebook Graph API に長期アクセストークン更新リクエストを送信する AWS Lambda 関数を、57 日ごとに実行するように、Amazon EventBridge ルールを定義する。

   - 最大有効期限の 60 日間から余裕を持って更新する。

2. 長期アクセストークンと更新日時を AWS Systems Manager Parameter Store に保管する。

## 5. 開発・運用ガイドライン

### 5.1 開発ツール

本システムの開発には、以下のツールとテクノロジーを使用する:

- Python 3.12 (プログラミング言語)
- AWS SAM CLI (ローカルテストとデプロイ)
- pytest (ユニットテスト)
- pylint (コード静的解析)

### 5.2 重要な制約事項

セキュリティとシステム信頼性を確保するため、以下の制約事項を遵守する:

- YouTube API キー、クライアント ID、シークレット、Google PubSubHubbub Hub の設定情報(チャンネル ID、コールバック URL、検証トークン)は AWS Systems Manager Parameter Store で安全に管理し、リポジトリには保存しない。
- Facebook Graph API 長期アクセストークンは AWS Systems Manager Parameter Store で管理し、57 日ごとに自動更新する。

### 5.3 開発時の実装規則

コード品質と一貫性を確保するため、以下の実装規則に従う:

- インフラストラクチャは全て Infrastructure as Code (IaC) で管理し、手動構成は行わない。本システムでは、目的に応じて複数のテンプレートファイルを使用する:

  - **`cfn.yml` (CloudFormation テンプレート)**: CI/CD パイプラインの AWS リソースを定義

    - AWS CodeBuild
    - AWS CloudFormation
    - AWS CodePipeline
    - Amazon S3
    - 上記 AWS リソースに必要な IAM ロール・IAM ポリシー

  - **`sam.yml` (SAM テンプレート)**: サーバーレスアプリケーションの実行環境の AWS リソースを定義

    - Amazon API Gateway
    - Amazon CloudWatch
    - Amazon DynamoDB
    - Amazon EventBridge
    - AWS Lambda
    - AWS Systems Manager Parameter Store
    - 上記 AWS リソースに必要な IAM ロール・IAM ポリシー

- 初期セットアップのみ AWS CloudFormation を使用して手動でデプロイし、以下の AWS サービスを連携した CI/CD パイプラインを手動で構築する。この CI/CD パイプラインは、GitHub リポジトリの main ブランチへの commit をトリガーとして実行される。

  - **AWS CodeBuild**: `buildspec.yml`で定義したテスト・ビルド処理(依存関係解決、テスト実行、SAM パッケージング、S3 アップロード)
  - **AWS CloudFormation**: ビルドアーティファクト(`packaged.yaml`)を用いたサーバーレスアプリケーションのデプロイ

- AWS Lambda 関数の Python のコードは、Python のユニットテストの stmt のカバレッジ率 80%以上をなるようにして、コード品質を担保する。ユニットテストは、以下のコマンドで実行する。
  ```bash
  coverage run -m unittest discover -s lambda/tests && coverage report -m
  ```
- AWS Lambda 関数は Python を用いてコーディングし、Pylint のデフォルトルールを採用して、コード品質を担保する。Pylint の静的解析は、以下のコマンドで実行する。
  ```bash
  pylint lambda/**/*.py
  ```
