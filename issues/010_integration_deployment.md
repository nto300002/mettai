# Issue #010: 統合テスト＋デプロイ準備

## 目的

全コンポーネント（Django API + ブラウザ拡張）の統合テストを実施し、本番環境（Cloud Run + Neon）へのデプロイ準備を完了する。

## 作成ファイル名

```
.github/
└── workflows/
    └── ci-cd.yml               # GitHub Actions CI/CD

docker/
├── Dockerfile                  # 本番用マルチステージビルド
├── Dockerfile.dev              # ローカル開発用
└── docker-compose.yml          # ローカル開発環境

mettai-extension/
└── build.sh                    # 拡張機能ビルドスクリプト（実行権限付与）

scripts/
├── deploy.sh                   # デプロイスクリプト
└── test_integration.sh         # 統合テストスクリプト
```

## ディレクトリ構成

```
.github/workflows/
└── ci-cd.yml                # CI/CD パイプライン

docker/
├── Dockerfile               # Cloud Run デプロイ用
├── Dockerfile.dev           # ローカル開発用
└── docker-compose.yml       # PostgreSQL + Django

mettai-extension/
└── build.sh                 # Chrome/Firefox ビルド

scripts/
├── deploy.sh                # Cloud Run デプロイ
└── test_integration.sh      # 統合テスト実行
```

## 実装内容

### 1. .github/workflows/ci-cd.yml

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  PROJECT_ID: mettai-prod
  REGION: asia-northeast1
  SERVICE_NAME: mettai-api
  IMAGE: asia-northeast1-docker.pkg.dev/mettai-prod/mettai-repo/mettai-api

jobs:
  # ── CI: Djangoテスト ──────────────────────────
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: mettai_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Lint check
        run: ruff check .
      - name: Run tests
        run: pytest --cov=apps --cov-report=term-missing
        env:
          DATABASE_URL: postgres://test:test@localhost:5432/mettai_test
          DJANGO_SETTINGS_MODULE: config.settings.testing
          SECRET_KEY: test-secret-key

  # ── CI: 拡張機能テスト ──────────────────────────
  test-extension:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - name: Install dependencies
        working-directory: mettai-extension
        run: npm ci
      - name: Run tests
        working-directory: mettai-extension
        run: npm test -- --coverage

  # ── CD: Cloud Runデプロイ（mainのみ）──────────────
  deploy:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: [test-backend, test-extension]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write  # Workload Identity Federation

    steps:
      - uses: actions/checkout@v4

      # GCP 認証（Workload Identity Federation）
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      # Docker ビルド & プッシュ
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud auth configure-docker ${{ env.REGION }}-docker.pkg.dev --quiet
      - run: |
          docker build -t ${{ env.IMAGE }}:${{ github.sha }} -f docker/Dockerfile .
          docker push ${{ env.IMAGE }}:${{ github.sha }}

      # Cloud Run デプロイ
      - uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE_NAME }}
          region: ${{ env.REGION }}
          image: ${{ env.IMAGE }}:${{ github.sha }}
          flags: |
            --allow-unauthenticated
            --memory=512Mi
            --cpu=1
            --min-instances=0
            --max-instances=10
            --concurrency=80
            --port=8080
            --set-secrets=SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest

      # マイグレーション実行
      - run: |
          gcloud run jobs execute mettai-migrate \
            --region ${{ env.REGION }} \
            --wait
```

### 2. docker/Dockerfile

```dockerfile
# ── 本番用マルチステージビルド（Cloud Run）──────────

# ===== Build stage =====
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===== Production stage =====
FROM python:3.12-slim AS production

# セキュリティ: 非root ユーザーで実行
RUN groupadd -r django && useradd -r -g django django

WORKDIR /app

# 依存ライブラリをコピー
COPY --from=builder /install /usr/local

# アプリケーションコードをコピー
COPY manage.py .
COPY config/ config/
COPY apps/ apps/

# 静的ファイル収集
RUN DJANGO_SETTINGS_MODULE=config.settings.production \
    SECRET_KEY=dummy-for-collectstatic \
    DATABASE_URL=sqlite:///dummy \
    python manage.py collectstatic --noinput

# 非root ユーザーに切替
USER django

# Cloud Run は PORT 環境変数を注入する
ENV PORT=8080
EXPOSE 8080

# gunicorn 起動
CMD exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

### 3. docker/Dockerfile.dev

