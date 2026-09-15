/* Account avatar editor; only an explicit Save uploads an image. */
let avatarDraft = null, avatarPreviewURL = null, avatarStream = null, cameraGeneration = 0, avatarSelectionGeneration = 0;
function avatarProfileCard() {
  return `<section class="card avatar-profile"><div class="avatar-large">${av()}</div><div><h2>${tr("我的头像")}</h2><p class="sub">${tr("默认使用紫色背景和昵称首字，也可以上传图片或拍照。")}</p><div class="actions">${btn(tr("更换头像"),"avatar-edit")}${S.user.avatar_url ? btn(tr("恢复默认头像"),"avatar-reset","secondary") : ""}</div></div></section>`;
}
function stopAvatarCamera() {
  cameraGeneration++;
  if (avatarStream) avatarStream.getTracks().forEach(track => track.stop());
  avatarStream = null;
  const video = document.querySelector('#avatar-video');
  if (video) { video.srcObject = null; video.hidden = true; }
  const snap = document.querySelector('[data-action="avatar-snap"]');
  if (snap) snap.hidden = true;
}
function disposeAvatarEditor() {
  avatarSelectionGeneration++;
  stopAvatarCamera();
  if (avatarPreviewURL) URL.revokeObjectURL(avatarPreviewURL);
  avatarPreviewURL = null;
  avatarDraft = null;
}
function openAvatarEditor() {
  disposeAvatarEditor();
  modal(tr("更换头像"), `<div id="avatar-editor"><div class="avatar-preview"><img id="avatar-preview" alt="${tr("头像预览")}" hidden><video id="avatar-video" autoplay playsinline muted hidden aria-label="${tr("相机预览")}"></video><div id="avatar-placeholder">${av()}</div></div><p class="sub">${tr("选择 JPG、PNG 或 WebP 图片，最大 5 MB。将居中裁剪为正方形。")}</p><input id="avatar-camera-file" type="file" accept="image/*" capture="user" hidden><input id="avatar-file" type="file" accept="image/jpeg,image/png,image/webp" hidden><div class="actions">${btn(tr("上传图片"),"avatar-pick")}${btn(tr("拍照"),"avatar-camera","secondary")}${btn(tr("拍摄"),"avatar-snap","secondary","hidden")}</div><p id="camera-status" class="sub" role="status"></p><div class="actions"><button class="btn" data-action="avatar-save" disabled>${tr("保存头像")}</button></div></div>`);
}
async function setAvatarDraft(blob) {
  const generation = ++avatarSelectionGeneration;
  if (!blob || !blob.size || blob.size > 5 * 1024 * 1024) throw Error(tr("头像图片不能为空，且不能超过 5 MB"));
  if (!['image/jpeg','image/png','image/webp'].includes(blob.type)) throw Error(tr("请选择 JPG、PNG 或 WebP 图片"));
  const url = URL.createObjectURL(blob);
  try {
    await new Promise((resolve,reject) => { const img = new Image(); img.onload=resolve; img.onerror=()=>reject(Error(tr("无法读取图片，请选择完整有效的 JPG、PNG 或 WebP 图片"))); img.src=url; });
  } catch (e) { URL.revokeObjectURL(url); throw e; }
  if (generation !== avatarSelectionGeneration || !document.querySelector('#modal[open] #avatar-editor')) { URL.revokeObjectURL(url); return; }
  stopAvatarCamera();
  if (avatarPreviewURL) URL.revokeObjectURL(avatarPreviewURL);
  avatarPreviewURL=url; avatarDraft=blob;
  const preview=document.querySelector('#avatar-preview'); preview.src=url;preview.hidden=false;
  document.querySelector('#avatar-placeholder').hidden=true;
  document.querySelector('[data-action="avatar-save"]').disabled=false;
  document.querySelector('#camera-status').textContent='';
}
async function startAvatarCamera() {
  disposeAvatarEditor();
  document.querySelector('[data-action="avatar-save"]').disabled=true;
  document.querySelector('#avatar-preview').hidden=true;
  document.querySelector('#avatar-placeholder').hidden=false;
  const status=document.querySelector('#camera-status');
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    status.textContent=tr("当前页面无法直接开启相机。请使用上传图片，手机可尝试从文件选择器中拍照。");
    document.querySelector("#avatar-camera-file").click();
    return;
  }
  const generation=cameraGeneration;
  status.textContent=tr("正在打开相机…");
  try {
    const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640},height:{ideal:640}},audio:false});
    if (generation!==cameraGeneration || !document.querySelector('#modal[open] #avatar-editor')) { stream.getTracks().forEach(t=>t.stop()); return; }
    avatarStream=stream;
    const video=document.querySelector('#avatar-video');video.srcObject=stream;video.hidden=false;
    document.querySelector('#avatar-preview').hidden=true;document.querySelector('#avatar-placeholder').hidden=true;
    await video.play();
    if(generation!==cameraGeneration) return;
    document.querySelector('[data-action="avatar-snap"]').hidden=false;
    status.textContent=tr("准备好后点击拍摄，照片只在保存头像后提交。");
  } catch (_) {
    if(generation!==cameraGeneration) return;
    stopAvatarCamera();
    if(document.querySelector('#camera-status')) status.textContent=tr("无法开启相机，请允许相机权限，或使用上传图片。");
  }
}
async function captureAvatarPhoto() {
  const video=document.querySelector('#avatar-video');
  if (!video?.videoWidth || !video.videoHeight) throw Error(tr("相机尚未准备好，请稍后再拍"));
  const canvas=document.createElement('canvas');canvas.width=canvas.height=512;
  const size=Math.min(video.videoWidth,video.videoHeight);
  canvas.getContext('2d').drawImage(video,(video.videoWidth-size)/2,(video.videoHeight-size)/2,size,size,0,0,512,512);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.9));
  if(!blob) throw Error(tr("无法拍摄照片，请重试或上传图片"));
  await setAvatarDraft(blob);
}
async function uploadAvatarDraft() {
  if (!avatarDraft) throw Error(tr("请先选择图片或拍摄照片"));
  const form=new FormData();form.append('image',avatarDraft,'avatar.'+(avatarDraft.type==='image/png'?'png':avatarDraft.type==='image/webp'?'webp':'jpg'));
  const response=await fetch('/api/profile/avatar',{method:'POST',headers:{'X-CSRF-Token':S.csrf,'X-NCS-Language':NCSPreferences.state.language},body:form});
  let data;try{data=await response.json()}catch(_){throw Error(tr("服务器响应异常，请检查 VS Code 终端"))}
  if(!response.ok) throw Error(data.error || tr("请求失败"));
  document.querySelector('#modal').close();disposeAvatarEditor();
  await refresh();await go('profile');toast(tr("头像已保存"));
}
document.addEventListener('change',async e=>{
  if(!['avatar-file','avatar-camera-file'].includes(e.target.id))return;
  const blob=e.target.files?.[0];e.target.value='';if(!blob)return;
  try{await setAvatarDraft(blob)}catch(err){error(err)}
});
document.addEventListener('click',e=>{
  document.querySelectorAll('.account-menu[open]').forEach(menu=>{if(!menu.contains(e.target)||e.target.closest('[data-page],[data-action]'))menu.open=false});
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.account-menu[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus()})});
document.addEventListener('error',e=>{if(e.target.matches?.('img[data-account-avatar]'))e.target.remove()},true);
document.addEventListener('close',e=>{if(e.target.id==='modal'&&!e.target.open)disposeAvatarEditor()},true);
window.addEventListener('pagehide',disposeAvatarEditor);
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopAvatarCamera()});


