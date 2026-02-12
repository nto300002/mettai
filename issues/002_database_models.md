# Issue #002: データベースモデル実装

## 目的

MVPに必要な3つのモデル（User, UserSetting, URLRule）を実装し、データベーススキーマを構築する。TDDサイクルに従い、テストファーストで実装する。

## 作成ファイル名

```
apps/
├── accounts/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py              # User モデル
│   ├── admin.py
│   └── tests/
│       ├── __init__.py
│       └── test_models.py     # User モデルのテスト
│
└── rules/
    ├── __init__.py
    ├── apps.py
    ├── models.py              # UserSetting, URLRule モデル
    ├── admin.py
    └── tests/
        ├── __init__.py
        ├── test_models.py     # モデルのテスト
        └── factories.py       # factory-boy テストデータ
```

## ディレクトリ構成

```
apps/
├── accounts/               # 認証・ユーザー管理アプリ
│   ├── models.py          # User（AbstractUser 継承）
│   └── tests/
│       └── test_models.py # User モデルのユニットテスト
│
└── rules/                  # URLルール管理アプリ
    ├── models.py          # UserSetting, URLRule
    └── tests/
        ├── test_models.py # UserSetting/URLRule のユニットテスト
        └── factories.py   # テストデータファクトリ
```

## 実装内容

### 1. apps/accounts/models.py

```python
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    カスタムユーザーモデル
    MVP段階では AbstractUser をそのまま継承し、カスタムフィールドは追加しない
    """
    class Meta:
        db_table = 'accounts_user'
        indexes = [
            models.Index(fields=['email'], name='idx_user_email'),
        ]
```

### 2. apps/rules/models.py

```python
from django.conf import settings
from django.db import models

class UserSetting(models.Model):
    """ユーザーごとの設定"""
    MODE_CHOICES = [
        ('blacklist', 'Blacklist'),
        ('whitelist', 'Whitelist'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='setting'
    )
    mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        default='blacklist'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rules_usersetting'

class URLRule(models.Model):
    """URLルール"""
    LIST_TYPE_CHOICES = [
        ('whitelist', 'Whitelist'),
        ('blacklist', 'Blacklist'),
    ]
    MATCH_TYPE_CHOICES = [
        ('keyword', 'Keyword'),
        ('domain', 'Domain'),
        ('regex', 'Regex'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='urlrules'
    )
    list_type = models.CharField(max_length=10, choices=LIST_TYPE_CHOICES)
    match_type = models.CharField(
        max_length=10,
        choices=MATCH_TYPE_CHOICES,
        default='keyword'
    )
    pattern = models.CharField(max_length=500)
    label = models.CharField(max_length=100, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rules_urlrule'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'list_type', 'pattern'],
                name='uq_user_list_pattern'
            )
        ]
        indexes = [
            models.Index(
                fields=['user', 'is_active'],
                name='idx_urlrule_user_active'
            ),
            models.Index(
                fields=['user', 'list_type'],
                name='idx_urlrule_user_listtype'
            ),
        ]
```

### 3. apps/rules/tests/factories.py

```python
import factory
from factory.django import DjangoModelFactory
from apps.accounts.models import User
from apps.rules.models import UserSetting, URLRule

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')

class UserSettingFactory(DjangoModelFactory):
    class Meta:
        model = UserSetting

    user = factory.SubFactory(UserFactory)
    mode = 'blacklist'

class URLRuleFactory(DjangoModelFactory):
    class Meta:
        model = URLRule

    user = factory.SubFactory(UserFactory)
    list_type = 'blacklist'
    match_type = 'keyword'
    pattern = 'youtube'
    label = 'YouTube'
    is_active = True
```

## テスト要件

### TDD サイクル

**必ず Red → Green → Refactor の順で実装すること**

### apps/accounts/tests/test_models.py

```python
import pytest
from django.db import IntegrityError
from apps.accounts.models import User

@pytest.mark.django_db
class TestUserModel:
    def test_create_user_success(self):
        """ユーザー作成が正常に完了すること"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.check_password('testpass123')

    def test_email_unique_constraint(self):
        """メールアドレスの重複が禁止されること"""
        User.objects.create_user(
            username='user1',
            email='test@example.com',
            password='pass123'
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username='user2',
                email='test@example.com',
                password='pass123'
            )

    def test_username_unique_constraint(self):
        """ユーザー名の重複が禁止されること"""
        User.objects.create_user(
            username='testuser',
            email='test1@example.com',
            password='pass123'
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username='testuser',
                email='test2@example.com',
                password='pass123'
            )
```

### apps/rules/tests/test_models.py

