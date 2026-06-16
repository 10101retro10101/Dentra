import sys
import argparse
import io
import os
import trimesh
import numpy as np
import pymeshlab
import networkx as nx
import mapbox_earcut as earcut
from .fixModel import solidify_jaw

# ============================================================
# НАСТРОЙКИ БАЗЫ ДАННЫХ (измени на свои!)
# ============================================================
DB_CONFIG = {
    'dbname': 'mydatabase',      # название БД
    'user': 'myuser',            # пользователь
    'password': 'mypassword',    # пароль
    'host': 'localhost',         # хост
    'port': 5432                 # порт PostgreSQL
}

# SQL-запросы для работы с БД
SQL_GET_MODEL = "SELECT model_data, file_type FROM models WHERE id = %s"
SQL_SAVE_MODEL = "INSERT INTO models (model_data, file_type, description) VALUES (%s, %s, %s) RETURNING id"

OUTPUT_DIR = "output_steps"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_blob_from_database(model_id):
    """Загрузка модели из БД по ID. Возвращает (bytes, file_type)."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError("Установите: pip install psycopg2-binary")
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(SQL_GET_MODEL, (model_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row is None:
        raise ValueError(f"Модель ID={model_id} не найдена")
    
    return row[0], row[1] if len(row) > 1 else 'stl'


def save_blob_to_database(mesh, file_type='stl', description=''):
    """Сохранение модели в БД. Возвращает ID записи."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError("Установите: pip install psycopg2-binary")
    
    buffer = io.BytesIO()
    mesh.export(buffer, file_type=file_type)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(SQL_SAVE_MODEL, (buffer.getvalue(), file_type, description))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    
    return new_id


def load_mesh_from_source(source, file_type=None):
    """
    Загрузка меша из файла (str) или bytes (BLOB).
    file_type нужен только для bytes (например 'stl', 'obj').
    """
    if isinstance(source, bytes):
        file_obj = io.BytesIO(source)
        return trimesh.load(file_obj, file_type=file_type, force='mesh') if file_type else trimesh.load(file_obj, force='mesh')
    elif isinstance(source, str):
        return trimesh.load(source, force='mesh')
    else:
        raise ValueError(f"Неподдерживаемый тип: {type(source)}")


