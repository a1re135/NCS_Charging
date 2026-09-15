"use strict";

const $ = (q, r = document) => r.querySelector(q);

const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c],
  );

const yuan = (c) => (Number(c || 0) / 100).toFixed(2);

const time = (s) =>
  s ? s.replace("T", " ").slice(0, 19) : "—";

const fmtDate = (d) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");

  return `${y}-${m}-${day}`;
};

const scanPath =
  location.pathname.match(/^\/charge\/([^/]+)\/?$/);

const S = {
  user: null,
  csrf: "",
  page: "dashboard",

  stations: [],
  orders: [],
  chargers: [],
  pricing: [],
  faults: [],

  agentMessages: [],
  agentBusy: false,

  lat: 39.9593,
  lng: 116.2981,
  location: "海淀区",

  timer: null,
  realtimeHistory: [],
  version: 0,
  scale: 60,

  scanNumber: scanPath
    ? decodeURIComponent(scanPath[1])
    : null,
};

const names = new Proxy(
  {
    idle: "空闲",
    reserved: "已预约",
    charging: "充电中",
    fault: "故障",
    offline: "离线",
    maintenance: "维修中",
    completed: "已结算",
    cancelled: "已取消",
    expired: "已过期",
    operating: "运营中",
    paused: "暂停运营",
    pending: "待处理",
    processing: "处理中",
    resolved: "已解决",
  },
  {
    get: (target, key) =>
      tr(target[key] ?? key),
  },
);


const paymentNames = {
  "待结算": "待结算",
  "已支付": "已支付",
  "待补缴": "待补缴",
  "部分支付": "部分支付",
  "支付失败": "支付失败",
  "无需支付": "无需支付",
};

const roleNames = {
  user: "普通用户",
  operator: "运营人员",
  technician: "运维人员",
  admin: "系统管理员",
};

const can = (permission) =>
  S.user?.role === "admin" ||
  (S.user?.permissions || []).includes(permission);

const paymentBadge = (status) =>
  `<span class="pay-badge ${esc(String(status || "").replaceAll(" ", "-"))}">
    <i class="dot"></i>
    ${esc(paymentNames[status] || status || "—")}
  </span>`;

const paths = {
  home: "M3 10 12 3l9 7v10H3z M9 20v-7h6v7",
  pin: "M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  bolt: "m14 2-9 12h7l-2 8 9-13h-7z",
  orders:
    "M6 3h12v18l-3-2-3 2-3-2-3 2z M9 8h6M9 12h6",
  wallet:
    "M3 6h17v14H3z M3 6V4l14-2v4 M15 11h6v5h-6z",
  user:
    "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3",
  chart: "M4 3v18h17 M8 16v-5 M13 16V6 M18 16v-8",
  grid:
    "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  logout: "M9 4H3v16h6 M9 12h12m-5-5 5 5-5 5",
  arrow: "M4 12h16m-6-6 6 6-6 6",
  leaf:
    "M20 3C5 2 1 13 7 18c5 5 15-1 13-15ZM5 21l10-12",
  help:
    "M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 3 M12 17h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  menu: "M3 6h18M3 12h18M3 18h18",
};

const ic = (n) =>
  `<svg class="ico"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.65"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true">
      <path d="${paths[n] || paths.grid}"/>
   </svg>`;

const badge = (s) =>
  `<span class="badge ${esc(s)}">
    <i
      class="dot"
      style="
        background:currentColor;
        width:5px;
        height:5px
      "
    ></i>
    ${esc(names[s] || s)}
  </span>`;

const av = (u = S.user) =>
  `<div class="avatar ${esc(u.avatar)}">
    ${esc(u.nickname.slice(0, 1))}
  </div>`;

const btn = (
  t,
  a,
  c = "secondary",
  data = "",
) =>
  `<button
      class="btn ${c}"
      data-action="${a}"
      ${data}
   >
      ${t}
   </button>`;

const pageBtn = (
  p,
  t,
  c = "secondary",
) =>
  `<button
      class="btn ${c}"
      data-page="${p}"
   >
      ${t}
   </button>`;

const empty = (t) =>
  `<div class="empty">${t}</div>`;

const field = (
  label,
  name,
  value = "",
  type = "text",
  extra = "",
) =>
  `<div class="field">
    <label for="f-${name}">
      ${label}
    </label>
    <input
      id="f-${name}"
      name="${name}"
      type="${type}"
      value="${esc(value)}"
      ${extra}
    >
  </div>`;

const opt = (
  v,
  t,
  s,
) =>
  `<option
      value="${esc(v)}"
      ${
        String(v) === String(s)
          ? "selected"
          : ""
      }
   >
      ${esc(t)}
   </option>`;

const table = (
  hs,
  rs,
) =>
  `<div class="table-wrap">
    <table>
      <thead>
        <tr>
          ${hs
            .map(
              (h) =>
                `<th>${h}</th>`,
            )
            .join("")}
        </tr>
      </thead>

      <tbody>
        ${
          rs.join("") ||
          `<tr>
             <td colspan="${hs.length}">
               ${empty(tr("暂无数据"))}
             </td>
           </tr>`
        }
      </tbody>
    </table>
  </div>`;

const line = (
  k,
  v,
) =>
  `<div class="receipt-line">
    <span>${k}</span>
    <b>${esc(v)}</b>
  </div>`;

function toast(t) {
  $("#toast").textContent = t;

  $("#toast").classList.add(
    "show",
  );

  clearTimeout(
    S.toastTimer,
  );

  S.toastTimer =
    setTimeout(
      () =>
        $("#toast")
          .classList
          .remove("show"),
      4000,
    );
}

async function api(
  path,
  method = "GET",
  data,
) {
  const r = await fetch(
    "/api" + path,
    {
      method,

      headers: {
        "Content-Type":
          "application/json",

        "X-CSRF-Token":
          S.csrf,

        "X-NCS-Language":
          NCSPreferences.state
            .language,
      },

      ...(data !== undefined
        ? {
            body:
              JSON.stringify(
                data,
              ),
          }
        : {}),
    },
  );

  let j;

  try {
    j = await r.json();
  } catch {
    throw Error(
      tr(
        "服务器响应异常，请检查 VS Code 终端",
      ),
    );
  }

  if (!r.ok) {
    const e = Error(
      j.error ||
        tr("请求失败"),
    );

    Object.assign(
      e,
      j,
      {
        status: r.status,
      },
    );

    throw e;
  }

  return j;
}

function modal(
  title,
  html,
) {
  $("#modal-content").innerHTML =
    trHtml`
      <div class="modal-head">
        <h2>${esc(title)}</h2>

        <button
          data-action="close"
          aria-label="关闭"
        >
          ×
        </button>
      </div>

      ${html}

      <div
        class="modal-error"
        role="alert"
      ></div>
    `;

  if (!$("#modal").open) {
    $("#modal").showModal();
  }
}

function error(e) {
  if (
    $("#modal").open &&
    $(".modal-error")
  ) {
    $(".modal-error")
      .textContent =
        e.message;
  } else {
    toast(e.message);
  }
}

function loginView(
  register = false,
) {
  S.registering = register;

  clearInterval(
    S.timer,
  );

  clearTimeout(
    S.toastTimer,
  );

  $("#toast")
    .classList
    .remove("show");

  S.user = null;

  $("#app").innerHTML =
    trHtml`
      <div class="login-screen">

        <div class="login-preferences">
          ${preferenceControls()}
        </div>

        <section class="login-art">

          <div class="brand">
            <img
              src="/static/logo.svg"
              alt=""
            >

            <div>
              <strong>NCS</strong>
              <small>
                SMART CHARGING
              </small>
            </div>
          </div>

          <h1>
            让每次出发，<br>
            都充满能量。
          </h1>

          <p>
            连接城市的绿色脉动，让充电成为生活中<br>
            轻松、美好的一部分。
          </p>

          <img
            src="/static/hero.svg"
            alt="两位同事在充电站旁协作的插画"
          >
        </section>

        <section class="login-form">

          <div class="eyebrow">
            A LITTLE ENERGY.
            A BETTER DAY.
          </div>

          <h2>
            ${
              register
                ? tr(
                    "开启绿色旅程",
                  )
                : tr(
                    "欢迎回来",
                  )
            }
          </h2>

          <p class="sub">
            ${
              S.scanNumber &&
              !register
                ? tr(
                    "登录后继续扫码充电",
                  )
                : register
                  ? tr(
                      "创建你的 NCS 账号",
                    )
                  : tr(
                      "登录 NCS，发现身边的美好与能量",
                    )
            }
          </p>

          <div class="login-tabs">
            <button
              data-action="login-tab"
              class="${
                register
                  ? ""
                  : "selected"
              }"
            >
              账号登录
            </button>

            <button
              data-action="register-tab"
              class="${
                register
                  ? "selected"
                  : ""
              }"
            >
              注册账号
            </button>
          </div>

          <form
            id="auth-form"
            data-register="${register}"
          >

            ${field(
              tr(
                "手机号 / 管理员账号",
              ),
              "phone",
              "",
              "text",
              tr(
                'required autocomplete="username" placeholder="请输入账号"',
              ),
            )}

            ${
              register
                ? field(
                    tr("昵称"),
                    "nickname",
                    "",
                    "text",
                    'required maxlength="24"',
                  )
                : ""
            }

            ${field(
              tr("密码"),
              "password",
              "",
              "password",
              trHtml`
                required
                autocomplete="${
                  register
                    ? "new-password"
                    : "current-password"
                }"
                minlength="8"
                maxlength="128"
                placeholder="至少 8 位密码"
              `,
            )}

            <div
              class="form-error"
              role="alert"
            ></div>

            <button
              class="btn"
              type="submit"
            >
              ${
                register
                  ? tr("创建账号")
                  : tr("登录")
              }

              ${ic("arrow")}
            </button>
          </form>

          <div class="demo-accounts">
            课程演示账号（点击填入）
            <br>

            <button
              data-action="demo-user"
            >
              用户：
              13800138000 /
              User123456
            </button>

            <br>

            <button
              data-action="demo-admin"
            >
              管理：
              admin /
              Admin123456
            </button>

            <br>

            <button
              data-action="demo-operator"
            >
              运营：
              operator /
              Operator123456
            </button>

            <br>

            <button
              data-action="demo-tech"
            >
              运维：
              tech /
              Tech123456
            </button>
          </div>

          <p class="footer-note">
            本地课程演示 ·
            模拟充值与充电 ·
            数据自动保存
          </p>

        </section>
      </div>
    `;
}

const userNav = [
  [
    "dashboard",
    "home",
    "总览",
  ],
  [
    "stations",
    "pin",
    "附近电站",
  ],
  [
    "charging",
    "bolt",
    "我的充电",
  ],
  [
    "orders",
    "orders",
    "我的订单",
  ],
  [
    "wallet",
    "wallet",
    "我的钱包",
  ],
  [
    "agent",
    "help",
    "AI 智能助手",
  ],
  [
    "profile",
    "user",
    "个人中心",
  ],
];

const roleNav = [
  ["dashboard", "home", "运营总览", null],
  ["stations", "pin", "电站管理", "station.view"],
  ["chargers", "bolt", "电桩管理", "charger.view"],
  ["realtime", "chart", "实时监控", "charger.view"],
  ["agent", "help", "AI 智能助手", null],
  ["pricing", "wallet", "价格管理", "pricing.manage"],
  ["faults", "help", "故障管理", "fault.manage"],
  ["users", "user", "用户管理", "user.manage"],
  ["orders", "orders", "订单管理", "order.view_all"],
  ["revenue", "chart", "营收统计", "analytics.view"],
  ["prediction", "chart", "负荷预测", "prediction.view"],
  ["roles", "grid", "角色与权限", "role.manage"],
  ["logs", "orders", "操作日志", "log.view"],
  ["settings", "grid", "偏好设置", null],
];

function currentNav() {
  if (S.user.role === "user") {
    return userNav;
  }

  return roleNav
    .filter(([, , , permission]) =>
      !permission || can(permission),
    )
    .map((item) => {
      const copy = [...item];

      if (S.user.role === "technician" && copy[0] === "dashboard") {
        copy[2] = "运维总览";
      }
      if (S.user.role === "technician" && copy[0] === "stations") {
        copy[2] = "电站运维";
      }
      if (S.user.role === "technician" && copy[0] === "chargers") {
        copy[2] = "设备运维";
      }

      return copy;
    });
}

function shell() {
  const nav = currentNav();
  const ops = S.user.role !== "user";

  $("#app").innerHTML =
    trHtml`
      <div class="shell">

        <aside class="sidebar">

          <div class="brand">
            <img
              src="/static/logo.svg"
              alt=""
            >

            <div>
              <strong>NCS</strong>
              <small>
                SMART CHARGING
              </small>
            </div>
          </div>

          <div class="nav-label">
            MY WORKSPACE
          </div>

          <nav class="nav">
            ${nav
              .map(
                ([id, i, t]) =>
                  `<button
                     data-page="${id}"
                     class="${
                       S.page === id
                         ? "active"
                         : ""
                     }"
                   >
                     ${ic(i)}
                     ${tr(t)}
                   </button>`,
              )
              .join("")}
          </nav>

          <div class="side-bottom">

            <div class="side-promo">

              <div class="leaf">
                ${ic("leaf")}
              </div>

              <h3>
                一点能量，一份美好
              </h3>

              <p>
                每一次绿色出行<br>
                都是给城市的温柔回应
              </p>
            </div>

            <div class="side-user">

              ${av()}

              <span>
                <b>
                  ${esc(
                    S.user.nickname,
                  )}
                </b>

                <small
                  style="
                    display:block;
                    margin-top:4px
                  "
                >
                  ${esc(
                    S.user.role_name ||
                      roleNames[S.user.role] ||
                      S.user.role,
                  )}
                </small>
              </span>

              <button
                data-action="logout"
                title="退出登录"
              >
                ${ic("logout")}
              </button>

            </div>
          </div>
        </aside>

        <main class="main">

          <header class="topbar">

            <button
              class="
                circle-btn
                mobile-menu
              "
              data-action="menu"
              aria-label="展开导航"
            >
              ${ic("menu")}
            </button>

            <div>
              <h1>
                ${
                  tr(
                    nav.find(
                      (x) =>
                        x[0] ===
                        S.page,
                    )?.[2],
                  ) ||
                  (
                    S.page ===
                    "scan"
                      ? tr(
                          "扫码充电",
                        )
                      : tr(
                          "电站详情",
                        )
                  )
                }
              </h1>

              <p class="sub">
                ${
                  ops
                    ? tr(
                        "从每一度电，看见城市的绿色未来。",
                      )
                    : tr(
                        "新的一天，为你的下一站充满能量。",
                      )
                }
              </p>
            </div>

            <div class="top-right">

              ${preferenceControls()}

              ${
                ops
                  ? `<span class="role-chip">
                       ${ic("grid")}
                       ${esc(
                         S.user.role_name ||
                           roleNames[S.user.role] ||
                           S.user.role,
                       )}
                     </span>`
                  : ""
              }

              <span class="date-pill">
                ${new Date()
                  .toLocaleDateString(
                    NCSPreferences
                      .state
                      .language ===
                      "en"
                      ? "en-GB"
                      : "zh-CN",
                    {
                      year:
                        "numeric",
                      month:
                        "long",
                      day:
                        "numeric",
                    },
                  )}
              </span>

              <button
                class="circle-btn"
                data-action="help"
                aria-label="使用帮助"
              >
                ${ic("help")}
              </button>

              ${av()}

            </div>
          </header>

          <div id="content">
          </div>

          <p class="footer-note">
            NCS SMART CHARGING ·
            课程演示版 ·
            充电按 ${S.scale}
            倍时间模拟
          </p>

        </main>
      </div>
    `;
}

function chart(
  ds,
  key = "energy",
) {
  const vs =
      ds.map(
        (d) =>
          d[key] || 0,
      ),

    max =
      Math.max(
        ...vs,
        1,
      ),

    pts =
      vs.map(
        (v, i) => [
          10 +
            (
              i *
              580
            ) /
              Math.max(
                vs.length -
                  1,
                1,
              ),

          130 -
            (
              v /
              max
            ) *
              112,
        ],
      ),

    ln =
      pts
        .map(
          (p) =>
            p.join(","),
        )
        .join(" ");

  return trHtml`
    <svg
      class="chart"
      viewBox="0 0 600 150"
      preserveAspectRatio="none"
      role="img"
      aria-label="最近七天${
        key === "energy"
          ? tr("电量")
          : tr("实收金额")
      }趋势"
    >

      <defs>
        <linearGradient
          id="fill"
          x1="0"
          y1="0"
          x2="0"
          y2="1"
        >
          <stop
            stop-color="#ad9bdf"
            stop-opacity=".19"
          />

          <stop
            offset="1"
            stop-color="#ad9bdf"
            stop-opacity="0"
          />
        </linearGradient>
      </defs>

      ${[
        20,
        57,
        94,
        131,
      ]
        .map(
          (y) =>
            `<path
               d="M0 ${y}H600"
               stroke="#f1eef7"
               stroke-dasharray="4 5"
             />`,
        )
        .join("")}

      <polygon
        points="
          10,145
          ${ln}
          590,145
        "
        fill="url(#fill)"
      />

      <polyline
        points="${ln}"
        stroke="#ad9bdf"
        stroke-width="3"
        fill="none"
        stroke-linejoin="round"
        vector-effect="
          non-scaling-stroke
        "
      />

      ${pts
        .map(
          ([x, y], i) =>
            `<circle
               cx="${x}"
               cy="${y}"
               r="3.5"
               fill="white"
               stroke="#ad9bdf"
               stroke-width="2"
             >
               <title>
                 ${ds[i].day}：
                 ${
                   key ===
                   "cents"
                     ? yuan(
                         vs[i],
                       ) +
                       tr(" 元")
                     : vs[
                         i
                       ].toFixed(
                         2,
                       ) +
                       " kWh"
                 }
               </title>
             </circle>`,
        )
        .join("")}
    </svg>

    <div class="chart-labels">
      ${ds
        .map(
          (d) =>
            `<span>
               ${d.day.slice(
                 5,
               )}
             </span>`,
        )
        .join("")}
    </div>
  `;
}

