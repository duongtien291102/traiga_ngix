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
- Push `traiga_ngix` → VPS `git pull` → restart cả stack

VPS không build gì, chỉ `docker pull` image → dùng được VPS cấu hình nhỏ.

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
docker compose pull && docker compose up -d
```

Mở firewall: `80/tcp`, `1935/tcp`, `8080/tcp`, `8088/tcp`, `1985/tcp`, `8000/udp`.

SRS giữ các file DVR trong volume Docker `traiga_recordings`. Backend Azure đọc file qua URL trong `SRS_HTTP_URL` (ví dụ `https://<DOMAIN>:8088`). Trong GitHub repo BE → Settings → Secrets and variables → Actions → Variables, đặt `SRS_HTTP_URL` bằng URL chứng chỉ đó. Không dùng IP nếu chứng chỉ được cấp cho domain.

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
