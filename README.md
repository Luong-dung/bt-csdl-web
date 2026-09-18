# Cheat Sheet & Hướng dẫn quy trình dự án

### 1. Lần đầu tải dự án về máy mới (Chỉ làm 1 lần duy nhất)

**Bước 1: Tải mã nguồn về máy**
git clone <URL_REPO_GITHUB_CUA_BAN>
cd esports-tournament-web

**Bước 2: Cài đặt CSDL (XAMPP)**
- Mở XAMPP Control Panel -> Bấm Start **Apache** và **MySQL**.
- Mở trình duyệt vào `http://localhost/phpmyadmin/`.
- Tạo cơ sở dữ liệu mới đặt tên đúng là: `esports_tournament`.
- Chọn CSDL vừa tạo, bấm tab **Import**:
  - Chọn file `database/schema.sql` -> Bấm **Import**.
  - Chọn tiếp file `database/seed_data.sql` -> Bấm **Import**.
- Kiểm tra `http://127.0.0.1:8000/test-db`

**Bước 3: Thiết lập môi trường Python Backend**
cd backend
copy .env.example .env
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

**Bước 4: Kiểm tra chạy thử**
uvicorn main:app --reload
- Mở trình duyệt vào: `http://127.0.0.1:8000/docs` (thấy Swagger UI là xong setup).

---

### 2. Khởi động môi trường code (Hàng ngày)
- Mở XAMPP -> Start Apache & MySQL.
- Mở terminal tại thư mục backend:
  cd backend
  .\venv\Scripts\activate
  uvicorn main:app --reload

---

### 3. Đồng bộ code trước khi làm tính năng mới
git checkout main
git pull origin main
git checkout -b feature/<ten-tinh-nang>

---

### 4. Lưu và đẩy code lên sau khi hoàn thành
git add .
git commit -m "feat: mo ta ngan gon chuc nang vua code"
git push origin feature/<ten-tinh-nang>
- Vào GitHub bấm nút **Compare & pull request** để gửi yêu cầu gộp code vào `main`.

---

### 5. Cập nhật khi có thành viên khác thêm thư viện mới
- Nếu thấy có cập nhật ở file `requirements.txt` sau khi `git pull`:
  .\venv\Scripts\activate
  pip install -r requirements.txt
---
### 🔑 Tài khoản Test & Mật khẩu mặc định

Tất cả tài khoản trong dữ liệu mẫu (`seed_data.sql`) đều sử dụng mật khẩu chung:
- Mật khẩu: `123456`

Reset toàn bộ mật khẩu tài khoản test về `123456`, chạy câu lệnh sau trong tab SQL của phpMyAdmin:

```sql
UPDATE users 
SET password_hash = '$2b$12$K8K3t0mBvR6B8P7T5eQeSe0hZ6lZ7w5FzQxX8wQ7v1v4.Yk7wO8Gy';
```


  