function metric(
  i,
  label,
  value,
  unit = "",
) {
  return `
    <div class="card metric">
      <div class="metric-icon">
        ${ic(i)}
      </div>

      <div>
        <small>
          ${label}
        </small>

        <strong>
          ${value}
          <em>${unit}</em>
        </strong>
      </div>
    </div>
  `;
}

function pushRealtimeHistory(data) {
  if (!Array.isArray(S.realtimeHistory)) {
    S.realtimeHistory = [];
  }

  const point = {
    time: new Date(),

    idle:
      Number(
        data.status_counts?.idle || 0,
      ),

    busy:
      Number(
        data.summary?.busy || 0,
      ),

    abnormal:
      Number(
        data.summary?.abnormal || 0,
      ),
  };

  S.realtimeHistory.push(point);

  // 5 seconds per point × 60 points = about 5 minutes
  if (
    S.realtimeHistory.length >
    60
  ) {
    S.realtimeHistory.splice(
      0,
      S.realtimeHistory.length -
        60,
    );
  }
}

function liveBars(
  items,
  valueKey,
  labelKey,
  suffix = "",
) {
  const max = Math.max(
    ...items.map(
      (x) =>
        Number(
          x[valueKey] || 0,
        ),
    ),
    1,
  );

  return `
    <div class="live-bar-list">
      ${items
        .map(
          (x) => {
            const value =
              Number(
                x[valueKey] || 0,
              );

            const width =
              Math.max(
                1,
                value /
                  max *
                  100,
              );

            return `
              <div class="live-bar-row">

                <div class="live-bar-label">
                  <span>
                    ${esc(
                      x[labelKey],
                    )}
                  </span>

                  <b>
                    ${value}${suffix}
                  </b>
                </div>

                <div class="live-bar-track">
                  <i
                    style="
                      width:${width}%
                    "
                  ></i>
                </div>

              </div>
            `;
          },
        )
        .join("")}
    </div>
  `;
}

function healthDonut(data) {
  const total =
    Number(
      data.summary?.total || 0,
    );

  const abnormal =
    Number(
      data.summary?.abnormal || 0,
    );

  const healthy =
    Math.max(
      0,
      total - abnormal,
    );

  const percentage =
    total
      ? (
          healthy /
          total *
          100
        ).toFixed(1)
      : "0.0";

  return `
    <div class="health-wrap">

      <div
        class="health-donut"
        style="
          background:
            conic-gradient(
              var(--green)
              0
              ${percentage}%,

              var(--purple-soft)
              ${percentage}%
              100%
            )
        "
      >

        <div class="health-donut-inner">

          <strong>
            ${percentage}%
          </strong>

          <small>
            ${tr("健康率")}
          </small>

        </div>

      </div>

      <div class="health-stats">

        <div>
          <span>
            ${tr("正常设备")}
          </span>

          <b>
            ${healthy}
            ${tr("台")}
          </b>
        </div>

        <div>
          <span>
            ${tr("异常设备")}
          </span>

          <b>
            ${abnormal}
            ${tr("台")}
          </b>
        </div>

        <div>
          <span>
            ${tr("设备总数")}
          </span>

          <b>
            ${total}
            ${tr("台")}
          </b>
        </div>

      </div>

    </div>
  `;
}

function realtimeTrendChart() {
  const history =
    S.realtimeHistory || [];

  if (
    history.length <
    2
  ) {
    return `
      <div class="realtime-waiting">
        ${tr(
          "正在采集实时数据，请稍候…",
        )}
      </div>
    `;
  }

  const width = 720;
  const height = 220;

  const left = 25;
  const right = 15;
  const top = 15;
  const bottom = 35;

  const chartWidth =
    width -
    left -
    right;

  const chartHeight =
    height -
    top -
    bottom;

  const values =
    history.flatMap(
      (x) => [
        x.idle,
        x.busy,
        x.abnormal,
      ],
    );

  const max =
    Math.max(
      ...values,
      1,
    );

  const x =
    (index) =>
      left +
      (
        index *
        chartWidth
      ) /
        Math.max(
          history.length -
            1,
          1,
        );

  const y =
    (value) =>
      top +
      chartHeight -
      (
        Number(value || 0) /
        max
      ) *
        chartHeight;

  const points =
    (key) =>
      history
        .map(
          (item, index) =>
            `${x(index)},${y(
              item[key],
            )}`,
        )
        .join(" ");

  const first =
    history[0];

  const middle =
    history[
      Math.floor(
        history.length / 2,
      )
    ];

  const last =
    history[
      history.length - 1
    ];

  const timeLabel =
    (item) =>
      item.time
        .toLocaleTimeString(
          [],
          {
            hour:
              "2-digit",
            minute:
              "2-digit",
            second:
              "2-digit",
          },
        );

  return `
    <div class="realtime-chart-wrap">

      <div class="realtime-chart-legend">

        <span class="trend-legend idle">
          <i></i>
          ${tr("空闲")}
          <b>
            ${last.idle}
          </b>
        </span>

        <span class="trend-legend busy">
          <i></i>
          ${tr("使用中")}
          <b>
            ${last.busy}
          </b>
        </span>

        <span class="trend-legend abnormal">
          <i></i>
          ${tr("异常")}
          <b>
            ${last.abnormal}
          </b>
        </span>

      </div>

      <svg
        class="realtime-line-chart"
        viewBox="
          0 0
          ${width}
          ${height}
        "
        preserveAspectRatio="none"
        role="img"
        aria-label="${tr(
          "最近五分钟设备实时趋势",
        )}"
      >

        ${[
          0,
          0.25,
          0.5,
          0.75,
          1,
        ]
          .map(
            (ratio) => {
              const gy =
                top +
                chartHeight *
                  ratio;

              return `
                <line
                  x1="${left}"
                  x2="${width - right}"
                  y1="${gy}"
                  y2="${gy}"
                  class="realtime-grid-line"
                />
              `;
            },
          )
          .join("")}

        <polyline
          points="${points(
            "idle",
          )}"
          class="
            realtime-series
            realtime-series-idle
          "
        />

        <polyline
          points="${points(
            "busy",
          )}"
          class="
            realtime-series
            realtime-series-busy
          "
        />

        <polyline
          points="${points(
            "abnormal",
          )}"
          class="
            realtime-series
            realtime-series-abnormal
          "
        />

      </svg>

      <div class="realtime-time-axis">

        <span>
          ${timeLabel(
            first,
          )}
        </span>

        <span>
          ${timeLabel(
            middle,
          )}
        </span>

        <span>
          ${timeLabel(
            last,
          )}
        </span>

      </div>

    </div>
  `;
}

function realtimeContent(d) {
  const statusData = [
    {
      label: tr("空闲"),
      value:
        d.status_counts.idle ||
        0,
    },
    {
      label: tr("充电中"),
      value:
        d.status_counts.charging ||
        0,
    },
    {
      label: tr("已预约"),
      value:
        d.status_counts.reserved ||
        0,
    },
    {
      label: tr("故障"),
      value:
        d.status_counts.fault ||
        0,
    },
    {
      label: tr("离线"),
      value:
        d.status_counts.offline ||
        0,
    },
    {
      label: tr("维修中"),
      value:
        d.status_counts.maintenance ||
        0,
    },
  ];

  return trHtml`
    <div class="stack">

      <section class="card">

        <div class="section-head">

          <div>
            <h2>
              实时运营监控
            </h2>

            <p class="sub">
              页面每 5 秒自动刷新，
              无需手动重新加载。
            </p>
          </div>

          <span class="role-chip">
            LIVE ·
            ${time(
              d.generated_at,
            ).slice(11)}
          </span>

        </div>

        <div class="metric-grid">

          ${metric(
            "bolt",
            tr("设备总数"),
            d.summary.total,
            tr("台"),
          )}

          ${metric(
            "grid",
            tr("空闲设备"),
            d.summary.idle,
            tr("台"),
          )}

          ${metric(
            "bolt",
            tr("使用中"),
            d.summary.busy,
            tr("台"),
          )}

          ${metric(
            "help",
            tr("异常设备"),
            d.summary.abnormal,
            tr("台"),
          )}

        </div>

      </section>


      <div class="realtime-grid">

        <section class="card">

          <div class="section-head">

            <h2>
              电桩实时状态分布
            </h2>

            <small>
              当前设备状态
            </small>

          </div>

          ${liveBars(
            statusData,
            "value",
            "label",
            tr(" 台"),
          )}

        </section>


        <section class="card">

          <div class="section-head">

            <h2>
              电站实时利用率
            </h2>

            <small>
              充电中 + 已预约
            </small>

          </div>

          ${liveBars(
            d.stations,
            "utilization_pct",
            "name",
            "%",
          )}

        </section>

      </div>

        <div class="realtime-extra-grid">

        <section class="card">

          <div class="section-head">

            <div>
              <h2>
                ${tr("系统设备健康率")}
              </h2>

              <p class="sub">
                ${tr(
                  "正常设备占全部设备的比例",
                )}
              </p>
            </div>

            <span class="role-chip">
              HEALTH
            </span>

          </div>

          ${healthDonut(d)}

        </section>


        <section class="card">

          <div class="section-head">

            <div>

              <h2>
                ${tr(
                  "最近 5 分钟设备实时趋势",
                )}
              </h2>

              <p class="sub">
                ${tr(
                  "每 5 秒采集一次当前设备状态",
                )}
              </p>

            </div>

            <span class="live-indicator">
              <i></i>
              LIVE
            </span>

          </div>

          ${realtimeTrendChart()}

        </section>

      </div>


      <section class="card">

        <div class="section-head">

          <h2>
            各电站异常设备
          </h2>

          <small>
            故障 + 离线 + 维修
          </small>

        </div>

        ${liveBars(
          d.stations,
          "abnormal",
          "name",
          tr(" 台"),
        )}

      </section>

    </div>
  `;
}


async function realtimePage() {
  const data =
    await api(
      "/realtime",
    );

  // Start a fresh 5-minute history
  // whenever the monitoring page is opened.
  S.realtimeHistory = [];

  pushRealtimeHistory(
    data,
  );

  return `
    <div id="realtime-root">
      ${realtimeContent(
        data,
      )}
    </div>
  `;
}

function stationCard(s) {
  return trHtml`
    <article class="card station-card">

      <div class="station-top">

        <div class="station-symbol">
          ${ic("bolt")}
        </div>

        ${badge(
          s.operating_status,
        )}
      </div>

      <h3>
        ${esc(s.name)}
      </h3>

      <div class="station-meta">

        ${esc(s.address)}
        <br>

        ${ic("pin")}

        距离
        ${s.distance.toFixed(1)}
        km ·

        ${s.fast_count || 0}
        快充 /

        ${s.slow_count || 0}
        慢充 ·

        ${s.free || 0}
        空闲

        <br>

        营业时间：
        ${esc(
          s.business_hours,
        )}
      </div>

      <div class="station-footer">

        <div class="price">
          ¥
          ${yuan(
            s.current_price_cents,
          )}

          <small>
            / 度（当前）
          </small>
        </div>

        ${btn(
          can("station.manage")
            ? tr("管理电站")
            : S.user.role === "technician"
              ? tr("进入运维")
              : tr("查看电站"),

          "station",

          "secondary small",

          `data-id="${s.id}"`,
        )}
      </div>

    </article>
  `;
}

function agentSuggestions() {
  if (
    S.user.role ===
    "user"
  ) {
    return [
      "附近哪里有空闲快充？",
      "我现在有充电订单吗？",
      "我的余额是多少？",
      "我有欠费吗？",
      "我最近一次充电花了多少钱？",
      "为什么我的充电桩无法启动？",
    ];
  }

  if (
    S.user.role ===
    "technician"
  ) {
    return [
      "现在有多少故障设备？",
      "现在设备情况怎么样？",
      "哪些设备故障次数最多？",
    ];
  }

  return [
    "今天哪个充电站订单最多？",
    "最近7天收入怎么样？",
    "现在有多少故障设备？",
    "现在设备情况怎么样？",
    "哪些设备故障次数最多？",
    "生成最近7天运营报告",
  ];
}

function agentWelcome() {
  if (
    S.user.role ===
    "user"
  ) {
    return (
      "你好，我是 NCS 智能充电助手。" +
      "我可以结合平台实时数据，帮你查询附近充电站、" +
      "订单、余额、欠费和充电问题。"
    );
  }

  if (
    S.user.role ===
    "technician"
  ) {
    return (
      "你好，我是 NCS 智能运维助手。" +
      "我可以查询实时设备状态、故障情况和故障历史，" +
      "帮助你快速了解设备运行情况。"
    );
  }

  return (
    "你好，我是 NCS AI 运营助手。" +
    "我可以结合订单、营收、设备和故障数据，" +
    "回答运营问题并生成简单运营报告。"
  );
}

function agentMessageHtml(
  message,
) {
  const role =
    message.role ===
    "user"
      ? "user"
      : "assistant";

  return `
    <div
      class="
        agent-message
        ${role}
      "
    >

      ${
        role ===
        "assistant"
          ? `
              <div class="agent-avatar">
                AI
              </div>
            `
          : ""
      }

      <div class="agent-bubble">

        <div class="agent-message-role">
          ${
            role ===
            "user"
              ? esc(
                  S.user.nickname,
                )
              : "NCS AI"
          }
        </div>

        <div class="agent-message-text">
          ${esc(
            message.text,
          ).replace(
            /\n/g,
            "<br>",
          )}
        </div>

        ${
          message.intent
            ? `
                <small
                  class="agent-intent"
                >
                  ${
                    esc(
                      message.intent,
                    )
                  }
                </small>
              `
            : ""
        }

      </div>

      ${
        role ===
        "user"
          ? `
              <div class="agent-user-avatar">
                ${esc(
                  S.user.nickname
                    .slice(
                      0,
                      1,
                    ),
                )}
              </div>
            `
          : ""
      }

    </div>
  `;
}

function renderAgentMessages() {
  const target =
    $("#agent-messages");

  if (!target) {
    return;
  }

  const welcome = {
    role: "assistant",
    text: agentWelcome(),
  };

  const messages = [
    welcome,
    ...S.agentMessages,
  ];

  target.innerHTML =
    messages
      .map(
        agentMessageHtml,
      )
      .join("");

  target.scrollTop =
    target.scrollHeight;
}

function showAgentThinking() {
  const target =
    $("#agent-messages");

  if (!target) {
    return;
  }

  const thinking =
    document.createElement(
      "div",
    );

  thinking.id =
    "agent-thinking";

  thinking.className =
    "agent-message assistant";

  thinking.innerHTML = `
    <div class="agent-avatar">
      AI
    </div>

    <div
      class="
        agent-bubble
        agent-thinking
      "
    >

      <div class="agent-message-role">
        NCS AI
      </div>

      <div class="thinking-dots">
        <i></i>
        <i></i>
        <i></i>
      </div>

    </div>
  `;

  target.appendChild(
    thinking,
  );

  target.scrollTop =
    target.scrollHeight;
}


function hideAgentThinking() {
  $("#agent-thinking")
    ?.remove();
}

async function agentPage() {
  const suggestions =
    agentSuggestions();

  return trHtml`
    <div class="agent-layout">

      <section
        class="
          card
          agent-main
        "
      >

        <div class="agent-header">

          <div>

            <div class="eyebrow">
              NCS AI AGENT
            </div>

            <h2>
              AI 智能助手
            </h2>

            <p class="sub">
              基于实时业务数据进行查询与分析
            </p>

          </div>

          <span
            class="
              agent-online
            "
          >
            <i></i>
            在线
          </span>

        </div>


        <div
          id="agent-messages"
          class="agent-messages"
        >
        </div>


        <form
          id="agent-form"
          class="agent-input-area"
        >

          <textarea
            id="agent-input"
            name="message"
            placeholder="请输入你想咨询的问题…"
            maxlength="500"
            required
          ></textarea>

          <button
            class="btn"
            type="submit"
          >
            发送
            ${ic("arrow")}
          </button>

        </form>

      </section>


      <aside class="stack">

        <section class="card">

          <div class="section-head">

            <div>

              <h3>
                推荐问题
              </h3>

              <p class="sub">
                点击即可向 Agent 提问
              </p>

            </div>

            ${ic("help")}

          </div>

          <div class="agent-suggestions">

            ${suggestions
              .map(
                (question) =>
                  `
                    <button
                      class="
                        agent-suggestion
                      "
                      data-action=
                        "agent-suggest"
                      data-question=
                        "${esc(
                          question,
                        )}"
                    >
                      ${esc(
                        question,
                      )}
                    </button>
                  `,
              )
              .join("")}

          </div>

        </section>


        <section
          class="
            card
            agent-capability
          "
        >

          <h3>
            当前能力
          </h3>

          <div
            class="
              agent-capability-list
            "
          >

            <div>
              ${ic("pin")}
              <span>
                电站与空闲设备查询
              </span>
            </div>

            <div>
              ${ic("orders")}
              <span>
                订单与充电记录查询
              </span>
            </div>

            <div>
              ${ic("wallet")}
              <span>
                余额、欠费与价格信息
              </span>
            </div>

            <div>
              ${ic("bolt")}
              <span>
                设备状态与故障分析
              </span>
            </div>

            ${
              S.user.role !==
              "user"
                ? `
                    <div>
                      ${ic(
                        "chart",
                      )}
                      <span>
                        运营数据分析与报告
                      </span>
                    </div>
                  `
                : ""
            }

          </div>

        </section>


        <section class="note">
          Agent 会根据当前登录角色访问允许的数据。
          AI 助手不会绕过系统 RBAC 权限。
        </section>

      </aside>

    </div>
  `;
}

