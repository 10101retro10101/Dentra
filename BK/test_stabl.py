import os
import trimesh
import numpy as np
import networkx as nx
import mapbox_earcut as earcut

def solidify_jaw(input_path, output_path, base_z=None):
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

    # 1. Уровень дна = МИНИМАЛЬНЫЙ Z скана (не ниже!)
    min_z = original_vertices[:, 2].min()
    if base_z is None:
        base_z = min_z  # ← КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
    
    print(f"Минимальный Z скана: {min_z:.2f}, дно будет на Z: {base_z:.2f}")

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
    
    # 4. Вершины дна — копируем boundary и ставим Z = min_z
    boundary_vertices = original_vertices[boundary_indices].copy()
    bottom_vertices = boundary_vertices.copy()
    bottom_vertices[:, 2] = base_z  # Z = минимальному Z скана
    
    new_vertices = np.vstack([new_vertices, bottom_vertices])
    
    # 5. Стенки (юбка) — если boundary вершины уже на min_z, стенки будут нулевой высоты
    #    но если есть boundary выше min_z — стенки закроют дыру
    for i in range(num_b_verts):
        next_i = (i + 1) % num_b_verts
        
        v_top_curr = boundary_indices[i]
        v_top_next = boundary_indices[next_i]
        v_bot_curr = start_idx + i
        v_bot_next = start_idx + next_i
        
        # Пропускаем вырожденные грани (если top и bottom совпадают)
        if v_top_curr != v_bot_curr or v_top_next != v_bot_next:
            new_faces.append([v_top_curr, v_bot_curr, v_bot_next])
            new_faces.append([v_top_curr, v_bot_next, v_top_next])

    # 6. Дно через earcut
    print("Триангуляция дна...")
    bottom_2d = bottom_vertices[:, :2]
    rings = np.array([len(bottom_2d)], dtype=np.int32)
    bottom_faces_2d = earcut.triangulate_float64(bottom_2d, rings)
    bottom_faces_2d = bottom_faces_2d.reshape(-1, 3)
    bottom_faces = bottom_faces_2d + start_idx
    new_faces.extend(bottom_faces)

    # 7. Сборка
    solid_mesh = trimesh.Trimesh(
        vertices=new_vertices,
        faces=np.array(new_faces, dtype=np.int64)
    )
    solid_mesh.fix_normals()
    
    # Проверка: нижняя точка не должна измениться
    new_min_z = solid_mesh.vertices[:, 2].min()
    print(f"\nПроверка координат:")
    print(f"  Оригинальный min Z: {min_z:.4f}")
    print(f"  Новый min Z:        {new_min_z:.4f}")
    print(f"  Совпадает: {np.isclose(min_z, new_min_z)}")
    
    print(f"\nРезультат:")
    print(f"  Вершин: {len(solid_mesh.vertices)}")
    print(f"  Граней: {len(solid_mesh.faces)}")
    print(f"  Герметична: {solid_mesh.is_watertight}")
    print(f"  Bounding box: "
          f"X[{solid_mesh.vertices[:, 0].min():.2f}:{solid_mesh.vertices[:, 0].max():.2f}] "
          f"Y[{solid_mesh.vertices[:, 1].min():.2f}:{solid_mesh.vertices[:, 1].max():.2f}] "
          f"Z[{solid_mesh.vertices[:, 2].min():.2f}:{solid_mesh.vertices[:, 2].max():.2f}]")

    solid_mesh.export(output_path)
    print(f"\n✓ Сохранено в: {output_path}")

input_file = r"D:\Dentra\BK\Project_1\LowerJaw.stl"
output_file = r"D:\Dentra\BK\Project_1\LowerJaw_solid.stl"

if __name__ == "__main__":
    solidify_jaw(input_file, output_file)