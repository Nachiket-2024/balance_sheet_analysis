import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn/ui's standard class-merging helper: clsx for conditionals, tailwind-merge to dedupe conflicting utility classes. */
export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}