async function dashboard() {
  const [
    d,
    s,
    o,
  ] =
    await Promise.all([
      api("/dashboard"),

      api(
        `/stations?lat=${S.lat}&lng=${S.lng}`,
      ),

      api("/orders"),
    ]);

  S.stations = s;
  S.orders = o;

  if (S.user.role === "technician") {
    const m = d.maintenance_stats || d.counts || {};

    return trHtml`
      <div class="stack">
        <section class="hero">
          <div class="hero-text">
            <div class="eyebrow">MAINTENANCE CONTROL</div>
            <h2>让每一台设备，<br>都保持在最佳状态。</h2>
            <p>
              统一查看电站健康度、设备状态与异常情况，<br>
              直接从电站进入设备运维。
            </p>
            ${pageBtn(
              "stations",
              tr("进入电站运维") + " " + ic("arrow"),
              "",
            )}
          </div>
          <div class="hero-badge">
            ${m.total || 0}
            <br>
            <small>设备</small>
          </div>
        </section>

        <div class="metric-grid">
          ${metric("pin", tr("管理电站"), d.stations, tr("座"))}
          ${metric("bolt", tr("设备总数"), m.total || 0, tr("台"))}
          ${metric("grid", tr("故障设备"), m.fault || 0, tr("台"))}
          ${metric(
            "bolt",
            tr("运行中"),
            (m.charging || 0) + (m.reserved || 0),
            tr("台"),
          )}
        </div>

        <section class="card">
          <div class="section-head">
            <h2>运维工作台</h2>
            <small>授权操作</small>
          </div>
          <div class="actions" style="margin-top:18px">
            ${pageBtn("stations", tr("查看全部电站"), "secondary")}
            ${pageBtn("chargers", tr("查看全部设备"), "secondary")}
          </div>
        </section>
      </div>
    `;
  }

  const a =
      can("analytics.view"),

    total =
      Object.values(
        d.counts,
      ).reduce(
        (x, y) =>
          x + y,
        0,
      ),

    free =
      d.counts.idle || 0,

    sum =
      d.days.reduce(
        (x, y) =>
          x +
          (
            a
              ? y.cents
              : y.energy
          ),
        0,
      );

  return trHtml`
    <div class="dashboard-grid">

      <div class="stack">

        <section class="hero">

          <div class="hero-text">

            <div class="eyebrow">
              ${
                a
                  ? "A GREENER CITY STARTS HERE"
                  : "GOOD ENERGY, EVERY DAY"
              }
            </div>

            <h2>
              ${
                a
                  ? tr(
                      "让绿色能量，<br>流向城市每一站。",
                    )
                  : trHtml`
                      你好，
                      ${esc(
                        S.user
                          .nickname,
                      )}
                      <br>
                      今天也要满电出发。
                    `
              }
            </h2>

            <p>
              ${
                a
                  ? tr(
                      "在这里掌握电站运营动态，<br>让每一份能量，都有更好的去处。",
                    )
                  : tr(
                      "附近的充电站已为你准备就绪，<br>给爱车充电，也给生活一点留白。",
                    )
              }
            </p>

            ${pageBtn(
              a
                ? "revenue"
                : "stations",

              (
                a
                  ? tr(
                      "查看运营数据",
                    )
                  : tr(
                      "寻找充电站",
                    )
              ) +
                " " +
                ic("arrow"),

              "",
            )}

          </div>

          <img
            src="/static/hero.svg"
            alt="绿色充电设施"
          >

        </section>

        ${
          !a &&
          d.active.length
            ? trHtml`
                <div class="live">

                  <div>
                    <strong>
                      ${badge(
                        d.active[0]
                          .status,
                      )}
                      你有一个未完成订单
                    </strong>

                    <small>
                      ${esc(
                        d.active[0]
                          .station_name,
                      )}
                    </small>
                  </div>

                  ${pageBtn(
                    "charging",
                    tr(
                      "去处理",
                    ),
                    "small",
                  )}
                </div>
              `
            : ""
        }

        <div class="metric-grid">

          ${metric(
            "bolt",

            a
              ? tr(
                  "累计服务电量",
                )
              : tr(
                  "累计充电量",
                ),

            d.totals.energy.toFixed(
              1,
            ),

            "kWh",
          )}

          ${metric(
            "orders",

            a
              ? tr(
                  "已结算订单",
                )
              : tr(
                  "已完成订单",
                ),

            d.totals.orders,

            tr("笔"),
          )}

          ${metric(
            a
              ? "pin"
              : "wallet",

            a
              ? tr(
                  "接入电站",
                )
              : tr(
                  "累计充电消费",
                ),

            a
              ? d.stations
              : yuan(
                  d.totals
                    .paid_cents,
                ),

            a
              ? tr("座")
              : tr("元"),
          )}

        </div>

        <section class="card">

          <div class="section-head">

            <h2>
              ${
                a
                  ? tr(
                      "营收趋势",
                    )
                  : tr(
                      "我的充电趋势",
                    )
              }
            </h2>

            <span class="legend">
              <i class="dot"></i>
              最近 7 天 ·
              ${
                a
                  ? tr("实收")
                  : tr("电量")
              }
            </span>
          </div>

          <div class="chart-summary">
            ${
              a
                ? "¥ " +
                  yuan(sum)
                : sum.toFixed(
                    1,
                  )
            }

            <small>
              ${
                a
                  ? tr(
                      "实收金额",
                    )
                  : tr(
                      "kWh / 最近 7 天",
                    )
              }
            </small>
          </div>

          ${chart(
            d.days,
            a
              ? "cents"
              : "energy",
          )}

        </section>

        <section>

          <div class="section-head">

            <h2>
              ${
                a
                  ? tr(
                      "电站概览",
                    )
                  : tr(
                      "附近的充电站",
                    )
              }
            </h2>

            <button
              class="text-btn"
              data-page="stations"
            >
              查看全部 →
            </button>
          </div>

          <div
            class="
              station-grid
              home-stations
            "
          >
            ${
              s
                .slice(
                  0,
                  2,
                )
                .map(
                  stationCard,
                )
                .join("") ||
              empty(
                tr(
                  "暂无电站",
                ),
              )
            }
          </div>

        </section>

      </div>

      <aside
        class="
          stack
          right-stack
        "
      >

        <section class="card wallet">

          <h3>
            ${
              a
                ? tr(
                    "累计实收营收",
                  )
                : tr(
                    "我的钱包",
                  )
            }

            <span style="float:right">
              ${ic("wallet")}
            </span>
          </h3>

          <div class="balance">
            ¥
            ${yuan(
              a
                ? d.totals
                    .paid_cents
                : S.user
                    .balance_cents,
            )}
          </div>

          <small>
            ${
              a
                ? trHtml`
                    注册用户
                    ${d.users}
                    ·
                    未解决故障
                    ${d.open_faults}
                  `
                : tr(
                    "可用余额 · 模拟账户",
                  )
            }
          </small>

          <div class="wallet-bottom">

            <span style="font-size:10px">
              NCS
              ${
                a
                  ? "BUSINESS"
                  : "MEMBER"
              }
            </span>

            ${
              a
                ? pageBtn(
                    "revenue",
                    tr(
                      "营收详情 ↗",
                    ),
                    "white small",
                  )
                : btn(
                    tr(
                      "＋ 充值",
                    ),
                    "recharge",
                    "white small",
                  )
            }
          </div>
        </section>

        <section class="card">

          <div class="section-head">

            <h3>
              电桩实时状态
            </h3>

            ${ic("grid")}
          </div>

          <div
            class="donut"
            style="
              background:
                conic-gradient(
                  #ac9ae0
                  0
                  ${
                    total
                      ? (
                          free /
                          total
                        ) *
                        100
                      : 0
                  }%,
                  #e7d1ea
                  ${
                    total
                      ? (
                          free /
                          total
                        ) *
                        100
                      : 0
                  }%
                  100%
                )
            "
          >
            <span>
              ${free}

              <small>
                空闲充电桩 /
                ${total}
              </small>
            </span>
          </div>

          ${[
            "idle",
            "charging",
            "reserved",
            "fault",
            "offline",
            "maintenance",
          ]
            .map(
              (k) =>
                trHtml`
                  <div class="status-row">
                    <i class="dot"></i>

                    ${names[k]}

                    <b>
                      ${
                        d.counts[
                          k
                        ] ||
                        0
                      }
                      个
                    </b>
                  </div>
                `,
            )
            .join("")}

        </section>

        <section class="card">

          <div class="section-head">

            <h3>
              最近订单
            </h3>

            <button
              class="text-btn"
              data-page="orders"
            >
              全部
            </button>

          </div>

          ${
            o
              .slice(
                0,
                3,
              )
              .map(
                (x) =>
                  `<div class="activity-item">

                    <div class="avatar">
                      ${ic("bolt")}
                    </div>

                    <div>
                      <p>
                        ${esc(
                          x.station_name,
                        )}
                      </p>

                      <small>
                        ${time(
                          x.created_at,
                        ).slice(
                          5,
                          16,
                        )}
                        ·
                        ${names[
                          x.status
                        ]}
                      </small>
                    </div>
                  </div>`,
              )
              .join("") ||
            empty(
              tr(
                "还没有订单",
              ),
            )
          }

        </section>
      </aside>
    </div>
  `;
}

async function stationsPage() {
  S.stationFilter = {
    status: "",
    sort: "distance",
  };

  await loadStations();

  return trHtml`
    <div class="toolbar">

      <input
        id="station-search"
        placeholder="搜索电站名称或地址"
        aria-label="搜索电站"
      >

      <select
        id="region"
        aria-label="当前位置"
      >
        ${[
          "海淀区",
          "东城区",
          "朝阳区",
          "丰台区",
          "石景山区",
          "自定义位置",
        ]
          .map(
            (v) =>
              opt(
                v,
                tr(v),
                S.location,
              ),
          )
          .join("")}
      </select>

      <select
        id="station-status"
        aria-label="充电状态筛选"
      >
        <option value="">
          ${tr("全部状态")}
        </option>

        ${opt(
          "idle",
          tr("有空闲桩"),
        )}

        ${opt(
          "fault",
          tr("有故障桩"),
        )}

        ${opt(
          "maintenance",
          tr("有维修中桩"),
        )}

        ${opt(
          "offline",
          tr("有离线桩"),
        )}
      </select>

      <select
        id="station-sort"
        aria-label="排序方式"
      >
        <option value="distance">
          ${tr(
            "按距离排序",
          )}
        </option>

        <option value="usage">
          ${tr(
            "充电次数最多",
          )}
        </option>
      </select>

      ${btn(
        tr(
          "使用我的位置",
        ),
        "locate",
      )}

      ${
        can("station.manage")
          ? btn(
              tr(
                "＋ 添加电站",
              ),
              "edit-station",
              "",
            )
          : ""
      }

    </div>

    <p
      class="sub"
      style="margin-bottom:20px"
    >
      ${ic("pin")}

      ${tr("当前位置")}：
      ${esc(
        tr(S.location),
      )}

      （
      ${S.lat.toFixed(4)},
      ${S.lng.toFixed(4)}
      ）
    </p>

    <div
      class="station-grid"
      id="station-list"
    >
      ${
        S.stations
          .map(
            stationCard,
          )
          .join("") ||
        empty(
          tr(
            "暂无充电站数据",
          ),
        )
      }
    </div>
  `;
}

async function loadStations() {
  const version =
    S.version;

  const params =
    new URLSearchParams({
      lat: S.lat,
      lng: S.lng,
    });

  const filter =
    S.stationFilter ||
    {};

  if (filter.status) {
    params.set(
      "status",
      filter.status,
    );
  }

  if (filter.sort) {
    params.set(
      "sort",
      filter.sort,
    );
  }

  const stations =
    await api(
      "/stations?" +
        params.toString(),
    );

  if (
    version !== S.version
  ) {
    return;
  }

  S.stations =
    stations;

  const list =
    $("#station-list");

  if (list) {
    list.innerHTML =
      stations
        .map(
          stationCard,
        )
        .join("") ||
      empty(
        tr(
          "没有匹配的电站",
        ),
      );
  }
}

function stationChargersTable(
  chargers,
) {
  const canEdit =
    can("charger.manage");

  return table(
    [
      tr("充电桩"),
      tr("类型 / 功率"),
      tr("状态"),
      tr("累计次数"),
      tr("操作"),
    ],

    chargers.map(
      (c) => {
        let actions;

        if (
          canEdit &&
          ![
            "charging",
            "reserved",
          ].includes(c.status)
        ) {
          actions =
            btn(
              tr("二维码"),
              "qr",
              "secondary small",
              `data-id="${c.id}"`,
            ) +
            btn(
              c.status === "idle"
                ? tr("故障")
                : tr("恢复"),
              "charger-action",
              "secondary small",
              `data-id="${c.id}" data-op="${
                c.status === "idle"
                  ? "fault"
                  : "restore"
              }"`,
            ) +
            btn(
              tr("重启"),
              "charger-action",
              "secondary small",
              `data-id="${c.id}" data-op="restart"`,
            );
        } else if (
          S.user.role === "user" &&
          c.status === "idle" &&
          S.detail?.operating_status === "operating"
        ) {
          actions =
            btn(
              tr("预约"),
              "reserve",
              "secondary small",
              `data-id="${c.id}"`,
            ) +
            btn(
              tr("开始充电"),
              "start-charge",
              "small",
              `data-id="${c.id}"`,
            );
        } else {
          actions =
            `<small>${tr("仅查看")}</small>`;
        }

        return `<tr>
          <td><b>${esc(c.number)}</b></td>
          <td>
            ${c.kind === "fast" ? tr("快充") : tr("慢充")}
            / ${c.power} kW
          </td>
          <td>${badge(c.status)}</td>
          <td>${c.total_count} ${tr("次")}</td>
          <td>${actions}</td>
        </tr>`;
      },
    ),
  );
}

function renderStationChargers() {
  const f =
    S.chargerFilter ||
    {};

  let chargers =
    (
      S.detailChargers ||
      []
    ).filter(
      (c) =>
        (
          !f.status ||
          c.status ===
            f.status
        ) &&
        (
          !f.kind ||
          c.kind ===
            f.kind
        ),
    );

  chargers = [
    ...chargers,
  ];

  if (
    f.sort === "usage"
  ) {
    chargers.sort(
      (a, b) =>
        b.total_count -
        a.total_count,
    );
  } else {
    chargers.sort(
      (a, b) =>
        a.number.localeCompare(
          b.number,
        ),
    );
  }

  const target =
    $("#charger-list");

  if (target) {
    target.innerHTML =
      stationChargersTable(
        chargers,
      );
  }
}

