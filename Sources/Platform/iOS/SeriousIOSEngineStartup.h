#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum SeriousIOSEngineState {
    SeriousIOSEngineStateIdle = 0,
    SeriousIOSEngineStateCoreStarting = 1,
    SeriousIOSEngineStateCoreInitialized = 2,
    SeriousIOSEngineStateGameStarting = 3,
    SeriousIOSEngineStateGameInitialized = 4,
    SeriousIOSEngineStateFailed = 5,
    SeriousIOSEngineStateStopped = 6,
} SeriousIOSEngineState;

bool SeriousIOS_StartCoreEngine(void);
bool SeriousIOS_StartGameRuntime(const char* gameIdentifier);
void SeriousIOS_StopEngine(void);
SeriousIOSEngineState SeriousIOS_GetEngineState(void);
const char* SeriousIOS_GetEngineStartupError(void);

#ifdef __cplusplus
} // extern "C"
#endif
