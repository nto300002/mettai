# Issue #009: ブラウザ拡張機能 - API通信モジュール実装

## 目的

Django APIと通信するためのモジュールを実装する。トークン認証、リトライロジック、エラーハンドリングを備え、拡張機能がバックエンドと連携できるようにする。

## 作成ファイル名

```
mettai-extension/
├── shared/
│   └── utils/
│       ├── api.js              # API通信モジュール
│       └── api.test.js         # Jestテスト
└── .env.example                # 環境変数サンプル
```

## ディレクトリ構成

```
mettai-extension/
├── shared/
│   └── utils/
│       ├── api.js           # fetch wrapper、トークン管理、リトライ
│       └── api.test.js      # モックを使ったテスト
└── .env.example             # API_BASE_URL
```

## 実装内容

### 1. mettai-extension/.env.example

```
# API Base URL
API_BASE_URL=http://localhost:8000
```

### 2. mettai-extension/shared/utils/api.js

```javascript
/**
 * API通信モジュール
 */

// Chrome/Firefox互換
self.browser = self.browser || self.chrome;

// API Base URL（開発環境 or 本番環境）
const API_BASE_URL = 'http://localhost:8000';  // TODO: 環境変数から読み込み

/**
 * トークン付きfetchラッパー
 */
async function authenticatedFetch(url, options = {}) {
    const token = await getToken();
    if (!token) {
        throw new Error('トークンが見つかりません。ログインしてください。');
    }

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Token ${token}`,
        ...options.headers
    };

    const response = await fetch(url, {
        ...options,
        headers
    });

    if (response.status === 401) {
        throw new Error('認証エラー。再度ログインしてください。');
    }

    return response;
}

/**
 * リトライ付きfetch
 */
async function fetchWithRetry(url, options = {}, maxRetries = 2) {
    for (let i = 0; i <= maxRetries; i++) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 8000); // 8秒タイムアウト

            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (response.ok) {
                return response;
            }

            // 5xxエラーでリトライ
            if (response.status >= 500 && i < maxRetries) {
                console.warn(`[API] ${response.status} error, retrying... (${i + 1}/${maxRetries})`);
                await sleep(2000 * (i + 1)); // 2秒、4秒と徐々に間隔を延ばす
                continue;
            }

            // それ以外はそのまま返す
            return response;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.warn('[API] Request timeout');
            }

            // 最終リトライでもエラーの場合は投げる
            if (i === maxRetries) {
                throw error;
            }

            console.warn(`[API] Retry ${i + 1}/${maxRetries}...`);
            await sleep(3000);
        }
    }
}

/**
 * ユーザー登録
 */
async function register(username, email, password) {
    const response = await fetchWithRetry(`${API_BASE_URL}/api/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username,
            email,
            password,
            password_confirm: password
        })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'ユーザー登録に失敗しました。');
    }

    const data = await response.json();
    await setToken(data.token);
    return data;
}

/**
 * ログイン
 */
async function login(email, password) {
    const response = await fetchWithRetry(`${API_BASE_URL}/api/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'ログインに失敗しました。');
    }

    const data = await response.json();
    await setToken(data.token);
    return data;
}

/**
 * ログアウト
 */
async function logout() {
    try {
        await authenticatedFetch(`${API_BASE_URL}/api/auth/logout/`, {
            method: 'POST'
        });
    } catch (error) {
        console.warn('[API] Logout failed:', error);
    } finally {
        await browser.storage.local.remove('token');
    }
}

/**
 * ルール設定を取得（同期API）
 */
async function fetchConfig() {
    const response = await authenticatedFetch(`${API_BASE_URL}/api/rules/sync/`);

    if (!response.ok) {
        throw new Error('ルール設定の取得に失敗しました。');
    }

    const data = await response.json();
    return data; // { mode, rules, updated_at }
}

/**
 * ルール一覧取得
 */
async function fetchRules() {
    const response = await authenticatedFetch(`${API_BASE_URL}/api/rules/`);

    if (!response.ok) {
        throw new Error('ルール一覧の取得に失敗しました。');
    }

    return response.json();
}

/**
 * ルール作成
 */
async function createRule(ruleData) {
    const response = await authenticatedFetch(`${API_BASE_URL}/api/rules/`, {
        method: 'POST',
        body: JSON.stringify(ruleData)
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'ルールの作成に失敗しました。');
    }

    return response.json();
}

/**
 * ルール更新
 */
async function updateRule(ruleId, ruleData) {
    const response = await authenticatedFetch(`${API_BASE_URL}/api/rules/${ruleId}/`, {
        method: 'PATCH',
        body: JSON.stringify(ruleData)
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'ルールの更新に失敗しました。');
    }

    return response.json();
}

/**
 * ルール削除
 */
async function deleteRule(ruleId) {
    const response = await authenticatedFetch(`${API_BASE_URL}/api/rules/${ruleId}/`, {
        method: 'DELETE'
    });

    if (!response.ok) {
        throw new Error('ルールの削除に失敗しました。');
    }
}

/**
 * ユーザー設定取得
 */
async function fetchUserSetting() {
    const response = await authenticatedFetch(`${API_BASE_URL}/api/rules/setting/`);

    if (!response.ok) {
        throw new Error('ユーザー設定の取得に失敗しました。');
    }

    return response.json();
}

/**
 * ユーザー設定更新
 */
async function updateUserSetting(mode) {
    const response = await authenticatedFetch(`${API_BASE_URL}/api/rules/setting/`, {
        method: 'PUT',
        body: JSON.stringify({ mode })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'ユーザー設定の更新に失敗しました。');
    }

    return response.json();
}

