# Issue #007: ブラウザ拡張機能 - オーバーレイUI実装

## 目的

許可外サイトを開いた際に表示される気づきオーバーレイを実装する。5秒カウントダウン後に「作業に戻る」「5分だけ許可」の選択肢を表示し、ユーザーの自己選択を促す。

## 作成ファイル名

```
mettai-extension/
├── shared/
│   ├── content/
│   │   └── overlay.js          # オーバーレイロジック
│   └── styles/
│       └── overlay.css         # オーバーレイスタイル
└── icons/
    ├── icon16.png              # 拡張アイコン（16x16）
    ├── icon48.png              # 拡張アイコン（48x48）
    └── icon128.png             # 拡張アイコン（128x128）
```

## ディレクトリ構成

```
mettai-extension/
├── shared/
│   ├── content/
│   │   └── overlay.js       # Content Script（DOM操作）
│   └── styles/
│       └── overlay.css      # オーバーレイデザイン
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

## 実装内容

### 1. mettai-extension/shared/content/overlay.js

```javascript
/**
 * オーバーレイUI
 * Content Script として動作
 */

// Chrome/Firefox互換
self.browser = self.browser || self.chrome;

let overlayElement = null;
let countdownInterval = null;
let currentUrl = null;

/**
 * Background scriptからのメッセージを受信
 */
browser.runtime.onMessage.addListener((message) => {
    if (message.action === 'showOverlay') {
        showOverlay(message.url);
    }
});

/**
 * オーバーレイを表示
 */
