document.addEventListener("DOMContentLoaded", function () {
  if (typeof hasil === "undefined" || !hasil.detailed_journey) {
    console.warn("Tidak ada hasil rute untuk divisualisasikan.");
    return;
  }

  // --- Inisialisasi Map
  const map = L.map("mapRekomendasi").setView([-6.2, 106.8], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  // --- 🎯 Definisi ikon marker
  const iconStart = L.divIcon({
    html: `<div style="width:20px;height:20px;background:#2ecc71;border:3px solid white;border-radius:50%;box-shadow:0 0 4px #2ecc71;"></div>`,
    className: "grab-point",
    iconSize: [20, 20],
    popupAnchor: [0, -10],
  });
  const iconEnd = L.divIcon({
    html: `<div style="width:20px;height:20px;background:#e74c3c;border:3px solid white;border-radius:50%;box-shadow:0 0 4px #e74c3c;"></div>`,
    className: "grab-point",
    iconSize: [20, 20],
    popupAnchor: [0, -10],
  });
  const iconTransit = L.divIcon({
    html: `<div style="width:24px;height:24px;background:#8e44ad;border:3px solid white;border-radius:50%;box-shadow:0 0 6px #8e44ad;"></div>`,
    className: "grab-point-transit",
    iconSize: [24, 24],
    popupAnchor: [0, -12],
  });
  const iconStop = L.divIcon({
    html: `<div style="width:10px;height:10px;background:#007bff;border:2px solid white;border-radius:50%;box-shadow:0 0 2px #007bff;"></div>`,
    className: "grab-stop",
    iconSize: [10, 10],
    popupAnchor: [0, -5],
  });

  const bounds = [];

  // --- Siapkan path utama
  let latlngs = [];
  if (Array.isArray(pathCoords) && pathCoords.length > 0) {
    latlngs = pathCoords.map(([lon, lat]) => [lat, lon]);
    bounds.push(...latlngs);
  }

  // --- Buat polyline untuk animasi
  const fullLine = L.polyline([], { color: "#007bff", weight: 6, opacity: 0.9 }).addTo(map);
  let animationIndex = 0;
  let currentColor = "#007bff";

  // --- Fungsi animasi garis
  function animatePath() {
    if (animationIndex >= latlngs.length) return;

    // Ganti warna jika sudah melewati halte "Semanggi"
    const currentPoint = latlngs[animationIndex];
    const semanggiFound = hasil.detailed_journey.some((step) => {
      return (
        (step.dari && step.dari.toLowerCase().includes("semanggi")) ||
        (step.ke && step.ke.toLowerCase().includes("semanggi"))
      );
    });

    // Deteksi jarak dengan halte Semanggi (ubah warna sesudahnya)
    if (semanggiFound && animationIndex > latlngs.length * 0.5 && currentColor !== "#f39c12") {
      currentColor = "#f39c12"; // oranye
      map.removeLayer(fullLine);
      fullLine.setStyle({ color: currentColor });
      fullLine.addTo(map);
    }

    fullLine.addLatLng(currentPoint);
    animationIndex++;
    requestAnimationFrame(animatePath);
  }

  animatePath();

  // --- Marker halte dan transit
  hasil.detailed_journey.forEach((step) => {
    if (step.type === "travel") {
      // Halte awal & akhir tiap segmen
      if (step.coords_dari) {
        const latlon = [step.coords_dari[1], step.coords_dari[0]];
        L.marker(latlon, { icon: iconStop })
          .addTo(map)
          .bindPopup(`<b>${step.dari}</b><br>Koridor ${step.koridor}`);
        bounds.push(latlon);
      }
      if (step.coords_ke) {
        const latlon = [step.coords_ke[1], step.coords_ke[0]];
        L.marker(latlon, { icon: iconStop })
          .addTo(map)
          .bindPopup(`<b>${step.ke}</b><br>Koridor ${step.koridor}`);
        bounds.push(latlon);
      }

      // Halte yang dilewati (melewatinya)
      if (step.melewati && step.melewati.length > 0) {
        step.melewati.forEach((halteNama) => {
          const halteData = hasil.detailed_journey.find(
            (h) => h.dari === halteNama || h.ke === halteNama
          );
          if (halteData && halteData.coords_dari) {
            const latlon = [halteData.coords_dari[1], halteData.coords_dari[0]];
            L.marker(latlon, { icon: iconStop })
              .addTo(map)
              .bindPopup(`<b>${halteNama}</b><br>Koridor ${step.koridor}`);
            bounds.push(latlon);
          }
        });
      }
    }

    // --- Halte Transit
    else if (step.type === "transfer" && step.coords) {
      const latlon = [step.coords[1], step.coords[0]];
      L.marker(latlon, { icon: iconTransit })
        .addTo(map)
        .bindPopup(
          `<b>Transit:</b> ${step.halte}<br>${step.dari_koridor} → ${step.ke_koridor}`
        );
      bounds.push(latlon);
    }
  });

  // --- Marker Asal & Tujuan
  if (latlngs.length > 1) {
    const startLatLon = latlngs[0];
    const endLatLon = latlngs[latlngs.length - 1];
    L.marker(startLatLon, { icon: iconStart }).addTo(map).bindPopup("<b>Halte Asal</b>");
    L.marker(endLatLon, { icon: iconEnd }).addTo(map).bindPopup("<b>Halte Tujuan</b>");
    bounds.push(startLatLon, endLatLon);
  }

  if (bounds.length > 0) map.fitBounds(bounds);
});
