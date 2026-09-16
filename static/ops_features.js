(function(){
  'use strict';

  const FEATURE_PAGE = 'ops-center';

  const esc0 =
    window.esc ||
    (v =>
      String(v ?? '').replace(
        /[&<>"']/g,
        c => ({
          '&':'&amp;',
          '<':'&lt;',
          '>':'&gt;',
          '"':'&quot;',
          "'":'&#39;'
        }[c])
      )
    );

  const yuan0 =
    window.yuan ||
    (c => (Number(c || 0) / 100).toFixed(2));

  const time0 =
    window.time ||
    (s =>
      s
        ? String(s).replace('T',' ').slice(0,19)
        : '—'
    );

  const api0 = window.api;

  const tr0 = (value) => {
    try {
      if (typeof tr === 'function') {
        return tr(value);
      }
    } catch (_) {}

    return value;
  };

  const translateOperation0 = (value) => {
    const text = String(value ?? '');
    if (window.NCSPreferences?.state?.language !== 'en') {
      return tr0(text);
    }

    const statusNames = {
      pending: "Pending",
      processing: "In progress",
      resolved: "Resolved",
      fault: "Fault",
      maintenance: "Maintenance",
      offline: "Offline",
      idle: "Idle",
      charging: "Charging",
    };

    let match;

    match =
      text.match(
        /^更新故障\s*#?(\d+):\s*([a-z]+)$/i,
      );

    if (match) {
      return (
        `Updated fault #${match[1]}: ` +
        `${statusNames[match[2]] || match[2]}`
      );
    }

    match =
      text.match(
        /^电桩\s*#?(\d+):\s*([a-z]+)$/i,
      );

    if (match) {
      return (
        `Charger #${match[1]}: ` +
        `${statusNames[match[2]] || match[2]}`
      );
    }

    const rules = [
      [/^创建数据库备份(?:\s+)?(.+)?$/, 'Created database backup'],
      [/^启用用户(?:\s+)?(.+)$/, 'Enabled user'],
      [/^冻结用户(?:\s+)?(.+)$/, 'Frozen user'],
      [/^删除用户(?:\s+)?(.+)$/, 'Deleted user'],
      [/^更新用户(?:\s+)?(.+)$/, 'Updated user'],
      [/^禁用用户(?:\s+)?(.+)$/, 'Disabled user'],
    ];

    for (const [pattern, prefix] of rules) {
      const match = text.match(pattern);
      if (match) {
        return match[1] ? `${prefix} ${match[1]}` : prefix;
      }
    }

    return tr0(text);
  };

  function notificationCopy0(n) {
  const title =
    String(
      n?.title || ""
    );

  const body =
    String(
      n?.body || ""
    );

  if (
    window.NCSPreferences
      ?.state
      ?.language !== "en"
  ) {
    return {
      title,
      body,
    };
  }

  if (
    n?.kind === "fault"
  ) {
    const match =
      body.match(
        /^(.*) · ([^·]+) 当前状态：([a-z]+)。$/,
      );

    if (match) {
      const statusNames = {
        pending: "Pending",
        processing: "In progress",
        resolved: "Resolved",
        fault: "Fault",
        maintenance: "Maintenance",
        offline: "Offline",
      };

      return {
        title:
          "Device fault requires attention",

        body:
          `${tr0(match[1])} · ${match[2]} — ` +
          `Status: ${
            statusNames[
              match[3]
            ] ||
            match[3]
          }.`,
      };
    }
  }

  return {
    title:
      tr0(title),

    body:
      tr0(body),
  };
}

  const toast0 =
    window.toast ||
    (() => {});

  function fmtDuration(sec){
    sec = Math.max(0, Number(sec || 0));

    const d = Math.floor(sec / 86400);
    sec %= 86400;

    const h = Math.floor(sec / 3600);
    sec %= 3600;

    const m = Math.floor(sec / 60);

    const isEn = window.NCSPreferences?.state?.language === "en";
    return d
      ? isEn
        ? `${d} days ${h} hours`
        : `${d}${tr0("天")} ${h}${tr0("小时")}`
      : isEn
        ? `${h} hours ${m} minutes`
        : `${h}${tr0("小时")} ${m}${tr0("分钟")}`;
  }

  function pct(v){
    return `${Math.max(
      0,
      Math.min(100, Number(v || 0))
    ).toFixed(1)}%`;
  }

  function healthClass(ok, value, warnAt){
    if(!ok){
      return 'bad';
    }

    if(
      warnAt != null &&
      Number(value || 0) >= warnAt
    ){
      return 'warn';
    }

    return 'ok';
  }

  function kpi(title, value, unit, icon){
    return `
      <section class="card ops-card">
        <div class="ops-kpi">

          <div>
            <small>
              ${esc0(tr0(title))}
            </small>

            <strong>
              ${esc0(value)}
              <em>
                ${esc0(tr0(unit || ''))}
              </em>
            </strong>
          </div>

          <div class="ops-icon">
            ${icon || '◌'}
          </div>

        </div>
      </section>
    `;
  }

  function table(headers, rows){
    return `
      <div class="ops-table-wrap">

        <table class="ops-table">

          <thead>
            <tr>
              ${headers
                .map(h => `<th>${esc0(tr0(h))}</th>`)
                .join('')}
            </tr>
          </thead>

          <tbody>

            ${
              rows.join('') ||
              `
                <tr>
                  <td colspan="${headers.length}">
                    <div class="ops-empty">
                      ${tr0('暂无数据')}
                    </div>
                  </td>
                </tr>
              `
            }

          </tbody>

        </table>

      </div>
    `;
  }

  /*
   * Jiaqi's latest app.js keeps S as a top-level
   * lexical variable rather than window.S.
   *
   * The native app.js and this file are both classic
   * scripts, so we can safely try to access S.
   */
  function getSessionUser(){

    try{
      if(
        typeof S !== 'undefined' &&
        S &&
        S.user
      ){
        return S.user;
      }
    }catch(_){}

    try{
      if(
        window.S &&
        window.S.user
      ){
        return window.S.user;
      }
    }catch(_){}

    /*
     * Fallback for environments where S is not
     * accessible from this script.
     */
    try{

      const badge =
        document.querySelector('.top-right');

      const text =
        badge
          ? badge.textContent
          : '';

      if(
        text.includes(tr0('系统管理员'))
      ){
        return {
          role:'admin',
          nickname:tr0('系统管理员')
        };
      }

      if(
        text.includes(tr0('运营人员'))
      ){
        return {
          role:'operator',
          nickname:tr0('运营人员')
        };
      }

      if(
        text.includes(tr0('维护人员')) ||
        text.includes(tr0('技术员'))
      ){
        return {
          role:'technician',
          nickname:tr0('维护人员')
        };
      }

    }catch(_){}

    return null;
  }

  function navAllowed(){

    const user =
      getSessionUser();

    return !!user &&
      user.role !== 'user';
  }

  async function fetchJson(path){

    if(
      typeof api0 !== 'function'
    ){
      throw new Error(
        'NCS API helper is unavailable'
      );
    }

    return api0(path);
  }

  async function renderHealth(){

    const h =
      await fetchJson(
        '/admin/ops/health'
      );

    const mem =
      h.memory || {};

    const disk =
      h.disk || {};

    const load =
      h.load || {};

    const dbOk =
      h.database === 'ok';

    return `
      <div class="ops-grid">

        ${kpi(
          tr0('数据库'),
          tr0('正常'),
          '',
          '●'
        )}

        ${kpi(
          tr0('数据库延迟'),
          h.database_latency_ms,
          'ms',
          '↯'
        )}

        ${kpi(
          tr0('进程内存'),
          h.process_memory_mb,
          'MB',
          '▦'
        )}

        ${kpi(
          tr0('运行时长'),
          fmtDuration(
            h.process_uptime_seconds
          ),
          '',
          '◷'
        )}

      </div>

      <section class="card ops-card">

        <div class="ops-section-head">

          <div>

            <h2>
              ${tr0("系统健康")}
            </h2>

            <p class="ops-mini">
              ${tr0("实时读取 ECS / 容器内应用运行状态；")}
              ${tr0("不依赖额外监控服务。")}
            </p>

          </div>

          <span
            class="ops-pill ${
              dbOk
                ? 'success'
                : 'danger'
            }"
          >
            ${
              dbOk
                ? tr0('● 正常')
                : tr0('● 异常')
            }
          </span>

        </div>

        <div class="ops-health-row">

          <div class="ops-health-item">

            <small>
              ${tr0("数据库")}
            </small>

            <div
              class="ops-status ${
                dbOk
                  ? 'ok'
                  : 'bad'
              }"
            >
              ${
                dbOk
                  ? tr0('连接正常')
                  : tr0('连接失败')
              }
            </div>

            <div class="ops-mini">
              ${h.db_backend || 'sqlite'}
              ·
              ${h.database_latency_ms}
              ms
            </div>

          </div>

          <div class="ops-health-item">

            <small>
              ${tr0("系统内存")}
            </small>

            <div
              class="ops-status ${
                healthClass(
                  true,
                  mem.used_pct,
                  85
                )
              }"
            >
              ${pct(mem.used_pct)}
              ${tr0("已使用")}
            </div>

            <div class="ops-meter">
              <i
                style="
                  width:${Math.min(
                    100,
                    Number(
                      mem.used_pct || 0
                    )
                  )}%
                "
              ></i>
            </div>

            <div class="ops-mini">
              ${tr0("可用")}
              ${Number(
                mem.available_mb || 0
              ).toFixed(1)}
              MB /
              ${tr0("总计")}
              ${Number(
                mem.total_mb || 0
              ).toFixed(1)}
              MB
            </div>

          </div>

          <div class="ops-health-item">

            <small>
              ${tr0("磁盘")}
            </small>

            <div
              class="ops-status ${
                healthClass(
                  true,
                  disk.used_pct,
                  85
                )
              }"
            >
              ${pct(disk.used_pct)}
              ${tr0("已使用")}
            </div>

            <div class="ops-meter">
              <i
                style="
                  width:${Math.min(
                    100,
                    Number(
                      disk.used_pct || 0
                    )
                  )}%
                "
              ></i>
            </div>

            <div class="ops-mini">
              ${tr0("可用")}
              ${Number(
                disk.free_gb || 0
              ).toFixed(2)}
              GB
            </div>

          </div>

        </div>

        <div class="ops-health-row">

          <div class="ops-health-item">

            <small>
              Python
            </small>

            <div class="ops-status ok">
              ${esc0(
                h.python || '—'
              )}
            </div>

            <div class="ops-mini">
              PID
              ${esc0(
                h.pid || '—'
              )}
            </div>

          </div>

          <div class="ops-health-item">

            <small>
              ${tr0("系统负载 1m")}
            </small>

            <div
              class="ops-status ${
                healthClass(
                  true,
                  load['1m'],
                  2
                )
              }"
            >
              ${esc0(
                load['1m'] || 0
              )}
            </div>

            <div class="ops-mini">
              5m
              ${esc0(
                load['5m'] || 0
              )}
              ·
              15m
              ${esc0(
                load['15m'] || 0
              )}
            </div>

          </div>

          <div class="ops-health-item">

            <small>
              ${tr0("最近检查")}
            </small>

            <div class="ops-status ok">
              ${tr0("已完成")}
            </div>

            <div class="ops-mini">
              ${esc0(
                time0(h.timestamp)
              )}
            </div>

          </div>

        </div>

      </section>
    `;
  }

  async function renderAnalytics(){

    const a =
      await fetchJson(
        '/admin/ops/analytics?days=28'
      );

    const s =
      a.summary || {};

    const ub =
      a.user_behavior || {};

    const peak =
      a.peak_hour || {};

    const rows =
      (a.station_utilization || [])
        .map(x => `
          <tr>

            <td>
              <b>
                ${esc0(
                  tr0(
                    x.station_name
                  )
                )}
              </b>
            </td>

            <td>
              ${x.chargers}
            </td>

            <td>
              <span class="ops-pill">
                ${tr0("快")} ${x.fast}
              </span>

              <span class="ops-pill">
                ${tr0("慢")} ${x.slow}
              </span>
            </td>

            <td>
              ${x.orders}
            </td>

            <td>
              ${Number(
                x.energy_kwh || 0
              ).toFixed(2)}
              kWh
            </td>

            <td>
              ¥
              ${yuan0(
                x.revenue_cents
              )}
            </td>

            <td>
              <b>
                ${Number(
                  x.utilization_pct || 0
                ).toFixed(1)}%
              </b>
            </td>

            <td>
              ${Number(
                x.avg_session_minutes || 0
              ).toFixed(1)}
              min
            </td>

          </tr>
        `);

    const top =
      (a.top_stations || [])
        .slice(0,5)
        .map((x,i) => `
          <tr>

            <td>
              #${i + 1}
            </td>

            <td>
              <b>
                ${esc0(
                  tr0(
                    x.station_name
                  )
                )}
              </b>
            </td>

            <td>
              <b>
                ${Number(
                  x.utilization_pct || 0
                ).toFixed(1)}%
              </b>
            </td>

            <td>
              ${x.orders}
            </td>

            <td>
              ¥
              ${yuan0(
                x.revenue_cents
              )}
            </td>

          </tr>
        `);

    const hourly =
      (a.hourly || [])
        .map(x => `
          <tr>

            <td>
              ${String(
                x.hour
              ).padStart(2,'0')}:00
            </td>

            <td>
              ${x.orders}
            </td>

            <td>
              ${Number(
                x.energy_kwh || 0
              ).toFixed(2)}
              kWh
            </td>

            <td>
              ${Number(
                x.charging_minutes || 0
              ).toFixed(1)}
              min
            </td>

          </tr>
        `);

    const avgUtilization =
      (
        (a.station_utilization || [])
          .reduce(
            (sum,x) =>
              sum +
              Number(
                x.utilization_pct || 0
              ),
            0
          )
        /
        Math.max(
          (a.station_utilization || [])
            .length,
          1
        )
      ).toFixed(1);

    return `

      <div class="ops-grid">

        ${kpi(
          tr0('近 28 天订单'),
          s.orders,
          '笔',
          '▤'
        )}

        ${kpi(
          tr0('充电电量'),
          s.energy_kwh,
          'kWh',
          '⚡'
        )}

        ${kpi(
          tr0('实收营收'),
          '¥ ' +
            yuan0(
              s.revenue_cents
            ),
          '',
          '￥'
        )}

        ${kpi(
          tr0('平均利用率'),
          avgUtilization,
          '%',
          '◒'
        )}

      </div>

      <section class="ops-banner">

        <div>

          <strong>
            ${tr0("峰值时段")}
            ${String(
              peak.hour ?? 0
            ).padStart(2,'0')}:00
          </strong>

<p>
  ${tr0("共")}
  ${peak.orders || 0}
  ${tr0("笔订单；")}
  ${tr0("可用于容量与负荷预测的运营依据。")}
</p>

        </div>

        <span class="ops-pill">
          ${tr0("活跃用户")}
          ${ub.sessions_users || 0}
        </span>

      </section>

      <section class="card ops-card">

        <div class="ops-section-head">

          <div>

            <h2>
              ${tr0("电站利用率分析")}
            </h2>

            <p class="ops-mini">
              ${tr0("按近 28 天已完成订单的实际充电分钟数")}
              ${tr0("÷ 电桩可服务分钟数计算。")}
            </p>

          </div>

        </div>

        ${table(
          [
            '电站',
            '电桩',
            '类型',
            '订单',
            '电量',
            '实收',
            '利用率',
            '平均时长'
          ],
          rows
        )}

      </section>

      <div
        class="ops-grid"
        style="grid-template-columns:1.25fr 1fr"
      >

        <section class="card ops-card">

          <div class="ops-section-head">

            <div>

              <h3>
                ${tr0("利用率 Top 5")}
              </h3>

              <p class="ops-mini">
                ${tr0("优先关注高负载站点。")}
              </p>

            </div>

          </div>

          ${table(
            [
              '排名',
              '电站',
              '利用率',
              '订单',
              '实收'
            ],
            top
          )}

        </section>

        <section class="card ops-card">

          <div class="ops-section-head">

            <div>

              <h3>
                ${tr0("用户行为")}
              </h3>

              <p class="ops-mini">
                ${tr0("回访与消费概况。")}
              </p>

            </div>

          </div>

          ${table(
            [
              '指标',
              '值'
            ],
            [
              `
                <tr>
                  <td>
                    ${tr0("人均订单")}
                  </td>
                  <td>
                    <b>
                      ${
                        ub.avg_sessions_per_user ||
                        0
                      }
                    </b>
                  </td>
                </tr>
              `,
              `
                <tr>
                  <td>
                    ${tr0("人均电量")}
                  </td>
                  <td>
                    <b>
                      ${
                        ub.avg_energy_per_user_kwh ||
                        0
                      }
                      kWh
                    </b>
                  </td>
                </tr>
              `,
              `
                <tr>
                  <td>
                    ${tr0("人均消费")}
                  </td>
                  <td>
                    <b>
                      ¥
                      ${yuan0(
                        ub.avg_spend_per_user_cents ||
                        0
                      )}
                    </b>
                  </td>
                </tr>
              `,
              `
                <tr>
                  <td>
                    ${tr0("回访用户")}
                  </td>
                  <td>
                    <b>
                      ${
                        ub.returning_users ||
                        0
                      }
                    </b>
                  </td>
                </tr>
              `
            ]
          )}

        </section>

      </div>

      <section class="card ops-card">

        <div class="ops-section-head">

          <div>

            <h2>
              ${tr0("24 小时使用分布")}
            </h2>

            <p class="ops-mini">
              ${tr0("订单量、电量和充电时长的时段分布。")}
            </p>

          </div>

        </div>

        ${table(
          [
            '时段',
            '订单',
            '电量',
            '充电时长'
          ],
          hourly
        )}

      </section>

    `;
  }

  async function renderAudit(role){
      if (role === 'technician') {
    return `
      <section class="card ops-card">

        <div class="ops-section-head">

          <div>
            <h2>${tr0("操作审计")}</h2>

            <p class="ops-mini">
              ${tr0("查看增强审计日志需要相应的审计权限。")}
            </p>
          </div>

          <span class="ops-pill warn">
            ${tr0("无访问权限")}
          </span>

        </div>

        <div class="ops-empty">
          ${tr0("当前角色无法查看增强审计日志。")}
        </div>

      </section>
    `;
  }

  try{

    const q =
      new URLSearchParams();

    const qv =
      document.querySelector(
        '#ops-audit-q'
      )?.value || '';

    const actor =
      document.querySelector(
        '#ops-audit-actor'
      )?.value || '';

    const from =
      document.querySelector(
        '#ops-audit-from'
      )?.value || '';

    const to =
      document.querySelector(
        '#ops-audit-to'
      )?.value || '';

    if(qv){
      q.set('q', qv);
    }

    if(actor){
      q.set('actor', actor);
    }

    if(from){
      q.set('date_from', from);
    }

    if(to){
      q.set('date_to', to);
    }

    const data =
      await fetchJson(
        '/admin/ops/audit?' +
        q.toString()
      );

    const rows =
      (data.items || [])
        .map(x => `
          <tr>

            <td>
              #${x.id}
            </td>

            <td>

              <b>
                ${esc0(
                  x.nickname
                    ? tr0(x.nickname)
                    : (
                        tr0("用户 #") +
                        x.actor_id
                      )
                )}
              </b>

              <br>

              <span class="ops-mini">
                ID
                ${esc0(
                  x.actor_id || '—'
                )}
                ·
                ${esc0(
                  x.phone || '—'
                )}
              </span>

            </td>

            <td>
              ${esc0(
                translateOperation0(x.operation)
              )}
            </td>

            <td>
              ${esc0(
                time0(
                  x.created_at
                )
              )}
            </td>

          </tr>
        `);

    const cats =
      Object.entries(
        data.category_counts || {}
      )
        .map(
          ([k,v]) => `
            <span class="ops-pill">
              ${esc0(tr0(k))}
              ${v}
            </span>
          `
        )
        .join(' ');

    return `

      <section class="card ops-card">

        <div class="ops-section-head">

          <div>

            <h2>
              ${tr0("操作审计")}
            </h2>

            <p class="ops-mini">
              ${tr0("支持按操作人、关键词和日期范围查询关键管理行为。")}
            </p>

          </div>

          <div>
            ${
              cats ||
              '<span class="ops-mini">暂无分类</span>'
            }
          </div>

        </div>

        <div class="ops-toolbar">

          <input
            id="ops-audit-q"
            placeholder="${esc0(
              tr0("搜索操作内容")
            )}"
          >

          <input
            id="ops-audit-actor"
            placeholder="${esc0(
              tr0("操作人 ID")
            )}"
          >

          <input
            id="ops-audit-from"
            type="date"
            lang="${
              window.NCSPreferences?.state?.language === "en"
                ? "en"
                : "zh-CN"
            }"
          >

          <input
            id="ops-audit-to"
            type="date"
          >

          <button
            class="btn secondary"
            data-ops-action="audit-search"
          >
            ${tr0("查询")}
          </button>

        </div>

        <div style="height:14px"></div>

        ${table(
[
    tr0('编号'),
    tr0('操作人'),
    tr0('操作内容'),
    tr0('时间')
],
          rows
        )}

      </section>

    `;

  }catch(e){

    /*
     * Audit logs are permission-controlled.
     * A technician/operator without audit.view
     * must not make the entire Operations Center fail.
     */
    return `

      <section class="card ops-card">

        <div class="ops-section-head">

          <div>

            <h2>
              ${tr0("操作审计")}
            </h2>

            <p class="ops-mini">
              ${tr0("查看增强审计日志需要相应的审计权限。")}
            </p>

          </div>

          <span class="ops-pill warn">
            ${tr0("无访问权限")}
          </span>

        </div>

        <div class="ops-empty">

          ${tr0("当前角色无法查看增强审计日志。")}
          <br>

          <span class="ops-mini">
            如需查看，请使用具有 audit.view
            权限的运营人员或管理员账号。
          </span>

        </div>

      </section>

    `;

  }
}

  async function renderNotifications(){

    const d =
      await fetchJson(
        '/notifications'
      );

    const items =
      d.items || [];

    return `

      <section
        class="card ops-card ops-notifications"
      >

        <div class="ops-section-head">

          <div>

            <h2>
              ${tr0("通知中心")}
            </h2>

            <p class="ops-mini">
              ${d.unread || 0}
              ${tr0("条未读通知")} ·
              ${tr0("系统会根据当前业务状态自动生成提醒。")}
            </p>

          </div>

          <button
            class="btn secondary small"
            data-ops-action="read-all"
          >
            ${tr0("全部已读")}
          </button>

        </div>

        ${
          items.map(
            n => {
              const copy =
                notificationCopy0(n);

              return `

              <div class="ops-notify">

                <div
                  class="ops-notify-icon ${esc0(
                    n.level
                  )}"
                >
                  ●
                </div>

                <div class="ops-notify-main">

                  <div class="ops-notify-title">

                    ${esc0(
                      copy.title
                    )}

                    ${
                      n.read
                        ? ''
                        : `
                          <span class="ops-unread">
                            ${tr0("新")}
                          </span>
                        `
                    }

                  </div>

                  <div class="ops-notify-body">
                    ${esc0(
                      copy.body
                    )}
                  </div>

                  <div class="ops-notify-time">
                    ${esc0(
                      time0(
                        n.created_at
                      )
                    )}
                  </div>

                </div>

                ${
                  n.read
                    ? ''
                    : `
                      <button
                        class="btn secondary small"
                        data-ops-read="${esc0(
                          n.id
                        )}"
                      >
                        ${tr0("标记已读")}
                      </button>
                    `
                }

              </div>

            `;
              }
          ).join('') ||
          `
            <div class="ops-empty">
              ${tr0("暂无通知")}
            </div>
          `
        }

      </section>

    `;
  }

  async function renderBackups(role){
      if (role === 'technician') {
    return `
      <section class="card ops-card">

        <div class="ops-section-head">

          <div>
            <h2>${tr0("数据库备份与恢复")}</h2>

            <p class="ops-mini">
              ${tr0("数据备份与恢复需要系统管理员权限。")}
            </p>
          </div>

          <span class="ops-pill warn">
            ${tr0("无访问权限")}
          </span>

        </div>

        <div class="ops-empty">
          ${tr0("当前角色无法执行数据库备份与恢复。")}
        </div>

      </section>
    `;
  }

    let b;

    try{

      b =
        await fetchJson(
          '/admin/ops/backups'
        );

    }catch(e){

      return `

        <section class="card ops-card">

          <h2>
            ${tr0("数据备份")}
          </h2>

          <div class="ops-empty">
            ${esc0(
              e.message
            )}
          </div>

        </section>

      `;
    }

    if(!b.supported){

      return `

        <section class="card ops-card">

          <h2>
            ${tr0("数据备份")}
          </h2>

          <p class="ops-mini">
            ${tr0("当前数据库后端为")}
            ${esc0(
              b.backend
            )}，
            ${tr0("本页面仅提供 SQLite 文件备份；")}
            ${tr0("MySQL 请使用数据库原生备份。")}
          </p>

        </section>

      `;
    }

    const rows =
      (b.items || [])
        .map(x => `

          <tr>

            <td>
              <b>
                ${esc0(
                  x.filename
                )}
              </b>
            </td>

            <td>
              ${(
                Number(
                  x.size_bytes || 0
                ) / 1024
              ).toFixed(1)}
              KB
            </td>

            <td>
              ${esc0(
                time0(
                  x.created_at
                )
              )}
            </td>

            <td>

              <a
                class="btn secondary small"
                href="/api/admin/ops/backups/${encodeURIComponent(
                  x.filename
                )}"
              >
                ${tr0("下载")}
              </a>

            </td>

          </tr>

        `);

    return `

      <section class="card ops-card">

        <div class="ops-section-head">

          <div>

            <h2>
              ${tr0("数据库备份与恢复")}
            </h2>

            <p class="ops-mini">
              ${tr0("创建 SQLite 热备并保留最近 10 份文件；")}
              ${tr0("下载后可用于灾备恢复。")}
            </p>

          </div>

          <button
            class="btn"
            data-ops-action="backup-create"
          >
            ${tr0("立即备份")}
          </button>

        </div>

        ${table(
          [
            '备份文件',
            '大小',
            '时间',
            '操作'
          ],
          rows
        )}

      </section>

    `;
  }

  /*
   * IMPORTANT:
   *
   * This function is a renderer for app.js.
   *
   * It MUST return HTML.
   * It must NOT manipulate #content directly.
   * The native go() function in app.js handles
   * inserting the returned HTML.
   */
async function renderOpsCenter(role){

    try{

      const [
        health,
        analytics,
        notifications,
        audit
      ] = await Promise.all([

        renderHealth(),
        renderAnalytics(),
        renderNotifications(),
        renderAudit(role)

      ]);

      return `

        <div class="ops-page">

          <div class="ops-banner">

            <div>

              <strong>
                NCS Operations Center
              </strong>

<p>
  ${tr0("系统健康")} ·
  ${tr0("设备利用率")} ·
  ${tr0("通知中心")} ·
  ${tr0("操作审计")}
</p>

            </div>

            <div class="ops-banner-actions">

              <button
                class="ops-notify-button"
                type="button"
                data-ops-action="notifications"
                data-ops-notify-button
              >

                <span
                  class="ops-bell"
                  aria-hidden="true"
                >
                  🔔
                </span>

                <span>
                  ${tr0("通知")}
                </span>

                <span
                  class="ops-notify-badge"
                  hidden
                >
                  0
                </span>

              </button>

              <span
                class="ops-pill success"
              >
                ${tr0("云端运行")}
              </span>

            </div>

          </div>

          ${health}

          ${analytics}

          ${notifications}

          ${audit}

        </div>

      `;

    }catch(e){

      return `

        <div class="card ops-card">

          <h2>
            运营中心加载失败
          </h2>

          <p class="ops-mini">
            ${esc0(
              e.message
            )}
          </p>

        </div>

      `;

    }
  }

  async function reloadOpsCenter(){

    const content =
      document.querySelector(
        '#content'
      );

    if(!content){
      return;
    }

    content.innerHTML =
      await renderOpsCenter();

    await refreshNotificationsDot();
  }

  async function refreshNotificationsDot(){

    try{

      const d =
        await fetchJson(
          '/notifications'
        );

      const button =
        document.querySelector(
          '[data-ops-notify-button]'
        );

      const badge =
        button?.querySelector(
          '.ops-notify-badge'
        );

      const unread =
        Number(
          d.unread || 0
        );

      if(badge){

        badge.hidden =
          unread <= 0;

        badge.textContent =
          unread > 99
            ? '99+'
            : String(unread);
      }

    }catch(_){

      /*
       * Notification refresh is
       * non-critical.
       */
    }
  }

  /*
   * Operations Center button actions.
   */
  document.addEventListener(
    'click',
    async function(e){

      const b =
        e.target.closest(
          '[data-ops-action]'
        );

      if(!b){
        return;
      }

      const action =
        b.getAttribute(
          'data-ops-action'
        );

      try{

        if(
          action ===
          'notifications'
        ){

          document
            .querySelector(
              '.ops-notifications'
            )
            ?.scrollIntoView({
              behavior:'smooth',
              block:'start'
            });

          return;
        }

        if(
          action ===
          'audit-search'
        ){

          const html =
            await renderAudit();

          const holder =
            b.closest(
              '.ops-card'
            );

          if(holder){
            holder.outerHTML =
              html;
          }

          return;
        }

        if(
          action ===
          'backup-create'
        ){

          b.disabled = true;

          const d =
            await fetchJson(
              '/admin/ops/backups'
            );

          if(!d.supported){

            throw new Error(
              '当前后端不支持本地 SQLite 备份'
            );
          }

          const r =
            await api0(
              '/admin/ops/backups',
              'POST',
              {}
            );

          toast0(
            `备份成功：${r.filename}`
          );

          await reloadOpsCenter();

          return;
        }

        if(
          action ===
          'read-all'
        ){

          await api0(
            '/notifications/read-all',
            'POST',
            {}
          );

          await reloadOpsCenter();

          return;
        }

      }catch(err){

        toast0(
          err.message
        );

        b.disabled = false;
      }

    }
  );

  /*
   * Individual notification read action.
   */
  document.addEventListener(
    'click',
    async function(e){

      const b =
        e.target.closest(
          '[data-ops-read]'
        );

      if(!b){
        return;
      }

      try{

        await api0(
          '/notifications/' +
          encodeURIComponent(
            b.dataset.opsRead
          ) +
          '/read',
          'POST',
          {}
        );

        await reloadOpsCenter();

      }catch(err){

        toast0(
          err.message
        );

      }

    }
  );

  /*
   * Do not create another sidebar.
   *
   * app.js already owns:
   *   roleNav
   *   shell()
   *   go()
   *   data-page
   *
   * This file only exposes the renderer.
   */
  document.addEventListener(
    'DOMContentLoaded',
    () => {
      refreshNotificationsDot();
    }
  );

  setInterval(
    refreshNotificationsDot,
    60000
  );

  window.NCSOpsFeatures = {
    renderOpsCenter,
    refreshNotificationsDot
  };

})();