# 開発ガイド

## 🚀 クイックスタート

### 前提条件

- Docker Desktop
- Git

### セットアップ

```bash
# 1. リポジトリクローン
git clone https://github.com/nto300002/mettai.git
cd mettai

# 2. 環境変数設定
cp .env.example .env

# 3. SECRET_KEY生成（重要！）
docker-compose -f docker/docker-compose.yml run --rm web \
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. .env ファイルに生成されたSECRET_KEYを設定
# SECRET_KEY=<生成されたキー>

# 5. Docker起動
docker-compose -f docker/docker-compose.yml up -d

# 6. マイグレーション実行
docker-compose -f docker/docker-compose.yml exec web python manage.py migrate

# 7. 開発サーバー確認
open http://localhost:8001
```

## 🔧 開発コマンド

### Django管理

```bash
# マイグレーション作成
docker-compose -f docker/docker-compose.yml exec web python manage.py makemigrations

# マイグレーション適用
docker-compose -f docker/docker-compose.yml exec web python manage.py migrate

# スーパーユーザー作成
docker-compose -f docker/docker-compose.yml exec web python manage.py createsuperuser

# Djangoシェル
docker-compose -f docker/docker-compose.yml exec web python manage.py shell
```

### テスト・Lint

```bash
# Lint実行
docker-compose -f docker/docker-compose.yml exec web ruff check .

# Lint自動修正
docker-compose -f docker/docker-compose.yml exec web ruff check --fix .

# テスト実行
docker-compose -f docker/docker-compose.yml exec web pytest

# カバレッジ付きテスト
docker-compose -f docker/docker-compose.yml exec web pytest --cov=apps --cov-report=term-missing
```

### Docker操作

```bash
# コンテナ起動
docker-compose -f docker/docker-compose.yml up -d

# コンテナ停止
docker-compose -f docker/docker-compose.yml down

# ログ確認
docker-compose -f docker/docker-compose.yml logs -f web

# コンテナ再ビルド
docker-compose -f docker/docker-compose.yml up -d --build
```

## 📁 プロジェクト構造

```
mettai/
├── apps/                    # Djangoアプリケーション
│   ├── accounts/           # 認証・ユーザー管理
│   └── rules/              # URLルール管理
├── config/                 # Django設定
│   ├── settings/
│   │   ├── base.py        # 共通設定
│   │   ├── development.py # 開発環境
│   │   ├── production.py  # 本番環境
│   │   └── testing.py     # テスト環境
│   └── urls.py            # ルーティング
├── docker/                 # Docker設定
│   ├── Dockerfile         # 本番用
│   ├── Dockerfile.dev     # 開発用
│   └── docker-compose.yml
├── .github/workflows/      # CI/CD
└── manage.py
```

## 🔐 セキュリティ

**重要**: 開発を始める前に必ず [SECURITY.md](SECURITY.md) を確認してください。

### クイックチェック

- ✅ `.env` ファイルを絶対にコミットしない
- ✅ SECRET_KEYを必ず新規生成する（`.env.example`のままにしない）
- ✅ コミット前に機密情報が含まれていないか確認

## 🌿 ブランチ戦略

Gitflowに準拠：

```
main              # 本番環境
  ├── feature/issue-XXX  # 機能開発
  ├── fix/issue-XXX      # バグ修正
  └── docs/issue-XXX     # ドキュメント
```

### ワークフロー

```bash
# 1. Issue番号でブランチ作成
git checkout -b feature/issue-001

# 2. 開発・コミット
git add .
git commit -m "Add feature X

Issue: #001"

# 3. プッシュ
git push origin feature/issue-001

# 4. PR作成（GitHub上）

# 5. CIパス確認

# 6. レビュー・マージ
```

## 🧪 テスト方針

### TDDサイクル

1. **Red**: 失敗するテストを書く
2. **Green**: テストが通る最小のコードを書く
3. **Refactor**: コードを改善する

### テスト配置

```python
apps/
└── rules/
    ├── models.py
    ├── serializers.py
    ├── views.py
    └── tests/
        ├── test_models.py
        ├── test_serializers.py
        └── test_views.py
```

## 📊 カバレッジ目標

| モジュール | 目標 |
|-----------|------|
| models.py | 90%+ |
| serializers.py | 90%+ |
| views.py | 85%+ |

## 🔗 関連ドキュメント

- [セキュリティガイドライン](SECURITY.md)
- [ビジネス要件定義](README.md)
- [技術設計書](.claude/rules/CLAUDE.md)
- [Issue管理](issues/)
