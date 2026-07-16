#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum SeriousIOSEngineState {
    SeriousIOSEngineStateIdle = 0,
    SeriousIOSEngineStateStarting = 1,
    SeriousIOSEngineStateInitialized = 2,
    SeriousIOSEngineStateFailed = 3,
    SeriousIOSEngineStateStopped = 4,
} SeriousIOSEngineState;

bool SeriousIOS_StartCoreEngine(void);
void SeriousIOS_StopCoreEngine(void);
SeriousIOSEngineState SeriousIOS_GetEngineState(void);
const char* SeriousIOS_GetEngineStartupError(void);

#ifdef __cplusplus
} // extern "C"
#endif
