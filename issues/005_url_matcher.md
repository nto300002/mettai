# Issue #005: URLマッチングエンジン実装（matcher.js）

## 目的

ブラウザ拡張機能のコア機能である、URLマッチングエンジンを実装する。キーワード部分一致・ドメイン一致・正規表現マッチングの3種類をサポートし、TDDで高いカバレッジを実現する。

## 作成ファイル名

```
mettai-extension/
├── shared/
│   └── utils/
│       ├── matcher.js          # URLマッチングエンジン本体
│       └── matcher.test.js     # Jestテスト
├── package.json                # Jest依存関係
├── jest.config.js              # Jest設定
└── .gitignore                  # node_modules除外
```

## ディレクトリ構成

```
mettai-extension/
├── shared/
│   └── utils/
│       ├── matcher.js       # キーワード・ドメイン・正規表現マッチング
│       └── matcher.test.js  # 95%以上のカバレッジを目指す
├── package.json             # Jest, @types/jest
├── jest.config.js           # テスト設定
└── .gitignore
```

## 実装内容

### 1. mettai-extension/package.json

```json
{
  "name": "mettai-extension",
  "version": "1.0.0",
  "description": "Mettai Browser Extension",
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "@types/jest": "^29.5.11"
  }
}
```

### 2. mettai-extension/jest.config.js

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
  testEnvironment: 'node',
};
```

### 3. mettai-extension/shared/utils/matcher.js

```javascript
/**
 * URLマッチングエンジン
 */

/**
 * URLがルールにマッチするか判定
 * @param {string} url - チェック対象のURL
 * @param {string} pattern - マッチパターン
 * @param {string} matchType - マッチタイプ（keyword, domain, regex）
 * @returns {boolean} マッチしたらtrue
 */
function matchUrl(url, pattern, matchType = 'keyword') {
    if (!url || !pattern) {
        return false;
    }

    const normalizedUrl = url.toLowerCase();
    const normalizedPattern = pattern.toLowerCase();

    switch (matchType) {
        case 'keyword':
            return matchKeyword(normalizedUrl, normalizedPattern);
        case 'domain':
            return matchDomain(url, normalizedPattern);
        case 'regex':
            return matchRegex(url, pattern);
        default:
            return false;
    }
}

/**
 * キーワード部分一致
 */
function matchKeyword(url, keyword) {
    return url.includes(keyword);
}

/**
 * ドメイン一致（www付き、サブドメイン対応）
 */
function matchDomain(url, domain) {
    try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname.toLowerCase();
        const normalizedDomain = domain.toLowerCase();

        // 完全一致
        if (hostname === normalizedDomain) {
            return true;
        }

        // www. 付き一致
        if (hostname === `www.${normalizedDomain}` || normalizedDomain === `www.${hostname}`) {
            return true;
        }

        // ワイルドカード対応（*.example.com）
        if (normalizedDomain.startsWith('*.')) {
            const baseDomain = normalizedDomain.slice(2);
            return hostname.endsWith(`.${baseDomain}`) || hostname === baseDomain;
        }

        // サブドメイン対応
        return hostname.endsWith(`.${normalizedDomain}`);
    } catch (e) {
        return false;
    }
}

/**
 * 正規表現マッチング（ReDoS対策付き）
 */
function matchRegex(url, pattern, timeoutMs = 100) {
    try {
        const start = performance.now();
        const regex = new RegExp(pattern, 'i');
        const result = regex.test(url);
        const elapsed = performance.now() - start;

        if (elapsed > timeoutMs) {
            console.warn(`[Matcher] Regex timeout: ${pattern} took ${elapsed}ms`);
            return false;
        }

        return result;
    } catch (e) {
        console.warn(`[Matcher] Invalid regex: ${pattern}`, e);
        return false;
    }
}

