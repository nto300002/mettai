# Issue #004: URLルール管理API実装

## 目的

URLルールのCRUD操作を行うREST APIを実装する。拡張機能がルールを管理し、定期的に同期できるようにする。

## 作成ファイル名

```
apps/rules/
├── serializers.py            # URLRuleSerializer, UserSettingSerializer
├── views.py                  # URLRuleViewSet, UserSettingView, RuleSyncView
├── urls.py                   # /api/rules/ エンドポイント
├── services.py               # RuleSyncService（ビジネスロジック層）
└── tests/
    ├── test_serializers.py   # シリアライザのテスト
    ├── test_views.py         # APIエンドポイントのテスト
    └── test_services.py      # サービス層のテスト

config/
└── urls.py                   # rules.urls をインクルード
```

## ディレクトリ構成

```
apps/rules/
├── models.py               # UserSetting, URLRule（Issue #002 で実装済み）
├── serializers.py          # バリデーション・整形層
├── views.py                # プレゼンテーション層
├── services.py             # ビジネスロジック層
├── urls.py                 # ルーティング
└── tests/
    ├── test_serializers.py # バリデーションテスト
    ├── test_views.py       # API統合テスト
    └── test_services.py    # ビジネスロジックテスト
```

## 実装内容

### 1. apps/rules/serializers.py

```python
import re
from rest_framework import serializers
from apps.rules.models import URLRule, UserSetting

class URLRuleSerializer(serializers.ModelSerializer):
    """URLルール用シリアライザ"""
    class Meta:
        model = URLRule
        fields = ['id', 'list_type', 'match_type', 'pattern', 'label', 'is_active']
        read_only_fields = ['id']

    def validate_pattern(self, value):
        """パターンのバリデーション"""
        if not value or not value.strip():
            raise serializers.ValidationError("パターンは空にできません。")

        if len(value) > 500:
            raise serializers.ValidationError("パターンは500文字以内にしてください。")

        # 正規表現の場合はコンパイルテスト
        match_type = self.initial_data.get('match_type', 'keyword')
        if match_type == 'regex':
            try:
                re.compile(value)
            except re.error as e:
                raise serializers.ValidationError(f"無効な正規表現です: {e}")

            # ReDoS 対策: パターンの長さ制限
            if len(value) > 200:
                raise serializers.ValidationError(
                    "正規表現は200文字以内にしてください"
                )

        return value

    def validate(self, attrs):
        """重複チェック"""
        user = self.context['request'].user
        list_type = attrs.get('list_type')
        pattern = attrs.get('pattern')

        # 更新時は自身を除外
        queryset = URLRule.objects.filter(
            user=user,
            list_type=list_type,
            pattern=pattern
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError({
                'pattern': 'このパターンは既に登録されています。'
            })

        return attrs

class UserSettingSerializer(serializers.ModelSerializer):
    """ユーザー設定用シリアライザ"""
    class Meta:
        model = UserSetting
        fields = ['mode']
```

### 2. apps/rules/services.py

```python
from apps.rules.models import URLRule, UserSetting

class RuleSyncService:
    """拡張機能用の同期データを構築するサービス"""

    @staticmethod
    def get_sync_data(user):
        """ユーザーの設定とアクティブなルールを取得"""
        setting, _ = UserSetting.objects.get_or_create(user=user)

        rules = URLRule.objects.filter(
            user=user,
            is_active=True
        ).values('pattern', 'match_type')

        # 最終更新日時を取得
        latest_rule = URLRule.objects.filter(
            user=user
        ).order_by('-updated_at').first()

        return {
            'mode': setting.mode,
            'rules': list(rules),
            'updated_at': latest_rule.updated_at if latest_rule else None,
        }
```

### 3. apps/rules/views.py

```python
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.rules.models import URLRule, UserSetting
from apps.rules.serializers import URLRuleSerializer, UserSettingSerializer
from apps.rules.services import RuleSyncService

class URLRuleViewSet(viewsets.ModelViewSet):
    """URLルールのCRUD操作"""
    serializer_class = URLRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """自分のルールのみ取得"""
        return URLRule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """作成時にユーザーを自動設定"""
        serializer.save(user=self.request.user)

class UserSettingView(APIView):
    """ユーザー設定の取得・更新"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """設定を取得"""
        setting, _ = UserSetting.objects.get_or_create(user=request.user)
        serializer = UserSettingSerializer(setting)
        return Response(serializer.data)

    def put(self, request):
        """設定を更新"""
        setting, _ = UserSetting.objects.get_or_create(user=request.user)
        serializer = UserSettingSerializer(setting, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RuleSyncView(APIView):
    """拡張機能用の同期API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """ユーザーの設定とアクティブなルールを返す"""
        data = RuleSyncService.get_sync_data(request.user)
        return Response(data)
```

