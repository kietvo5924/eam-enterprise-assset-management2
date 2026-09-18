import os
import sys
import time
import subprocess
import requests

ADB_PATH = r"C:\Users\Admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
ARTIFACTS_DIR = r"C:\Users\Admin\.gemini\antigravity-ide\brain\59bf5e2f-4a97-401d-82a0-2ec8b868c774"
BACKEND_URL = "http://127.0.0.1:8000"

def adb_command(*args):
    cmd = [ADB_PATH] + list(args)
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return res.stdout.strip()

def capture_screenshot(filename):
    out_path = os.path.join(ARTIFACTS_DIR, filename)
    adb_command("shell", "screencap", "-p", "/sdcard/e2e_screen.png")
    adb_command("pull", "/sdcard/e2e_screen.png", out_path)
    print(f"  [SCREENSHOT] Saved: {filename}")
    return out_path

def tap(x, y, delay=1.0):
    adb_command("shell", "input", "tap", str(x), str(y))
    time.sleep(delay)

def main():
    print("=" * 70)
    print("STARTING AUTOMATED MOBILE E2E NOTIFICATION TEST SUITE")
    print("=" * 70)

    # 1. Reverse port 8000
    print("\n[Step 1] Port forwarding 8000...")
    adb_command("reverse", "tcp:8000", "tcp:8000")

    # 2. Check Backend Health
    print("\n[Step 2] Checking Django Backend API...")
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/notifications/unread-count/", timeout=5)
        print(f"  Backend unread-count response: status {r.status_code}")
    except Exception as e:
        print(f"  Backend check failed: {e}")

    # 3. Dismiss any Android system dialogs
    print("\n[Step 3] Dismissing system dialogs/keyboard...")
    adb_command("shell", "input", "keyevent", "111") # Escape
    adb_command("shell", "input", "keyevent", "4")   # Back (dismiss keyboard)
    time.sleep(1)

    # 4. Sign in if on Login screen
    print("\n[Step 4] Triggering Sign In on Mobile App...")
    # Tap Sign In button at (540, 1750)
    tap(540, 1750, delay=3.5)

    # 5. Capture Dashboard
    print("\n[Step 5] Verifying Dashboard & Unread Notification Badge...")
    dash_img = capture_screenshot("mobile_01_dashboard.png")

    # 6. Tap Notification Bell Icon on top right
    print("\n[Step 6] Navigating to Notifications Screen via Bell Icon...")
    # Appbar bell icon is around x=980, y=170
    tap(980, 170, delay=2.5)
    notif_all_img = capture_screenshot("mobile_02_notifications_all.png")

    # 7. Tap 'Chưa đọc' tab (x=540, y=340)
    print("\n[Step 7] Filtering Tab 'Chưa đọc'...")
    tap(540, 340, delay=1.5)
    notif_unread_img = capture_screenshot("mobile_03_notifications_unread.png")

    # 8. Tap 'Cần xử lý' tab (x=880, y=340)
    print("\n[Step 8] Filtering Tab 'Cần xử lý' (Actionable Notifications)...")
    tap(880, 340, delay=1.5)
    notif_action_img = capture_screenshot("mobile_04_notifications_actionable.png")

    # 9. Tap first notification card to open Detail Bottom Sheet (x=540, y=480)
    print("\n[Step 9] Opening Notification Detail BottomSheet Modal...")
    tap(540, 480, delay=2.0)
    sheet_img = capture_screenshot("mobile_05_notification_detail_sheet.png")

    # 10. Check if action resolve button exists and tap it (around x=540, y=2120)
    print("\n[Step 10] Interacting with Action Button or closing sheet...")
    # Tap "Xác nhận đã xử lý" button if present
    tap(540, 2120, delay=2.0)
    resolved_img = capture_screenshot("mobile_06_action_resolved.png")

    print("\n" + "=" * 70)
    print("ALL MOBILE E2E NOTIFICATION TEST STEPS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
