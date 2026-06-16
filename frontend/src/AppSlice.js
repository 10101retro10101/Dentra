import { createSlice } from '@reduxjs/toolkit';

const loadLang = (lang) => {
    return require("./language.json")[lang]
}
const supported = ['ru', 'en', 'de', 'es', 'zh']
const user_locales = navigator.languages || [navigator.language];
const lang = user_locales.find(l => {
  const code = l.toLowerCase().split('-')[0];
  return supported.includes(code);
}) || 'en';
const backend_port = 8000

export const appSlice = createSlice({
    name: "app",
    initialState: {
        modal:{
            title: ""
        },
        backend_port: backend_port,
        lang: lang,
        lang_data: loadLang(lang),
        is_loading: false
    },
    reducers: {
        updateModal: (state, action) => {
            state.modal.title = action.payload.title 
        },
        updateLang: (state, action) => {
            state.lang = action.payload
            state.lang_data = loadLang(action.payload)
        },
        setLoading: (state, action) => {
            state.is_loading = action.payload
        }
    }
})
export const {updateModal, updateLang, setLoading} = appSlice.actions 
export default appSlice.reducer