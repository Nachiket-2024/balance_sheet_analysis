import axios from "axios";
import settings from "../core/settings";

const api = axios.create({
    baseURL: settings.apiBaseUrl,
    withCredentials: true,
    // A tunnel or unavailable API must not leave the app's boot/session
    // screen spinning forever. Individual long-running operations can opt
    // into a larger timeout at the call site when their contract requires it.
    timeout: 15_000,
});

export default api;
