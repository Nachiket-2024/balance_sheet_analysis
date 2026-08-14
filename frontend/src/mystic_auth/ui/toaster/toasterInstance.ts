import { createToaster } from "@chakra-ui/react";

/**
 * App-wide toast queue singleton. Call `toaster.create({...})` from any component/hook to
 * surface a success/error/info message.
 *
 * Split into its own file (rather than living in toaster.tsx alongside the <Toaster />
 * component) so that file exports only a component, required by
 * react-refresh/only-export-components for reliable Vite Fast Refresh.
 */
export const toaster = createToaster({
    placement: "top-end",
    pauseOnPageIdle: true,
    // Top offset clears the sticky Navbar (h="16" = 4rem, plus a little
    // breathing room) so toasts render below it instead of over the
    // logout button. The other sides keep the library's 1rem default.
    offsets: { top: "5rem", right: "1rem", bottom: "1rem", left: "1rem" },
});
