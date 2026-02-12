# Issue #006: ブラウザ拡張機能 - background.js 実装

## 目的

ブラウザ拡張機能のバックグラウンドスクリプトを実装し、タブ監視・URL判定・オーバーレイ表示トリガーを実現する。Service Worker（Manifest V3）対応とする。

## 作成ファイル名

```
mettai-extension/
├── manifest.chrome.json        # Chrome用マニフェスト
├── manifest.firefox.json       # Firefox用マニフェスト
├── shared/
│   ├── background.js           # バックグラウンドスクリプト
│   └── utils/
│       ├── storage.js          # ストレージ管理モジュール
│       ├── api.js              # API通信モジュール（後続Issue）
│       └── matcher.js          # マッチングエンジン（Issue #005で実装済み）
├── vendor/
│   └── browser-polyfill.min.js # WebExtensions Polyfill
└── build.sh                    # ビルドスクリプト
```

## ディレクトリ構成

```
mettai-extension/
├── manifest.chrome.json     # Manifest V3（Service Worker）
├── manifest.firefox.json    # Manifest V2互換
├── shared/
│   ├── background.js        # タブ監視、URL判定、オーバーレイトリガー
│   └── utils/
│       ├── storage.js       # browser.storage.local ラッパー
│       ├── api.js           # API通信（次のIssue）
│       └── matcher.js       # Issue #005で実装済み
├── vendor/
│   └── browser-polyfill.min.js  # Chrome/Firefox互換性
└── build.sh                 # manifest切替ビルド
```

## 実装内容

### 1. mettai-extension/manifest.chrome.json