/* Compatibility layer for the newer dev app.js.
   This keeps the current filtering/management UI intact while adding the
   avatar and expanded-station features from this upgrade. */
const NCS_EXPANDED_REGIONS = {
  "房山区": [39.7479, 116.1433],
  "大兴区": [39.7289, 116.3380],
  "通州区": [39.9099, 116.6564],
  "昌平区": [40.2207, 116.2312],
  "顺义区": [40.1302, 116.6546],
};

function accountAvatarMarkup() {
  if (!S.user) return "";
  const initial = esc(Array.from(S.user.nickname || "?")[0]);
  const image = S.user.avatar_url
    ? `<img data-account-avatar src="${esc(S.user.avatar_url)}" alt="${esc(tr("用户头像"))}">`
    : "";
  return `<div class="avatar ${esc(S.user.avatar || "lavender")}"><span>${initial}</span>${image}</div>`;
}

function decorateAccountAvatar(node) {
  if (!node || !S.user) return;
  const old = node.querySelector("img[data-account-avatar]");
  if (!S.user.avatar_url) {
    if (old) old.remove();
    return;
  }
  if (old && old.getAttribute("src") === S.user.avatar_url) return;
  if (old) old.remove();
  const image = document.createElement("img");
  image.dataset.accountAvatar = "";
  image.src = S.user.avatar_url;
  image.alt = tr("用户头像");
  node.appendChild(image);
}

function ensureAvatarProfileCard() {
  if (!S.user || S.page !== "profile") return;
  const content = document.querySelector("#content");
  if (!content || content.querySelector(".avatar-profile")) return;

  const holder = document.createElement("div");
  holder.innerHTML = avatarProfileCard().trim();
  const card = holder.firstElementChild;
  if (!card) return;

  const grid = content.querySelector(".page-grid");
  if (grid) content.insertBefore(card, grid);
  else content.prepend(card);
}

