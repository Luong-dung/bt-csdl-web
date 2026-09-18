const API_AUTH = "http://127.0.0.1:8000/api/v1/auth";
const API_TEAM = "http://127.0.0.1:8000/api/v1/team";

let isRegister = false;

// 1. Chuyển đổi qua lại giữa Đăng nhập và Đăng ký
function toggleAuth() {
  isRegister = !isRegister;
  document.getElementById("auth-title").innerText = isRegister ? "Đăng Ký Tài Khoản" : "Đăng Nhập";
  document.getElementById("btn-auth-submit").innerText = isRegister ? "Tạo Tài Khoản" : "Đăng Nhập";
  document.getElementById("auth-email").classList.toggle("hidden", !isRegister);
  document.getElementById("auth-switch-link").innerText = isRegister 
    ? "Đã có tài khoản? Quay lại Đăng nhập" 
    : "Chưa có tài khoản? Đăng ký ngay";
}

// 2. Gửi yêu cầu Login / Register
async function submitAuth() {
  const username = document.getElementById("auth-username").value.trim();
  const password = document.getElementById("auth-password").value.trim();
  const email = document.getElementById("auth-email").value.trim();

  if (!username || !password || (isRegister && !email)) {
    return alert("Vui lòng điền đầy đủ thông tin!");
  }

  const endpoint = isRegister ? "/register" : "/login";
  const payload = isRegister ? { username, email, password } : { username, password };

  try {
    const res = await fetch(`${API_AUTH}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Thao tác thất bại");

    if (isRegister) {
      alert("Đăng ký thành công! Hãy đăng nhập lại.");
      toggleAuth();
    } else {
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("role", data.role);
      localStorage.setItem("username", data.username || username);
      renderState();
    }
  } catch (err) {
    alert("Lỗi: " + err.message);
  }
}

// 3. Xử lý tạo đội (Dành cho tài khoản Viewer)
async function createTeam() {
  const team_name = document.getElementById("t-name").value.trim();
  const tag = document.getElementById("t-tag").value.trim();
  const token = localStorage.getItem("token");

  if (!team_name || !tag) return alert("Vui lòng nhập đủ tên đội và tag!");

  try {
    const res = await fetch(`${API_TEAM}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ team_name, tag })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Tạo đội thất bại");

    alert("Tạo đội thành công! Chuyển sang khu vực Quản lý đội.");
    localStorage.setItem("role", "MANAGER");
    window.location.href = "team.html";
  } catch (err) {
    alert("Lỗi: " + err.message);
  }
}

// 4. Kiểm tra session để render giao diện
function renderState() {
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("role");
  const username = localStorage.getItem("username");

  const boxAuth = document.getElementById("box-auth");
  const boxViewer = document.getElementById("box-viewer");

  if (!token) {
    boxAuth.classList.remove("hidden");
    boxViewer.classList.add("hidden");
    return;
  }

  // Nếu là TEAM_MANAGER thì đá thẳng sang team.html
  if (role === "TEAM_MANAGER") {
    window.location.href = "team.html";
    return;
  }

  // Nếu là VIEWER thì mở giao diện tạo đội
  boxAuth.classList.add("hidden");
  boxViewer.classList.remove("hidden");
  document.getElementById("user-name").innerText = username || "Khán giả";
}

function logout() {
  localStorage.clear();
  renderState();
}

// Tự động kiểm tra khi vừa tải file
renderState();