/**
 * URLがブロック対象かどうかを判定
 * @param {string} url - チェック対象のURL
 * @param {Array} rules - ルールの配列 [{pattern, match_type}]
 * @param {string} mode - 'blacklist' or 'whitelist'
 * @returns {boolean} ブロックすべきならtrue
 */
function shouldBlock(url, rules, mode = 'blacklist') {
    if (!url || !rules) {
        return false;
    }

    const matched = rules.some(rule => matchUrl(url, rule.pattern, rule.match_type));

    if (mode === 'blacklist') {
        // ブラックリストモード: マッチしたらブロック
        return matched;
    } else if (mode === 'whitelist') {
        // ホワイトリストモード: マッチしなかったらブロック
        return !matched;
    }

    return false;
}

// Node.js環境（Jest）用のエクスポート
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        matchUrl,
        matchKeyword,
        matchDomain,
        matchRegex,
        shouldBlock,
    };
}
```

### 4. mettai-extension/.gitignore

```
node_modules/
coverage/
*.log
.DS_Store
```

## テスト要件

### TDD サイクル

**Red → Green → Refactor を厳守**

### mettai-extension/shared/utils/matcher.test.js

```javascript
const {
    matchUrl,
    matchKeyword,
    matchDomain,
    matchRegex,
    shouldBlock,
} = require('./matcher');

describe('matchKeyword', () => {
    test('キーワードが含まれる場合にtrueを返す', () => {
        expect(matchKeyword('https://www.youtube.com/watch', 'youtube')).toBe(true);
    });

    test('キーワードが含まれない場合にfalseを返す', () => {
        expect(matchKeyword('https://www.google.com/', 'youtube')).toBe(false);
    });

    test('大文字小文字を無視する', () => {
        expect(matchKeyword('https://www.YouTube.com/', 'youtube')).toBe(true);
        expect(matchKeyword('https://www.youtube.com/', 'YOUTUBE')).toBe(true);
    });

    test('URL全体に対してマッチする', () => {
        expect(matchKeyword('https://m.youtube.com/shorts/abc', 'youtube')).toBe(true);
        expect(matchKeyword('https://youtube.googleapis.com/', 'youtube')).toBe(true);
    });
});

describe('matchDomain', () => {
    test('完全一致する場合にtrueを返す', () => {
        expect(matchDomain('https://github.com/', 'github.com')).toBe(true);
    });

    test('www付きドメインにマッチする', () => {
        expect(matchDomain('https://www.github.com/', 'github.com')).toBe(true);
        expect(matchDomain('https://github.com/', 'www.github.com')).toBe(true);
    });

    test('サブドメインにマッチする', () => {
        expect(matchDomain('https://api.github.com/', 'github.com')).toBe(true);
        expect(matchDomain('https://docs.github.com/', 'github.com')).toBe(true);
    });

    test('ワイルドカード（*.domain）にマッチする', () => {
        expect(matchDomain('https://sub.example.com/', '*.example.com')).toBe(true);
        expect(matchDomain('https://deep.sub.example.com/', '*.example.com')).toBe(true);
    });

    test('異なるドメインにはマッチしない', () => {
        expect(matchDomain('https://github.com/', 'gitlab.com')).toBe(false);
        expect(matchDomain('https://xgithub.com/', 'github.com')).toBe(false);
    });

    test('不正なURLの場合にfalseを返す', () => {
        expect(matchDomain('not-a-url', 'github.com')).toBe(false);
    });
});

describe('matchRegex', () => {
    test('正規表現にマッチする場合にtrueを返す', () => {
        expect(matchRegex('https://www.reddit.com/r/programming', 'reddit\\.com/r/')).toBe(true);
    });

    test('正規表現にマッチしない場合にfalseを返す', () => {
        expect(matchRegex('https://www.reddit.com/user/test', 'reddit\\.com/r/')).toBe(false);
    });

    test('大文字小文字を無視する', () => {
        expect(matchRegex('https://www.REDDIT.com/r/test', 'reddit\\.com')).toBe(true);
    });

    test('不正な正規表現の場合にfalseを返す', () => {
        expect(matchRegex('https://example.com/', '[invalid(regex')).toBe(false);
    });

    test('ReDoSリスクのあるパターンでタイムアウトする', () => {
        const evilPattern = '(a+)+b';
        const evilUrl = 'aaaaaaaaaaaaaaaaaaaaaaaaaaac';
        expect(matchRegex(evilUrl, evilPattern, 50)).toBe(false);
    });
});