### 4. apps/rules/urls.py

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.rules.views import URLRuleViewSet, UserSettingView, RuleSyncView

router = DefaultRouter()
router.register(r'', URLRuleViewSet, basename='urlrule')

app_name = 'rules'

urlpatterns = [
    path('sync/', RuleSyncView.as_view(), name='sync'),
    path('setting/', UserSettingView.as_view(), name='setting'),
    path('', include(router.urls)),
]
```

### 5. config/urls.py（追加）

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/rules/', include('apps.rules.urls')),  # ← 追加
]
```

## テスト要件

### TDD サイクル

**Red → Green → Refactor を厳守**

### apps/rules/tests/test_serializers.py

```python
import pytest
from apps.rules.serializers import URLRuleSerializer, UserSettingSerializer
from apps.rules.tests.factories import UserFactory, URLRuleFactory

@pytest.mark.django_db
class TestURLRuleSerializer:
    def test_valid_keyword_rule(self):
        """キーワードルールが正常に作成されること"""
        user = UserFactory()
        data = {
            'list_type': 'blacklist',
            'match_type': 'keyword',
            'pattern': 'youtube',
            'label': 'YouTube'
        }
        serializer = URLRuleSerializer(data=data, context={'request': type('Request', (), {'user': user})()})
        assert serializer.is_valid()

    def test_empty_pattern_rejected(self):
        """空のパターンが拒否されること"""
        user = UserFactory()
        data = {
            'list_type': 'blacklist',
            'match_type': 'keyword',
            'pattern': '',
            'label': 'Empty'
        }
        serializer = URLRuleSerializer(data=data, context={'request': type('Request', (), {'user': user})()})
        assert not serializer.is_valid()
        assert 'pattern' in serializer.errors

    def test_invalid_regex_rejected(self):
        """不正な正規表現が拒否されること"""
        user = UserFactory()
        data = {
            'list_type': 'blacklist',
            'match_type': 'regex',
            'pattern': '[invalid(regex',
            'label': 'Invalid Regex'
        }
        serializer = URLRuleSerializer(data=data, context={'request': type('Request', (), {'user': user})()})
        assert not serializer.is_valid()
        assert 'pattern' in serializer.errors

    def test_regex_length_limit(self):
        """正規表現が200文字制限を超えると拒否されること"""
        user = UserFactory()
        data = {
            'list_type': 'blacklist',
            'match_type': 'regex',
            'pattern': 'a' * 201,
            'label': 'Too Long'
        }
        serializer = URLRuleSerializer(data=data, context={'request': type('Request', (), {'user': user})()})
        assert not serializer.is_valid()
        assert 'pattern' in serializer.errors

    def test_duplicate_pattern_rejected(self):
        """同一パターンの重複が拒否されること"""
        user = UserFactory()
        URLRuleFactory(user=user, list_type='blacklist', pattern='youtube')

        data = {
            'list_type': 'blacklist',
            'match_type': 'keyword',
            'pattern': 'youtube',
            'label': 'Duplicate'
        }
        serializer = URLRuleSerializer(data=data, context={'request': type('Request', (), {'user': user})()})
        assert not serializer.is_valid()
        assert 'pattern' in serializer.errors

@pytest.mark.django_db
class TestUserSettingSerializer:
    def test_valid_mode_change(self):
        """モード変更が正常に動作すること"""
        data = {'mode': 'whitelist'}
        serializer = UserSettingSerializer(data=data)
        assert serializer.is_valid()

    def test_invalid_mode_rejected(self):
        """不正なモードが拒否されること"""
        data = {'mode': 'invalid_mode'}
        serializer = UserSettingSerializer(data=data)
        assert not serializer.is_valid()
```

### apps/rules/tests/test_views.py

