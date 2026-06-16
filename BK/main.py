import trimesh
import numpy as np
import os
import pymeshlab
import networkx as nx
import mapbox_earcut as earcut

# ================= НАСТРОЙКИ (CONFIGURATION) =================
OUTPUT_DIR = "output_steps"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Пути к файлам
PATH_MODEL_TARGET = r'/Users/retro/Documents/Project 1/UpperJaw_top.stl'  # Целевая форма (после препарирования)
PATH_MODEL_SOURCE = r'/Users/retro/Documents/Project 1/Teeth.stl'        # Исходная форма (до препарирования)

# Параметры капы
CAP_THICKNESS = 2.0   # мм - толщина стенки капы
CLEARANCE = 0.05      # мм - технологический зазор для посадки

# Параметры прорезей (шахматный паттерн)
SLOT_WIDTH = 1.0      # мм - ширина прорези (соответствует диаметру бора)
SLOT_STEP = 1.0       # мм - шаг между центрами прорезей (1.0 = сплошные линии)
Y_BRIDGE = 5.0        # мм - ширина боковых мостиков (прочность конструкции)

# Параметры юбки (фиксация)
SKIRT_ZONE = 3.0      # мм - высота зоны юбки, вырезаемой из цельной капы
SKIRT_POSITION = 'top'# 'top' - сверху (для верхних зубов), 'bottom' - снизу (для нижних)

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================

def save_mesh(mesh, filename, step_name=""):
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        mesh.export(filepath)
        if step_name: print(f"✅ {step_name} -> {filename}")
        return mesh
    except Exception as e:
        print(f"❌ Ошибка сохранения {filename}: {e}")
        return None

def check_coordinates(mesh, name, original_bounds=None):
    bounds = mesh.bounds
    if original_bounds is not None:
        diff = np.abs(bounds - original_bounds).max()
        status = "✓" if diff < 0.01 else ""
        print(f"   {status} {name}: отклонение {diff:.4f} мм")

def repair_mesh_with_pymeshlab(mesh, name):
    print(f"🔧 Ремонт: {name}")
    original_bounds = mesh.bounds.copy()
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces))
    
    try: ms.apply_filter('meshing_merge_close_vertices', threshold=pymeshlab.AbsoluteValue(0.0001))
    except: pass
    try:
        ms.apply_filter('meshing_remove_duplicate_faces')
        ms.apply_filter('meshing_remove_null_faces')
        ms.apply_filter('meshing_remove_duplicate_vertices')
    except: pass
    try:
        ms.apply_filter('meshing_repair_non_manifold_edges')
        ms.apply_filter('meshing_repair_non_manifold_vertices')
    except: pass
    try: ms.apply_filter('meshing_close_holes', maxholesize=100)
    except: pass
    
    result = trimesh.Trimesh(vertices=ms.current_mesh().vertex_matrix(), faces=ms.current_mesh().face_matrix())
    result.fix_normals()
    ms.clear()
    check_coordinates(result, f"{name} (после ремонта)", original_bounds)
    return result

