#!/bin/bash
# 盤後自動更新：對帳到期預測、更新 open 標的的估值、補最近幾週的每週估值。
# 由 launchd 呼叫（設定見 SKILL.md「自動更新」），不需要 Claude session。
# 錯過一次不會造成資料缺口：日線按月抓、對帳以歷史收盤計算，下次執行即補齊。

set -u
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${TRACKER_PYTHON:-/usr/bin/python3}"   # launchd 的 PATH 極簡，一律用絕對路徑
LOG_DIR="$HOME/.stock-tracker/logs"
LOG_RETENTION_DAYS=60
LAUNCHD_LOG_MAX_BYTES=1048576
LOCK_FILE="$HOME/.stock-tracker/update.lock"
EX_TEMPFAIL=75   # lockf：鎖已被其他程序持有

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/update-$(date +%Y%m%d).log"
cd "$SCRIPTS_DIR" || exit 1

# 互斥：用 lockf 的核心層檔案鎖重新執行自己。程序結束（含被強制中斷）鎖即釋放，
# 不會有殘留鎖，取得鎖也沒有競態。手動執行與排程重疊時，後到的略過。
if [ -z "${TRACKER_UPDATE_LOCKED:-}" ]; then
    TRACKER_UPDATE_LOCKED=1 /usr/bin/lockf -s -k -t 0 "$LOCK_FILE" \
        /bin/bash "$SCRIPTS_DIR/$(basename "$0")" "$@"   # 已 cd 進 SCRIPTS_DIR，相對的 $0 會失效
    code=$?
    if [ "$code" -eq "$EX_TEMPFAIL" ]; then
        echo "== $(date '+%F %T') 另一個更新仍在執行，本次略過" >> "$LOG"
        exit 0
    fi
    exit "$code"
fi

status=0
run_step() {
    echo "== $(date '+%F %T') $*" >> "$LOG"
    if ! "$PYTHON" "$@" >> "$LOG" 2>&1; then
        echo "!! 失敗：$*" >> "$LOG"
        status=1
    fi
}

run_step track.py reconcile
if ! open_tickers=$("$PYTHON" -c "import db; conn = db.connect(); print(' '.join(r[0] for r in conn.execute(
    \"SELECT DISTINCT ticker FROM predictions WHERE status = 'open' ORDER BY ticker\")))" 2>> "$LOG"); then
    echo "!! 失敗：查詢 open 標的，略過估值更新" >> "$LOG"
    status=1
elif [ -n "$open_tickers" ]; then
    # shellcheck disable=SC2086  # 代號以空白分隔，需要拆成多個參數
    run_step fetch_valuation.py latest $open_tickers
fi
run_step fetch_valuation.py backfill --years 0.05   # 約 2.5 週；已抓過的週走快取，不重複請求

# 清理失敗只記警告：舊 log 刪不掉不代表資料沒更新
find "$LOG_DIR" -name 'update-*.log' -mtime +"$LOG_RETENTION_DAYS" -delete 2>> "$LOG" \
    || echo "!! 警告：清理舊 log 失敗" >> "$LOG"
# launchd.log 只收腳本外層錯誤，量很少；超過上限就清空，避免無限累積
if [ -f "$LOG_DIR/launchd.log" ] && [ "$(stat -f%z "$LOG_DIR/launchd.log")" -gt "$LAUNCHD_LOG_MAX_BYTES" ]; then
    : > "$LOG_DIR/launchd.log"
fi
echo "== $(date '+%F %T') 結束 status=$status" >> "$LOG"
exit "$status"
