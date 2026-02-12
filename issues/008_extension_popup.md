# Issue #008: ブラウザ拡張機能 - ポップアップUI実装

## 目的

拡張機能のポップアップUIを実装し、集中モードのON/OFF切替と簡易設定を提供する。ユーザーがワンクリックで集中モードを制御できるようにする。

## 作成ファイル名

```
mettai-extension/
└── shared/
    └── popup/
        ├── popup.html          # ポップアップHTML
        ├── popup.js            # ポップアップロジック
        └── popup.css           # ポップアップスタイル
```

## ディレクトリ構成

```
mettai-extension/
└── shared/
    └── popup/
        ├── popup.html       # UI構造
        ├── popup.js         # 集中モードON/OFF、設定変更
        └── popup.css        # デザイン
```

## 実装内容

### 1. mettai-extension/shared/popup/popup.html

```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>滅諦（Mettai）</title>
    <link rel="stylesheet" href="popup.css">
</head>
<body>
    <div class="popup-container">
        <!-- ヘッダー -->
        <header class="popup-header">
            <h1 class="popup-title">滅諦（Mettai）</h1>
            <p class="popup-subtitle">気づきベース集中支援</p>
        </header>

        <!-- 集中モード切替 -->
        <section class="popup-section">
            <div class="focus-mode-toggle">
                <div class="toggle-info">
                    <h2 class="toggle-label">集中モード</h2>
                    <p class="toggle-description" id="focus-status">
                        オフ
                    </p>
                </div>
                <label class="switch">
                    <input type="checkbox" id="focus-mode-switch">
                    <span class="slider"></span>
                </label>
            </div>
        </section>

        <!-- ステータス表示 -->
        <section class="popup-section">
            <div class="status-info">
                <div class="status-item">
                    <span class="status-label">モード:</span>
                    <span class="status-value" id="current-mode">--</span>
                </div>
                <div class="status-item">
                    <span class="status-label">アクティブルール:</span>
                    <span class="status-value" id="rule-count">--</span>
                </div>
            </div>
        </section>

        <!-- アクションボタン -->
        <section class="popup-section">
            <button class="btn btn-primary" id="open-settings">
                設定を開く
            </button>
            <button class="btn btn-secondary" id="sync-rules">
                ルールを同期
            </button>
        </section>

        <!-- フッター -->
        <footer class="popup-footer">
            <a href="#" id="about-link">About</a>
            <a href="#" id="help-link">Help</a>
        </footer>
    </div>

    <script src="../utils/storage.js"></script>
    <script src="popup.js"></script>
</body>
</html>
```

### 2. mettai-extension/shared/popup/popup.js

```javascript
/**
 * ポップアップUI制御
 */

// Chrome/Firefox互換
self.browser = self.browser || self.chrome;

// DOM要素
const focusModeSwitch = document.getElementById('focus-mode-switch');
const focusStatus = document.getElementById('focus-status');
const currentMode = document.getElementById('current-mode');
const ruleCount = document.getElementById('rule-count');
const openSettingsBtn = document.getElementById('open-settings');
const syncRulesBtn = document.getElementById('sync-rules');

// 初期化
document.addEventListener('DOMContentLoaded', async () => {
    await loadStatus();
    setupEventListeners();
});

/**
 * 現在の状態をロード
 */
async function loadStatus() {
    // 集中モードの状態
    const focusMode = await getFocusMode();
    focusModeSwitch.checked = focusMode;
    updateFocusStatus(focusMode);

    // ルール設定
    const config = await getCachedConfig();
    if (config) {
        currentMode.textContent = config.mode === 'blacklist' ? 'ブラックリスト' : 'ホワイトリスト';
        ruleCount.textContent = `${config.rules.length}件`;
    } else {
        currentMode.textContent = '未設定';
        ruleCount.textContent = '0件';
    }
}

/**
 * 集中モードステータス表示を更新
 */
function updateFocusStatus(enabled) {
    if (enabled) {
        focusStatus.textContent = 'オン（監視中）';
        focusStatus.classList.add('status-on');
        focusStatus.classList.remove('status-off');
    } else {
        focusStatus.textContent = 'オフ（休憩中）';
        focusStatus.classList.add('status-off');
        focusStatus.classList.remove('status-on');
    }
}

/**
 * イベントリスナー設定
 */
function setupEventListeners() {
    // 集中モード切替
    focusModeSwitch.addEventListener('change', async (e) => {
        const enabled = e.target.checked;
        await setFocusMode(enabled);
        updateFocusStatus(enabled);
    });

    // 設定を開く
    openSettingsBtn.addEventListener('click', () => {
        // TODO: Web管理画面を開く（Issue #009で実装）
        browser.tabs.create({
            url: 'https://mettai.example.com/settings'
        });
    });

    // ルールを同期
    syncRulesBtn.addEventListener('click', async () => {
        syncRulesBtn.disabled = true;
        syncRulesBtn.textContent = '同期中...';

        try {
            // Background scriptに同期リクエストを送信
            await browser.runtime.sendMessage({ action: 'syncRules' });
            await loadStatus();
            syncRulesBtn.textContent = '同期完了';
            setTimeout(() => {
                syncRulesBtn.textContent = 'ルールを同期';
                syncRulesBtn.disabled = false;
            }, 2000);
        } catch (error) {
            console.error('[Popup] Sync failed:', error);
            syncRulesBtn.textContent = '同期失敗';
            setTimeout(() => {
                syncRulesBtn.textContent = 'ルールを同期';
                syncRulesBtn.disabled = false;
            }, 2000);
        }
    });
}
```

