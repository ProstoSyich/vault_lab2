const TOKEN_KEY = "vault_token";
const state = { token: localStorage.getItem(TOKEN_KEY) };

const el = (id) => document.getElementById(id);

function showError(message) {
  el("error-box").textContent = message || "";
}

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  let data = {};
  try {
    data = await response.json();
  } catch (_) {
    // тело может быть пустым
  }

  if (!response.ok) {
    throw new Error(data.detail || `Ошибка ${response.status}`);
  }
  return data;
}

async function gql(query, variables = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch("/graphql", {
    method: "POST",
    headers,
    body: JSON.stringify({ query, variables }),
  });

  let data;
  try {
    data = await response.json();
  } catch (_) {
    throw new Error(`Ошибка ${response.status}`);
  }

  if (!response.ok) {
    throw new Error(`Ошибка ${response.status}`);
  }
  if (data.errors && data.errors.length) {
    throw new Error(data.errors.map((error) => error.message).join("\n"));
  }
  return data.data;
}

function renderClients(clients) {
  const body = el("clients-body");
  body.replaceChildren();
  el("clients-empty").classList.toggle("hidden", clients.length > 0);

  for (const client of clients) {
    const row = document.createElement("tr");
    const values = [
      client.clientId,
      client.name,
      client.isConfidential ? "конфиденциальный" : "публичный",
      client.createdAt ? new Date(client.createdAt).toLocaleString() : "—",
    ];

    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    }
    body.appendChild(row);
  }
}

async function loadClients() {
  const data = await gql(`
    query {
      clients {
        id
        clientId
        name
        isConfidential
        redirectUris
        createdAt
      }
    }
  `);
  renderClients(data.clients);
}

async function loadDashboard() {
  const data = await gql(`query { me { email isAdmin } }`);

  el("current-email").textContent = data.me.email;
  el("admin-badge").classList.toggle("hidden", !data.me.isAdmin);
  el("login-view").classList.add("hidden");
  el("dashboard-view").classList.remove("hidden");

  if (!data.me.isAdmin) {
    showError("Для управления клиентами нужны права администратора.");
    renderClients([]);
    return;
  }

  await loadClients();
}

function showLogin() {
  el("dashboard-view").classList.add("hidden");
  el("login-view").classList.remove("hidden");
  el("clients-body").replaceChildren();
}

function logout() {
  state.token = null;
  localStorage.removeItem(TOKEN_KEY);
  showError("");
  showLogin();
}

el("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");

  try {
    const data = await api("/auth/login", {
      email: el("login-email").value.trim(),
      password: el("login-password").value,
    });
    state.token = data.access_token;
    localStorage.setItem(TOKEN_KEY, data.access_token);
    el("login-password").value = "";
    await loadDashboard();
  } catch (error) {
    showError(error.message);
  }
});

el("logout-button").addEventListener("click", logout);

el("create-client-button").addEventListener("click", () => {
  el("create-client-form").classList.toggle("hidden");
});

el("cancel-client-button").addEventListener("click", () => {
  el("create-client-form").classList.add("hidden");
});

el("create-client-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");

  try {
    await gql(
      `mutation CreateClient($name: String!, $isConfidential: Boolean!) {
        createClient(name: $name, isConfidential: $isConfidential) {
          id
          clientId
          name
          isConfidential
          createdAt
        }
      }`,
      {
        name: el("client-name").value.trim(),
        isConfidential: el("client-confidential").checked,
      },
    );
    el("client-name").value = "";
    el("client-confidential").checked = false;
    el("create-client-form").classList.add("hidden");
    await loadClients();
  } catch (error) {
    showError(error.message);
  }
});

if (state.token) {
  loadDashboard().catch(() => logout());
} else {
  showLogin();
}