```dockerfile
# ── ローカル開発用 ──────────

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

ENV DJANGO_SETTINGS_MODULE=config.settings.development
EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

### 4. docker/docker-compose.yml

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: mettai_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  web:
    build:
      context: ..
      dockerfile: docker/Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ..:/app
    env_file:
      - ../.env
    environment:
      - DATABASE_URL=postgres://postgres:postgres@db:5432/mettai_dev
      - DJANGO_SETTINGS_MODULE=config.settings.development
    depends_on:
      - db

volumes:
  postgres_data:
```

### 5. mettai-extension/build.sh

```bash
#!/bin/bash

set -e

echo "Building Mettai Extension..."

# クリーンアップ
rm -rf dist

# Chrome用ビルド
echo "Building for Chrome..."
mkdir -p dist/chrome
cp manifest.chrome.json dist/chrome/manifest.json
cp -r shared vendor icons dist/chrome/

# Firefox用ビルド
echo "Building for Firefox..."
mkdir -p dist/firefox
cp manifest.firefox.json dist/firefox/manifest.json
cp -r shared vendor icons dist/firefox/

echo "✅ Build completed!"
echo "Chrome: dist/chrome"
echo "Firefox: dist/firefox"
```

### 6. scripts/deploy.sh

```bash
#!/bin/bash

set -e

PROJECT_ID="mettai-prod"
REGION="asia-northeast1"
SERVICE_NAME="mettai-api"
IMAGE="asia-northeast1-docker.pkg.dev/${PROJECT_ID}/mettai-repo/mettai-api"

echo "Deploying to Cloud Run..."

# Docker ビルド
docker build -t ${IMAGE}:latest -f docker/Dockerfile .

# Docker プッシュ
docker push ${IMAGE}:latest

# Cloud Run デプロイ
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE}:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-secrets SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest

echo "✅ Deployment completed!"
```

### 7. scripts/test_integration.sh

```bash
#!/bin/bash

set -e

echo "Running integration tests..."

# Djangoテスト
echo "1. Backend tests..."
pytest --cov=apps --cov-report=term-missing

# 拡張機能テスト
echo "2. Extension tests..."
cd mettai-extension
npm test -- --coverage
cd ..

# Lint
echo "3. Lint checks..."
ruff check .

echo "✅ All tests passed!"
```

## テスト要件

### 統合テストシナリオ

```
【シナリオ1: 新規ユーザー登録 → ルール作成 → ブロック動作確認】
1. 拡張機能からユーザー登録
2. APIでトークンが発行される
3. ルールを作成（youtube をブラックリスト）
4. 拡張機能でルールを同期
5. YouTube を開く
6. オーバーレイが表示される
7. 「作業に戻る」で前のページに戻る

【シナリオ2: 既存ユーザーログイン → 一時許可 → 5分後にブロック再開】
1. 既存ユーザーでログイン
2. ルール同期
3. ブロック対象URLを開く
4. オーバーレイで「5分だけ許可」を選択
5. 5分間は再度開いてもブロックされない
6. 5分経過後に再度開くとブロックされる

【シナリオ3: ホワイトリストモード動作確認】
1. ユーザー設定を「ホワイトリスト」に変更
2. github.com のみ許可ルールを作成
3. github.com を開く → ブロックされない
4. youtube.com を開く → ブロックされる

【シナリオ4: 集中モードOFF → ブロック停止】
1. ポップアップから集中モードをOFF
2. ブロック対象URLを開いてもオーバーレイが表示されない
3. 集中モードをONに戻すとブロック再開
```

### E2Eテスト（将来実装）

```javascript
// Playwright を使ったE2Eテスト（Issue #011で実装予定）
// 拡張機能 → API → DB の一連の流れを自動テスト
```

## テストコマンド

```bash
# ローカル統合テスト
./scripts/test_integration.sh

# Docker Compose で起動
docker-compose -f docker/docker-compose.yml up

# 拡張機能ビルド
cd mettai-extension
chmod +x build.sh
./build.sh

# デプロイ（本番環境）
./scripts/deploy.sh
```

## 完了条件

- [ ] CI/CD パイプライン（GitHub Actions）が動作する
- [ ] 全ての統合テストシナリオが手動で通る
- [ ] Docker Compose でローカル環境が起動する
- [ ] Dockerfile で本番イメージがビルドできる
- [ ] Cloud Run へのデプロイが成功する
- [ ] Neon データベースに接続できる
- [ ] 拡張機能が本番APIと通信できる
- [ ] Chrome/Firefoxで実際に動作確認できる

## 備考

- 統合テストは手動実行（E2Eテストは将来実装）
- CI/CD パイプラインは main ブランチへのpush で自動実行
- Cloud Run + Neon のダブルゼロスケール構成
- 本番環境変数は Secret Manager で管理
- デプロイ後は必ず動作確認を実施