function showOverlay(url) {
    // 既存のオーバーレイを削除
    removeOverlay();

    currentUrl = url;

    // オーバーレイ要素を作成
    overlayElement = document.createElement('div');
    overlayElement.id = 'mettai-overlay';
    overlayElement.innerHTML = `
        <div class="mettai-overlay-content">
            <h1 class="mettai-overlay-title">気づき</h1>
            <p class="mettai-overlay-message">
                作業中に別のサイトを開こうとしています。<br>
                本当にこのサイトを開きますか?
            </p>
            <div class="mettai-overlay-countdown" id="mettai-countdown">
                5
            </div>
            <div class="mettai-overlay-buttons" id="mettai-buttons" style="display: none;">
                <button class="mettai-btn mettai-btn-primary" id="mettai-btn-back">
                    作業に戻る
                </button>
                <button class="mettai-btn mettai-btn-secondary" id="mettai-btn-allow">
                    5分だけ許可
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(overlayElement);

    // カウントダウン開始
    startCountdown();

    // イベントリスナー設定
    document.getElementById('mettai-btn-back').addEventListener('click', handleGoBack);
    document.getElementById('mettai-btn-allow').addEventListener('click', handleAllow);
}

/**
 * カウントダウン開始
 */
function startCountdown() {
    let count = 5;
    const countdownElement = document.getElementById('mettai-countdown');
    const buttonsElement = document.getElementById('mettai-buttons');

    countdownInterval = setInterval(() => {
        count--;
        if (count > 0) {
            countdownElement.textContent = count;
        } else {
            // カウントダウン終了
            clearInterval(countdownInterval);
            countdownElement.style.display = 'none';
            buttonsElement.style.display = 'flex';
        }
    }, 1000);
}

/**
 * 「作業に戻る」ボタンのハンドラ
 */
async function handleGoBack() {
    await browser.runtime.sendMessage({
        action: 'goBack',
        url: currentUrl
    });
    removeOverlay();
    window.history.back();
}

/**
 * 「5分だけ許可」ボタンのハンドラ
 */
async function handleAllow() {
    await browser.runtime.sendMessage({
        action: 'allowTemporarily',
        url: currentUrl
    });
    removeOverlay();
}

/**
 * オーバーレイを削除
 */
function removeOverlay() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }
    if (overlayElement) {
        overlayElement.remove();
        overlayElement = null;
    }
}
```

### 2. mettai-extension/shared/styles/overlay.css

```css
/* オーバーレイ全体 */
#mettai-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.95);
    z-index: 2147483647; /* 最大値 */
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #fff;
}

/* コンテンツエリア */
.mettai-overlay-content {
    text-align: center;
    max-width: 500px;
    padding: 40px;
    background: rgba(30, 30, 30, 0.9);
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

/* タイトル */
.mettai-overlay-title {
    font-size: 32px;
    font-weight: 700;
    margin: 0 0 20px 0;
    color: #f0f0f0;
}

/* メッセージ */
.mettai-overlay-message {
    font-size: 18px;
    line-height: 1.6;
    margin: 0 0 30px 0;
    color: #d0d0d0;
}

/* カウントダウン */
.mettai-overlay-countdown {
    font-size: 80px;
    font-weight: 700;
    color: #ff6b6b;
    margin: 30px 0;
    animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% {
        transform: scale(1);
        opacity: 1;
    }
    50% {
        transform: scale(1.1);
        opacity: 0.8;
    }
}

/* ボタンコンテナ */
.mettai-overlay-buttons {
    display: flex;
    gap: 16px;
    justify-content: center;
    margin-top: 30px;
}

/* ボタン共通 */
.mettai-btn {
    padding: 14px 28px;
    font-size: 16px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.mettai-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.mettai-btn:active {
    transform: translateY(0);
}

/* プライマリボタン（作業に戻る） */
.mettai-btn-primary {
    background: #4CAF50;
    color: #fff;
}

.mettai-btn-primary:hover {
    background: #45a049;
}

/* セカンダリボタン（5分だけ許可） */
.mettai-btn-secondary {
    background: #757575;
    color: #fff;
}

.mettai-btn-secondary:hover {
    background: #616161;
}
```

### 3. アイコン作成（仮）

```bash
# 仮のアイコン作成スクリプト（ImageMagick使用）
mkdir -p mettai-extension/icons

# 128x128 ベースアイコン
convert -size 128x128 xc:#FF6B6B -gravity center \
    -pointsize 80 -annotate 0 "滅" \
    mettai-extension/icons/icon128.png

# 48x48
convert mettai-extension/icons/icon128.png -resize 48x48 \
    mettai-extension/icons/icon48.png

# 16x16
convert mettai-extension/icons/icon128.png -resize 16x16 \
    mettai-extension/icons/icon16.png
```

**注:** 本番環境では、デザイナーが作成した適切なアイコンに差し替えること。

## テスト要件

### 手動テスト項目

```
[ ] オーバーレイが画面全体を覆う
[ ] カウントダウンが5秒間動作する
[ ] カウントダウン終了後にボタンが表示される
[ ] 「作業に戻る」ボタンで前のページに戻る
[ ] 「5分だけ許可」ボタンでオーバーレイが消える
[ ] 5分間一時許可が有効になる
[ ] オーバーレイがページのCSSに影響されない（z-index最大）
[ ] アニメーション（pulse）が正常に動作する
```

### デザイン確認項目

```
[ ] ダークモードで視認性が高い
[ ] ボタンのhover/activeエフェクトが動作する
[ ] モバイルブラウザでも適切に表示される
[ ] カウントダウンの数字が読みやすい
[ ] ボタンのラベルが明確
```

### アクセシビリティ

```
[ ] キーボード操作が可能（Tab, Enter）
[ ] スクリーンリーダーで読み上げ可能
[ ] 高コントラスト（背景rgba(0,0,0,0.95)）
```

## テストコマンド

```bash
# 拡張機能をビルド
cd mettai-extension
./build.sh

# Chrome で手動テスト
# 1. chrome://extensions/ から dist/chrome を読み込み
# 2. ブロック対象URLを開く（例: https://www.youtube.com/）
# 3. オーバーレイが表示されることを確認

# Firefox で手動テスト
# 1. about:debugging から dist/firefox を読み込み
# 2. 同様にテスト
```

## 完了条件

- [ ] overlay.js が正しく動作する
- [ ] overlay.css が適用され、デザインが美しい
- [ ] カウントダウン（5秒）が正常に動作する
- [ ] 「作業に戻る」ボタンが動作する
- [ ] 「5分だけ許可」ボタンが動作する
- [ ] オーバーレイがページのスタイルに影響されない
- [ ] Chrome/Firefoxで手動テストが全て通る
- [ ] アイコンが表示される（仮アイコンでOK）

## 備考

- Content Scriptとして動作するため、ページのDOM操作が可能
- z-index: 2147483647 で最前面表示を保証
- カウントダウンは `setInterval` で1秒ごとに更新
- `window.history.back()` で前のページに戻る
- アイコンは仮で作成し、後でデザイナーが差し替え
- 色彩: #FF6B6B（赤系）でカウントダウンを強調、#4CAF50（緑系）でポジティブなアクションを促す
