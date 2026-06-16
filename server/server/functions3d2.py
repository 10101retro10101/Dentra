# import sys
# import argparse
# import io
# import os
# import trimesh
# import numpy as np
# import pymeshlab
# import networkx as nx
# import mapbox_earcut as earcut

# # ============================================================
# # НАСТРОЙКИ БАЗЫ ДАННЫХ
# # ============================================================
# DB_CONFIG = {
#     'dbname': 'mydatabase',
#     'user': 'myuser',
#     'password': 'mypassword',
#     'host': 'localhost',
#     'port': 5432
# }

# SQL_GET_MODEL = "SELECT model_data, file_type FROM models WHERE id = %s"
# SQL_SAVE_MODEL = "INSERT INTO models (model_data, file_type, description) VALUES (%s, %s, %s) RETURNING id"

# OUTPUT_DIR = "output_steps"
# os.makedirs(OUTPUT_DIR, exist_ok=True)


# def get_blob_from_database(model_id):
#     """Загрузка модели из БД по ID."""
#     try:
#         import psycopg2
#     except ImportError:
#         raise ImportError("Установите: pip install psycopg2-binary")
    
#     conn = psycopg2.connect(**DB_CONFIG)
#     cur = conn.cursor()
#     cur.execute(SQL_GET_MODEL, (model_id,))
#     row = cur.fetchone()
#     cur.close()
#     conn.close()
    
#     if row is None:
#         raise ValueError(f"Модель ID={model_id} не найдена")
    
#     return row[0], row[1] if len(row) > 1 else 'stl'


# def save_blob_to_database(mesh, file_type='stl', description=''):
#     """Сохранение модели в БД."""
#     try:
#         import psycopg2
#     except ImportError:
#         raise ImportError("Установите: pip install psycopg2-binary")
    
#     buffer = io.BytesIO()
#     mesh.export(buffer, file_type=file_type)
    
#     conn = psycopg2.connect(**DB_CONFIG)
#     cur = conn.cursor()
#     cur.execute(SQL_SAVE_MODEL, (buffer.getvalue(), file_type, description))
#     new_id = cur.fetchone()[0]
#     conn.commit()
#     cur.close()
#     conn.close()
    
#     return new_id


# def load_mesh_from_source(source, file_type=None):
#     """Загрузка меша из файла или bytes."""
#     if isinstance(source, bytes):
#         file_obj = io.BytesIO(source)
#         return trimesh.load(file_obj, file_type=file_type, force='mesh') if file_type else trimesh.load(file_obj, force='mesh')
#     elif isinstance(source, str):
#         return trimesh.load(source, force='mesh')
#     else:
#         raise ValueError(f"Неподдерживаемый тип: {type(source)}")


# def save_mesh(mesh, filename, step_name):
#     """Сохранение меша в файл."""
#     if mesh is None:
#         print(f"[ERR] Mesh is None для {step_name}")
#         return None
    
#     filepath = os.path.join(OUTPUT_DIR, filename)
#     try:
#         mesh.export(filepath)
#         print(f"[OK] {step_name} -> {filepath}")
#         return mesh
#     except Exception as e:
#         print(f"[ERR] Ошибка сохранения: {e}")
#         return None


# def save_mesh_to_blob(mesh, description='', file_type='stl'):
#     """Сохранение меша в БД."""
#     try:
#         new_id = save_blob_to_database(mesh, file_type, description)
#         print(f"[OK] Сохранено в БД ID={new_id} ({description})")
#         return new_id
#     except Exception as e:
#         print(f"[ERR] Ошибка сохранения в БД: {e}")
#         return None


# def repair_mesh_gentle(mesh, name):
#     """
#     Щадящий ремонт меша - только удаление артефактов, без изменения геометрии.
#     """
#     print(f"Щадящий ремонт: {name} ({mesh.vertices.shape[0]} вершин)")
    
#     ms = pymeshlab.MeshSet()
#     ms.add_mesh(pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces))
    
#     # Только удаление дубликатов и невалидных элементов
#     try:
#         ms.apply_filter('meshing_remove_duplicate_faces')
#         ms.apply_filter('meshing_remove_null_faces')
#         ms.apply_filter('meshing_remove_duplicate_vertices')
#     except Exception as e:
#         print(f"  Удаление дубликатов: {e}")
    
