# myapp/sma_solver/sma.py
import networkx as nx
import random
import numpy as np
import itertools
import warnings
from math import radians, sin, cos, sqrt, asin # Import time library if not already imported
import geopandas as gpd
import json
import os
from pathlib import Path
from datetime import datetime, time # Import time class


try:
    from ..pulp_solver.pulp import calculate_final_metrics
except ImportError:
    print("WARNING: Gagal mengimpor calculate_final_metrics dari pulp_solver.pulp.")
    # Definisikan fungsi dummy jika impor gagal
    def calculate_final_metrics(G, path):
        return {"waktu_tempuh_menit": 0, "jarak_km": 0, "jumlah_transit": 0, "error": "Fungsi kalkulator tidak ditemukan"}

# --- 1. Fungsi Utilitas ---

def haversine(lon1, lat1, lon2, lat2):
    """Calculates the great-circle distance between two points on the Earth."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1; dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c # kilometers

def calculate_base_price(waktu_keberangkatan):
    """Calculates the base fare based on departure time."""
    try:
        # Gunakan datetime.strptime dan time
        dep_time = datetime.strptime(waktu_keberangkatan, '%H:%M').time()
        time_start, time_end = time(5, 0), time(7, 0) # Gunakan time class
        return 2000 if time_start <= dep_time <= time_end else 3500
    except (ValueError, TypeError):
        return 3500 # Default fare

# Redirect build_graph (assuming pulp.py has the definitive version)
def build_transport_graph_with_costs(*args, **kwargs):
    """Redirects graph building to the pulp_solver implementation."""
    try:
        from ..pulp_solver.pulp import build_transport_graph_with_costs as build_graph_pulp
        return build_graph_pulp(*args, **kwargs)
    except ImportError:
        print("ERROR: Gagal mengimpor build_transport_graph_with_costs dari pulp_solver.")
        return None, None

# --- 2. Fungsi Fitness ---

def calculate_path_fitness(G, path, weights):
    """Calculates the combined cost (fitness) of a path based on weights."""
    if not path or len(path) < 2:
        return float('inf')

    total_cost = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        if not G.has_edge(u, v):
            return float('inf') # Invalid path

        data = G.get_edge_data(u, v)
        waktu_ij = data.get('Waktuij', 0)
        biaya_ij = data.get('Biayaij', 0)

        # Biaya dasar (waktu + biaya moneter)
        cost = (weights['waktu'] * waktu_ij) + (weights['biaya'] * biaya_ij)

        # Tambahkan penalti transit abstrak HANYA jika terjadi perpindahan koridor
        if data.get('type') == 'transfer' and u[1] != v[1]:
            cost += weights.get('transit', 0) # Gunakan weights['transit'] saja

        total_cost += cost
    return total_cost

# --- 3. Operator Genetika SMA (Adaptasi Rumus 6 untuk Pathfinding) ---

def generate_random_path(G, start_nodes, end_nodes):
    """Generates a random path using shortest_path with random weights."""
    try:
        source = random.choice(start_nodes)
        target = random.choice(end_nodes)
        for u, v in G.edges(): G[u][v]['random_weight'] = random.uniform(0.1, 1.0)
        path = nx.shortest_path(G, source, target, weight='random_weight')
        return path
    except (nx.NetworkXNoPath, IndexError, nx.NodeNotFound):
        return None

def mutation_operator_faithful(G, path_xi, vc, start_nodes, end_nodes):

    # Probabilitas mutasi dikontrol oleh |vc| (Rumus 9)
    if len(path_xi) < 3: return path_xi
    new_path = list(path_xi)
    if random.random() < abs(vc): # |vc| sebagai probabilitas
        try:
            # Cari shortcut antara dua node acak di path_xi
            idx1, idx2 = sorted(random.sample(range(len(new_path)), 2))
            node1, node2 = new_path[idx1], new_path[idx2]
            if node1 == node2: return new_path
            sub_path = nx.shortest_path(G, node1, node2, weight='Waktuij')  # Shortcut berdasarkan waktu
            final_path = new_path[:idx1] + sub_path + new_path[idx2+1:]
            # Validasi
            if (final_path and final_path[0] in start_nodes and final_path[-1] in end_nodes and len(final_path) == len(set(final_path))):
                return final_path
        except (nx.NetworkXNoPath, ValueError, nx.NodeNotFound):
            pass    # Gagal mutasi, kembalikan path asli
    return new_path # Kembalikan path asli jika probabilitas tidak terpenuhi


def crossover_operator_faithful(G, best_path_xb, population, W_vec, vb, start_nodes, end_nodes):
    """Applies crossover (path merging) based on vb and W_vec."""
    # Probabilitas crossover dikontrol oleh |vb| (Rumus 9)
    new_path = list(best_path_xb)   # Mulai dari solusi terbaik (Xb)    
    if random.random() < abs(vb):   # |vb| sebagai probabilitas
        try:
            # Pilih path_A (XA) berdasarkan bobot W (Rumus 10)
            W_probs = np.array(W_vec); W_probs = None if W_probs.sum() == 0 else W_probs / W_probs.sum()
            idx_A = np.random.choice(len(population), p=W_probs)
            path_A, _ = population[idx_A]
            if not path_A or len(path_A) < 2: return new_path
            common_nodes = [n for n in (set(best_path_xb) & set(path_A)) if n not in start_nodes and n not in end_nodes]
            
            # Cari titik persimpangan (common node) antara Xb dan XA
            if not common_nodes: return new_path    # Jika tidak ada, kembali ke Xb
            crossover_node = random.choice(common_nodes)
            idx_best = best_path_xb.index(crossover_node); idx_a = path_A.index(crossover_node)
            final_path = best_path_xb[:idx_best] + path_A[idx_a:]
            if (final_path and final_path[0] in start_nodes and final_path[-1] in end_nodes and len(final_path) == len(set(final_path))):
                return final_path
        except Exception:
            pass
    return new_path


# --- 4. Fungsi Helper Baru untuk Rekonstruksi Hasil (TANPA is_difficult) ---

def build_detailed_journey_sma(G, path):
    """Builds the detailed_journey list from a path of nodes."""
    detailed_route_steps = []
    if not path or len(path) < 2: return detailed_route_steps
    seg_nodes = []

    def flush_travel_segment(nodes_segment):
        if len(nodes_segment) < 2: return
        start_node = nodes_segment[0]; end_node = nodes_segment[-1]
        corridor = start_node[1]; halte_names = [n[0] for n in nodes_segment]
        step = {"type": "travel", "koridor": corridor, "dari": halte_names[0], "ke": halte_names[-1], "melewati": halte_names[1:-1]}
        detailed_route_steps.append(step)

    for u, v in zip(path, path[1:]):
        if not G.has_edge(u, v): continue
        edge_data = G.get_edge_data(u, v); typ = edge_data.get('type', 'travel')
        if typ == 'travel':
            if not seg_nodes: seg_nodes = [u, v]
            elif u[1] == seg_nodes[0][1]: seg_nodes.append(v)
            else: flush_travel_segment(seg_nodes); seg_nodes = [u, v]
        else: # typ == 'transfer'
            flush_travel_segment(seg_nodes); seg_nodes = []
            # Hapus is_difficult dari step
            step = {"type": "transfer", "halte": u[0], "dari_koridor": u[1], "ke_koridor": v[1]}
            detailed_route_steps.append(step)
    flush_travel_segment(seg_nodes)
    return detailed_route_steps


def build_path_coords_sma(detailed_journey, path, nodes_file, edges_file, stop_map):
    """Builds the path_coords list by matching journey steps to GeoJSON edges."""
    path_coords = []
    coord_map = {} # Inisialisasi di luar try

    try:
        # --- Tahap 1: Bangun coord_map ---
        print("INFO (SMA PathCoords): Memulai pembangunan coord_map...")
        if stop_map and isinstance(stop_map, dict):
            # Pastikan data di stop_map valid
            for name, data in stop_map.items():
                if isinstance(data, dict) and 'lon' in data and 'lat' in data:
                     try:
                         coord_map[name] = (float(data['lon']), float(data['lat']))
                     except (ValueError, TypeError):
                          print(f"WARNING (SMA PathCoords): Format lon/lat tidak valid di stop_map untuk {name}")
                # else: print(f"DEBUG: Format data stop_map tidak valid untuk {name}")
        # print(f"DEBUG: coord_map dari stop_map berisi {len(coord_map)} item.")

        if not coord_map and os.path.exists(nodes_file):
            print("INFO (SMA PathCoords): stop_map kosong, mencoba membaca dari nodes_file...")
            nodes_gdf = gpd.read_file(nodes_file).to_crs("EPSG:4326")
            for _, r in nodes_gdf.iterrows():
                nm = r.get("name")
                if nm and nm not in coord_map and hasattr(r.geometry, 'x') and hasattr(r.geometry, 'y'):
                     try:
                         coord_map[nm] = (float(r.geometry.x), float(r.geometry.y))
                     except (ValueError, TypeError):
                          print(f"WARNING (SMA PathCoords): Format geometri tidak valid di nodes_file untuk {nm}")
            print(f"INFO (SMA PathCoords): Membangun coord_map dari file, {len(coord_map)} halte ditemukan.")
        elif not coord_map:
             print("WARNING (SMA PathCoords): Gagal membangun coord_map.")

        # --- Tahap 2: Bangun ref_map dan path_coords ---
        print("INFO (SMA PathCoords): Memulai pembangunan ref_map dan path_coords...")
        edges_data = None; ref_map = {}
        if os.path.exists(edges_file):
            with open(edges_file, "r", encoding="utf-8") as f: edges_data = json.load(f)
        if edges_data:
            for feat in edges_data.get("features", []):
                props = feat.get("properties", {}) or {}; ref_key = str(props.get("ref") or "").strip()
                coords_list = feat.get("geometry", {}).get("coordinates", [])
                # Validasi format koordinat LEBIH KETAT
                if ref_key and isinstance(coords_list, list) and \
                   all(isinstance(c, (list, tuple)) and len(c) == 2 and \
                       all(isinstance(n, (int, float)) for n in c) for c in coords_list):
                    ref_map.setdefault(ref_key, []).append({"coords": coords_list})
                # else:
                    # if ref_key: print(f"DEBUG: Format koordinat edge tidak valid untuk koridor '{ref_key}'")

        def nearest_index(coords_list, target_coord):
            best_i, best_d = None, 1e9
            if not isinstance(target_coord, (tuple, list)) or len(target_coord) != 2: return None
            if not coords_list: return None
            target_lon, target_lat = target_coord # Unpack setelah validasi
            for i, point_coord in enumerate(coords_list):
                 if not isinstance(point_coord, (list, tuple)) or len(point_coord) != 2: continue
                 try:
                     lon, lat = point_coord[0], point_coord[1]
                     # Pastikan numerik sebelum haversine
                     if not all(isinstance(n, (int, float)) for n in [lon, lat, target_lon, target_lat]): continue
                     d = haversine(lon, lat, target_lon, target_lat)
                     if d < best_d: best_d = d; best_i = i
                 except Exception: continue # Abaikan jika ada error kalkulasi
            return best_i

        print(f"INFO (SMA PathCoords): Memproses {len(detailed_journey)} langkah perjalanan...")
        for idx_step, step in enumerate(detailed_journey):
            # Dapatkan koordinat dari coord_map (sudah tuple (lon, lat) atau None)
            start_coord = coord_map.get(step.get("dari")); end_coord = coord_map.get(step.get("ke")); t_coord = coord_map.get(step.get("halte"))

            # Simpan koordinat ke step (selalu sebagai list atau None)
            step["coords_dari"] = list(start_coord) if start_coord else None
            step["coords_ke"] = list(end_coord) if end_coord else None
            step["coords"] = list(t_coord) if t_coord else None

            if step.get("type") == "travel":
                kor = str(step.get("koridor")); candidates = ref_map.get(kor) or []
                seg_added = False
                if start_coord and end_coord: # Hanya proses jika start dan end coord ada
                    for feat in candidates:
                        coords_geom = feat["coords"]
                        if coords_geom: # Pastikan geometri edge tidak kosong
                            i0 = nearest_index(coords_geom, start_coord); i1 = nearest_index(coords_geom, end_coord)
                            if i0 is not None and i1 is not None: # Pastikan index ditemukan
                                part = coords_geom[i0:i1+1] if i0 <= i1 else list(reversed(coords_geom[i1:i0+1]))
                                if part: # Pastikan hasil slice tidak kosong
                                     # Filter lagi untuk memastikan semua point valid sebelum extend
                                     valid_part = [p for p in part if isinstance(p, (list, tuple)) and len(p) == 2]
                                     if valid_part:
                                          if path_coords and valid_part and path_coords[-1] == valid_part[0]:
                                               path_coords.extend(valid_part[1:])
                                          else:
                                               path_coords.extend(valid_part)
                                          seg_added = True; break
                # Fallback hanya jika segmen tidak ketemu DAN start/end coord ada
                if not seg_added and start_coord and end_coord:
                     # print(f"DEBUG Fallback travel: Koridor {kor}")
                     if not path_coords or path_coords[-1] != list(start_coord): path_coords.append(list(start_coord))
                     path_coords.append(list(end_coord))

            elif step.get("type") == "transfer" and t_coord:
                if not path_coords or path_coords[-1] != list(t_coord): path_coords.append(list(t_coord))

        print(f"INFO (SMA PathCoords): Selesai memproses langkah, {len(path_coords)} titik ditemukan.")

    except Exception as e:
        # --- BLOK FALLBACK YANG LEBIH AMAN ---
        print(f"❌ ERROR UTAMA building path_coords in SMA: {type(e).__name__} - {e}")
        print("INFO (SMA): Menggunakan fallback path_coords (garis lurus antar node).")
        path_coords = [] # Reset path_coords jika error di try block
        # Pastikan coord_map sudah terdefinisi (dari luar try)
        if coord_map and path and isinstance(path, list):
            for node_data in path: # Ubah nama variabel agar tidak bentrok
                halte_node_name = None
                # Cek format node_data dengan lebih hati-hati
                if isinstance(node_data, tuple) and len(node_data) > 0 and isinstance(node_data[0], str):
                    halte_node_name = node_data[0]
                # else: print(f"DEBUG Fallback: Format node tidak terduga: {node_data}")

                if halte_node_name:
                    coord = coord_map.get(halte_node_name)
                    # Cek format coord dari coord_map
                    if isinstance(coord, tuple) and len(coord) == 2:
                        try:
                            # Coba konversi lon/lat ke float dan buat list
                            lon = float(coord[0])
                            lat = float(coord[1])
                            path_coords.append([lon, lat])
                        except (ValueError, TypeError):
                            print(f"WARNING (SMA Fallback): Format koordinat tidak valid untuk {halte_node_name}: {coord}")
                    # else: print(f"DEBUG Fallback: Coord tidak ditemukan atau format salah untuk {halte_node_name}")
        # else: print(f"DEBUG Fallback: Gagal karena coord_map kosong atau path tidak valid.")
        # --- AKHIR FALLBACK ---

    # Validasi final
    final_path_coords = [pc for pc in path_coords if isinstance(pc, list) and len(pc) == 2]
    if len(final_path_coords) != len(path_coords):
         print("WARNING (SMA): Beberapa koordinat tidak valid di path_coords final.")

    return final_path_coords


# --- 5. Fungsi Utama SMA (Menggunakan Helper Baru) ---
def find_route_with_sma(G, stop_map, start_stop, end_stop, weights,
                        n_agents=50, max_iter=100, z_param=0.03):
    """Finds the best route using the Slime Mould Algorithm."""
    warnings.filterwarnings('ignore', category=RuntimeWarning)

    start_nodes = [n for n in G.nodes() if n[0] == start_stop]
    end_nodes = [n for n in G.nodes() if n[0] == end_stop]
    if not start_nodes: return {"error": f"Halte Asal '{start_stop}' tdk terhubung."}
    if not end_nodes: return {"error": f"Halte Tujuan '{end_stop}' tdk terhubung."}

    # --- Inisialisasi Populasi ---
    population = []; print(f"INFO (SMA): Menginisialisasi populasi {n_agents} agen...")
    for _ in range(n_agents):
        path = generate_random_path(G, start_nodes, end_nodes)
        if path:
            fitness = calculate_path_fitness(G, path, weights)
            if fitness != float('inf'): population.append((path, fitness))
    if not population: return {"error": "Gagal inisialisasi populasi SMA."}
    population.sort(key=lambda x: x[1]); BestSol = population[0]    # BestSol = Xb (Solusi terbaik)
    print(f"INFO (SMA): Fitness awal terbaik: {BestSol[1]:.4f}")

    # --- Loop Iterasi SMA ---
    for t in range(max_iter):
        # Hitung parameter a (Rumus 8)
        a = np.arctanh(-(t / max_iter) + 1) if t != max_iter else 0
        
        # Hitung Bobot W (Rumus 10)
        SmellIndex = sorted(range(len(population)), key=lambda k: population[k][1])
        W_vec = np.zeros(len(population)); bF = population[SmellIndex[0]][1]; wF = population[SmellIndex[-1]][1]
        for idx, i in enumerate(SmellIndex):
            r = random.random(); S_i = population[i][1]; denom = bF - wF
            log_val = 0 if denom == 0 else np.log((bF - S_i) / (denom + 1e-10) + 1)
            W_vec[i] = 1 + r * log_val if i < len(population) / 2 else 1 - r * log_val
        if (t + 1) % 20 == 0: print(f"INFO (SMA): Iter {t+1}/{max_iter}, Fitness: {BestSol[1]:.4f}")
        
        # Update Posisi Setiap Agen (Implementasi Rumus 6)
        new_pop = list(population)
        for i in range(len(population)):
            curr_path, curr_fit = population[i]; rand = random.random()
            
            # Kasus 1: Eksplorasi Acak (jika rand < z)
            if rand < z_param: new_path = generate_random_path(G, start_nodes, end_nodes)
            else:
                
                # Kasus 2 & 3: Eksploitasi
                # Hitung parameter p (Rumus 7)
                
                p = np.tanh(abs(curr_fit - BestSol[1])); 
                r = random.random()
                
                # Kasus 2: Mendekati Makanan (jika r < p)
                if r < p:
                    # Hitung parameter vb (Logika Rumus 9)
                    vb = (2 * a * r) - a
                    # Panggil operator crossover (adaptasi Xb + vb*(W*XA - XB))
                    new_path = crossover_operator_faithful(G, BestSol[0], population, W_vec, vb, start_nodes, end_nodes)
                # Panggil operator crossover (adaptasi Xb + vb*(W*XA - XB))
                else:
                    # Hitung parameter vc (Logika Rumus 9)
                    vc_range = 1 - (t / max_iter); vc = (2 * vc_range * r) - vc_range
                    # Panggil operator mutasi (adaptasi vc*Xi)
                    new_path = mutation_operator_faithful(G, curr_path, vc, start_nodes, end_nodes)
                    
            # Evaluasi & Seleksi Elitis
            if new_path:
                new_fit = calculate_path_fitness(G, new_path, weights)
                if new_fit < curr_fit: new_pop[i] = (new_path, new_fit)
        
        # --- Inisialisasi Populasi ---
        population = new_pop; population.sort(key=lambda x: x[1])
        if population[0][1] < BestSol[1]: BestSol = population[0]   # Update Xb (BestSol)

    print(f"INFO (SMA): Optimasi Selesai. Fitness Optimal: {BestSol[1]:.4f}")

    # --- Gunakan Fungsi Helper untuk Hasil Akhir ---
    final_metrics = calculate_final_metrics(G, BestSol[0])
    if "error" in final_metrics: return final_metrics

    detailed_journey = build_detailed_journey_sma(G, BestSol[0])

    BASE_DIR = Path(__file__).resolve().parent.parent # /myapp
    nodes_file = BASE_DIR / "static" / "data" / "cleaned_nodes_new.geojson"
    edges_file = BASE_DIR / "static" / "data" / "transjakarta_edges.geojson"
    coord_map = {name: (data['lon'], data['lat']) for name, data in stop_map.items()} if stop_map else {}

    path_coords = build_path_coords_sma(detailed_journey, BestSol[0], nodes_file, edges_file, coord_map)

    # Gabungkan hasil
    final_result = {
        "detailed_journey": detailed_journey,
        "jarak_km": final_metrics["jarak_km"],
        "waktu_tempuh_menit": final_metrics["waktu_tempuh_menit"],
        "jumlah_transit": final_metrics["jumlah_transit"],
        "path_nodes": BestSol[0],
        "path_coords": path_coords,
        "objective_cost": BestSol[1]
    }
    return final_result