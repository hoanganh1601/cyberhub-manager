"use strict";

Object.assign(copy, {
  forecastSimulated: ["DỮ LIỆU MÔ PHỎNG", "SIMULATED DATA"],
  forecastReal: ["Dữ liệu MySQL", "MySQL data"],
  forecastStale: [
    "Dự báo đã cũ hoặc chưa bắt đầu đúng ngày hiện tại. Hãy chạy huấn luyện lại trước khi ra quyết định.",
    "This forecast is stale or does not start near today. Retrain it before making decisions.",
  ],
  forecastDisclaimer: [
    "Dữ liệu mô phỏng.",
    "Simulated data.",
  ],
  forecastRevenue: ["Doanh thu dự báo", "Forecast revenue"],
  forecastCustomers: ["Lượng khách dự báo", "Forecast customers"],
  forecastSessions: ["Lượt mở máy", "Forecast sessions"],
  forecastDailyAverage: ["Doanh thu TB/ngày", "Average daily revenue"],
  forecastRevenueChart: ["Xu hướng doanh thu", "Revenue trend"],
  forecastDemandChart: ["Xu hướng lượng khách", "Customer demand trend"],
  forecastRoomComparison: ["So sánh loại phòng", "Room category comparison"],
  forecastBusinessPlan: ["Gợi ý kế hoạch kinh doanh", "Business planning suggestions"],
  forecastModelQuality: ["Chất lượng mô hình", "Model quality"],
  forecastDetails: ["Chi tiết theo ngày", "Daily details"],
  forecastPeriod: ["Kỳ dự báo", "Forecast horizon"],
  forecastModel: ["Mô hình được chọn", "Selected model"],
  forecastTarget: ["Mục tiêu", "Target"],
  forecastMAE: ["MAE", "MAE"],
  forecastMAPE: ["MAPE", "MAPE"],
  forecastRevenueTarget: ["Mục tiêu doanh thu (+5%)", "Revenue target (+5%)"],
  forecastBusyDays: ["Ngày dự kiến đông khách", "Expected busy days"],
  forecastExtraStaff: ["Nhân sự tăng cường", "Additional staff"],
  forecastInventory: ["Ước tính hàng cần chuẩn bị", "Estimated stock preparation"],
  forecastDrinks: ["đồ uống", "drinks"],
  forecastMeals: ["suất ăn", "meals"],
  forecastRoomFocus: ["Nhóm phòng cần ưu tiên", "Priority room category"],
  forecastNoBusyDays: ["Không có ngày vượt ngưỡng cao điểm", "No day exceeds the busy threshold"],
  forecastSessionsLabel: ["Lượt", "Sessions"],
  forecastGenerated: ["Huấn luyện lúc", "Trained at"],
  forecastDate: ["Ngày", "Date"],
  forecastCustomersShort: ["Khách", "Customers"],
  forecastTrainingSource: ["Nguồn huấn luyện", "Training source"],
  revenueTargetName: ["Doanh thu", "Revenue"],
  customerTargetName: ["Lượng khách", "Customers"],
  sessionTargetName: ["Lượt mở máy", "Sessions"],
});