```python
import pytest
from django.db import IntegrityError
from apps.rules.tests.factories import UserFactory, UserSettingFactory, URLRuleFactory
from apps.rules.models import UserSetting, URLRule

@pytest.mark.django_db
class TestUserSettingModel:
    def test_create_user_setting(self):
        """UserSetting が正常に作成されること"""
        user = UserFactory()
        setting = UserSetting.objects.create(user=user, mode='blacklist')
        assert setting.user == user
        assert setting.mode == 'blacklist'

    def test_user_one_to_one_constraint(self):
        """1ユーザーに1設定のみ作成可能であること"""
        user = UserFactory()
        UserSetting.objects.create(user=user, mode='blacklist')
        with pytest.raises(IntegrityError):
            UserSetting.objects.create(user=user, mode='whitelist')

    def test_default_mode_is_blacklist(self):
        """デフォルトモードが blacklist であること"""
        user = UserFactory()
        setting = UserSetting.objects.create(user=user)
        assert setting.mode == 'blacklist'

    def test_cascade_delete(self):
        """ユーザー削除時に設定も削除されること"""
        user = UserFactory()
        setting = UserSetting.objects.create(user=user)
        user_id = user.id
        user.delete()
        assert not UserSetting.objects.filter(user_id=user_id).exists()

@pytest.mark.django_db
class TestURLRuleModel:
    def test_create_url_rule(self):
        """URLRule が正常に作成されること"""
        user = UserFactory()
        rule = URLRule.objects.create(
            user=user,
            list_type='blacklist',
            match_type='keyword',
            pattern='youtube',
            label='YouTube'
        )
        assert rule.user == user
        assert rule.pattern == 'youtube'
        assert rule.is_active is True

    def test_unique_constraint_user_listtype_pattern(self):
        """同一ユーザー・リストタイプ・パターンの重複が禁止されること"""
        user = UserFactory()
        URLRule.objects.create(
            user=user,
            list_type='blacklist',
            match_type='keyword',
            pattern='youtube'
        )
        with pytest.raises(IntegrityError):
            URLRule.objects.create(
                user=user,
                list_type='blacklist',
                match_type='keyword',
                pattern='youtube'
            )

    def test_different_users_can_have_same_pattern(self):
        """異なるユーザーは同じパターンを登録可能であること"""
        user1 = UserFactory()
        user2 = UserFactory()
        rule1 = URLRule.objects.create(
            user=user1,
            list_type='blacklist',
            match_type='keyword',
            pattern='youtube'
        )
        rule2 = URLRule.objects.create(
            user=user2,
            list_type='blacklist',
            match_type='keyword',
            pattern='youtube'
        )
        assert rule1.pattern == rule2.pattern
        assert rule1.user != rule2.user

    def test_cascade_delete_rules(self):
        """ユーザー削除時にルールも全て削除されること"""
        user = UserFactory()
        URLRule.objects.create(user=user, list_type='blacklist', pattern='youtube')
        URLRule.objects.create(user=user, list_type='blacklist', pattern='twitter')
        user_id = user.id
        user.delete()
        assert URLRule.objects.filter(user_id=user_id).count() == 0

    def test_default_is_active_true(self):
        """デフォルトで is_active が True であること"""
        rule = URLRuleFactory()
        assert rule.is_active is True

    def test_default_match_type_is_keyword(self):
        """デフォルトの match_type が keyword であること"""
        user = UserFactory()
        rule = URLRule.objects.create(
            user=user,
            list_type='blacklist',
            pattern='youtube'
        )
        assert rule.match_type == 'keyword'
```

## テストコマンド

```bash
# テスト実行（Red → モデル未実装なので失敗する）
pytest apps/accounts/tests/test_models.py -v
pytest apps/rules/tests/test_models.py -v

# カバレッジ付きテスト
pytest --cov=apps --cov-report=term-missing

# マイグレーション作成
python manage.py makemigrations

# マイグレーション適用
python manage.py migrate

# テスト実行（Green → 実装後に成功する）
pytest apps/accounts/tests/test_models.py -v
pytest apps/rules/tests/test_models.py -v
```

## 完了条件

- [ ] User モデルが実装され、全テストが通る
- [ ] UserSetting モデルが実装され、全テストが通る
- [ ] URLRule モデルが実装され、全テストが通る
- [ ] マイグレーションファイルが生成される
- [ ] テストカバレッジが 90% 以上
- [ ] ruff check でエラーなし

## 備考

- **TDD厳守:** テストを先に書き、失敗を確認してから実装する
- factory-boy を使ってテストデータ生成を効率化
- カスケード削除のテストは重要（データ整合性の保証）
