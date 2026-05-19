#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для вычитания одной 3D модели из другой
Использование:
  python subtract.py 1 2 output.stl --base-pos 0,0,-17.416 --pattern-pos 0,0,-11.044
"""

import sys
import argparse
import io  # для работы с бинарными данными как с файлом (BytesIO)
import numpy as np
import trimesh
import os


# ============================================================
# НАСТРОЙКИ ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ (замени на свои!)
# ============================================================
DB_CONFIG = {
    'dbname': 'mydatabase',      # название базы данных
    'user': 'myuser',            # пользователь
    'password': 'mypassword',    # пароль
    'host': 'localhost',         # хост
    'port': 5432                 # порт (5432 — стандартный для PostgreSQL)
}

# SQL-запрос для получения модели по ID
# Замени 'models' на название твоей таблицы
# Замени 'model_data' на название колонки с BLOB
# Замени 'id' на название колонки с идентификатором
SQL_GET_MODEL = "SELECT model_data, file_type FROM models WHERE id = %s"


def get_blob_from_database(model_id):
    """
    Достаёт бинарные данные модели и её формат из базы данных по ID
    model_id - идентификатор модели в БД
    
    Возвращает:
        (blob_data, file_type) - бинарные данные (bytes) и формат файла (str)
    """
    try:
        import psycopg2  # библиотека для работы с PostgreSQL
    except ImportError:
        raise  # если нет библиотеки — ошибка, дальше нет смысла продолжать
    
    conn = psycopg2.connect(**DB_CONFIG)  # подключаемся к БД, ** распаковывает словарь в именованные аргументы
    cur = conn.cursor()  # создаём курсор для выполнения SQL-запросов
    
    cur.execute(SQL_GET_MODEL, (model_id,))  # передаём id как кортеж, защита от SQL-инъекций
    row = cur.fetchone()  # получаем первую строку результата запроса
    
    cur.close()  # закрываем курсор
    conn.close()  # закрываем соединение с БД
    
    if row is None:  # если запрос ничего не вернул — модель с таким ID не существует
        raise ValueError(f"Модель с ID={model_id} не найдена в базе данных")
    
    blob_data = row[0]  # бинарные данные модели (колонка model_data)
    file_type = row[1] if len(row) > 1 else 'stl'  # формат файла (колонка file_type), если колонки нет — stl по умолчанию
    
    return blob_data, file_type  # возвращаем бинарные данные и формат файла


def load_mesh_from_source(source, file_type=None):
    """
    Загружает меш из строки (путь к файлу) или из bytes (blob из БД)
    source - путь к файлу (str) или бинарные данные (bytes)
    file_type - формат файла ('stl', 'obj'), нужно указывать для bytes
    """
    
    # Если передали путь к файлу (str) — загружаем как обычно
    #if isinstance(source, str):
    #    mesh = trimesh.load(source, force='mesh')  # гарантировано получаем объект mesh а не сцену
    
    # Если передали бинарные данные (bytes) — оборачиваем в BytesIO чтобы trimesh мог прочитать
    if isinstance(source, bytes):
        file_obj = io.BytesIO(source)  # создаём file-like объект в памяти из байтов, чтобы trimesh думал что читает файл
        if file_type:
            mesh = trimesh.load(file_obj, file_type=file_type, force='mesh')  # указываем формат, потому что у BytesIO нет расширения файла
        else:
            mesh = trimesh.load(file_obj, force='mesh')  # если формат не указан — trimesh попытается угадать сам
    
    return mesh


def apply_transform(mesh, pos, rot):
    """
    Применяет позицию и вращение к мешу
    mesh - объект trimesh.Trimesh
    pos - позиция [x,y,z]
    rot - вращение [rx, ry, rz]
    """
    
    m = mesh.copy() # копируем чтобы изменения не отразились на оригинале 
    rot_rad = np.radians(rot) # переводим градусы в радианы, возвращает [rx, ry, rz], но в радианах 
    
    # Матриа поворота, когда двигаем по одной оси, одна ось не изменяется, а остальные изменяются 
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(rot_rad[0]), -np.sin(rot_rad[0])],
        [0, np.sin(rot_rad[0]), np.cos(rot_rad[0])]
    ])
    
    Ry = np.array([
        [np.cos(rot_rad[1]), 0, np.sin(rot_rad[1])],
        [0, 1, 0],
        [-np.sin(rot_rad[1]), 0, np.cos(rot_rad[1])]
    ])
    
    Rz = np.array([
        [np.cos(rot_rad[2]), -np.sin(rot_rad[2]), 0],
        [np.sin(rot_rad[2]), np.cos(rot_rad[2]), 0],
        [0, 0, 1]
    ])
    
    R = Rz @ Ry @ Rx #Умножение матриы c право на лево сначало rx-ry-rz, чтобы получить 1 матрицу 
    
    m.vertices = m.vertices @ R.T #Переводим координаты в нормальный вид из матриц в вектор [x,y,z]

    m.vertices += pos #добавляем к нашим координатам перемещение 
    
    return m


def make_watertight(mesh):
    """
    Делает меш водонепроницаемым для булевых операций
    mesh - объект trimesh.Trimesh
    """
    m = mesh.copy()# копируем mesh
    m.merge_vertices()# сливаем вершины которые находятся очень близко, но между ними есть разрывы
    m.remove_unreferenced_vertices()# удаляем мертвые вершины 
    
    try:
        m.fix_normals() #: Пытаемся автоматически вывернуть все нормали наружу
    except:
        pass
    
    if m.is_watertight: # проверяем водонепрониыемый ли модель после изменений 
        return m
    
    try:
        m.fill_holes() # заклеиваем дырки если они есть 
    except:
        pass
    
    if m.is_watertight: # проверяем ещё раз после заклеивания дырок
        return m
    
    # Разбиваем на компоненты и берём самую большую
    try:
        parts = m.split(only_watertight=False)
        if len(parts) > 1:
            m = max(parts, key=lambda x: len(x.faces))
            try:
                m.fill_holes()
            except:
                pass
    except:
        pass
    
    if m.is_watertight: # проверяем после разделения на компоненты
        return m
    
    # Последний шанс
    #m = m.convex_hull  # строим выпуклую оболочку, она всегда watertight, но теряются вогнутые детали
    
    return m


def subtract_models(base_source, pattern_source, output_path,
                    base_pos=(0, 0, 0), base_rot=(0, 0, 0),
                    pattern_pos=(0, 0, 0), pattern_rot=(0, 0, 0),
                    base_file_type=None, pattern_file_type=None):
    """
    Вычитает base из pattern (Pattern - Base) и сохраняет результат
        base_source - путь к базовой модели str или бинарные данные bytes (что вычитаем)
        pattern_source - путь ко второй модели str или бинарные данные bytes (из чего вычитаем)
        output_path - путь для сохранения результата
        base_pos - позиция base (x, y, z)
        base_rot - вращение base (x, y, z) в градусах
        pattern_pos - позиция pattern (x, y, z)
        pattern_rot - вращение pattern (x, y, z) в градусах
        base_file_type - формат файла для base ('stl', 'obj'), указывать если base_source это bytes
        pattern_file_type - формат файла для pattern ('stl', 'obj'), указывать если pattern_source это bytes
    """
    
    try:
        # Загрузка моделей
        base = load_mesh_from_source(base_source, base_file_type)  # загружаем из файла или из bytes
        base.merge_vertices()# сливаем вершины которые находятся очень близко, но между ними есть разрывы
        base.remove_unreferenced_vertices()# удаляем мертвые вершины 
        #base = apply_transform(base, np.array(base_pos), np.array(base_rot))#дополнительные координаты если хотим передать 
        
        pattern = load_mesh_from_source(pattern_source, pattern_file_type)  # загружаем из файла или из bytes
        pattern.merge_vertices()# сливаем вершины которые находятся очень близко, но между ними есть разрывы
        pattern.remove_unreferenced_vertices()# удаляем мертвые вершины 
        #pattern = apply_transform(pattern, np.array(pattern_pos), np.array(pattern_rot))#дополнительные координаты если хотим передать 
        
        # Подготовка
        base_ready = make_watertight(base)#делаем mesh замкнутым
        pattern_ready = make_watertight(pattern)#делаем mesh замкнутым
        
        # Вычитание
        result = None# если вычитание не сработает передадим None
        
        # Пробуем manifold3d
        #try:
        #    import manifold3d
        #    result = pattern_ready.difference(base_ready, engine='manifold')#вычитание из pattern вычти base
        #except ImportError:
        #    pass  # библиотека не установлена, пробуем дальше
        #except Exception:
        #    pass  # другая ошибка, пробуем дальше
        
        # Fallback
        if result is None or result.is_empty:  # если manifold3d не сработал или дал пустой результат
            for engine in ['scad', 'blender']:  # перебираем запасные движки
                try:
                    result = pattern_ready.difference(base_ready, engine=engine)  # пробуем вычитание с другим движком
                    if result is not None and not result.is_empty and len(result.faces) > 0: #проверяем что результат не пустой
                        break  # нашли работающий движок, выходим из цикла
                except:
                    continue  # движок упал, пробуем следующий
        
        if result is None or result.is_empty:  # если ни один движок не дал результат
            return False
        
        # Очистка результата
        result.merge_vertices()#удаляем дубликаты 
        result.remove_unreferenced_vertices()#удаяляем мёртвые грани 
        #try:
        #    result.fix_normals()# Пытаемся автоматически вывернуть все нормали наружу
        #except:
        #    pass
        
        # Сохранение
        #os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)#создаём папку если её нет, '.' если путь без папки
        #result.export(output_path)#записываем даные
        
        return True
        
    except FileNotFoundError:
        return False  # файл не найден
    except Exception:
        import traceback
        traceback.print_exc()  # выводим полный стек ошибки для отладки
        return False


def parse_vec3(s):
    """Парсит строку 'x,y,z' в список float"""
    return [float(v) for v in s.split(',')]  # разбиваем строку по запятым и каждую часть в float


def parse_int_or_path(s):
    """
    Парсит аргумент: если число — возвращает int (ID для Blob), иначе строку (путь к файлу)
    s - строка из командной строки
    """
    try:
        return int(s)  # пробуем превратить в число (ID модели в БД)
    except ValueError:
        return s  # не число — значит путь к файлу


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Вычитание одной 3D модели из другой",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python subtract.py 1 2 output.stl --base-pos 0,0,-17.416 --pattern-pos 0,0,-11.044
        """
    )
    
    parser.add_argument("base", type=parse_int_or_path, 
                        help="Путь к базовой модели (str) или ID модели в БД (int)")
    parser.add_argument("pattern", type=parse_int_or_path,
                        help="Путь ко второй модели (str) или ID модели в БД (int)")
    parser.add_argument("output", help="Путь для сохранения результата (.stl)")
    
    parser.add_argument("--base-pos", type=parse_vec3, default=[0, 0, 0],
                        help="Позиция base: x,y,z (по умолчанию: 0,0,0)")
    parser.add_argument("--base-rot", type=parse_vec3, default=[0, 0, 0],
                        help="Вращение base в градусах: x,y,z (по умолчанию: 0,0,0)")
    parser.add_argument("--pattern-pos", type=parse_vec3, default=[0, 0, 0],
                        help="Позиция pattern: x,y,z (по умолчанию: 0,0,0)")
    parser.add_argument("--pattern-rot", type=parse_vec3, default=[0, 0, 0],
                        help="Вращение pattern в градусах: x,y,z (по умолчанию: 0,0,0)")
    
    args = parser.parse_args()  # парсим аргументы командной строки
    
    # ============================================================
    # РЕЖИМ ЗАГРУЗКИ: Blob (из БД) или Файлы (с диска)
    # Раскомментируй нужный блок, второй закомментируй
    # ============================================================
    
    # --- РЕЖИМ BLOB: загрузка из базы данных по ID ---
    # Передаём ID моделей: python subtract.py 1 2 output.stl
    base_blob, base_ft = get_blob_from_database(args.base)  # args.base — это число (ID), получаем bytes и формат
    pattern_blob, pattern_ft = get_blob_from_database(args.pattern)  # args.pattern — это число (ID), получаем bytes и формат
    
    success = subtract_models(
        base_source=base_blob,            # ← bytes из БД
        pattern_source=pattern_blob,      # ← bytes из БД
        output_path=args.output,
        base_pos=args.base_pos,
        base_rot=args.base_rot,
        pattern_pos=args.pattern_pos,
        pattern_rot=args.pattern_rot,
        base_file_type=base_ft,           # ← формат из БД ('stl', 'obj'...)
        pattern_file_type=pattern_ft      # ← формат из БД ('stl', 'obj'...)
    )
    
    # --- РЕЖИМ ФАЙЛЫ: загрузка с диска по пути ---
    # Раскомментируй этот блок и закомментируй блок выше чтобы читать из файлов
    # Передаём пути: python subtract.py base.stl pattern.stl output.stl
    #success = subtract_models(
    #    base_source=args.base,       # ← путь к файлу (str)
    #    pattern_source=args.pattern, # ← путь к файлу (str)
    #    output_path=args.output,
    #    base_pos=args.base_pos,
    #    base_rot=args.base_rot,
    #    pattern_pos=args.pattern_pos,
    #    pattern_rot=args.pattern_rot
    #    # file_type не передаём — trimesh сам определит формат по расширению
    #)
    
    sys.exit(0 if success else 1)  # выходим с кодом 0 если успех, 1 если ошибка