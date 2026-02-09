// ====== Map init (Bandung-ish default view; adjust as needed) ======
const map = L.map("map").setView([-6.9, 107.6], 11);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

// ====== SSI color scale ======
function getColor(ssi) {
  if (ssi == null || isNaN(ssi)) return "#dddddd";
  return ssi > 0.8
    ? "#800026"
    : ssi > 0.6
      ? "#BD0026"
      : ssi > 0.4
        ? "#E31A1C"
        : ssi > 0.2
          ? "#FD8D3C"
          : "#FED976";
}

function style(feature) {
  const p = feature.properties || {};
  const ssi = Number(p.ssi_score);

  // recommended zones: thicker outline
  const recommended = Number(p.is_recommended) === 1;

  return {
    fillColor: getColor(ssi),
    weight: recommended ? 3 : 1,
    opacity: 1,
    color: recommended ? "#111" : "#555",
    fillOpacity: 0.7,
  };
}

function fmt(n, digits = 4) {
  if (n === null || n === undefined) return "-";
  const x = Number(n);
  if (Number.isNaN(x)) return "-";
  return x.toFixed(digits);
}

function onEachFeature(feature, layer) {
  const p = feature.properties || {};

  const tag =
    Number(p.is_recommended) === 1
      ? `<span class="badge">RECOMMENDED #${p.recommend_rank}</span>`
      : "";

  layer.bindPopup(`
    <div style="min-width:220px">
      <div style="font-size:14px; font-weight:700;">
        Zone: ${p.zone_id || "-"} ${tag}
      </div>
      <hr style="border:none;border-top:1px solid #eee;margin:8px 0" />
      <div><b>SSI:</b> ${fmt(p.ssi_score, 6)}</div>
      <div><b>ENV pressure:</b> ${fmt(p.env_pressure, 6)}</div>
      <div><b>SOCIAL pressure:</b> ${fmt(p.social_pressure, 6)}</div>
      <div><b>OPS pressure:</b> ${fmt(p.ops_pressure, 6)}</div>
      <div><b>Dominant pressure:</b> ${p.dominant_pressure || "-"}</div>
      <div><b>Activity count:</b> ${p.activity_count ?? "-"}</div>
      <div><b>Access score:</b> ${fmt(p.access_score, 6)}</div>
      <div><b>Underserved score:</b> ${fmt(p.underserved_score, 6)}</div>
    </div>
  `);

  layer.on({
    mouseover: (e) => {
      e.target.setStyle({ fillOpacity: 0.85 });
    },
    mouseout: (e) => {
      geojson.resetStyle(e.target);
    },
  });
}

// ====== Legend ======
function buildLegend() {
  const legend = document.getElementById("legend");
  const items = [
    { label: "SSI > 0.8", color: getColor(0.81) },
    { label: "0.6 – 0.8", color: getColor(0.61) },
    { label: "0.4 – 0.6", color: getColor(0.41) },
    { label: "0.2 – 0.4", color: getColor(0.21) },
    { label: "≤ 0.2", color: getColor(0.1) },
    { label: "No data", color: "#dddddd" },
  ];

  legend.innerHTML =
    `<b>SSI Score Legend</b><br/>` +
    items
      .map(
        (it) => `
      <div class="row">
        <div class="swatch" style="background:${it.color}"></div>
        <div>${it.label}</div>
      </div>
    `,
      )
      .join("") +
    `<hr style="border:none;border-top:1px solid #eee;margin:8px 0" />
     <div class="row">
       <div class="swatch" style="background:#fff;border:2px solid #111"></div>
       <div>Recommended zones (thick border)</div>
     </div>`;
}

buildLegend();

// ====== Load GeoJSON & render ======
let geojson;

fetch("./zones_with_dss.geojson")
  .then((r) => r.json())
  .then((data) => {
    geojson = L.geoJSON(data, {
      style,
      onEachFeature,
    }).addTo(map);

    // Fit map to data bounds
    map.fitBounds(geojson.getBounds(), { padding: [20, 20] });
  })
  .catch((err) => {
    console.error(err);
    alert(
      "Failed to load zones_with_dss.geojson. Make sure you're running a local server (not opening index.html directly).",
    );
  });
