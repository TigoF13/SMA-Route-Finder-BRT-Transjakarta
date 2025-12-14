# myapp/pulp_module.py
import os
from pathlib import Path
from .pulp_solver.pulp import (
    calculate_base_price,
    build_transport_graph_with_costs,
    find_route_with_pulp_weighted,
)

BASE_DIR = Path(__file__).resolve().parent  # /myapp

def run_optimization(halte_asal, halte_tujuan, preferensi_input, waktu_keberangkatan):
    import warnings
    warnings.filterwarnings("ignore")

    # Lokasi file data
    BASE_DIR = Path(__file__).resolve().parent
    nodes_file = BASE_DIR / "static" / "data" / "cleaned_nodes_new.geojson"
    edges_file = BASE_DIR / "static" / "data" / "transjakarta_edges.geojson"
    # Konstanta sistem
    AVG_BUS_SPEED_KMH = 25
    MAX_BUS_SPEED_KMH = 50
    AVG_TRANSFER_MIN = 5
    STOP_DWELL_TIME_SECONDS = 30
    DELAY_PER_KM_SECONDS = 15
    SNAP_THRESHOLD_METERS = 500
    CONGESTION_FACTOR = 1.8

    harga_dasar = calculate_base_price(waktu_keberangkatan)

    # Penetapan bobot berdasarkan preferensi
    if preferensi_input == "min_transit":
        weights = {"waktu": 0.1, "biaya": 0.1, "transit": 0.8}
        label = "Minim Transit"
    elif preferensi_input == "cepat":
        weights = {"waktu": 0.8, "biaya": 0.1, "transit": 0.1}
        label = "Paling Cepat"
    else:
        weights = {"waktu": 0.45, "biaya": 0.1, "transit": 0.45}
        label = "Efisien & Seimbang"

    # Bangun graf
    G, stop_map = build_transport_graph_with_costs(
        nodes_file, edges_file,
        AVG_BUS_SPEED_KMH, MAX_BUS_SPEED_KMH,
        AVG_TRANSFER_MIN, STOP_DWELL_TIME_SECONDS,
        DELAY_PER_KM_SECONDS, SNAP_THRESHOLD_METERS
    )

    if G is None:
        return {"error": "Graf tidak berhasil dibangun."}

    # Jalankan optimasi PuLP
    hasil = find_route_with_pulp_weighted(G, stop_map, halte_asal, halte_tujuan, weights)
    if "error" in hasil:
        return hasil

    # Hitung waktu & biaya tambahan
    waktu_normal = hasil["waktu_tempuh_menit"]
    waktu_macet = waktu_normal * CONGESTION_FACTOR
    hasil["waktu_normal_fmt"] = f"{int(waktu_normal)} menit"
    hasil["waktu_macet_fmt"] = f"{int(waktu_macet)} menit"
    hasil["biaya_fmt"] = f"Rp {harga_dasar:,}"
    hasil["preferensi_label"] = label
    hasil["jam_berangkat"] = waktu_keberangkatan
    return hasil