#     # Минимальный ремонт не-manifold (только самые простые случаи)
#     try:
#         ms.apply_filter('meshing_repair_non_manifold_edges')
#     except Exception as e:
#         print(f"  Repair edges: {e}")
    
#     # Не закрываем дыры, чтобы сохранить детали!
    
#     # Пересчёт нормалей
#     try:
#         ms.apply_filter('compute_normal_for_mesh')
#     except:
#         try:
#             ms.apply_filter('recompute_vertex_normals')
#         except:
#             pass
    
#     repaired = ms.current_mesh()
#     result = trimesh.Trimesh(
#         vertices=repaired.vertex_matrix(), 
#         faces=repaired.face_matrix()
#     )
#     result.fix_normals()
#     ms.clear()
    
#     print(f"  Результат: {result.vertices.shape[0]} вершин, watertight={result.is_watertight}")
#     return result


# def close_boundary_holes(mesh, name):
#     """
#     Закрытие только открытых краев (boundary) для создания объема,
#     но с сохранением всех внутренних деталей.
#     """
#     print(f"Закрытие boundary holes: {name}")
    
#     if mesh.is_watertight:
#         print(f"  Уже watertight")
#         return mesh
    
#     # Находим все boundary edges
#     edges = mesh.edges_sorted
#     edge_counts = {}
#     for edge in edges:
#         key = tuple(edge)
#         edge_counts[key] = edge_counts.get(key, 0) + 1
    
#     boundary_edges = [np.array(k) for k, count in edge_counts.items() if count % 2 != 0]
    
#     if not boundary_edges:
#         print(f"  Нет boundary edges")
#         return mesh
    
#     print(f"  Найдено {len(boundary_edges)} boundary edges")
    
#     # Группируем boundary edges в циклы
#     g = nx.Graph()
#     g.add_edges_from(boundary_edges)
    
#     # Находим все компоненты связности
#     components = list(nx.connected_components(g))
#     print(f"  Найдено {len(components)} boundary компонент")
    
#     # Сортируем компоненты по размеру (самый большой - главное отверстие)
#     components.sort(key=len, reverse=True)
    
#     # Закрываем только самые большие отверстия (обычно 1-2)
#     # Оставляем маленькие отверстия открытыми (они не влияют на watertight для булевых операций)
#     max_holes_to_close = min(3, len(components))  # Закрываем не более 3 отверстий
    
#     new_vertices = mesh.vertices.copy()
#     new_faces = list(mesh.faces.copy())
#     start_idx = len(new_vertices)
    
#     closed_holes = 0
    
#     for idx, comp in enumerate(components[:max_holes_to_close]):
#         if len(comp) < 10:  # Слишком маленькие отверстия игнорируем
#             continue
            
#         boundary_indices = list(comp)
        
#         # Проверяем, что это действительно цикл
#         if len(boundary_indices) < 3:
#             continue
            
#         # Создаем вершины для закрытия
#         boundary_vertices = mesh.vertices[boundary_indices].copy()
        
#         # Средняя Z для этого отверстия
#         avg_z = np.mean(boundary_vertices[:, 2])
        
#         # Закрываем на уровне средней Z
#         cap_vertices = boundary_vertices.copy()
#         cap_vertices[:, 2] = avg_z
        
#         new_vertices = np.vstack([new_vertices, cap_vertices])
        
#         # Триангуляция отверстия
#         cap_2d = cap_vertices[:, :2]
#         rings = np.array([len(cap_2d)], dtype=np.int32)
        
#         try:
#             cap_faces_2d = earcut.triangulate_float64(cap_2d, rings).reshape(-1, 3)
            
#             # Добавляем грани
#             for face in cap_faces_2d:
#                 new_faces.append(face + start_idx)
            
#             # Создаем стенки
#             for i in range(len(boundary_indices)):
#                 next_i = (i + 1) % len(boundary_indices)
#                 v_top_curr = boundary_indices[i]
#                 v_top_next = boundary_indices[next_i]
#                 v_bot_curr = start_idx + i
#                 v_bot_next = start_idx + next_i
                
#                 if v_top_curr != v_bot_curr or v_top_next != v_bot_next:
#                     # Нормаль направлена наружу
#                     new_faces.append([v_top_curr, v_bot_next, v_bot_curr])
#                     new_faces.append([v_top_curr, v_top_next, v_bot_next])
            
#             start_idx += len(boundary_vertices)
#             closed_holes += 1
            
#         except Exception as e:
#             print(f"  Ошибка закрытия отверстия {idx}: {e}")
#             continue
    
