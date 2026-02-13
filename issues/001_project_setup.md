# Issue #001: プロジェクト初期設定

## 目的

Djangoプロジェクトの初期設定を行い、開発環境を構築する。TDD開発に必要な依存関係をインストールし、設定ファイルを整備する。

## 作成ファイル名

```
mettai/
├── manage.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── testing.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── apps/
    └── __init__.py
```

## ディレクトリ構成

```
mettai/
├── config/                    # Django プロジェクト設定
│   └── settings/             # 環境別設定
│       ├── base.py           # 共通設定
│       ├── development.py    # ローカル開発
│       ├── production.py     # 本番環境（CloudRun）
│       └── testing.py        # テスト環境
└── apps/                     # Django アプリケーション配置先
```

## 実装内容

### 1. requirements.txt

```
Django==5.1.5
djangorestframework==3.15.2
psycopg[binary]==3.2.4
django-cors-headers==4.6.0
django-environ==0.12.0
gunicorn==23.0.0
whitenoise==6.8.2
```

### 2. requirements-dev.txt

```
-r requirements.txt

pytest==8.3.4
pytest-django==4.9.0
pytest-cov==6.0.0
factory-boy==3.3.1
ruff==0.9.4
django-debug-toolbar==5.0.1
ipython==8.31.0
```

### 3. pyproject.toml

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "DJ",   # flake8-django
]

[tool.ruff.lint.isort]
known-first-party = ["apps", "config"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.testing"
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--strict-markers --tb=short"

[tool.coverage.run]
source = ["apps"]
omit = ["*/migrations/*", "*/tests/*", "*/admin.py"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### 4. .env.example

```
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://user:password@localhost:5432/mettai_dev

# CORS
CORS_ALLOWED_ORIGINS=chrome-extension://your-extension-id
```

### 5. config/settings/base.py

共通設定を実装：
- INSTALLED_APPS
- MIDDLEWARE
- TEMPLATES
- REST_FRAMEWORK 設定
- CORS 設定
- 国際化設定

### 6. config/settings/development.py

開発環境固有設定：
- DEBUG = True
- django-debug-toolbar
- SQLite or PostgreSQL（Docker）

### 7. config/settings/production.py

本番環境設定：
- DEBUG = False
- セキュリティ設定（HSTS, SSL, CSRF）
- PostgreSQL（Railway）
- Whitenoise 静的ファイル配信

### 8. config/settings/testing.py

テスト環境設定：
- PostgreSQL（GitHub Actions services）
- 高速化設定

### 9. .github/workflows/ci.yml

CI/CD パイプライン：
- ruff check
- pytest --cov

## テスト要件

### テスト観点

1. **設定ファイルの読み込み確認**
   - 各環境設定が正しくロードされること
   - 環境変数が適切に読み込まれること

2. **依存関係の整合性**
   - requirements.txt の全パッケージがインストール可能
   - バージョン競合がないこと

3. **Django プロジェクトの起動確認**
   - `python manage.py check` がエラーなく完了
   - `python manage.py migrate` が実行可能

### テストコマンド

```bash
# Lint チェック
ruff check .

# Django チェック
python manage.py check --settings=config.settings.testing

# マイグレーション確認
python manage.py makemigrations --check --dry-run

# テスト実行（この段階ではテストなし）
pytest --cov=apps --cov-report=term-missing
```

## 完了条件

- [ ] Django プロジェクトが起動する
- [ ] 環境別設定（development, production, testing）が動作する
- [ ] ruff check がエラーなく完了する
- [ ] pytest が実行可能（テストケースは0件でOK）
- [ ] GitHub Actions CI が設定され、グリーンになる

## 備考

- TDD サイクルの「Red」フェーズはスキップ（設定ファイルのため）
- 後続の Issue からは **必ず失敗するテストを先に書く** こと
