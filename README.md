# Free Proxy Fetcher (GitHub Actions)

VPS မလို — GitHub Actions အလကားသုံး။ ၂ နာရီတစ်ခါ public proxy list 18 ခုကနေ
ယူ → စစ် → repo ထဲ commit → Telegram ကို အကြောင်းကြား။

## အသုံးပြုပုံ (၅ မိနစ်)

1. **Repo အသစ်ဆောက်** — github.com → New repository → နာမည်ပေး (ဥပမာ `free-proxy`)
   → Public → Create
2. **ဒီ folder ထဲက file အားလုံး upload** — repo page → `Add file` → `Upload files`
   → file/folder အားလုံး drag-drop (`.github` folder ရော ပါရမယ်)
3. **Secrets ၂ ခု ထည့်** — repo `Settings` → `Secrets and variables` → `Actions`
   → `New repository secret`:
   - `TG_BOT_TOKEN` = BotFather က ရတဲ့ token
   - `TG_CHAT_ID` = ကိုယ့် Telegram user ID ( [@userinfobot](https://t.me/userinfobot) ကနေ ယူ)
4. **Actions ဖွင့်** — repo `Actions` tab → `proxy-refresh` → `Enable workflow`
   → `Run workflow` နှိပ် စမ်း
5. **List ယူသုံးရန်** —
   `https://cdn.jsdelivr.net/gh/<user>/<repo>@main/proxies/http_tested.txt`
   (jsdelivr CDN, အလကား, မြန်)

## ထွက်တဲ့ file တွေ (`proxies/`)

| file | အကြောင်း |
|---|---|
| `http_tested.txt` | စစ်ပြီးသား၊ အမြန်ဆုံး အရင်စီ — **အဓိက သုံးမယ့် list**။ အပေါ်မှာ `# last_update` / `# next_update` / `# working` ပါတယ်။ ပြီးရင် **`# portal_ok`** section (portal ကို တကယ်ဖြေတဲ့ အကောင်းဆုံးတွေ အရင်), ပြီးမှ **`# tested_ok`** section။ Header/section ကြောင်းတွေက `#` နဲ့စ + colon မပါ — proxy parser တွေ အမှားမဖတ်မိအောင် စစ်ပြီးသား |
| `portal_ok.txt` | Ruijie portal ကို ဖြေတဲ့ proxy တွေ (stage 2) |
| `http_raw.txt` | မစစ်ရသေးတဲ့ unique အားလုံး |
| `stats.json` | စာရင်း (source တစ်ခုချင်းစီ ရမရ, working အရေအတွက်...) |

## သူများကို ရက်အကန့်အသတ်နဲ့ ထည့်တာ (subscribers)

`subscribers.json` — chat_id နဲ့ expiry date:
```json
{
  "123456789": {"expiry": "2026-10-24", "note": "Mg Mg"},
  "987654321": {"expiry": "2026-11-17", "note": ""}
}
```
- Run တိုင်း noti ကို owner + expiry မကျော်သေးသူတွေဆီ ပို့တယ်
- Expiry ကျော်ရင် auto-ဖြုတ်ပြီး commit တယ်
- **အရေးကြီး**: လူက bot ကို အရင် `/start` နှိပ်ထားရမယ် — မနှိပ်ထားရင် Telegram က message ပို့ခွင့်မပြုဘူး
- ထည့်ချင်ရင် **ကိုယ်တိုင်** — repo `Actions` tab → `add-subscriber` → `Run workflow`
  → chat ID + ရက် + note ဖြည့် → Run. ဒါပဲ (30 စက္ကန့်, ဖုန်းနဲ့ရ)
  - days = `0` ဆို ဖြုတ်တာ
- ဒါမှမဟုတ် ငါ့ကိုပြော — "123456789 ကို 7 ရက် ထည့်" — ငါထည့်ပေးမယ်

## ပြင်လို့ရတာတွေ

- `.github/workflows/proxy-refresh.yml` ထဲ `cron: "0 */2 * * *"` = ၂ နာရီတစ်ခါ
  (ဥပမာ ၃ နာရီတစ်ခါ → `0 */3 * * *`)
- `TEST_PORTAL: "1"` → `"0"` ဆို portal stage မစစ်ဘူး (ပိုမြန်)
- `REFRESH_HOURS` env နဲ့ cron interval အတူတူထားရ — `http_tested.txt` ထဲက
  `# next_update` line အတွက် သုံးတယ်
- `fetch_proxies.py` → `SAMPLE_PER_SOURCE` (default 1000/source)
- `test_proxies.py` → `TEST_CONCURRENCY=250`, `TEST_TIMEOUT=8`

## သတိပြုရန်

- Run တိုင်း auto-commit ဖြစ်လို့ schedule က 60 ရက်ကြာလည်း မရပ်ဘူး
- GitHub cron အချိန် မိနစ်ပိုင်း နောက်ကျနိုင်တယ်
- Portal stage က GitHub IP (datacenter) ကနေ စစ်တာ — portal rate limit ထိရင်
  working နည်းသွားနိုင်တယ်, ဒါကြောင့် neutral check (stage 1) က အဓိက
