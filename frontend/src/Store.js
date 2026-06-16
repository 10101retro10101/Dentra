import {combineReducers, configureStore} from '@reduxjs/toolkit';
import AppSlice from './AppSlice';

const rootReducer = combineReducers({
    app:AppSlice
})

export const store = configureStore({
    reducer:rootReducer
})