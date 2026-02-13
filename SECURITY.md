# セキュリティガイドライン

## 🔐 機密情報の取り扱い

### 絶対にコミットしてはいけないもの

- ✅ `.env` ファイル（実際の環境変数）
- ✅ SECRET_KEY の実際の値
- ✅ データベース接続文字列（本番環境）
- ✅ APIキー、トークン、パスワード
- ✅ 拡張機能のプライベートキー

### コミット前チェックリスト

コミット前に必ず確認：

```bash
# 1. .env ファイルが含まれていないか
git status | grep -E "\.env$"

# 2. SECRET_KEY が含まれていないか
git diff --cached | grep -i "SECRET_KEY.*=.*['\"]django-"

# 3. 機密情報が含まれていないか
git diff --cached | grep -iE "(password|secret|key|token).*=.*['\"][^{]"
```

### SECRET_KEY の生成方法

新しいSECRET_KEYを生成する場合：

```python
# Python対話シェルで実行
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

または：

```bash
# Dockerコンテナ内で生成
docker-compose exec web python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 🛡️ 環境変数の設定

### 開発環境

1. `.env.example` をコピー：
   ```bash
   cp .env.example .env
   ```

2. `.env` を編集して実際の値を設定：
   ```bash
   SECRET_KEY=<generate-random-key>
   DATABASE_URL=postgres://mettai:mettai_dev_password@db:5432/mettai_dev
   ```

### 本番環境（Cloud Run）

環境変数は Secret Manager を使用：

```bash
# Secret Manager に登録
gcloud secrets create django-secret-key --data-file=-
# 入力: <your-actual-secret-key>

# Cloud Run で環境変数として設定
gcloud run deploy mettai \
  --set-secrets="SECRET_KEY=django-secret-key:latest"
```

## 🚨 誤ってコミットしてしまった場合

### 本番環境のキーを誤ってコミット

1. **即座に無効化**: 新しいSECRET_KEYを生成して本番環境を更新
2. **Git履歴を書き換え**: `git filter-branch` または BFG Repo-Cleaner
3. **Force push**: `git push --force-with-lease`
4. **チームに通知**: 全員に `git pull --rebase` を依頼

### 開発環境のキー（今回のケース）

- 実害なし（開発用のデフォルトキー）
- 修正コミットを追加（既に対応済み）
- 今後は注意

## 📋 定期的なセキュリティチェック

- [ ] 週次: `.env` ファイルが .gitignore に含まれているか確認
- [ ] 月次: GitHub Security Alerts を確認
- [ ] リリース前: 全環境変数が適切に設定されているか確認

## 🔍 参考リンク

- [Django Security](https://docs.djangoproject.com/en/5.1/topics/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