function forecastCompact(value) {
  return new Intl.NumberFormat(state.lang === "en" ? "en-US" : "vi-VN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value) || 0);
}

function forecastDate(value) {
  const date = new Date(`${value}T00:00:00Z`);
  return new Intl.DateTimeFormat(state.lang === "en" ? "en-GB" : "vi-VN", {
    day: "2-digit",
    month: "2-digit",
  }).format(date);
}

function forecastLineChart(points, key, color, formatter = forecastCompact) {
  const width = 760;
  const height = 230;
  const padX = 42;
  const padY = 24;
  const values = points.map((item) => Number(item[key]) || 0);
  const maximum = Math.max(1, ...values) * 1.08;
  const x = (index) =>
    padX + (index * (width - padX * 2)) / Math.max(1, points.length - 1);
  const y = (value) => height - padY - (value / maximum) * (height - padY * 2);
  const line = values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
  const area = `${padX},${height - padY} ${line} ${x(points.length - 1)},${height - padY}`;
  const grid = [0.25, 0.5, 0.75]
    .map((ratio) => {
      const lineY = padY + ratio * (height - padY * 2);
      return `<line class="grid-line" x1="${padX}" y1="${lineY}" x2="${width - padX}" y2="${lineY}"></line>`;
    })
    .join("");
  const labels = points
    .map((item, index) =>
      index === 0 || index === points.length - 1 || index % Math.ceil(points.length / 6) === 0
        ? `<text x="${x(index)}" y="${height - 4}" text-anchor="middle">${esc(forecastDate(item.day))}</text>`
        : "",
    )
    .join("");
  const dots = points
    .map(
      (item, index) =>
        `<circle cx="${x(index)}" cy="${y(values[index])}" r="3"><title>${esc(item.day)}: ${esc(formatter(values[index]))}</title></circle>`,
    )
    .join("");
  return `<div class="forecast-chart-scroll"><svg class="forecast-line-chart ${color}" viewBox="0 0 ${width} ${height}" role="img"><defs><linearGradient id="forecast-area-${key}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-opacity="0.3"></stop><stop offset="100%" stop-opacity="0"></stop></linearGradient></defs>${grid}<line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}"></line><line x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}"></line><text x="${padX - 8}" y="${padY + 5}" text-anchor="end">${esc(formatter(maximum))}</text><text x="${padX - 8}" y="${height - padY + 5}" text-anchor="end">0</text><polygon class="forecast-area" points="${area}" fill="url(#forecast-area-${key})"></polygon><polyline points="${line}"></polyline>${dots}${labels}</svg></div>`;
}

function forecastTargetLabel(target) {
  return t(
    target === "revenue"
      ? "revenueTargetName"
      : target === "customer_count"
        ? "customerTargetName"
        : "sessionTargetName",
  );
}

function forecastAdminPage() {
  const data = state.items;
  const predictions = data.predictions || [];
  const roomMax = Math.max(1, ...(data.room_types || []).map((item) => item.revenue));
  const sourceBadge = data.is_simulated
    ? `<span class="forecast-source simulated">${t("forecastSimulated")}</span>`
    : `<span class="forecast-source real">${t("forecastReal")}</span>`;
  const horizon = `<div class="segment forecast-horizon" role="group" aria-label="${t("forecastPeriod")}">${[7, 30]
    .map(
      (days) =>
        `<button type="button" data-forecast-days="${days}" class="${data.horizon_days === days ? "active" : ""}">${days} ${state.lang === "en" ? "days" : "ngày"}</button>`,
    )
    .join("")}</div>`;
  const modelCards = Object.entries(data.metrics || {})
    .map(
      ([target, result]) => {
        const mape = result.mape == null ? null : Number(result.mape);
        const quality = mape == null ? "" : mape < 10 ? "good" : mape < 15 ? "fair" : "weak";
        return `<article class="forecast-model-card ${quality}"><div class="forecast-model-top"><span class="forecast-model-icon">${icon(target === "revenue" ? "wallet" : target === "customer_count" ? "users" : "monitor")}</span><div><small>${t("forecastTarget")}</small><strong>${esc(forecastTargetLabel(target))}</strong></div></div><span class="forecast-model-name">${esc(String(result.selected_model || "—").replaceAll("_", " "))}</span><div class="forecast-model-metrics"><div><small>${t("forecastMAE")}</small><strong>${target === "revenue" ? money(result.mae) : Number(result.mae || 0).toFixed(2)}</strong></div><div><small>${t("forecastMAPE")}</small><strong>${mape == null ? "—" : `${mape.toFixed(2)}%`}</strong></div></div></article>`;
      },
    )
    .join("");
  const dailyRows = predictions
    .map(
      (item) =>
        `<tr class="${data.planning.busy_days?.includes(item.day) ? "forecast-busy-row" : ""}"><td class="table-code">${esc(item.day)}</td><td class="money cyan">${money(item.predicted_revenue)}</td><td>${esc(item.predicted_customers)}</td><td>${esc(item.predicted_sessions)}</td></tr>`,
    )
    .join("");
  const busyDays = data.planning.busy_days?.length
    ? data.planning.busy_days.map((day) => `<span class="forecast-day-chip">${esc(day)}</span>`).join("")
    : `<span class="muted">${t("forecastNoBusyDays")}</span>`;

  return (
    pageHead(horizon) +
    `<section class="forecast-meta"><div class="forecast-meta-main">${sourceBadge}<div><small>${t("forecastTrainingSource")}</small><strong title="${esc(data.source)}">${esc(data.source)}</strong></div></div><div class="forecast-meta-details"><span>${icon("clock")}<span><small>${t("forecastGenerated")}</small><strong>${dt(data.trained_at)}</strong></span></span><span>${icon("chart")}<span><small>${t("forecastPeriod")}</small><strong>${esc(data.forecast_from)} → ${esc(data.forecast_to)}</strong></span></span></div></section>` +
    `${data.is_stale ? `<div class="notice warning">${icon("alert")}<strong>${t("forecastStale")}</strong></div>` : ""}` +
    `${data.is_simulated ? `<div class="forecast-disclaimer">${icon("alert")}<span>${t("forecastDisclaimer")}</span></div>` : ""}` +
    `<div class="metrics forecast-metrics">${metric("forecastRevenue", money(data.summary.total_revenue), "cyan", "wallet")}${metric("forecastCustomers", data.summary.total_customers, "green", "users", `${data.summary.average_daily_customers}/${state.lang === "en" ? "day" : "ngày"}`)}${metric("forecastSessions", data.summary.total_sessions, "", "monitor", `${data.summary.average_daily_sessions}/${state.lang === "en" ? "day" : "ngày"}`)}${metric("forecastDailyAverage", money(data.summary.average_daily_revenue), "amber", "chart")}</div>` +
    `<div class="forecast-chart-grid"><section class="panel forecast-chart-panel revenue"><header class="panel-heading"><h3>${icon("chart")} ${t("forecastRevenueChart")}</h3><div class="forecast-peak"><small>${esc(data.summary.peak_revenue_day)}</small><strong class="cyan">${money(data.summary.peak_revenue)}</strong></div></header><div class="panel-body">${forecastLineChart(predictions, "predicted_revenue", "cyan", money)}</div></section><section class="panel forecast-chart-panel demand"><header class="panel-heading"><h3>${icon("users")} ${t("forecastDemandChart")}</h3><div class="forecast-peak"><small>${esc(data.summary.peak_customer_day)}</small><strong class="green">${esc(data.summary.peak_customer_count)} ${state.lang === "en" ? "customers" : "khách"}</strong></div></header><div class="panel-body">${forecastLineChart(predictions, "predicted_customers", "green", (value) => String(Math.round(value)))}</div></section></div>` +
    `<div class="forecast-lower-grid"><section class="panel forecast-room-panel"><header class="panel-heading"><h3>${icon("grid")} ${t("forecastRoomComparison")}</h3><small>${data.room_types.length} ${state.lang === "en" ? "categories" : "loại phòng"}</small></header><div class="forecast-room-list">${data.room_types
      .map(
        (room) =>
          `<article class="forecast-room ${room.room_type.toLowerCase().replaceAll("_", "-")}"><div class="forecast-room-head"><span class="forecast-room-icon">${icon(room.room_type.includes("VIP") ? "check" : room.room_type === "COUPLE" ? "users" : "monitor")}</span><div><small>${room.sessions} ${t("forecastSessionsLabel").toLowerCase()}</small><strong>${esc(t(room.room_type))}</strong></div></div><div class="forecast-room-value money">${money(room.revenue)}</div><div class="forecast-room-bar"><i style="width:${Math.max(2, (room.revenue / roomMax) * 100)}%"></i></div><small class="muted">${money(room.average_revenue_per_session)}/${state.lang === "en" ? "session" : "lượt"}</small></article>`,
      )
      .join("")}</div></section><section class="panel forecast-plan-panel"><header class="panel-heading"><h3>${icon("check")} ${t("forecastBusinessPlan")}</h3><small>${data.horizon_days} ${state.lang === "en" ? "day plan" : "ngày kế hoạch"}</small></header><div class="forecast-plan"><div class="forecast-plan-main"><span class="forecast-plan-icon">${icon("chart")}</span><div><small>${t("forecastRevenueTarget")}</small><strong class="money cyan">${money(data.planning.revenue_target)}</strong></div></div><div class="forecast-plan-grid"><article>${icon("users")}<small>${t("forecastExtraStaff")}</small><strong>+${data.planning.suggested_extra_staff}</strong></article><article>${icon("utensils")}<small>${t("forecastInventory")}</small><strong>${data.planning.estimated_drinks} · ${data.planning.estimated_meals}</strong><span>${t("forecastDrinks")} · ${t("forecastMeals")}</span></article><article>${icon("monitor")}<small>${t("forecastRoomFocus")}</small><strong>${esc(t(data.planning.room_focus))}</strong></article></div><div class="forecast-busy-block"><h4>${t("forecastBusyDays")}</h4><div class="forecast-busy-days">${busyDays}</div></div><p class="pc-fine">${state.lang === "en" ? "Staff and stock figures are operational estimates; validate them against shift capacity and actual recipes." : "Số nhân sự và hàng cần chuẩn bị là ước tính vận hành; cần đối chiếu năng lực ca và định lượng món thực tế."}</p></div></section></div>` +
    `<section class="panel forecast-model-panel"><header class="panel-heading"><h3>${icon("check")} ${t("forecastModelQuality")}</h3><small>${esc(data.split.test_from || "")} → ${esc(data.split.test_to || "")}</small></header><div class="forecast-model-grid">${modelCards}</div></section>` +
    `<section class="panel forecast-daily"><header class="panel-heading"><h3>${icon("clock")} ${t("forecastDetails")}</h3><span class="badge cyan">${predictions.length} ${state.lang === "en" ? "days" : "ngày"}</span></header>${table(["forecastDate", "forecastRevenue", "forecastCustomersShort", "forecastSessions"], dailyRows)}</section>`
  );
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-forecast-days]");
  if (!button || state.page !== "forecasting") return;
  const days = Number(button.dataset.forecastDays);
  if (![7, 30].includes(days) || days === state.forecastHorizon) return;
  state.forecastHorizon = days;
  await loadPage();
});
