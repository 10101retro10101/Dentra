import "./Loading.scss";
import logo from "../Auth/media/logo.png"
import { useState, useEffect } from "react";

const Loading = () => {
    //state
    const [dots, setDots] = useState(3)

    //handlers
    useEffect(() => {
        const timerId = setInterval(() => {
            setDots(prevDots => (prevDots === 0 ? 3 : prevDots - 1));
        }, 500);
        return () => clearInterval(timerId);
    }, []);

    return <div className="loading glass">
        <img src={logo} alt="" />
        <p className="descr">Загрузка{".".repeat(dots)}</p>
    </div>
}

export default Loading