async function stationDetail(
  id,
) {
  const data =
      await api(
        "/stations/" + id,
      ),

    s =
      data.station,

    cs =
      data.chargers,

    pricing =
      data.pricing;

  S.detail = s;

  S.detailChargers =
    cs;

  S.chargerFilter = {
    status: "",
    kind: "",
    sort: "number",
  };

  const a =
    can("station.manage");

  const info =
    `<div class="info-grid">

      <div>
        ${line(
          tr(
            "所属城市",
          ),
          s.city,
        )}

        ${line(
          tr(
            "营业时间",
          ),
          s.business_hours,
        )}

        ${line(
          tr(
            "联系电话",
          ),
          s.contact_phone,
        )}
      </div>

      <div>
        ${line(
          tr(
            "运营状态",
          ),
          names[
            s.operating_status
          ] ||
            s.operating_status,
        )}

        ${line(
          tr(
            "停车说明",
          ),
          s.parking_info,
        )}

        ${line(
          tr(
            "当前价格",
          ),
          "¥ " +
            yuan(
              s.current_price_cents,
            ) +
            tr(
              " / 度",
            ),
        )}
      </div>

    </div>`;

  const tariff =
    table(
      [
        tr("时段"),
        tr("电费"),
        tr("服务费"),
        tr("合计"),
      ],

      pricing.map(
        (p) =>
          `<tr>

            <td>
              ${p.start_time}
              -
              ${p.end_time}
            </td>

            <td>
              ¥
              ${yuan(
                p.electricity_fee_cents,
              )}
            </td>

            <td>
              ¥
              ${yuan(
                p.service_fee_cents,
              )}
            </td>

            <td>
              <b>
                ¥
                ${yuan(
                  p.price_cents,
                )}
              </b>
            </td>
          </tr>`,
      ),
    );

  return trHtml`
    <div class="section-head">

      <div>
        <h2>
          ${esc(s.name)}
        </h2>

        <p class="sub">
          ${esc(s.address)}
          ·
          ${badge(
            s.operating_status,
          )}
        </p>
      </div>

      ${pageBtn(
        "stations",
        tr(
          "返回列表",
        ),
      )}

    </div>

    <div
      class="card"
      style="margin-bottom:20px"
    >

      <div class="section-head">

        <h3>
          ${tr(
            "电站信息",
          )}
        </h3>

        <div class="actions">

          ${btn(
            tr(
              "路线导航",
            ),
            "map",
            "secondary",
            `data-id="${s.id}"`,
          )}

          ${
            a
              ? btn(
                  tr(
                    "编辑电站",
                  ),
                  "edit-station",
                  "secondary",
                  `data-id="${s.id}"`,
                ) +
                btn(
                  tr(
                    "删除",
                  ),
                  "delete-station",
                  "danger",
                  `data-id="${s.id}"`,
                )
              : ""
          }

        </div>
      </div>

      ${info}

      <h3
        style="
          margin:
            22px 0 12px
        "
      >
        ${tr(
          "分时收费标准",
        )}
      </h3>

      ${tariff}

    </div>

    <div class="card">

      <div class="section-head">

        <h3>
          ${tr(
            "选择你的充电桩",
          )}
        </h3>

        <small>
          ${
            cs.filter(
              (c) =>
                c.status ===
                "idle",
            ).length
          }

          ${tr(
            "个空闲",
          )}
        </small>

      </div>

      <div class="toolbar">

        <select
          id="charger-filter-status"
        >
          <option value="">
            ${tr(
              "全部状态",
            )}
          </option>

          ${[
            "idle",
            "reserved",
            "charging",
            "fault",
            "maintenance",
            "offline",
          ]
            .map(
              (k) =>
                opt(
                  k,
                  names[k],
                ),
            )
            .join("")}
        </select>

        <select
          id="charger-filter-kind"
        >
          <option value="">
            ${tr(
              "全部类型",
            )}
          </option>

          ${opt(
            "fast",
            tr("快充"),
          )}

          ${opt(
            "slow",
            tr("慢充"),
          )}
        </select>

        <select
          id="charger-filter-sort"
        >
          <option value="number">
            ${tr(
              "按编号排序",
            )}
          </option>

          <option value="usage">
            ${tr(
              "充电次数最多",
            )}
          </option>
        </select>

      </div>

      <div id="charger-list">
        ${stationChargersTable(
          cs,
        )}
      </div>

      <div class="note">
        ${tr(
          "预约后保留 15 分钟。收费按照开始充电时所在的分时时段锁定电费和服务费，订单结束后仍保留该价格快照。",
        )}
      </div>

    </div>
  `;
}

async function scanPage(
  number,
) {
  const c =
    await api(
      "/chargers/by-number/" +
        encodeURIComponent(
          number,
        ),
    );

  S.scanCharger = c;

  return trHtml`
    <div class="page-grid">

      <div class="card">

        <div class="section-head">

          <h2>
            已识别充电桩
          </h2>

          ${badge(c.status)}

        </div>

        <div class="charge-display">

          ${ic("bolt")}

          <div
            class="energy"
            style="font-size:32px"
          >
            ${esc(c.number)}
          </div>

          <p class="muted">
            ${esc(
              c.station_name,
            )}
          </p>
        </div>

        ${[
          [
            tr("电站地址"),
            c.address,
          ],
          [
            tr("所属城市"),
            c.city,
          ],
          [
            tr("营业时间"),
            c.business_hours,
          ],
          [
            tr("充电类型"),
            c.kind ===
            "fast"
              ? tr(
                  "快充",
                )
              : tr(
                  "慢充",
                ),
          ],
          [
            tr("额定功率"),
            c.power +
              " kW",
          ],
          [
            tr("设备状态"),
            names[c.status] ||
              c.status,
          ],
        ]
          .map(
            (x) =>
              line(...x),
          )
          .join("")}

        <div
          class="actions"
          style="margin-top:22px"
        >
          ${
            S.user.role ===
              "user" &&
            c.status ===
              "idle" &&
            c.operating_status ===
              "operating"
              ? btn(
                  tr(
                    "开始充电",
                  ),
                  "start-charge",
                  "",
                  `data-id="${c.id}"`,
                )
              : tr(
                  '<span class="note">当前设备暂不能开始充电</span>',
                )
          }

          ${btn(
            tr(
              "查看电站",
            ),
            "station",
            "secondary",
            `data-id="${c.station_id}"`,
          )}

        </div>
      </div>

      <div class="card">

        <h3>
          扫码充电说明
        </h3>

        <div class="note">
          二维码绑定唯一充电桩编号。
          系统会先检查电站运营状态和设备状态，
          只有空闲设备才能创建充电订单。
        </div>

        <p class="sub">
          停车说明：
          ${esc(
            c.parking_info,
          )}
        </p>

      </div>

    </div>
  `;
}

function ordersTable(os) {
  return table(
    [
      tr("订单号"),

      ...(
        can("order.view_all")
          ? [
              tr("用户"),
            ]
          : []
      ),

      tr("电站 / 电桩"),
      tr("状态"),
      tr("支付状态"),
      tr("电量"),
      tr("金额"),
      tr("创建时间"),
      tr("操作"),
    ],

    os.map(
      (o) =>
        `<tr>

          <td>
            <b>
              #
              ${String(
                o.id,
              ).padStart(
                5,
                "0",
              )}
            </b>
          </td>

          ${
            can("order.view_all")
              ? `<td>
                   ${esc(
                     o.nickname,
                   )}
                 </td>`
              : ""
          }

          <td>
            ${esc(
              o.station_name,
            )}
            <br>
            <small>
              ${esc(
                o.charger_number,
              )}
            </small>
          </td>

          <td>
            ${badge(o.status)}
          </td>

          <td>
            ${paymentBadge(
              o.payment_status,
            )}
          </td>

          <td>
            ${Number(
              o.energy,
            ).toFixed(2)}
            kWh
          </td>

          <td>
            ¥
            ${yuan(
              o.amount_cents,
            )}

            ${
              o.debt_cents
                ? trHtml`
                    <br>

                    <small
                      style="
                        color:#c67588
                      "
                    >
                      欠费 ¥
                      ${yuan(
                        o.debt_cents,
                      )}
                    </small>
                  `
                : ""
            }
          </td>

          <td>
            ${time(
              o.created_at,
            ).slice(
              0,
              16,
            )}
          </td>

          <td>
            ${btn(
              tr("详情"),
              "receipt",
              "secondary small",
              `data-id="${o.id}"`,
            )}
          </td>

        </tr>`,
    ),
  );
}

async function ordersPage() {
  S.orderFrom = "";
  S.orderTo = "";

  await loadOrders();

  return trHtml`
    <div class="toolbar">

      <input
        id="order-search"
        placeholder="搜索订单号、电站或用户"
        aria-label="搜索订单"
      >

      <select
        id="order-status"
        aria-label="筛选状态"
      >
        <option value="">
          ${tr(
            "全部状态",
          )}
        </option>

        ${[
          "reserved",
          "charging",
          "completed",
          "cancelled",
          "expired",
        ]
          .map(
            (k) =>
              opt(
                k,
                names[k],
              ),
          )
          .join("")}
      </select>

      <input
        type="date"
        id="order-from"
        title="${tr(
          "开始日期",
        )}"
      >

      <span class="muted">
        ${tr("至")}
      </span>

      <input
        type="date"
        id="order-to"
        title="${tr(
          "结束日期",
        )}"
      >

      ${btn(
        tr("今天"),
        "order-range",
        "secondary small",
        'data-days="1"',
      )}

      ${btn(
        tr("近 7 天"),
        "order-range",
        "secondary small",
        'data-days="7"',
      )}

      ${btn(
        tr("近 30 天"),
        "order-range",
        "secondary small",
        'data-days="30"',
      )}

      ${btn(
        tr("全部"),
        "order-range",
        "secondary small",
        'data-days="0"',
      )}

      ${
        can("order.export")
          ? trHtml`
              <a
                class="btn secondary"
                id="order-export"
                href="/api/admin/export?lang=${NCSPreferences.state.language}"
              >
                导出 CSV
              </a>
            `
          : ""
      }

    </div>

    <p
      class="sub"
      id="order-filter-info"
      style="
        margin:
          -8px
          0
          20px
      "
    >
      ${tr(
        "按订单创建日期筛选",
      )}
    </p>

    <div
      class="card"
      id="orders-table"
    >
      ${ordersTable(
        S.orders,
      )}
    </div>
  `;
}

async function loadOrders() {
  const version =
    S.version;

  const params =
    new URLSearchParams();

  if (S.orderFrom) {
    params.set(
      "date_from",
      S.orderFrom,
    );
  }

  if (S.orderTo) {
    params.set(
      "date_to",
      S.orderTo,
    );
  }

  const orders =
    await api(
      "/orders?" +
        params.toString(),
    );

  if (
    version !==
    S.version
  ) {
    return;
  }

  S.orders = orders;

  if (
    $("#orders-table")
  ) {
    filterOrders();
  }

  const exportButton =
    $("#order-export");

  if (exportButton) {
    const exportParams =
      new URLSearchParams(
        params,
      );

    exportParams.set(
      "lang",
      NCSPreferences
        .state
        .language,
    );

    exportButton.href =
      "/api/admin/export?" +
      exportParams.toString();
  }

  const info =
    $("#order-filter-info");

  if (info) {
    info.textContent =
      S.orderFrom ||
      S.orderTo
        ? `${tr("日期")}：${
            S.orderFrom ||
            "…"
          } ${tr("至")} ${
            S.orderTo ||
            "…"
          } · ${
            orders.length
          } ${tr("条")}`
        : `${tr(
            "全部日期",
          )} · ${
            orders.length
          } ${tr("条")}`;
  }
}

async function chargingPage() {
  const d =
      await api(
        "/dashboard",
      ),

    o =
      d.active[0];

  if (!o) {
    return `
      <div class="card">

        ${empty(
          tr(
            "当前没有未完成订单<br>选一个附近电站，为爱车补充能量。",
          ),
        )}

        <div
          style="
            text-align:center
          "
        >
          ${pageBtn(
            "stations",
            tr(
              "寻找充电站 ",
            ) +
              ic(
                "arrow",
              ),
            "",
          )}
        </div>
      </div>
    `;
  }

  S.liveId =
    o.id;

  return trHtml`
    <div class="page-grid">

      <div class="card">

        <div class="section-head">

          <h2>
            订单 #${o.id}
          </h2>

          ${badge(
            o.status,
          )}
        </div>

        <div class="charge-display">

          ${ic("bolt")}

          <div
            class="energy"
            id="live-energy"
          >
            ${Number(
              o.energy,
            ).toFixed(3)}
          </div>

          <p class="muted">
            kWh ·
            ${
              o.status ===
              "charging"
                ? tr(
                    "正在为你的下一程蓄能",
                  )
                : tr(
                    "充电桩已为你保留",
                  )
            }
          </p>
        </div>

        <div class="receipt-grid">

          <div>
            <small>
              当前费用
            </small>

            <b
              id="live-amount"
            >
              ¥
              ${yuan(
                o.amount_cents,
              )}
            </b>
          </div>

          <div>
            <small>
              模拟充电时长
            </small>

            <b
              id="live-time"
            >
              ${Math.floor(
                o.simulated_seconds /
                  60,
              )}
              分钟
            </b>
          </div>
        </div>

        <div class="actions">

          ${
            o.status ===
            "reserved"
              ? btn(
                  tr(
                    "开始充电",
                  ),
                  "order-start",
                  "",
                  `data-id="${o.id}"`,
                ) +
                btn(
                  tr(
                    "取消预约",
                  ),
                  "order-cancel",
                  "danger",
                  `data-id="${o.id}"`,
                )
              : btn(
                  tr(
                    "结束充电并结算",
                  ),
                  "order-finish",
                  "",
                  `data-id="${o.id}"`,
                )
          }
        </div>

        <div class="note">
          ${
            o.status ===
            "reserved"
              ? tr(
                  "预约到期时间：",
                ) +
                time(
                  o.expires_at,
                )
              : trHtml`
                  模拟速度
                  ${o.time_scale}×
                  ·
                  本次价格快照：
                  电费 ¥
                  ${yuan(
                    o.electricity_fee_cents,
                  )}
                  +
                  服务费 ¥
                  ${yuan(
                    o.service_fee_cents,
                  )}
                  /
                  度。
                `
          }
        </div>

      </div>

      <div class="stack">

        <div class="card">

          <h3>
            充电信息
          </h3>

          ${[
            [
              tr(
                "电站",
              ),
              o.station_name,
            ],
            [
              tr(
                "电桩",
              ),
              o.charger_number,
            ],
            [
              tr(
                "功率",
              ),
              o.power +
                " kW",
            ],
            [
              tr(
                "电费",
              ),
              "¥ " +
                yuan(
                  o.electricity_fee_cents,
                ) +
                tr(
                  " / 度",
                ),
            ],
            [
              tr(
                "服务费",
              ),
              "¥ " +
                yuan(
                  o.service_fee_cents,
                ) +
                tr(
                  " / 度",
                ),
            ],
            [
              tr(
                "合计单价",
              ),
              "¥ " +
                yuan(
                  o.price_cents,
                ) +
                tr(
                  " / 度",
                ),
            ],
            [
              tr(
                "开始时间",
              ),
              time(
                o.started_at,
              ),
            ],
          ]
            .map(
              (x) =>
                line(...x),
            )
            .join("")}

        </div>

        <div class="card wallet">

          <h3>
            钱包余额
          </h3>

          <div class="balance">
            ¥
            ${yuan(
              S.user
                .balance_cents,
            )}
          </div>

          ${btn(
            tr(
              "模拟充值",
            ),
            "recharge",
            "white small",
          )}

        </div>

      </div>
    </div>
  `;
}

async function receipt(id) {
  const o =
    await api(
      `/orders/${id}/receipt`,
    );

  modal(
    tr(
      "订单详情 · #",
    ) + id,

    trHtml`
      ${badge(o.status)}

      <div class="payment-highlight">
        ${paymentBadge(
          o.payment_status,
        )}

        <span>
          ${
            o.payment_status ===
            "已支付"
              ? tr("余额自动扣款成功")
              : o.payment_status ===
                  "待补缴"
                ? tr("余额不足，待充值补缴")
                : tr("结算状态已记录")
          }
        </span>
      </div>

      <div class="receipt-grid">

        <div>
          <small>
            充电电量
          </small>

          <b>
            ${Number(
              o.energy,
            ).toFixed(3)}
            kWh
          </b>
        </div>

        <div>
          <small>
            订单金额
          </small>

          <b>
            ¥
            ${yuan(
              o.amount_cents,
            )}
          </b>
        </div>

      </div>

      ${[
        [
          tr(
            "电站",
          ),
          o.station_name,
        ],
        [
          tr(
            "电桩",
          ),
          o.charger_number,
        ],
        [
          tr(
            "电费",
          ),
          "¥ " +
            yuan(
              o.electricity_fee_cents,
            ) +
            tr(
              " / 度",
            ),
        ],
        [
          tr(
            "服务费",
          ),
          "¥ " +
            yuan(
              o.service_fee_cents,
            ) +
            tr(
              " / 度",
            ),
        ],
        [
          tr(
            "计费单价",
          ),
          "¥ " +
            yuan(
              o.price_cents,
            ) +
            tr(
              " / 度",
            ),
        ],
        [
          tr(
            "开始时间",
          ),
          time(
            o.started_at,
          ),
        ],
        [
          tr(
            "结束时间",
          ),
          time(
            o.ended_at,
          ),
        ],
        [
          tr(
            "已支付",
          ),
          "¥ " +
            yuan(
              o.paid_cents,
            ),
        ],
        [
          tr(
            "欠费",
          ),
          "¥ " +
            yuan(
              o.debt_cents,
            ),
        ],
      ]
        .map(
          (x) =>
            line(...x),
        )
        .join("")}

      <div
        class="actions"
        style="margin-top:23px"
      >

        ${btn(
          tr(
            "打印小票",
          ),
          "print",
        )}

        ${
          S.user.role ===
            "user" &&
          o.debt_cents
            ? btn(
                tr(
                  "补缴欠费",
                ),
                "order-pay",
                "",
                `data-id="${id}"`,
              )
            : ""
        }

        ${
          S.user.role ===
            "user" &&
          [
            "reserved",
            "charging",
          ].includes(
            o.status,
          )
            ? pageBtn(
                "charging",
                tr(
                  "去处理",
                ),
                "",
              )
            : ""
        }

      </div>
    `,
  );
}