### 3. mettai-extension/shared/popup/popup.css

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    width: 320px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a1a;
    color: #e0e0e0;
}

.popup-container {
    padding: 16px;
}

/* ヘッダー */
.popup-header {
    text-align: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid #333;
}

.popup-title {
    font-size: 20px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 4px;
}

.popup-subtitle {
    font-size: 12px;
    color: #888;
}

/* セクション */
.popup-section {
    margin-bottom: 20px;
}

/* 集中モード切替 */
.focus-mode-toggle {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px;
    background: #2a2a2a;
    border-radius: 8px;
}

.toggle-info {
    flex: 1;
}

.toggle-label {
    font-size: 16px;
    font-weight: 600;
    color: #fff;
    margin-bottom: 4px;
}

.toggle-description {
    font-size: 13px;
    color: #aaa;
}

.toggle-description.status-on {
    color: #4CAF50;
    font-weight: 600;
}

.toggle-description.status-off {
    color: #757575;
}

/* トグルスイッチ */
.switch {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 28px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #555;
    transition: 0.3s;
    border-radius: 28px;
}

.slider:before {
    position: absolute;
    content: "";
    height: 20px;
    width: 20px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: 0.3s;
    border-radius: 50%;
}

input:checked + .slider {
    background-color: #4CAF50;
}

input:checked + .slider:before {
    transform: translateX(22px);
}

/* ステータス表示 */
.status-info {
    background: #2a2a2a;
    border-radius: 8px;
    padding: 12px;
}

.status-item {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
}

.status-item:not(:last-child) {
    border-bottom: 1px solid #333;
}

.status-label {
    font-size: 13px;
    color: #aaa;
}

.status-value {
    font-size: 13px;
    color: #fff;
    font-weight: 600;
}

/* ボタン */
.btn {
    width: 100%;
    padding: 10px;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-bottom: 8px;
}

.btn:hover {
    transform: translateY(-1px);
}

.btn:active {
    transform: translateY(0);
}

.btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.btn-primary {
    background: #4CAF50;
    color: #fff;
}

.btn-primary:hover:not(:disabled) {
    background: #45a049;
}

.btn-secondary {
    background: #424242;
    color: #fff;
}

.btn-secondary:hover:not(:disabled) {
    background: #525252;
}

/* フッター */
.popup-footer {
    text-align: center;
    padding-top: 12px;
    border-top: 1px solid #333;
}

.popup-footer a {
    font-size: 12px;
    color: #888;
    text-decoration: none;
    margin: 0 8px;
}

.popup-footer a:hover {
    color: #4CAF50;
}
```

## テスト要件

### 手動テスト項目

```
[ ] ポップアップが320px幅で表示される
[ ] 集中モードON/OFFトグルが動作する
[ ] トグルON時に「オン（監視中）」と表示される
[ ] トグルOFF時に「オフ（休憩中）」と表示される
[ ] 現在のモード（ブラックリスト/ホワイトリスト）が表示される
[ ] アクティブルール数が表示される
[ ] 「設定を開く」ボタンで新しいタブが開く
[ ] 「ルールを同期」ボタンで同期が実行される
[ ] 同期中は「同期中...」と表示される
[ ] 同期完了後に「同期完了」→「ルールを同期」に戻る
[ ] トグルスイッチのアニメーションが滑らか
[ ] ダークモードで統一されたデザイン
```

### デザイン確認項目

```
[ ] 320px幅で収まる
[ ] ダークテーマが適用されている
[ ] トグルスイッチが分かりやすい
[ ] ボタンのhover/activeエフェクトが動作する
[ ] ステータス表示が見やすい
[ ] フッターのリンクが機能する
```

## テストコマンド

```bash
# 拡張機能をビルド
cd mettai-extension
./build.sh

# Chrome で手動テスト
# 1. chrome://extensions/ から dist/chrome を読み込み
# 2. ツールバーの拡張アイコンをクリック
# 3. ポップアップが表示されることを確認

# Firefox で手動テスト
# 1. about:debugging から dist/firefox を読み込み
# 2. 同様にテスト
```

## 完了条件

- [ ] popup.html が正しく表示される
- [ ] popup.js が動作する
- [ ] popup.css が適用され、デザインが美しい
- [ ] 集中モードON/OFF切替が動作する
- [ ] ルール同期ボタンが動作する
- [ ] トグルスイッチのアニメーションが滑らか
- [ ] Chrome/Firefoxで手動テストが全て通る

## 備考

- ポップアップサイズは 320px × auto（高さは自動）
- ダークテーマ（#1a1a1a 背景）で統一
- トグルスイッチは CSS のみで実装（JS不要）
- 「設定を開く」ボタンは Issue #009 でWeb管理画面を実装後に接続
- storage.js を再利用してローカルストレージと連携
- リアクティブに状態を反映（トグル変更→即座に反映）
