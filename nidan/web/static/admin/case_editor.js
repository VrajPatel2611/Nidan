/**
 * Case Editor Static JS (BUILD_PLAN T-021)
 *
 * Handles live token counting for LLM system prompts, tag chip inputs,
 * and C-4 validation helper interactions.
 */

document.addEventListener("DOMContentLoaded", function () {
  const promptEl = document.getElementById("system_prompt");
  if (promptEl) {
    promptEl.addEventListener("input", function () {
      const approxTokens = Math.round(promptEl.value.length / 4);
      const counter = document.getElementById("token-counter");
      if (counter) {
        counter.textContent = `≈ ${approxTokens} tokens`;
      }
    });
  }
});
