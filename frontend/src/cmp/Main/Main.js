/* eslint-disable react-hooks/exhaustive-deps */
import "./Main.scss"
import Scene3d from "./Scene3d/Scene3d"
import { useRef, useState, useEffect, useCallback } from "react"
import { STLExporter } from 'three/examples/jsm/exporters/STLExporter'
import * as THREE from 'three'
import Library from "./Library/Library"
import { connect } from "react-redux"
import { setLoading, updateLang, updateModal } from "../../AppSlice"
import axios from "axios"

//imgs
import logo from "../Auth/media/logo.png"
import download from "./media/upload.svg"
import upload from "./media/download.svg" 
import translate from "./media/translate.svg"
import rotate from "./media/rotate.svg"
import merge from "./media/merge.svg"
import library from "./media/library.svg"
import edit from "./media/edit.svg"
import ru from "./media/ru.svg"
import en from "./media/en.svg"
import de from "./media/de.svg"
import es from "./media/es.svg"
import zh from "./media/zh.svg"
import opacity_1 from "./media/opacity_1.svg";
import opacity_0 from "./media/opacity_0.svg";
import language from "./media/language.svg"

const Main = (props) => {
    //state
    const langs = [
        {name:"ru", img:ru},
        {name:"en", img:en},
        {name:"es", img:es},
        {name:"de", img:de},
        {name:"zh", img:zh},
    ]
    const XYZ = [
        {name:"X", color:"red"},
        {name:"Y", color:"green"},
        {name:"Z", color:"blue"},
    ]
    const base_input_ref = useRef(null)
    const pattern_input_ref = useRef(null)
    const [stl_base, setStlBase] = useState(null)
    const [stl_pattern, setStlPattern] = useState(null)
    const [stl_union_1, setStlUnion1] = useState(null)
    const [stl_union_2, setStlUnion2] = useState(null)
    const default_data = {xyz: [0,0,0], rotation: [0,0,0], opacity: 1, size_x:0, size_y:0, size_z:0, verticles:0, triangles:0}
    const [stl_data, setStlData] = useState({
        base: JSON.parse(JSON.stringify(default_data)),
        pattern: JSON.parse(JSON.stringify(default_data)),
        union_1: JSON.parse(JSON.stringify(default_data)),
        union_2: JSON.parse(JSON.stringify(default_data))
    })
    const [stl_state, setStlState] = useState("translate")
    const model_refs = useRef({})
    const [lib_open, setLibState] = useState("")
    const [drill_params, setDrillParams] = useState({
        name:"-", d1:0, L:0, L1:0, L2:0, L3:0
    })
    const [additional_params, setAddParams] = useState({
        skirt:3, is_upper:true
    })

    //handlers
    const baseHandler = () => {
        base_input_ref.current?.click()
    }
    const patternHandler = () => {
        pattern_input_ref.current?.click()
    } 
    
    const baseFileChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            const url = URL.createObjectURL(file)
            setStlBase(url)
            e.target.value = null
        }
    }
    const patternFileChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            const url = URL.createObjectURL(file)
            setStlPattern(url)
            e.target.value = null
        }
    }

    useEffect(() => {
        return () => {
            if (stl_base) URL.revokeObjectURL(stl_base)
            if (stl_pattern) URL.revokeObjectURL(stl_pattern)
        }
    }, [stl_base, stl_pattern])

    const clearScene = () => {
        setStlBase(null)
        setStlPattern(null)
        setStlUnion1(null)
        setStlUnion2(null)
        setStlData({
            base: JSON.parse(JSON.stringify(default_data)),
            pattern: JSON.parse(JSON.stringify(default_data)),
            union_1: JSON.parse(JSON.stringify(default_data)),
            union_2: JSON.parse(JSON.stringify(default_data))
        })
    }

    const exportMergedSTL = useCallback(() => {
        let union_1 = model_refs.current.union_1
        union_1.updateMatrixWorld(true)
        const union_1_clone = union_1.clone()
        union_1_clone.applyMatrix4(union_1.matrixWorld)
        const temp_scene_union_1 = new THREE.Scene()
        temp_scene_union_1.add(union_1_clone)
        const exporter = new STLExporter()
        const stlData_union_1 = exporter.parse(temp_scene_union_1, { binary: true })
        const union_1_blob = new Blob([stlData_union_1], { type: 'application/sla' })

        let union_2 = model_refs.current.union_2
        union_2.updateMatrixWorld(true)
        const union_2_clone = union_2.clone()
        union_2_clone.applyMatrix4(union_2.matrixWorld)
        const temp_scene_union_2 = new THREE.Scene()
        temp_scene_union_2.add(union_2_clone)
        const stlData_union_2 = exporter.parse(temp_scene_union_2, { binary: true })
        const union_2_blob = new Blob([stlData_union_2], { type: 'application/sla' })

        let data = new FormData()
        data.append('union_1_stl', union_1_blob, 'union_1.stl')
        data.append('union_2_stl', union_2_blob, 'union_2.stl')
        axios.post(`http://localhost:${props.app.backend_port}/save_model`, data, {headers: {'Content-Type': 'multipart/form-data',}}).then(response => {
            let file_path = response.data.file_path 
            props.updateModal({title: file_path})
        })
    }, [stl_union_1, stl_union_2])

    const unionModels = useCallback(async () => {
        if ((drill_params.name === "-") || (stl_base === null) || (stl_pattern === null)){
            props.updateModal({title:props.app.lang_data.error_5})
        }else{
            props.setLoading(true)
            try {
                const { base, pattern } = model_refs.current
                base.updateMatrixWorld(true)
                const base_clone = base.clone()
                base_clone.applyMatrix4(base.matrixWorld)
                const temp_scene_base = new THREE.Scene()
                temp_scene_base.add(base_clone)
                const exporter = new STLExporter()
                const stlData_base = exporter.parse(temp_scene_base, { binary: true })
                
                pattern.updateMatrixWorld(true)
                const pattern_clone = pattern.clone()
                pattern_clone.applyMatrix4(pattern.matrixWorld)
                const temp_scene_pattern = new THREE.Scene()
                temp_scene_pattern.add(pattern_clone)
                const stlData_pattern = exporter.parse(temp_scene_pattern, { binary: true })
                
                const formData = new FormData()
                const baseBlob = new Blob([stlData_base], { type: 'application/sla' })
                const patternBlob = new Blob([stlData_pattern], { type: 'application/sla' })
                formData.append('base_stl', baseBlob, 'base.stl')
                formData.append('pattern_stl', patternBlob, 'pattern.stl')
                formData.append('drill_l', drill_params.L)
                formData.append('drill_d', drill_params.d1)
                formData.append('skirt', additional_params.skirt)
                formData.append('is_upper', additional_params.is_upper)
                
                const response = await axios.post(
                    `http://localhost:${props.app.backend_port}/union_models`,
                    formData,
                    {
                        headers: {
                            'Content-Type': 'multipart/form-data',
                        },
                    }
                )

                const binaryString1 = atob(response.data.guide_1);
                const bytes1 = new Uint8Array(binaryString1.length);
                for (let i = 0; i < binaryString1.length; i++) {
                    bytes1[i] = binaryString1.charCodeAt(i);
                }
                const guide1Blob = new Blob([bytes1], { type: 'application/sla' });
                const url1 = URL.createObjectURL(guide1Blob);
                
                const binaryString2 = atob(response.data.guide_2);
                const bytes2 = new Uint8Array(binaryString2.length);
                for (let i = 0; i < binaryString2.length; i++) {
                    bytes2[i] = binaryString2.charCodeAt(i);
                }
                const guide2Blob = new Blob([bytes2], { type: 'application/sla' });
                const url2 = URL.createObjectURL(guide2Blob);
                
                if (stl_union_1) {
                    URL.revokeObjectURL(stl_union_1)
                }
                if (stl_union_2) {
                    URL.revokeObjectURL(stl_union_2)
                }
                
                clearScene()
                setStlUnion1(url1)
                setStlUnion2(url2)
                
            } catch (error) {
                console.error('Error merging models:', error)
                props.setLoading(false)
            } finally {
                props.setLoading(false)
            }
        }
    }, [model_refs, props.app.backend_port, stl_union_1, stl_union_2, drill_params, stl_base, stl_pattern, props.app.lang_data, additional_params])

    const xyzHandler = (key, index, value) => {
        const numValue = value === '' ? 0 : Number(value)
        setStlData(prev_data => {
            let cur_data = {...prev_data}
            cur_data[key].xyz[index] = numValue
            return cur_data
        })
    }
    const rotationHandler = (key, index, value) => {
        const numValue = value === '' ? 0 : Number(value)
        setStlData(prev_data => {
            let cur_data = {...prev_data}
            cur_data[key].rotation[index] = numValue
            return cur_data
        })
    }
    const opacityHandler = () => {
        let cur_opacity = stl_data.pattern.opacity
        let new_opacity = 1
        if (cur_opacity === 1){
            new_opacity = 0.5
        }
        setStlData(prev_data => {
            let cur_data = {...prev_data}
            cur_data.pattern.opacity = new_opacity
            return cur_data
        })
    }

    const additionalParamsHandler = (key, value) => {
        if (key === "is_upper"){
            let is_upper = false
            if (value === "top"){is_upper = true}
            setAddParams(prev_data => {
                let cur_data = {...prev_data}
                cur_data.is_upper = is_upper
                return cur_data
            })
        }
        if (key === "skirt"){
            setAddParams(prev_data => {
                let cur_data = {...prev_data}
                cur_data.skirt = value
                return cur_data
            })
        }
    }
    
    return <div className="main">
        <input
            type="file"
            accept=".stl"
            ref={base_input_ref}
            onChange={baseFileChange}
            style={{ display: 'none' }}
        />
        <input
            type="file"
            accept=".stl"
            ref={pattern_input_ref}
            onChange={patternFileChange}
            style={{ display: 'none' }}
        />
        <div className="left_section">
            <div className="logo_section glass shadow">
                <img src={logo} alt="" className="logo"/>
                <p>{props.app.lang_data.name}</p>
            </div>
            <div className="object_loading">
                <div className="language">
                    <button className="main_button glass shadow">
                        <img src={language} alt=""/>
                    </button>
                    <div className="hint glass shadow">
                        {langs.map((l_item, l_index) => {
                            return <div key={l_index} className={"lang_item " + (props.app.lang===l_item.name?"active":"")} onClick={() => {props.updateLang(l_item.name)}}>
                                <img src={l_item.img} alt="" />
                            </div>
                        })}
                    </div>
                </div>
                <div className="upload">
                    <button className="main_button glass shadow">
                        <img src={upload} alt="" />
                    </button>
                    <div className="hint item_1 glass shadow" onClick={baseHandler}>
                        <p>{props.app.lang_data.upload_1}</p>
                    </div>
                    <div className="hint item_2 glass shadow" onClick={patternHandler}>
                        <p>{props.app.lang_data.upload_2}</p>
                    </div>
                </div>
                <div className="download">
                    <button className="main_button glass shadow" onClick={exportMergedSTL}>
                        <img src={download} alt="" />
                    </button>
                    <div className="hint glass shadow" onClick={exportMergedSTL}>
                        <p>{props.app.lang_data.download}</p>
                    </div>
                </div>
                <div className="clear">
                    <button className="main_button glass shadow" onClick={clearScene}></button>
                    <div className="hint glass shadow" onClick={clearScene}>
                        <p>{props.app.lang_data.clear}</p>
                    </div>
                </div>
                <div className="download">
                    <button className="main_button glass shadow">
                        <img src={stl_state==="translate"?translate:rotate} alt="" />
                    </button>
                    <div className="hint item_1 glass shadow" onClick={() => {setStlState("translate")}}>
                        <p>{props.app.lang_data.translate}</p>
                    </div>
                    <div className="hint item_2 glass shadow" onClick={() => {setStlState("rotate")}}>
                        <p>{props.app.lang_data.rotate}</p>
                    </div>
                </div>
                <div className="download">
                    <button className="main_button glass shadow" onClick={opacityHandler}>
                        <img src={stl_data.pattern.opacity===1?opacity_1:opacity_0} alt="" />
                    </button>
                    <div className="hint glass shadow" onClick={opacityHandler}>
                        <p>{props.app.lang_data.opacity}</p>
                    </div>
                </div>
            </div>
        </div>

        <div className="right_section">
            <div className="section_button">
                <button className="main_button glass shadow" onClick={unionModels}>
                    <img src={merge} alt="" />
                </button>
                <div className="hint glass shadow" onClick={unionModels}>
                    <p>{props.app.lang_data.union}</p>
                </div>
            </div>
            <div className="section_button">
                <button className="main_button glass shadow" onClick={() => {setLibState("active")}}>
                    <img src={library} alt="" />
                </button>
                <div className="hint glass shadow" onClick={() => {setLibState("active")}}>
                    <p>{props.app.lang_data.library}</p>
                </div>
            </div>
            <div className="section_button xyz_section">
                <button className="main_button glass shadow">
                    <img src={edit} alt="" />
                </button>
                <div className="hint glass shadow">
                    <div className="xyz_group">
                        <div className="xyz">
                            <p className="top">{props.app.lang_data.params_base}</p>
                            <ul className="inputs">
                                {XYZ.map((item, index) => {
                                    return <li key={index}>
                                        <p className={item.color}>{item.name}</p>
                                        <input type="number" value={stl_data.base.xyz[index] === 0 ? '' : stl_data.base.xyz[index]} placeholder="0" onChange={(e) => {xyzHandler("base", index, e.target.value)}}/>
                                    </li>
                                })}
                            </ul>
                        </div>
                        <div className="xyz">
                            <p className="top">{props.app.lang_data.params_pattern}</p>
                            <ul className="inputs">
                                {XYZ.map((item, index) => {
                                    return <li key={index}>
                                        <p className={item.color}>{item.name}</p>
                                        <input type="number" value={stl_data.pattern.xyz[index] === 0 ? '' : stl_data.pattern.xyz[index]} placeholder="0" onChange={(e) => {xyzHandler("pattern", index, e.target.value)}}/>
                                    </li>
                                })}
                            </ul>
                        </div>
                    </div>
                    <div className="xyz_group">
                        <div className="xyz">
                            <p className="top">{props.app.lang_data.rotation_base}</p>
                            <ul className="inputs">
                                {XYZ.map((item, index) => {
                                    return <li key={index}>
                                        <p className={item.color}>{item.name}</p>
                                        <input type="number" value={stl_data.base.rotation[index] === 0 ? '' : stl_data.base.rotation[index]} placeholder="0" onChange={(e) => {rotationHandler("base", index, e.target.value)}}/>
                                    </li>
                                })}
                            </ul>
                        </div>
                        <div className="xyz">
                            <p className="top">{props.app.lang_data.rotation_pattern}</p>
                            <ul className="inputs">
                                {XYZ.map((item, index) => {
                                    return <li key={index}>
                                        <p className={item.color}>{item.name}</p>
                                        <input type="number" value={stl_data.pattern.rotation[index] === 0 ? '' : stl_data.pattern.rotation[index]} placeholder="0" onChange={(e) => {rotationHandler("pattern", index, e.target.value)}}/>
                                    </li>
                                })}
                            </ul>
                        </div>
                    </div>
                    <div className="orientation">
                        <div className="orientation_item">
                            <input type="checkbox" checked={additional_params.is_upper} onChange={() => {additionalParamsHandler("is_upper", "top")}}/>
                            <p>{props.app.lang_data.top_jaw}</p>
                        </div>
                        <div className="orientation_item">
                            <input type="checkbox" checked={!additional_params.is_upper} onChange={() => {additionalParamsHandler("is_upper", "bottom")}}/>
                            <p>{props.app.lang_data.bottom_jaw}</p>
                        </div>
                    </div>
                    <div className="skirt">
                        <input type="range" value={additional_params.skirt} step={0.1} min={0.1} max={10} onChange={(e) => {additionalParamsHandler("skirt", e.target.value)}}/>
                        <p>{props.app.lang_data.skirt} - {additional_params.skirt} {props.app.lang_data.mm}</p>
                    </div>
                </div>
            </div>
            <div className="section_drill glass shadow">
                <h2 className="top">{props.app.lang_data.drill_params}</h2>
                <div className="drill_params">
                    <p className="drill_param">{props.app.lang_data.drill_name}: {props.app.lang_data.drill} {drill_params.name}</p>
                    <p className="drill_param">d1: {drill_params.d1} {props.app.lang_data.mm}</p>
                    <p className="drill_param">L: {drill_params.L} {props.app.lang_data.mm}</p>
                    <p className="drill_param">L1: {drill_params.L1} {props.app.lang_data.mm}</p>
                    <p className="drill_param">L2: {drill_params.L2} {props.app.lang_data.mm}</p>
                    <p className="drill_param">L3: {drill_params.L3} {props.app.lang_data.mm}</p>
                </div>
            </div>
        </div>

        <div className="bottom_section glass shadow">
            <div className="info">
                <div className="item_1">
                    <p>{props.app.lang_data.size}: {stl_data.base.size_x}{props.app.lang_data.mm} * {stl_data.base.size_y}{props.app.lang_data.mm} * {stl_data.base.size_z}{props.app.lang_data.mm}</p>
                    <p className="divider">|</p>
                    <p>{props.app.lang_data.verticles}: {stl_data.base.verticles}</p>
                    <p className="divider">|</p>
                    <p className={stl_data.base.triangles>60000?"good":"bad"}>{props.app.lang_data.triangles}: {stl_data.base.triangles}</p>
                </div>
                <div className="item_1">
                    <p>{props.app.lang_data.size}: {stl_data.pattern.size_x}{props.app.lang_data.mm} * {stl_data.pattern.size_y}{props.app.lang_data.mm} * {stl_data.pattern.size_z}{props.app.lang_data.mm}</p>
                    <p className="divider">|</p>
                    <p>{props.app.lang_data.verticles}: {stl_data.pattern.verticles}</p>
                    <p className="divider">|</p>
                    <p>{props.app.lang_data.triangles}: {stl_data.pattern.triangles}</p>
                </div>
            </div>
            <div className="credentials">
                <p>{props.app.lang_data.rules}<br/>@ 2026</p>
            </div>
        </div>
    
        <Scene3d
            stl_base={stl_base}
            stl_pattern={stl_pattern}
            stl_union_1={stl_union_1}
            stl_union_2={stl_union_2}
            stl_data={stl_data}
            setStlData={setStlData}
            stl_state={stl_state}
            model_refs={model_refs}
            exportMergedSTL={exportMergedSTL}
        />

        <Library 
            lib_open={lib_open}
            setLibState={setLibState}
            setDrillParams={setDrillParams}
        />
    </div>
}

const mapStateToProps = (state) => {return state}
const mapDispatchToProps = (dispatch) => {return {
    "updateLang": (data) => {dispatch(updateLang(data))},
    "setLoading": (data) => {dispatch(setLoading(data))},
    "updateModal": (data) => {dispatch(updateModal(data))}
}}
export default connect(mapStateToProps, mapDispatchToProps)(Main)