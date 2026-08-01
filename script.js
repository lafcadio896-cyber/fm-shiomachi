const DATA_URL = "data/broadcasts.json";

function formatDate(dateString) {
  const date = new Date(`${dateString}T00:00:00+09:00`);
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
  }).format(date);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderAudio(item, className) {
  if (!item.audio) {
    return `<p class="audio-pending">音声記録は準備中です。</p>`;
  }

  return `
    <div class="${className}">
      <p class="audio-label">RECORDED AUDIO / MONAURAL</p>
      <audio controls preload="metadata">
        <source src="${escapeHtml(item.audio)}?v=20260802-1" type="audio/mpeg">
        このブラウザでは音声を再生できません。
      </audio>
    </div>
  `;
}

function renderLatest(item) {
  document.querySelector("#latest-date").textContent = formatDate(item.date);
  document.querySelector("#latest-broadcast").innerHTML = `
    <p class="broadcast-meta">${escapeHtml(item.time)} / ${escapeHtml(item.program)} / ${escapeHtml(item.type)}</p>
    ${renderAudio(item, "latest-player")}
    <div class="broadcast-text">${escapeHtml(item.text)}</div>
  `;
}

function renderArchive(items) {
  const archive = document.querySelector("#archive-list");
  archive.innerHTML = items.map((item) => {
    const isFirstBroadcast = item.date === "2026-08-01";
    return `
      <article class="archive-item${isFirstBroadcast ? " first-broadcast" : ""}">
        <time datetime="${escapeHtml(item.date)}">${formatDate(item.date)}</time>
        <h3>${escapeHtml(item.title)}</h3>
        <span class="type">${escapeHtml(item.type)}</span>
        ${item.audio ? renderAudio(item, "archive-player") : ""}
        <details class="archive-transcript"${isFirstBroadcast ? " open" : ""}>
          <summary>${isFirstBroadcast ? "初回放送原稿" : "放送原稿を表示"}</summary>
          <p class="archive-meta">${escapeHtml(item.time)} / ${escapeHtml(item.program)}</p>
          <div class="broadcast-text">${escapeHtml(item.text)}</div>
        </details>
      </article>
    `;
  }).join("");
}

async function main() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const items = [...data.broadcasts].sort((a, b) => b.date.localeCompare(a.date));
    if (!items.length) throw new Error("放送記録がありません");
    renderLatest(items[0]);
    renderArchive(items);
    if (data.corrections?.length) {
      document.querySelector("#correction-summary").textContent = data.corrections[0].summary;
    }
  } catch (error) {
    document.querySelector("#latest-date").textContent = "受信不能";
    document.querySelector("#latest-broadcast").innerHTML = `
      <p class="broadcast-meta">SYSTEM / ARCHIVE</p>
      <p>放送記録を受信できませんでした。</p>
    `;
    console.error(error);
  }
}

main();
