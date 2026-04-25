/**
 * Init/destroy lifecycle helpers.
 *
 * Wrong pattern (allows re-init while still "initialized" if destroyed is true):
 *   if (this.is_initialized && !this.is_destroyed) return;
 *
 * Correct: bail if destroyed, then bail if already initialized; destroy() clears
 * is_initialized so state stays consistent if you later revive() for reuse.
 */

/**
 * @param {{ is_initialized?: boolean, is_destroyed?: boolean }} self
 * @returns {boolean} true if the init body should run
 */
export function shouldRunInit(self) {
  if (self.is_destroyed) return false;
  if (self.is_initialized) return false;
  return true;
}

/**
 * @param {{ is_initialized?: boolean }} self
 */
export function markInitialized(self) {
  self.is_initialized = true;
}

/**
 * @param {{ is_initialized?: boolean, is_destroyed?: boolean }} self
 * @param {() => void} [teardown]
 */
export function markDestroyed(self, teardown) {
  if (self.is_destroyed) return;
  if (typeof teardown === 'function') teardown();
  self.is_destroyed = true;
  self.is_initialized = false;
}

/**
 * Opt-in after destroy() when an instance should be initialized again (pools, tests).
 * @param {{ is_initialized?: boolean, is_destroyed?: boolean }} self
 */
export function reviveLifecycle(self) {
  self.is_destroyed = false;
}

/**
 * Class form: call beginInit() at start of init(); if true, run setup then endInit().
 * Call destroy(teardown) from dispose/teardown.
 */
export class LifecycleCapable {
  constructor() {
    this.is_initialized = false;
    this.is_destroyed = false;
  }

  /** @returns {boolean} */
  beginInit() {
    return shouldRunInit(this);
  }

  endInit() {
    markInitialized(this);
  }

  /** @param {() => void} [teardown] */
  destroy(teardown) {
    markDestroyed(this, teardown);
  }

  revive() {
    reviveLifecycle(this);
  }
}
