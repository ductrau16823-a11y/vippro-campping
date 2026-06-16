#!/usr/bin/env bash
# Bản auto-push cho Mac (tương đương auto_push.bat trên Win).
# Cách chạy thủ công:   ./auto_push.sh
# Cách chạy tự động:    crontab -e   →   0 0 * * * /bin/bash "/Users/daviiduc/Desktop/Thư mục mới với các mục/github-repos/vippro-campping/auto_push.sh"

REPO_DIR="/Users/daviiduc/Desktop/Thư mục mới với các mục/github-repos/vippro-campping"
LOG_FILE="$REPO_DIR/auto_push.log"
BRANCH="dev-fix"

cd "$REPO_DIR" || exit 1

{
  echo "==== $(date '+%a %m/%d/%Y %H:%M:%S.%N') ===="

  git add -A

  if git diff --cached --quiet; then
    echo "Khong co thay doi — skip."
  else
    git commit -m "auto-push $(date '+%a %m/%d/%Y %H:%M:%S.%N')"
    git push origin "$BRANCH"
    echo "Push xong."
  fi
  echo
} >> "$LOG_FILE" 2>&1
