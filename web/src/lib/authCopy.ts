/**
 * Auth copy shared between the server actions and their tests. Lives outside
 * `actions.ts` because a "use server" module may export async functions only.
 */
export const UNREACHABLE = "We can't reach the sign-in service right now. Please try again in a moment.";