#     print(f"  Закрыто отверстий: {closed_holes}")
    
#     result = trimesh.Trimesh(vertices=new_vertices, faces=np.array(new_faces, dtype=np.int64))
#     result.fix_normals()
    
#     print(f"  Результат: watertight={result.is_watertight}")
#     return result


# def make_watertight_for_boolean(mesh, name):
#     """
#     Создание водонепроницаемой версии для булевых операций.
#     """
#     print(f"Подготовка для булевых операций: {name}")
    
#     if mesh.is_watertight:
#         return mesh
    
#     # Пробуем разные методы, начиная с самого щадящего
#     methods = [
#         ("close_boundary", lambda: close_boundary_holes(mesh, name)),
#         ("fill_small_holes", lambda: fill_small_holes(mesh)),
#         ("convex_hull", lambda: mesh.convex_hull)
#     ]
    
#     for method_name, method_func in methods:
#         try:
#             print(f"  Пробуем метод: {method_name}")
#             result = method_func()
#             if result and result.is_watertight:
#                 print(f"  Успех! Метод {method_name} сработал")
#                 return result
#         except Exception as e:
#             print(f"  Метод {method_name} не сработал: {e}")
    
#     print(f"  НЕ УДАЛОСЬ создать watertight mesh для {name}")
#     return mesh


# def fill_small_holes(mesh, max_hole_area=100):
#     """Закрытие только маленьких дыр."""
#     try:
#         # Используем fill_holes с ограничением по размеру
#         mesh_copy = mesh.copy()
#         mesh_copy.fill_holes(max_hole_area=max_hole_area)
#         return mesh_copy
#     except:
#         return mesh


# def add_skirt_by_copying(cap_with_slots, original_base_cap, skirt_zone=3.0, position='top'):
#     """Создание юбки."""
#     print(f"Создание юбки: зона={skirt_zone}мм, позиция={position}")
    
#     bounds = cap_with_slots.bounds
#     z_min, z_max = bounds[0][2], bounds[1][2]
    
#     if position == 'top':
#         cut_z_min = z_max - skirt_zone
#         cut_z_max = z_max + 5
#     else:
#         cut_z_min = z_min - 5
#         cut_z_max = z_min + skirt_zone
    
#     cutter_size = [
#         bounds[1][0] - bounds[0][0] + 30,
#         bounds[1][1] - bounds[0][1] + 30,
#         cut_z_max - cut_z_min + 10
#     ]
#     cutter = trimesh.creation.box(extents=cutter_size)
#     cutter.apply_transform(trimesh.transformations.translation_matrix([
#         (bounds[0][0] + bounds[1][0]) / 2,
#         (bounds[0][1] + bounds[1][1]) / 2,
#         (cut_z_min + cut_z_max) / 2
#     ]))
    
#     try:
#         skirt_piece = trimesh.boolean.intersection([original_base_cap, cutter], engine='manifold')
#     except:
#         try:
#             skirt_piece = trimesh.boolean.intersection([original_base_cap, cutter], engine='blender')
#         except Exception as e:
#             print(f"  Не удалось вырезать юбку: {e}")
#             return cap_with_slots
    
#     try:
#         result = trimesh.boolean.union([cap_with_slots, skirt_piece], engine='manifold')
#         return result
#     except:
#         try:
#             return trimesh.boolean.union([cap_with_slots, skirt_piece], engine='blender')
#         except:
#             return trimesh.util.concatenate([cap_with_slots, skirt_piece])


# def clean_slots_by_redo(cap_with_slots, slot_boxes_list, solid_model_1):
#     """
#     Пересоздание прорезей заново по исходным координатам для очистки геометрии.
#     """
#     print("  Пересоздание прорезей для очистки геометрии...")
    
#     if not slot_boxes_list:
#         print("    Нет прорезей для очистки")
#         return cap_with_slots
    
#     # Сначала вычитаем все объемы, которые не должны быть в капе
#     try:
#         # Получаем чистую капу без прорезей
#         clean_cap = trimesh.boolean.difference([cap_with_slots, solid_model_1], engine='manifold')
#         if clean_cap is None or clean_cap.volume == 0:
#             clean_cap = cap_with_slots.copy()
#     except:
#         clean_cap = cap_with_slots.copy()
    
#     # Создаем новые прорези по тем же координатам
#     all_slots = trimesh.util.concatenate(slot_boxes_list)
    
