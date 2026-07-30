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
});