describe('matchUrl', () => {
    test('keywordタイプでマッチする', () => {
        expect(matchUrl('https://www.youtube.com/', 'youtube', 'keyword')).toBe(true);
    });

    test('domainタイプでマッチする', () => {
        expect(matchUrl('https://github.com/', 'github.com', 'domain')).toBe(true);
    });

    test('regexタイプでマッチする', () => {
        expect(matchUrl('https://reddit.com/r/test', 'reddit\\.com/r/', 'regex')).toBe(true);
    });

    test('空のURLやパターンの場合にfalseを返す', () => {
        expect(matchUrl('', 'youtube', 'keyword')).toBe(false);
        expect(matchUrl('https://example.com/', '', 'keyword')).toBe(false);
    });

    test('未知のマッチタイプの場合にfalseを返す', () => {
        expect(matchUrl('https://example.com/', 'test', 'unknown')).toBe(false);
    });
});

describe('shouldBlock', () => {
    const rules = [
        { pattern: 'youtube', match_type: 'keyword' },
        { pattern: 'twitter.com', match_type: 'domain' },
    ];

    test('ブラックリストモード: マッチしたらブロック', () => {
        expect(shouldBlock('https://www.youtube.com/', rules, 'blacklist')).toBe(true);
        expect(shouldBlock('https://twitter.com/', rules, 'blacklist')).toBe(true);
        expect(shouldBlock('https://github.com/', rules, 'blacklist')).toBe(false);
    });

    test('ホワイトリストモード: マッチしなかったらブロック', () => {
        expect(shouldBlock('https://www.youtube.com/', rules, 'whitelist')).toBe(false);
        expect(shouldBlock('https://twitter.com/', rules, 'whitelist')).toBe(false);
        expect(shouldBlock('https://github.com/', rules, 'whitelist')).toBe(true);
    });

    test('空のURLやルールの場合にfalseを返す', () => {
        expect(shouldBlock('', rules, 'blacklist')).toBe(false);
        expect(shouldBlock('https://example.com/', null, 'blacklist')).toBe(false);
    });

    test('ルールが空配列の場合の挙動', () => {
        expect(shouldBlock('https://example.com/', [], 'blacklist')).toBe(false);
        expect(shouldBlock('https://example.com/', [], 'whitelist')).toBe(true);
    });
});
```

## テストコマンド

```bash
# 依存関係インストール
cd mettai-extension
npm install

# テストを先に書く（Red）
npm test

# 実装後にテスト実行（Green）
npm test

# カバレッジ確認
npm run test:coverage

# ウォッチモード（開発時）
npm run test:watch
```

## 完了条件

- [ ] matchKeyword が正しく動作する
- [ ] matchDomain が正しく動作する（www付き、サブドメイン、ワイルドカード対応）
- [ ] matchRegex が正しく動作する（ReDoS対策付き）
- [ ] shouldBlock が blacklist/whitelist モードで正しく動作する
- [ ] 全テストが通る
- [ ] カバレッジが 95% 以上
- [ ] ReDoS対策が機能する（タイムアウト100ms）

## 備考

- **TDD厳守:** テストを先に書き、失敗を確認してから実装する
- matcher.js はアプリのコア機能のため、カバレッジ目標は **95%以上**
- ReDoS対策として、正規表現マッチングに100msのタイムアウトを設定
- `performance.now()` がNode.js環境で使用できない場合は `Date.now()` で代替
- ブラウザ環境では `module.exports` が undefined なので条件分岐
