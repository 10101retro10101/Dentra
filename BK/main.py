#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Программа для вычитания моделей с жёсткими координатами

Использование:
  python main.py base.stl pattern.stl --base-pos 0,0,-17.416 --pattern-pos 0,0,-11.044
  
  Или с вращением:
  python main.py base.stl pattern.stl --base-pos 0,0,-17.416 --base-rot 0,0,0 --pattern-pos 0,0,-11.044 --pattern-rot 0,0,0
"""

import sys
import argparse
import numpy as np
import pyvista as pv
import trimesh
import os
import vtk

MOVE_STEP = 0.5

COLOR_BASE = '#cccccc'
COLOR_PATTERN = '#ff8800'
COLOR_RESULT = '#00ff00'


class DentalSubtractor:
    def __init__(self, base_path, pattern_path, base_pos, base_rot, pattern_pos, pattern_rot):
        self.base_path = base_path
        self.pattern_path = pattern_path
        
        # Позиции из аргументов
        self.base_pos = np.array(base_pos)
        self.base_rot = np.array(base_rot)
        self.pattern_pos = np.array(pattern_pos)
        self.pattern_rot = np.array(pattern_rot)
        
        # Модели
        self.base_mesh = None
        self.base_pv = None
        self.pattern_mesh = None
        self.pattern_pv = None
        self.result_mesh = None
        
        # Акторы
        self.base_actor = None
        self.pattern_actor = None
        self.result_actor = None
        
        # Смещения для ручной настройки
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        
        self.plotter = None
        
        self._load_models()
    
    def _apply_transform(self, mesh, pos, rot):
        """Применяет позицию и вращение к мешу"""
        m = mesh.copy()
        
        # Вращение (в градусах)
        rot_rad = np.radians(rot)
        
        # Матрица вращения
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
        
        R = Rz @ Ry @ Rx
        
        # Применяем вращение
        m.vertices = m.vertices @ R.T
        
        # Применяем позицию
        m.vertices += pos
        
        return m
    
    def _load_models(self):
        """Загрузка моделей с применением координат"""
        print("📥 Загрузка моделей...")
        
        # Базовая модель
        print(f"   Base: {self.base_path}")
        base = trimesh.load(self.base_path, force='mesh')
        base.merge_vertices()
        base.remove_unreferenced_vertices()
        
        # Применяем координаты
        self.base_mesh = self._apply_transform(base, self.base_pos, self.base_rot)
        
        faces = np.column_stack([
            np.full(len(self.base_mesh.faces), 3),
            self.base_mesh.faces
        ]).flatten()
        self.base_pv = pv.PolyData(self.base_mesh.vertices, faces)
        
        print(f"      Вершин: {len(self.base_mesh.vertices)}")
        print(f"      Позиция: ({self.base_pos[0]:.3f}, {self.base_pos[1]:.3f}, {self.base_pos[2]:.3f})")
        print(f"      Вращение: ({self.base_rot[0]:.1f}°, {self.base_rot[1]:.1f}°, {self.base_rot[2]:.1f}°)")
        
        # Вторая модель
        if self.pattern_path:
            print(f"   Pattern: {self.pattern_path}")
            pattern = trimesh.load(self.pattern_path, force='mesh')
            pattern.merge_vertices()
            pattern.remove_unreferenced_vertices()
            self.pattern_mesh = self._apply_transform(pattern, self.pattern_pos, self.pattern_rot)
        else:
            print(f"   Pattern: куб 20x20x20 мм")
            pattern = trimesh.creation.box(extents=[20, 20, 20])
            self.pattern_mesh = self._apply_transform(pattern, self.pattern_pos, self.pattern_rot)
        
        faces = np.column_stack([
            np.full(len(self.pattern_mesh.faces), 3),
            self.pattern_mesh.faces
        ]).flatten()
        self.pattern_pv = pv.PolyData(self.pattern_mesh.vertices, faces)
        
        print(f"      Вершин: {len(self.pattern_mesh.vertices)}")
        print(f"      Позиция: ({self.pattern_pos[0]:.3f}, {self.pattern_pos[1]:.3f}, {self.pattern_pos[2]:.3f})")
        print(f"      Вращение: ({self.pattern_rot[0]:.1f}°, {self.pattern_rot[1]:.1f}°, {self.pattern_rot[2]:.1f}°)\n")
    
    def _update_pattern_position(self):
        """Обновляет позицию второй модели с учётом смещений"""
        # Итоговая позиция = базовая + смещение
        final_pos = self.pattern_pos + np.array([self.offset_x, self.offset_y, self.offset_z])
        
        # Пересоздаём модель с новыми координатами
        if self.pattern_path:
            pattern = trimesh.load(self.pattern_path, force='mesh')
            pattern.merge_vertices()
            pattern.remove_unreferenced_vertices()
        else:
            pattern = trimesh.creation.box(extents=[20, 20, 20])
        
        self.pattern_mesh = self._apply_transform(pattern, final_pos, self.pattern_rot)
        
        faces = np.column_stack([
            np.full(len(self.pattern_mesh.faces), 3),
            self.pattern_mesh.faces
        ]).flatten()
        self.pattern_pv = pv.PolyData(self.pattern_mesh.vertices, faces)
        
        # Обновляем отображение
        if self.pattern_actor:
            self.plotter.remove_actor(self.pattern_actor)
        
        self.pattern_actor = self.plotter.add_mesh(
            self.pattern_pv,
            color=COLOR_PATTERN,
            opacity=0.5,
            show_edges=True,
            edge_color='black',
            line_width=2,
            name='pattern',
            pickable=False
        )
        
        if self.result_actor:
            self.plotter.remove_actor(self.result_actor)
            self.result_actor = None
            self.result_mesh = None
        
        self.plotter.render()
        
        print(f"📍 Pattern позиция: ({final_pos[0]:.3f}, {final_pos[1]:.3f}, {final_pos[2]:.3f})")
        print(f"   Смещение от базовой: X={self.offset_x:.1f} Y={self.offset_y:.1f} Z={self.offset_z:.1f}\n")
    
    def _move_pattern(self, dx, dy, dz):
        """Перемещает вторую модель"""
        self.offset_x += dx
        self.offset_y += dy
        self.offset_z += dz
        print(f"📍 Смещение: X={self.offset_x:.1f} Y={self.offset_y:.1f} Z={self.offset_z:.1f}")
        self._update_pattern_position()
    
    def _make_watertight(self, mesh):
        """Делает меш водонепроницаемым"""
        m = mesh.copy()
        m.merge_vertices()
        m.remove_unreferenced_vertices()
        
        try:
            m.fix_normals()
        except:
            pass
        
        if m.is_watertight:
            return m
        
        try:
            m.fill_holes()
        except:
            pass
        
        if m.is_watertight:
            return m
        
        m = m.convex_hull
        return m
    
    def _subtract(self):
        """Вычитает base из pattern (Pattern - Base)"""
        if self.pattern_mesh is None:
            print("⚠️ Нет второй модели!\n")
            return
        
        print("🛠️ ВЫЧИТАНИЕ: Pattern - Base...")
        
        try:
            base_ready = self._make_watertight(self.base_mesh)
            pattern_ready = self._make_watertight(self.pattern_mesh)
            
            print(f"   Base: {len(base_ready.vertices)} вершин, watertight: {base_ready.is_watertight}")
            print(f"   Pattern: {len(pattern_ready.vertices)} вершин, watertight: {pattern_ready.is_watertight}")
            print("   🔧 Вычитание...")
            
            result = None
            
            try:
                import manifold3d
                result = pattern_ready.difference(base_ready, engine='manifold')
                if result is not None and not result.is_empty and len(result.faces) > 0:
                    print("   ✅ manifold3d!")
            except:
                pass
            
            if result is None or result.is_empty:
                for engine in ['scad', 'blender']:
                    try:
                        result = pattern_ready.difference(base_ready, engine=engine)
                        if result is not None and not result.is_empty and len(result.faces) > 0:
                            print(f"   ✅ {engine}!")
                            break
                    except:
                        continue
            
            if result is None or result.is_empty:
                print("❌ Не удалось!\n")
                return
            
            self.result_mesh = result
            
            if self.result_actor:
                self.plotter.remove_actor(self.result_actor)
            
            if self.pattern_actor:
                self.pattern_actor.GetProperty().SetOpacity(0.1)
            
            pv_result = pv.wrap(result)
            self.result_actor = self.plotter.add_mesh(
                pv_result,
                color=COLOR_RESULT,
                opacity=0.9,
                name='result',
                pickable=False,
                smooth_shading=True
            )
            
            self.plotter.render()
            
            print(f"✅ {len(result.vertices)} вершин, {len(result.faces)} граней\n")
            
        except Exception as e:
            print(f"❌ {e}\n")
    
    def _export(self):
        if self.result_mesh is None:
            print("⚠️ Нет результата!\n")
            return
        
        os.makedirs("output", exist_ok=True)
        output_path = "output/result.stl"
        
        self.result_mesh.export(output_path)
        
        file_size = os.path.getsize(output_path) / 1024
        print(f"💾 {output_path} ({file_size:.1f} КБ)\n")
    
    def _reset(self):
        print("🔄 Сброс смещений...\n")
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        
        if self.result_actor:
            self.plotter.remove_actor(self.result_actor)
            self.result_actor = None
            self.result_mesh = None
        
        self._update_pattern_position()
        print("✅\n")
    
    def run(self):
        self.plotter = pv.Plotter()
        self.plotter.set_background('#1a1a1a')
        
        self.base_actor = self.plotter.add_mesh(
            self.base_pv,
            color=COLOR_BASE,
            opacity=1.0,
            name='base',
            pickable=False
        )
        
        self.pattern_actor = self.plotter.add_mesh(
            self.pattern_pv,
            color=COLOR_PATTERN,
            opacity=0.5,
            show_edges=True,
            edge_color='black',
            line_width=2,
            name='pattern',
            pickable=False
        )
        
        self.plotter.add_text(
            "ВЫЧИТАНИЕ: Pattern - Base",
            position='upper_left',
            font_size=14,
            color='white'
        )
        
        self.plotter.add_text(
            "IJKL/UO: двигать pattern | B: вычесть | X: экспорт | R: сброс смещений",
            position='lower_left',
            font_size=10,
            color='#aaaaaa'
        )
        
        self.plotter.add_key_event('b', self._subtract)
        self.plotter.add_key_event('x', self._export)
        self.plotter.add_key_event('r', self._reset)
        
        # Перемещение pattern
        self.plotter.add_key_event('i', lambda: self._move_pattern(0, 0, MOVE_STEP))
        self.plotter.add_key_event('k', lambda: self._move_pattern(0, 0, -MOVE_STEP))
        self.plotter.add_key_event('j', lambda: self._move_pattern(-MOVE_STEP, 0, 0))
        self.plotter.add_key_event('l', lambda: self._move_pattern(MOVE_STEP, 0, 0))
        self.plotter.add_key_event('u', lambda: self._move_pattern(0, -MOVE_STEP, 0))
        self.plotter.add_key_event('o', lambda: self._move_pattern(0, MOVE_STEP, 0))
        
        # Стрелки
        self.plotter.add_key_event('Up', lambda: self._move_pattern(0, 0, MOVE_STEP))
        self.plotter.add_key_event('Down', lambda: self._move_pattern(0, 0, -MOVE_STEP))
        self.plotter.add_key_event('Left', lambda: self._move_pattern(-MOVE_STEP, 0, 0))
        self.plotter.add_key_event('Right', lambda: self._move_pattern(MOVE_STEP, 0, 0))
        
        print("\n" + "="*60)
        print("  ВЫЧИТАНИЕ: PATTERN - BASE")
        print("="*60)
        print(f"  Base:    pos({self.base_pos[0]:.3f}, {self.base_pos[1]:.3f}, {self.base_pos[2]:.3f}) rot({self.base_rot[0]:.1f}, {self.base_rot[1]:.1f}, {self.base_rot[2]:.1f})")
        print(f"  Pattern: pos({self.pattern_pos[0]:.3f}, {self.pattern_pos[1]:.3f}, {self.pattern_pos[2]:.3f}) rot({self.pattern_rot[0]:.1f}, {self.pattern_rot[1]:.1f}, {self.pattern_rot[2]:.1f})")
        print("  IJKL/UO или стрелки - двигать pattern")
        print("  B - вычесть | X - экспорт | R - сброс")
        print("="*60 + "\n")
        
        self.plotter.show()


def parse_vec3(s):
    """Парсит строку 'x,y,z' в список float"""
    return [float(v) for v in s.split(',')]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Вычитание моделей с жёсткими координатами")
    parser.add_argument("base", help="Путь к базовой модели (челюсть)")
    parser.add_argument("pattern", nargs='?', default=None, help="Путь ко второй модели (если не указана - куб)")
    parser.add_argument("--base-pos", type=parse_vec3, default=[0, 0, -17.416], help="Позиция base: x,y,z")
    parser.add_argument("--base-rot", type=parse_vec3, default=[0, 0, 0], help="Вращение base: x,y,z (градусы)")
    parser.add_argument("--pattern-pos", type=parse_vec3, default=[0, 0, -11.044], help="Позиция pattern: x,y,z")
    parser.add_argument("--pattern-rot", type=parse_vec3, default=[0, 0, 0], help="Вращение pattern: x,y,z (градусы)")
    
    args = parser.parse_args()
    
    app = DentalSubtractor(
        args.base,
        args.pattern,
        args.base_pos,
        args.base_rot,
        args.pattern_pos,
        args.pattern_rot
    )
    app.run()