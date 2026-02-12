# 滅諦（Mettai）— 技術設計書

> **文書種別:** 技術設計書  
> **バージョン:** v1.0  
> **作成日:** 2026年2月11日  
> **ステータス:** Draft  
> **対象:** バックエンド（Django）+ ブラウザ拡張（WebExtensions）

---

## 目次

1. [開発手法（TDD）](#1-開発手法tdd)
2. [データベース設計](#2-データベース設計)
3. [コーディング規約](#3-コーディング規約)
4. [テストライブラリ比較検討](#4-テストライブラリ比較検討)
5. [依存ライブラリ（requirements.txt）](#5-依存ライブラリrequirementstxt)
6. [インフラ＋デプロイ戦略](#6-インフラデプロイ戦略)
7. [セキュリティ要件](#7-セキュリティ要件)
8. [スケーリング設計](#8-スケーリング設計)

---

## 1. 開発手法（TDD）

### 1.1 TDDサイクル

本プロジェクトは **Red → Green → Refactor** のTDDサイクルを厳守する。

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   ① Red: 失敗するテストを書く                        │
│      │                                              │
│      ▼                                              │
│   ② Green: テストが通る最小のコードを書く             │
│      │                                              │
│      ▼                                              │
│   ③ Refactor: テストを壊さずにコードを改善する        │
│      │                                              │
│      └──────────── ①に戻る ──────────────────────────│
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 1.2 テストの種類と実装順序

| テスト種別 | 対象 | 実行頻度 | ツール |
|-----------|------|---------|--------|
| ユニットテスト | Model, Serializer, matcher.js | 毎コミット | pytest + Jest |
| 統合テスト | API エンドポイント（View + DB） | 毎コミット | pytest + DRF APIClient |
| E2Eテスト | 拡張機能 → API → DB の一連の流れ | PR毎 | Playwright（将来） |

### 1.3 TDDの適用方針

```
■ 必ずTDDで書くもの（テストファースト必須）
  ├── URLマッチングエンジン（matcher.js）
  ├── Model のバリデーション・制約
  ├── Serializer の入力検証
  ├── API エンドポイントの正常系/異常系
  └── 認証・認可ロジック

■ テスト後付け可のもの
  ├── Django Admin のカスタマイズ
  ├── CSS / HTML テンプレート
  └── ビルドスクリプト（build.sh）
```

### 1.4 テストファイル命名規則

```
tests/
├── test_models.py          # Model 単体テスト
├── test_serializers.py     # Serializer テスト
├── test_views.py           # API エンドポイントテスト
├── test_auth.py            # 認証系テスト
└── test_matching.py        # URLマッチングロジック（Python版）

extension/
└── shared/utils/
    ├── matcher.test.js     # URLマッチングエンジン
    └── api.test.js         # API通信モジュール
```

### 1.5 カバレッジ目標

| モジュール | 目標カバレッジ | 理由 |
|-----------|--------------|------|
| matcher.js | 95%以上 | アプリのコア。パターンの漏れが直接UXに影響 |
| models.py | 90%以上 | データ整合性の保証 |
| serializers.py | 90%以上 | 入力バリデーションの網羅 |
| views.py | 85%以上 | 正常系+主要な異常系 |
| 拡張機能（background.js 等） | 70%以上 | ブラウザAPI依存部分はモック対応 |

---

## 2. データベース設計

### 2.1 RDBMS選定

| 候補 | 長所 | 短所 | 判定 |
|------|------|------|------|
| **Neon (Serverless PostgreSQL)** | スケールトゥゼロ、無料枠充実、ブランチ機能、PostgreSQL完全互換 | コールドスタート遅延（~500ms）、Free枠0.5GB | **✅ 採用** |
| Railway PostgreSQL | 常時起動、設定不要 | 最低$5/月、PaaS ロックイン | ❌ 不採用 |
| Supabase | PostgreSQL + Auth + Realtime同梱 | 機能過剰、Free枠500MBだが制約多い | ❌ 不採用 |
| SQLite | ゼロ設定、軽量 | 同時接続制限、マイグレーション制約 | ❌ 開発時のみ |

#### Neon 選定理由

1. **コスト最小化:** Free枠で100 CU-hours/月・0.5GB ストレージ。MVPの3テーブル構成には十分
2. **スケールトゥゼロ:** アイドル時（5分無操作）に自動サスペンド。使った分だけ課金
3. **PostgreSQL完全互換:** Django ORM / psycopg との互換性100%。移行コストゼロ
4. **ブランチ機能:** 本番DBをコピーゼロでブランチし、開発・テスト環境を即座に作成可能
5. **将来拡張:** v2の衝動ログ（時系列データ）やAI分析結果（JSONField）にもPostgreSQLとして対応

#### Neon Free プラン仕様（2026年1月時点）

| 項目 | 制限 |
|------|------|
| Compute | 100 CU-hours/月（0.25CU連続で約400時間） |
| Storage | 0.5 GB/プロジェクト |
| プロジェクト数 | 最大20 |
| ブランチ | 最大10/プロジェクト |
| Auto-scaling | 最大2 CU（1vCPU + 4GB RAM相当） |
| Scale-to-zero | 5分アイドルで自動サスペンド |
| PITR（復元） | 6時間 or 1GBの変更分（早い方） |

### 2.2 ERD

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│      User        │     │   UserSetting     │     │     URLRule       │
├─────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id         (PK) │◄──┐ │ id          (PK) │     │ id          (PK) │
│ username        │   ├─│ user_id (FK, UQ) │  ┌──│ user_id     (FK) │
│ email    (UQ)   │   │ │ mode             │  │  │ list_type        │
│ password        │   │ │ created_at       │  │  │ match_type       │
│ is_active       │   │ │ updated_at       │  │  │ pattern          │
│ date_joined     │   │ └──────────────────┘  │  │ label            │
└─────────────────┘   │                       │  │ is_active        │
                      └───────────────────────┘  │ created_at       │
                                                 │ updated_at       │
                                                 └──────────────────┘
                                                  UNIQUE (user_id, list_type, pattern)
```

### 2.3 テーブル定義（DDL相当）

#### User（Django AbstractUser 継承）

MVP段階ではDjango標準のAbstractUserをそのまま使用する。カスタムフィールドは追加しない。

```sql
-- Django が自動生成する auth_user テーブルに相当
-- カスタムユーザーモデルとして accounts.User を定義し、AUTH_USER_MODEL で指定

CREATE TABLE accounts_user (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(150) NOT NULL UNIQUE,
    email           VARCHAR(254) NOT NULL UNIQUE,
    password        VARCHAR(128) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_staff        BOOLEAN NOT NULL DEFAULT FALSE,
    is_superuser    BOOLEAN NOT NULL DEFAULT FALSE,
    date_joined     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_email ON accounts_user (email);
```

#### UserSetting

```sql
CREATE TABLE rules_usersetting (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES accounts_user(id) ON DELETE CASCADE,
    mode            VARCHAR(10) NOT NULL DEFAULT 'blacklist'
                    CHECK (mode IN ('blacklist', 'whitelist')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### URLRule

```sql
CREATE TABLE rules_urlrule (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    list_type       VARCHAR(10) NOT NULL
                    CHECK (list_type IN ('whitelist', 'blacklist')),
    match_type      VARCHAR(10) NOT NULL DEFAULT 'keyword'
                    CHECK (match_type IN ('keyword', 'domain', 'regex')),
    pattern         VARCHAR(500) NOT NULL,
    label           VARCHAR(100) NOT NULL DEFAULT '',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_list_pattern UNIQUE (user_id, list_type, pattern)
);

CREATE INDEX idx_urlrule_user_active ON rules_urlrule (user_id, is_active);
CREATE INDEX idx_urlrule_user_listtype ON rules_urlrule (user_id, list_type);
```

### 2.4 インデックス設計

| テーブル | インデックス | 種別 | 用途 |
|---------|------------|------|------|
| accounts_user | email | UNIQUE | ログイン時のメール検索 |
| rules_urlrule | (user_id, is_active) | B-Tree 複合 | /api/rules/sync/ のクエリ最適化 |
| rules_urlrule | (user_id, list_type) | B-Tree 複合 | モード別ルール取得 |
| rules_urlrule | (user_id, list_type, pattern) | UNIQUE 複合 | 重複ルール防止 |

### 2.5 クエリ設計（主要パス）

#### /api/rules/sync/（最頻出クエリ）

拡張機能が5分間隔でポーリングするエンドポイント。1ユーザーあたり1クエリで完結させる。

```sql
-- ユーザー設定 + アクティブなルールを1回で取得
-- Django ORM: URLRule.objects.filter(user=request.user, is_active=True)
--             .values('pattern', 'match_type')

SELECT r.pattern, r.match_type
FROM rules_urlrule r
WHERE r.user_id = %s
  AND r.is_active = TRUE;

-- 実行計画: idx_urlrule_user_active を使用
-- 想定行数: 5〜30行/ユーザー
-- 想定応答: < 1ms
```

#### N+1問題の防止規則

```python
# ❌ 禁止: ループ内クエリ
for user in User.objects.all():
    rules = URLRule.objects.filter(user=user)  # N+1

# ✅ 推奨: select_related / prefetch_related
users = User.objects.prefetch_related('urlrule_set').all()

# ✅ 推奨: values() による軽量クエリ
rules = URLRule.objects.filter(
    user=request.user, is_active=True
).values('pattern', 'match_type')  # SELECT 2列のみ
```

### 2.6 マイグレーション運用

| ルール | 内容 |
|--------|------|
| 命名規則 | `NNNN_<action>_<table>.py`（例: `0002_add_index_urlrule.py`） |
| 破壊的変更 | カラム削除・型変更は2段階マイグレーション（追加→移行→削除） |
| データマイグレーション | `RunPython` で別ファイルに分離。ロールバック関数を必ず書く |
| 本番適用 | `--plan` で確認後に `migrate` 実行。バックアップ必須 |

---

## 3. コーディング規約

### 3.1 ディレクトリ構成

```
mettai/
├── manage.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml                # Black, isort, pytest 設定
├── .env.example
│
├── config/                       # プロジェクト設定（旧 mettai/）
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py               # 共通設定
│   │   ├── development.py        # 開発環境
│   │   ├── production.py         # 本番環境
│   │   └── testing.py            # テスト環境
│   ├── urls.py                   # ルートURL
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── accounts/                 # 認証・ユーザー管理
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       ├── test_serializers.py
│   │       └── test_views.py
│   │
│   └── rules/                    # URLルール管理
│       ├── __init__.py
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       ├── services.py           # ビジネスロジック層
│       ├── admin.py
│       └── tests/
│           ├── __init__.py
│           ├── test_models.py
│           ├── test_serializers.py
│           ├── test_views.py
│           └── test_services.py
│
├── mettai-extension/             # ブラウザ拡張
│   ├── manifest.chrome.json
│   ├── manifest.firefox.json
│   ├── shared/
│   │   ├── background.js
│   │   ├── content/overlay.js
│   │   ├── popup/
│   │   │   ├── popup.html
│   │   │   ├── popup.js
│   │   │   └── popup.css
│   │   ├── utils/
│   │   │   ├── matcher.js
│   │   │   ├── matcher.test.js
│   │   │   ├── api.js
│   │   │   ├── api.test.js
│   │   │   └── storage.js
│   │   └── styles/overlay.css
│   ├── vendor/browser-polyfill.min.js
│   ├── package.json
│   ├── jest.config.js
│   └── build.sh
│
├── Dockerfile                    # 本番用マルチステージビルド（Cloud Run）
├── Dockerfile.dev                # ローカル開発用
├── docker-compose.yml            # ローカル開発環境
├── docker-compose.ci.yml         # CI テスト用
├── .dockerignore
│
└── clouddeploy/
    └── cloudbuild.yaml           # Cloud Build 設定
```

### 3.2 インポート規約

#### Python（Django）

```python
# ============================================================
# インポート順序（isort で自動整形）
# ============================================================

# 1. 標準ライブラリ
import re
from datetime import timedelta

# 2. サードパーティ
from django.conf import settings
from django.db import models
from rest_framework import serializers, status
from rest_framework.response import Response

# 3. ローカルアプリケーション（絶対インポート）
from apps.accounts.models import User
from apps.rules.models import URLRule, UserSetting
from apps.rules.services import RuleSyncService
```

**絶対インポートを使用する。** 相対インポート（`from .models import ...`）は同一app内のみ許可する。app間の参照は必ず `apps.xxx` の絶対パスで記述する。

```python
# ✅ 同一app内: 相対インポート許可
# apps/rules/serializers.py
from .models import URLRule

# ✅ app間: 絶対インポート必須
# apps/rules/views.py
from apps.accounts.models import User

# ❌ 禁止: app間の相対インポート
from ..accounts.models import User
```

#### JavaScript（拡張機能）

```javascript
// ============================================================
// インポート順序
// ============================================================

// 1. ブラウザAPI（polyfill経由）
// browser.* はグローバル（importなし）

// 2. ユーティリティ（相対パス）
import { shouldBlock, matchUrl } from '../utils/matcher.js';
import { fetchConfig } from '../utils/api.js';
import { getCached, setCached } from '../utils/storage.js';
```

拡張機能はバンドラーを使用しないため、ES Modules（`type: "module"`）は使用せず、共有コードは `shared/utils/` に配置してManifestの `background.scripts` で読み込む。

### 3.3 同期処理 vs 非同期処理の統一

#### 方針: Django は同期統一、拡張は非同期統一

| レイヤー | 方式 | 理由 |
|---------|------|------|
| Django View | **同期（sync）** | DRF の標準パターン。MVP規模でasyncのメリットなし |
| Django ORM | **同期（sync）** | Django ORM は同期設計。async ORM は5.x でも実験的 |
| 拡張 background.js | **非同期（async/await）** | ブラウザAPIが全てPromiseベース |
| 拡張 popup.js | **非同期（async/await）** | API通信・storage操作が非同期 |
| 拡張 overlay.js | **同期主体** | DOM操作中心。タイマーのみsetTimeout |

```python
# ============================================================
# Django: 同期で統一
# ============================================================

# ✅ 推奨: 同期View
class RuleSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        setting = UserSetting.objects.get(user=request.user)
        rules = URLRule.objects.filter(
            user=request.user, is_active=True
        ).values('pattern', 'match_type')
        return Response({
            'mode': setting.mode,
            'rules': list(rules),
        })

# ❌ 禁止: 非同期View（MVPでは不要な複雑さ）
class RuleSyncView(APIView):
    async def get(self, request):
        ...
```

```javascript
// ============================================================
// 拡張機能: async/await で統一
// ============================================================

// ✅ 推奨: async/await
async function fetchConfig() {
    const token = await browser.storage.local.get('token');
    const response = await fetch(`${API_BASE}/rules/sync/`, {
        headers: { 'Authorization': `Token ${token.token}` }
    });
    return response.json();
}

// ❌ 禁止: .then() チェーン
function fetchConfig() {
    return browser.storage.local.get('token')
        .then(token => fetch(...))
        .then(res => res.json());
}

// ❌ 禁止: コールバック
function fetchConfig(callback) {
    chrome.storage.local.get('token', function(result) {
        ...
    });
}
```

### 3.4 アーキテクチャ設計（各層の責務）

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│              urls.py → views.py (ViewSet)               │
│  責務: HTTPリクエスト/レスポンスの変換、認証チェック         │
│  禁止: ビジネスロジック、直接SQL                           │
├─────────────────────────────────────────────────────────┤
│                   Serialization Layer                    │
│                    serializers.py                        │
│  責務: 入力バリデーション、出力整形、型変換                 │
│  禁止: DB操作、外部API呼び出し                            │
├─────────────────────────────────────────────────────────┤
│                    Business Logic Layer                  │
│                     services.py                          │
│  責務: ドメインロジック、複数Modelの協調、トランザクション    │
│  禁止: HTTPオブジェクトへの依存（request, response）       │
├─────────────────────────────────────────────────────────┤
│                      Data Layer                         │
│                models.py + managers.py                   │
│  責務: データ定義、制約、基本CRUD、カスタムクエリセット      │
│  禁止: プレゼンテーション関心事                            │
└─────────────────────────────────────────────────────────┘
```

#### 層間の呼び出しルール

```
views.py  →  serializers.py  →  services.py  →  models.py
   │              │                  │               │
   │              │                  │               └── DB操作
   │              │                  └── ビジネスロジック
   │              └── バリデーション・整形
   └── HTTPハンドリング

✅ 上位層は直下の層のみ呼び出す
✅ services.py は models.py を直接呼び出してよい
❌ views.py が models.py を直接呼ぶのは単純なCRUDのみ許可
❌ serializers.py が他appの models.py を直接呼ぶことは禁止
```

#### 各層の具体例

```python
# ── urls.py（ルーティングのみ）──────────────────────
from django.urls import path
from apps.rules.views import RuleListCreateView, RuleSyncView

urlpatterns = [
    path('rules/', RuleListCreateView.as_view()),
    path('rules/sync/', RuleSyncView.as_view()),
]


# ── views.py（HTTP関心事のみ）──────────────────────
class RuleListCreateView(generics.ListCreateAPIView):
    """URLルールの一覧取得・新規作成"""
    serializer_class = URLRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return URLRule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ── serializers.py（バリデーションのみ）─────────────
class URLRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = URLRule
        fields = ['id', 'list_type', 'match_type', 'pattern',
                  'label', 'is_active']

    def validate_pattern(self, value):
        """正規表現パターンのコンパイルテスト"""
        if self.initial_data.get('match_type') == 'regex':
            try:
                re.compile(value)
            except re.error as e:
                raise serializers.ValidationError(
                    f"無効な正規表現です: {e}"
                )
        return value


# ── services.py（ビジネスロジック）──────────────────
class RuleSyncService:
    """拡張機能用の同期データを構築する"""

    @staticmethod
    def get_sync_data(user):
        setting, _ = UserSetting.objects.get_or_create(user=user)
        rules = URLRule.objects.filter(
            user=user, is_active=True
        ).values('pattern', 'match_type')
        latest = URLRule.objects.filter(
            user=user
        ).order_by('-updated_at').values_list(
            'updated_at', flat=True
        ).first()

        return {
            'mode': setting.mode,
            'rules': list(rules),
            'updated_at': latest,
        }


# ── models.py（データ定義と制約）───────────────────
class URLRule(models.Model):
    LIST_TYPE_CHOICES = [
        ('whitelist', 'Whitelist'),
        ('blacklist', 'Blacklist'),
    ]
    MATCH_TYPE_CHOICES = [
        ('keyword', 'Keyword'),
        ('domain', 'Domain'),
        ('regex', 'Regex'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    list_type = models.CharField(max_length=10,
                                 choices=LIST_TYPE_CHOICES)
    match_type = models.CharField(max_length=10,
                                  choices=MATCH_TYPE_CHOICES,
                                  default='keyword')
    pattern = models.CharField(max_length=500)
    label = models.CharField(max_length=100, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'list_type', 'pattern'],
                name='uq_user_list_pattern'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'is_active'],
                         name='idx_urlrule_user_active'),
        ]
```

### 3.5 命名規約

| 対象 | 規約 | 例 |
|------|------|-----|
| Pythonファイル | snake_case | `url_rule.py`, `rule_sync_service.py` |
| Pythonクラス | PascalCase | `URLRule`, `RuleSyncService` |
| Python関数/変数 | snake_case | `get_sync_data`, `is_active` |
| Python定数 | UPPER_SNAKE | `MAX_RULES_PER_USER = 100` |
| JavaScriptファイル | camelCase | `matcher.js`, `api.js` |
| JavaScript関数/変数 | camelCase | `shouldBlock`, `fetchConfig` |
| JavaScript定数 | UPPER_SNAKE | `API_BASE_URL`, `CACHE_TTL_MS` |
| APIエンドポイント | kebab-case（複数形） | `/api/rules/`, `/api/auth/login/` |
| DBテーブル | `<app>_<model>` snake_case | `rules_urlrule` |
| DBカラム | snake_case | `match_type`, `is_active` |
| テストメソッド | `test_<動作>_<条件>_<期待結果>` | `test_sync_returns_active_rules_only` |

### 3.6 エラーハンドリング規約

```python
# ── API レスポンス形式の統一 ──────────────────────

# 成功
{
    "mode": "blacklist",
    "rules": [...]
}

# エラー（DRF標準形式を踏襲）
{
    "detail": "認証情報が含まれていません。"          # 単一エラー
}
{
    "pattern": ["無効な正規表現です: ..."],            # フィールドエラー
    "match_type": ["この値は有効ではありません。"]
}
{
    "non_field_errors": ["この組み合わせは既に存在します。"]  # 複合エラー
}
```

```python
# ── HTTPステータスコードの使い分け ────────────────

# 200: 取得・更新成功
# 201: 作成成功
# 204: 削除成功（レスポンスボディなし）
# 400: バリデーションエラー（入力が不正）
# 401: 認証エラー（トークン不正/期限切れ）
# 403: 権限エラー（他ユーザーのリソースへのアクセス）
# 404: リソースが存在しない
# 409: 競合（重複ルール登録時）
# 500: サーバーエラー（意図しないエラー）
```

---

## 4. テストライブラリ比較検討

### 4.1 Python テストフレームワーク

| 項目 | unittest（標準） | **pytest** | nose2 |
|------|-----------------|-----------|-------|
| アサーション | `self.assertEqual(a, b)` | `assert a == b` | unittest互換 |
| フィクスチャ | `setUp/tearDown` | `@pytest.fixture`（柔軟） | unittest互換 |
| パラメタライズ | ❌ 非対応 | `@pytest.mark.parametrize` | ❌ |
| Django統合 | ○ 標準対応 | ○ `pytest-django` | △ |
| 実行速度 | 普通 | 速い（並列 `pytest-xdist`） | 普通 |
| プラグイン | 少ない | 豊富（1000+） | 少ない |
| 出力の見やすさ | △ | ◎（差分表示が優秀） | △ |
| 学習コスト | 低 | 低 | 中 |
| **判定** | ❌ | **✅ 採用** | ❌ |

**採用理由:** `assert` 文による直感的な記述、`@pytest.fixture` の柔軟なDI、`@pytest.mark.parametrize` によるマッチングパターンの網羅テスト、`pytest-cov` によるカバレッジ計測の容易さ。

### 4.2 JavaScript テストフレームワーク

| 項目 | **Jest** | Vitest | Mocha + Chai |
|------|---------|--------|-------------|
| 設定量 | ゼロコンフィグ | ゼロコンフィグ | 設定多い |
| 実行速度 | 普通 | 高速（ESM native） | 普通 |
| モック | 内蔵（`jest.fn()`） | 内蔵（Jest互換） | 要 sinon |
| アサーション | 内蔵（`expect`） | 内蔵（Jest互換） | 要 chai |
| カバレッジ | 内蔵（`--coverage`） | 内蔵（c8） | 要 nyc |
| ブラウザAPI モック | `jest.mock` で可 | 可 | 可 |
| Node.js互換 | ◎ | ◎ | ◎ |
| **判定** | **✅ 採用** | △ 候補 | ❌ |

**採用理由:** matcher.js のテストが主用途。ゼロコンフィグ、モック内蔵、カバレッジ内蔵で追加依存なし。拡張機能はバンドラー不使用のため、Vitestの速度メリットが薄い。

### 4.3 採用するテストツール一覧

| ツール | バージョン | 用途 |
|--------|-----------|------|
| pytest | 8.x | Python テストランナー |
| pytest-django | 4.x | Django テスト統合 |
| pytest-cov | 5.x | カバレッジ計測 |
| pytest-xdist | 3.x | テスト並列実行（将来） |
| factory-boy | 3.x | テストデータ生成 |
| Jest | 29.x | JavaScript テストランナー |

---

## 5. 依存ライブラリ（requirements.txt）

### 5.1 本番依存（requirements.txt）

```
# ── Web Framework ──────────────────────────────
Django==5.1.5
djangorestframework==3.15.2

# ── Database ───────────────────────────────────
psycopg[binary]==3.2.4           # PostgreSQL アダプタ（libpq不要のbinary版）

# ── Authentication ─────────────────────────────
# DRF TokenAuthentication を使用（追加ライブラリ不要）

# ── CORS ───────────────────────────────────────
django-cors-headers==4.6.0       # 拡張機能からのクロスオリジン通信

# ── Environment ────────────────────────────────
django-environ==0.12.0           # .env ファイルからの設定読み込み

# ── Production Server ─────────────────────────
gunicorn==23.0.0                 # WSGI サーバー

# ── Static Files ───────────────────────────────
whitenoise==6.8.2                # 静的ファイル配信（Django Admin用）
```

### 5.2 開発依存（requirements-dev.txt）

```
-r requirements.txt

# ── Testing ────────────────────────────────────
pytest==8.3.4
pytest-django==4.9.0
pytest-cov==6.0.0
factory-boy==3.3.1

# ── Linting & Formatting ──────────────────────
ruff==0.9.4                      # Linter + Formatter（Black+isort+flake8 統合）

# ── Debug ──────────────────────────────────────
django-debug-toolbar==5.0.1      # 開発時のSQLクエリ確認
ipython==8.31.0                  # 対話シェル強化
```

### 5.3 ライブラリ選定の補足

| ライブラリ | 不採用候補 | 選定理由 |
|-----------|-----------|---------|
| psycopg[binary] 3.x | psycopg2-binary | psycopg3はasync対応、型ヒント強化。将来のasync移行に備える |
| django-environ | python-decouple | Django設定との統合が自然。db(), cache() ヘルパーが便利 |
| ruff | Black + isort + flake8 | 1ツールで3機能を統合。高速（Rust製） |
| gunicorn | uvicorn | 同期View統一のためWSGI。ASGIへの移行時にuvicornに切替 |
| whitenoise | nginx静的配信 | コンテナ単体で完結。Cloud Run デプロイとの親和性 |
| factory-boy | Faker単体 | Django Modelとの統合が強力。リレーション自動生成 |

---

## 6. インフラ＋デプロイ戦略

### 6.1 基本方針

**最小コスト・最小運用負荷** を最優先する。MVPフェーズでは月額 $0〜$10 の範囲で運用し、ユーザー数に応じてスケールアップする。

### 6.2 インフラ構成比較

| 候補（App） | 候補（DB） | 月額合計 | デプロイ | 運用負荷 | 判定 |
|-------------|-----------|---------|---------|---------|------|
| **Cloud Run** | **Neon Free** | **$0** | Docker + gcloud | 最小 | **✅ 採用** |
| Railway | Neon Free | $0〜$5 | Git push | 最小 | △ PaaS依存 |
| Render Free | Neon Free | $0 | Git push | 最小 | △ 30秒コールドスタート |
| Fly.io | Neon Free | $0〜$5 | flyctl | 低 | △ CLI操作必要 |
| AWS (ECS+RDS) | RDS | $30〜 | CI/CD構築 | 高 | ❌ 過剰 |

#### Cloud Run 選定理由

1. **完全無料枠:** 月200万リクエスト・180,000 vCPU秒・360,000 GiB秒が無料。MVP には十分すぎる
2. **スケールトゥゼロ:** リクエストがない時はインスタンス0。Neon と組み合わせて App+DB 両方 $0
3. **Docker ネイティブ:** 標準 Dockerfile をそのままデプロイ。ベンダーロックインなし
4. **自動スケーリング:** トラフィックに応じて0〜N インスタンスを自動調整
5. **Google Cloud エコシステム:** Cloud Build、Artifact Registry、Cloud Logging、Secret Manager と連携
6. **カスタムドメイン+SSL自動:** Let's Encrypt 証明書を自動発行・更新

#### Cloud Run Free Tier 仕様（2026年時点）

| 項目 | 無料枠/月 |
|------|----------|
| リクエスト数 | 200万リクエスト |
| vCPU 時間 | 180,000 vCPU秒（= 50 vCPU時間） |
| メモリ時間 | 360,000 GiB秒（= 100 GiB時間） |
| ネットワーク（北米内） | 1 GiB 送信 |
| ビルド（Cloud Build） | 120分/日 |

### 6.3 採用構成: Cloud Run（App）+ Neon（Serverless DB）

```
                    Google Cloud
┌───────────────────────────────────────────────┐
│                                               │
│  Artifact Registry     Cloud Run              │
│  ┌──────────┐    ┌──────────────────┐         │
│  │  Docker   │───▶│  Django App      │         │
│  │  Image    │    │  (gunicorn)      │──┐      │
│  └──────────┘    │  256MB〜512MB RAM │  │      │
│                  │  0→N instances    │  │      │
│                  └──────┬───────────┘  │      │
│                         │              │      │
│  Secret Manager         │              │      │
│  ┌──────────┐           │              │      │
│  │ DB_URL    │───────────┘              │      │
│  │ SECRET_KEY│                         │      │
│  └──────────┘                          │      │
│                                        │      │
└────────────────────────────────────────┼──────┘
          │ HTTPS (自動SSL)              │
          │                              ▼
    ┌─────┴─────┐              ┌──────────────────┐
    │ Chrome拡張  │              │   Neon Database   │
    │ Firefox拡張 │              │   (Serverless PG) │
    └───────────┘              │                  │
     browser.storage に          │  Scale-to-zero   │
     トークン保存                 │  Auto-scaling    │
     5分間隔で sync              │  Branching       │
                               └──────────────────┘
```

#### 分離アーキテクチャの利点

| 利点 | 説明 |
|------|------|
| **ダブルゼロスケール** | Cloud Run + Neon 両方がスケールトゥゼロ。アイドル時は完全 $0 |
| コンテナポータビリティ | Docker イメージなのでどこでも動く。ベンダーロックインなし |
| 環境分離 | Neon のブランチ機能で dev/staging/prod を即座に複製 |
| 独立スケーリング | App と DB を別々にスケール。Cloud Run は自動、Neon は Auto-scaling |
| シークレット管理 | Secret Manager で DATABASE_URL 等を安全に注入 |

#### Docker 構成

```dockerfile
# ── Dockerfile（本番用マルチステージビルド）──────────

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

```dockerfile
# ── Dockerfile.dev（ローカル開発用）──────────

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

ENV DJANGO_SETTINGS_MODULE=config.settings.development
EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

```yaml
# ── docker-compose.yml（ローカル開発環境）──────────

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    env_file:
      - .env
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.development
```

```
# ── .dockerignore ──────────
.git
.github
__pycache__
*.pyc
*.pyo
.env
.env.*
node_modules
mettai-extension/
*.md
docs/
.vscode/
.idea/
docker-compose*.yml
Dockerfile.dev
```

#### Neon 接続設定

```python
# config/settings/production.py
import environ

env = environ.Env()

DATABASES = {
    'default': {
        **env.db('DATABASE_URL'),
        # Neon サーバーレス接続に最適化
        'CONN_MAX_AGE': 0,           # コネクションプーリングは Neon 側に委譲
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'sslmode': 'require',     # Neon は SSL 必須
        },
    }
}

# DATABASE_URL の形式（Neon ダッシュボードからコピー）:
# postgres://<user>:<password>@<endpoint>.neon.tech/<dbname>?sslmode=require
```

#### Neon ブランチ戦略

```
main (本番ブランチ)
  │
  ├── dev (開発ブランチ)        ← ローカル開発時に接続
  │     Copy-on-Write で即座に作成
  │     本番データのスナップショットで開発可能
  │
  └── ci-test (CI用ブランチ)    ← GitHub Actions で自動作成・破棄
        テスト実行 → ブランチ削除
        本番データを汚さない
```

#### コールドスタート対策

Cloud Run と Neon の両方がスケールトゥゼロするため、初回リクエストでは「Cloud Run コンテナ起動 + Neon DB ウォームアップ」が同時に発生する。合計 1〜3秒の遅延が想定される。

| レイヤー | 遅延 | 対策 |
|---------|------|------|
| Cloud Run | 500ms〜1s | コンテナイメージを軽量化（slim ベース、マルチステージ） |
| Neon DB | 300〜500ms | 拡張側キャッシュで DB 不要時はリクエストしない |
| 合計（初回） | 1〜2s | リトライ付き fetch + ローカルキャッシュで体感ゼロ |

```javascript
// ── api.js: Cloud Run + Neon ダブルコールドスタート対応 ──────────
async function fetchConfigWithRetry(maxRetries = 2) {
    for (let i = 0; i <= maxRetries; i++) {
        try {
            const response = await fetch(`${API_BASE}/rules/sync/`, {
                headers: { 'Authorization': `Token ${token}` },
                signal: AbortSignal.timeout(8000),  // 8秒タイムアウト（Cloud Run起動を考慮）
            });
            if (response.ok) return response.json();
            if (response.status >= 500 && i < maxRetries) {
                await new Promise(r => setTimeout(r, 2000));
                continue;
            }
            throw new Error(`API error: ${response.status}`);
        } catch (e) {
            if (i === maxRetries) throw e;
            await new Promise(r => setTimeout(r, 3000));  // Cloud Run 起動待ち
        }
    }
}
```

#### コスト見積もり（Cloud Run + Neon）

| フェーズ | ユーザー数 | Cloud Run | Neon | 月額合計 |
|---------|-----------|-----------|------|---------|
| MVP（開発中） | 1〜10 | Free ($0) | Free ($0) | **$0** |
| ローンチ初期 | 10〜100 | Free ($0) | Free ($0) | **$0** |
| 成長期 | 100〜1,000 | Free ($0) | Free〜Launch ($0〜$5) | **$0〜$5** |
| 拡大期 | 1,000〜10,000 | Free〜$5 | Launch ($5) | **$5〜$10** |
| 大規模 | 10,000+ | $10〜 | Scale ($19〜) | **$29〜** |

**Cloud Run Free Tier により、1,000 ユーザーまでは App 側コスト $0。旧 Railway 構成比で大幅にコスト削減。**

### 6.4 デプロイパイプライン

```
Developer
    │
    ▼
GitHub (main branch)
    │
    ├── Push / Merge
    │
    ▼
GitHub Actions (CI)
    │
    ├── 1. ruff check（Lint）
    ├── 2. pytest --cov（テスト + カバレッジ）
    ├── 3. jest --coverage（JS テスト）
    │
    ├── All Green?
    │   ├── Yes ─┐
    │   └── No  → 失敗通知（GitHub）
    │            │
    │            ▼
    │   Cloud Build (CD)
    │     ├── 4. docker build（マルチステージ）
    │     ├── 5. docker push → Artifact Registry
    │     ├── 6. gcloud run deploy（Cloud Run 更新）
    │     └── 7. python manage.py migrate（Direct エンドポイント経由）
    │
    ▼
Cloud Run (Production)
    └── gunicorn config.wsgi（コンテナ起動）
```

#### GitHub Actions + Cloud Build 設定

```yaml
# .github/workflows/ci-cd.yml
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
  AR_REPO: mettai-repo
  IMAGE: asia-northeast1-docker.pkg.dev/mettai-prod/mettai-repo/mettai-api

jobs:
  # ── CI: テスト ──────────────────────────
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: mettai_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: pytest --cov=apps --cov-report=term-missing
        env:
          DATABASE_URL: postgres://test:test@localhost:5432/mettai_test
          DJANGO_SETTINGS_MODULE: config.settings.testing

  test-js:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - working-directory: mettai-extension
        run: npm ci && npx jest --coverage

  # ── CD: ビルド＆デプロイ（main のみ）──────────
  deploy:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: [test, test-js]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write       # Workload Identity Federation

    steps:
      - uses: actions/checkout@v4

      # GCP 認証（Workload Identity Federation — キーレス）
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      # Docker ビルド & プッシュ
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud auth configure-docker ${{ env.REGION }}-docker.pkg.dev --quiet
      - run: |
          docker build -t ${{ env.IMAGE }}:${{ github.sha }} .
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

      # マイグレーション実行（Cloud Run Jobs or ローカル）
      - run: |
          gcloud run jobs execute mettai-migrate \
            --region ${{ env.REGION }} \
            --wait
```

```yaml
# ── clouddeploy/cloudbuild.yaml（代替: Cloud Build トリガー利用時）──

steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_IMAGE}:${SHORT_SHA}', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_IMAGE}:${SHORT_SHA}']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - '${_SERVICE_NAME}'
      - '--image=${_IMAGE}:${SHORT_SHA}'
      - '--region=${_REGION}'
      - '--allow-unauthenticated'
images:
  - '${_IMAGE}:${SHORT_SHA}'
substitutions:
  _IMAGE: asia-northeast1-docker.pkg.dev/mettai-prod/mettai-repo/mettai-api
  _SERVICE_NAME: mettai-api
  _REGION: asia-northeast1
```

### 6.5 環境管理

| 環境 | 用途 | App 実行環境 | DB | 設定ファイル |
|------|------|-------------|-----|------------|
| development | ローカル開発 | Docker Compose | Neon dev ブランチ | config/settings/development.py |
| testing | CI/CD テスト | GitHub Actions | PostgreSQL（services） | config/settings/testing.py |
| production | 本番 | Cloud Run | Neon main ブランチ | config/settings/production.py |

```python
# config/settings/production.py
import environ

env = environ.Env()

DEBUG = False
SECRET_KEY = env('SECRET_KEY')

# Cloud Run は単一ホスト名を割り当て。カスタムドメイン追加時は更新
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*.run.app'])

DATABASES = {
    'default': {
        **env.db('DATABASE_URL'),
        'CONN_MAX_AGE': 0,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'sslmode': 'require'},
    }
}

# Cloud Run は HTTPS 終端を行うため SSL_REDIRECT は不要
# ただし Cloud Run 外からの直接アクセスを防ぐためヘッダチェックを追加
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False   # Cloud Run のロードバランサが処理
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

---

## 7. セキュリティ要件

### 7.1 認証・認可

| 要件 | 実装 |
|------|------|
| 認証方式 | DRF TokenAuthentication |
| トークン保管（拡張） | `browser.storage.local`（暗号化ストレージ） |
| パスワード保存 | Django標準 PBKDF2_SHA256（iterations=870,000） |
| パスワード要件 | 最低8文字、Django標準バリデータ4種適用 |
| セッション | 使用しない（トークン認証のみ） |
| 権限分離 | 全API で `request.user` によるフィルタ。他ユーザーデータへのアクセス不可 |

#### データアクセス制御の実装パターン

```python
# ✅ 全ViewSet で get_queryset をオーバーライドし、
#    必ず request.user でフィルタする
class URLRuleViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return URLRule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# ❌ 禁止: pk のみでオブジェクト取得（IDOR脆弱性）
def get(self, request, pk):
    rule = URLRule.objects.get(pk=pk)  # 他ユーザーのデータが取れる
```

### 7.2 通信セキュリティ

| 要件 | 実装 |
|------|------|
| HTTPS強制 | Cloud Run が自動SSL終端。`SECURE_PROXY_SSL_HEADER` でプロキシ経由を検知 |
| HSTS | `SECURE_HSTS_SECONDS = 31536000`（1年） |
| CORS | `django-cors-headers` で拡張機能のオリジンのみ許可 |
| CSP | 拡張機能の `manifest.json` で `content_security_policy` 設定 |

#### CORS設定

```python
# config/settings/production.py
CORS_ALLOWED_ORIGINS = [
    # Chrome拡張のオリジン（拡張IDに依存）
    # chrome-extension://<extension-id>
]
CORS_ALLOW_CREDENTIALS = False  # トークン認証のため Cookie 不要
CORS_ALLOW_HEADERS = [
    'authorization',
    'content-type',
]
```

### 7.3 入力バリデーション

| 入力 | バリデーション |
|------|--------------|
| pattern（keyword） | 空文字禁止、500文字以内 |
| pattern（domain） | ドメイン形式チェック（`[a-zA-Z0-9.-]+`） |
| pattern（regex） | `re.compile()` でコンパイルテスト。失敗時は400 |
| email | Django EmailValidator |
| password | UserAttributeSimilarityValidator, MinimumLengthValidator(8), CommonPasswordValidator, NumericPasswordValidator |

#### 正規表現パターンのサニタイズ

```python
# ── serializers.py ─────────────────────────────
import re

def validate_pattern(self, value):
    match_type = self.initial_data.get('match_type', 'keyword')

    if match_type == 'regex':
        try:
            compiled = re.compile(value)
        except re.error as e:
            raise serializers.ValidationError(f"無効な正規表現: {e}")

        # ReDoS 対策: パターンの長さ制限
        if len(value) > 200:
            raise serializers.ValidationError(
                "正規表現は200文字以内にしてください"
            )

    return value
```

### 7.4 ReDoS（正規表現サービス拒否）対策

ユーザー入力の正規表現をそのまま実行するため、ReDoS攻撃のリスクがある。

| 対策 | 実装 |
|------|------|
| パターン長制限 | 正規表現は200文字以内 |
| タイムアウト | matcher.js でマッチング処理に100msタイムアウトを設定 |
| サーバー側不使用 | 正規表現マッチングはクライアント（拡張機能）のみで実行。サーバーはパターン保存のみ |

```javascript
// ── matcher.js: タイムアウト付き正規表現マッチング ──
function safeRegexTest(pattern, url, timeoutMs = 100) {
    const start = performance.now();
    try {
        const regex = new RegExp(pattern, 'i');
        const result = regex.test(url);
        const elapsed = performance.now() - start;
        if (elapsed > timeoutMs) {
            console.warn(`Regex timeout: ${pattern} took ${elapsed}ms`);
            return false;  // タイムアウトは「マッチしない」扱い
        }
        return result;
    } catch (e) {
        return false;  // 不正な正規表現は無視
    }
}
```

### 7.5 セキュリティヘッダ

```python
# config/settings/production.py
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
```

### 7.6 依存パッケージの脆弱性管理

| ツール | 対象 | 実行タイミング |
|--------|------|--------------|
| `pip-audit` | Python依存 | CI（週次）+ リリース前 |
| `npm audit` | JS依存 | CI（週次）+ リリース前 |
| Dependabot | GitHub リポジトリ | 自動PR作成 |

---

## 8. スケーリング設計

### 8.1 ボトルネック分析

MVP段階で最も負荷がかかるのは `/api/rules/sync/` エンドポイントである。

```
アクティブユーザー × ポーリング頻度 = リクエスト/分

例: 100 DAU × 1回/5分 = 20 req/min（余裕）
    1,000 DAU × 1回/5分 = 200 req/min（要最適化）
    10,000 DAU × 1回/5分 = 2,000 req/min（要アーキテクチャ変更）
```

### 8.2 SQLメモリ効率

#### クエリ最適化

```python
# ── /api/rules/sync/ の最適化 ──────────────────

# ✅ 推奨: values() で必要カラムのみ取得
URLRule.objects.filter(
    user=request.user, is_active=True
).values('pattern', 'match_type')
# → SELECT pattern, match_type FROM rules_urlrule
#   WHERE user_id = %s AND is_active = TRUE
# メモリ: 辞書のリスト（Model インスタンスより軽量）

# ❌ 非推奨: 全カラム取得
URLRule.objects.filter(user=request.user, is_active=True)
# → SELECT * FROM rules_urlrule ...
# メモリ: Model インスタンス（各フィールドのPythonオブジェクト分重い）
```

#### メモリ消費量比較

| 取得方式 | 100ルールあたりメモリ | 備考 |
|---------|---------------------|------|
| `.all()`（Model インスタンス） | ~80KB | 全フィールド + Pythonオブジェクトヘッダ |
| `.values('pattern', 'match_type')` | ~12KB | 辞書2キーのみ |
| `.values_list('pattern', 'match_type')` | ~8KB | タプルのリスト（最軽量） |

#### 接続プール（Neon サーバーレス対応）

Neon はサーバー側で接続プーリングを提供する。Django 側は `CONN_MAX_AGE=0`（リクエスト毎に切断）で運用し、接続プールの管理を Neon に委譲する。

```python
# config/settings/production.py

DATABASES = {
    'default': {
        **env.db('DATABASE_URL'),
        # Neon サーバーレス: 接続プーリングは Neon 側
        'CONN_MAX_AGE': 0,            # リクエスト毎に接続を返却
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'sslmode': 'require',
            # Neon の接続プールエンドポイントを使用
            # DATABASE_URL に -pooler 付きホスト名を指定:
            # postgres://user:pw@ep-xxx-pooler.neon.tech/db?sslmode=require
        },
    }
}

# ── Neon 接続エンドポイントの使い分け ──────────
# Direct:  ep-xxx.neon.tech         → マイグレーション、管理コマンド用
# Pooler:  ep-xxx-pooler.neon.tech  → アプリケーション（gunicorn）用
#
# Django の DATABASE_URL には Pooler エンドポイントを設定し、
# マイグレーション時のみ環境変数で Direct に切り替える
```

```yaml
# Cloud Run 環境変数（Secret Manager 経由で注入）
DATABASE_URL=postgres://user:pw@ep-xxx-pooler.neon.tech/mettai?sslmode=require
MIGRATION_DATABASE_URL=postgres://user:pw@ep-xxx.neon.tech/mettai?sslmode=require
```

### 8.3 キャッシュ戦略

#### 拡張機能側キャッシュ（1次キャッシュ）

```javascript
// ── storage.js ────────────────────────────────
const CACHE_TTL_MS = 5 * 60 * 1000;  // 5分

async function getCachedConfig() {
    const cached = await browser.storage.local.get('ruleConfig');
    if (cached.ruleConfig) {
        const age = Date.now() - cached.ruleConfig.fetchedAt;
        if (age < CACHE_TTL_MS) {
            return cached.ruleConfig.data;  // キャッシュヒット
        }
    }
    // キャッシュミス → API取得
    const data = await fetchConfig();
    await browser.storage.local.set({
        ruleConfig: { data, fetchedAt: Date.now() }
    });
    return data;
}
```

#### サーバー側キャッシュ（2次キャッシュ・将来）

MVP段階ではサーバー側キャッシュは不要。1,000ユーザー超で以下を検討する。

```python
# ── 将来: Django キャッシュフレームワーク ────────

# Option A: メモリキャッシュ（LocMemCache）
#   長所: 追加サービス不要
#   短所: プロセス間で共有されない
#   適用: gunicorn 1 worker の場合

# Option B: Redis
#   長所: プロセス間共有、TTL管理
#   短所: 追加サービス（月額 $3〜）
#   適用: gunicorn 複数 worker、10,000+ ユーザー

# Option C: ETag/If-Modified-Since
#   長所: サーバー負荷軽減、追加サービス不要
#   短所: リクエスト自体は発生する
#   適用: 1,000〜10,000 ユーザー
```

#### ETagベースのキャッシュ（推奨・中規模）

```python
# ── views.py ───────────────────────────────────
from django.utils.http import http_date
from hashlib import md5

class RuleSyncView(APIView):
    def get(self, request):
        data = RuleSyncService.get_sync_data(request.user)

        # ETag生成
        etag = md5(str(data).encode()).hexdigest()
        if request.META.get('HTTP_IF_NONE_MATCH') == etag:
            return Response(status=304)  # Not Modified

        response = Response(data)
        response['ETag'] = etag
        response['Cache-Control'] = 'private, max-age=60'
        return response
```

```javascript
// ── api.js: ETag対応 ──────────────────────────
let cachedETag = null;

async function fetchConfig() {
    const headers = { 'Authorization': `Token ${token}` };
    if (cachedETag) {
        headers['If-None-Match'] = cachedETag;
    }

    const response = await fetch(`${API_BASE}/rules/sync/`, { headers });

    if (response.status === 304) {
        return null;  // キャッシュ有効、更新なし
    }

    cachedETag = response.headers.get('ETag');
    return response.json();
}
```

### 8.4 段階的スケーリング計画

| ユーザー数 | ボトルネック | 対策 | コスト変動 |
|-----------|------------|------|-----------|
| 〜100 | Cloud Run + Neon ダブルコールドスタート | 拡張側キャッシュ + リトライ | $0/月 |
| 100〜1,000 | sync APIの頻度 | ETag導入、ポーリング間隔を10分に延長 | $0〜$5/月 |
| 1,000〜5,000 | Neon CU-hours消費 | Neon Launch プラン、Pooler エンドポイント活用 | $5〜$10/月 |
| 5,000〜10,000 | Cloud Run インスタンス数 | max-instances 引上（10→30）、concurrency 調整、Neon Auto-scaling | $10〜$25/月 |
| 10,000+ | アーキテクチャ限界 | WebSocket（ポーリング廃止）、Redis キャッシュ導入 | $30+/月 |

### 8.5 Neon サーバーレス環境のチューニング

#### CU-hours 消費の最適化

Neon Free プランは月100 CU-hours。0.25CU で連続稼働すると約400時間（約16.7日）で枯渇する。以下で消費を最小化する。

| 最適化項目 | 実装 | 効果 |
|-----------|------|------|
| Scale-to-zero 活用 | アイドル5分で自動サスペンド（デフォルト） | 夜間・非アクティブ時の消費ゼロ |
| クエリ効率化 | `values()` / `values_list()` で最小カラム取得 | クエリ実行時間短縮 → CU消費削減 |
| N+1防止 | `select_related` / `prefetch_related` 必須 | DB往復回数削減 |
| 不要マイグレーション抑止 | `--check` で事前確認 | 不要なコンピュート起動を防止 |

```python
# ── 管理コマンド: Direct エンドポイント使用 ────────
# マイグレーション時は Pooler ではなく Direct 接続を使用
#
# $ DJANGO_DATABASE_URL=$MIGRATION_DATABASE_URL python manage.py migrate
```

#### ストレージ消費の管理

Neon Free プランは 0.5GB/プロジェクト。MVP の3テーブル構成での想定消費量：

| テーブル | 1ユーザーあたり | 100ユーザー | 1,000ユーザー |
|---------|---------------|------------|-------------|
| accounts_user | ~0.5KB | ~50KB | ~500KB |
| rules_usersetting | ~0.1KB | ~10KB | ~100KB |
| rules_urlrule（平均20ルール） | ~2KB | ~200KB | ~2MB |
| インデックス・メタデータ | - | ~50KB | ~500KB |
| **合計** | - | **~310KB** | **~3.1MB** |

1,000ユーザーでも約3MB。Free枠の0.5GBに対して余裕が大きい。ストレージがボトルネックになるのは v2 の衝動ログ導入後（推定 10,000ユーザー以上）。

### 8.6 監視・アラート

| 監視項目 | ツール | 閾値 |
|---------|--------|------|
| API応答時間 | Cloud Run Metrics（Cloud Logging） | P95 > 500ms で警告 |
| エラー率 | Cloud Run Metrics + Sentry（Free） | 5xx > 1% で警告 |
| コンテナ起動時間 | Cloud Run Metrics | コールドスタート > 3s で警告 |
| インスタンス数 | Cloud Run Metrics | max-instances の 80% 到達で警告 |
| Neon CU-hours 消費 | Neon Dashboard | 月80 CU-hours（Free枠80%）で警告 |
| Neon ストレージ | Neon Dashboard | 400MB（Free枠80%）で警告 |
| Neon コールドスタート頻度 | アプリログ（Cloud Logging） | 初回リクエスト > 2s が頻発で対策検討 |

---

## 付録A: pyproject.toml 設定

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

## 付録B: jest.config.js

```javascript
module.exports = {
  testMatch: ['**/*.test.js'],
  collectCoverageFrom: [
    'shared/utils/**/*.js',
    '!**/*.test.js',
  ],
  coverageThreshold: {
    'shared/utils/matcher.js': {
      branches: 90,
      functions: 95,
      lines: 95,
      statements: 95,
    },
  },
};
```