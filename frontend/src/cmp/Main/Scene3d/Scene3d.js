/* eslint-disable react-hooks/exhaustive-deps */
import "./Scene3d.scss"
import { Suspense, useRef, useEffect, useMemo, useCallback } from 'react'
import { Canvas, useLoader } from '@react-three/fiber'
import { OrbitControls, TransformControls } from '@react-three/drei'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { Environment } from '@react-three/drei'
import { connect } from "react-redux"
import { setLoading } from "../../../AppSlice"

const STLModel = ({ 
    url, type, color, initialPosition, initialRotation, onPositionChange, 
    onRotationChange, setStlData, stl_state, registerModelRef, setLoading, opacity
}) => {
    const controls_ref = useRef()
    const mesh_ref = useRef()
    const geometry = useLoader(STLLoader, url)
    const is_dragging_ref = useRef(false)
    const is_external_update_ref = useRef(false)

    const originalGeometry = useMemo(() => {
        const cloned = geometry.clone()
        cloned.computeBoundingBox()
        return cloned
    }, [geometry])

    // Вычисление размеров и статистики модели
    useEffect(() => {
        if (!originalGeometry.boundingBox) return
        
        const { min, max } = originalGeometry.boundingBox
        const vertices = originalGeometry.attributes.position.count
        
        setStlData(prev => ({
            ...prev,
            [type]: {
                ...prev[type],
                size_x: (max.x - min.x).toFixed(2),
                size_y: (max.y - min.y).toFixed(2),
                size_z: (max.z - min.z).toFixed(2),
                verticles: vertices,
                triangles: Math.floor(vertices / 3)
            }
        }))
    }, [originalGeometry, type, setStlData])

    // Регистрация модели
    useEffect(() => {
        if (mesh_ref.current && registerModelRef) {
            registerModelRef(type, mesh_ref.current)
            return () => registerModelRef(type, null)
        }
    }, [type, registerModelRef])

    // Обновление позиции извне
    const updateTransform = useCallback((source, target, value, toRadians = false) => {
        if (!controls_ref.current || is_dragging_ref.current || !controls_ref.current.object) return
        
        const current = controls_ref.current.object[source]
        const newValue = toRadians ? value * Math.PI / 180 : value
        
        if (current[target] !== newValue) {
            is_external_update_ref.current = true
            controls_ref.current.object[source].set(newValue.x, newValue.y, newValue.z)
            setTimeout(() => { is_external_update_ref.current = false }, 100)
        }
    }, [])

    useEffect(() => {
        updateTransform('position', 'set', { 
            x: initialPosition[0], 
            y: initialPosition[1], 
            z: initialPosition[2] 
        })
    }, [initialPosition, updateTransform])

    useEffect(() => {
        updateTransform('rotation', 'set', { 
            x: initialRotation[0] * Math.PI / 180, 
            y: initialRotation[1] * Math.PI / 180, 
            z: initialRotation[2] * Math.PI / 180 
        })
    }, [initialRotation, updateTransform])

    // Обработка изменений от TransformControls
    useEffect(() => {
        const tc = controls_ref.current
        if (!tc) return
        
        const handleDraggingChanged = (e) => {
            is_dragging_ref.current = e.value
            if (!e.value && tc.object && !is_external_update_ref.current) {
                const obj = tc.object
                onPositionChange(type, [obj.position.x, obj.position.y, obj.position.z])
                onRotationChange(type, [
                    obj.rotation.x * 180 / Math.PI,
                    obj.rotation.y * 180 / Math.PI,
                    obj.rotation.z * 180 / Math.PI
                ])
            }
        }
        
        tc.addEventListener('dragging-changed', handleDraggingChanged)
        return () => tc.removeEventListener('dragging-changed', handleDraggingChanged)
    }, [type, onPositionChange, onRotationChange])

    return (
        <TransformControls ref={controls_ref} mode={stl_state || 'translate'} size={1.3} makeDefault={false}>
            <mesh ref={mesh_ref} geometry={originalGeometry}>
                <meshStandardMaterial 
                    color={color} 
                    roughness={0.3} 
                    metalness={0.1}
                    transparent={opacity < 1}
                    opacity={opacity}
                />
            </mesh>
        </TransformControls>
    )
}

const ModelConfig = {
    base: { color: "lightblue" },
    pattern: { color: "lightgreen" },
    union_1: { color: "orange" },
    union_2: { color: "orange" },
}

const Scene3d = (props) => {
    const registerModelRef = useCallback((type, mesh) => {
        props.model_refs.current[type] = mesh
    }, [props.model_refs])

    const createHandler = (handlerName) => (type, value) => {
        const roundedValue = value.map(v => Math.floor(v))
        props.setStlData(prev => ({
            ...prev,
            [type]: { ...prev[type], [handlerName]: roundedValue }
        }))
    }

    const handlePositionChange = createHandler('xyz')
    const handleRotationChange = createHandler('rotation')

    useEffect(() => {
        props.onExportReady?.(props.exportMergedSTL)
    }, [props.exportMergedSTL, props.onExportReady])

    const renderModel = (type, stl, data) => {
        if (!stl) return null
        let opacity = data.opacity
        if (type === "union_2"){opacity = 0}
        
        return (
            <STLModel
                key={`${type}_${data.xyz.join('_')}_${data.rotation.join('_')}_${props.stl_state}_${data.opacity}`}
                url={stl}
                type={type}
                color={ModelConfig[type].color}
                initialPosition={data.xyz}
                initialRotation={data.rotation}
                onPositionChange={handlePositionChange}
                onRotationChange={handleRotationChange}
                setStlData={props.setStlData}
                stl_state={props.stl_state}
                registerModelRef={registerModelRef}
                setLoading={props.setLoading}
                opacity={opacity}
            />
        )
    }

    return (
        <div className="scene3d">
            <Canvas camera={{ position: [0, 0, 100], fov: 45, near: 0.1, far: 1000 }} dpr={[1, 2]}>
                <Environment preset="studio" />
                <Suspense fallback={null}>
                    <OrbitControls makeDefault />
                    {renderModel('base', props.stl_base, props.stl_data.base)}
                    {renderModel('pattern', props.stl_pattern, props.stl_data.pattern)}
                    {renderModel('union_1', props.stl_union_1, props.stl_data.union_1)}
                    {renderModel('union_2', props.stl_union_2, props.stl_data.union_2)}
                </Suspense>
            </Canvas>
        </div>
    )
}

const mapStateToProps = (state) => state
const mapDispatchToProps = (dispatch) => ({
    setLoading: (data) => dispatch(setLoading(data))
})

export default connect(mapStateToProps, mapDispatchToProps)(Scene3d)