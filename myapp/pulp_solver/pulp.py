# -*- coding: utf-8 -*-
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point
from math import radians, sin, cos, sqrt, asin
from datetime import time, datetime
import warnings, os, re, itertools

try:
    import pulp
except ImportError:
    pulp = None
    print("⚠️ Library 'pulp' tidak ditemukan. Instal dengan: py -m pip install pulp")

# --- Utilitas ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1; dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c  # dalam kilometer

def calculate_base_price(departure_time_str):
    try:
        dep_time = datetime.strptime(departure_time_str, '%H:%M').time()
    except ValueError:
        return 3500
    time_start, time_end = time(5, 0), time(7, 0)
    return 2000 if time_start <= dep_time <= time_end else 3500

def calculate_final_metrics(G, path):
    """Menghitung metrik akhir (waktu, jarak, transit) dari sebuah path node."""
    total_dist = 0.0
    total_time = 0.0 # dalam jam
    total_trans = 0

    if not path or len(path) < 2:
        return {"waktu_tempuh_menit": 0, "jarak_km": 0, "jumlah_transit": 0, "error": "Path tidak valid"}

    for u, v in zip(path, path[1:]):
        if not G.has_edge(u, v):
            # Seharusnya tidak terjadi jika path valid, tapi sebagai pengaman
            print(f"WARNING: Edge tidak ditemukan di path: {u} -> {v}")
            continue 

        edge_data = G.get_edge_data(u, v)

        # Akumulasi Waktu dan Jarak untuk SEMUA edge yang valid di path
        total_time += edge_data.get('Waktuij', 0) 
        total_dist += edge_data.get('distance_km', 0)

        # Hitung transit HANYA jika edge bertipe 'transfer'
        if edge_data.get('type') == 'transfer':
            # Anda bisa tambahkan logika cek is_different_family di sini jika perlu
            # Tapi untuk jumlah transit, cek type saja cukup
            total_trans += 1

    return {
        "waktu_tempuh_menit": round(total_time * 60, 1),
        "jarak_km": round(total_dist, 2),
        "jumlah_transit": total_trans 
    }

# --- Bangun graf ---
def build_transport_graph_with_costs(nodes_file, edges_file,
                                     avg_speed_kmh=20, max_speed_kmh=50,
                                     avg_transfer_min=5,
                                     stop_dwell_time_seconds=30,
                                     delay_per_km_seconds=15,
                                     snap_threshold_m=500):
    try:
        nodes_gdf = gpd.read_file(nodes_file).to_crs("EPSG:4326")
        edges_gdf = gpd.read_file(edges_file).to_crs("EPSG:4326")
    except Exception as e:
        print(f"Error membaca file GeoJSON: {nodes_file} / {edges_file}: {e}")
        return None, None

    nodes_gdf = nodes_gdf.dropna(subset=['name'])
    nodes_gdf = nodes_gdf[nodes_gdf['name'].astype(str).str.strip() != '']
    if nodes_gdf.empty:
        print("Error: Tidak ada node valid.")
        return None, None

    nodes_gdf_proj = nodes_gdf.to_crs("EPSG:32748")
    edges_gdf_proj = edges_gdf.to_crs("EPSG:32748").reset_index(drop=True)

    joined_gdf = gpd.sjoin_nearest(nodes_gdf_proj, edges_gdf_proj,
                                   max_distance=snap_threshold_m, how='inner')
    stop_to_corridors = {}; corridor_to_stops = {}
    for _, row in joined_gdf.iterrows():
        stop_name = row['name_left']
        corridor_ref = row['ref']
        stop_geom_proj = row['geometry']
        corridor_geom_proj = edges_gdf_proj.geometry.iloc[row['index_right']]
        stop_to_corridors.setdefault(stop_name, set()).add(corridor_ref)
        corridor_to_stops.setdefault(corridor_ref, []).append((stop_name, stop_geom_proj, corridor_geom_proj))

    G = nx.DiGraph()
    dwell_time_hour = stop_dwell_time_seconds / 3600
    delay_per_km_hour = delay_per_km_seconds / 3600
    transfer_time_hour = avg_transfer_min / 60

    for corridor_ref, stops in corridor_to_stops.items():
        if len(stops) < 2:
            continue
        unique_stops = list({s[0]: s for s in stops}.values())
        line = unique_stops[0][2]
        sorted_stops = sorted(
            [(line.project(sg), sn, sg) for sn, sg, _ in unique_stops], key=lambda x: x[0]
        )
        for i in range(len(sorted_stops) - 1):
            _, s1n, s1gp = sorted_stops[i]
            _, s2n, s2gp = sorted_stops[i+1]
            n1, n2 = (s1n, corridor_ref), (s2n, corridor_ref)
            if n1 == n2:
                continue
            s1gw = gpd.GeoSeries([s1gp], crs="EPSG:32748").to_crs("EPSG:4326").iloc[0]
            s2gw = gpd.GeoSeries([s2gp], crs="EPSG:32748").to_crs("EPSG:4326").iloc[0]
            dist_km = haversine(s1gw.x, s1gw.y, s2gw.x, s2gw.y)
            
            # Sesuai deskripsi di Bab 2.5 bahwa waktu dihitung dari kombinasi 25 km/jam, stop 30 detik, dan delay 15 detik per km.
            travel_time_hour = dist_km / avg_speed_kmh + dwell_time_hour + (dist_km * delay_per_km_hour)
            
            
            G.add_edge(n1, n2, type='travel', Waktuij=travel_time_hour, Biayaij=0, Transitij=0, distance_km=dist_km)
            G.add_edge(n2, n1, type='travel', Waktuij=travel_time_hour, Biayaij=0, Transitij=0, distance_km=dist_km)

    for stop_name, corridors in stop_to_corridors.items():
        if len(corridors) > 1:
            cl = list(corridors)
            for i in range(len(cl)):
                for j in range(i+1, len(cl)):
                    n1, n2 = (stop_name, cl[i]), (stop_name, cl[j])
                    G.add_edge(n1, n2, type='transfer', Waktuij=transfer_time_hour, Biayaij=0, Transitij=1, distance_km=0)
                    G.add_edge(n2, n1, type='transfer', Waktuij=transfer_time_hour, Biayaij=0, Transitij=1, distance_km=0)

    print(f"Graf selesai. Nodes={G.number_of_nodes()}, Edges={G.number_of_edges()}")
    return G, stop_to_corridors

