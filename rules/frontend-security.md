---
description: 前端資安規範。當使用者說「審查前端」、「review 這個 component」、「這個安全嗎」、
  「有沒有 XSS」、「token 怎麼存」、「CSP 設定」、「CORS 問題」、「前端 PR」、
  「PII 保護」、「供應鏈攻擊」時載入。也適用於所有含 React / Vue / Next.js 的專案。
---

# Frontend Security Rules

> 前端專屬資安規範，補充通用 security.md 未涵蓋的攻擊面。
> 適用於所有瀏覽器端程式碼（React / Vue / Vanilla JS）。

---

## Content Security Policy（CSP）

```http
# ✅ 嚴格 CSP，禁止 inline script
Content-Security-Policy: 
  default-src 'self';
  script-src 'self' 'nonce-{RANDOM}';
  style-src 'self' 'nonce-{RANDOM}';
  img-src 'self' data: https:;
  connect-src 'self' https://api.yourdomain.com;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

- nonce 必須每次 request 重新產生（不可重複使用）
- 禁止 `unsafe-inline`、`unsafe-eval`
- 使用 [CSP Evaluator](https://csp-evaluator.withgoogle.com/) 驗證

---

## Token 儲存策略

```ts
// ❌ localStorage — XSS 可直接讀取
localStorage.setItem('token', accessToken)

// ✅ HttpOnly Cookie — JS 無法存取
// 由 server 設定：
// Set-Cookie: token=xxx; HttpOnly; Secure; SameSite=Strict; Path=/
```

| 儲存位置 | XSS 風險 | CSRF 風險 | 建議 |
|---------|---------|---------|------|
| localStorage | 高 | 無 | ❌ 不用於 token |
| sessionStorage | 高 | 無 | ❌ 不用於 token |
| HttpOnly Cookie | 無 | 需防護 | ✅ 搭配 CSRF token |
| Memory（變數）| 低 | 無 | ✅ 短期 access token |

---

## Third-party Script 供應鏈防護

```html
<!-- ✅ Subresource Integrity（SRI） -->
<script
  src="https://cdn.example.com/lib.js"
  integrity="sha384-xxxxx"
  crossorigin="anonymous"
></script>
```

- 所有外部 CDN script 必須加 `integrity` hash
- 定期審查 `<script>`、`<link>` 來源清單
- 禁止動態插入來自使用者輸入的 script src

---

## Clickjacking 防護

```http
# HTTP Header（next.config.ts 已涵蓋）
X-Frame-Options: SAMEORIGIN

# CSP 更細緻控制
Content-Security-Policy: frame-ancestors 'self' https://trusted.com
```

---

## CORS 設定

```ts
// ❌ 開放所有來源
Access-Control-Allow-Origin: *

// ✅ 白名單驗證
const ALLOWED_ORIGINS = ['https://app.yourdomain.com']

function corsMiddleware(req, res) {
  const origin = req.headers.origin
  if (ALLOWED_ORIGINS.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin)
  }
}
```

- 禁止 `Access-Control-Allow-Origin: *` 搭配 `credentials: true`
- 預檢請求（OPTIONS）必須正確處理

---

## Prototype Pollution 防護

```ts
// ❌ 危險的物件合併
function merge(target, source) {
  for (const key in source) {
    target[key] = source[key]  // __proto__ 可被污染
  }
}

// ✅ 使用安全的合併方式
import { merge } from 'lodash'  // lodash 4.17.21+ 已修補
// 或
const merged = structuredClone({ ...target, ...source })

// ✅ JSON parse 來自外部的物件
const safe = JSON.parse(JSON.stringify(userInput))
```

---

## 使用者數據保護（PII）

```ts
// ✅ 最小化收集原則
// 只收集功能必要的欄位，不多取

// ❌ 敏感欄位進 analytics / log
analytics.track('signup', { email, password, phone })

// ✅ 只傳匿名識別碼
analytics.track('signup', { userId: hashUserId(userId), plan })

// ✅ 顯示前遮罩
const maskedCard = `**** **** **** ${card.slice(-4)}`
```

- 遵守 GDPR / CCPA：明確同意才收集
- Cookie consent 必須在設定前取得授權
- 使用者要求刪除時，前端 cache / localStorage 同步清除

---

## WebSocket 安全

```ts
// ✅ 使用 wss:// （TLS 加密）
const ws = new WebSocket('wss://api.yourdomain.com/ws')

// ✅ 連線時驗證 token
ws.onopen = () => {
  ws.send(JSON.stringify({ type: 'auth', token: getAccessToken() }))
}

// ✅ 接收訊息時驗證來源與格式
ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (!isValidMessageSchema(data)) return  // 拒絕非預期格式
}
```

---

## 前端安全 Checklist

PR 合併前確認：
- [ ] 無 `dangerouslySetInnerHTML` 含未消毒的使用者輸入
- [ ] token 未存放在 localStorage
- [ ] 所有外部 CDN 有 SRI hash
- [ ] CSP header 已設定且無 `unsafe-inline`
- [ ] CORS 白名單正確，無 wildcard + credentials
- [ ] 無未使用的第三方 SDK（供應鏈縮小攻擊面）
- [ ] PII 未進入 console.log / analytics
