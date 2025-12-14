# myapp/sma_module.py
import warnings
from pathlib import Path
import json
from .sma_solver.sma import find_route_with_sma
from .pulp_solver.pulp import build_transport_graph_with_costs as build_graph

BASE_DIR = Path(__file__).resolve().parent

def run_sma(halte_asal, halte_tujuan, preferensi_input="Rekomendasi", waktu_keberangkatan="08:00", dynamic_speed=None, dynamic_wait=None, dynamic_dwell=None, dynamic_delay=None):
    warnings.filterwarnings("ignore")

    # -----------------------
    # Lokasi file data
    # -----------------------
    nodes_file = BASE_DIR / "static" / "data" / "cleaned_nodes_new.geojson"
    edges_file = BASE_DIR / "static" / "data" / "transjakarta_edges.geojson"

    # -----------------------
    # Konstanta sistem 
    # -----------------------
    # Gunakan nilai dinamis jika diberikan, jika tidak, gunakan default
    AVG_BUS_SPEED_KMH = dynamic_speed if dynamic_speed is not None else 20
    AVG_TRANSFER_MIN = dynamic_wait if dynamic_wait is not None else 10
    
    STOP_DWELL_TIME_SECONDS = dynamic_dwell if dynamic_dwell is not None else 45
    DELAY_PER_KM_SECONDS = dynamic_delay if dynamic_delay is not None else 30
    
    # Konstanta lain tetap
    MAX_BUS_SPEED_KMH = 50
    SNAP_THRESHOLD_METERS = 500
    CONGESTION_FACTOR = 1.8

    # -----------------------
    # Penetapan bobot preferensi
    # -----------------------
    if preferensi_input == "min_transit":
        weights = {"waktu": 0.1, "biaya": 0.1, "transit": 0.8}
        label = "Minim Transit"
    elif preferensi_input == "cepat":
        weights = {"waktu": 0.8, "biaya": 0.1, "transit": 0.1}
        label = "Paling Cepat"
    else:
        weights = {"waktu": 0.45, "biaya": 0.1, "transit": 0.45}
        label = "Efisien & Seimbang"

    # -----------------------
    # Bangun graf transportasi
    # -----------------------
    print(f"INFO (SMA): Membangun graf dengan Speed={AVG_BUS_SPEED_KMH} km/jam, Wait={AVG_TRANSFER_MIN} min")
    G, _ = build_graph(nodes_file, edges_file,
                        AVG_BUS_SPEED_KMH, 
                        MAX_BUS_SPEED_KMH,
                        AVG_TRANSFER_MIN, 
                        STOP_DWELL_TIME_SECONDS,
                        DELAY_PER_KM_SECONDS, 
                        SNAP_THRESHOLD_METERS)

    if G is None:
        return {"error": "Graf tidak berhasil dibangun."}

    # -----------------------
    # Bangun stop_map untuk koordinat (baru)
    # -----------------------
    with open(nodes_file, "r", encoding="utf-8") as f:
        nodes_data = json.load(f)

    stop_map = {feat["properties"]["name"]: {
        "lat": feat["geometry"]["coordinates"][1],
        "lon": feat["geometry"]["coordinates"][0]
    } for feat in nodes_data["features"]}

    # -----------------------
    # Jalankan SMA
    # -----------------------
    hasil = find_route_with_sma(
        G, stop_map, halte_asal, halte_tujuan, weights,
        n_agents=50, max_iter=100, z_param=0.03
    )

    if "error" in hasil:
        return hasil

    # -----------------------
    # Hitung waktu normal & waktu macet
    # -----------------------
    waktu_normal = hasil["waktu_tempuh_menit"]
    waktu_macet = waktu_normal * CONGESTION_FACTOR
    hasil["waktu_normal_fmt"] = f"{int(waktu_normal)} menit"
    hasil["waktu_macet_fmt"] = f"{int(waktu_macet)} menit"
    hasil["preferensi_label"] = label
    hasil["jam_berangkat"] = waktu_keberangkatan

    # -----------------------
    # Tambahkan biaya dasar dari waktu keberangkatan
    # -----------------------
    from .sma_solver.sma import calculate_base_price
    harga_dasar = calculate_base_price(waktu_keberangkatan)
    hasil["biaya_fmt"] = f"Rp {harga_dasar:,}"

    return hasil
