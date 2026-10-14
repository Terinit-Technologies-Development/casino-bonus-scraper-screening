"use strict";

const SOURCE_URL = "https://betproof.co.za/casino-bonuses-south-africa/";

const elements = {
  status: document.querySelector("#loading-status"),
  error: document.querySelector("#error-panel"),
  table: document.querySelector("#table-scroll"),
  rows: document.querySelector("#casino-rows"),
  count: document.querySelector("#record-count"),
  generatedAt: document.querySelector("#generated-at"),
  scrollHint: document.querySelector("#scroll-hint"),
};

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function isHttpsSource(value) {
  if (!isNonEmptyString(value)) return false;

  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.href === SOURCE_URL;
  } catch {
    return false;
  }
}

function validateDataset(data) {
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("The snapshot root must be an object.");
  }
  if (!isNonEmptyString(data.generated_at) || Number.isNaN(Date.parse(data.generated_at))) {
    throw new Error("The snapshot timestamp is missing or invalid.");
  }
  if (!isNonEmptyString(data.model) || !isHttpsSource(data.source_url)) {
    throw new Error("The snapshot source or model is missing or invalid.");
  }
  if (!Array.isArray(data.casinos) || data.casinos.length !== 3) {
    throw new Error("The snapshot must contain exactly three casino records.");
  }

  const names = new Set();
  for (const record of data.casinos) {
    if (record === null || typeof record !== "object" || Array.isArray(record)) {
      throw new Error("A casino record is not a valid object.");
    }
    if (
      !isNonEmptyString(record.casino) ||
      !isNonEmptyString(record.welcome_bonus) ||
      !isNonEmptyString(record.minimum_deposit) ||
      typeof record.wagering_requirement_multiplier !== "number" ||
      !Number.isFinite(record.wagering_requirement_multiplier) ||
      record.wagering_requirement_multiplier < 0 ||
      !isHttpsSource(record.source_url) ||
      record.source_url !== data.source_url
    ) {
      throw new Error("A casino record is missing a valid required field.");
    }
    if (names.has(record.casino)) {
      throw new Error("The snapshot contains duplicate casino records.");
    }
    names.add(record.casino);
  }

  return data;
}

function createCell(text, className) {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text;
  return cell;
}

function renderDataset(data) {
  const fragment = document.createDocumentFragment();

  for (const record of data.casinos) {
    const row = document.createElement("tr");
    row.append(
      createCell(record.casino),
      createCell(record.welcome_bonus),
      createCell(`${record.wagering_requirement_multiplier}x`),
      createCell(record.minimum_deposit),
    );

    const sourceCell = document.createElement("td");
    const sourceLink = document.createElement("a");
    sourceLink.className = "source-link";
    sourceLink.href = record.source_url;
    sourceLink.target = "_blank";
    sourceLink.rel = "noopener noreferrer";
    sourceLink.textContent = "BetProof ↗";
    sourceLink.setAttribute(
      "aria-label",
      `Source listing for ${record.casino} (opens in a new tab)`,
    );
    sourceCell.append(sourceLink);
    row.append(sourceCell);
    fragment.append(row);
  }

  elements.rows.replaceChildren(fragment);
  elements.count.textContent = `${data.casinos.length} listings`;

  const generatedDate = new Date(data.generated_at);
  elements.generatedAt.dateTime = generatedDate.toISOString();
  elements.generatedAt.textContent = `Generated ${new Intl.DateTimeFormat("en-ZA", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Africa/Johannesburg",
  }).format(generatedDate)}`;

  elements.table.hidden = false;
  updateScrollHint();
  elements.status.textContent = "Snapshot loaded successfully.";
}

function updateScrollHint() {
  elements.scrollHint.hidden =
    elements.table.scrollWidth <= elements.table.clientWidth;
}

function showLoadError() {
  elements.table.hidden = true;
  elements.count.textContent = "Snapshot unavailable";
  elements.status.textContent = "Snapshot could not be loaded.";
  elements.error.textContent =
    "We couldn’t load or validate the bonus snapshot. Check your connection and refresh the page to try again.";
  elements.error.hidden = false;
}

async function loadDataset() {
  try {
    const response = await fetch("./bonuses.json", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`Snapshot request failed with HTTP ${response.status}.`);
    }

    const data = validateDataset(await response.json());
    renderDataset(data);
  } catch {
    showLoadError();
  }
}

window.addEventListener("resize", updateScrollHint, { passive: true });
loadDataset();