def save_mesh(mesh, filename, step_name):
    """Сохранение меша в файл в папке OUTPUT_DIR."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        mesh.export(filepath)
        print(f"[OK] {step_name} -> {filepath}")
        return mesh
    except Exception as e:
        print(f"[ERR] Ошибка сохранения: {e}")
        return None


def save_mesh_to_blob(mesh, description='', file_type='stl'):
    """Сохранение меша в БД. Возвращает ID или None при ошибке."""
    try:
        new_id = save_blob_to_database(mesh, file_type, description)
        print(f"[OK] Сохранено в БД ID={new_id} ({description})")
        return new_id
    except Exception as e:
        print(f"[ERR] Ошибка сохранения в БД: {e}")
        return None


def repair_mesh_with_pymeshlab(mesh, name):
    """
    Ремонт меша через pymeshlab:
    - Удаление дубликатов вершин и граней
    - Ремонт не-manifold геометрии
    - Заполнение мелких дыр
    - Пересчёт нормалей
    """
    print(f"Ремонт: {name} ({mesh.vertices.shape[0]} вершин)")
    
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces))
    
    # Слияние близких вершин (порог 0.0001 мм)
    try:
        ms.apply_filter('meshing_merge_close_vertices', threshold=pymeshlab.AbsoluteValue(0.0001))
    except Exception as e:
        print(f"  merge_close_vertices: {e}")
    
    # Удаление дубликатов
    try:
        ms.apply_filter('meshing_remove_duplicate_faces')
        ms.apply_filter('meshing_remove_null_faces')
        ms.apply_filter('meshing_remove_duplicate_vertices')
    except Exception as e:
        print(f"  Удаление граней: {e}")
    
    # Ремонт не-manifold рёбер и вершин
    try:
        ms.apply_filter('meshing_repair_non_manifold_edges')
        ms.apply_filter('meshing_repair_non_manifold_vertices')
    except Exception as e:
        print(f"  Repair non-manifold: {e}")
    
    # Заполнение дыр (макс. размер 100)
    try:
        ms.apply_filter('meshing_close_holes', maxholesize=100)
    except Exception as e:
        print(f"  close_holes: {e}")
    
    # Пересчёт нормалей
    try:
        ms.apply_filter('recompute_normals')
    except Exception as e:
        print(f"  Нормали: {e}")
    
    repaired = ms.current_mesh()
    result = trimesh.Trimesh(vertices=repaired.vertex_matrix(), faces=repaired.face_matrix())
    result.fix_normals()
    ms.clear()
    
    print(f"  Результат: {result.vertices.shape[0]} вершин, watertight={result.is_watertight}")
    return result


def solidify_open_mesh(mesh, name, base_z=None):
    """
    Закрытие большого открытого края (boundary) через earcut.
    Автоопределяет тип челюсти (upper/lower) по положению boundary.
    base_z - принудительный уровень закрытия (если None, определяется автоматически).
    """
    print(f"Закрытие открытого края: {name}")
    
    if mesh.is_watertight:
        print(f"  Уже watertight")
        return mesh
    
    # Поиск boundary edges (рёбра, которые встречаются нечётное число раз)
    edges = mesh.edges_sorted
    edge_counts = {}
    for edge in edges:
        key = tuple(edge)
        edge_counts[key] = edge_counts.get(key, 0) + 1
    
    boundary_edges = [np.array(k) for k, count in edge_counts.items() if count % 2 != 0]
    
    if not boundary_edges:
        print(f"  Boundary edges не найдены")
        return mesh
    
    print(f"  Найдено {len(boundary_edges)} boundary edges")
    
    # Сборка boundary в контур
    g = nx.Graph()
    g.add_edges_from(boundary_edges)
    cycles = nx.cycle_basis(g)
    
    if not cycles:
        print(f"  Не удалось собрать контур")
        return mesh
    
    boundary_indices = max(cycles, key=len)
    num_b_verts = len(boundary_indices)
    
    # Определение типа челюсти по среднему Z boundary
    boundary_z = mesh.vertices[boundary_indices, 2]
    avg_boundary_z = np.mean(boundary_z)
    min_z = mesh.vertices[:, 2].min()
    max_z = mesh.vertices[:, 2].max()
    mid_z = (min_z + max_z) / 2
    
    jaw_type = 'upper' if avg_boundary_z > mid_z else 'lower'
    cap_z = max_z if jaw_type == 'upper' else min_z
    if base_z is not None:
        cap_z = base_z
    
    print(f"  Тип: {jaw_type.upper()}, закрываем на Z={cap_z:.2f}")
    
    # Создание вершин крышки
    new_vertices = mesh.vertices.copy()
    new_faces = list(mesh.faces.copy())
    start_idx = len(new_vertices)
    
    boundary_vertices = mesh.vertices[boundary_indices].copy()
    cap_vertices = boundary_vertices.copy()
    cap_vertices[:, 2] = cap_z
    new_vertices = np.vstack([new_vertices, cap_vertices])
    
    # Создание стенок
    for i in range(num_b_verts):
        next_i = (i + 1) % num_b_verts
        v_top_curr = boundary_indices[i]
        v_top_next = boundary_indices[next_i]
        v_bot_curr = start_idx + i
        v_bot_next = start_idx + next_i
        
        if v_top_curr != v_bot_curr or v_top_next != v_bot_next:
            if jaw_type == 'lower':
                new_faces.append([v_top_curr, v_bot_curr, v_bot_next])
                new_faces.append([v_top_curr, v_bot_next, v_top_next])
            else:
                new_faces.append([v_top_curr, v_bot_next, v_bot_curr])
                new_faces.append([v_top_curr, v_top_next, v_bot_next])
    
    # Триангуляция крышки через earcut
    cap_2d = cap_vertices[:, :2]
    rings = np.array([len(cap_2d)], dtype=np.int32)
    cap_faces_2d = earcut.triangulate_float64(cap_2d, rings).reshape(-1, 3)
    
    # Для верхней челюсти инвертируем грани (нормаль вверх)
    if jaw_type == 'upper':
        cap_faces_2d = cap_faces_2d[:, ::-1]
    
    new_faces.extend(cap_faces_2d + start_idx)
    
    solid_mesh = trimesh.Trimesh(vertices=new_vertices, faces=np.array(new_faces, dtype=np.int64))
    solid_mesh.fix_normals()
    
    print(f"  Результат: watertight={solid_mesh.is_watertight}")
    return solid_mesh


def add_skirt_by_copying(cap_with_slots, original_base_cap, skirt_zone=3.0, position='top'):
    """
    Создание юбки путём копирования части оригинальной капы (без прорезей).
    
    Параметры:
    - skirt_zone: высота зоны юбки в мм (сколько взять от капы)
    - position: 'top' (сверху, у корней) или 'bottom' (снизу, у десны)
    """
    print(f"Создание юбки: зона={skirt_zone}мм, позиция={position}")
    
    bounds = cap_with_slots.bounds
    z_min, z_max = bounds[0][2], bounds[1][2]
    
    # Определение зоны вырезания
    if position == 'top':
        cut_z_min = z_max - skirt_zone
        cut_z_max = z_max + 5
    else:
        cut_z_min = z_min - 5
        cut_z_max = z_min + skirt_zone
    
    # Создание cutter box
    cutter_size = [
        bounds[1][0] - bounds[0][0] + 30,
        bounds[1][1] - bounds[0][1] + 30,
        cut_z_max - cut_z_min + 10
    ]
    cutter = trimesh.creation.box(extents=cutter_size)
    cutter.apply_transform(trimesh.transformations.translation_matrix([
        (bounds[0][0] + bounds[1][0]) / 2,
        (bounds[0][1] + bounds[1][1]) / 2,
        (cut_z_min + cut_z_max) / 2
    ]))
    
    # Вырезание части из оригинальной капы
    try:
        skirt_piece = trimesh.boolean.intersection([original_base_cap, cutter], engine='manifold')
    except:
        try:
            skirt_piece = trimesh.boolean.intersection([original_base_cap, cutter], engine='blender')
        except Exception as e:
            print(f"  Не удалось вырезать юбку: {e}")
            return cap_with_slots
    
    # Объединение с капой с прорезями
    try:
        result = trimesh.boolean.union([cap_with_slots, skirt_piece], engine='manifold')
        return result
    except:
        try:
            return trimesh.boolean.union([cap_with_slots, skirt_piece], engine='blender')
        except:
            return trimesh.util.concatenate([cap_with_slots, skirt_piece])

def solidify_mesh_with_jaw(mesh, is_upper=True, cap_z=None):
    """
    Закрывает открытую модель через solidify_jaw_top, работая с mesh.
    Возвращает новый замкнутый mesh.
    """
    temp_in = os.path.join(OUTPUT_DIR, "temp_solidify_in.stl")
    temp_out = os.path.join(OUTPUT_DIR, "temp_solidify_out.stl")
    
    mesh.export(temp_in)
    solidify_jaw(temp_in, temp_out, base_z=cap_z, is_upper=is_upper)
    result = trimesh.load(temp_out, force='mesh')
    
    # Удаляем временные файлы
    # os.remove(temp_in)
    # os.remove(temp_out)
    return result

def subtract_from_blobs(
        model_1_source, 
        model_2_source, 
        model_1_file_type, 
        model_2_file_type,
        skirt_position,
        skirt_zone,
        slot_width
        ):
    """
    ГЛАВНАЯ ФУНКЦИЯ: Генерация двух шаблонов с шахматными прорезями.
    
    Параметры:
    - model_1_source: целевая модель (путь к файлу str или bytes BLOB)
    - model_2_source: исходная модель (путь к файлу str или bytes BLOB)
    - output_path_1, output_path_2: пути для сохранения
    - model_1_file_type, model_2_file_type: формат файлов (нужен для bytes)
    
    Возвращает: (id_1, id_2)
    """
    
    print("Запуск генерации шаблона...")

    print("Восстановление модели")

    
    # ============================================================
    # НАСТРАИВАЕМЫЕ ПАРАМЕТРЫ
    # ============================================================
    cap_thickness = 2.0        # Толщина стенки капы (мм)
    clearance = 0.05           # Зазор между зубом и капой (мм)
    
    slot_step = slot_width     # Шаг прорезей (мм) - по умолчанию = ширина (сплошные)
    y_bridge = 5.0             # Мостики по бокам (мм) - зона без прорезей
    # ============================================================
    
    # ЭТАП 1: Загрузка и ремонт моделей
    try:
        raw_model_1 = load_mesh_from_source(model_1_source, model_1_file_type)
        print(f"Model_1: {raw_model_1.vertices.shape[0]} вершин")

        # Закрытие через обёртку (верхняя челюсть)
        solid_model_1 = solidify_mesh_with_jaw(raw_model_1, is_upper=True)
        solid_model_1 = repair_mesh_with_pymeshlab(solid_model_1, "Модель 1")
        save_mesh(solid_model_1, "01a_repaired_model_1.stl", "После pymeshlab")
        
        # Model_2 (исходная)
        raw_model_2 = load_mesh_from_source(model_2_source, model_2_file_type)
        print(f"Model_2: {raw_model_2.vertices.shape[0]} вершин")
        
        repaired_model_2 = repair_mesh_with_pymeshlab(raw_model_2, "Модель 2")
        save_mesh(repaired_model_2, "02a_repaired_model_2.stl", "Отремонтированная Модель 2")
        
        solid_model_2 = solidify_open_mesh(repaired_model_2, "Модель 2") if not repaired_model_2.is_watertight else repaired_model_2
        save_mesh(solid_model_2, "02_solid_model_2.stl", "Solid Модель 2")
        
    except Exception as e:
        print(f"Ошибка на этапе 1: {e}")
        return None, None
    
    # ЭТАП 2: Вычисление объёма редукции (Model_2 - Model_1)
    print("\n--- ЭТАП 2: Объем редукции ---")
    try:
        volume_to_remove = trimesh.boolean.difference([solid_model_2, solid_model_1], engine='manifold')
        volume_to_remove.visual.vertex_colors = [255, 165, 0, 255]
        save_mesh(volume_to_remove, "03_volume_to_remove.stl", "Объем редукции")
        print(f"Объем: {volume_to_remove.volume:.2f} мм³")
    except Exception as e:
        print(f"Ошибка булевой операции: {e}")
        return None, None
    
    # ЭТАП 3: Создание базовой капы (оболочка вокруг Model_2)
    print("\n--- ЭТАП 3: Генерация капы ---")
    
    # Внутренняя поверхность (с зазором)
    inner_surface = repaired_model_2.copy()
    inner_surface.vertices += inner_surface.vertex_normals * clearance
    
    # Внешняя поверхность (с зазором + толщина)
    outer_surface = repaired_model_2.copy()
    outer_surface.vertices += outer_surface.vertex_normals * (clearance + cap_thickness)
    
    # Булева операция: outer - inner = оболочка
    try:
        base_cap = trimesh.boolean.difference([outer_surface, inner_surface], engine='manifold')
    except:
        try:
            base_cap = trimesh.boolean.difference([outer_surface, inner_surface], engine='blender')
        except:
            base_cap = outer_surface.copy()
    
    base_cap.visual.vertex_colors = [0, 0, 255, 255]
    save_mesh(base_cap, "04_base_cap_closed.stl", "Базовая капа")
    
    # ЭТАП 4: Создание шахматных прорезей
    print("\n--- ЭТАП 4: Шахматные прорези ---")
    
    bounds = volume_to_remove.bounds
    x_min, x_max = bounds[0][0], bounds[1][0]
    y_min, y_max = bounds[0][1], bounds[1][1]
    z_min, z_max = bounds[0][2], bounds[1][2]
    slot_height = (z_max - z_min) + 10
    
    slot_boxes_1, slot_boxes_2 = [], []
    
    # Генерация box'ов вдоль оси X
    for idx, x_pos in enumerate(np.arange(x_min, x_max, slot_step)):
        box = trimesh.creation.box(extents=[slot_width, y_max-y_min+y_bridge, slot_height])
        box.apply_transform(trimesh.transformations.translation_matrix([
            x_pos + slot_width/2, (y_min+y_max)/2, (z_min+z_max)/2
        ]))
        
        # Проверка пересечения с volume_to_remove
        try:
            inter = trimesh.boolean.intersection([box, volume_to_remove], engine='manifold')
            if inter.volume > 0.1:
                if idx % 2 == 0:
                    slot_boxes_1.append(box)
                else:
                    slot_boxes_2.append(box)
        except:
            pass
    
    # Fallback: если ни один box не пересёкся, создаём без проверки
    if not slot_boxes_1 and not slot_boxes_2:
        print("Fallback: без проверки пересечения")
        for idx, x_pos in enumerate(np.arange(x_min, x_max, slot_step)):
            box = trimesh.creation.box(extents=[slot_width, y_max-y_min+y_bridge, slot_height])
            box.apply_transform(trimesh.transformations.translation_matrix([
                x_pos + slot_width/2, (y_min+y_max)/2, (z_min+z_max)/2
            ]))
            if idx % 2 == 0:
                slot_boxes_1.append(box)
            else:
                slot_boxes_2.append(box)
    
    # Объединение box'ов в маски
    mask_1 = trimesh.util.concatenate(slot_boxes_1) if slot_boxes_1 else trimesh.creation.box(extents=[1,1,1])
    mask_2 = trimesh.util.concatenate(slot_boxes_2) if slot_boxes_2 else trimesh.creation.box(extents=[1,1,1])
    
    print(f"Маска 1: {len(slot_boxes_1)} box'ов, Маска 2: {len(slot_boxes_2)} box'ов")
    
    save_mesh(mask_1, "04a_mask_1.stl", "Маска 1")
    save_mesh(mask_2, "04b_mask_2.stl", "Маска 2")
    
    # ЭТАП 5: Depth Stop (пространство для сверления)
    print("\n--- ЭТАП 5: Depth Stop ---")
    
    # Пространство для сверления = base_cap - solid_model_1
    try:
        space_to_drill = trimesh.boolean.difference([base_cap, solid_model_1], engine='manifold')
        save_mesh(space_to_drill, "05c_space_to_drill.stl", "Пространство сверления")
    except:
        space_to_drill = base_cap.copy()
    
    # Пересечение масок с space_to_drill = реальные прорези
    try:
        drill_1 = trimesh.boolean.intersection([mask_1, space_to_drill], engine='manifold')
        drill_2 = trimesh.boolean.intersection([mask_2, space_to_drill], engine='manifold')
        print(f"drill_1: {drill_1.volume:.2f} мм³, drill_2: {drill_2.volume:.2f} мм³")
        save_mesh(drill_1, "05d_drill_1.stl", "Прорези 1")
        save_mesh(drill_2, "05e_drill_2.stl", "Прорези 2")
    except Exception as e:
        print(f"Ошибка: {e}")
        return None, None
    
    # ЭТАП 6: Создание кап с прорезями
    print("\n--- ЭТАП 6: Формирование кап ---")
    
    try:
        cap_with_slots_1 = trimesh.boolean.difference([space_to_drill, drill_1], engine='manifold')
        cap_with_slots_2 = trimesh.boolean.difference([space_to_drill, drill_2], engine='manifold')
        save_mesh(cap_with_slots_1, "cap_with_slots_1.stl", "Прорези 1")
        save_mesh(cap_with_slots_2, "cap_with_slots_2.stl", "Прорези 2")
        print(f"cap_1: {cap_with_slots_1.volume:.2f} мм³, cap_2: {cap_with_slots_2.volume:.2f} мм³")
    except Exception as e:
        print(f"Ошибка: {e}")
        return None, None
    
    # ЭТАП 7: Добавление юбки
    print("\n--- ЭТАП 7: Юбка ---")
    
    final_cap_1 = add_skirt_by_copying(cap_with_slots_1, base_cap, skirt_zone, position=skirt_position)
    final_cap_2 = add_skirt_by_copying(cap_with_slots_2, base_cap, skirt_zone, position=skirt_position)
    
    final_cap_1.visual.vertex_colors = [0, 255, 255, 255]
    final_cap_2.visual.vertex_colors = [255, 0, 255, 255]
    save_mesh(cap_with_slots_1, "cap_with_slots_1.stl", "Прорези 1")
    save_mesh(cap_with_slots_2, "cap_with_slots_2.stl", "Прорези 2")
    
    # ЭТАП 8: Вычитание Model_1 (чтобы капа могла надеваться)
    print("\n--- ЭТАП 8: Вычитание Model_1 ---")
    
    try:
        final_cap_1 = trimesh.boolean.difference([final_cap_1, solid_model_1], engine='manifold')
        print(f"Капа 1: {final_cap_1.volume:.2f} мм³")
    except Exception as e:
        print(f"Ошибка вычитания из капы 1: {e}")
    
    try:
        final_cap_2 = trimesh.boolean.difference([final_cap_2, solid_model_1], engine='manifold')
        print(f"Капа 2: {final_cap_2.volume:.2f} мм³")
    except Exception as e:
        print(f"Ошибка вычитания из капы 2: {e}")
    
    # ============================================================
    # СОХРАНЕНИЕ РЕЗУЛЬТАТА
    # ============================================================
    print("\n--- Сохранение ---")

    bytes_1 = None
    bytes_2 = None
    
    buffer_1 = io.BytesIO()
    final_cap_1.export(buffer_1, file_type='stl')
    bytes_1 = buffer_1.getvalue()
    print(f"Модель 1: {len(bytes_1)} байт")
    
    # Конвертируем вторую модель в bytes
    buffer_2 = io.BytesIO()
    final_cap_2.export(buffer_2, file_type='stl')
    bytes_2 = buffer_2.getvalue()
    print(f"Модель 2: {len(bytes_2)} байт")

    return bytes_1, bytes_2


def parse_int_or_path(s):
    """Парсинг аргумента: int (ID из БД) или str (путь к файлу)."""
    try:
        return int(s)
    except ValueError:
        return s
