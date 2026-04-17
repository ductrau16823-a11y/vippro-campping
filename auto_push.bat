@echo off
cd /d "C:\Users\Admin\Documents\vippro campping"
(
  echo ==== %date% %time% ====
  git add -A
  git diff --cached --quiet
  if errorlevel 1 (
    git commit -m "auto-push %date% %time%"
    git push origin dev-fix
    echo Push xong.
  ) else (
    echo Khong co thay doi — skip.
  )
  echo.
) >> auto_push.log 2>&1
