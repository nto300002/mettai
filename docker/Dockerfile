# ============================================================
# Production Dockerfile for Mettai Django App
# ============================================================
FROM python:3.12-slim as builder

WORKDIR /app

# システム依存パッケージ
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python依存インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# PostgreSQL クライアント（マイグレーション用）
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python 依存をコピー
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# アプリケーションコードをコピー
COPY . .

# 静的ファイル収集
RUN python manage.py collectstatic --noinput --settings=config.settings.production

# 非rootユーザーで実行
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

# Cloud Run の PORT 環境変数を使用
ENV PORT=8080
EXPOSE 8080

# 起動スクリプト
CMD ["sh", "-c", "python manage.py migrate --settings=config.settings.production && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60"]