# --- MILP Route Finder ---
def find_route_with_pulp_weighted(G, stop_to_corridors, start_stop, end_stop, weights, nodes_file=None):
    if pulp is None:
        return {"error": "Library PuLP tidak terinstal."}
    if start_stop not in stop_to_corridors:
        return {"error": f"Halte Asal '{start_stop}' tidak ditemukan."}
    if end_stop not in stop_to_corridors:
        return {"error": f"Halte Tujuan '{end_stop}' tidak ditemukan."}

    # Ambil kandidat node di graf untuk start/end
    start_nodes = [n for n in G.nodes() if n[0] == start_stop]
    end_nodes = [n for n in G.nodes() if n[0] == end_stop]
    if not start_nodes or not end_nodes:
        return {"error": "Node asal atau tujuan tidak terhubung ke graf."}

    # Setup MILP
    prob = pulp.LpProblem("Transjakarta_MILP_Route", pulp.LpMinimize)
    
    # Variabel Keputusan (Rumus 5: x_ij binary)
    # x[(i, j)] = 1 jika edge (i, j) digunakan, 0 jika tidak
    
    x = pulp.LpVariable.dicts("x", G.edges(), cat=pulp.LpBinary)
    
    x_source = pulp.LpVariable.dicts("x_source", start_nodes, cat=pulp.LpBinary)
    x_sink = pulp.LpVariable.dicts("x_sink", end_nodes, cat=pulp.LpBinary)

    # Objektif Function (Rumus 1)
    
    obj = []
    for u, v in G.edges():
        data = G.get_edge_data(u, v)
        waktu = data.get('Waktuij', 0)                                                  # Parameter Waktu_ij
        biaya = data.get('Biayaij', 0)                                                  # Parameter Biaya_ij
        cost = (weights.get('waktu', 0) * waktu) + (weights.get('biaya', 0) * biaya)    # w_waktu * Waktu_ij + w_biaya * Biaya_ij
        
        # Implementasi parameter Transit_ij (bernilai 1 jika transfer antar koridor berbeda)
        
        if data.get('type') == 'transfer' and u[1] != v[1]:
            cost += weights.get('transit', 0)
        obj.append(cost * x[(u, v)])
    prob += pulp.lpSum(obj)

    # Batasan Sumber (Rumus 2, via Super Source)
    # # Hanya satu edge yang boleh keluar dari SOURCE
    prob += pulp.lpSum(x_source[s] for s in start_nodes) == 1
    
    # Batasan Tujuan (Rumus 3, via Super Sink)
    # Hanya satu edge yang boleh masuk ke SINK
    prob += pulp.lpSum(x_sink[e] for e in end_nodes) == 1

    # Flow conservation untuk semua node
    # Batasan Konservasi Aliran (Rumus 4: Aliran Masuk = Aliran Keluar)
    # Berlaku untuk semua node k (kecuali SOURCE dan SINK)
    for node in G.nodes():
        # Sigma(x_kj) untuk semua j yang keluar dari k
        out_f = pulp.lpSum(x.get((node, k), 0) for k in G.successors(node))
        
        # Sigma(x_ik) untuk semua i yang masuk ke k
        in_f = pulp.lpSum(x.get((j, node), 0) for j in G.predecessors(node))
        
        # Menetapkan batasan: Aliran Masuk = Aliran Keluar
        prob += in_f + x_source.get(node, 0) == out_f + x_sink.get(node, 0)

    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]
    if status != "Optimal":
        return {"error": f"Solusi tidak optimal: {status}"}

    # Ambil edges aktif
    active_edges = [(u, v) for u, v in G.edges() if x[(u, v)].varValue is not None and x[(u, v)].varValue > 0.9]

    # Rekonstruksi path sederhana (walk following active edges)
    # mulai dari node start yang aktif
    actual_start = next((s for s in start_nodes if x_source[s].varValue is not None and x_source[s].varValue > 0.9), None)
    if actual_start is None:
        # fallback: ambil start_nodes[0]
        actual_start = start_nodes[0]
    path = [actual_start]
    current = actual_start
    remaining = set(active_edges)
    safety = 0
    while safety < 500 and remaining:
        next_found = None
        for (u,v) in list(remaining):
            if u == current:
                next_found = v
                remaining.remove((u,v))
                break
        if not next_found:
            break
        path.append(next_found)
        current = next_found
        safety += 1

    # Pastikan path berakhir di salah satu end_nodes
    if not path or path[-1][0] != end_stop:
        # coba cek apakah ada sink var true
        if not any(x_sink.get(n) and getattr(x_sink.get(n), "varValue", 0) > 0.9 for n in end_nodes):
            return {"error": "Jalur tidak ditemukan lengkap."}

    final_metrics = calculate_final_metrics(G, path)
    if "error" in final_metrics:
        return final_metrics

    # Hitung ringkasan & susun detailed steps
    total_dist = 0.0
    total_time = 0.0   # dalam jam
    total_trans = 0
    total_penalty = 0.0
    detailed_route_steps = []

    # Kita gabungkan segmen travel per koridor
    seg_corridor = None
    seg_nodes = []

    def flush_travel_segment(nodes_segment):
        if len(nodes_segment) < 2:
            return
        start_node = nodes_segment[0]
        end_node = nodes_segment[-1]
        corridor = start_node[1]
        halte_names = [n[0] for n in nodes_segment]  # semua halte yang dilewati
        step = {
            "type": "travel",
            "koridor": corridor,
            "dari": halte_names[0],
            "ke": halte_names[-1],
            "melewati": halte_names[1:-1],  # halte tengah
        }
        detailed_route_steps.append(step)

    # Iterasi pasangan consecutive
    for u, v in zip(path, path[1:]):
        if not G.has_edge(u, v):
            # kalau edge tidak ada, skip
            continue
        edge_data = G.get_edge_data(u, v)
        typ = edge_data.get('type', 'travel')

        if typ == 'travel':
            # tambahkan metric
            total_dist += edge_data.get('distance_km', 0)
            total_time += edge_data.get('Waktuij', 0)  # jam
            total_penalty += edge_data.get('Biayaij', 0) or 0
            # segmen
            if seg_corridor is None:
                seg_corridor = u[1]
                seg_nodes = [u, v]
            else:
                # jika koridor sama, extend; jika beda, flush lalu mulai seg baru
                if u[1] == seg_corridor:
                    seg_nodes.append(v)
                else:
                    flush_travel_segment(seg_nodes)
                    seg_corridor = u[1]
                    seg_nodes = [u, v]
        else:  # transfer
            # flush existing travel segment dulu
            flush_travel_segment(seg_nodes)
            seg_corridor = None
            seg_nodes = []
            # tambahkan transfer step
            total_time += edge_data.get('Waktuij', 0)
            total_penalty += edge_data.get('Biayaij', 0) or 0
            total_trans += 1
            step = {
                "type": "transfer",
                "halte": u[0],
                "dari_koridor": u[1],
                "ke_koridor": v[1]
            }
            detailed_route_steps.append(step)

    # flush travel seg terakhir jika ada
    flush_travel_segment(seg_nodes)

    # Buat path_coords (lon, lat) bila nodes_file tersedia
        # --- Pastikan waktu_tempuh_menit selalu terdefinisi (dari total_time yang dihitung di atas)
    try:
        waktu_tempuh_menit = round(total_time * 60, 1)  # total_time ada dalam jam
    except Exception:
        waktu_tempuh_menit = 0.0
        
    # --- Build path_coords dari detailed_route_steps dan edges (jalur real, bukan garis lurus) ---
    path_coords = []
    try:
        import json

        # Tentukan lokasi file edges
        edges_file = None
        if nodes_file:
            edges_file = os.path.join(os.path.dirname(nodes_file), "transjakarta_edges.geojson")
        else:
            edges_file = os.path.join(
                os.path.dirname(__file__), "..", "static", "data", "transjakarta_edges.geojson"
            )

        edges_data = None
        if edges_file and os.path.exists(edges_file):
            with open(edges_file, "r", encoding="utf-8") as f:
                edges_data = json.load(f)

        # Buat peta koordinat halte (name -> (lon, lat))
        coord_map = {}
        if nodes_file and os.path.exists(nodes_file):
            try:
                nodes_gdf = gpd.read_file(nodes_file).to_crs("EPSG:4326")
                for _, r in nodes_gdf.iterrows():
                    nm = r.get("name") or r.get("halte_name")
                    if nm and nm not in coord_map:
                        coord_map[nm] = (r.geometry.x, r.geometry.y)
            except Exception:
                coord_map = {}

        # Buat peta ref koridor -> kumpulan koordinat edges
        ref_map = {}
        if edges_data:
            for feat in edges_data.get("features", []):
                props = feat.get("properties", {}) or {}
                ref_key = str(props.get("ref") or props.get("name") or "").strip()
                coords = feat.get("geometry", {}).get("coordinates", [])
                if ref_key:
                    ref_map.setdefault(ref_key, []).append({
                        "coords": coords,
                        "props": props
                    })

        # Fungsi bantu untuk cari titik terdekat di LineString
        def nearest_index(coords, coord):
            best_i, best_d = None, 1e9
            for i, (lon, lat) in enumerate(coords):
                d = haversine(lon, lat, coord[0], coord[1])
                if d < best_d:
                    best_d = d
                    best_i = i
            return best_i

        # Bangun path_coords per langkah perjalanan
        for step in detailed_route_steps:
            if step.get("type") == "travel":
                kor = str(step.get("koridor"))
                start_name = step.get("dari")
                end_name = step.get("ke")
                start_coord = coord_map.get(start_name)
                end_coord = coord_map.get(end_name)

                # Simpan koordinat halte untuk tampilan marker
                step["coords_dari"] = list(start_coord) if start_coord else None
                step["coords_ke"] = list(end_coord) if end_coord else None

                # Ambil semua segmen koridor
                candidates = ref_map.get(kor) or []
                seg_added = False
                for feat in candidates:
                    coords = feat["coords"]
                    if start_coord and end_coord and coords:
                        i0 = nearest_index(coords, start_coord)
                        i1 = nearest_index(coords, end_coord)
                        if i0 is None or i1 is None:
                            continue
                        if i0 <= i1:
                            part = coords[i0:i1+1]
                        else:
                            part = list(reversed(coords[i1:i0+1]))
                        if path_coords and part and path_coords[-1] == part[0]:
                            path_coords.extend(part[1:])
                        else:
                            path_coords.extend(part)
                        seg_added = True
                        step["koridor_props"] = feat.get("props", {})
                        break

                # Jika tidak ketemu segmen koridor, pakai fallback antarhalte langsung
                if not seg_added:
                    if start_coord:
                        if not path_coords or path_coords[-1] != [start_coord[0], start_coord[1]]:
                            path_coords.append([start_coord[0], start_coord[1]])
                    if end_coord:
                        path_coords.append([end_coord[0], end_coord[1]])

            elif step.get("type") == "transfer":
                halte_name = step.get("halte")
                step["coords"] = list(coord_map.get(halte_name)) if coord_map.get(halte_name) else None
                # tidak menambah path_coords, hanya marker

    except Exception as e:
        print("⚠️ Warning building path_coords:", e)
        # Fallback minimal jika gagal
        if 'coord_map' in locals() and coord_map:
            path_coords = []
            for n in path:
                nm = n[0]
                if nm in coord_map:
                    path_coords.append([coord_map[nm][0], coord_map[nm][1]])

    # Return hasil akhir (waktu_tempuh_menit sudah pasti ada)
    return {
        "detailed_journey": detailed_route_steps,
        "path": path,  # list nama halte
        "jarak_km": round(total_dist, 2),
        "waktu_tempuh_menit": waktu_tempuh_menit,
        "jumlah_transit": total_trans,
        "path_nodes": path,
        "path_coords": path_coords
    }



