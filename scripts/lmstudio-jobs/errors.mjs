/** Only controlled diagnostics may cross the CLI boundary. */
export class JobError extends Error {
  /** @param {string} code */
  constructor(code) { super(code); this.code = code; }
}
/** @param {unknown} error */
export function errorCode(error) {
  return error instanceof JobError ? error.code : 'operation_failed';
}
