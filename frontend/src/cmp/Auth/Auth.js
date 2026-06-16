import "./Auth.scss";
import { connect } from "react-redux";
import logo from "./media/logo.png";
import { updateModal } from "../../AppSlice";
import { useState } from "react";

const Auth = (props) => {
    //state
    const [key, set_key] = useState("")

    return <div className="auth">
        <img src={logo} alt="" />
        <div className="logo_name glass shadow">
            <p>{props.app.lang_data.name}</p>
        </div>
        <div className="form_field glass shadow">
            <h2 className="top">{props.app.lang_data.hello_phrase}</h2>
            <input type="text" placeholder={props.app.lang_data.hello_phrase} onChange={(e) => {set_key(e.target.value)}}/>
            <button className="enter" onClick={() => {props.checkAuth(key)}}>{props.app.lang_data.enter}</button>
        </div>
    </div>
}

const mapStateToProps = (state) => {return state}
const mapDispatchToProps = (dispatch) => {return {
    "updateModal": (data) => {dispatch(updateModal(data))},
}}
export default connect(mapStateToProps, mapDispatchToProps)(Auth)