/**
 * Sleep ヘルパー
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Node.js環境（Jest）用のエクスポート
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        register,
        login,
        logout,
        fetchConfig,
        fetchRules,
        createRule,
        updateRule,
        deleteRule,
        fetchUserSetting,
        updateUserSetting,
    };
}
```

## テスト要件

### TDD サイクル

**Red → Green → Refactor を厳守**

### mettai-extension/shared/utils/api.test.js

```javascript
/**
 * API通信モジュールのテスト
 * fetchをモック化してテスト
 */

// グローバルfetchをモック
global.fetch = jest.fn();
global.browser = {
    storage: {
        local: {
            get: jest.fn(),
            set: jest.fn(),
            remove: jest.fn(),
        }
    }
};

const {
    register,
    login,
    logout,
    fetchConfig,
} = require('./api');

beforeEach(() => {
    fetch.mockClear();
    browser.storage.local.get.mockClear();
    browser.storage.local.set.mockClear();
    browser.storage.local.remove.mockClear();
});

describe('register', () => {
    test('正常なユーザー登録が成功する', async () => {
        fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                user: { id: 1, email: 'test@example.com' },
                token: 'test-token-123'
            })
        });

        browser.storage.local.set.mockResolvedValueOnce();

        const result = await register('testuser', 'test@example.com', 'SecurePass123!');

        expect(result.token).toBe('test-token-123');
        expect(browser.storage.local.set).toHaveBeenCalledWith({ token: 'test-token-123' });
    });

    test('登録失敗時にエラーを投げる', async () => {
        fetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ detail: 'Email already exists' })
        });

        await expect(register('testuser', 'test@example.com', 'pass123')).rejects.toThrow();
    });
});

describe('login', () => {
    test('正常なログインが成功する', async () => {
        fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                user: { id: 1, email: 'test@example.com' },
                token: 'test-token-123'
            })
        });

        browser.storage.local.set.mockResolvedValueOnce();

        const result = await login('test@example.com', 'SecurePass123!');

        expect(result.token).toBe('test-token-123');
        expect(browser.storage.local.set).toHaveBeenCalledWith({ token: 'test-token-123' });
    });

    test('ログイン失敗時にエラーを投げる', async () => {
        fetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ detail: 'Invalid credentials' })
        });

        await expect(login('test@example.com', 'wrong-pass')).rejects.toThrow();
    });
});

describe('logout', () => {
    test('ログアウトが成功する', async () => {
        browser.storage.local.get.mockResolvedValueOnce({ token: 'test-token-123' });
        fetch.mockResolvedValueOnce({ ok: true });
        browser.storage.local.remove.mockResolvedValueOnce();

        await logout();

        expect(browser.storage.local.remove).toHaveBeenCalledWith('token');
    });

    test('ログアウト失敗時でもトークンは削除される', async () => {
        browser.storage.local.get.mockResolvedValueOnce({ token: 'test-token-123' });
        fetch.mockRejectedValueOnce(new Error('Network error'));
        browser.storage.local.remove.mockResolvedValueOnce();

        await logout();

        expect(browser.storage.local.remove).toHaveBeenCalledWith('token');
    });
});

describe('fetchConfig', () => {
    test('ルール設定を取得できる', async () => {
        browser.storage.local.get.mockResolvedValueOnce({ token: 'test-token-123' });
        fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                mode: 'blacklist',
                rules: [{ pattern: 'youtube', match_type: 'keyword' }],
                updated_at: '2026-02-11T00:00:00Z'
            })
        });

        const result = await fetchConfig();

        expect(result.mode).toBe('blacklist');
        expect(result.rules).toHaveLength(1);
    });

    test('トークンがない場合にエラーを投げる', async () => {
        browser.storage.local.get.mockResolvedValueOnce({});

        await expect(fetchConfig()).rejects.toThrow('トークンが見つかりません');
    });

    test('401エラーの場合に認証エラーを投げる', async () => {
        browser.storage.local.get.mockResolvedValueOnce({ token: 'invalid-token' });
        fetch.mockResolvedValueOnce({
            ok: false,
            status: 401
        });

        await expect(fetchConfig()).rejects.toThrow('認証エラー');
    });
});
```

## テストコマンド

```bash
# テストを先に書く（Red）
npm test -- api.test.js

# 実装後にテスト実行（Green）
npm test -- api.test.js

# カバレッジ確認
npm run test:coverage
```

## 完了条件

- [ ] register API が動作する
- [ ] login API が動作する
- [ ] logout API が動作する
- [ ] fetchConfig API が動作する
- [ ] fetchRules API が動作する
- [ ] createRule API が動作する
- [ ] updateRule API が動作する
- [ ] deleteRule API が動作する
- [ ] トークン認証が正しく動作する
- [ ] リトライロジックが動作する（5xxエラー時）
- [ ] タイムアウト（8秒）が動作する
- [ ] 全テストが通る（カバレッジ 80% 以上）

## 備考

- **TDD厳守:** テストを先に書き、失敗を確認してから実装する
- fetch API をモック化してテスト
- `browser.storage.local` もモック化
- リトライロジック: 5xxエラー時に最大2回リトライ
- タイムアウト: 8秒（Cloud Run + Neon のダブルコールドスタート対応）
- トークンは `browser.storage.local` に保存
- Issue #006 の background.js で `syncRules()` を完成させる際にこのモジュールを使用
