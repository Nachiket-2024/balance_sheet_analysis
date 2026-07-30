import axios from "axios";
import settings from "../core/settings";

const api = axios.create({
    baseURL: settings.apiBaseUrl,
    withCredentials: true,
});

export default api;
