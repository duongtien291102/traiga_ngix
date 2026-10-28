# traiga_ngix

Repo hạ tầng / deploy cho hệ thống Traiga Livestream: cấu hình SRS media server và `docker-compose.yml` chạy toàn bộ stack trên VPS.

| Repo | Vai trò |
|---|---|
| [traiga_be](https://github.com/duongtien291102/traiga_be) | Golang backend → image `traiga-be` |
| [traiga_fe](https://github.com/duongtien291102/traiga_fe) | React + Nginx → image `traiga-fe` |
| **traiga_ngix** (repo này) | SRS config + docker-compose production |

## Luồng CI/CD

- Push `traiga_be` → test → build image → push Docker Hub → VPS restart **chỉ backend**
- Push `traiga_fe` → build → push Docker Hub → VPS restart **chỉ frontend**
- Push `traiga_ngix` → VPS `git pull` → build SRS image with FFmpeg → restart SRS

VPS builds the SRS image locally to install FFmpeg/ffprobe. Keep `ABR_ENABLED=off` until the VPS has been sized for the extra CPU load; switch it to `on` in `.env` to produce 720p/480p/360p renditions and serve the multivariant playlist. The source rendition remains available at its incoming resolution. Software encoding is CPU intensive, especially for 60 FPS and multiple simultaneous rooms.

## Cài đặt VPS lần đầu (Ubuntu)

```bash
# 1. Cài Docker
curl -fsSL https://get.docker.com | sh

# 2. Clone repo hạ tầng
sudo git clone https://github.com/duongtien291102/traiga_ngix.git /opt/traiga
sudo chown -R $USER /opt/traiga && cd /opt/traiga

# 3. Tạo .env
cp .env.example .env && nano .env

# 4. Đặt chứng chỉ TLS công khai cho SRS (backend và trình duyệt phải tin cậy chứng chỉ)
mkdir -p certs
# Sao chép chứng chỉ Let's Encrypt cho domain trỏ về VPS:
cp /etc/letsencrypt/live/<DOMAIN>/fullchain.pem certs/fullchain.pem
cp /etc/letsencrypt/live/<DOMAIN>/privkey.pem certs/privkey.pem

# 5. Chạy (cần đã push BE & FE ít nhất 1 lần để có image trên Docker Hub)
docker compose build --pull srs && docker compose up -d
```

The React player uses HLS.js adaptive bitrate selection and offers Auto plus the renditions present in the master playlist. On Safari, native HLS keeps automatic quality switching; the quality menu can switch to a rendition listed in the master playlist.

The SRS container is the origin; a CDN is not provisioned by this repository. For large audiences, point a CDN hostname at the SRS HLS origin, route both `/live/*` and `/abr/*`, cache `.ts` segments briefly (about 3 seconds), and bypass cache for `.m3u8` playlists. Set the FE build variable `VITE_HLS_URL` to the CDN origin so the master playlist and all rendition requests use it.

Mở firewall: `80/tcp`, `1935/tcp`, `8080/tcp`, `8088/tcp`, `1985/tcp`, `8000/udp`.

SRS giữ các file DVR trong volume Docker `traiga_recordings`. Backend Azure đọc file qua URL trong `SRS_HTTP_URL` (ví dụ `https://<DOMAIN>:8088`). Trong GitHub repo BE → Settings → Secrets and variables → Actions → Variables, đặt `SRS_HTTP_URL` bằng URL chứng chỉ đó. Không dùng IP nếu chứng chỉ được cấp cho domain.

### Đồng bộ âm thanh video xem lại

Sau khi MP4 hoàn tất, worker chạy `normalize-recording.sh`: giữ nguyên video,
chuẩn hóa âm thanh theo timestamp bằng `aresample=async=1000:first_pts=0`, mã hóa
lại AAC và đưa metadata lên đầu file (`faststart`). Chỉ remux với `-c copy` không
sửa được khoảng trống giữa timestamp AAC và số mẫu âm thanh, có thể khiến tiếng
đi trước hình khi trình duyệt phát lại.

Triển khai bằng `docker compose build srs && docker compose up -d --force-recreate srs`
khi không có phiên live đang phát, vì thao tác này khởi động lại SRS. Worker xử lý
cả bản ghi cũ đã có dấu `.fixed`; dấu hoàn tất mới là `.avsync-v1`.
File gốc chỉ được thay bằng thao tác rename sau khi chuyển đổi thành công và kiểm
tra nguồn không thay đổi. Thời gian sửa file được giữ để không gia hạn lưu trữ 7 ngày.
Video đã lưu trên Google Drive cần được xử lý và tải lên lại riêng.

Kiểm thử: `python -m unittest discover -s tests -v` (cần FFmpeg, ffprobe và sh).

Để tự tải replay lên Google Drive, thêm `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, `GOOGLE_DRIVE_REFRESH_TOKEN` (và tùy chọn `GOOGLE_DRIVE_FOLDER_ID`) vào GitHub Secrets của repo backend. Quyền chia sẻ Anyone with link được dùng để phát video trên trang.

## GitHub Secrets (repo ngix và backend)

| Secret | Giá trị |
|---|---|
| `SERVER_HOST` | IP VPS |
| `SERVER_USER` | user SSH |
| `SERVER_SSH_KEY` | private key SSH |
| `SERVER_PORT` | (tuỳ chọn) mặc định 22 |
| `DOCKER_HUB_USER` | username Docker Hub (chỉ cần ở BE, FE) |
| `DOCKER_HUB_TOKEN` | access token Docker Hub (chỉ cần ở BE, FE) |
| `GOOGLE_DRIVE_CLIENT_ID` | OAuth client ID (BE) |
| `GOOGLE_DRIVE_CLIENT_SECRET` | OAuth client secret (BE) |
| `GOOGLE_DRIVE_REFRESH_TOKEN` | Refresh token có quyền ghi Drive (BE) |
| `GOOGLE_DRIVE_FOLDER_ID` | (tuỳ chọn) thư mục đích (BE) |

## Chạy local

```bash
docker compose -f docker-compose.dev.yml up -d   # chỉ SRS, BE chạy trên máy
```
