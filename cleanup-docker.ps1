# Xóa các image rác (dangling images) không còn được sử dụng (tag là <none>)
docker image prune -f

# Xóa các bộ nhớ đệm (cache) của Docker Builder để giải phóng ổ cứng
docker builder prune -f

Write-Host "Đã dọn dẹp xong rác của Docker!" -ForegroundColor Green