async function walletPage() {
  const [
    ls,
    d,
  ] =
    await Promise.all([
      api("/wallet"),
      api(
        "/dashboard",
      ),
    ]);

  return trHtml`
    <div class="page-grid">

      <section class="card">

        <div class="section-head">

          <h2>
            资金明细
          </h2>

          <small>
            最近 100 笔
          </small>

        </div>

        ${table(
          [
            tr("类型"),
            tr("金额"),
            tr("时间"),
          ],

          ls.map(
            (l) =>
              trHtml`
                <tr>

                  <td>
                    ${esc(
                      tr(
                        l.kind,
                      ),
                    )}
                  </td>

                  <td>
                    ${
                      l.amount_cents >
                      0
                        ? "+"
                        : ""
                    }

                    ${yuan(
                      l.amount_cents,
                    )}
                    元
                  </td>

                  <td>
                    ${time(
                      l.created_at,
                    )}
                  </td>

                </tr>
              `,
          ),
        )}

      </section>

      <div class="stack">

        <section class="card wallet">

          <h3>
            可用余额
          </h3>

          <div class="balance">
            ¥
            ${yuan(
              S.user
                .balance_cents,
            )}
          </div>

          ${btn(
            tr(
              "＋ 充值",
            ),
            "recharge",
            "white small",
          )}

        </section>

        <div class="card">

          <h3>
            待补缴金额
          </h3>

          <div
            class="chart-summary"
            style="margin-top:20px"
          >
            ¥
            ${yuan(
              d.totals
                .debt_cents,
            )}
          </div>

          ${pageBtn(
            "orders",
            tr(
              "查看欠费订单",
            ),
          )}

        </div>

      </div>
    </div>
  `;
}

function profilePage() {
  return trHtml`
    ${preferencesCard()}

    <div class="page-grid">

      <div class="card">

        <h2
          style="margin-bottom:25px"
        >
          个人资料
        </h2>

        <form id="profile-form">

          <div class="theme-choices">

            ${[
              "lavender",
              "pink",
              "blue",
              "mint",
            ]
              .map(
                (c) =>
                  `<button
                     type="button"
                     class="
                       theme-choice
                       ${
                         c ===
                         S.user
                           .avatar
                           ? "selected"
                           : ""
                       }
                     "
                     data-action="avatar"
                     data-color="${c}"
                   >
                     ${av({
                       ...S.user,
                       avatar:
                         c,
                     })}
                   </button>`,
              )
              .join("")}

          </div>

          <input
            type="hidden"
            name="avatar"
            value="${S.user.avatar}"
          >

          ${field(
            tr(
              "昵称",
            ),
            "nickname",
            S.user.nickname,
            "text",
            'required maxlength="24"',
          )}

          ${field(
            tr(
              "登录账号",
            ),
            "phone",
            S.user.phone,
            "text",
            "disabled",
          )}

          <button
            class="btn"
            type="submit"
          >
            保存资料
          </button>

        </form>
      </div>

      <div class="card">

        <h2
          style="margin-bottom:25px"
        >
          修改密码
        </h2>

        <form id="password-form">

          ${field(
            tr(
              "原密码",
            ),
            "old_password",
            "",
            "password",
            'required autocomplete="current-password"',
          )}

          ${field(
            tr(
              "新密码",
            ),
            "new_password",
            "",
            "password",
            'required minlength="8" maxlength="128" autocomplete="new-password"',
          )}

          <button
            class="btn secondary"
            type="submit"
          >
            更新密码
          </button>

        </form>

      </div>
    </div>
  `;
}

function chargersTable(cs) {
  const canEdit =
    can("charger.manage");

  return table(
    [
      tr("编号"),
      tr("所属电站"),
      tr("类型 / 功率"),
      tr("状态"),
      tr("充电次数"),
      tr("操作"),
    ],

    cs.map(
      (c) => {
        let actions =
          `<small>${tr("仅查看")}</small>`;

        if (
          canEdit &&
          ![
            "charging",
            "reserved",
          ].includes(c.status)
        ) {
          actions =
            btn(
              tr("二维码"),
              "qr",
              "secondary small",
              `data-id="${c.id}"`,
            ) +
            btn(
              tr("编辑"),
              "edit-charger",
              "secondary small",
              `data-id="${c.id}"`,
            ) +
            btn(
              c.status === "idle"
                ? tr("故障")
                : tr("恢复"),
              "charger-action",
              "secondary small",
              `data-id="${c.id}" data-op="${
                c.status === "idle"
                  ? "fault"
                  : "restore"
              }"`,
            ) +
            btn(
              tr("离线"),
              "charger-action",
              "secondary small",
              `data-id="${c.id}" data-op="offline"`,
            ) +
            btn(
              tr("维修"),
              "charger-action",
              "secondary small",
              `data-id="${c.id}" data-op="maintenance"`,
            ) +
            btn(
              tr("重启"),
              "charger-action",
              "secondary small",
              `data-id="${c.id}" data-op="restart"`,
            ) +
            btn(
              tr("删除"),
              "charger-action",
              "danger small",
              `data-id="${c.id}" data-op="delete"`,
            );
        } else if (
          [
            "charging",
            "reserved",
          ].includes(c.status)
        ) {
          actions =
            `<small>${tr("订单处理中")}</small>`;
        }

        return `<tr>
          <td><b>${esc(c.number)}</b></td>
          <td>${esc(c.station_name)}</td>
          <td>
            ${c.kind === "fast" ? tr("快充") : tr("慢充")}
            / ${c.power} kW
          </td>
          <td>${badge(c.status)}</td>
          <td>${c.total_count}</td>
          <td>${actions}</td>
        </tr>`;
      },
    ),
  );
}

async function chargersPage() {
  [
    S.chargers,
    S.stations,
  ] =
    await Promise.all([
      api(
        "/admin/chargers",
      ),

      api(
        "/stations",
      ),
    ]);

  return trHtml`
    <div class="toolbar">

      <input
        id="charger-search"
        placeholder="搜索电桩编号或站名"
        aria-label="搜索电桩"
      >

      <select
        id="charger-station"
      >
        <option value="">
          ${tr(
            "全部电站",
          )}
        </option>

        ${S.stations
          .map(
            (s) =>
              opt(
                s.id,
                s.name,
              ),
          )
          .join("")}
      </select>

      <select
        id="charger-kind"
      >
        <option value="">
          ${tr(
            "全部类型",
          )}
        </option>

        ${opt(
          "fast",
          tr("快充"),
        )}

        ${opt(
          "slow",
          tr("慢充"),
        )}
      </select>

      <select
        id="charger-status"
        aria-label="状态筛选"
      >
        <option value="">
          ${tr(
            "全部状态",
          )}
        </option>

        ${[
          "idle",
          "reserved",
          "charging",
          "fault",
          "offline",
          "maintenance",
        ]
          .map(
            (k) =>
              opt(
                k,
                names[k],
              ),
          )
          .join("")}
      </select>

      <select
        id="charger-sort"
      >
        <option value="number_asc">
          ${tr(
            "按编号排序",
          )}
        </option>

        <option value="count_desc">
          ${tr(
            "充电次数高到低",
          )}
        </option>

        <option value="count_asc">
          ${tr(
            "充电次数低到高",
          )}
        </option>
      </select>

      ${
        can("charger.manage")
          ? btn(
              tr(
                "＋ 添加电桩",
              ),
              "edit-charger",
              "",
            )
          : ""
      }

    </div>

    <div
      class="card"
      id="chargers-table"
    >
      ${chargersTable(
        sortedChargers(),
      )}
    </div>
  `;
}

async function pricingPage() {
  S.stations =
    await api(
      "/stations",
    );

  const sid =
    S.pricingStation ||
    S.stations[0]?.id;

  if (!sid) {
    return `
      <div class="card">
        ${empty(
          tr(
            "请先添加电站",
          ),
        )}
      </div>
    `;
  }

  S.pricingStation =
    Number(sid);

  S.pricing =
    await api(
      "/admin/pricing?station_id=" +
        sid,
    );

  return trHtml`
    <div class="toolbar">

      <select
        id="pricing-station"
      >
        ${S.stations
          .map(
            (s) =>
              opt(
                s.id,
                s.name,
                sid,
              ),
          )
          .join("")}
      </select>

      ${btn(
        tr(
          "＋ 添加价格时段",
        ),
        "edit-pricing",
        "",
      )}

    </div>

    <div class="card">

      <div class="section-head">

        <h2>
          分时计价
        </h2>

        <small>
          电费 + 服务费 =
          用户实际单价
        </small>

      </div>

      ${table(
        [
          tr("时段"),
          tr("电费 / 度"),
          tr(
            "服务费 / 度",
          ),
          tr("合计 / 度"),
          tr("操作"),
        ],

        S.pricing.map(
          (p) =>
            `<tr>

              <td>
                ${p.start_time}
                -
                ${p.end_time}
              </td>

              <td>
                ¥
                ${yuan(
                  p.electricity_fee_cents,
                )}
              </td>

              <td>
                ¥
                ${yuan(
                  p.service_fee_cents,
                )}
              </td>

              <td>
                <b>
                  ¥
                  ${yuan(
                    p.price_cents,
                  )}
                </b>
              </td>

              <td>
                ${btn(
                  tr(
                    "编辑",
                  ),
                  "edit-pricing",
                  "secondary small",
                  `data-id="${p.id}"`,
                )}

                ${btn(
                  tr(
                    "删除",
                  ),
                  "delete-pricing",
                  "danger small",
                  `data-id="${p.id}"`,
                )}
              </td>

            </tr>`,
        ),
      )}

      <div class="note">
        时段不能重叠。
        若需要跨午夜，
        请拆成
        18:00-24:00
        和
        00:00-08:00
        两条规则。
      </div>

    </div>
  `;
}

function faultsTable(fs) {
  return table(
    [
      tr("编号"),
      tr("电站 / 电桩"),
      tr("故障类型"),
      tr("故障描述"),
      tr("状态"),
      tr("故障时间"),
      tr("处理结果"),
      tr("操作"),
    ],

    fs.map(
      (f) =>
        `<tr>

          <td>
            #${f.id}
          </td>

          <td>
            ${esc(
              f.station_name,
            )}

            <br>

            <small>
              ${esc(
                f.charger_number,
              )}
            </small>
          </td>

          <td>
            ${esc(
              f.fault_type,
            )}
          </td>

          <td>
            ${esc(
              f.description,
            )}
          </td>

          <td>
            ${badge(
              f.status,
            )}
          </td>

          <td>
            ${time(
              f.reported_at,
            )}
          </td>

          <td>
            ${esc(
              f.resolution ||
                "—",
            )}
          </td>

          <td>
            ${
              f.status !==
              "resolved"
                ? btn(
                    tr(
                      "处理",
                    ),
                    "process-fault",
                    "secondary small",
                    `data-id="${f.id}"`,
                  )
                : tr(
                    "<small>已完成</small>",
                  )
            }
          </td>

        </tr>`,
    ),
  );
}

async function faultsPage() {
  [
    S.faults,
    S.chargers,
  ] =
    await Promise.all([
      api(
        "/admin/faults",
      ),

      api(
        "/admin/chargers",
      ),
    ]);

  return trHtml`
    <div class="toolbar">

      ${btn(
        tr(
          "＋ 登记故障",
        ),
        "new-fault",
        "",
      )}

    </div>

    <div class="card">

      <div class="section-head">

        <h2>
          设备故障记录
        </h2>

        <small>
          ${
            S.faults.filter(
              (f) =>
                f.status !==
                "resolved",
            ).length
          }

          条待处理/处理中
        </small>

      </div>

      ${faultsTable(
        S.faults,
      )}

    </div>
  `;
}

function userState(u) {
  if (
    Number(
      u.debt_cents,
    ) > 0
  ) {
    return "debt";
  }

  if (!u.active) {
    return "frozen";
  }

  return "normal";
}

function userBadge(u) {
  const labels = {
    normal:
      tr("正常"),
    debt:
      tr("欠费"),
    frozen:
      tr("冻结"),
  };

  const state =
    userState(u);

  return `
    <span
      class="badge ${state}"
    >
      ${labels[state]}
    </span>
  `;
}

function usersTable(users) {
  return table(
    [
      tr("用户"),
      tr("手机号"),
      tr("角色"),
      tr("余额"),
      tr("欠费"),
      tr("状态"),
      tr("注册时间"),
      tr("操作"),
    ],

    users.map(
      (u) =>
        `<tr>
          <td>${esc(u.nickname)}</td>
          <td>${esc(u.phone)}</td>
          <td>
            ${
              can("role.manage")
                ? `<select class="role-select" data-user-id="${u.id}">
                     ${opt("user", tr("普通用户"), u.role)}
                     ${opt("operator", tr("运营人员"), u.role)}
                     ${opt("technician", tr("运维人员"), u.role)}
                     ${opt("admin", tr("系统管理员"), u.role)}
                   </select>`
                : `<span class="role-chip compact">
                     ${esc(
                       u.role_name ||
                         roleNames[u.role] ||
                         u.role,
                     )}
                   </span>`
            }
          </td>
          <td>¥ ${yuan(u.balance_cents)}</td>
          <td>
            ${
              Number(u.debt_cents) > 0
                ? "¥ " + yuan(u.debt_cents)
                : "—"
            }
          </td>
          <td>${userBadge(u)}</td>
          <td>${time(u.created_at)}</td>
          <td>
            ${
              can("user.manage")
                ? btn(
                    u.active ? tr("冻结") : tr("启用"),
                    "user-toggle",
                    u.active
                      ? "danger small"
                      : "secondary small",
                    `data-id="${u.id}" data-active="${!u.active}"`,
                  )
                : `<small>${tr("仅查看")}</small>`
            }
          </td>
        </tr>`,
    ),
  );
}

async function usersPage() {
  S.userFilter = {
    status: "",
    from: "",
    to: "",
    sort: "newest",
  };

  await loadUsers();

  return trHtml`
    <div class="stack">
      <section class="card role-banner">
        <div>
          <div class="eyebrow">RBAC · ACCESS CONTROL</div>
          <h2>四种角色统一管理</h2>
          <p class="sub">
            权限在服务端强制校验，页面只展示当前角色可用的功能。
          </p>
        </div>

        ${
          can("role.manage")
            ? pageBtn(
                "roles",
                tr("查看权限矩阵"),
                "secondary",
              )
            : ""
        }
      </section>

      <div class="toolbar">
        <select id="user-status">
          <option value="">${tr("全部状态")}</option>
          ${opt("normal", tr("正常"))}
          ${opt("debt", tr("欠费"))}
          ${opt("frozen", tr("冻结"))}
        </select>

        <input
          type="date"
          id="user-from"
          title="${tr("开始日期")}"
        >

        <span class="muted">${tr("至")}</span>

        <input
          type="date"
          id="user-to"
          title="${tr("结束日期")}"
        >

        ${btn(
          tr("近 30 天"),
          "user-range",
          "secondary small",
          'data-days="30"',
        )}

        ${btn(
          tr("全部"),
          "user-range",
          "secondary small",
          'data-days="0"',
        )}

        <select id="user-sort">
          <option value="newest">${tr("最新注册")}</option>
          <option value="oldest">${tr("最早注册")}</option>
        </select>
      </div>

      <p
        class="sub"
        id="user-filter-info"
        style="margin:-8px 0 20px"
      >
        ${tr("按用户状态和注册日期筛选")}
      </p>

      <div class="card">
        <div class="section-head">
          <h2>${tr("账号与角色")}</h2>
          <small id="users-count">
            ${(S.users || []).length} ${tr("个账号")}
          </small>
        </div>

        <div id="users-table">
          ${usersTable(S.users || [])}
        </div>
      </div>
    </div>
  `;
}

async function loadUsers() {
  const version =
    S.version;

  const p =
    new URLSearchParams();

  const f =
    S.userFilter ||
    {};

  if (f.status) {
    p.set(
      "status",
      f.status,
    );
  }

  if (f.from) {
    p.set(
      "date_from",
      f.from,
    );
  }

  if (f.to) {
    p.set(
      "date_to",
      f.to,
    );
  }

  if (f.sort) {
    p.set(
      "sort",
      f.sort,
    );
  }

  const users =
    await api(
      "/admin/users?" +
        p.toString(),
    );

  if (
    version !==
    S.version
  ) {
    return;
  }

  S.users = users;

  const tableElement =
    $("#users-table");

  if (tableElement) {
    tableElement.innerHTML =
      usersTable(users);
  }

  const count =
    $("#users-count");

  if (count) {
    count.textContent =
      `${users.length} ${tr(
        "个账号",
      )}`;
  }

  const info =
    $("#user-filter-info");

  if (info) {
    info.textContent =
      `${tr(
        "筛选结果",
      )}：${users.length} ${tr(
        "个账号",
      )}`;
  }
}

async function rolesPage() {
  const data =
    await api(
      "/admin/roles",
    );

  const permissionMap =
    Object.fromEntries(
      data.permissions.map(
        (p) => [
          p.key,
          p,
        ],
      ),
    );

  return trHtml`
    <div class="stack">
      <section class="card role-banner">
        <div>
          <div class="eyebrow">RBAC · PERMISSIONS</div>
          <h2>${tr("角色与权限")}</h2>
          <p class="sub">
            后端按权限强制校验；这里显示四种业务角色的权限矩阵。
          </p>
        </div>
      </section>

      ${data.roles
        .map(
          (role) =>
            `<section class="card">
              <div class="section-head">
                <div>
                  <h3>${esc(role.name)}</h3>
                  <p class="sub">
                    ${esc(role.description)}
                  </p>
                </div>

                <span class="role-chip">
                  ${esc(role.key)}
                </span>
              </div>

              <div class="permission-cloud">
                ${(role.permissions || [])
                  .map(
                    (key) =>
                      `<span class="permission-pill">
                        ${esc(
                          permissionMap[key]?.name ||
                            key,
                        )}
                        <small class="role-code">
                          ${esc(key)}
                        </small>
                      </span>`,
                  )
                  .join("")}
              </div>
            </section>`,
        )
        .join("")}
    </div>
  `;
}