def solidify_open_mesh(mesh, name, base_z=None):
    """Закрывает большие открытые края через boundary + earcut."""
    if mesh.is_watertight: return mesh
    original_bounds = mesh.bounds.copy()
    
    edges = mesh.edges_sorted
    edge_counts = {}
    for edge in edges:
        key = tuple(edge)
        edge_counts[key] = edge_counts.get(key, 0) + 1
    boundary_edges = [np.array(k) for k, count in edge_counts.items() if count % 2 != 0]
    if not boundary_edges: return mesh
    
    g = nx.Graph()
    g.add_edges_from(boundary_edges)
    cycles = nx.cycle_basis(g)
    if not cycles: return mesh
    
    boundary_indices = max(cycles, key=len)
    num_b_verts = len(boundary_indices)
    
    boundary_z = mesh.vertices[boundary_indices, 2]
    avg_boundary_z = np.mean(boundary_z)
    min_z, max_z = mesh.vertices[:, 2].min(), mesh.vertices[:, 2].max()
    mid_z = (min_z + max_z) / 2
    
    jaw_type = 'upper' if avg_boundary_z > mid_z else 'lower'
    cap_z = (max_z if base_z is None else base_z) if jaw_type == 'upper' else (min_z if base_z is None else base_z)
    
    new_vertices = mesh.vertices.copy()
    new_faces = list(mesh.faces.copy())
    start_idx = len(new_vertices)
    
    boundary_vertices = mesh.vertices[boundary_indices].copy()
    cap_vertices = boundary_vertices.copy()
    cap_vertices[:, 2] = cap_z
    new_vertices = np.vstack([new_vertices, cap_vertices])
    
    for i in range(num_b_verts):
        next_i = (i + 1) % num_b_verts
        v_tc, v_tn = boundary_indices[i], boundary_indices[next_i]
        v_bc, v_bn = start_idx + i, start_idx + next_i
        if v_tc != v_bc or v_tn != v_bn:
            if jaw_type == 'lower':
                new_faces.extend([[v_tc, v_bc, v_bn], [v_tc, v_bn, v_tn]])
            else:
                new_faces.extend([[v_tc, v_bn, v_bc], [v_tc, v_tn, v_bn]])
    
    cap_2d = cap_vertices[:, :2]
    cap_faces_2d = earcut.triangulate_float64(cap_2d, np.array([len(cap_2d)], dtype=np.int32)).reshape(-1, 3)
    if jaw_type == 'upper': cap_faces_2d = cap_faces_2d[:, ::-1]
    new_faces.extend(cap_faces_2d + start_idx)
    
    solid_mesh = trimesh.Trimesh(vertices=new_vertices, faces=np.array(new_faces, dtype=np.int64))
    solid_mesh.fix_normals()
    check_coordinates(solid_mesh, f"{name} (solidify)", original_bounds)
    return solid_mesh

def add_skirt_by_copying(cap_with_slots, original_base_cap, skirt_zone=3.0, position='top'):
    """Создаёт юбку путём вырезания части цельной капы и объединения."""
    bounds = cap_with_slots.bounds
    z_min, z_max = bounds[0][2], bounds[1][2]
    
    cut_z_min = z_max - skirt_zone if position == 'top' else z_min - 5
    cut_z_max = z_max + 5 if position == 'top' else z_min + skirt_zone
    
    cutter_size = [bounds[1][0]-bounds[0][0]+30, bounds[1][1]-bounds[0][1]+30, cut_z_max-cut_z_min+10]
    cutter = trimesh.creation.box(extents=cutter_size)
    cutter.apply_transform(trimesh.transformations.translation_matrix([
        (bounds[0][0]+bounds[1][0])/2, (bounds[0][1]+bounds[1][1])/2, (cut_z_min+cut_z_max)/2
    ]))
    
    try:
        skirt_piece = trimesh.boolean.intersection([original_base_cap, cutter], engine='manifold')
    except:
        try: skirt_piece = trimesh.boolean.intersection([original_base_cap, cutter], engine='blender')
        except: return cap_with_slots
    
    try:
        return trimesh.boolean.union([cap_with_slots, skirt_piece], engine='manifold')
    except:
        try: return trimesh.boolean.union([cap_with_slots, skirt_piece], engine='blender')
        except: return trimesh.util.concatenate([cap_with_slots, skirt_piece])

# ================= ГЛАВНЫЙ ЦИКЛ =================
print("🚀 Генерация хирургического шаблона")

# --- ЭТАП 1: Загрузка и ремонт ---
try:
    raw_1 = trimesh.load(PATH_MODEL_TARGET, force='mesh')
    bounds_1_orig = raw_1.bounds.copy()
    solid_1 = solidify_open_mesh(repair_mesh_with_pymeshlab(raw_1, "Model_1"), "Model_1")
    save_mesh(solid_1, "01_solid_model_1.stl", "Solid Model_1")

    raw_2 = trimesh.load(PATH_MODEL_SOURCE, force='mesh')
    bounds_2_orig = raw_2.bounds.copy()
    repaired_2 = repair_mesh_with_pymeshlab(raw_2, "Model_2")
    solid_2 = solid_2 = repaired_2 if repaired_2.is_watertight else solidify_open_mesh(repaired_2, "Model_2")
    save_mesh(solid_2, "02_solid_model_2.stl", "Solid Model_2")
except Exception as e:
    print(f"❌ Ошибка загрузки/ремонта: {e}"); exit()

# --- ЭТАП 2: Объем редукции ---
try:
    volume_to_remove = trimesh.boolean.difference([solid_2, solid_1], engine='manifold')
    volume_to_remove.visual.vertex_colors = [255, 165, 0, 255]
    save_mesh(volume_to_remove, "03_volume_to_remove.stl", "Volume to remove")
