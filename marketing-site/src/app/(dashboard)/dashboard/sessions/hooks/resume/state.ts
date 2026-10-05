import type { ResumeState } from './contracts'

export const initialState: ResumeState = {
    loading: false,
    actionStatus: null,
    taskStatus: null,
    activeTaskId: null,
}