async function revenuePage() {
  const d =
    await api(
      "/dashboard",
    );

  return trHtml`
    <div class="stack">

      <div class="metric-grid">

        ${metric(
          "wallet",
          tr(
            "累计实收",
          ),
          "¥ " +
            yuan(
              d.totals
                .paid_cents,
            ),
        )}

        ${metric(
          "orders",
          tr(
            "已结算订单",
          ),
          d.totals.orders,
          tr("笔"),
        )}

        ${metric(
          "wallet",
          tr(
            "待补缴金额",
          ),
          "¥ " +
            yuan(
              d.totals
                .debt_cents,
            ),
        )}

      </div>

      <div class="card">

        <div class="section-head">

          <h2>
            最近 7 天营收
          </h2>

          <a
            class="btn secondary"
            href="/api/admin/export?lang=${NCSPreferences.state.language}"
          >
            导出全部订单 CSV
          </a>

        </div>

        ${chart(
          d.days,
          "cents",
        )}

        ${table(
          [
            tr("日期"),
            tr("订单数"),
            tr(
              "充电电量",
            ),
            tr(
              "实收金额",
            ),
          ],

          d.days.map(
            (x) =>
              `<tr>

                <td>
                  ${x.day}
                </td>

                <td>
                  ${x.orders}
                </td>

                <td>
                  ${x.energy.toFixed(
                    2,
                  )}
                  kWh
                </td>

                <td>
                  ¥
                  ${yuan(
                    x.cents,
                  )}
                </td>

              </tr>`,
          ),
        )}

      </div>
    </div>
  `;
}

async function predictionPage() {
  S.stations =
    await api(
      "/stations",
    );

  const sid =
    S.predictionStation ||
    S.stations[0]?.id;

  if (!sid) {
    return `
      <div class="card">
        ${empty(
          tr(
            "请先添加电站",
          ),
        )}
      </div>
    `;
  }

  const p =
      await api(
        "/admin/prediction?station_id=" +
          sid,
      ),

    max =
      Math.max(
        ...p.points.map(
          (x) =>
            x.load,
        ),
        1,
      );

  return trHtml`
    <div class="toolbar">

      <select
        id="prediction-station"
      >
        ${S.stations
          .map(
            (s) =>
              opt(
                s.id,
                s.name,
                sid,
              ),
          )
          .join("")}
      </select>

      <small>
        未来 12 小时 ·
        ${p.sample_count}
        条历史样本
      </small>

    </div>

    <div class="card">

      <h2>
        电站负荷参考
      </h2>

      <div class="note">
        ${esc(
          tr(p.method),
        )}
      </div>

      ${
        p.points.length
          ? `
            <div class="bar-chart">

              ${p.points
                .map(
                  (x) =>
                    `<div class="bar-item">

                      <small>
                        ${x.load}
                      </small>

                      <i
                        style="
                          height:
                            ${Math.max(
                              1,
                              (
                                x.load /
                                max
                              ) *
                                145,
                            )}px
                        "
                      ></i>

                      <small>
                        ${x.time.slice(
                          11,
                          16,
                        )}
                      </small>

                    </div>`,
                )
                .join("")}

            </div>

            ${table(
              [
                tr(
                  "目标时间",
                ),
                tr(
                  "参考平均负荷",
                ),
                tr(
                  "预计空闲桩",
                ),
                tr(
                  "高峰标记",
                ),
              ],

              p.points.map(
                (x) =>
                  trHtml`
                    <tr>

                      <td>
                        ${time(
                          x.time,
                        ).slice(
                          0,
                          16,
                        )}
                      </td>

                      <td>
                        ${x.load}
                        kW
                      </td>

                      <td>
                        ${x.free}
                        个
                      </td>

                      <td>
                        ${
                          x.peak
                            ? tr(
                                "高峰",
                              )
                            : tr(
                                "平稳",
                              )
                        }
                      </td>

                    </tr>
                  `,
              ),
            )}
          `
          : empty(
              tr(
                "暂无足够历史数据",
              ),
            )
      }

    </div>
  `;
}

async function logsPage() {
  const ls =
    await api(
      "/admin/logs",
    );

  return trHtml`
    <div class="card">

      <h2
        style="margin-bottom:22px"
      >
        最近操作
      </h2>

      ${table(
        [
          tr("编号"),
          tr("操作内容"),
          tr(
            "操作人 ID",
          ),
          tr("时间"),
        ],

        ls.map(
          (l) =>
            `<tr>

              <td>
                ${l.id}
              </td>

              <td>
                ${esc(
                  l.operation_display ||
                    l.operation,
                )}
              </td>

              <td>
                ${l.actor_id}
              </td>

              <td>
                ${time(
                  l.created_at,
                )}
              </td>

            </tr>`,
        ),
      )}

    </div>
  `;
}

const renderers = {
  dashboard,
  stations:
    stationsPage,
  station:
    stationDetail,
  scan:
    scanPage,
  orders:
    ordersPage,
  charging:
    chargingPage,
  wallet:
    walletPage,
  profile:
    profilePage,
  chargers:
    chargersPage,
  realtime:
    realtimePage,
  agent:
    agentPage,
  pricing:
    pricingPage,
  faults:
    faultsPage,
  users:
    usersPage,
  roles:
    rolesPage,
  revenue:
    revenuePage,
  prediction:
    predictionPage,
  logs:
    logsPage,
  settings:
    preferencesCard,
};

async function go(
  page = "dashboard",
  id,
) {
  clearInterval(
    S.timer,
  );

  S.page = page;
  S.pageId = id;

  if (
    page !== "scan" &&
    location.pathname.startsWith(
      "/charge/",
    )
  ) {
    history.replaceState(
      null,
      "",
      "/",
    );

    S.scanNumber =
      null;
  }

  const v =
    ++S.version;

  $("#modal").close();

  shell();

  $("#content").innerHTML =
    tr(
      '<div class="loading">正在加载…</div>',
    );

  try {
    const html =
      await (
        renderers[
          page
        ]?.(id) ||
        empty(
          tr(
            "页面不存在",
          ),
        )
      );

    if (
      v !==
      S.version
    ) {
      return;
    }

    $("#content")
      .innerHTML =
        html;
    if (
      page ===
      "agent"
    ) {
      renderAgentMessages();
    }

    if (
      page ===
        "charging" &&
      $("#live-energy")
    ) {
      S.timer =
        setInterval(
          async () => {
            try {
              const o =
                await api(
                  `/orders/${S.liveId}/receipt`,
                );

              if (
                v !==
                S.version
              ) {
                return;
              }

              if (
                ![
                  "charging",
                  "reserved",
                ].includes(
                  o.status,
                )
              ) {
                await go(
                  "charging",
                );

                return;
              }

              $("#live-energy")
                .textContent =
                  Number(
                    o.energy,
                  ).toFixed(
                    3,
                  );

              $("#live-amount")
                .textContent =
                  "¥ " +
                  yuan(
                    o.amount_cents,
                  );

              $("#live-time")
                .textContent =
                  Math.floor(
                    o.simulated_seconds /
                      60,
                  ) +
                  tr(
                    " 分钟",
                  );
            } catch (e) {
              clearInterval(
                S.timer,
              );

              toast(
                e.message,
              );
            }
          },

          3000,
        );
    }

    if (
        page ===
            "realtime" &&
        $("#realtime-root")
        ) {
        S.timer =
            setInterval(
            async () => {
                try {
                const data =
                    await api(
                    "/realtime",
                    );
                pushRealtimeHistory(
                    data,
                );

                if (
                    v !==
                    S.version
                ) {
                    return;
                }

                const root =
                    $("#realtime-root");

                if (root) {
                    root.innerHTML =
                    realtimeContent(
                        data,
                    );
                }

                } catch (e) {
                clearInterval(
                    S.timer,
                );

                toast(
                    e.message,
                );
                }
            },

            5000,
            );
        }

  } catch (e) {
    if (
      v !==
      S.version
    ) {
      return;
    }

    $("#content")
      .innerHTML =
        empty(
          esc(
            e.message,
          ),
        );

    if (
      e.status === 401
    ) {
      await boot();
    }
  }
}

async function refresh() {
  const s =
    await api(
      "/session",
    );

  S.user =
    s.user;

  S.csrf =
    s.csrf;

  S.scale =
    s.time_scale;

  if (!s.user) {
    loginView();

    throw Error(
      tr(
        "请重新登录",
      ),
    );
  }
}

async function afterLogin() {
  await adoptAccountPreferences();

  if (
    S.scanNumber &&
    S.user.role ===
      "user"
  ) {
    await go(
      "scan",
      S.scanNumber,
    );
  } else {
    await go(
      "dashboard",
    );
  }
}

function rechargeModal() {
  modal(
    tr(
      "给钱包充点能量",
    ),

    trHtml`
      <p class="sub">
        模拟充值，
        仅用于课程演示，
        不产生真实付款。
      </p>

      <div
        class="actions"
        style="margin:20px 0"
      >
        ${[
          20,
          50,
          100,
          200,
        ]
          .map(
            (n) =>
              btn(
                "¥ " +
                  n,
                "preset",
                "secondary",
                `data-amount="${n}"`,
              ),
          )
          .join("")}
      </div>

      <form id="recharge-form">

        ${field(
          tr(
            "充值金额（元）",
          ),
          "amount",
          50,
          "number",
          'required min="0.01" max="100000" step="0.01"',
        )}

        <button
          class="btn"
          type="submit"
        >
          确认模拟充值
        </button>

      </form>
    `,
  );
}

function editStation(id) {
  const s =
    id
      ? S.stations.find(
          (x) =>
            x.id ===
            id,
        ) ||
        S.detail
      : {};

  modal(
    id
      ? tr(
          "编辑电站",
        )
      : tr(
          "添加电站",
        ),

    trHtml`
      <form
        id="station-form"
        data-id="${id || ""}"
      >

        ${field(
          tr(
            "电站名称",
          ),
          "name",
          s.name ||
            "",
          "text",
          'required maxlength="60"',
        )}

        ${field(
          tr(
            "详细地址",
          ),
          "address",
          s.address ||
            "",
          "text",
          'required maxlength="160"',
        )}

        ${field(
          tr(
            "所属城市",
          ),
          "city",
          s.city ||
            "北京市",
          "text",
          'required maxlength="60"',
        )}

        ${field(
          tr(
            "营业时间",
          ),
          "business_hours",
          s.business_hours ||
            "00:00-24:00",
          "text",
          tr(
            'required maxlength="60" placeholder="例如 06:00-23:00"',
          ),
        )}

        ${field(
          tr(
            "联系方式",
          ),
          "contact_phone",
          s.contact_phone ||
            "010-00000000",
          "text",
          'required maxlength="40"',
        )}

        <div class="field">

          <label for="f-operating_status">
            运营状态
          </label>

          <select
            id="f-operating_status"
            name="operating_status"
          >
            ${opt(
              "operating",
              tr(
                "运营中",
              ),
              s.operating_status ||
                "operating",
            )}

            ${opt(
              "paused",
              tr(
                "暂停运营",
              ),
              s.operating_status,
            )}

            ${opt(
              "maintenance",
              tr(
                "维护中",
              ),
              s.operating_status,
            )}
          </select>

        </div>

        ${field(
          tr(
            "停车说明",
          ),
          "parking_info",
          s.parking_info ||
            "以现场停车规定为准",
          "text",
          'required maxlength="240"',
        )}

        <div class="info-grid">

          ${field(
            tr(
              "经度",
            ),
            "lng",
            s.lng ??
              116.2981,
            "number",
            'required step="any" min="-180" max="180"',
          )}

          ${field(
            tr(
              "纬度",
            ),
            "lat",
            s.lat ??
              39.9593,
            "number",
            'required step="any" min="-90" max="90"',
          )}

        </div>

        <div
          style="margin-top:17px"
        >
          ${field(
            tr(
              "基础单价（元/度）",
            ),
            "price",
            s.price_cents
              ? yuan(
                  s.price_cents,
                )
              : 1.5,
            "number",
            'required min="0.01" max="100" step="0.01"',
          )}
        </div>

        <div class="note">
          新增电站时会自动生成早/日间/晚三个分时价格；
          之后请到“价格管理”单独调整。
        </div>

        <button
          class="btn"
          type="submit"
        >
          保存电站
        </button>

      </form>
    `,
  );
}

function editCharger(id) {
  const c =
    id
      ? S.chargers.find(
          (x) =>
            x.id ===
            id,
        )
      : {};

  modal(
    id
      ? tr(
          "编辑充电桩",
        )
      : tr(
          "添加充电桩",
        ),

    trHtml`
      <form
        id="charger-form"
        data-id="${id || ""}"
      >

        <div class="field">

          <label for="f-station_id">
            所属电站
          </label>

          <select
            name="station_id"
            id="f-station_id"
            required
          >
            ${S.stations
              .map(
                (s) =>
                  opt(
                    s.id,
                    s.name,
                    c.station_id,
                  ),
              )
              .join("")}
          </select>

        </div>

        ${field(
          tr(
            "充电桩编号",
          ),
          "number",
          c.number ||
            "",
          "text",
          'required maxlength="30"',
        )}

        <div class="field">

          <label for="f-kind">
            类型
          </label>

          <select
            id="f-kind"
            name="kind"
          >
            ${opt(
              "fast",
              tr("快充"),
              c.kind ||
                "fast",
            )}

            ${opt(
              "slow",
              tr("慢充"),
              c.kind,
            )}
          </select>

        </div>

        ${field(
          tr(
            "额定功率（kW）",
          ),
          "power",
          c.power ||
            60,
          "number",
          'required min="1" max="1000" step="any"',
        )}

        <button
          class="btn"
          type="submit"
        >
          保存充电桩
        </button>

      </form>
    `,
  );
}

function editPricing(id) {
  const p =
    id
      ? S.pricing.find(
          (x) =>
            x.id ===
            id,
        )
      : {};

  modal(
    id
      ? tr(
          "编辑分时价格",
        )
      : tr(
          "添加分时价格",
        ),

    trHtml`
      <form
        id="pricing-form"
        data-id="${id || ""}"
      >

        <div class="field">

          <label>
            所属电站
          </label>

          <select
            name="station_id"
          >
            ${S.stations
              .map(
                (s) =>
                  opt(
                    s.id,
                    s.name,
                    p.station_id ||
                      S.pricingStation,
                  ),
              )
              .join("")}
          </select>
        </div>

        <div class="info-grid">

          ${field(
            tr(
              "开始时间",
            ),
            "start_time",
            p.start_time ||
              "00:00",
            "text",
            'required pattern="[0-9]{2}:[0-9]{2}" placeholder="08:00"',
          )}

          ${field(
            tr(
              "结束时间",
            ),
            "end_time",
            p.end_time ||
              "08:00",
            "text",
            tr(
              'required pattern="[0-9]{2}:[0-9]{2}" placeholder="可填写 24:00"',
            ),
          )}

        </div>

        <div
          class="info-grid"
          style="margin-top:17px"
        >

          ${field(
            tr(
              "电费（元/度）",
            ),
            "electricity_fee",
            p.id
              ? yuan(
                  p.electricity_fee_cents,
                )
              : 1.0,
            "number",
            'required min="0" max="100" step="0.01"',
          )}

          ${field(
            tr(
              "服务费（元/度）",
            ),
            "service_fee",
            p.id
              ? yuan(
                  p.service_fee_cents,
                )
              : 0.3,
            "number",
            'required min="0" max="100" step="0.01"',
          )}

        </div>

        <button
          class="btn"
          type="submit"
        >
          保存价格规则
        </button>

      </form>
    `,
  );
}

function newFaultModal() {
  modal(
    tr(
      "登记设备故障",
    ),

    trHtml`
      <form id="fault-form">

        <div class="field">

          <label>
            故障设备
          </label>

          <select
            name="charger_id"
          >
            ${S.chargers
              .filter(
                (c) =>
                  ![
                    "reserved",
                    "charging",
                  ].includes(
                    c.status,
                  ),
              )
              .map(
                (c) =>
                  opt(
                    c.id,
                    c.station_name +
                      " · " +
                      c.number,
                  ),
              )
              .join("")}
          </select>

        </div>

        ${field(
          tr(
            "故障类型",
          ),
          "fault_type",
          "通信故障",
          "text",
          'required maxlength="60"',
        )}

        ${field(
          tr(
            "故障描述",
          ),
          "description",
          "",
          "text",
          tr(
            'required maxlength="300" placeholder="请描述故障现象"',
          ),
        )}

        <button
          class="btn"
          type="submit"
        >
          登记故障
        </button>

      </form>
    `,
  );
}