#     if all_slots is None:
#         return cap_with_slots
    
#     # Вычитаем прорези из чистой капы
#     try:
#         result = trimesh.boolean.difference([clean_cap, all_slots], engine='manifold')
#         if result and result.volume > 0:
#             print(f"    Пересоздание прорезей успешно: {result.volume:.2f} мм³")
#             return result
#     except Exception as e:
#         print(f"    Ошибка пересоздания: {e}")
    
#     # Fallback: пробуем с другим движком
#     try:
#         result = trimesh.boolean.difference([clean_cap, all_slots], engine='blender')
#         if result and result.volume > 0:
#             print(f"    Пересоздание прорезей успешно (blender): {result.volume:.2f} мм³")
#             return result
#     except Exception as e:
#         print(f"    Ошибка пересоздания (blender): {e}")
    
#     # Если ничего не получилось, используем исходный результат
#     print("    Не удалось пересоздать прорези, используем исходный результат")
#     return cap_with_slots

# def subtract_from_blobs(model_1_source, model_2_source, output_path_1=None, output_path_2=None,
#                    model_1_file_type=None, model_2_file_type=None,
#                    save_to_db=False, description_prefix='Guide'):
#     """Главная функция генерации шаблонов. Возвращает кортеж (bytes_1, bytes_2) или (None, None) при ошибке."""
    
#     print("Запуск генерации шаблона...")
    
#     # Параметры
#     cap_thickness = 2.0
#     clearance = 0.05
#     slot_width = 1.0
#     slot_step = slot_width
#     y_bridge = 5.0
#     skirt_zone = 2.0
#     skirt_position = 'bottom'
    
#     # ЭТАП 1: Загрузка и щадящий ремонт
#     print("\n--- ЭТАП 1: Загрузка моделей ---")
    
#     try:
#         # Model_1 (целевая)
#         raw_model_1 = load_mesh_from_source(model_1_source, model_1_file_type)
#         print(f"Model_1: {raw_model_1.vertices.shape[0]} вершин, watertight={raw_model_1.is_watertight}")
        
#         repaired_model_1 = repair_mesh_gentle(raw_model_1, "Модель 1")
#         save_mesh(repaired_model_1, "01a_repaired_model_1.stl", "После ремонта Model_1")
        
#         solid_model_1 = make_watertight_for_boolean(repaired_model_1, "Model_1")
#         save_mesh(solid_model_1, "01_solid_model_1.stl", "Solid Модель 1")
        
#         detail_model_1 = repaired_model_1.copy()
#         save_mesh(detail_model_1, "01_detail_model_1.stl", "Детальная Model_1")
        
#         # Model_2 (исходная)
#         raw_model_2 = load_mesh_from_source(model_2_source, model_2_file_type)
#         print(f"Model_2: {raw_model_2.vertices.shape[0]} вершин, watertight={raw_model_2.is_watertight}")
        
#         repaired_model_2 = repair_mesh_gentle(raw_model_2, "Модель 2")
#         save_mesh(repaired_model_2, "02a_repaired_model_2.stl", "После ремонта Model_2")
        
#         solid_model_2 = make_watertight_for_boolean(repaired_model_2, "Model_2")
#         save_mesh(solid_model_2, "02_solid_model_2.stl", "Solid Модель 2")
        
#         detail_model_2 = repaired_model_2.copy()
#         save_mesh(detail_model_2, "02_detail_model_2.stl", "Детальная Model_2")
        
#     except Exception as e:
#         print(f"Ошибка на этапе 1: {e}")
#         import traceback
#         traceback.print_exc()
#         return None, None
    
#     # ЭТАП 2: Вычисление объёма редукции
#     print("\n--- ЭТАП 2: Объем редукции ---")
#     try:
#         volume_to_remove = trimesh.boolean.difference([solid_model_2, solid_model_1], engine='manifold')
        
#         if volume_to_remove is None or volume_to_remove.volume == 0:
#             print("  Объем редукции пуст, пробуем альтернативный метод...")
#             try:
#                 bbox = solid_model_1.bounds
#                 size = bbox[1] - bbox[0]
#                 center = (bbox[0] + bbox[1]) / 2
#                 big_box = trimesh.creation.box(extents=size * 2)
#                 big_box.apply_translation(center)
                
#                 inverted_1 = trimesh.boolean.difference([big_box, solid_model_1], engine='manifold')
#                 volume_to_remove = trimesh.boolean.intersection([solid_model_2, inverted_1], engine='manifold')
#             except:
#                 volume_to_remove = solid_model_2.copy()
        
