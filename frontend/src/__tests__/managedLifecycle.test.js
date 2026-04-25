import {
  shouldRunInit,
  markDestroyed,
  reviveLifecycle,
  LifecycleCapable,
} from '../utils/managedLifecycle';

describe('managedLifecycle', () => {
  test('shouldRunInit is false when destroyed', () => {
    const o = { is_initialized: false, is_destroyed: true };
    expect(shouldRunInit(o)).toBe(false);
  });

  test('shouldRunInit is false when already initialized', () => {
    const o = { is_initialized: true, is_destroyed: false };
    expect(shouldRunInit(o)).toBe(false);
  });

  test('shouldRunInit is true when fresh', () => {
    const o = { is_initialized: false, is_destroyed: false };
    expect(shouldRunInit(o)).toBe(true);
  });

  test('markDestroyed clears initialized and is idempotent', () => {
    const o = { is_initialized: true, is_destroyed: false };
    const fn = jest.fn();
    markDestroyed(o, fn);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(o.is_destroyed).toBe(true);
    expect(o.is_initialized).toBe(false);
    markDestroyed(o, fn);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test('after destroy, shouldRunInit is false until revive', () => {
    const o = { is_initialized: true, is_destroyed: false };
    markDestroyed(o);
    expect(shouldRunInit(o)).toBe(false);
    reviveLifecycle(o);
    expect(shouldRunInit(o)).toBe(true);
  });

  test('LifecycleCapable matches functional API', () => {
    const c = new LifecycleCapable();
    expect(c.beginInit()).toBe(true);
    c.endInit();
    expect(c.beginInit()).toBe(false);
    c.destroy();
    expect(c.beginInit()).toBe(false);
    c.revive();
    expect(c.beginInit()).toBe(true);
  });
});