function processFaultModal(id) {
  const f =
    S.faults.find(
      (x) =>
        x.id === id,
    );

  modal(
    tr(
      "处理故障 · #",
    ) + id,

    trHtml`
      <form
        id="fault-process-form"
        data-id="${id}"
      >

        <div class="note">
          ${esc(
            f.station_name,
          )}
          ·
          ${esc(
            f.charger_number,
          )}

          <br>

          ${esc(
            f.fault_type,
          )}
          ：
          ${esc(
            f.description,
          )}
        </div>

        <div class="field">

          <label>
            处理状态
          </label>

          <select name="status">

            ${opt(
              "pending",
              tr(
                "待处理",
              ),
              f.status,
            )}

            ${opt(
              "processing",
              tr(
                "处理中",
              ),
              f.status,
            )}

            ${opt(
              "resolved",
              tr(
                "已解决",
              ),
              f.status,
            )}

          </select>
        </div>

        ${field(
          tr(
            "处理结果",
          ),
          "resolution",
          f.resolution ||
            "",
          "text",
          tr(
            'maxlength="300" placeholder="解决时必须填写，例如：更换通信模块后恢复正常"',
          ),
        )}

        <button
          class="btn"
          type="submit"
        >
          更新故障状态
        </button>

      </form>
    `,
  );
}

function qrModal(id) {
  const all = [
      ...(S.chargers ||
        []),

      ...(S.detailChargers ||
        []),
    ],

    c =
      all.find(
        (x) =>
          x.id ===
          id,
      );

  const number =
      c?.number ||
      "charger-" +
        id,

    url =
      location.origin +
      "/charge/" +
      encodeURIComponent(
        number,
      );

  modal(
    tr(
      "充电桩二维码 · ",
    ) + number,

    trHtml`
      <div class="qr-box">

        <img
          src="/api/chargers/${id}/qr"
          alt="${esc(
            number,
          )} 充电二维码"
        >

        <p>
          用手机相机/微信扫码后进入对应充电桩页面。
        </p>

        <code>
          ${esc(url)}
        </code>

      </div>
    `,
  );
}

function mapModal(id) {
  const s =
    S.stations.find(
      (x) =>
        x.id === id,
    ) ||
    S.detail;

  modal(
    tr("前往 ") +
      s.name,

    trHtml`
      <p class="sub">
        ${esc(
          s.address,
        )}
      </p>

      <div class="note">
        起点：
        ${esc(
          tr(
            S.location,
          ),
        )}
        （${S.lat},
        ${S.lng}）

        <br>

        终点：
        （${s.lat},
        ${s.lng}）

        <br>

        路线将在浏览器地图页面规划，
        需要联网。
      </div>

      <div class="field">

        <label
          for="travel-mode"
        >
          出行方式
        </label>

        <select
          id="travel-mode"
        >
          <option value="drive">
            驾车
          </option>

          <option value="walk">
            步行
          </option>

          <option value="bus">
            公交
          </option>
        </select>

      </div>

      <a
        class="btn"
        id="map-link"
        target="_blank"
        rel="noopener noreferrer"
      >
        打开腾讯地图 ↗
      </a>
    `,
  );

  const update =
    () => {
      $("#map-link")
        .href =
          "https://apis.map.qq.com/uri/v1/routeplan?" +
          new URLSearchParams({
            type:
              $("#travel-mode")
                .value,

            from:
              S.location,

            fromcoord:
              S.lat +
              "," +
              S.lng,

            to:
              s.name,

            tocoord:
              s.lat +
              "," +
              s.lng,

            coord_type:
              "2",

            policy:
              "0",

            referer:
              "NCS_Charging_Platform",
          });
    };

  update();

  $("#travel-mode")
    .onchange =
      update;
}

function confirmModal(
  title,
  text,
  next,
  data,
) {
  modal(
    title,

    `<p class="sub">
       ${esc(text)}
     </p>

     <div
       class="actions"
       style="margin-top:24px"
     >
       ${btn(
         tr(
           "取消",
         ),
         "close",
       )}

       ${btn(
         tr(
           "确认",
         ),
         "confirm",
         "",
         `data-next="${next}" ${data}`,
       )}
     </div>`,
  );
}

async function sendAgentMessage(
  question,
) {
  question =
    String(
      question || "",
    ).trim();

  if (
    !question ||
    S.agentBusy
  ) {
    return;
  }

  S.agentBusy = true;

  S.agentMessages.push({
    role: "user",
    text: question,
  });

  renderAgentMessages();

  const input =
    $("#agent-input");

  if (input) {
    input.value = "";
  }

  showAgentThinking();

  try {
    const result =
      await api(
        "/agent/chat",
        "POST",
        {
          message:
            question,

          lat:
            S.lat,

          lng:
            S.lng,
        },
      );

    hideAgentThinking();

    S.agentMessages.push({
      role:
        "assistant",

      text:
        result.answer ||
        tr(
          "暂时无法生成回答。",
        ),

      intent:
        result.intent,
    });

    renderAgentMessages();

  } catch (e) {
    hideAgentThinking();

    S.agentMessages.push({
      role:
        "assistant",

      text:
        "请求失败：" +
        e.message,
    });

    renderAgentMessages();

  } finally {
    S.agentBusy =
      false;

    $("#agent-input")
      ?.focus();
  }
}

async function act(
  name,
  b,
) {
  const id =
    Number(
      b.dataset.id,
    );

  switch (name) {
    case "preferences":
      openPreferences();
      break;

    case "close":
      $("#modal").close();
      break;

    case "menu":
      $(".sidebar")
        .classList
        .toggle("open");
      break;
    
    case "agent-suggest":
      await sendAgentMessage(
        b.dataset.question,
      );
      break;

    case "login-tab":
      loginView();
      break;

    case "register-tab":
      loginView(true);
      break;

    case "demo-user":
      $("#f-phone")
        .value =
          "13800138000";

      $("#f-password")
        .value =
          "User123456";
      break;

    case "demo-admin":
      $("#f-phone")
        .value =
          "admin";

      $("#f-password")
        .value =
          "Admin123456";
      break;

    case "demo-operator":
      $("#f-phone")
        .value =
          "operator";

      $("#f-password")
        .value =
          "Operator123456";
      break;

    case "demo-tech":
      $("#f-phone")
        .value =
          "tech";

      $("#f-password")
        .value =
          "Tech123456";
      break;

    case "logout":
      await api(
        "/logout",
        "POST",
        {},
      );

      S.agentMessages = [];
      S.agentBusy = false;

      await boot();
      break;

    case "station":
      await go(
        "station",
        id,
      );
      break;

    case "receipt":
      await receipt(id);
      break;

    case "print":
      window.print();
      break;

    case "recharge":
      rechargeModal();
      break;

    case "preset":
      $("#f-amount")
        .value =
          b.dataset.amount;
      break;

    case "order-range": {
      const days =
        Number(
          b.dataset.days,
        );

      if (days === 0) {
        S.orderFrom = "";
        S.orderTo = "";
      } else {
        const today =
            new Date(),

          from =
            new Date(
              today,
            );

        from.setDate(
          from.getDate() -
            (
              days -
              1
            ),
        );

        S.orderFrom =
          fmtDate(from);

        S.orderTo =
          fmtDate(
            today,
          );
      }

      if (
        $("#order-from")
      ) {
        $("#order-from")
          .value =
            S.orderFrom;
      }

      if (
        $("#order-to")
      ) {
        $("#order-to")
          .value =
            S.orderTo;
      }

      await loadOrders();

      break;
    }

    case "user-range": {
      const days =
        Number(
          b.dataset.days,
        );

      if (days === 0) {
        S.userFilter.from =
          "";

        S.userFilter.to =
          "";
      } else {
        const today =
            new Date(),

          from =
            new Date(
              today,
            );

        from.setDate(
          from.getDate() -
            (
              days -
              1
            ),
        );

        S.userFilter.from =
          fmtDate(from);

        S.userFilter.to =
          fmtDate(
            today,
          );
      }

      if (
        $("#user-from")
      ) {
        $("#user-from")
          .value =
            S.userFilter.from;
      }

      if (
        $("#user-to")
      ) {
        $("#user-to")
          .value =
            S.userFilter.to;
      }

      await loadUsers();

      break;
    }

    case "qr":
      qrModal(id);
      break;

    case "reserve":
    case "start-charge":
      try {
        await api(
          "/orders",
          "POST",
          {
            charger_id:
              id,

            mode:
              name ===
              "reserve"
                ? "reserve"
                : "start",
          },
        );

        await go(
          "charging",
        );

        toast(
          name ===
          "reserve"
            ? tr(
                "预约成功，电桩为你保留 15 分钟",
              )
            : tr(
                "充电已开始",
              ),
        );
      } catch (e) {
        if (
          e.order_id
        ) {
          await go(
            "charging",
          );

          toast(
            tr(
              "您有未完成的充电订单，请先处理",
            ),
          );
        } else {
          throw e;
        }
      }

      break;

    case "order-finish":
      confirmModal(
        tr(
          "结束充电并结算",
        ),

        tr(
          "确认后停止模拟充电，按最终电量扣款并释放充电桩。",
        ),

        "finish",

        `data-id="${id}"`,
      );
      break;

    case "order-cancel":
      confirmModal(
        tr(
          "取消预约",
        ),

        tr(
          "确认取消此预约并释放充电桩？",
        ),

        "cancel",

        `data-id="${id}"`,
      );
      break;

    case "order-start":
      await api(
        `/orders/${id}/start`,
        "POST",
        {},
      );

      await go(
        "charging",
      );
      break;

    case "order-pay":
      await api(
        `/orders/${id}/pay`,
        "POST",
        {},
      );

      await refresh();

      await go(
        "orders",
      );

      toast(
        tr(
          "欠费补缴成功",
        ),
      );
      break;

    case "confirm": {
      const op =
        b.dataset.next;

      if (
        [
          "finish",
          "cancel",
        ].includes(op)
      ) {
        await api(
          `/orders/${id}/${op}`,
          "POST",
          {},
        );

        await refresh();

        await go(
          "orders",
        );

        if (
          op ===
          "finish"
        ) {
          await receipt(
            id,
          );
        } else {
          toast(
            tr(
              "预约已取消",
            ),
          );
        }
      } else if (
        op ===
        "delete-station"
      ) {
        await api(
          "/admin/stations/" +
            id,
          "DELETE",
        );

        await go(
          "stations",
        );

        toast(
          tr(
            "电站已删除",
          ),
        );
      } else if (
        op ===
        "charger-action"
      ) {
        await api(
          `/admin/chargers/${id}/action`,
          "POST",
          {
            action:
              b.dataset.op,
          },
        );

        await go(
          S.page === "station"
            ? "station"
            : "chargers",
          S.page === "station"
            ? S.pageId
            : undefined,
        );

        toast(
          tr(
            "操作成功",
          ),
        );
      } else if (
        op ===
        "delete-pricing"
      ) {
        await api(
          "/admin/pricing/" +
            id,
          "DELETE",
        );

        await go(
          "pricing",
        );

        toast(
          tr(
            "价格规则已删除",
          ),
        );
      }

      break;
    }

    case "avatar":
      $(".theme-choice.selected")
        ?.classList
        .remove(
          "selected",
        );

      b.classList.add(
        "selected",
      );

      $(
        "#profile-form [name=avatar]",
      ).value =
        b.dataset.color;

      break;

    case "edit-station":
      editStation(id);
      break;

    case "delete-station":
      confirmModal(
        tr(
          "删除电站",
        ),

        tr(
          "仅允许删除没有关联电桩的电站。确定继续？",
        ),

        "delete-station",

        `data-id="${id}"`,
      );
      break;

    case "edit-charger":
      editCharger(id);
      break;

    case "charger-action":
      confirmModal(
        tr(
          "设备操作",
        ),

        b.dataset.op ===
        "delete"
          ? tr(
              "删除此设备？有历史订单的设备无法删除。",
            )
          : tr(
              "确认更改此充电桩状态？",
            ),

        "charger-action",

        `data-id="${id}" data-op="${b.dataset.op}"`,
      );
      break;

    case "edit-pricing":
      editPricing(
        Number.isFinite(
          id,
        ) &&
          id > 0
          ? id
          : null,
      );
      break;

    case "delete-pricing":
      confirmModal(
        tr(
          "删除价格规则",
        ),

        tr(
          "确定删除这个分时时段？每个电站至少保留一条规则。",
        ),

        "delete-pricing",

        `data-id="${id}"`,
      );
      break;

    case "new-fault":
      newFaultModal();
      break;

    case "process-fault":
      processFaultModal(
        id,
      );
      break;

    case "user-toggle":
      await api(
        "/admin/users/" +
          id,
        "POST",
        {
          active:
            b.dataset.active ===
            "true",
        },
      );

      await go(
        "users",
      );

      toast(
        tr(
          "用户状态已更新",
        ),
      );
      break;

    case "map":
      mapModal(id);
      break;

    case "locate":
      if (
        !navigator.geolocation
      ) {
        throw Error(
          tr(
            "此浏览器不支持定位，请使用区域选择",
          ),
        );
      }

      toast(
        tr(
          "正在请求浏览器定位权限…",
        ),
      );

      navigator.geolocation
        .getCurrentPosition(
          async (p) => {
            try {
              [
                S.lat,
                S.lng,
              ] =
                wgsToGcj(
                  p.coords
                    .latitude,

                  p.coords
                    .longitude,
                );

              S.location =
                "自定义位置";

              await go(
                "stations",
              );

              toast(
                tr(
                  "已按浏览器位置排序",
                ),
              );
            } catch (e) {
              error(e);
            }
          },

          () =>
            toast(
              tr(
                "定位未成功，请允许定位权限或选择预置区域",
              ),
            ),

          {
            timeout:
              10000,
          },
        );

      break;

    case "help":
      modal(
        tr(
          "使用帮助",
        ),

        trHtml`
          <div class="help-list">

            <p>
              <b>
                扫码充电
              </b>

              管理员可以在电桩管理查看每个设备二维码。
              手机扫描后登录用户账号，
              系统会自动识别该设备。
            </p>

            <p>
              <b>
                分时计价
              </b>

              管理员在价格管理维护电费与服务费；
              开始充电时锁定当前时段价格。
            </p>

            <p>
              <b>
                故障处理
              </b>

              登记故障后设备变为故障，
              进入处理中时变为维修中，
              解决后恢复空闲。
            </p>

          </div>
        `,
      );

      break;
  }
}

function wgsToGcj(
  lat,
  lng,
) {
  if (
    lng < 72.004 ||
    lng > 137.8347 ||
    lat < 0.8293 ||
    lat > 55.8271
  ) {
    return [
      lat,
      lng,
    ];
  }

  const pi =
      Math.PI,

    x =
      lng -
      105,

    y =
      lat -
      35;

  let a =
      -100 +
      2 * x +
      3 * y +
      0.2 * y * y +
      0.1 * x * y +
      0.2 *
        Math.sqrt(
          Math.abs(x),
        ),

    b =
      300 +
      x +
      2 * y +
      0.1 * x * x +
      0.1 * x * y +
      0.1 *
        Math.sqrt(
          Math.abs(x),
        );

  a +=
    (
      (
        20 *
          Math.sin(
            6 *
              x *
              pi,
          ) +
        20 *
          Math.sin(
            2 *
              x *
              pi,
          )
      ) *
      2
    ) /
      3 +
    (
      (
        20 *
          Math.sin(
            y *
              pi,
          ) +
        40 *
          Math.sin(
            (
              y *
              pi
            ) /
              3,
          )
      ) *
      2
    ) /
      3 +
    (
      (
        160 *
          Math.sin(
            (
              y *
              pi
            ) /
              12,
          ) +
        320 *
          Math.sin(
            (
              y *
              pi
            ) /
              30,
          )
      ) *
      2
    ) /
      3;

  b +=
    (
      (
        20 *
          Math.sin(
            6 *
              x *
              pi,
          ) +
        20 *
          Math.sin(
            2 *
              x *
              pi,
          )
      ) *
      2
    ) /
      3 +
    (
      (
        20 *
          Math.sin(
            x *
              pi,
          ) +
        40 *
          Math.sin(
            (
              x *
              pi
            ) /
              3,
          )
      ) *
      2
    ) /
      3 +
    (
      (
        150 *
          Math.sin(
            (
              x *
              pi
            ) /
              12,
          ) +
        300 *
          Math.sin(
            (
              x *
              pi
            ) /
              30,
          )
      ) *
      2
    ) /
      3;

  const r =
      (
        lat /
        180
      ) *
      pi,

    m =
      1 -
      0.00669342162296594323 *
        Math.sin(r) **
          2,

    q =
      Math.sqrt(m);

  return [
    lat +
      (
        a *
        180
      ) /
        (
          (
            (
              6378245 *
              (
                1 -
                0.00669342162296594323
              )
            ) /
            (
              m *
              q
            )
          ) *
          pi
        ),

    lng +
      (
        b *
        180
      ) /
        (
          (
            6378245 /
            q
          ) *
          Math.cos(r) *
          pi
        ),
  ];
}

document.addEventListener(
  "click",

  async (e) => {
    const b =
      e.target.closest(
        "[data-action],[data-page]",
      );

    if (!b) {
      return;
    }

    e.preventDefault();

    if (
      b.disabled
    ) {
      return;
    }

    b.disabled =
      true;

    try {
      if (
        b.dataset.page
      ) {
        await go(
          b.dataset.page,
        );
      } else {
        await act(
          b.dataset.action,
          b,
        );
      }
    } catch (err) {
      error(err);
    } finally {
      b.disabled =
        false;
    }
  },
);

