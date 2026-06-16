import os
import trimesh
import numpy as np
import networkx as nx
import mapbox_earcut as earcut

def solidify_jaw_top(input_path, output_path, cap_z=None):
    if not os.path.exists(input_path):
        print(f"Ошибка: Файл не найден по пути {input_path}")
        return
        
    print("Загрузка модели...")
    mesh = trimesh.load(input_path)
    
    original_vertices = mesh.vertices.copy()
    original_faces = mesh.faces.copy()
    
    print(f"Оригинальная модель: {len(original_vertices)} вершин, {len(original_faces)} граней")
    print(f"Оригинальный bounding box: "
          f"X[{original_vertices[:, 0].min():.2f}:{original_vertices[:, 0].max():.2f}] "
          f"Y[{original_vertices[:, 1].min():.2f}:{original_vertices[:, 1].max():.2f}] "
          f"Z[{original_vertices[:, 2].min():.2f}:{original_vertices[:, 2].max():.2f}]")
    
    if mesh.is_watertight:
        print("Модель уже замкнута.")
        mesh.export(output_path)
        return

    # 1. Уровень крышки = МАКСИМАЛЬНЫЙ Z скана (не выше!)
    max_z = original_vertices[:, 2].max()
    if cap_z is None:
        cap_z = max_z  
    
    print(f"Максимальный Z скана: {max_z:.2f}, крышка будет на Z: {cap_z:.2f}")

    # 2. Получаем открытые рёбра
    boundary_edges = mesh.edges_sorted[
        trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)
    ]
    
    if len(boundary_edges) == 0:
        print("Открытых краёв не найдено.")
        return

    # Собираем в цепочку
    g = nx.Graph()
    g.add_edges_from(boundary_edges)
    cycles = nx.cycle_basis(g)
    if not cycles:
        print("Не удалось собрать контур.")
        return
        
    boundary_indices = max(cycles, key=len)
    num_b_verts = len(boundary_indices)
    print(f"Граница: {num_b_verts} вершин.")

    # 3. Работаем с оригинальными вершинами
    new_vertices = original_vertices.copy()
    new_faces = list(original_faces.copy())
    start_idx = len(new_vertices)
    
    # 4. Вершины крышки — копируем boundary и ставим Z = max_z
    boundary_vertices = original_vertices[boundary_indices].copy()
    top_vertices = boundary_vertices.copy()
    top_vertices[:, 2] = cap_z  
    
    new_vertices = np.vstack([new_vertices, top_vertices])
    
    # 5. Стенки — соединяем границу с крышкой
    for i in range(num_b_verts):
        next_i = (i + 1) % num_b_verts
        
        v_top_curr = boundary_indices[i]
        v_top_next = boundary_indices[next_i]
        v_cap_curr = start_idx + i
        v_cap_next = start_idx + next_i
        
        if v_top_curr != v_cap_curr or v_top_next != v_cap_next:
            # Для верхней крышки порядок граней отличается от нижней (чтобы нормали смотрели наружу)
            new_faces.append([v_top_curr, v_cap_next, v_cap_curr])
            new_faces.append([v_top_curr, v_top_next, v_cap_next])

    # 6. Крышка через earcut
    print("Триангуляция крышки...")
    top_2d = top_vertices[:, :2]
    rings = np.array([len(top_2d)], dtype=np.int32)
    top_faces_2d = earcut.triangulate_float64(top_2d, rings)
    top_faces_2d = top_faces_2d.reshape(-1, 3)
    
    # Для верхней крышки инвертируем порядок граней, чтобы нормаль смотрела ВВЕРХ (+Z)
    top_faces_2d = top_faces_2d[:, ::-1]
    
    top_faces = top_faces_2d + start_idx
    new_faces.extend(top_faces)

    # 7. Сборка
    solid_mesh = trimesh.Trimesh(
        vertices=new_vertices,
        faces=np.array(new_faces, dtype=np.int64)
    )
    solid_mesh.fix_normals()
    
    # Проверка: верхняя точка не должна измениться
    new_max_z = solid_mesh.vertices[:, 2].max()
    print(f"\nПроверка координат:")
    print(f"  Оригинальный max Z: {max_z:.4f}")
    print(f"  Новый max Z:        {new_max_z:.4f}")
    print(f"  Совпадает: {np.isclose(max_z, new_max_z)}")
    
    print(f"\nРезультат:")
    print(f"  Вершин: {len(solid_mesh.vertices)}")
    print(f"  Граней: {len(solid_mesh.faces)}")
    print(f"  Герметична: {solid_mesh.is_watertight}")
    print(f"  Bounding box: "
          f"X[{solid_mesh.vertices[:, 0].min():.2f}:{solid_mesh.vertices[:, 0].max():.2f}] "
          f"Y[{solid_mesh.vertices[:, 1].min():.2f}:{solid_mesh.vertices[:, 1].max():.2f}] "
          f"Z[{solid_mesh.vertices[:, 2].min():.2f}:{solid_mesh.vertices[:, 2].max():.2f}]")

    solid_mesh.export(output_path)
    print(f"Solid Model_1 watertight? {solid_mesh.is_watertight}")
    print(f"\n✓ Сохранено в: {output_path}")

input_file = r'/Users/retro/Documents/Project 1/UpperJaw.stl'
output_file = r"./good.stl"

if __name__ == "__main__":
    solidify_jaw_top(input_file, output_file)