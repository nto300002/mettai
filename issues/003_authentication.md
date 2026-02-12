# Issue #003: 認証機能実装

## 目的

ユーザー登録・ログイン機能を実装し、DRF TokenAuthentication によるAPI認証を実現する。拡張機能が `browser.storage.local` にトークンを保存し、以降のAPIリクエストで使用できるようにする。

## 作成ファイル名

```
apps/
└── accounts/
    ├── serializers.py           # ユーザー登録・ログイン用シリアライザ
    ├── views.py                 # 登録・ログインAPI
    ├── urls.py                  # /api/auth/ エンドポイント
    └── tests/
        ├── test_serializers.py  # シリアライザのテスト
        └── test_views.py        # APIエンドポイントのテスト

config/
└── urls.py                      # ルートURL設定（accounts.urls をインクルード）
```

## ディレクトリ構成

```
apps/accounts/
├── models.py              # User モデル（Issue #002 で実装済み）
├── serializers.py         # UserRegisterSerializer, UserLoginSerializer
├── views.py               # RegisterView, LoginView, LogoutView
├── urls.py                # /api/auth/register/, /api/auth/login/, /api/auth/logout/
└── tests/
    ├── test_serializers.py # バリデーションテスト
    └── test_views.py       # API統合テスト
```

## 実装内容

### 1. apps/accounts/serializers.py

```python
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from apps.accounts.models import User

class UserRegisterSerializer(serializers.ModelSerializer):
    """ユーザー登録用シリアライザ"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "パスワードが一致しません。"
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class UserLoginSerializer(serializers.Serializer):
    """ログイン用シリアライザ"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            # email でユーザーを検索
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    "メールアドレスまたはパスワードが正しくありません。"
                )

            # パスワード検証
            user = authenticate(username=user.username, password=password)
            if not user:
                raise serializers.ValidationError(
                    "メールアドレスまたはパスワードが正しくありません。"
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    "このアカウントは無効化されています。"
                )

            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                "メールアドレスとパスワードは必須です。"
            )
```

### 2. apps/accounts/views.py

```python
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from apps.accounts.serializers import UserRegisterSerializer, UserLoginSerializer

class RegisterView(APIView):
    """ユーザー登録API"""
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
                'token': token.key
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    """ログインAPI"""
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
                'token': token.key
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    """ログアウトAPI（トークン削除）"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response({'detail': 'ログアウトしました。'}, status=status.HTTP_200_OK)
```

### 3. apps/accounts/urls.py

```python
from django.urls import path
from apps.accounts.views import RegisterView, LoginView, LogoutView

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
```

### 4. config/urls.py

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
]
```

### 5. config/settings/base.py（追加設定）

```python
INSTALLED_APPS = [
    # ...
    'rest_framework',
    'rest_framework.authtoken',  # ← 追加
    'django_filters',
    'corsheaders',
    'apps.accounts',
    'apps.rules',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}
```

## テスト要件

### TDD サイクル

**Red → Green → Refactor を厳守**

### apps/accounts/tests/test_serializers.py

```python
import pytest
from apps.accounts.serializers import UserRegisterSerializer, UserLoginSerializer
from apps.accounts.models import User

@pytest.mark.django_db
class TestUserRegisterSerializer:
    def test_valid_registration(self):
        """正常なユーザー登録が成功すること"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        serializer = UserRegisterSerializer(data=data)
        assert serializer.is_valid()
        user = serializer.save()
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.check_password('SecurePass123!')

    def test_password_mismatch(self):
        """パスワードが一致しない場合にエラーとなること"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'DifferentPass123!'
        }
        serializer = UserRegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'password' in serializer.errors

    def test_weak_password_rejected(self):
        """脆弱なパスワードが拒否されること"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': '12345678',  # 数字のみ
            'password_confirm': '12345678'
        }
        serializer = UserRegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'password' in serializer.errors

    def test_duplicate_email_rejected(self):
        """重複メールアドレスが拒否されること"""
        User.objects.create_user(
            username='user1',
            email='test@example.com',
            password='pass123'
        )
        data = {
            'username': 'user2',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        serializer = UserRegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'email' in serializer.errors

@pytest.mark.django_db
class TestUserLoginSerializer:
    def test_valid_login(self):
        """正常なログインが成功すること"""
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        data = {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }
        serializer = UserLoginSerializer(data=data)
        assert serializer.is_valid()
        assert 'user' in serializer.validated_data

    def test_wrong_password(self):
        """誤ったパスワードでログイン失敗すること"""
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        data = {
            'email': 'test@example.com',
            'password': 'WrongPassword!'
        }
        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()

    def test_nonexistent_email(self):
        """存在しないメールアドレスでログイン失敗すること"""
        data = {
            'email': 'nonexistent@example.com',
            'password': 'SecurePass123!'
        }
        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()
```

### apps/accounts/tests/test_views.py

```python
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User

@pytest.fixture
def api_client():
    return APIClient()

@pytest.mark.django_db
class TestRegisterView:
    def test_register_success(self, api_client):
        """ユーザー登録APIが正常に動作すること"""
        url = reverse('accounts:register')
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert 'token' in response.data
        assert 'user' in response.data
        assert response.data['user']['email'] == 'test@example.com'

    def test_register_duplicate_email(self, api_client):
        """重複メールアドレスで登録失敗すること"""
        User.objects.create_user(
            username='user1',
            email='test@example.com',
            password='pass123'
        )
        url = reverse('accounts:register')
        data = {
            'username': 'user2',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
class TestLoginView:
    def test_login_success(self, api_client):
        """ログインAPIが正常に動作すること"""
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        url = reverse('accounts:login')
        data = {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'token' in response.data
        assert 'user' in response.data

    def test_login_wrong_password(self, api_client):
        """誤ったパスワードでログイン失敗すること"""
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        url = reverse('accounts:login')
        data = {
            'email': 'test@example.com',
            'password': 'WrongPassword!'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
class TestLogoutView:
    def test_logout_success(self, api_client):
        """ログアウトAPIが正常に動作すること"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        api_client.force_authenticate(user=user)
        url = reverse('accounts:logout')
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK

    def test_logout_without_authentication(self, api_client):
        """未認証でログアウトするとエラーになること"""
        url = reverse('accounts:logout')
        response = api_client.post(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

## テストコマンド

```bash
# テストを先に書く（Red）
pytest apps/accounts/tests/test_serializers.py -v
pytest apps/accounts/tests/test_views.py -v

# マイグレーション（authtoken アプリ）
python manage.py migrate

# 実装後にテスト実行（Green）
pytest apps/accounts/tests/ -v

# カバレッジ確認
pytest --cov=apps.accounts --cov-report=term-missing
```

## 完了条件

- [ ] ユーザー登録APIが動作し、トークンが発行される
- [ ] ログインAPIが動作し、トークンが発行される
- [ ] ログアウトAPIが動作し、トークンが削除される
- [ ] 全テストが通る（カバレッジ 85% 以上）
- [ ] ruff check でエラーなし
- [ ] パスワードバリデーションが正しく動作する（8文字以上、Django標準バリデータ）

## 備考

- **TDD厳守:** テストを先に書き、失敗を確認してから実装する
- トークン認証は DRF の `rest_framework.authtoken` を使用
- ログインは email ベースで行う（username ではない）
- セキュリティ: パスワードは平文保存しない（Django の `set_password` を使用）