function ensureAccountMenu() {
  if (!S.user) return;
  const topbar = document.querySelector(".topbar");
  if (!topbar || topbar.querySelector(".account-menu")) return;

  const target = topbar.querySelector(".avatar");
  if (!target) return;

  const details = document.createElement("details");
  details.className = "account-menu";
  details.innerHTML = `
    <summary aria-label="${esc(tr("账户菜单"))}" title="${esc(tr("账户菜单"))}">
      ${accountAvatarMarkup()}
    </summary>
    <div class="account-dropdown">
      <strong>${esc(S.user.nickname)}</strong>
      <small>${tr("用户编号")}：${esc(S.user.id)}</small>
      <button data-page="profile">${ic("user")}${tr("个人主页")}</button>
      <button data-action="logout">${ic("logout")}${tr("退出登录")}</button>
    </div>`;
  target.replaceWith(details);
}

function ensureExpandedRegions() {
  const select = document.querySelector("#region");
  if (!select) return;

  const custom = Array.from(select.options).find((o) => o.value === "自定义位置");
  for (const name of Object.keys(NCS_EXPANDED_REGIONS)) {
    let option = Array.from(select.options).find((o) => o.value === name);
    if (!option) {
      option = document.createElement("option");
      option.value = name;
      option.textContent = tr(name);
      if (custom) select.insertBefore(option, custom);
      else select.appendChild(option);
    }
    option.selected = S.location === name;
  }
}

function decorateAdminOrderUserIds() {
  if (!S.user || S.user.role !== "admin" || S.page !== "orders") return;
  const content = document.querySelector("#content");
  if (!content) return;

  for (const tableNode of content.querySelectorAll("table")) {
    const firstHeading = tableNode.querySelector("thead th")?.textContent?.trim();
    if (!firstHeading || !firstHeading.includes(tr("订单号"))) continue;

    for (const row of tableNode.querySelectorAll("tbody tr")) {
      const cells = row.querySelectorAll("td");
      if (cells.length < 2) continue;
      const match = cells[0].textContent.match(/\d+/);
      if (!match) continue;
      const orderId = Number(match[0]);
      const order = (S.orders || []).find((item) => Number(item.id) === orderId);
      if (!order || order.user_id == null || cells[1].querySelector(".ncs-user-id")) continue;

      const id = document.createElement("small");
      id.className = "ncs-user-id";
      id.style.marginLeft = "8px";
      id.style.opacity = ".72";
      id.textContent = `${tr("用户编号")} #${order.user_id}`;
      cells[1].appendChild(id);
    }
  }
}

function enhanceUpgradeUI() {
  if (typeof S === "undefined" || !S.user) return;
  ensureAvatarProfileCard();
  ensureAccountMenu();
  ensureExpandedRegions();
  decorateAdminOrderUserIds();

  document.querySelectorAll(".side-user > .avatar, .topbar .avatar, .avatar-profile .avatar")
    .forEach(decorateAccountAvatar);
}

let upgradeEnhanceQueued = false;
function queueUpgradeEnhance() {
  if (upgradeEnhanceQueued) return;
  upgradeEnhanceQueued = true;
  queueMicrotask(() => {
    upgradeEnhanceQueued = false;
    try { enhanceUpgradeUI(); } catch (_) {}
  });
}

new MutationObserver(queueUpgradeEnhance).observe(document.documentElement, {
  childList: true,
  subtree: true,
});

document.addEventListener("DOMContentLoaded", queueUpgradeEnhance);
window.addEventListener("ncs-preferences-external", queueUpgradeEnhance);

document.addEventListener("change", async (e) => {
  if (e.target.id !== "region" || !NCS_EXPANDED_REGIONS[e.target.value]) return;
  e.stopImmediatePropagation();
  const [lat, lng] = NCS_EXPANDED_REGIONS[e.target.value];
  S.lat = lat;
  S.lng = lng;
  S.location = e.target.value;
  try {
    await go("stations");
  } catch (err) {
    error(err);
  }
}, true);

document.addEventListener("click", async (e) => {
  const button = e.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  if (!["avatar-edit", "avatar-pick", "avatar-camera", "avatar-snap", "avatar-save", "avatar-reset"].includes(action)) return;

  e.preventDefault();
  try {
    if (action === "avatar-edit") openAvatarEditor();
    else if (action === "avatar-pick") document.querySelector("#avatar-file")?.click();
    else if (action === "avatar-camera") await startAvatarCamera();
    else if (action === "avatar-snap") await captureAvatarPhoto();
    else if (action === "avatar-save") await uploadAvatarDraft();
    else if (action === "avatar-reset") {
      await api("/profile/avatar", "DELETE");
      await refresh();
      await go("profile");
      toast(tr("已恢复默认头像"));
    }
  } catch (err) {
    error(err);
  }
});
