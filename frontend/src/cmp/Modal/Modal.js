import "./Modal.scss";
import { connect } from "react-redux";
import { updateModal } from "../../AppSlice";
import allert from "./media/allert.png";
import { useEffect, useState } from "react";

const Modal = (props) => {
    //state
    const [timer, setTimer] = useState(null)

    //handlers
    useEffect(() => {
        clearInterval(timer)
        setTimer(setTimeout(() => {props.updateModal({title: "", message: ""})}, 5000))
    }, [props.app.modal])

    return <div className={"modal glass shadow " + ((props.app.modal.title==="")?"disactive":"active")}>
        <img src={allert} alt="" />
        <p className="title">{props.app.modal.title}</p>
    </div>
}

const mapStateToProps = (state) => {return state}
const mapDispatchToProps = (dispatch) => {return {
  "updateModal": (data) => {dispatch(updateModal(data))},
}}
export default connect(mapStateToProps, mapDispatchToProps)(Modal)