```python
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.rules.tests.factories import UserFactory, URLRuleFactory, UserSettingFactory

@pytest.fixture
def auth_client():
    client = APIClient()
    user = UserFactory()
    client.force_authenticate(user=user)
    client.user = user
    return client

@pytest.mark.django_db
class TestURLRuleViewSet:
    def test_list_rules(self, auth_client):
        """ルール一覧取得が動作すること"""
        URLRuleFactory.create_batch(3, user=auth_client.user)
        url = reverse('rules:urlrule-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

    def test_create_rule(self, auth_client):
        """ルール作成が動作すること"""
        url = reverse('rules:urlrule-list')
        data = {
            'list_type': 'blacklist',
            'match_type': 'keyword',
            'pattern': 'youtube',
            'label': 'YouTube'
        }
        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['pattern'] == 'youtube'

    def test_update_rule(self, auth_client):
        """ルール更新が動作すること"""
        rule = URLRuleFactory(user=auth_client.user, pattern='youtube')
        url = reverse('rules:urlrule-detail', args=[rule.id])
        data = {'pattern': 'twitter', 'list_type': 'blacklist'}
        response = auth_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['pattern'] == 'twitter'

    def test_delete_rule(self, auth_client):
        """ルール削除が動作すること"""
        rule = URLRuleFactory(user=auth_client.user)
        url = reverse('rules:urlrule-detail', args=[rule.id])
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_user_isolation(self, auth_client):
        """他ユーザーのルールが取得できないこと"""
        other_user = UserFactory()
        URLRuleFactory(user=other_user, pattern='secret')
        url = reverse('rules:urlrule-list')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

@pytest.mark.django_db
class TestUserSettingView:
    def test_get_setting(self, auth_client):
        """設定取得が動作すること"""
        url = reverse('rules:setting')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'mode' in response.data

    def test_update_setting(self, auth_client):
        """設定更新が動作すること"""
        url = reverse('rules:setting')
        data = {'mode': 'whitelist'}
        response = auth_client.put(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['mode'] == 'whitelist'

@pytest.mark.django_db
class TestRuleSyncView:
    def test_sync_returns_active_rules_only(self, auth_client):
        """アクティブなルールのみ返すこと"""
        URLRuleFactory(user=auth_client.user, pattern='youtube', is_active=True)
        URLRuleFactory(user=auth_client.user, pattern='twitter', is_active=False)
        url = reverse('rules:sync')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['rules']) == 1
        assert response.data['rules'][0]['pattern'] == 'youtube'

    def test_sync_includes_mode(self, auth_client):
        """モード情報が含まれること"""
        UserSettingFactory(user=auth_client.user, mode='whitelist')
        url = reverse('rules:sync')
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['mode'] == 'whitelist'
```

### apps/rules/tests/test_services.py

```python
import pytest
from apps.rules.services import RuleSyncService
from apps.rules.tests.factories import UserFactory, URLRuleFactory, UserSettingFactory

@pytest.mark.django_db
class TestRuleSyncService:
    def test_get_sync_data_creates_default_setting(self):
        """設定が存在しない場合にデフォルト作成されること"""
        user = UserFactory()
        data = RuleSyncService.get_sync_data(user)
        assert data['mode'] == 'blacklist'

    def test_get_sync_data_filters_active_rules(self):
        """アクティブなルールのみ取得されること"""
        user = UserFactory()
        URLRuleFactory(user=user, pattern='youtube', is_active=True)
        URLRuleFactory(user=user, pattern='twitter', is_active=False)
        data = RuleSyncService.get_sync_data(user)
        assert len(data['rules']) == 1
        assert data['rules'][0]['pattern'] == 'youtube'

    def test_get_sync_data_includes_updated_at(self):
        """最終更新日時が含まれること"""
        user = UserFactory()
        rule = URLRuleFactory(user=user)
        data = RuleSyncService.get_sync_data(user)
        assert data['updated_at'] == rule.updated_at
```

## テストコマンド

```bash
# テストを先に書く（Red）
pytest apps/rules/tests/test_serializers.py -v
pytest apps/rules/tests/test_views.py -v
pytest apps/rules/tests/test_services.py -v

# 実装後にテスト実行（Green）
pytest apps/rules/tests/ -v

# カバレッジ確認
pytest --cov=apps.rules --cov-report=term-missing
```

## 完了条件

- [ ] ルール一覧取得API（GET /api/rules/）が動作する
- [ ] ルール作成API（POST /api/rules/）が動作する
- [ ] ルール更新API（PATCH /api/rules/:id/）が動作する
- [ ] ルール削除API（DELETE /api/rules/:id/）が動作する
- [ ] 設定取得API（GET /api/rules/setting/）が動作する
- [ ] 設定更新API（PUT /api/rules/setting/）が動作する
- [ ] 同期API（GET /api/rules/sync/）が動作する
- [ ] 全テストが通る（カバレッジ 85% 以上）
- [ ] ruff check でエラーなし
- [ ] ユーザー分離が正しく機能する（他ユーザーのデータにアクセス不可）

## 備考

- **TDD厳守:** テストを先に書き、失敗を確認してから実装する
- レイヤー分離: views.py → serializers.py → services.py → models.py
- 権限制御: 全API で `request.user` によるフィルタ必須（IDOR脆弱性対策）
- ReDoS対策: 正規表現は200文字以内に制限
