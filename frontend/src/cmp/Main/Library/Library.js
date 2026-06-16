import "./Library.scss";
import drill_501 from "./media/drill_501.png";
import drill_199 from "./media/drill_199.png";
import { connect } from "react-redux";

const Library = (props) => {
    //state
    const drills = [
        {name:"501", img:drill_501, d1:1.5, L:7, L1:3.5, L2: 20, L3:0},
        {name:"199", img:drill_199, d1:1, L:13.5, L1:10, L2:26.5, L3:10}
    ]

    //handlers
    const drillParamsHandler = (index) => {
        props.setDrillParams(prev_data => {
            let cur_data = {...prev_data}
            cur_data.name = drills[index].name
            cur_data.d1 = drills[index].d1
            cur_data.L = drills[index].L
            cur_data.L1 = drills[index].L1
            cur_data.L2 = drills[index].L2
            cur_data.L3 = drills[index].L3
            return cur_data
        })
    }

    return <div className={"library " + props.lib_open}>
        <div className="lib_bg"></div>
        <div className="library_main">
            <button className="close" onClick={() => {props.setLibState("")}}></button>
            <ul className="drills">
                {drills.map((d_item, d_index) => {
                    return <li key={d_index} className="shadow glass" onClick={() => {drillParamsHandler(d_index)}}>
                        <img src={d_item.img} alt="" />
                        <div className="text_section">
                            <p className="name">{props.app.lang_data.drill_name}: {props.app.lang_data.drill} {d_item.name}</p>
                            <p>d1: {d_item.d1} {props.app.lang_data.mm}</p>
                            <p>L: {d_item.L} {props.app.lang_data.mm}</p>
                            <p>L1: {d_item.L1} {props.app.lang_data.mm}</p>
                            <p>L2: {d_item.L2} {props.app.lang_data.mm}</p>
                            <p>L3: {d_item.L3} {props.app.lang_data.mm}</p>
                        </div>
                    </li>
                })}
            </ul>
        </div>
    </div>
}

const mapStateToProps = (state) => {return state}
const mapDispatchToProps = (dispatch) => {return {
    
}}
export default connect(mapStateToProps, mapDispatchToProps)(Library)