#         if volume_to_remove and hasattr(volume_to_remove, 'volume') and volume_to_remove.volume > 0:
#             volume_to_remove.visual.vertex_colors = [255, 165, 0, 255]
#             save_mesh(volume_to_remove, "03_volume_to_remove.stl", "Объем редукции")
#             print(f"Объем: {volume_to_remove.volume:.2f} мм³")
#         else:
#             print("  ВНИМАНИЕ: Не удалось вычислить объем редукции, используем Model_2 как основу")
#             volume_to_remove = solid_model_2.copy()
            
#     except Exception as e:
#         print(f"Ошибка булевой операции: {e}")
#         import traceback
#         traceback.print_exc()
#         volume_to_remove = solid_model_2.copy()
    
#     # ЭТАП 3: Создание базовой капы
#     print("\n--- ЭТАП 3: Генерация капы ---")
    
#     try:
#         inner_surface = detail_model_2.copy()
#         if inner_surface.vertices.shape[0] > 0:
#             inner_surface.vertices += inner_surface.vertex_normals * clearance
        
#         outer_surface = detail_model_2.copy()
#         if outer_surface.vertices.shape[0] > 0:
#             outer_surface.vertices += outer_surface.vertex_normals * (clearance + cap_thickness)
        
#         inner_watertight = make_watertight_for_boolean(inner_surface, "inner")
#         outer_watertight = make_watertight_for_boolean(outer_surface, "outer")
        
#         try:
#             base_cap = trimesh.boolean.difference([outer_watertight, inner_watertight], engine='manifold')
#         except:
#             try:
#                 base_cap = trimesh.boolean.difference([outer_watertight, inner_watertight], engine='blender')
#             except:
#                 base_cap = outer_watertight.copy()
        
#         if base_cap is None or base_cap.volume == 0:
#             base_cap = outer_watertight.copy()
        
#         base_cap.visual.vertex_colors = [0, 0, 255, 255]
#         save_mesh(base_cap, "04_base_cap_closed.stl", "Базовая капа")
        
#     except Exception as e:
#         print(f"Ошибка создания капы: {e}")
#         import traceback
#         traceback.print_exc()
#         return None, None
    
#     # ЭТАП 4: Создание шахматных прорезей
#     print("\n--- ЭТАП 4: Шахматные прорези ---")
    
#     try:
#         bounds = volume_to_remove.bounds
#         x_min, x_max = bounds[0][0], bounds[1][0]
#         y_min, y_max = bounds[0][1], bounds[1][1]
#         z_min, z_max = bounds[0][2], bounds[1][2]
#         slot_height = (z_max - z_min) + 10
        
#         slot_boxes_1, slot_boxes_2 = [], []
        
#         for idx, x_pos in enumerate(np.arange(x_min, x_max, slot_step)):
#             box = trimesh.creation.box(extents=[slot_width, y_max-y_min+y_bridge, slot_height])
#             box.apply_transform(trimesh.transformations.translation_matrix([
#                 x_pos + slot_width/2, (y_min+y_max)/2, (z_min+z_max)/2
#             ]))
            
#             # Проверяем пересечение с объемом редукции
#             try:
#                 inter = trimesh.boolean.intersection([box, volume_to_remove], engine='manifold')
#                 if inter and inter.volume > 0.01:
#                     if idx % 2 == 0:
#                         slot_boxes_1.append(box)
#                     else:
#                         slot_boxes_2.append(box)
#             except:
#                 # Если не удалось проверить пересечение, добавляем все
#                 if idx % 2 == 0:
#                     slot_boxes_1.append(box)
#                 else:
#                     slot_boxes_2.append(box)
        
#         # Если прорези не создались, создаем их без проверки пересечения
#         if not slot_boxes_1 and not slot_boxes_2:
#             print("  Fallback: создаем прорези без проверки пересечения")
#             for idx, x_pos in enumerate(np.arange(x_min, x_max, slot_step)):
#                 box = trimesh.creation.box(extents=[slot_width, y_max-y_min+y_bridge, slot_height])
#                 box.apply_transform(trimesh.transformations.translation_matrix([
#                     x_pos + slot_width/2, (y_min+y_max)/2, (z_min+z_max)/2
#                 ]))
#                 if idx % 2 == 0:
#                     slot_boxes_1.append(box)
#                 else:
#                     slot_boxes_2.append(box)
        
