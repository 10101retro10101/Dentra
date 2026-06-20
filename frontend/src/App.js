import "./App.scss";
import { useEffect, useRef, useState } from "react";
import { connect } from "react-redux";
import { setLoading, updateModal } from "./AppSlice";
import '@fontsource/jetbrains-mono';
import axios from "axios";
import './fonts.css';  

//cmps
import Auth from "./cmp/Auth/Auth";
import Modal from "./cmp/Modal/Modal";
import Loading from "./cmp/Loading/Loading";
import Main from "./cmp/Main/Main";

const App = (props) => {
  //state
  const app_ref = useRef(null);
  const [is_auth, setAuth] = useState(true)

  //handlers
  useEffect(() => {
    const handleMouseMove = (e) => {
      requestAnimationFrame(() => {
        if (!app_ref.current) return;
        const x = (e.clientX / window.innerWidth - 0.5) * 16;
        const y = (e.clientY / window.innerHeight - 0.5) * 16;
        app_ref.current.style.setProperty("--bg-x", `${50 + x}%`);
        app_ref.current.style.setProperty("--bg-y", `${50 + y}%`);
      });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  useEffect(() => {
    axios.get(`http://localhost:${props.app.backend_port}/app_version`).then(response => {
      if (response.data.code === 0){
        props.updateModal({title: props.app.lang_data.error_4})
      }
    })
  }, [])

  const checkAuth = (key) => {
    if (key === ""){props.updateModal({title: props.app.lang_data.error_1})}
    else{
      props.setLoading(true)
      axios.get(`http://localhost:${props.app.backend_port}/auth`, {params: {key: key}}).then(response => {
        props.setLoading(false)
        let response_code = response.data.code 
        if (response_code === 0){setAuth(true)}
        else if (response_code === 1){props.updateModal({title: props.app.lang_data.error_2})}
        else if (response_code === 2){props.updateModal({title: props.app.lang_data.error_3})}
      })
    }
  }

  return <div className="App" ref={app_ref}>
    {is_auth===true?
      <Main/>:
      <Auth 
      checkAuth={checkAuth}
    />
    }
    <Modal/>
    {props.app.is_loading===true?<Loading/>:""}
  </div>
}

const mapStateToProps = (state) => {return state}
const mapDispatchToProps = (dispatch) => {return {
  "updateModal": (data) => {dispatch(updateModal(data))},
  "setLoading": (data) => {dispatch(setLoading(data))}
}}
export default connect(mapStateToProps, mapDispatchToProps)(App)