document.addEventListener(
  "submit",

  async (e) => {
    e.preventDefault();

    const f =
        e.target,

      b =
        $(
          "[type=submit]",
          f,
        );

    if (!b) {
      return;
    }

    b.disabled =
      true;

    const d =
      Object.fromEntries(
        new FormData(
          f,
        ),
      );

    try {
      switch (f.id) {
        case "agent-form":
          await sendAgentMessage(
            d.message,
          );
          break;
        
        case "auth-form": {
          const r =
            await api(
              f.dataset.register ===
              "true"
                ? "/register"
                : "/login",

              "POST",

              d,
            );

          S.user =
            r.user;

          S.csrf =
            r.csrf;

          await afterLogin();

          break;
        }

        case "recharge-form":
          await api(
            "/wallet/recharge",
            "POST",
            d,
          );

          await refresh();

          await go(
            S.page,
            S.pageId,
          );

          toast(
            tr(
              "模拟充值成功，余额已更新",
            ),
          );

          break;

        case "profile-form":
          await api(
            "/profile",
            "POST",
            d,
          );

          await refresh();

          await go(
            "profile",
          );

          toast(
            tr(
              "资料已保存",
            ),
          );

          break;

        case "password-form":
          await api(
            "/profile/password",
            "POST",
            d,
          );

          f.reset();

          toast(
            tr(
              "密码已更新",
            ),
          );

          break;

        case "station-form":
          d.lng =
            Number(
              d.lng,
            );

          d.lat =
            Number(
              d.lat,
            );

          await api(
            "/admin/stations" +
              (
                f.dataset.id
                  ? "/" +
                    f.dataset.id
                  : ""
              ),

            "POST",

            d,
          );

          await go(
            "stations",
          );

          toast(
            tr(
              "电站已保存",
            ),
          );

          break;

        case "charger-form":
          d.station_id =
            Number(
              d.station_id,
            );

          d.power =
            Number(
              d.power,
            );

          await api(
            "/admin/chargers" +
              (
                f.dataset.id
                  ? "/" +
                    f.dataset.id
                  : ""
              ),

            "POST",

            d,
          );

          await go(
            "chargers",
          );

          toast(
            tr(
              "电桩已保存",
            ),
          );

          break;

        case "pricing-form":
          d.station_id =
            Number(
              d.station_id,
            );

          await api(
            "/admin/pricing" +
              (
                f.dataset.id
                  ? "/" +
                    f.dataset.id
                  : ""
              ),

            "POST",

            d,
          );

          S.pricingStation =
            d.station_id;

          await go(
            "pricing",
          );

          toast(
            tr(
              "分时价格已保存",
            ),
          );

          break;

        case "fault-form":
          d.charger_id =
            Number(
              d.charger_id,
            );

          await api(
            "/admin/faults",
            "POST",
            d,
          );

          await go(
            "faults",
          );

          toast(
            tr(
              "故障已登记",
            ),
          );

          break;

        case "fault-process-form":
          await api(
            "/admin/faults/" +
              f.dataset.id,

            "POST",

            d,
          );

          await go(
            "faults",
          );

          toast(
            tr(
              "故障状态已更新",
            ),
          );

          break;
      }
    } catch (err) {
      if (
        f.id ===
        "auth-form"
      ) {
        $(
          ".form-error",
          f,
        ).textContent =
          err.message;
      } else {
        error(err);
      }
    } finally {
      b.disabled =
        false;
    }
  },
);

function filterOrders() {
  const q =
      (
        $("#order-search")
          ?.value ||
        ""
      ).toLowerCase(),

    s =
      $("#order-status")
        ?.value;

  $("#orders-table")
    .innerHTML =
      ordersTable(
        S.orders.filter(
          (o) =>
            (
              !s ||
              o.status ===
                s
            ) &&
            `${
              o.id
            } ${
              o.station_name
            } ${
              o.nickname
            }`
              .toLowerCase()
              .includes(
                q,
              ),
        ),
      );
}

function sortedChargers() {
  const sort =
    $("#charger-sort")
      ?.value ||
    "number_asc";

  const chargers = [
    ...S.chargers,
  ];

  if (
    sort ===
    "count_desc"
  ) {
    chargers.sort(
      (a, b) =>
        b.total_count -
        a.total_count,
    );
  } else if (
    sort ===
    "count_asc"
  ) {
    chargers.sort(
      (a, b) =>
        a.total_count -
        b.total_count,
    );
  } else {
    chargers.sort(
      (a, b) =>
        a.number.localeCompare(
          b.number,
        ),
    );
  }

  return chargers;
}

function filterChargers() {
  const q =
      (
        $("#charger-search")
          ?.value ||
        ""
      ).toLowerCase(),

    status =
      $("#charger-status")
        ?.value ||
      "",

    kind =
      $("#charger-kind")
        ?.value ||
      "",

    station =
      $("#charger-station")
        ?.value ||
      "";

  const result =
    sortedChargers()
      .filter(
        (c) =>
          (
            !status ||
            c.status ===
              status
          ) &&
          (
            !kind ||
            c.kind ===
              kind
          ) &&
          (
            !station ||
            String(
              c.station_id,
            ) ===
              station
          ) &&
          `${
            c.number
          } ${
            c.station_name
          }`
            .toLowerCase()
            .includes(q),
      );

  $("#chargers-table")
    .innerHTML =
      chargersTable(
        result,
      );
}

document.addEventListener(
  "input",

  (e) => {
    if (
      e.target
        .setCustomValidity
    ) {
      e.target
        .setCustomValidity(
          "",
        );
    }

    if (
      e.target.id ===
      "station-search"
    ) {
      const q =
        e.target.value
          .toLowerCase();

      $("#station-list")
        .innerHTML =
          S.stations
            .filter(
              (s) =>
                (
                  s.name +
                  s.address +
                  s.city
                )
                  .toLowerCase()
                  .includes(
                    q,
                  ),
            )
            .map(
              stationCard,
            )
            .join("") ||
          empty(
            tr(
              "没有匹配的电站",
            ),
          );
    }

    if (
      e.target.id ===
      "order-search"
    ) {
      filterOrders();
    }

    if (
      e.target.id ===
      "charger-search"
    ) {
      filterChargers();
    }
  },
);

document.addEventListener(
  "change",

  async (e) => {
    try {
      if (
        e.target.dataset
          .pref
      ) {
        await changePreference(
          e.target.dataset
            .pref,

          e.target.value,
        );

        return;
      }

      if (
        e.target.id ===
        "region"
      ) {
        const rs = {
          海淀区: [
            39.9593,
            116.2981,
          ],

          东城区: [
            39.9042,
            116.4074,
          ],

          朝阳区: [
            39.9219,
            116.4435,
          ],

          丰台区: [
            39.8584,
            116.2869,
          ],

          石景山区: [
            39.9062,
            116.2229,
          ],
        };

        if (
          !rs[
            e.target.value
          ]
        ) {
          return;
        }

        [
          S.lat,
          S.lng,
        ] =
          rs[
            e.target.value
          ];

        S.location =
          e.target.value;

        await go(
          "stations",
        );

        toast(
          tr(
            "已切换为区域预置位置",
          ),
        );
      }

      if (
        e.target.id ===
        "station-status"
      ) {
        S.stationFilter.status =
          e.target.value;

        await loadStations();
      }

      if (
        e.target.id ===
        "station-sort"
      ) {
        S.stationFilter.sort =
          e.target.value;

        await loadStations();
      }

      if (
        e.target.id ===
        "charger-filter-status"
      ) {
        S.chargerFilter.status =
          e.target.value;

        renderStationChargers();
      }

      if (
        e.target.id ===
        "charger-filter-kind"
      ) {
        S.chargerFilter.kind =
          e.target.value;

        renderStationChargers();
      }

      if (
        e.target.id ===
        "charger-filter-sort"
      ) {
        S.chargerFilter.sort =
          e.target.value;

        renderStationChargers();
      }

      if (
        e.target.id ===
        "order-status"
      ) {
        filterOrders();
      }

      if (
        e.target.id ===
        "order-from"
      ) {
        S.orderFrom =
          e.target.value;

        await loadOrders();
      }

      if (
        e.target.id ===
        "order-to"
      ) {
        S.orderTo =
          e.target.value;

        await loadOrders();
      }

      if (
        [
          "charger-status",
          "charger-station",
          "charger-kind",
          "charger-sort",
        ].includes(
          e.target.id,
        )
      ) {
        filterChargers();
      }

      if (
        e.target.id ===
        "user-status"
      ) {
        S.userFilter.status =
          e.target.value;

        await loadUsers();
      }

      if (
        e.target.id ===
        "user-from"
      ) {
        S.userFilter.from =
          e.target.value;

        await loadUsers();
      }

      if (
        e.target.id ===
        "user-to"
      ) {
        S.userFilter.to =
          e.target.value;

        await loadUsers();
      }

      if (
        e.target.id ===
        "user-sort"
      ) {
        S.userFilter.sort =
          e.target.value;

        await loadUsers();
      }

      if (
        e.target.classList
          .contains(
            "role-select",
          )
      ) {
        await api(
          "/admin/users/" +
            e.target.dataset
              .userId +
            "/role",
          "POST",
          {
            role:
              e.target.value,
          },
        );

        await refresh();

        await go(
          "users",
        );

        toast(
          tr(
            "角色已更新，新的权限立即生效",
          ),
        );
      }

      if (
        e.target.id ===
        "prediction-station"
      ) {
        S.predictionStation =
          Number(
            e.target.value,
          );

        await go(
          "prediction",
        );
      }

      if (
        e.target.id ===
        "pricing-station"
      ) {
        S.pricingStation =
          Number(
            e.target.value,
          );

        await go(
          "pricing",
        );
      }
    } catch (err) {
      error(err);
    }
  },
);

document.addEventListener(
  "keydown",

  async (e) => {
    if (
      e.target.id !==
      "agent-input"
    ) {
      return;
    }

    if (
      e.key !==
      "Enter"
      ||
      e.shiftKey
    ) {
      return;
    }

    e.preventDefault();

    await sendAgentMessage(
      e.target.value,
    );
  },
);

async function boot() {
  try {
    await NCSPreferences.ready;

    const s =
      await api(
        "/session",
      );

    S.csrf =
      s.csrf;

    S.user =
      s.user;

    S.scale =
      s.time_scale;

    if (s.user) {
      await afterLogin();
    } else {
      loginView();
    }
  } catch (e) {
    $("#app").innerHTML =
      empty(
        esc(
          e.message,
        ) +
          tr(
            "<br>请确认 Python 服务已启动，然后刷新页面。",
          ),
      );
  }
}

function preferenceControls() {
  const p =
    NCSPreferences.state;

  return `
    <div
      class="preference-controls"
      role="group"
      aria-label="${tr(
        "语言与外观",
      )}"
    >

      <select
        data-pref="language"
        aria-label="${tr(
          "语言",
        )}"
      >
        ${opt(
          "zh",
          "中文",
          p.language,
        )}

        ${opt(
          "en",
          "English",
          p.language,
        )}
      </select>

      <select
        data-pref="theme"
        aria-label="${tr(
          "外观",
        )}"
      >
        ${opt(
          "system",
          tr(
            "跟随系统",
          ),
          p.theme,
        )}

        ${opt(
          "light",
          tr(
            "浅色",
          ),
          p.theme,
        )}

        ${opt(
          "dark",
          tr(
            "深色",
          ),
          p.theme,
        )}
      </select>

    </div>
  `;
}

function preferencesCard() {
  return `
    <section
      class="
        card
        preferences-card
      "
    >

      <div class="section-head">

        <div>
          <h2>
            ${tr(
              "偏好设置",
            )}
          </h2>

          <p class="sub">
            ${tr(
              "界面语言和外观会自动保存，重新登录后继续使用。",
            )}
          </p>
        </div>

        ${preferenceControls()}

      </div>

      <p class="sub">
        ${tr(
          "跟随设备的浅色或深色设置；你也可以固定选择喜欢的主题。",
        )}
      </p>

      <p
        class="preferences-message"
        role="status"
      ></p>

    </section>
  `;
}

function openPreferences() {
  modal(
    tr(
      "语言与外观",
    ),

    preferencesCard(),
  );
}

async function adoptAccountPreferences() {
  if (
    S.user?.preferences
  ) {
    NCSPreferences.set(
      S.user.preferences,
    );
  } else if (S.user) {
    try {
      const r =
        await api(
          "/preferences",
          "POST",
          {
            ...NCSPreferences
              .state,
          },
        );

      S.user.preferences =
        r.preferences;
    } catch (_) {
      S.preferenceSyncFailed =
        true;
    }
  }
}

let preferenceQueue =
  Promise.resolve();

function captureForms() {
  return [
    ...document.querySelectorAll(
      "form",
    ),
  ].map(
    (form) => ({
      id: form.id,

      fields: [
        ...form.elements,
      ]
        .filter(
          (e) =>
            e.name &&
            !e.dataset.pref,
        )
        .map(
          (e) => ({
            name:
              e.name,

            value:
              e.value,

            checked:
              e.checked,
          }),
        ),
    }),
  );
}

function restoreForms(forms) {
  for (
    const saved
    of forms
  ) {
    const form =
      document.getElementById(
        saved.id,
      );

    if (!form) {
      continue;
    }

    for (
      const f
      of saved.fields
    ) {
      const el =
        form.elements
          .namedItem(
            f.name,
          );

      if (!el) {
        continue;
      }

      el.value =
        f.value;

      if (
        "checked" in el
      ) {
        el.checked =
          f.checked;
      }
    }

    if (
      saved.id ===
      "profile-form"
    ) {
      const color =
        form.elements
          .namedItem(
            "avatar",
          )
          ?.value;

      form
        .querySelectorAll(
          ".theme-choice",
        )
        .forEach(
          (b) =>
            b.classList.toggle(
              "selected",
              b.dataset.color ===
                color,
            ),
        );
    }
  }
}

function syncPreferenceControls() {
  document
    .querySelectorAll(
      "[data-pref]",
    )
    .forEach(
      (el) =>
        (
          el.value =
            NCSPreferences
              .state[
              el.dataset.pref
            ]
        ),
    );
}

async function redrawLanguage() {
  const forms =
      captureForms(),

    scroll =
      window.scrollY;

  const settingsOpen =
    $("#modal").open &&
    !!$(
      "#modal .preferences-card",
    );

  if (S.user) {
    await go(
      S.page,
      S.pageId,
    );
  } else {
    loginView(
      S.registering,
    );
  }

  restoreForms(
    forms,
  );

  if (settingsOpen) {
    openPreferences();
  }

  window.scrollTo(
    0,
    scroll,
  );
}

async function changePreference(
  key,
  value,
) {
  const previous =
    NCSPreferences
      .state
      .language;

  NCSPreferences.set({
    [key]:
      value,
  });

  if (
    previous !==
    NCSPreferences
      .state
      .language
  ) {
    await redrawLanguage();
  } else {
    syncPreferenceControls();
  }

  const snapshot = {
      ...NCSPreferences
        .state,
    },

    uid =
      S.user?.id;

  preferenceQueue =
    preferenceQueue
      .catch(
        () => {},
      )
      .then(
        async () => {
          if (
            !uid ||
            S.user?.id !==
              uid
          ) {
            return;
          }

          try {
            const r =
              await api(
                "/preferences",
                "POST",
                snapshot,
              );

            if (
              S.user?.id ===
              uid
            ) {
              S.user.preferences =
                r.preferences;
            }

            S.preferenceSyncFailed =
              false;

            document
              .querySelectorAll(
                ".preferences-message",
              )
              .forEach(
                (el) =>
                  (
                    el.textContent =
                      tr(
                        "偏好已保存",
                      )
                  ),
              );
          } catch (e) {
            S.preferenceSyncFailed =
              true;

            const msg =
              tr(
                "偏好已保存在此浏览器，账号同步失败，请稍后重试",
              );

            document
              .querySelectorAll(
                ".preferences-message",
              )
              .forEach(
                (el) =>
                  (
                    el.textContent =
                      msg
                  ),
              );

            if (
              !document.querySelector(
                ".preferences-message",
              )
            ) {
              toast(msg);
            }
          }
        },
      );

  await preferenceQueue;
}

window.addEventListener(
  "ncs-preferences-external",

  async () => {
    if (
      !document.querySelector(
        ".login-screen,.shell",
      )
    ) {
      return;
    }

    try {
      await redrawLanguage();
    } catch (e) {
      error(e);
    }
  },
);

document.addEventListener(
  "invalid",

  (e) => {
    const el =
      e.target;

    if (
      !el.validity ||
      !el.setCustomValidity
    ) {
      return;
    }

    el.setCustomValidity(
      "",
    );

    const v =
      el.validity;

    const message =
      v.valueMissing
        ? "必填项"
        : v.badInput
          ? "请输入有效的数值"
          : v.rangeUnderflow ||
              v.rangeOverflow
            ? "数值超出允许范围"
            : v.tooShort
              ? "请输入足够长度的内容"
              : "输入格式不正确";

    if (!v.valid) {
      el.setCustomValidity(
        tr(message),
      );
    }
  },

  true,
);

boot();