```json
{
  "manifest_version": 3,
  "name": "滅諦（Mettai）",
  "version": "1.0.0",
  "description": "ADHD当事者のための気づきベース集中支援ツール",
  "permissions": [
    "tabs",
    "storage",
    "activeTab"
  ],
  "host_permissions": [
    "<all_urls>"
  ],
  "background": {
    "service_worker": "shared/background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["vendor/browser-polyfill.min.js", "shared/content/overlay.js"],
      "css": ["shared/styles/overlay.css"]
    }
  ],
  "action": {
    "default_popup": "shared/popup/popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

### 2. mettai-extension/manifest.firefox.json

```json
{
  "manifest_version": 2,
  "name": "滅諦（Mettai）",
  "version": "1.0.0",
  "description": "ADHD当事者のための気づきベース集中支援ツール",
  "permissions": [
    "tabs",
    "storage",
    "<all_urls>"
  ],
  "background": {
    "scripts": [
      "vendor/browser-polyfill.min.js",
      "shared/utils/matcher.js",
      "shared/utils/storage.js",
      "shared/utils/api.js",
      "shared/background.js"
    ]
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["vendor/browser-polyfill.min.js", "shared/content/overlay.js"],
      "css": ["shared/styles/overlay.css"]
    }
  ],
  "browser_action": {
    "default_popup": "shared/popup/popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

### 3. mettai-extension/shared/utils/storage.js

```javascript
/**
 * ストレージ管理モジュール
 */

const CACHE_TTL_MS = 5 * 60 * 1000; // 5分

/**
 * ルール設定をキャッシュから取得（有効期限付き）
 */
async function getCachedConfig() {
    const cached = await browser.storage.local.get('ruleConfig');
    if (cached.ruleConfig) {
        const age = Date.now() - cached.ruleConfig.fetchedAt;
        if (age < CACHE_TTL_MS) {
            console.log('[Storage] Cache hit');
            return cached.ruleConfig.data;
        }
    }
    console.log('[Storage] Cache miss');
    return null;
}

/**
 * ルール設定をキャッシュに保存
 */
async function setCachedConfig(data) {
    await browser.storage.local.set({
        ruleConfig: {
            data,
            fetchedAt: Date.now()
        }
    });
    console.log('[Storage] Config cached');
}

/**
 * トークンを取得
 */
async function getToken() {
    const result = await browser.storage.local.get('token');
    return result.token || null;
}

/**
 * トークンを保存
 */
async function setToken(token) {
    await browser.storage.local.set({ token });
}

/**
 * 集中モードの状態を取得
 */
async function getFocusMode() {
    const result = await browser.storage.local.get('focusMode');
    return result.focusMode !== undefined ? result.focusMode : true;
}

/**
 * 集中モードの状態を保存
 */
async function setFocusMode(enabled) {
    await browser.storage.local.set({ focusMode: enabled });
}

/**
 * 一時許可リストを取得
 */
async function getTemporaryAllowList() {
    const result = await browser.storage.local.get('temporaryAllowList');
    return result.temporaryAllowList || [];
}

/**
 * 一時許可を追加（5分間有効）
 */
async function addTemporaryAllow(url) {
    const list = await getTemporaryAllowList();
    list.push({
        url,
        expiresAt: Date.now() + 5 * 60 * 1000 // 5分後
    });
    await browser.storage.local.set({ temporaryAllowList: list });
}

/**
 * 期限切れの一時許可を削除
 */
async function cleanupTemporaryAllowList() {
    const list = await getTemporaryAllowList();
    const now = Date.now();
    const active = list.filter(item => item.expiresAt > now);
    await browser.storage.local.set({ temporaryAllowList: active });
}

// Node.js環境（Jest）用のエクスポート
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getCachedConfig,
        setCachedConfig,
        getToken,
        setToken,
        getFocusMode,
        setFocusMode,
        getTemporaryAllowList,
        addTemporaryAllow,
        cleanupTemporaryAllowList,
    };
}
```

### 4. mettai-extension/shared/background.js

```javascript
/**
 * バックグラウンドスクリプト
 * タブ監視、URL判定、オーバーレイ表示トリガー
 */

// Chrome/Firefox互換
self.browser = self.browser || self.chrome;

// 5分間隔でルール同期
const SYNC_INTERVAL_MS = 5 * 60 * 1000;

// 初期化
browser.runtime.onInstalled.addListener(() => {
    console.log('[Background] Extension installed');
    initializeExtension();
});

// 拡張起動時
browser.runtime.onStartup.addListener(() => {
    console.log('[Background] Extension startup');
    initializeExtension();
});

/**
 * 初期化処理
 */
async function initializeExtension() {
    // 集中モードのデフォルト値を設定
    const focusMode = await getFocusMode();
    if (focusMode === null) {
        await setFocusMode(true);
    }

    // 定期的にルールを同期
    setInterval(async () => {
        await syncRules();
    }, SYNC_INTERVAL_MS);

    // 初回同期
    await syncRules();

    // 期限切れ一時許可のクリーンアップ
    setInterval(async () => {
        await cleanupTemporaryAllowList();
    }, 60 * 1000); // 1分ごと
}

/**
 * ルール同期（APIから取得してキャッシュ）
 */
async function syncRules() {
    const token = await getToken();
    if (!token) {
        console.log('[Background] No token, skip sync');
        return;
    }

    try {
        // 注: fetchConfig は api.js で実装（次のIssue）
        // const data = await fetchConfig();
        // await setCachedConfig(data);
        console.log('[Background] Rules synced');
    } catch (error) {
        console.error('[Background] Sync failed:', error);
    }
}

/**
 * タブ更新時のハンドラ
 */
browser.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    // URLが変更され、読み込みが完了したときのみ処理
    if (changeInfo.status === 'complete' && tab.url) {
        await checkUrl(tabId, tab.url);
    }
});

/**
 * タブアクティブ化時のハンドラ
 */
browser.tabs.onActivated.addListener(async (activeInfo) => {
    const tab = await browser.tabs.get(activeInfo.tabId);
    if (tab.url) {
        await checkUrl(activeInfo.tabId, tab.url);
    }
});

/**
 * URLをチェックしてブロック判定
 */
async function checkUrl(tabId, url) {
    // 集中モードがOFFの場合はスキップ
    const focusMode = await getFocusMode();
    if (!focusMode) {
        return;
    }

    // 拡張機能の内部ページはスキップ
    if (url.startsWith('chrome://') || url.startsWith('about:') || url.startsWith('moz-extension://')) {
        return;
    }

    // 一時許可リストをチェック
    const allowList = await getTemporaryAllowList();
    const isTemporarilyAllowed = allowList.some(item =>
        item.url === url && item.expiresAt > Date.now()
    );
    if (isTemporarilyAllowed) {
        console.log('[Background] Temporarily allowed:', url);
        return;
    }

    // キャッシュからルール設定を取得
    const config = await getCachedConfig();
    if (!config) {
        console.log('[Background] No config, skip check');
        return;
    }

    // URL判定（matcher.js を使用）
    const blocked = shouldBlock(url, config.rules, config.mode);
    if (blocked) {
        console.log('[Background] Blocked:', url);
        // オーバーレイを表示（content scriptにメッセージ送信）
        browser.tabs.sendMessage(tabId, {
            action: 'showOverlay',
            url: url
        });
    }
}

/**
 * Content scriptからのメッセージハンドラ
 */
browser.runtime.onMessage.addListener(async (message, sender) => {
    if (message.action === 'allowTemporarily') {
        // 5分間の一時許可を追加
        await addTemporaryAllow(message.url);
        console.log('[Background] Temporarily allowed:', message.url);
        return { success: true };
    }

    if (message.action === 'goBack') {
        // 前のタブに戻る
        if (sender.tab) {
            // TODO: 前のタブIDを保存・復元する実装
            console.log('[Background] Go back requested');
        }
        return { success: true };
    }
});
```

### 5. mettai-extension/build.sh

```bash
#!/bin/bash

# Chrome用ビルド
mkdir -p dist/chrome
cp manifest.chrome.json dist/chrome/manifest.json
cp -r shared vendor icons dist/chrome/

# Firefox用ビルド
mkdir -p dist/firefox
cp manifest.firefox.json dist/firefox/manifest.json
cp -r shared vendor icons dist/firefox/

echo "Build completed!"
```

## テスト要件

### テスト観点

background.js はブラウザAPI依存が強いため、**手動テストを中心とする**。自動テストは storage.js のみ実施。

### shared/utils/storage.test.js（追加実装）

```javascript
// モックを使った storage.js のユニットテスト
// browser.storage.local をモック化

describe('storage module', () => {
    beforeEach(() => {
        // browser.storage.local のモック
        global.browser = {
            storage: {
                local: {
                    get: jest.fn(),
                    set: jest.fn(),
                }
            }
        };
    });

    test('getCachedConfig returns cached data if not expired', async () => {
        const mockData = { mode: 'blacklist', rules: [] };
        global.browser.storage.local.get.mockResolvedValue({
            ruleConfig: {
                data: mockData,
                fetchedAt: Date.now() - 1000 // 1秒前
            }
        });

        const result = await getCachedConfig();
        expect(result).toEqual(mockData);
    });

    test('getCachedConfig returns null if expired', async () => {
        global.browser.storage.local.get.mockResolvedValue({
            ruleConfig: {
                data: { mode: 'blacklist', rules: [] },
                fetchedAt: Date.now() - 10 * 60 * 1000 // 10分前
            }
        });

        const result = await getCachedConfig();
        expect(result).toBeNull();
    });

    // ... その他のストレージ関数のテスト
});
```

### 手動テスト項目

```
[ ] Chrome拡張として読み込める
[ ] Firefox拡張として読み込める
[ ] 拡張機能インストール時に初期化される
[ ] 集中モードON時にブロック対象URLでオーバーレイが表示される
[ ] 集中モードOFF時にブロック判定がスキップされる
[ ] 5分間隔でルール同期が実行される（ログ確認）
[ ] 一時許可が5分間有効になる
[ ] 期限切れの一時許可が自動削除される
[ ] chrome://, about:, moz-extension:// URLがスキップされる
```

## テストコマンド

```bash
# storage.js のテスト
npm test -- storage.test.js

# 拡張機能をビルド
cd mettai-extension
chmod +x build.sh
./build.sh

# Chrome で手動テスト
# chrome://extensions/ から dist/chrome を読み込み

# Firefox で手動テスト
# about:debugging から dist/firefox を読み込み
```

## 完了条件

- [ ] manifest.chrome.json が正しく動作する
- [ ] manifest.firefox.json が正しく動作する
- [ ] background.js がタブ更新・アクティブ化を監視する
- [ ] ブロック対象URLでオーバーレイ表示がトリガーされる
- [ ] 集中モードON/OFF切替が動作する
- [ ] 一時許可（5分間）が動作する
- [ ] storage.js のテストが通る
- [ ] Chrome/Firefoxで手動テストが全て通る

## 備考

- Manifest V3（Chrome）とV2（Firefox）の両対応
- Service Worker（Chrome）と background scripts（Firefox）の両対応
- browser-polyfill.min.js で Chrome/Firefox API統一
- 自動テストは storage.js のみ、background.js は手動テスト中心
- Issue #007 で api.js を実装後、syncRules() を完成させる
