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

# 4. Tạo chứng chỉ HTTPS cho SRS (self-signed, hoặc thay bằng Let's Encrypt)
mkdir -p certs
openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
  -keyout certs/server.key -out certs/server.crt -subj "/CN=traiga"

# 5. Chạy (cần đã push BE & FE ít nhất 1 lần để có image trên Docker Hub)
docker compose pull && docker compose up -d
```

Mở firewall: `80/tcp`, `1935/tcp`, `8088/tcp`, `8000/udp`.

## GitHub Secrets (thêm vào **cả 3 repo**)

| Secret | Giá trị |
|---|---|
| `SERVER_HOST` | IP VPS |
| `SERVER_USER` | user SSH |
| `SERVER_SSH_KEY` | private key SSH |
| `SERVER_PORT` | (tuỳ chọn) mặc định 22 |
| `DOCKER_HUB_USER` | username Docker Hub (chỉ cần ở BE, FE) |
| `DOCKER_HUB_TOKEN` | access token Docker Hub (chỉ cần ở BE, FE) |

## Chạy local

```bash
docker compose -f docker-compose.dev.yml up -d   # chỉ SRS, BE chạy trên máy
```