except Exception as e:
    print(f"❌ Ошибка вычисления объема: {e}"); exit()

# --- ЭТАП 3: Базовая капа ---
inner = repaired_2.copy()
inner.vertices += inner.vertex_normals * CLEARANCE
outer = repaired_2.copy()
outer.vertices += outer.vertex_normals * (CLEARANCE + CAP_THICKNESS)

try:
    base_cap = trimesh.boolean.difference([outer, inner], engine='manifold')
except:
    try: base_cap = trimesh.boolean.difference([outer, inner], engine='blender')
    except: base_cap = outer.copy()

base_cap.visual.vertex_colors = [0, 0, 255, 255]
save_mesh(base_cap, "04_base_cap.stl", "Base Cap")

# --- ЭТАП 4: Шахматные прорези ---
bounds = volume_to_remove.bounds
x_min, x_max = bounds[0][0], bounds[1][0]
y_min, y_max = bounds[0][1], bounds[1][1]
z_min, z_max = bounds[0][2], bounds[1][2]
slot_height = (z_max - z_min) + 10
slot_y_size = (y_max - y_min) + Y_BRIDGE

slot_boxes_1, slot_boxes_2 = [], []
for idx, x_pos in enumerate(np.arange(x_min, x_max, SLOT_STEP)):
    box = trimesh.creation.box(extents=[SLOT_WIDTH, slot_y_size, slot_height])
    box.apply_transform(trimesh.transformations.translation_matrix([x_pos + SLOT_WIDTH/2, (y_min+y_max)/2, (z_min+z_max)/2]))
    try:
        if trimesh.boolean.intersection([box, volume_to_remove], engine='manifold').volume > 0.1:
            (slot_boxes_1 if idx % 2 == 0 else slot_boxes_2).append(box)
    except: pass

mask_1 = trimesh.util.concatenate(slot_boxes_1) if slot_boxes_1 else trimesh.creation.box(extents=[1,1,1])
mask_2 = trimesh.util.concatenate(slot_boxes_2) if slot_boxes_2 else trimesh.creation.box(extents=[1,1,1])
save_mesh(mask_1, "04a_mask_1.stl", "Mask 1")
save_mesh(mask_2, "04b_mask_2.stl", "Mask 2")

# --- ЭТАП 5: Depth Stop ---
try:
    space_to_drill = trimesh.boolean.difference([base_cap, solid_1], engine='manifold')
except: space_to_drill = base_cap.copy()

try:
    drill_1 = trimesh.boolean.intersection([mask_1, space_to_drill], engine='manifold')
    drill_2 = trimesh.boolean.intersection([mask_2, space_to_drill], engine='manifold')
    save_mesh(drill_1, "05_drill_1.stl", "Drill 1")
    save_mesh(drill_2, "05_drill_2.stl", "Drill 2")
except Exception as e:
    print(f"❌ Ошибка Depth Stop: {e}"); exit()

# --- ЭТАП 6: Капы с прорезями ---
try:
    cap_1 = trimesh.boolean.difference([space_to_drill, drill_1], engine='manifold')
    cap_2 = trimesh.boolean.difference([space_to_drill, drill_2], engine='manifold')
except Exception as e:
    print(f"❌ Ошибка формирования кап: {e}"); exit()

# --- ЭТАП 7: Юбка через копирование ---
cap_1 = add_skirt_by_copying(cap_1, base_cap, SKIRT_ZONE, SKIRT_POSITION)
cap_2 = add_skirt_by_copying(cap_2, base_cap, SKIRT_ZONE, SKIRT_POSITION)

# --- ЭТАП 8: Финальное вычитание (посадочная поверхность) ---
try:
    final_1 = trimesh.boolean.difference([cap_1, solid_1], engine='manifold')
    final_2 = trimesh.boolean.difference([cap_2, solid_1], engine='manifold')
except:
    final_1, final_2 = cap_1, cap_2

final_1.visual.vertex_colors = [0, 255, 255, 255]
final_2.visual.vertex_colors = [255, 0, 255, 255]
save_mesh(final_1, "06_FINAL_Cap_Step_1.stl", "FINAL Cap 1")
save_mesh(final_2, "07_FINAL_Cap_Step_2.stl", "FINAL Cap 2")

print("="*50)
print("✅ Генерация завершена. Файлы в:", OUTPUT_DIR)