#         mask_1 = trimesh.util.concatenate(slot_boxes_1) if slot_boxes_1 else trimesh.creation.box(extents=[0.1,0.1,0.1])
#         mask_2 = trimesh.util.concatenate(slot_boxes_2) if slot_boxes_2 else trimesh.creation.box(extents=[0.1,0.1,0.1])
        
#         print(f"Маска 1: {len(slot_boxes_1)} box'ов, Маска 2: {len(slot_boxes_2)} box'ов")
        
#         save_mesh(mask_1, "04a_mask_1.stl", "Маска 1")
#         save_mesh(mask_2, "04b_mask_2.stl", "Маска 2")
        
#     except Exception as e:
#         print(f"Ошибка создания прорезей: {e}")
#         import traceback
#         traceback.print_exc()
#         return None, None
    
#     # ЭТАП 5: Depth Stop
#     print("\n--- ЭТАП 5: Depth Stop ---")
    
#     try:
#         space_to_drill = trimesh.boolean.difference([base_cap, solid_model_1], engine='manifold')
#         if space_to_drill is None or space_to_drill.volume == 0:
#             space_to_drill = base_cap.copy()
        
#         save_mesh(space_to_drill, "05c_space_to_drill.stl", "Пространство сверления")
        
#         try:
#             drill_1 = trimesh.boolean.intersection([mask_1, space_to_drill], engine='manifold')
#             drill_2 = trimesh.boolean.intersection([mask_2, space_to_drill], engine='manifold')
            
#             if drill_1 and drill_1.volume > 0:
#                 print(f"drill_1: {drill_1.volume:.2f} мм³")
#                 save_mesh(drill_1, "05d_drill_1.stl", "Прорези 1")
#             else:
#                 drill_1 = mask_1
                
#             if drill_2 and drill_2.volume > 0:
#                 print(f"drill_2: {drill_2.volume:.2f} мм³")
#                 save_mesh(drill_2, "05e_drill_2.stl", "Прорези 2")
#             else:
#                 drill_2 = mask_2
                
#         except Exception as e:
#             print(f"Ошибка пересечения: {e}")
#             drill_1, drill_2 = mask_1, mask_2
            
#     except Exception as e:
#         print(f"Ошибка Depth Stop: {e}")
#         space_to_drill = base_cap.copy()
#         drill_1, drill_2 = mask_1, mask_2
    
#     # ЭТАП 6: Создание кап с прорезями
#     print("\n--- ЭТАП 6: Формирование кап ---")
    
#     try:
#         cap_with_slots_1 = trimesh.boolean.difference([space_to_drill, drill_1], engine='manifold')
#         cap_with_slots_2 = trimesh.boolean.difference([space_to_drill, drill_2], engine='manifold')
        
#         if cap_with_slots_1 is None or cap_with_slots_1.volume == 0:
#             cap_with_slots_1 = space_to_drill.copy()
#         if cap_with_slots_2 is None or cap_with_slots_2.volume == 0:
#             cap_with_slots_2 = space_to_drill.copy()
            
#         print(f"cap_1: {cap_with_slots_1.volume:.2f} мм³, cap_2: {cap_with_slots_2.volume:.2f} мм³")
        
#         save_mesh(cap_with_slots_1, "06_cap_with_slots_1.stl", "Капа с прорезями 1")
#         save_mesh(cap_with_slots_2, "06_cap_with_slots_2.stl", "Капа с прорезями 2")
        
#     except Exception as e:
#         print(f"Ошибка формирования кап: {e}")
#         import traceback
#         traceback.print_exc()
#         return None, None
    
#     # ЭТАП 6.5: ОЧИСТКА ПРОРЕЗЕЙ
#     print("\n--- ЭТАП 6.5: Очистка прорезей ---")
    
#     try:
#         cap_with_slots_1 = clean_slots_by_redo(
#             cap_with_slots_1, 
#             slot_boxes_1,
#             solid_model_1
#         )
#         save_mesh(cap_with_slots_1, "06_5_cleaned_cap_1.stl", "Капа 1 после очистки")
        
#         cap_with_slots_2 = clean_slots_by_redo(
#             cap_with_slots_2,
#             slot_boxes_2,
#             solid_model_1
#         )
#         save_mesh(cap_with_slots_2, "06_5_cleaned_cap_2.stl", "Капа 2 после очистки")
        
#     except Exception as e:
#         print(f"Ошибка очистки прорезей: {e}")
#         import traceback
#         traceback.print_exc()
    
#     # ЭТАП 7: Добавление юбки
#     print("\n--- ЭТАП 7: Юбка ---")
    
#     try:
#         final_cap_1 = add_skirt_by_copying(cap_with_slots_1, base_cap, skirt_zone, position=skirt_position)
#         final_cap_2 = add_skirt_by_copying(cap_with_slots_2, base_cap, skirt_zone, position=skirt_position)
        
#         final_cap_1.visual.vertex_colors = [0, 255, 255, 255]
#         final_cap_2.visual.vertex_colors = [255, 0, 255, 255]
        
#         save_mesh(final_cap_1, "07_cap_with_skirt_1.stl", "Капа с юбкой 1")
#         save_mesh(final_cap_2, "07_cap_with_skirt_2.stl", "Капа с юбкой 2")
        
#     except Exception as e:
#         print(f"Ошибка добавления юбки: {e}")
#         final_cap_1, final_cap_2 = cap_with_slots_1, cap_with_slots_2
    
    
#     # ЭТАП 9: Финальная очистка
#     print("\n--- ЭТАП 9: Финальная очистка ---")
    
#     try:
#         final_cap_1 = clean_slots_by_redo(
#             final_cap_1,
#             slot_boxes_1,
#             solid_model_1
#         )
#         final_cap_2 = clean_slots_by_redo(
#             final_cap_2,
#             slot_boxes_2,
#             solid_model_1
#         )

#         # final_cap_1 = add_skirt_by_copying(cap_with_slots_1, base_cap, skirt_zone, position=skirt_position)
#         # final_cap_2 = add_skirt_by_copying(cap_with_slots_2, base_cap, skirt_zone, position=skirt_position)
        
#         # final_cap_1.visual.vertex_colors = [0, 255, 255, 255]
#         # final_cap_2.visual.vertex_colors = [255, 0, 255, 255]
        
#         save_mesh(final_cap_1, "08_FINAL_Cap_Step_1.stl", "ФИНАЛЬНАЯ КАПА 1")
#         save_mesh(final_cap_2, "08_FINAL_Cap_Step_2.stl", "ФИНАЛЬНАЯ КАПА 2")
        
#     except Exception as e:
#         print(f"Ошибка финальной очистки: {e}")
    
#     # ============================================================
#     # КОНВЕРТАЦИЯ В БАЙТЫ ДЛЯ ОТПРАВКИ НА ФРОНТЕНД
#     # ============================================================
#     print("\n--- КОНВЕРТАЦИЯ В БАЙТЫ ---")
    
#     bytes_1 = None
#     bytes_2 = None
    
#     try:
#         # Конвертируем первую модель в bytes
#         buffer_1 = io.BytesIO()
#         final_cap_1.export(buffer_1, file_type='stl')
#         bytes_1 = buffer_1.getvalue()
#         print(f"Модель 1: {len(bytes_1)} байт")
        
#         # Конвертируем вторую модель в bytes
#         buffer_2 = io.BytesIO()
#         final_cap_2.export(buffer_2, file_type='stl')
#         bytes_2 = buffer_2.getvalue()
#         print(f"Модель 2: {len(bytes_2)} байт")
        
#     except Exception as e:
#         print(f"Ошибка конвертации в bytes: {e}")
#         import traceback
#         traceback.print_exc()
#         return None, None
    
#     # Сохранение в БД (если нужно)
#     if save_to_db:
#         id_1 = save_mesh_to_blob(final_cap_1, f"{description_prefix}_Step1", 'stl')
#         id_2 = save_mesh_to_blob(final_cap_2, f"{description_prefix}_Step2", 'stl')
#         print(f"Сохранено в БД: ID_1={id_1}, ID_2={id_2}")
    
#     # Сохранение в файлы (если указаны пути)
#     if output_path_1 is not None:
#         final_cap_1.export(output_path_1)
#         print(f"Сохранено в файл: {output_path_1}")
    
#     if output_path_2 is not None:
#         final_cap_2.export(output_path_2)
#         print(f"Сохранено в файл: {output_path_2}")
    
#     print("ГЕНЕРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
    
#     # Возвращаем кортеж байтов
#     return bytes_1, bytes_2

# def parse_int_or_path(s):
#     try:
#         return int(s)
#     except ValueError:
#         return s